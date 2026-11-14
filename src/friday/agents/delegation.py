"""Handoffs-as-tools : outils `delegate_<agent>` du Conductor, lanceur d'agents et Validateur.

Une délégation lance un `claude -p` one-shot (sans session gardée) qui ne voit, par le
serveur MCP relais, que les outils de son agent. Les appels qu'il fait passent par la
même passerelle (guardrails, confirmations Tier 1 dans la bulle, audit) et sont notés ;
le Validateur confronte ensuite le compte rendu de l'agent à ces appels réels.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..brain import dire_date, dire_heure
from ..claude_brain import ClaudeError, Runner, clean_env, parse_result, run_process
from ..log import get_logger
from ..tools.builtin import Tool, ToolError
from ..tools.gateway import ToolGateway, ToolRecord
from .registry import AgentRegistry, AgentSpec

_CLAIM = re.compile(r"\b(cré[ée]e?s?|ajout[ée]e?s?|programm[ée]e?s?|enregistr[ée]e?s?|planifi[ée]e?s?|"
                    r"exécut[ée]e?s?|lanc[ée]e?s?|envoy[ée]e?s?|activ[ée]e?s?)\b"
                    # domotique : « j'ai allumé », « a été verrouillée » (pas « est allumée », simple état lu)
                    r"|\b(ai|as|a|avons|ont)\s+(bien\s+)?(été\s+)?(allum|étei|ouv|ferm|verrouill|déverrouill|arm|"
                    r"désarm|régl|bascul)\w*", re.IGNORECASE)


def validate(spec: AgentSpec, text: str, records: Sequence[ToolRecord]) -> str:
    """Validateur : compte rendu de l'agent + ce que les outils ont réellement confirmé."""
    lines = [f"[{spec.title}] {text.strip() or '(compte rendu vide)'}"]
    done = [r for r in records if r.ok and r.tool in spec.writes]
    failed = [r for r in records if not r.ok]
    if done:
        lines.append("Validateur — actions confirmées par les outils : "
                     + " ; ".join(r.text.splitlines()[0] for r in done))
    elif spec.writes and _CLAIM.search(text):
        lines.append("Validateur — ATTENTION : l'agent affirme une action qu'aucun outil n'a confirmée. "
                     "Ne la présente pas comme faite.")
    if failed:
        lines.append("Validateur — échecs ou refus : " + " ; ".join(f"{r.tool} : {r.text.splitlines()[0][:150]}"
                                                                    for r in failed))
    if not spec.writes and not any(r.ok for r in records):
        lines.append("Validateur — aucune source consultée avec succès : réponse non vérifiée, à présenter avec prudence.")
    return "\n".join(lines)


class AgentRunner:
    def __init__(self, registry: AgentRegistry, gateway: ToolGateway, binary: Path, workdir: Path,
                 python: str = sys.executable, runner: Runner = run_process, timeout: float = 240,
                 clock: Callable[[], datetime] = datetime.now, env: Any = None) -> None:
        self.registry = registry
        self.gateway = gateway
        self.binary = binary
        self.workdir = workdir
        self.python = python
        self.runner = runner
        self.timeout = timeout
        self.clock = clock
        self.env = clean_env(env if env is not None else os.environ)
        self._log = get_logger("friday.agents")

    def command(self, spec: AgentSpec, task: str, run: str) -> list[str]:
        now = self.clock()
        stamp = f"[{dire_date(now)} {dire_heure(now)}]"
        return [str(self.binary), "-p", f"{stamp}\n{task}", "--output-format", "json", "--model", spec.model,
                "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
                "--mcp-config", self.gateway.mcp_config(self.python, spec.name, run),
                "--allowedTools", ",".join(f"mcp__friday__{t}" for t in spec.tools),
                "--system-prompt", spec.prompt]

    async def run(self, agent: str, task: str) -> str:
        spec = self.registry.get(agent)
        if spec is None:
            raise ToolError(f"Agent inconnu : {agent}.")
        run = uuid.uuid4().hex[:12]
        self.gateway.begin_run(run)
        self.workdir.mkdir(parents=True, exist_ok=True)
        start = self.clock()
        try:
            code, out = await self.runner(self.command(spec, task, run), self.env, self.workdir, self.timeout)
            text, _ = parse_result(code, out)
        except ClaudeError as exc:
            text = f"Échec de l'agent : {exc}"
        finally:
            records = self.gateway.end_run(run)
        self._log.info("agents.delegate", agent=agent, tool_calls=len(records),
                       seconds=round((self.clock() - start).total_seconds(), 1))
        return validate(spec, text, records)


def delegate_tools(registry: AgentRegistry, runner: AgentRunner) -> list[Tool]:
    """Un outil `delegate_<agent>` par agent, pour le Conductor."""
    def make(spec: AgentSpec) -> Tool:
        async def run(a: dict[str, Any]) -> str:
            return await runner.run(spec.name, a["task"])

        return Tool(
            name=spec.delegate_tool, action="agent.delegate",
            description=f"Confie une tâche au {spec.title} : {spec.role} Donne une consigne complète et autonome "
                        "(l'agent ne voit pas la conversation). Plusieurs délégations indépendantes peuvent être "
                        "lancées en parallèle. Renvoie son compte rendu vérifié par le Validateur.",
            schema={"type": "object", "properties": {
                        "task": {"type": "string", "description": "Consigne complète pour l'agent."}},
                    "required": ["task"], "additionalProperties": False},
            run=run, summary=lambda a, s=spec: f"Déléguer au {s.title} : {a['task'][:80]}")

    return [make(s) for s in registry.all()]
