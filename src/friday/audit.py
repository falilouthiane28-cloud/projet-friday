"""Journal d'audit SQLite : mode WAL, ajout seul, chaînage de hachés.

- UPDATE et DELETE sont refusés par des triggers SQLite.
- Chaque ligne stocke le SHA-256 de la ligne précédente : toute altération
  hors de l'API (édition directe du fichier) est détectée par `verify()`.
- Une ancre (`<base>.head` : nombre de lignes et dernier haché) est réécrite après chaque
  ajout : une troncature de la fin du journal est détectée elle aussi.
- Les identifiants reconnus (clés, jetons) sont masqués avant écriture (`redact`).

Vérification : `python -m friday --verify-audit`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redact import redact

GENESIS_HASH = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    actor      TEXT NOT NULL,
    event      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    prev_hash  TEXT NOT NULL,
    hash       TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log est en ajout seul'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log est en ajout seul'); END;
"""


@dataclass(frozen=True)
class AuditEntry:
    id: int
    ts: str
    actor: str
    event: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    count: int
    broken_id: int | None = None      # première ligne fautive
    reason: str = ""

    def __str__(self) -> str:
        if self.ok:
            return f"Audit intègre : {self.count} entrées, chaîne et ancre vérifiées."
        where = f" (entrée #{self.broken_id})" if self.broken_id is not None else ""
        return f"AUDIT FALSIFIÉ{where} : {self.reason}"


def _digest(prev_hash: str, ts: str, actor: str, event: str, payload: str) -> str:
    material = "\x1f".join((prev_hash, ts, actor, event, payload))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self.head_path = self.db_path.with_name(self.db_path.name + ".head")
        if not self.head_path.exists():
            self._anchor_existing()

    def _anchor_existing(self) -> None:
        """Base d'avant l'ancre (ou ancre effacée) : on ancre l'état actuel et on le trace."""
        row = self._conn.execute("SELECT id, hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return
        self._write_head(row[0], row[1])
        self.append("audit", "audit.anchor_created", {"after_id": row[0]})

    @property
    def journal_mode(self) -> str:
        return self._conn.execute("PRAGMA journal_mode").fetchone()[0]

    def append(self, actor: str, event: str, payload: dict[str, Any] | None = None) -> AuditEntry:
        body = json.dumps(redact(payload or {}), ensure_ascii=False, sort_keys=True, default=str)
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
                prev = row[0] if row else GENESIS_HASH
                h = _digest(prev, ts, actor, event, body)
                cur = self._conn.execute(
                    "INSERT INTO audit_log (ts, actor, event, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)",
                    (ts, actor, event, body, prev, h),
                )
                self._write_head(cur.lastrowid, h)      # sous le verrou d'écriture SQLite (multi-processus)
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return AuditEntry(cur.lastrowid, ts, actor, event, json.loads(body), prev, h)

    def entries(self) -> list[AuditEntry]:
        rows = self._conn.execute(
            "SELECT id, ts, actor, event, payload, prev_hash, hash FROM audit_log ORDER BY id"
        ).fetchall()
        return [AuditEntry(r[0], r[1], r[2], r[3], json.loads(r[4]), r[5], r[6]) for r in rows]

    def _write_head(self, count: int, h: str) -> None:
        tmp = self.head_path.with_name(self.head_path.name + ".tmp")
        tmp.write_text(json.dumps({"id": count, "hash": h}), encoding="utf-8")
        os.replace(tmp, self.head_path)

    def verify(self) -> ChainReport:
        """Vérifie chaque maillon (haché, lien au précédent, ids contigus) puis l'ancre de fin."""
        prev, count, last_id = GENESIS_HASH, 0, 0
        for r in self._conn.execute(
            "SELECT id, ts, actor, event, payload, prev_hash, hash FROM audit_log ORDER BY id"
        ):
            rid, ts, actor, event, payload, prev_hash, h = r
            if rid != last_id + 1:
                return ChainReport(False, count, rid, f"entrées manquantes avant #{rid}")
            if prev_hash != prev:
                return ChainReport(False, count, rid, "lien rompu avec l'entrée précédente")
            if _digest(prev_hash, ts, actor, event, payload) != h:
                return ChainReport(False, count, rid, "contenu modifié (haché invalide)")
            prev, count, last_id = h, count + 1, rid
        if self.head_path.exists():
            try:
                head = json.loads(self.head_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return ChainReport(False, count, None, "ancre illisible")
            if head.get("id") != last_id or head.get("hash") != (prev if count else GENESIS_HASH):
                if isinstance(head.get("id"), int) and head["id"] > last_id:
                    return ChainReport(False, count, None, f"fin du journal supprimée ({head['id'] - last_id} entrées)")
                return ChainReport(False, count, None, "l'ancre ne correspond pas à la dernière entrée")
        elif count:
            return ChainReport(False, count, None, "ancre absente")
        return ChainReport(True, count)

    def verify_chain(self) -> bool:
        return self.verify().ok

    def close(self) -> None:
        self._conn.close()
