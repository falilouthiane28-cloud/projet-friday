"""Cerveau Claude Code : `claude -p` en mode headless, sans outils.

- Conversation suivie : la session Claude Code est reprise avec `--resume`.
- Aucun outil (`--tools ""`), aucun serveur MCP, aucun réglage utilisateur : Claude ne
  peut rien exécuter sur la machine. Les actions passeront plus tard par les guardrails.
- Connexion : abonnement Claude (`claude` puis `/login`, une fois) ou clé
  `ANTHROPIC_API_KEY` dans l'environnement.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .conductor import RoutingDecision
from .log import get_logger

# Exécute une commande, retourne (code, stdout).
Runner = Callable[[Sequence[str], Mapping[str, str], Path, float], Awaitable[tuple[int, str]]]

LOGIN_HELP = ("Claude Code n'est pas connecté. Ouvrez un terminal, lancez « claude » puis « /login », "
              "ou ajoutez une clé ANTHROPIC_API_KEY.")

# Variables injectées par une session Claude Code parente : à ne pas transmettre.
_HOST_ENV = re.compile(r"^(CLAUDECODE|CLAUDE_CODE_|CLAUDE_AGENT_SDK|CLAUDE_PID|CLAUDE_EFFORT|CLAUDE_PREVIEW|ANTHROPIC_BASE_URL$)")


class ClaudeError(RuntimeError):
    pass


def _version_key(path: Path) -> tuple[int, ...]:
    for part in path.parts:
        if re.fullmatch(r"\d+(\.\d+)+", part):
            return tuple(int(x) for x in part.split("."))
    return (0,)


def find_claude_binary(configured: str | None = None, home: Path | None = None) -> Path | None:
    """Binaire `claude` : config, PATH, installations courantes, puis celui de l'app Claude."""
    if configured:
        p = Path(configured).expanduser()
        return p if p.exists() else None
    if found := shutil.which("claude"):
        return Path(found)
    home = home or Path.home()
    for p in (home / ".claude/local/claude", home / ".local/bin/claude",
              Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude")):
        if p.exists():
            return p
    bundled = list((home / "Library/Application Support/Claude/claude-code").glob(
        "*/*/claude.app/Contents/MacOS/claude"))
    return max(bundled, key=_version_key) if bundled else None


def clean_env(env: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not _HOST_ENV.match(k)}


def system_prompt(soul: Mapping[str, Any], voice: bool) -> str:
    ident = soul.get("IDENTITY", {})
    rules = soul.get("COMMUNICATION_RULES", [])
    values = soul.get("CORE_VALUES", [])
    lines = [
        f"Tu es {ident.get('name', 'FRIDAY')}, {ident.get('role', 'assistante personnelle')} de "
        f"{ident.get('master', 'ton utilisateur')}, sur son Mac.",
        f"Ton : {ident.get('tone', 'professionnel')}. Langue : français. {ident.get('address', '')}.",
        "Valeurs : " + " ; ".join(values) + ".",
        "Règles : " + " ; ".join(rules) + ".",
        "Tu n'as aucun outil pour l'instant : n'affirme jamais avoir fait une action sur la machine.",
    ]
    if voice:
        lines.append("Cette réponse sera lue à voix haute : 1 à 2 phrases, sans markdown, sans liste, "
                     "sans emoji, nombres écrits simplement.")
    else:
        lines.append("Réponse affichée dans une petite fenêtre de discussion : concise, markdown léger accepté.")
    return "\n".join(lines)


async def run_process(cmd: Sequence[str], env: Mapping[str, str], cwd: Path, timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, env=dict(env), cwd=cwd, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise ClaudeError(f"Claude n'a pas répondu en {int(timeout)} secondes.") from None
    return proc.returncode or 0, out.decode(errors="replace")


def parse_result(code: int, out: str) -> tuple[str, str | None]:
    """Sortie `--output-format json` → (texte, session_id). Lève ClaudeError si échec."""
    try:
        data = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except json.JSONDecodeError:
        raise ClaudeError(f"Réponse illisible de Claude Code (code {code}).") from None
    result = str(data.get("result") or "").strip()
    if data.get("is_error") or code != 0:
        if "login" in result.lower() or "logged in" in result.lower() or "api key" in result.lower():
            raise ClaudeError(LOGIN_HELP)
        raise ClaudeError(result or f"Claude Code a échoué (code {code}).")
    if not result:
        raise ClaudeError("Claude a renvoyé une réponse vide.")
    return result, data.get("session_id")


class ClaudeCodeBrain:
    def __init__(
        self,
        binary: Path,
        soul: Mapping[str, Any],
        workdir: Path,
        model: str = "sonnet",
        timeout: float = 60,
        runner: Runner = run_process,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.binary = binary
        self.soul = soul
        self.workdir = workdir
        self.model = model
        self.timeout = timeout
        self.runner = runner
        self.env = clean_env(env if env is not None else os.environ)
        self.session_id: str | None = None
        self._log = get_logger("friday.claude")

    def reset(self) -> None:
        """Nouvelle conversation."""
        self.session_id = None

    def command(self, text: str, voice: bool) -> list[str]:
        cmd = [str(self.binary), "-p", text, "--output-format", "json", "--model", self.model,
               "--tools", "", "--strict-mcp-config", "--setting-sources", "",
               "--system-prompt", system_prompt(self.soul, voice)]
        if self.session_id:
            cmd += ["--resume", self.session_id]
        return cmd

    async def respond(self, text: str, decision: RoutingDecision, source: str = "text") -> str:
        self.workdir.mkdir(parents=True, exist_ok=True)
        code, out = await self.runner(self.command(text, source == "voice"), self.env, self.workdir, self.timeout)
        try:
            reply, session = parse_result(code, out)
        except ClaudeError as exc:
            if self.session_id and str(exc) != LOGIN_HELP:   # session perdue : conversation neuve
                self._log.warning("claude.resume_failed")
                self.session_id = None
                code, out = await self.runner(self.command(text, source == "voice"), self.env, self.workdir, self.timeout)
                reply, session = parse_result(code, out)
            else:
                raise
        self.session_id = session or self.session_id
        return reply
