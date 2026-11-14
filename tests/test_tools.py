import asyncio
import io
import json
import subprocess
import sys
import threading
from datetime import datetime

import pytest

from friday.conductor import Conductor
from friday.guardrails import GuardrailsEngine
from friday.tools import ToolGateway, ToolError
from friday.tools.builtin import Tool, parse_ddg, parse_due, reminder_tool, say_date, weather_tool, web_search_tool
from friday.tools.gateway import MCP_SERVER_PATH
from friday.voice import CoreServer, parse_app_message

TIERS = {"reminder.create": 2, "weather.read": 3, "web.search": 3}


def fake_tool(name="echo", action="weather.read", calls=None, fail=None):
    async def run(a):
        if fail:
            raise fail
        (calls if calls is not None else []).append(a)
        return f"ok {a['text']}"
    return Tool(name=name, action=action, description="test",
                schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                run=run, summary=lambda a: f"Faire {a['text']}")


def gateway(audit, tiers=TIERS, **kw):
    calls = []
    tools = [fake_tool("lire", "weather.read", calls), fake_tool("noter", "reminder.create", calls),
             fake_tool("effacer", "file.delete", calls), fake_tool("inconnue", "truc.nouveau", calls)]
    return ToolGateway(tools, GuardrailsEngine(tiers, audit=audit), audit, **kw), calls


def outcomes(audit):
    return [e.payload["outcome"] for e in audit.entries() if e.event == "tool.call"]


# --- Décisions par tier ---

def test_tier3_execute_et_audite_sans_texte_brut(audit):
    gw, calls = gateway(audit)
    assert asyncio.run(gw.call("lire", {"text": "secret de Paul"})) == (True, "ok secret de Paul")
    assert calls == [{"text": "secret de Paul"}]
    assert outcomes(audit) == ["executed"]
    assert "Paul" not in json.dumps([e.payload for e in audit.entries()])     # empreinte seulement
    assert any(e.event == "guardrails.verdict" for e in audit.entries())


def test_tier2_execute_puis_notifie(audit):
    notes = []
    gw, calls = gateway(audit, notify=notes.append)
    ok, _ = asyncio.run(gw.call("noter", {"text": "appeler Paul"}))
    assert ok and notes == ["ok appeler Paul"]


@pytest.mark.parametrize("answer,expected", [(True, "executed"), (False, "refused")])
def test_tier1_attend_la_confirmation(audit, answer, expected):
    asked = []

    async def confirm(summary, action):
        asked.append((summary, action))
        return answer
    gw, calls = gateway(audit, confirm=confirm)
    ok, text = asyncio.run(gw.call("effacer", {"text": "x"}))
    assert ok is answer and asked == [("Faire x", "file.delete")]
    assert bool(calls) is answer and outcomes(audit) == [expected]
    if not answer:
        assert "refusé" in text


def test_tier1_refus_par_defaut_sans_reponse(audit):
    async def never(summary, action):
        await asyncio.sleep(10)
        return True
    gw, calls = gateway(audit, confirm=never, confirm_timeout=0.05)
    assert asyncio.run(gw.call("effacer", {"text": "x"}))[0] is False
    assert calls == [] and outcomes(audit) == ["refused"]
    assert "pas répondu" in asyncio.run(gw.call("effacer", {"text": "x"}))[1]
    assert [e.payload["why"] for e in audit.entries() if e.event == "tool.confirm"] == ["timeout", "timeout"]


def test_action_inconnue_tier1_et_sans_interface_refus(audit):
    gw, calls = gateway(audit)                                  # pas de confirmer
    assert asyncio.run(gw.call("inconnue", {"text": "x"}))[0] is False
    assert calls == []


def test_config_durcit_le_rappel_en_tier1(audit):
    gw, calls = gateway(audit, tiers={**TIERS, "reminder.create": 1})
    assert asyncio.run(gw.call("noter", {"text": "x"}))[0] is False   # personne pour confirmer


def test_tier0_bloque_meme_confirme(audit):
    async def yes(summary, action):
        return True
    gw, calls = gateway(audit, confirm=yes)
    ok, text = asyncio.run(gw.call("lire", {"text": "password: hunter2222"}))
    assert not ok and "T0-CREDENTIALS" in text and calls == []
    assert outcomes(audit) == ["blocked"]


def test_outil_inconnu_arguments_invalides_et_erreur(audit):
    gw, _ = gateway(audit)
    assert asyncio.run(gw.call("rm", {}))[0] is False
    assert asyncio.run(gw.call("lire", {}))[1] == "Argument manquant : text."
    assert asyncio.run(gw.call("lire", {"text": "x", "autre": 1}))[0] is False
    gw.tools["lire"] = fake_tool("lire", fail=ToolError("service indisponible"))
    assert asyncio.run(gw.call("lire", {"text": "x"})) == (False, "service indisponible")
    assert outcomes(audit) == ["unknown_tool", "invalid_args", "invalid_args", "error"]


# --- Socket et serveur MCP ---

def test_serveur_mcp_relaie_vers_le_socket(audit):
    """Le vrai relais stdio (lancé comme par Claude Code) parle au socket de la passerelle."""
    async def scenario():
        gw, calls = gateway(audit)
        path = await gw.start()
        assert oct(path.stat().st_mode & 0o777) == "0o600" and oct(path.parent.stat().st_mode & 0o777) == "0o700"
        cfg = json.loads(gw.mcp_config(sys.executable))["mcpServers"]["friday"]
        assert cfg["args"][:2] == ["-I", str(MCP_SERVER_PATH)]
        proc = await asyncio.create_subprocess_exec(cfg["command"], *cfg["args"], stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE)
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lire", "arguments": {"text": "Lyon"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "effacer", "arguments": {"text": "x"}}},
                {"jsonrpc": "2.0", "id": 5, "method": "inconnue"}]
        out, _ = await proc.communicate("".join(json.dumps(m) + "\n" for m in msgs).encode())
        await gw.close()
        assert not path.exists() and not path.parent.exists()
        return [json.loads(line) for line in out.decode().splitlines()], calls

    res, calls = asyncio.run(scenario())
    assert [r["id"] for r in res] == [1, 2, 3, 4, 5]              # rien pour la notification
    assert res[0]["result"]["protocolVersion"] == "2025-06-18" and "tools" in res[0]["result"]["capabilities"]
    assert [t["name"] for t in res[1]["result"]["tools"]] == ["lire", "noter", "effacer", "inconnue"]
    assert res[2]["result"] == {"content": [{"type": "text", "text": "ok Lyon"}], "isError": False}
    assert res[3]["result"]["isError"] is True                     # Tier 1 sans interface : refus
    assert res[4]["error"]["code"] == -32601
    assert calls == [{"text": "Lyon"}]


def test_serveur_mcp_coeur_injoignable(tmp_path):
    proc = subprocess.run([sys.executable, "-I", str(MCP_SERVER_PATH), "--socket", str(tmp_path / "absent.sock")],
                          input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                            "params": {"name": "x", "arguments": {}}}) + "\n",
                          capture_output=True, text=True, timeout=10)
    assert json.loads(proc.stdout)["result"]["isError"] is True


# --- Confirmation via l'app (CoreServer) ---

class ToolBrain:
    """Faux cerveau : appelle l'outil « effacer » pendant sa réponse, comme Claude via MCP."""
    name = "test"

    def __init__(self, gw):
        self.gw = gw
        self.mcp = None

    def use_tools(self, cfg):
        self.mcp = cfg

    async def stream(self, text, decision, source):
        ok, msg = await self.gw.call("effacer", {"text": text})
        yield f"{ok}: {msg}"


class Pipe:
    """stdin bloquant : les lignes sont ajoutées par l'« app » quand elle voit un message."""

    def __init__(self):
        self.lines, self.cv = [], threading.Condition()

    def push(self, line):
        with self.cv:
            self.lines.append(line + "\n")
            self.cv.notify()

    def readline(self):
        with self.cv:
            self.cv.wait_for(lambda: self.lines, timeout=10)
            return self.lines.pop(0) if self.lines else ""


class App(io.StringIO):
    """stdout : répond aux messages du cœur comme le ferait l'app Swift."""

    def __init__(self, stdin, answer):
        super().__init__()
        self.stdin, self.answer, self.msgs = stdin, answer, []

    def write(self, s):
        msg = json.loads(s)
        self.msgs.append(msg)
        if msg["type"] == "ready":
            self.stdin.push('{"type":"ask","id":1,"text":"vieux.txt"}')
        elif msg["type"] == "confirm" and self.answer is not None:
            self.stdin.push(json.dumps({"type": "confirm_result", "id": msg["id"], "ok": self.answer}))
        elif msg["type"] in ("reply", "confirm_expired"):
            if msg["type"] == "reply":
                self.stdin.push('{"type":"shutdown"}')
        return len(s)


@pytest.mark.parametrize("answer", [True, False, None])
def test_confirmation_dans_la_bulle(audit, answer):
    gw, calls = gateway(audit, confirm_timeout=0.3)
    brain = ToolBrain(gw)
    stdin = Pipe()
    app = App(stdin, answer)
    assert asyncio.run(CoreServer(Conductor(audit=audit), brain, audit, gateway=gw).run(stdin, app)) == 0
    types = [m["type"] for m in app.msgs]
    assert app.msgs[0]["tools"] == ["lire", "noter", "effacer", "inconnue"] and brain.mcp
    confirm = next(m for m in app.msgs if m["type"] == "confirm")
    assert confirm["summary"] == "Faire vieux.txt" and confirm["action"] == "file.delete"
    reply = next(m for m in app.msgs if m["type"] == "reply")
    assert reply["text"].startswith("True" if answer else "False")
    assert ("confirm_expired" in types) is (answer is None)
    assert bool(calls) is bool(answer)


def test_parse_confirm_result():
    assert parse_app_message('{"type":"confirm_result","id":3,"ok":true}')["ok"] is True
    assert parse_app_message('{"type":"confirm_result","id":3}') is None
    assert parse_app_message('{"type":"confirm_result","id":"3","ok":false}') is None


# --- Outils réels (sans réseau ni Rappels) ---

def test_rappel_osascript_et_resume():
    seen = []

    async def runner(cmd):
        seen.append(cmd)
        return 0, "Rappels\n", ""
    tool = reminder_tool(runner)
    args = tool.validate({"title": "Appeler Paul", "due": "2026-11-15T10:00"})
    assert tool.summary(args) == "Créer le rappel « Appeler Paul » pour le 15 novembre 2026 à 10 h"
    assert asyncio.run(tool.run(args)) == "Rappel « Appeler Paul » créé dans la liste Rappels, le 15 novembre 2026 à 10 h."
    assert seen[0][0] == "osascript" and seen[0][3:] == ["Appeler Paul", "", "1", "2026", "11", "15", "10", "0"]
    assert say_date(datetime(2026, 1, 2, 9, 5)) == "le 2 janvier 2026 à 9 h 05"
    with pytest.raises(ToolError):
        parse_due("demain")


def test_rappel_sans_autorisation():
    async def runner(cmd):
        return 1, "", "execution error: Not authorized to send Apple events to Reminders. (-1743)"
    with pytest.raises(ToolError, match="Automatisation"):
        asyncio.run(reminder_tool(runner).run({"title": "x"}))


def test_meteo_open_meteo():
    async def fetch(method, url, data):
        if "geocoding" in url:
            return json.dumps({"results": [{"name": "Lyon", "country": "France", "latitude": 45.7, "longitude": 4.8}]})
        return json.dumps({"current": {"temperature_2m": 8.6, "apparent_temperature": 6.7, "weather_code": 3,
                                       "wind_speed_10m": 5},
                           "daily": {"time": ["2026-11-14"], "weather_code": [61], "temperature_2m_min": [1.2],
                                     "temperature_2m_max": [10.8], "precipitation_probability_max": [58]}})
    out = asyncio.run(weather_tool(fetch).run({"city": "Lyon"}))
    assert "Lyon (France) maintenant : couvert, 8.6 °C" in out and "pluie faible" in out
    with pytest.raises(ToolError, match="Ville"):
        asyncio.run(weather_tool(fetch).run({}))
    assert weather_tool(fetch, default_city="Paris").schema["required"] == []


def test_recherche_web_duckduckgo():
    page = ('<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fex.fr%2Fa&amp;rut=1">'
            'Titre <b>A</b></a> ... <a class="result__snippet" href="x">Résumé &amp; plus</a>')
    assert parse_ddg(page) == [("Titre A", "https://ex.fr/a", "Résumé & plus")]

    async def fetch(method, url, data):
        assert method == "POST" and b"q=Ligue+1" in data
        return page
    out = asyncio.run(web_search_tool(fetch).run({"query": "Ligue 1"}))
    assert "NON FIABLE" in out and "https://ex.fr/a" in out


# --- Lecture de page (web_read) ---
from friday.tools.builtin import is_public_url, page_text, web_read_tool  # noqa: E402


def test_page_text_garde_le_contenu_utile():
    page = ("<html><head><style>x{}</style><script>alert(1)</script></head><body><nav>Menu</nav>"
            "<h1>PSG 3 - 1 Lyon</h1><p>Le PSG l&#39;emporte au Parc.</p><footer>Mentions</footer></body></html>")
    assert page_text(page) == "PSG 3 - 1 Lyon\nLe PSG l'emporte au Parc."
    assert page_text("<p>" + "a" * 50 + "</p>", limit=10).endswith("[… page tronquée]")


def test_is_public_url_refuse_le_reseau_local():
    pub = lambda h: ["93.184.216.34"]                                    # noqa: E731
    assert is_public_url("https://www.lequipe.fr/foot", pub)
    assert not is_public_url("file:///etc/passwd", pub)
    assert not is_public_url("ftp://exemple.fr", pub)
    assert not is_public_url("http://localhost:8080", lambda h: ["127.0.0.1"])
    assert not is_public_url("http://box", lambda h: ["192.168.1.1"])
    assert not is_public_url("http://meta", lambda h: ["169.254.169.254"])
    assert not is_public_url("http://mixte.fr", lambda h: ["93.184.216.34", "10.0.0.2"])


def test_web_read_lit_la_page_et_refuse_le_local():
    async def fetch(method, url, data):
        return "<p>Score final : 2-0</p>"
    tool = web_read_tool(fetch, resolve=lambda h: ["93.184.216.34"])
    out = asyncio.run(tool.run({"url": "https://exemple.fr/match"}))
    assert "Score final : 2-0" in out and "NON FIABLE" in out
    local = web_read_tool(fetch, resolve=lambda h: ["127.0.0.1"])
    with pytest.raises(ToolError):
        asyncio.run(local.run({"url": "http://localhost/admin"}))
    assert tool.action == "web.read"


# --- Calendrier (faux runner, jamais l'app Calendrier) ---

from friday.tools.builtin import calendar_create_tool, calendar_read_tool  # noqa: E402

DENIED = "execution error: Not authorized to send Apple events to Calendar. (-1743)"


def test_agenda_lecture_osascript_et_mise_en_forme():
    seen = []

    async def runner(cmd):
        seen.append(cmd)
        return 0, ("2026-11-17T10:00\t2026-11-17T11:00\tDentiste\tPerso\t12 rue X\n"
                   "2026-11-16T00:00\t2026-11-17T00:00\tFérié\tJours fériés\t\n"), ""
    tool = calendar_read_tool(runner)
    args = tool.validate({"start": "2026-11-16", "days": 7})
    text = asyncio.run(tool.run(args))
    assert seen[0][0] == "osascript" and seen[0][1] == "-e" and seen[0][3:] == ["2026", "11", "16", "7"]
    assert "whose start date < d2 and end date > d1" in seen[0][2]
    assert text.splitlines() == [
        "Agenda du 2026-11-16 au 2026-11-22 (2 événement(s), heures locales) :",
        "- 2026-11-16 journée : Férié [Jours fériés]",
        "- 2026-11-17 10:00 → 11:00 : Dentiste [Perso] @ 12 rue X"]
    assert tool.action == "calendar.read"


def test_agenda_lecture_vide_et_arguments_invalides():
    async def runner(cmd):
        return 0, "\n", ""
    tool = calendar_read_tool(runner)
    assert asyncio.run(tool.run({"start": "2026-11-16"})) == "Agenda du 2026-11-16 au 2026-11-22 : aucun événement."
    with pytest.raises(ToolError):
        asyncio.run(tool.run({"start": "mardi"}))
    with pytest.raises(ToolError):
        asyncio.run(tool.run({"days": 90}))
    with pytest.raises(ToolError):
        tool.validate({"days": "7"})


def test_agenda_creation_osascript_et_resume():
    seen = []

    async def runner(cmd):
        seen.append(cmd)
        return 0, "Perso\n", ""
    tool = calendar_create_tool(runner)
    args = tool.validate({"title": "Dentiste", "start": "2026-11-17T10:00", "end": "2026-11-17T11:30"})
    assert tool.summary(args) == "Créer l'événement « Dentiste » le 17 novembre 2026 à 10 h jusqu'à 11 h 30"
    assert asyncio.run(tool.run(args)) == ("Événement « Dentiste » créé dans le calendrier Perso, "
                                           "le 17 novembre 2026 à 10 h jusqu'à 11 h 30.")
    assert seen[0][3:] == ["Dentiste", "", "2026", "11", "17", "10", "0", "2026", "11", "17", "11", "30"]
    assert tool.action == "calendar.create_event"


@pytest.mark.parametrize("start,end", [("mardi 10h", "2026-11-17T11:00"), ("2026-11-17T11:00", "2026-11-17T10:00"),
                                       ("2026-11-17T10:00", "2027-01-17T10:00")])
def test_agenda_creation_dates_invalides(start, end):
    calls = []

    async def runner(cmd):
        calls.append(cmd)
        return 0, "Perso", ""
    with pytest.raises(ToolError):
        asyncio.run(calendar_create_tool(runner).run({"title": "x", "start": start, "end": end}))
    assert calls == []


def test_agenda_sans_autorisation_et_calendrier_inconnu():
    async def denied(cmd):
        return 1, "", DENIED
    with pytest.raises(ToolError, match="Automatisation"):
        asyncio.run(calendar_read_tool(denied).run({}))
    with pytest.raises(ToolError, match="Automatisation"):
        asyncio.run(calendar_create_tool(denied).run({"title": "x", "start": "2026-11-17T10:00",
                                                       "end": "2026-11-17T11:00"}))

    async def unknown(cmd):
        return 1, "", "execution error: CALENDRIER_INCONNU (-2700)"
    with pytest.raises(ToolError, match="introuvable"):
        asyncio.run(calendar_create_tool(unknown).run({"title": "x", "start": "2026-11-17T10:00",
                                                        "end": "2026-11-17T11:00", "calendar": "Boulot"}))

    async def slow(cmd):
        raise TimeoutError
    with pytest.raises(ToolError, match="ne répond pas"):
        asyncio.run(calendar_read_tool(slow).run({}))


def test_agenda_tiers_de_la_config():
    from friday.config import load_config
    from friday.guardrails.tiers import Action
    engine = GuardrailsEngine(load_config().guardrails.actions)
    assert engine.tier_for(Action("calendar.read")) == 3
    assert engine.tier_for(Action("calendar.create_event")) == 2
