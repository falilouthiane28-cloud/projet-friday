"""Monitoring système (phase 8, agent System_Monitor) sans psutil (pas de wheel pour Python 3.15).

- system_read (`system.read_metrics`, Tier 3) : charge CPU, mémoire, disque, batterie, durée
  depuis le démarrage, via la stdlib et des commandes macOS à arguments fixes
  (`vm_stat`, `sysctl`, `pmset`). Seuils d'alerte de la spec signalés dans la réponse.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import time
from collections.abc import Callable
from typing import Any

from .builtin import CommandRunner, Tool, ToolError, run_command

# Seuils d'alerte (spec, section 10 « Monitoring Système »).
CPU_ALERT = 0.90             # charge moyenne 1 min / cœurs
RAM_ALERT = 0.85
DISK_ALERT = 0.90
BATTERY_ALERT = 15           # %
WATCH_INTERVAL_S = 300       # alertes proactives : relevé toutes les 5 minutes


def parse_vm_stat(out: str) -> tuple[int, dict[str, int]]:
    m = re.search(r"page size of (\d+) bytes", out)
    page = int(m.group(1)) if m else 4096
    pages = {k.strip().lower(): int(v) for k, v in re.findall(r"^([^:\n]+):\s+(\d+)\.", out, re.MULTILINE)}
    return page, pages


def parse_battery(out: str) -> tuple[int, str] | None:
    m = re.search(r"(\d+)%;\s*([^;]+);", out)
    return (int(m.group(1)), m.group(2).strip()) if m else None


def _gb(n: float) -> str:
    return f"{n / 1024 ** 3:.1f} Go"


async def collect(runner: CommandRunner = run_command, now: Callable[[], float] = time.time) -> dict[str, Any]:
    m: dict[str, Any] = {"cores": os.cpu_count() or 1, "load": os.getloadavg()}
    du = shutil.disk_usage("/")
    m["disk"] = (du.used, du.total)
    code, out, _ = await runner(["/usr/sbin/sysctl", "-n", "hw.memsize"])
    total = int(out.strip()) if code == 0 and out.strip().isdigit() else 0
    code, out, _ = await runner(["/usr/bin/vm_stat"])
    if code == 0 and total:
        page, p = parse_vm_stat(out)
        used = (p.get("pages active", 0) + p.get("pages wired down", 0)
                + p.get("pages occupied by compressor", 0)) * page
        m["ram"] = (min(used, total), total)
    code, out, _ = await runner(["/usr/bin/pmset", "-g", "batt"])
    if code == 0:
        m["battery"] = parse_battery(out)
    code, out, _ = await runner(["/usr/sbin/sysctl", "-n", "kern.boottime"])
    b = re.search(r"sec = (\d+)", out) if code == 0 else None
    if b:
        m["uptime_h"] = (now() - int(b.group(1))) / 3600
    return m


def alerts(m: dict[str, Any]) -> list[str]:
    out = []
    if m["load"][0] / m["cores"] > CPU_ALERT:
        out.append("processeur très chargé")
    if "ram" in m and m["ram"][0] / m["ram"][1] > RAM_ALERT:
        out.append("mémoire presque pleine")
    if m["disk"][0] / m["disk"][1] > DISK_ALERT:
        out.append("disque presque plein")
    if m.get("battery") and m["battery"][0] < BATTERY_ALERT and "discharging" in m["battery"][1]:
        out.append("batterie faible")
    return out


def report(m: dict[str, Any]) -> str:
    lines = [f"CPU : charge {m['load'][0]:.2f} sur {m['cores']} cœurs ({m['load'][0] / m['cores']:.0%})"]
    if "ram" in m:
        used, total = m["ram"]
        lines.append(f"Mémoire : {_gb(used)} utilisés sur {_gb(total)} ({used / total:.0%})")
    used, total = m["disk"]
    lines.append(f"Disque : {_gb(total - used)} libres sur {_gb(total)} ({used / total:.0%} utilisé)")
    if m.get("battery"):
        pct, state = m["battery"]
        lines.append(f"Batterie : {pct} % ({state})")
    if "uptime_h" in m:
        lines.append(f"Allumé depuis {m['uptime_h']:.0f} h")
    found = alerts(m)
    lines.append("Alertes : " + (", ".join(found) if found else "aucune"))
    return "\n".join(lines)


class SystemWatcher:
    """Alertes proactives : relève l'état toutes les `interval` s et prévient (notice dans la bulle)
    quand une alerte APPARAÎT ; elle n'est répétée qu'après être retombée."""

    def __init__(self, runner: CommandRunner = run_command, interval: float = WATCH_INTERVAL_S) -> None:
        self.runner = runner
        self.interval = interval
        self.active: set[str] = set()

    async def check(self, notify: Callable[[str], None]) -> list[str]:
        found = alerts(await collect(self.runner))
        new = [a for a in found if a not in self.active]
        self.active = set(found)
        if new:
            notify("Alerte système : " + ", ".join(new) + ".")
        return new

    async def run(self, notify: Callable[[str], None]) -> None:
        while True:
            try:
                await self.check(notify)
            except Exception:                    # un relevé raté ne doit jamais arrêter la veille
                pass
            await asyncio.sleep(self.interval)


def system_read_tool(runner: CommandRunner = run_command) -> Tool:
    async def run(a: dict[str, Any]) -> str:
        try:
            return report(await collect(runner))
        except (OSError, ValueError) as exc:
            raise ToolError(f"Lecture des métriques impossible ({type(exc).__name__}).") from None

    return Tool(
        name="system_read", action="system.read_metrics",
        description="Lit l'état du Mac : charge CPU, mémoire, disque, batterie, durée depuis le démarrage, "
                    "avec les alertes (CPU > 90 %, RAM > 85 %, disque > 90 %, batterie < 15 %).",
        schema={"type": "object", "properties": {}, "additionalProperties": False},
        run=run, summary=lambda a: "Lire l'état du système")
