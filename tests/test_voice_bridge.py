import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

from friday.brain import LocalBrain
from friday.conductor import Conductor
from friday.voice import VoiceBridge, parse_voice_message

FAKE = str(Path(__file__).with_name("fake_voice.py"))


def test_parse_voice_message():
    assert parse_voice_message('{"type":"utterance","text":"salut"}') == {"type": "utterance", "text": "salut"}
    assert parse_voice_message('{"type":"utterance"}') is None
    assert parse_voice_message('{"type":"inconnu"}') is None
    assert parse_voice_message("pas du json") is None
    assert parse_voice_message("[1, 2]") is None


def test_hey_friday_quelle_heure_bout_en_bout(audit):
    brain = LocalBrain(clock=lambda: datetime(2026, 11, 14, 10, 5))
    bridge = VoiceBridge([sys.executable, FAKE], Conductor(audit=audit), brain, audit)

    async def scenario():
        t0 = time.monotonic()
        task = asyncio.create_task(bridge.run())
        while not bridge.ttfa_ms:                  # attend la réponse vocale simulée
            await asyncio.sleep(0.01)
        elapsed = time.monotonic() - t0
        while bridge.state != "idle":
            await asyncio.sleep(0.01)
        await bridge.shutdown()
        return await task, elapsed

    code, elapsed = asyncio.run(scenario())
    assert code == 0                               # le faux binaire a reçu say puis shutdown
    assert elapsed < 2.0                           # critère de la phase 2 (hors micro réel)
    assert bridge.ttfa_ms[0] < 500                 # le cœur Python ne consomme pas le budget
    events = [e.event for e in audit.entries()]
    assert "intent.classified" in events and "voice.ttfa" in events
