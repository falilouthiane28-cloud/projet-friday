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


# --- Streaming ---
from friday.claude_brain import SentenceSplitter, parse_stream_line  # noqa: E402


def delta_line(t):
    return json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": t}}})


def result_line(text, session="s1", error=False):
    return json.dumps({"type": "result", "is_error": error, "result": text, "session_id": session})


class FakeStream:
    def __init__(self, *runs):
        self.runs = list(runs)
        self.calls = []

    def __call__(self, cmd, env, cwd, timeout):
        self.calls.append(list(cmd))
        lines = self.runs.pop(0)

        async def gen():
            for line in lines:
                yield line
        return gen()


def test_decoupage_en_phrases():
    s = SentenceSplitter()
    assert s.feed("Bonjour ") == []
    assert s.feed("! Com") == ["Bonjour !"]
    assert s.feed("ment allez-vous ? Il est 10 h") == ["Comment allez-vous ?"]
    assert s.feed(".5 et") == []                                  # pas de coupure dans « 10 h.5 »
    assert s.feed(" voilà.\nSuite") == ["Il est 10 h.5 et voilà."]
    assert s.flush() == ["Suite"] and s.flush() == []


def test_parse_stream_line():
    assert parse_stream_line(delta_line("ab")) == ("delta", "ab")
    assert parse_stream_line(result_line("x"))[0] == "result"
    assert parse_stream_line('{"type":"system"}') is None and parse_stream_line("pas json") is None


def test_stream_claude_et_session(tmp_path):
    fake = FakeStream([delta_line("Bon"), delta_line("jour."), result_line("Bonjour.", "abc")],
                      [delta_line("Re."), result_line("Re.", "abc")])
    b = ClaudeCodeBrain(Path("/bin/claude"), SOUL, tmp_path, stream_runner=fake, env={})

    async def collect(text):
        return [d async for d in b.stream(text, decision(), "voice")]

    assert asyncio.run(collect("salut")) == ["Bon", "jour."]
    assert b.session_id == "abc"
    assert asyncio.run(collect("encore")) == ["Re."]
    first, second = fake.calls
    assert first[first.index("--output-format") + 1] == "stream-json" and "--include-partial-messages" in first
    assert second[second.index("--resume") + 1] == "abc"


def test_stream_connexion_requise(tmp_path):
    fake = FakeStream([result_line("Not logged in · Please run /login", error=True)])
    h = HybridBrain(LocalBrain(), ClaudeCodeBrain(Path("/bin/claude"), SOUL, tmp_path, stream_runner=fake, env={}))

    async def collect():
        return [d async for d in h.stream("raconte", decision(), "text")]

    assert asyncio.run(collect()) == [LOGIN_HELP]


# --- Processus persistant ---
from friday.claude_brain import VOICE_TAG, PersistentClaudeBrain  # noqa: E402


class FakeProc:
    """Faux Claude Code persistant : à chaque message reçu, rejoue la réponse suivante."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []
        self.returncode = None
        self.queue = []
        proc = self

        class In:
            def write(self, data):
                proc.sent.append(json.loads(data))
                proc.queue.extend((line + "\n").encode() for line in proc.replies.pop(0))

            async def drain(self):
                pass

        class Out:
            async def readline(self):
                return proc.queue.pop(0) if proc.queue else b""

        self.stdin, self.stdout = In(), Out()

    def kill(self):
        self.returncode = -9


def persistent(tmp_path, *procs):
    spawned = []

    async def spawner(cmd, env, cwd):
        spawned.append(list(cmd))
        return procs[len(spawned) - 1]

    b = PersistentClaudeBrain(Path("/bin/claude"), SOUL, tmp_path, env={}, spawner=spawner)
    return b, spawned


def test_persistant_un_seul_processus_et_style_par_message(tmp_path):
    proc = FakeProc([[delta_line("Bonjour."), result_line("Bonjour.", "s9")],
                     [delta_line("Rome."), result_line("Rome.", "s9")]])
    b, spawned = persistent(tmp_path, proc)

    async def scenario():
        await b.prewarm()
        a = [d async for d in b.stream("salut", decision(), "text")]
        c = [d async for d in b.stream("capitale de l'Italie", decision(), "voice")]
        return a, c

    assert asyncio.run(scenario()) == (["Bonjour."], ["Rome."])
    assert len(spawned) == 1                                            # préchauffé, jamais relancé
    cmd = spawned[0]
    assert cmd[cmd.index("--input-format") + 1] == "stream-json" and cmd[cmd.index("--tools") + 1] == ""
    assert "[voix]" in cmd[cmd.index("--system-prompt") + 1]
    assert [m["message"]["content"] for m in proc.sent] == ["salut", VOICE_TAG + "capitale de l'Italie"]
    assert b.session_id == "s9"


def test_persistant_relance_avec_resume_si_le_processus_meurt(tmp_path):
    dead = FakeProc([[]])                                               # meurt sans répondre
    first = FakeProc([[delta_line("Un."), result_line("Un.", "s1")]])
    second = FakeProc([[delta_line("Deux."), result_line("Deux.", "s1")]])
    b, spawned = persistent(tmp_path, first, dead, second)

    async def scenario():
        out = [d async for d in b.stream("a", decision())]
        first.returncode = 0                                            # le processus s'est arrêté entre deux questions
        out += [d async for d in b.stream("b", decision())]
        return out

    assert asyncio.run(scenario()) == ["Un.", "Deux."]
    assert len(spawned) == 3 and spawned[2][spawned[2].index("--resume") + 1] == "s1"


def test_persistant_reset_tue_le_processus(tmp_path):
    p1 = FakeProc([[delta_line("A."), result_line("A.", "x")]])
    p2 = FakeProc([[delta_line("B."), result_line("B.", "y")]])
    b, spawned = persistent(tmp_path, p1, p2)
    asyncio.run(b.respond("a", decision()))
    b.reset()
    assert p1.returncode == -9 and b.session_id is None
    assert asyncio.run(b.respond("b", decision())) == "B."
    assert "--resume" not in spawned[1]                                 # nouvelle conversation


def test_persistant_avec_outils_mcp_et_date_en_tete(tmp_path):
    from datetime import datetime
    proc = FakeProc([[delta_line("Fait."), result_line("Fait.", "s2")]])
    b, spawned = persistent(tmp_path, proc)
    b.clock = lambda: datetime(2026, 11, 14, 15, 30)
    b.use_tools('{"mcpServers": {}}')

    async def scenario():
        return [d async for d in b.stream("rappelle-moi", decision(), "voice")]

    assert asyncio.run(scenario()) == ["Fait."]
    cmd = spawned[0]
    assert cmd[cmd.index("--tools") + 1] == "" and "--strict-mcp-config" in cmd    # aucun outil intégré
    assert cmd[cmd.index("--mcp-config") + 1] == '{"mcpServers": {}}'
    assert cmd[cmd.index("--allowedTools") + 1] == "mcp__friday"
    prompt = cmd[cmd.index("--system-prompt") + 1]
    assert "aucun outil" not in prompt and "rappels" in prompt
    assert proc.sent[0]["message"]["content"] == VOICE_TAG + "[samedi 2026-11-14 15:30] rappelle-moi"


def test_sans_outils_le_prompt_le_dit(tmp_path):
    b, _ = persistent(tmp_path)
    cmd = b.persistent_command()
    assert "--mcp-config" not in cmd and "aucun outil" in cmd[cmd.index("--system-prompt") + 1]


def test_blocs_de_texte_separes(tmp_path):
    block = json.dumps({"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "text", "text": ""}}})
    proc = FakeProc([[block, delta_line("Je cherche."), block, delta_line("Le rappel est créé."), result_line("x", "s")]])
    b, _ = persistent(tmp_path, proc)
    assert asyncio.run(b.respond("a", decision())) == "Je cherche.\n\nLe rappel est créé."
