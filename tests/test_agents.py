"""Phase 3, étape 3 : registre d'agents, handoffs-as-tools, Validateur, bac à sable du Codeur."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from friday.agents import CONDUCTOR, AgentRegistry, AgentRunner, AgentSpec, default_registry, delegate_tools, validate
from friday.guardrails import GuardrailsEngine
from friday.tools import ToolGateway
from friday.tools.builtin import Tool, code_run_tool, sandbox_profile
from friday.tools.gateway import ToolRecord

TIERS = {"reminder.create": 2, "web.search": 3, "web.read": 3, "weather.read": 3, "code.run": 2,
         "agent.delegate": 3}


def tool(name, action, calls):
    async def run(a):
        calls.append((name, a))
        return f"{name} ok : {a.get('text', '')}"
    return Tool(name=name, action=action, description="test",
                schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                run=run, summary=lambda a: f"{name} {a['text']}")


def make_gateway(audit, registry, calls):
    tools = [tool("web_search", "web.search", calls), tool("web_read", "web.read", calls),
             tool("reminder_create", "reminder.create", calls), tool("weather_read", "weather.read", calls)]
    return ToolGateway(tools, GuardrailsEngine(TIERS, audit=audit), audit, allowed=registry.allowed_tools)


# --- Registre ---
def test_registre_par_defaut_et_outils_permis():
    reg = default_registry()
    assert [a.name for a in reg.all()] == ["researcher", "scheduler", "coder", "home_controller"]
    assert reg.allowed_tools(CONDUCTOR) == {"weather_read", "delegate_researcher", "delegate_scheduler",
                                            "delegate_coder", "delegate_home_controller"}
    assert reg.allowed_tools("researcher") == {"web_search", "web_read"}
    assert reg.allowed_tools("scheduler") == {"calendar_read", "calendar_create_event", "reminder_create"}
    assert set(reg.get("scheduler").writes) == {"calendar_create_event", "reminder_create"}
    assert reg.allowed_tools("inconnu") == frozenset()


@pytest.mark.parametrize("spec", [
    AgentSpec("Researcher", "x", "x", (), "x"),                       # majuscule
    AgentSpec("conductor", "x", "x", (), "x"),                        # nom réservé
    AgentSpec("relais", "x", "x", ("delegate_coder",), "x"),          # un agent ne délègue pas
])
def test_registre_refuse(spec):
    with pytest.raises(ValueError):
        AgentRegistry([spec])


# --- Passerelle : chacun ses outils ---
def test_chaque_appelant_ne_voit_et_n_appelle_que_ses_outils(audit):
    reg, calls = default_registry(), []
    gw = make_gateway(audit, reg, calls)
    assert {t["name"] for t in gw.list_tools()} == {"weather_read"}       # pas encore de delegate_*
    assert {t["name"] for t in gw.list_tools("researcher")} == {"web_search", "web_read"}
    ok, text = asyncio.run(gw.call("reminder_create", {"text": "x"}, agent="researcher"))
    assert not ok and "pas autorisé" in text and calls == []
    ok, _ = asyncio.run(gw.call("web_search", {"text": "x"}, agent=CONDUCTOR))
    assert not ok                                                       # le Conductor délègue
    assert asyncio.run(gw.call("web_search", {"text": "ligue 1"}, agent="researcher"))[0]
    forbidden = [e.payload for e in audit.entries() if e.event == "tool.call" and e.payload["outcome"] == "forbidden_tool"]
    assert len(forbidden) == 2 and forbidden[0]["agent"] == "researcher"


def test_appels_notes_par_delegation(audit):
    reg, calls = default_registry(), []
    gw = make_gateway(audit, reg, calls)
    gw.begin_run("r1")
    asyncio.run(gw.call("reminder_create", {"text": "match"}, agent="scheduler", run="r1"))
    asyncio.run(gw.call("web_search", {"text": "x"}, agent="scheduler", run="r1"))
    asyncio.run(gw.call("reminder_create", {"text": "hors délégation"}, agent="scheduler"))
    recs = gw.end_run("r1")
    assert [(r.tool, r.ok) for r in recs] == [("reminder_create", True), ("web_search", False)]
    assert gw.end_run("r1") == []


def test_mcp_config_au_nom_de_l_agent(audit, tmp_path):
    gw = make_gateway(audit, default_registry(), [])
    gw.socket_path = tmp_path / "s.sock"
    args = json.loads(gw.mcp_config("/py", "scheduler", "r9"))["mcpServers"]["friday"]["args"]
    assert args[-4:] == ["--agent", "scheduler", "--run", "r9"]
    assert "--agent" not in json.loads(gw.mcp_config("/py"))["mcpServers"]["friday"]["args"]


# --- Validateur ---
SCHED = default_registry().get("scheduler")
RESEARCH = default_registry().get("researcher")


def test_validateur_confirme_les_actions_reelles():
    out = validate(SCHED, "Rappel créé.", [ToolRecord("reminder_create", True, "Rappel « Nice - PSG » créé, le 21.")])
    assert out.startswith("[Planificateur] Rappel créé.") and "actions confirmées" in out and "Nice - PSG" in out
    assert "ATTENTION" not in out


def test_validateur_signale_une_action_inventee_et_les_refus():
    out = validate(SCHED, "J'ai créé le rappel.", [ToolRecord("reminder_create", False, "Le maître a refusé cette action.")])
    assert "ATTENTION" in out and "refusé" in out


def test_validateur_recherche_sans_source():
    assert "non vérifiée" in validate(RESEARCH, "Le PSG a gagné.", [])
    assert "non vérifiée" not in validate(RESEARCH, "Le PSG a gagné.", [ToolRecord("web_read", True, "…")])


# --- Lanceur d'agents ---
def test_delegation_lance_un_agent_isole_et_valide(audit, tmp_path):
    reg, calls, seen = default_registry(), [], []
    gw = make_gateway(audit, reg, calls)
    gw.socket_path = tmp_path / "s.sock"

    async def fake_claude(cmd, env, cwd, timeout):
        seen.append(cmd)
        run = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["friday"]["args"][-1]
        await gw.call("reminder_create", {"text": "Nice - PSG"}, agent="scheduler", run=run)   # l'agent agit
        return 0, json.dumps({"type": "result", "result": "Rappel créé pour Nice - PSG."})

    runner = AgentRunner(reg, gw, Path("/bin/claude"), tmp_path / "agents", runner=fake_claude,
                         clock=lambda: datetime(2026, 11, 14, 10, 0))
    gw.add_tools(delegate_tools(reg, runner))
    assert {t["name"] for t in gw.list_tools()} >= {"delegate_scheduler", "delegate_researcher"}
    ok, out = asyncio.run(gw.call("delegate_scheduler", {"task": "Rappel du match"}))
    assert ok and "actions confirmées" in out and "Nice - PSG" in out
    cmd = seen[0]
    assert cmd[cmd.index("--allowedTools") + 1] == ("mcp__friday__calendar_read,mcp__friday__calendar_create_event,"
                                                    "mcp__friday__reminder_create")
    assert "--no-session-persistence" in cmd and "--resume" not in cmd
    assert "14 novembre 2026" in cmd[cmd.index("-p") + 1]
    assert "Planificateur" in cmd[cmd.index("--system-prompt") + 1]


def test_delegations_en_parallele(audit, tmp_path):
    reg = default_registry()
    gw = make_gateway(audit, reg, [])
    gw.socket_path = tmp_path / "s.sock"
    active, peak = [0], [0]

    async def slow_claude(cmd, env, cwd, timeout):
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        await asyncio.sleep(0.05)
        active[0] -= 1
        return 0, json.dumps({"type": "result", "result": "fait"})

    runner = AgentRunner(reg, gw, Path("/bin/claude"), tmp_path / "a", runner=slow_claude)
    gw.add_tools(delegate_tools(reg, runner))

    async def both():
        return await asyncio.gather(gw.call("delegate_researcher", {"task": "Ligue 1"}),
                                    gw.call("delegate_scheduler", {"task": "rappel"}))
    a, b = asyncio.run(both())
    assert peak[0] == 2 and a[0] and b[0]


def test_echec_de_l_agent_rendu_proprement(audit, tmp_path):
    reg = default_registry()
    gw = make_gateway(audit, reg, [])
    gw.socket_path = tmp_path / "s.sock"

    async def broken(cmd, env, cwd, timeout):
        return 1, json.dumps({"type": "result", "is_error": True, "result": "boum"})

    out = asyncio.run(AgentRunner(reg, gw, Path("/bin/claude"), tmp_path / "a", runner=broken).run("researcher", "x"))
    assert "Échec de l'agent : boum" in out and "non vérifiée" in out


# --- Codeur : bac à sable réel ---
def test_profil_sandbox():
    p = sandbox_profile("/tmp", "/Users/x")
    assert "(deny network*)" in p and '(deny file-read* (subpath "/Users/x"))' in p


@pytest.mark.skipif(not os.path.exists("/usr/bin/sandbox-exec"), reason="macOS seulement")
def test_code_run_dans_le_bac_a_sable(tmp_path):
    code = (
        "import os, socket\nprint(sum(range(10)))\n"
        "open('ok.txt','w').write('x')\n"
        f"try:\n    os.listdir({str(Path.home() / 'Documents')!r}); print('LU')\nexcept OSError: print('lecture refusée')\n"
        "try:\n    socket.create_connection(('1.1.1.1', 80), timeout=2); print('RESEAU')\n"
        "except OSError: print('réseau refusé')\n"
    )
    out = asyncio.run(code_run_tool().run({"code": code}))
    assert "45" in out and "lecture refusée" in out and "réseau refusé" in out
    assert "LU" not in out and "RESEAU" not in out


def test_code_run_delai(tmp_path):
    out = None
    with pytest.raises(Exception) as exc:
        out = asyncio.run(code_run_tool(timeout=1).run({"code": "while True: pass"}))
    assert out is None and "1 s" in str(exc.value)


def test_code_obfusque_bloque_tier0(audit):
    gw = ToolGateway([code_run_tool()], GuardrailsEngine(TIERS, audit=audit), audit)
    ok, text = asyncio.run(gw.call("code_run", {"code": "exec(base64.b64decode('cHJpbnQoMSk='))"}))
    assert not ok and "T0-OBFUSCATED" in text
