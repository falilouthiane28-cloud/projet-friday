import sqlite3

import pytest


def test_mode_wal(audit):
    assert audit.journal_mode == "wal"


def test_chainage(audit):
    a = audit.append("test", "e1", {"x": 1})
    b = audit.append("test", "e2", {"x": 2})
    assert b.prev_hash == a.hash
    assert audit.verify_chain()


@pytest.mark.parametrize("sql", ["UPDATE audit_log SET event='x'", "DELETE FROM audit_log"])
def test_ajout_seul(audit, sql):
    audit.append("test", "e1")
    with pytest.raises(sqlite3.IntegrityError, match="ajout seul"):
        audit._conn.execute(sql)


def test_alteration_detectee(audit):
    audit.append("test", "e1", {"x": 1})
    audit.append("test", "e2", {"x": 2})
    conn = audit._conn
    conn.execute("DROP TRIGGER audit_no_update")          # attaquant avec accès au fichier
    conn.execute("UPDATE audit_log SET payload='{\"x\": 9}' WHERE id=1")
    assert not audit.verify_chain()
