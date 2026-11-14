"""Mémoire à long terme de Friday : faits sur l'utilisateur dans SQLite + FTS5.

- Table `facts` (fait, catégorie, source, date, confiance, clé) et index plein
  texte `facts_fts` (unicode61 sans accents), tenus à jour ensemble.
- `forget` efface vraiment : `secure_delete` (pages remises à zéro), fusion de
  l'index FTS5 (`optimize`) et checkpoint du WAL.
- Chaque mémorisation et chaque oubli est audité avec une empreinte seulement.

Chroma n'est pas utilisé : il dépend d'onnxruntime, absent sous Python 3.15.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from friday.audit import AuditLog
from friday.memory.extractor import ExtractedFact, FactExtractor, RuleBasedExtractor

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    category    TEXT NOT NULL,
    source      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    confidence  REAL NOT NULL,
    key         TEXT
);
CREATE INDEX IF NOT EXISTS facts_key ON facts(key);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    text, category, tokenize = 'unicode61 remove_diacritics 2'
);
"""

# Mots vides retirés des requêtes (forme sans accents, minuscules).
_STOPWORDS = frozenset("""
a au aux avec ce ces cet cette c ca d de des du elle en es est et etre il ils
j je l la le les leur lui m ma me mes moi mon n ne nous on ou par pas pour qu
que qui quoi quel quelle quels quelles s sa se ses son sur t ta te tes toi ton
tu un une vos votre vous y suis as ai sont etait souviens souvient rappelles
rappelle sais sait dis dit oublie oublies efface effacer tout toute comment
quand ou pourquoi est-ce friday thaine utilisateur
""".split())


@dataclass(frozen=True)
class Fact:
    id: int
    text: str
    category: str
    source: str
    created_at: str
    confidence: float
    key: str | None = None


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _fold(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in norm if not unicodedata.combining(c))


def query_terms(query: str) -> list[str]:
    """Termes FTS5 d'une question : mots utiles, racine grossière, préfixe."""
    terms: list[str] = []
    for word in re.findall(r"[a-z0-9]+", _fold(query)):
        if word in _STOPWORDS or len(word) < 3:
            continue
        stem = word[:-2] if len(word) >= 7 else word   # préférée → prefer*, souviens → souvi*
        term = f'"{stem}"*'
        if term not in terms:
            terms.append(term)
    return terms


class MemoryStore:
    def __init__(
        self,
        db_path: str | Path,
        audit: AuditLog,
        extractor: FactExtractor | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = audit
        self.extractor: FactExtractor = extractor or RuleBasedExtractor()
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA secure_delete=ON")
        self._conn.executescript(_SCHEMA)

    # ── écriture ────────────────────────────────────────────────────────────
    def remember(
        self,
        fact: str | ExtractedFact,
        *,
        category: str = "general",
        source: str = "user",
        confidence: float = 1.0,
        key: str | None = None,
    ) -> Fact:
        """Mémorise un fait. Même texte = rafraîchi ; même clé = remplacé."""
        if isinstance(fact, ExtractedFact):
            text, category, key, confidence = fact.text, fact.category, fact.key, fact.confidence
        else:
            text = fact
        text = " ".join(text.split())
        if not text:
            raise ValueError("fait vide")
        confidence = max(0.0, min(1.0, confidence))
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                stale = [r[0] for r in self._conn.execute(
                    "SELECT id FROM facts WHERE lower(text) = lower(?) OR (? IS NOT NULL AND key = ?)",
                    (text, key, key))]
                self._delete_ids(stale)
                cur = self._conn.execute(
                    "INSERT INTO facts (text, category, source, created_at, confidence, key) "
                    "VALUES (?, ?, ?, ?, ?, ?)", (text, category, source, now, confidence, key))
                fid = cur.lastrowid
                self._conn.execute("INSERT INTO facts_fts (rowid, text, category) VALUES (?, ?, ?)",
                                   (fid, text, category))
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        self.audit.append("memory", "memory.remember", {
            "fact_id": fid, "text_sha256": _fingerprint(text), "category": category,
            "source": source, "confidence": confidence, "replaced": len(stale),
        })
        return Fact(fid, text, category, source, now, confidence, key)

    def learn(self, utterance: str, source: str = "user") -> list[Fact]:
        """Extrait les faits d'un énoncé et les mémorise."""
        return [self.remember(f, source=source) for f in self.extractor.extract(utterance)]

    def forget(self, query: str) -> int:
        """Droit à l'oubli : efface les faits contenant tous les mots utiles de la requête."""
        terms = query_terms(query)
        if not terms:
            return 0
        with self._lock:
            ids = [r[0] for r in self._conn.execute(
                "SELECT rowid FROM facts_fts WHERE facts_fts MATCH ?", (" AND ".join(terms),))]
            self._erase(ids)
        self.audit.append("memory", "memory.forget", {
            "query_sha256": _fingerprint(query), "count": len(ids), "fact_ids": ids})
        return len(ids)

    def forget_id(self, fact_id: int) -> bool:
        with self._lock:
            exists = self._conn.execute("SELECT 1 FROM facts WHERE id = ?", (fact_id,)).fetchone()
            if exists:
                self._erase([fact_id])
        self.audit.append("memory", "memory.forget", {"count": int(bool(exists)), "fact_ids": [fact_id]})
        return bool(exists)

    def forget_all(self) -> int:
        with self._lock:
            ids = [r[0] for r in self._conn.execute("SELECT id FROM facts")]
            self._erase(ids)
        self.audit.append("memory", "memory.forget_all", {"count": len(ids)})
        return len(ids)

    # ── lecture ─────────────────────────────────────────────────────────────
    def recall(self, query: str, k: int = 5) -> list[Fact]:
        """Faits les plus pertinents (BM25 pondéré par la confiance)."""
        terms = query_terms(query)
        if not terms or k <= 0:
            return []
        rows = self._conn.execute(
            "SELECT f.id, f.text, f.category, f.source, f.created_at, f.confidence, f.key "
            "FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid "
            "WHERE facts_fts MATCH ? ORDER BY bm25(facts_fts) / f.confidence LIMIT ?",
            (" OR ".join(terms), k)).fetchall()
        return [Fact(*r) for r in rows]

    def all(self) -> list[Fact]:
        rows = self._conn.execute(
            "SELECT id, text, category, source, created_at, confidence, key FROM facts ORDER BY id")
        return [Fact(*r) for r in rows]

    def context_for(self, question: str, k: int = 5, max_chars: int = 600) -> str:
        """Court bloc à placer en tête du message envoyé à Claude ("" si rien)."""
        facts = self.recall(question, k)
        if not facts:
            return ""
        lines = ["[mémoire] Faits connus sur l'utilisateur (à utiliser seulement si utile) :"]
        size = len(lines[0])
        for f in facts:
            line = f"- {f.text}"
            if size + len(line) + 1 > max_chars:
                break
            lines.append(line)
            size += len(line) + 1
        return "\n".join(lines) if len(lines) > 1 else ""

    def close(self) -> None:
        self._conn.close()

    # ── interne ─────────────────────────────────────────────────────────────
    def _delete_ids(self, ids: list[int]) -> None:
        for fid in ids:
            self._conn.execute("DELETE FROM facts WHERE id = ?", (fid,))
            self._conn.execute("DELETE FROM facts_fts WHERE rowid = ?", (fid,))

    def _erase(self, ids: list[int]) -> None:
        """Suppression définitive : lignes, segments FTS fusionnés, WAL vidé."""
        if not ids:
            return
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._delete_ids(ids)
            self._conn.execute("INSERT INTO facts_fts (facts_fts) VALUES ('optimize')")
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
