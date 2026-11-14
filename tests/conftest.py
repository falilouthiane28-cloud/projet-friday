import pytest

from friday.audit import AuditLog
from friday.config import load_config
from friday.guardrails import GuardrailsEngine


@pytest.fixture
def audit(tmp_path):
    log = AuditLog(tmp_path / "audit.db")
    yield log
    log.close()


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def engine(config, audit):
    return GuardrailsEngine(config.guardrails.actions, config.guardrails.allowed_domains, audit)
