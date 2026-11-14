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
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
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


_SENTENCE_END = re.compile(r"([.!?…]+[»\"')\]]*)(\s+)|(\n+)")


class SentenceSplitter:
    """Découpe un flux de texte en phrases complètes (pour parler dès la première)."""

    def __init__(self) -> None:
        self.buffer = ""

    def feed(self, delta: str) -> list[str]:
        self.buffer += delta
        out: list[str] = []
        while m := _SENTENCE_END.search(self.buffer):
            sentence, self.buffer = self.buffer[: m.end()].strip(), self.buffer[m.end():]
            if sentence:
                out.append(sentence)
        return out

    def flush(self) -> list[str]:
        rest, self.buffer = self.buffer.strip(), ""
        return [rest] if rest else []


def parse_stream_line(line: str) -> tuple[str, Any] | None:
    """Ligne `--output-format stream-json` → ("delta", texte) ou ("result", dict) ; None sinon."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("type") == "stream_event":
        delta = (data.get("event") or {}).get("delta") or {}
        if delta.get("type") == "text_delta" and delta.get("text"):
            return "delta", delta["text"]
        return None
    if data.get("type") == "result":
        return "result", data
    return None


# Exécute une commande en flux : produit les lignes de stdout.
StreamRunner = Callable[[Sequence[str], Mapping[str, str], Path, float], AsyncIterator[str]]


async def stream_process(cmd: Sequence[str], env: Mapping[str, str], cwd: Path, timeout: float) -> AsyncIterator[str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, env=dict(env), cwd=cwd, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=1 << 22,
    )
    assert proc.stdout
    try:
        async with asyncio.timeout(timeout):
            async for raw in proc.stdout:
                yield raw.decode(errors="replace")
            await proc.wait()
    except TimeoutError:
        raise ClaudeError(f"Claude n'a pas répondu en {int(timeout)} secondes.") from None
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


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
        stream_runner: StreamRunner = stream_process,
    ) -> None:
        self.binary = binary
        self.soul = soul
        self.workdir = workdir
        self.model = model
        self.timeout = timeout
        self.runner = runner
        self.stream_runner = stream_runner
        self.env = clean_env(env if env is not None else os.environ)
        self.session_id: str | None = None
        self._log = get_logger("friday.claude")

    def reset(self) -> None:
        """Nouvelle conversation."""
        self.session_id = None

    def command(self, text: str, voice: bool, stream: bool = False) -> list[str]:
        fmt = ["stream-json", "--verbose", "--include-partial-messages"] if stream else ["json"]
        cmd = [str(self.binary), "-p", text, "--output-format", *fmt, "--model", self.model,
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

    async def stream(self, text: str, decision: RoutingDecision, source: str = "text") -> AsyncIterator[str]:
        """Produit le texte de la réponse au fil de l'eau (morceaux bruts de Claude)."""
        self.workdir.mkdir(parents=True, exist_ok=True)
        for attempt in (0, 1):
            got_text = False
            result: dict[str, Any] | None = None
            async for line in self.stream_runner(self.command(text, source == "voice", stream=True),
                                                 self.env, self.workdir, self.timeout):
                parsed = parse_stream_line(line)
                if parsed is None:
                    continue
                kind, value = parsed
                if kind == "delta":
                    got_text = True
                    yield value
                else:
                    result = value
            try:
                if result is None:
                    raise ClaudeError("Claude Code s'est arrêté sans réponse.")
                _, session = parse_result(1 if result.get("is_error") else 0, json.dumps(result))
                self.session_id = session or self.session_id
                return
            except ClaudeError as exc:
                # Session perdue avant tout texte : on réessaie une fois avec une conversation neuve.
                if attempt == 0 and not got_text and self.session_id and str(exc) != LOGIN_HELP:
                    self._log.warning("claude.resume_failed")
                    self.session_id = None
                    continue
                raise
