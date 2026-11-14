"""Faux binaire friday-voice : rejoue « Hey Friday, quelle heure est-il ? »."""

import json
import sys
import time


def out(**msg):
    print(json.dumps(msg), flush=True)


out(type="ready")
out(type="state", state="idle")
out(type="state", state="listening")
print("ligne invalide", flush=True)
t0 = time.monotonic()
out(type="utterance", text="quelle heure est il")
out(type="state", state="processing")
reply = json.loads(sys.stdin.readline())
assert reply["type"] == "say", reply
out(type="state", state="speaking")
out(type="metrics", ttfa_ms=int((time.monotonic() - t0) * 1000))
print(json.dumps({"echo": reply["text"]}), file=sys.stderr, flush=True)
out(type="state", state="idle")
msg = json.loads(sys.stdin.readline())
sys.exit(0 if msg["type"] == "shutdown" else 3)
