"""Boucle texte minimale : `python -m friday`."""

from __future__ import annotations

from .audit import AuditLog
from .conductor import Conductor
from .config import load_config
from .guardrails import GuardrailsEngine
from .log import setup_logging
from .soul import load_soul


def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level, cfg.log_json)
    soul = load_soul(cfg.soul_path)
    audit = AuditLog(cfg.audit_db_path)
    guardrails = GuardrailsEngine(cfg.guardrails.actions, cfg.guardrails.allowed_domains, audit)
    conductor = Conductor(guardrails=guardrails, audit=audit)
    print(f"{soul['IDENTITY']['name']} prêt. Ctrl-D pour quitter.")
    try:
        while True:
            text = input("> ")
            d = conductor.handle(text)
            print(f"  intention={d.intent.value} agent={d.agent} confiance={d.confidence}")
    except (EOFError, KeyboardInterrupt):
        print()
    finally:
        audit.close()


if __name__ == "__main__":
    main()
