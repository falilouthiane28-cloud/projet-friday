"""Données réelles du dashboard de l'app (message `dashboard`) : météo, agenda du jour, agents, domotique.

Lecture seule, déclenchée par l'app (jamais par Claude) : rien ne passe par le cerveau. Chaque bloc échoue
séparément (`null` + message court) pour qu'une source indisponible ne vide pas tout le dashboard.
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any

from .agents.registry import AgentRegistry
from .log import get_logger
from .tools.builtin import (_CALENDAR_READ_SCRIPT, _WMO, CommandRunner, Fetcher, _calendar_runner, _osascript,
                            http_fetch)

_log = get_logger("friday.dashboard")


async def read_weather(city: str, fetch: Fetcher = http_fetch) -> dict[str, Any]:
    """Météo actuelle + min/max du jour (Open-Meteo, même source que l'outil `weather_read`)."""
    geo = json.loads(await fetch("GET", "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": city, "count": 1, "language": "fr", "format": "json"}), None))
    if not geo.get("results"):
        raise ValueError(f"Ville introuvable : {city}")
    place = geo["results"][0]
    data = json.loads(await fetch("GET", "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto", "forecast_days": 1,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day",
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max"}), None))
    cur, daily = data.get("current", {}), data.get("daily", {})

    def first(key: str) -> Any:
        values = daily.get(key) or [None]
        return values[0]

    code = cur.get("weather_code")
    return {"city": place.get("name") or city, "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"), "code": code, "label": _WMO.get(code, "temps inconnu"),
            "wind": cur.get("wind_speed_10m"), "is_day": bool(cur.get("is_day", 1)),
            "min": first("temperature_2m_min"), "max": first("temperature_2m_max"),
            "rain": first("precipitation_probability_max")}


async def read_agenda(day: datetime, runner: CommandRunner | None = None) -> list[dict[str, Any]]:
    """Événements du jour (Calendrier macOS, même script que `calendar_read`), triés par heure."""
    run = runner or _calendar_runner
    args = [str(day.year), str(day.month), str(day.day), "1"]
    code, out, err = await _osascript(run, _CALENDAR_READ_SCRIPT, args)
    if code != 0 and "(-600)" in err:          # Calendrier fermé : le lancer masqué, en arrière-plan, puis réessayer
        await run(["/usr/bin/open", "-g", "-j", "-a", "Calendar"])
        await asyncio.sleep(2)
        code, out, err = await _osascript(run, _CALENDAR_READ_SCRIPT, args)
    if code != 0:
        raise RuntimeError(err.strip()[:200] or f"code {code}")
    events = []
    for line in out.splitlines():
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        try:
            b, e = datetime.fromisoformat(cols[0]), datetime.fromisoformat(cols[1])
        except ValueError:
            continue
        all_day = (b.hour, b.minute, e.hour, e.minute) == (0, 0, 0, 0) and e > b
        events.append({"start": b.isoformat(), "end": e.isoformat(), "title": cols[2][:200],
                       "calendar": cols[3][:80], "all_day": all_day})
    return sorted(events, key=lambda ev: (not ev["all_day"], ev["start"]))


class DashboardData:
    """Assemble le message `dashboard` envoyé à l'app."""

    def __init__(self, registry: AgentRegistry, default_city: str | None, home_configured: bool,
                 fetch: Fetcher = http_fetch, calendar_runner: CommandRunner | None = None,
                 now: Callable[[], datetime] = datetime.now) -> None:
        self.registry = registry
        self.default_city = default_city
        self.home_configured = home_configured
        self.fetch = fetch
        self.calendar_runner = calendar_runner
        self.now = now

    async def _safe(self, name: str, op: Callable[[], Awaitable[Any]]) -> tuple[Any, str | None]:
        try:
            return await op(), None
        except Exception as exc:              # une source indisponible ne doit pas casser les autres
            _log.warning("dashboard.source_failed", source=name, error=type(exc).__name__)
            return None, _reason(name, exc)

    async def collect(self) -> dict[str, Any]:
        today = self.now().replace(hour=0, minute=0, second=0, microsecond=0)
        weather, weather_err = (None, "Aucune ville par défaut (tools.default_city).")
        if self.default_city:
            weather, weather_err = await self._safe("weather", lambda: read_weather(self.default_city or "", self.fetch))
        agenda, agenda_err = await self._safe("agenda", lambda: read_agenda(today, self.calendar_runner))
        return {
            "type": "dashboard",
            "city": self.default_city,
            "weather": weather, "weather_error": weather_err,
            "agenda": agenda, "agenda_error": agenda_err, "agenda_day": today.date().isoformat(),
            "agents": [{"name": a.name, "title": a.title, "role": a.role, "model": a.model, "tools": list(a.tools)}
                       for a in self.registry.all()],
            "home_configured": self.home_configured,
        }


def _reason(source: str, exc: Exception) -> str:
    text = str(exc)
    if source == "agenda" and ("-1743" in text or "not authorized" in text.lower() or "autoris" in text.lower()):
        return "Accès au Calendrier refusé : Réglages Système › Confidentialité › Automatisation."
    if source == "agenda":
        return "Calendrier indisponible."
    return "Météo indisponible (réseau)."


__all__: Sequence[str] = ("DashboardData", "read_weather", "read_agenda")
