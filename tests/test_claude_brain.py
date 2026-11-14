import asyncio
import json
from pathlib import Path

import pytest

from friday.brain import HybridBrain, LocalBrain
from friday.claude_brain import (
    LOGIN_HELP, ClaudeCodeBrain, ClaudeError, clean_env, find_claude_binary, parse_result, system_prompt,
)
from friday.conductor import Conductor

SOUL = {"IDENTITY": {"name": "FRIDAY", "master": "Thaïne", "tone": "pro"}, "CORE_VALUES": ["Vérité"],
        "COMMUNICATION_RULES": ["Court"]}


def ok(text, session="s1"):
    return 0, json.dumps({"type": "result", "is_error": False, "result": text, "session_id": session})


class FakeRunner:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def __call__(self, cmd, env, cwd, timeout):
        self.calls.append(list(cmd))
        return self.outputs.pop(0)


def brain(runner, tmp_path):
    return ClaudeCodeBrain(Path("/bin/claude"), SOUL, tmp_path / "claude", runner=runner,
                           env={"PATH": "/bin", "CLAUDECODE": "1", "CLAUDE_CODE_X": "y", "ANTHROPIC_API_KEY": "k"})


def decision(text="raconte une blague"):
    return Conductor().handle(text)


def test_parse_result():
    assert parse_result(*ok("Bonjour.")) == ("Bonjour.", "s1")
    with pytest.raises(ClaudeError, match="connecté"):
        parse_result(1, json.dumps({"is_error": True, "result": "Not logged in · Please run /login"}))
    with pytest.raises(ClaudeError):
        parse_result(0, "pas du json")
    with pytest.raises(ClaudeError):
        parse_result(*ok(""))


def test_commande_sans_outils_et_suivi_de_session(tmp_path):
    runner = FakeRunner(ok("Première.", "abc"), ok("Deuxième.", "abc"))
    b = brain(runner, tmp_path)
    assert asyncio.run(b.respond("salut", decision(), "text")) == "Première."
    assert asyncio.run(b.respond("et ensuite", decision(), "voice")) == "Deuxième."
    first, second = runner.calls
    assert first[first.index("--tools") + 1] == ""                    # aucun outil
    assert "--strict-mcp-config" in first and "--resume" not in first
    assert second[second.index("--resume") + 1] == "abc"
    assert "voix haute" in second[second.index("--system-prompt") + 1]
    assert "voix haute" not in first[first.index("--system-prompt") + 1]
    b.reset()
    assert b.session_id is None


def test_session_perdue_repart_a_zero(tmp_path):
    runner = FakeRunner(ok("Un.", "old"), (1, json.dumps({"is_error": True, "result": "No conversation found"})),
                        ok("Deux.", "new"))
    b = brain(runner, tmp_path)
    asyncio.run(b.respond("a", decision()))
    assert asyncio.run(b.respond("b", decision())) == "Deux."
    assert "--resume" not in runner.calls[2] and b.session_id == "new"


def test_env_nettoye():
    env = clean_env({"PATH": "/bin", "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "x",
                     "ANTHROPIC_BASE_URL": "http://proxy", "ANTHROPIC_API_KEY": "k"})
    assert env == {"PATH": "/bin", "ANTHROPIC_API_KEY": "k"}


def test_hybride_local_puis_claude_et_erreur_lisible(tmp_path):
    runner = FakeRunner(ok("Une blague."), (1, json.dumps({"is_error": True, "result": "Not logged in"})))
    h = HybridBrain(LocalBrain(), brain(runner, tmp_path))
    assert asyncio.run(h.respond("quelle heure est-il", decision("quelle heure est-il"))).startswith("Il est")
    assert runner.calls == []                                          # heure : jamais Claude
    assert asyncio.run(h.respond("raconte une blague", decision())) == "Une blague."
    assert asyncio.run(h.respond("encore", decision())) == LOGIN_HELP


def test_find_claude_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "vide"))
    assert find_claude_binary(home=tmp_path) is None
    for v in ("2.1.9", "2.1.321"):
        p = tmp_path / f"Library/Application Support/Claude/claude-code/{v}/h/claude.app/Contents/MacOS/claude"
        p.parent.mkdir(parents=True)
        p.touch()
    assert "2.1.321" in str(find_claude_binary(home=tmp_path))       # version la plus récente
    assert find_claude_binary(str(tmp_path / "absent")) is None


def test_system_prompt():
    p = system_prompt(SOUL, voice=False)
    assert "FRIDAY" in p and "Thaïne" in p and "aucun outil" in p
