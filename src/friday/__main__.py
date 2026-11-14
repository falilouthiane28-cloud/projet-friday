"""Point d'entrée.

    python -m friday           → boucle texte
    python -m friday --voice   → pipeline vocal (binaire Swift friday-voice)
    python -m friday --serve   → cœur en sous-processus de l'app friday-app (JSON Lines)
"""

from __future__ import annotations

import asyncio
import sys

from .audit import AuditLog
from .brain import Brain, HybridBrain, LocalBrain
from .claude_brain import PersistentClaudeBrain, find_claude_binary
from .conductor import Conductor
from .config import FridayConfig, load_config
from .guardrails import GuardrailsEngine
from .log import setup_logging
from .soul import load_soul
from .voice import CoreServer, VoiceBridge


async def text_loop(conductor: Conductor, brain: Brain) -> None:
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


async def voice_loop(cfg: FridayConfig, conductor: Conductor, brain: Brain, audit: AuditLog) -> int:
    if not cfg.voice_binary.exists():
        print(f"Binaire introuvable : {cfg.voice_binary}\nCompiler : cd voice && swift build -c release", file=sys.stderr)
        return 1
    bridge = VoiceBridge([str(cfg.voice_binary), "--locale", cfg.voice_locale], conductor, brain, audit)
    print("Dites « Hey Friday… ». Ctrl-C pour quitter.")
    try:
        return await bridge.run()
    finally:
        await bridge.shutdown()


def make_brain(cfg: FridayConfig, soul: dict) -> Brain:
    local = LocalBrain()
    if cfg.brain_engine != "claude-code":
        return local
    binary = find_claude_binary(cfg.claude_binary)
    if binary is None:
        print("Claude Code introuvable : réponses locales seulement.", file=sys.stderr)
        return local
    workdir = cfg.audit_db_path.parent / "claude"      # sessions Claude Code de Friday, hors du dépôt
    return HybridBrain(local, PersistentClaudeBrain(binary, soul, workdir, cfg.claude_model, cfg.claude_timeout_s))


def main() -> None:
    i = sys.argv.index("--config") if "--config" in sys.argv else -1
    cfg = load_config(sys.argv[i + 1] if 0 <= i < len(sys.argv) - 1 else None)
    setup_logging(cfg.log_level, cfg.log_json)
    soul = load_soul(cfg.soul_path)
    audit = AuditLog(cfg.audit_db_path)
    guardrails = GuardrailsEngine(cfg.guardrails.actions, cfg.guardrails.allowed_domains, audit)
    conductor = Conductor(guardrails=guardrails, audit=audit)
    brain = make_brain(cfg, soul)
    try:
        if "--serve" in sys.argv:
            server = CoreServer(conductor, brain, audit, name=soul["IDENTITY"]["name"])
            sys.exit(asyncio.run(server.run()))
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
