"""Point d'entrée.

    python -m friday           → boucle texte
    python -m friday --voice   → pipeline vocal (binaire Swift friday-voice)
    python -m friday --serve   → cœur en sous-processus de l'app friday-app (JSON Lines)
    python -m friday --verify-audit → vérifie la chaîne d'audit (code 1 si falsifiée)
"""

from __future__ import annotations

import asyncio
import sys

from .audit import AuditLog
from .memory import MemoryStore
from .memory.claude_extractor import ClaudeFactExtractor
from .brain import Brain, HybridBrain, LocalBrain
from .claude_brain import PersistentClaudeBrain, find_claude_binary
from .conductor import Conductor
from .config import FridayConfig, load_config
from .guardrails import GuardrailsEngine
from .log import setup_logging
from .soul import load_soul
from .agents import AgentRunner, default_registry, delegate_tools
from .tools import HomeAssistantClient, ToolGateway, default_tools, home_tools
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


def make_brain(cfg: FridayConfig, soul: dict, audit: AuditLog | None = None) -> Brain:
    local = LocalBrain()
    if cfg.brain_engine != "claude-code":
        return local
    binary = find_claude_binary(cfg.claude_binary)
    if binary is None:
        print("Claude Code introuvable : réponses locales seulement.", file=sys.stderr)
        return local
    workdir = cfg.audit_db_path.parent / "claude"      # sessions Claude Code de Friday, hors du dépôt
    memory = None
    if audit is not None:
        extractor = ClaudeFactExtractor(binary, cfg.audit_db_path.parent / "claude-memory", cfg.memory_model)
        memory = MemoryStore(cfg.audit_db_path.parent / "memory.db", audit, deep_extractor=extractor)
    return HybridBrain(local, PersistentClaudeBrain(binary, soul, workdir, cfg.claude_model, cfg.claude_timeout_s), memory)


def verify_audit(cfg: FridayConfig) -> int:
    if not cfg.audit_db_path.exists():
        print(f"Aucun journal d'audit : {cfg.audit_db_path}")
        return 1
    audit = AuditLog(cfg.audit_db_path)
    try:
        report = audit.verify()
    finally:
        audit.close()
    print(report)
    return 0 if report.ok else 1


def main() -> None:
    i = sys.argv.index("--config") if "--config" in sys.argv else -1
    cfg = load_config(sys.argv[i + 1] if 0 <= i < len(sys.argv) - 1 else None)
    setup_logging(cfg.log_level, cfg.log_json)
    if "--verify-audit" in sys.argv:
        sys.exit(verify_audit(cfg))
    soul = load_soul(cfg.soul_path)
    audit = AuditLog(cfg.audit_db_path)
    guardrails = GuardrailsEngine(cfg.guardrails.actions, cfg.guardrails.allowed_domains, audit)
    conductor = Conductor(guardrails=guardrails, audit=audit)
    brain = make_brain(cfg, soul, audit)
    try:
        if "--serve" in sys.argv:
            registry = default_registry()
            home = HomeAssistantClient(cfg.ha_url, cfg.ha_keychain_service, cfg.ha_timeout_s)
            gateway = ToolGateway(default_tools(cfg.default_city) + home_tools(home), guardrails, audit,
                                  allowed=registry.allowed_tools)
            if binary := getattr(getattr(brain, "remote", None), "binary", None):
                runner = AgentRunner(registry, gateway, binary, cfg.audit_db_path.parent / "claude-agents")
                gateway.add_tools(delegate_tools(registry, runner))
            server = CoreServer(conductor, brain, audit, name=soul["IDENTITY"]["name"], gateway=gateway)
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
