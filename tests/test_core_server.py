import asyncio
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from friday.brain import LocalBrain
from friday.conductor import Conductor
from friday.voice import CoreServer, parse_app_message

ROOT = Path(__file__).resolve().parents[1]


def test_parse_app_message():
    assert parse_app_message('{"type":"ask","id":1,"text":"salut","source":"voice"}')["id"] == 1
    assert parse_app_message('{"type":"ask","id":1,"text":"salut"}') is not None      # source par défaut : texte
    assert parse_app_message('{"type":"ask","text":"salut"}') is None                 # id manquant
    assert parse_app_message('{"type":"ask","id":1,"text":"x","source":"mail"}') is None
    assert parse_app_message('{"type":"shutdown"}') == {"type": "shutdown"}
    assert parse_app_message('{"type":"say","text":"x"}') is None
    assert parse_app_message("pas du json") is None


def test_server_repond_et_audite(audit):
    brain = LocalBrain(clock=lambda: datetime(2026, 11, 14, 10, 5))
    server = CoreServer(Conductor(audit=audit), brain, audit)
    stdin = io.StringIO(
        '{"type":"ask","id":7,"text":"quelle heure est-il","source":"voice"}\n'
        "ligne invalide\n"
        '{"type":"metrics","ttfa_ms":420}\n'
        '{"type":"shutdown"}\n'
        '{"type":"ask","id":8,"text":"jamais traité"}\n'
    )
    stdout = io.StringIO()
    assert asyncio.run(server.run(stdin, stdout)) == 0
    out = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert out[0] == {"type": "ready", "name": "Friday", "brain": "local"}
    by_type = {m["type"]: m for m in out[1:]}
    reply = by_type["reply"]
    assert reply["id"] == 7 and "10" in reply["text"]
    assert reply["intent"] and reply["agent"]
    assert by_type["error"]["message"] == "message invalide"
    assert len(out) == 3                                        # rien après shutdown
    events = [e.event for e in audit.entries()]
    assert "intent.classified" in events and "voice.ttfa" in events


def test_serve_en_sous_processus(tmp_path):
    """`python -m friday --serve` : ce que lance l'app Swift (stdout = JSON Lines seulement)."""
    cfg = (ROOT / "config" / "friday.yaml").read_text(encoding="utf-8")
    cfg += f"\naudit:\n  db_path: {tmp_path / 'audit.db'}\nbrain:\n  engine: local\n"
    (tmp_path / "friday.yaml").write_text(cfg, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, "-m", "friday", "--serve", "--config", str(tmp_path / "friday.yaml")], cwd=ROOT, env=env, text=True, timeout=20,
        input='{"type":"ask","id":1,"text":"bonjour","source":"text"}\n',
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [m["type"] for m in out] == ["ready", "reply"]
    assert out[1]["id"] == 1 and out[1]["text"]
    assert (tmp_path / "audit.db").exists()


class SlowBrain:
    name = "lent"

    def __init__(self):
        self.resets = 0

    def reset(self):
        self.resets += 1

    async def respond(self, text, decision, source="text"):
        await asyncio.sleep(0.2 if text == "lent" else 0)
        return f"{source}:{text}"


def test_questions_en_parallele_et_reset(audit):
    brain = SlowBrain()
    server = CoreServer(Conductor(audit=audit), brain, audit)
    stdin = io.StringIO(
        '{"type":"ask","id":1,"text":"lent","source":"text"}\n'
        '{"type":"ask","id":2,"text":"vite","source":"voice"}\n'
        '{"type":"reset"}\n'
    )
    stdout = io.StringIO()
    assert asyncio.run(server.run(stdin, stdout)) == 0          # EOF : attend les réponses en cours
    out = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert out[0]["brain"] == "lent"
    assert [(m["id"], m["text"]) for m in out[1:]] == [(2, "voice:vite"), (1, "text:lent")]
    assert brain.resets == 1
