import pytest

from friday.config import load_config
from friday.soul import load_soul


def test_config_yaml(config):
    assert config.name == "FRIDAY"
    assert config.guardrails.actions["file.delete"] == 1
    assert config.audit_db_path.name == "audit.db"


def test_soul(config):
    soul = load_soul(config.soul_path)
    assert soul["IDENTITY"]["name"] == "FRIDAY"
    assert "REFUSAL_LIST" in soul


def test_tier0_refuse_en_config(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("guardrails:\n  actions:\n    file.read: 0\n")
    with pytest.raises(ValueError):
        load_config(p)
