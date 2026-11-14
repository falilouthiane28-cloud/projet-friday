"""Point d'entrée.

    python -m friday           → boucle texte
    python -m friday --voice   → pipeline vocal (binaire Swift friday-voice)
"""

from __future__ import annotations

import asyncio
import sys

from .audit import AuditLog
from .brain import LocalBrain
from .conductor import Conductor
from .config import FridayConfig, load_config
from .guardrails import GuardrailsEngine
from .log import setup_logging
from .soul import load_soul
from .voice import VoiceBridge


async def text_loop(conductor: Conductor, brain: LocalBrain) -> None:
    loop = asyncio.get_running_loop()
    while True:
        try:
            text = await loop.run_in_executor(None, input, "> ")
        except EOFError:
            print()
            return
        d = conductor.handle(text)
        reply = await brain.respond(text, d)
        print(f"  [{d.intent.value} → {d.agent}, {d.confidence}] {reply}")


async def voice_loop(cfg: FridayConfig, conductor: Conductor, brain: LocalBrain, audit: AuditLog) -> int:
    if not cfg.voice_binary.exists():
        print(f"Binaire introuvable : {cfg.voice_binary}\nCompiler : cd voice && swift build -c release", file=sys.stderr)
        return 1
    bridge = VoiceBridge([str(cfg.voice_binary), "--locale", cfg.voice_locale], conductor, brain, audit)
    print("Dites « Hey Friday… ». Ctrl-C pour quitter.")
    try:
        return await bridge.run()
    finally:
        await bridge.shutdown()


def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level, cfg.log_json)
    soul = load_soul(cfg.soul_path)
    audit = AuditLog(cfg.audit_db_path)
    guardrails = GuardrailsEngine(cfg.guardrails.actions, cfg.guardrails.allowed_domains, audit)
    conductor = Conductor(guardrails=guardrails, audit=audit)
    brain = LocalBrain()
    try:
        if "--voice" in sys.argv:
            sys.exit(asyncio.run(voice_loop(cfg, conductor, brain, audit)))
        print(f"{soul['IDENTITY']['name']} prêt. Ctrl-D pour quitter.")
        asyncio.run(text_loop(conductor, brain))
    except KeyboardInterrupt:
        print()
    finally:
        audit.close()


if __name__ == "__main__":
    main()
