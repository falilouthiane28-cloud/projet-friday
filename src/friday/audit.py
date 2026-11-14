"""Journal d'audit SQLite : mode WAL, ajout seul, chaînage de hachés.

- UPDATE et DELETE sont refusés par des triggers SQLite.
- Chaque ligne stocke le SHA-256 de la ligne précédente : toute altération
  hors de l'API (édition directe du fichier) est détectée par `verify_chain()`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

    @property
    def journal_mode(self) -> str:
        return self._conn.execute("PRAGMA journal_mode").fetchone()[0]

    def append(self, actor: str, event: str, payload: dict[str, Any] | None = None) -> AuditEntry:
        body = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
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

    def verify_chain(self) -> bool:
        prev = GENESIS_HASH
        for r in self._conn.execute(
            "SELECT ts, actor, event, payload, prev_hash, hash FROM audit_log ORDER BY id"
        ):
            ts, actor, event, payload, prev_hash, h = r
            if prev_hash != prev or _digest(prev_hash, ts, actor, event, payload) != h:
                return False
            prev = h
        return True

    def close(self) -> None:
        self._conn.close()
