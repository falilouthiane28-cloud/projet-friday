import asyncio
import io
import json
from datetime import datetime

from friday.agents import default_registry
from friday.brain import LocalBrain
from friday.conductor import Conductor
from friday.dashboard import DashboardData
from friday.voice import CoreServer, parse_app_message

GEO = {"results": [{"name": "Dakar", "country": "Sénégal", "latitude": 14.7, "longitude": -17.4}]}
FORECAST = {"current": {"temperature_2m": 27.4, "apparent_temperature": 29.0, "weather_code": 2,
                        "wind_speed_10m": 18.0, "is_day": 0},
            "daily": {"temperature_2m_min": [22.1], "temperature_2m_max": [30.2],
                      "precipitation_probability_max": [5]}}


async def fake_fetch(method, url, data=None, timeout=10):
    return json.dumps(GEO if "geocoding" in url else FORECAST)


async def fake_calendar(cmd):
    return 0, ("2026-11-14T14:00:00\t2026-11-14T15:00:00\tDentiste\tPerso\t\n"
               "2026-11-14T00:00:00\t2026-11-15T00:00:00\tAnniversaire Awa\tFamille\t\n"), ""


async def denied_calendar(cmd):
    return 1, "", "execution error: Not authorized to send Apple events to Calendar. (-1743)"


def data(**kw):
    base = dict(registry=default_registry(), default_city="Dakar", home_configured=False, fetch=fake_fetch,
                calendar_runner=fake_calendar, now=lambda: datetime(2026, 11, 14, 21, 35))
    return DashboardData(**{**base, **kw})


def test_dashboard_meteo_agenda_agents():
    out = asyncio.run(data().collect())
    assert out["type"] == "dashboard" and out["city"] == "Dakar"
    w = out["weather"]
    assert w["city"] == "Dakar" and w["temperature"] == 27.4 and w["label"] == "partiellement nuageux"
    assert w["min"] == 22.1 and w["max"] == 30.2 and w["is_day"] is False
    assert [e["title"] for e in out["agenda"]] == ["Anniversaire Awa", "Dentiste"]   # journée entière d'abord
    assert out["agenda"][0]["all_day"] and not out["agenda"][1]["all_day"]
    assert out["agenda_day"] == "2026-11-14"
    titles = [a["title"] for a in out["agents"]]
    for t in ("Chercheur", "Planificateur", "Codeur", "Contrôleur domotique", "Communicateur"):
        assert t in titles
    assert out["home_configured"] is False


def test_dashboard_sources_independantes():
    async def broken_fetch(*a, **k):
        raise OSError("réseau")
    out = asyncio.run(data(fetch=broken_fetch, calendar_runner=denied_calendar).collect())
    assert out["weather"] is None and "Météo" in out["weather_error"]
    assert out["agenda"] is None and "Automatisation" in out["agenda_error"]
    assert out["agents"]                                     # le reste est toujours là


def test_dashboard_sans_ville():
    out = asyncio.run(data(default_city=None).collect())
    assert out["weather"] is None and "default_city" in out["weather_error"]


def test_serveur_message_dashboard(audit):
    assert parse_app_message('{"type":"dashboard"}') == {"type": "dashboard"}
    server = CoreServer(Conductor(audit=audit), LocalBrain(), audit, dashboard=data())
    stdout = io.StringIO()
    assert asyncio.run(server.run(io.StringIO('{"type":"dashboard"}\n{"type":"shutdown"}\n'), stdout)) == 0
    out = [json.loads(line) for line in stdout.getvalue().splitlines()]
    dash = next(m for m in out if m["type"] == "dashboard")
    assert dash["weather"]["city"] == "Dakar"


def test_serveur_dashboard_absent(audit):
    server = CoreServer(Conductor(audit=audit), LocalBrain(), audit)
    out = asyncio.run(server.handle({"type": "dashboard"}))
    assert out == {"type": "dashboard", "unavailable": True}


def test_agenda_calendrier_ferme_relance_masque(monkeypatch):
    calls = []

    async def runner(cmd):
        calls.append(cmd)
        if cmd[0] == "/usr/bin/open":
            return 0, "", ""
        if len([c for c in calls if c[0] != "/usr/bin/open"]) == 1:
            return 1, "", "execution error: Erreur dans Calendar : L’application n’est pas ouverte. (-600)"
        return await fake_calendar(cmd)

    async def no_sleep(_):
        return None
    monkeypatch.setattr("friday.dashboard.asyncio.sleep", no_sleep)
    out = asyncio.run(data(calendar_runner=runner).collect())
    assert ["/usr/bin/open", "-g", "-j", "-a", "Calendar"] in calls
    assert len(out["agenda"]) == 2
