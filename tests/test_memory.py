"""Mémoire de Friday (phase 4) : stockage, rappel, oubli, extraction, audit."""

import json

import pytest

from friday.memory import ExtractedFact, MemoryStore, RuleBasedExtractor, query_terms


@pytest.fixture
def mem(tmp_path, audit):
    store = MemoryStore(tmp_path / "memory.db", audit)
    yield store
    store.close()


def _raw_bytes(path):
    data = path.read_bytes()
    wal = path.with_name(path.name + "-wal")
    if wal.exists():
        data += wal.read_bytes()
    return data


def test_test_de_la_spec_cafe_apres_redemarrage(tmp_path, audit):
    db = tmp_path / "memory.db"
    first = MemoryStore(db, audit)
    first.learn("Au fait, mon café préféré est l'espresso.")
    first.close()

    second = MemoryStore(db, audit)  # « redémarrage » : nouvelle instance, même base
    facts = second.recall("Tu te souviens de mon café préféré ?", k=3)
    assert facts and "espresso" in facts[0].text
    ctx = second.context_for("Tu te souviens de mon café préféré ?")
    assert ctx.startswith("[mémoire]") and "espresso" in ctx
    second.close()


def test_forget_efface_vraiment_y_compris_fts(tmp_path, audit):
    db = tmp_path / "memory.db"
    mem = MemoryStore(db, audit)
    mem.remember("La voiture du garage s'appelle zorglubium", category="maison")
    mem.remember("L'utilisateur aime le jazz")
    assert b"zorglubium" in _raw_bytes(db)

    assert mem.forget("oublie la voiture du garage") == 1
    assert mem.recall("garage zorglubium") == []
    assert mem._conn.execute(
        "SELECT count(*) FROM facts_fts WHERE facts_fts MATCH 'zorglubium'").fetchone()[0] == 0
    assert [f.text for f in mem.all()] == ["L'utilisateur aime le jazz"]
    mem.close()

    assert b"zorglubium" not in _raw_bytes(db)  # ni dans la base, ni dans le WAL
    again = MemoryStore(db, audit)
    assert again.recall("voiture garage") == []
    again.close()


def test_forget_demande_tous_les_mots(mem):
    mem.remember("Café préféré : espresso", key="preference.cafe")
    mem.remember("Thé préféré : vert", key="preference.the")
    assert mem.forget("café") == 1
    assert [f.text for f in mem.all()] == ["Thé préféré : vert"]
    assert mem.forget("chocolat") == 0
    assert mem.forget("le la de") == 0  # que des mots vides : rien


def test_forget_id_et_forget_all(mem):
    a = mem.remember("Fait un")
    mem.remember("Fait deux")
    assert mem.forget_id(a.id) is True
    assert mem.forget_id(a.id) is False
    assert mem.forget_all() == 1
    assert mem.all() == []


def test_meme_cle_remplace_et_meme_texte_rafraichit(mem):
    mem.learn("Mon café préféré est l'espresso")
    mem.learn("Mon café préféré est le cappuccino")
    texts = [f.text for f in mem.all()]
    assert texts == ["Café préféré : cappuccino"]
    assert not mem.recall("espresso")

    mem.remember("L'utilisateur aime le jazz")
    mem.remember("l'utilisateur aime le jazz")
    assert len(mem.all()) == 2
    assert mem._conn.execute("SELECT count(*) FROM facts_fts").fetchone()[0] == 2


def test_recall_classe_et_limite(mem):
    mem.remember("L'utilisateur habite à Lyon", category="identite")
    mem.remember("Café préféré : espresso", category="preference")
    mem.remember("L'utilisateur aime les cafés de Lyon", confidence=0.3)
    got = mem.recall("quel est mon café préféré", k=2)
    assert len(got) == 2 and got[0].text == "Café préféré : espresso"
    assert mem.recall("café", k=0) == []
    assert mem.recall("?!") == []


def test_fait_complet_stocke(mem):
    f = mem.remember("Aime la voile", category="loisir", source="claude", confidence=1.7)
    (stored,) = mem.all()
    assert (stored.text, stored.category, stored.source, stored.confidence) == (
        "Aime la voile", "loisir", "claude", 1.0)
    assert stored.created_at and stored.id == f.id
    with pytest.raises(ValueError):
        mem.remember("   ")


def test_context_for_vide_et_borne(mem):
    assert mem.context_for("quelle heure est-il") == ""
    for i in range(10):
        mem.remember(f"Projet numéro {i} : " + "détail " * 20)
    ctx = mem.context_for("projet", k=10, max_chars=300)
    assert 0 < len(ctx) <= 300


def test_audit_empreinte_seulement(mem, audit):
    mem.remember("Le mot secret est papaye")
    mem.forget("mot secret papaye")
    events = [e for e in audit.entries() if e.actor == "memory"]
    assert [e.event for e in events] == ["memory.remember", "memory.forget"]
    assert len(events[0].payload["text_sha256"]) == 16
    assert events[1].payload["count"] == 1
    assert all("papaye" not in str(e.payload) for e in events)
    assert audit.verify_chain()


def test_query_terms():
    assert query_terms("Tu te souviens de mon café préféré ?") == ['"cafe"*', '"prefe"*']
    assert query_terms('a"b OR c*') == []  # rien d'injectable dans FTS5


@pytest.mark.parametrize("utterance, text, key", [
    ("Je m'appelle Thaïne.", "L'utilisateur s'appelle Thaïne", "identite.nom"),
    ("je m’appelle Thaïne Fallou", "L'utilisateur s'appelle Thaïne Fallou", "identite.nom"),
    ("Mon café préféré est l'espresso", "Café préféré : espresso", "preference.cafe"),
    ("ma couleur préférée c'est le bleu !", "Couleur préférée : bleu", "preference.couleur"),
    ("Je préfère le thé au café", "L'utilisateur préfère le thé au café", None),
    ("J'habite à Lyon", "L'utilisateur habite à Lyon", "identite.ville"),
    ("j'adore la voile", "L'utilisateur aime la voile", None),
    ("je n'aime pas les épinards", "L'utilisateur n'aime pas les épinards", None),
])
def test_extracteur_a_regles(utterance, text, key):
    (fact,) = RuleBasedExtractor().extract(utterance)
    assert (fact.text, fact.key) == (text, key)


def test_extracteur_ignore_le_reste():
    assert RuleBasedExtractor().extract("Quelle heure est-il ?") == []


def test_extracteur_injectable(tmp_path, audit):
    class Fixed:
        def extract(self, utterance):
            return [ExtractedFact("Fait fixe", "test", None, 0.5)]

    store = MemoryStore(tmp_path / "m.db", audit, extractor=Fixed())
    (f,) = store.learn("n'importe quoi", source="claude")
    assert (f.text, f.category, f.source, f.confidence) == ("Fait fixe", "test", "claude", 0.5)
    store.close()


# --- Branchement au cerveau ---
import asyncio as _asyncio  # noqa: E402

from friday.brain import HybridBrain, LocalBrain  # noqa: E402
from friday.conductor import Conductor  # noqa: E402


class EchoBrain:
    def __init__(self):
        self.prompts = []
        self.resets = 0

    def reset(self):
        self.resets += 1

    async def stream(self, text, decision, source="text"):
        self.prompts.append(text)
        yield "ok"

    async def respond(self, text, decision, source="text"):
        self.prompts.append(text)
        return "ok"


def test_cerveau_apprend_rappelle_et_oublie(tmp_path, audit):
    remote = EchoBrain()
    h = HybridBrain(LocalBrain(), remote, MemoryStore(tmp_path / "m.db", audit))
    d = Conductor().handle("x")

    def ask(t):
        return _asyncio.run(_collect(h.stream(t, d)))

    async def _collect(gen):
        return "".join([x async for x in gen])

    ask("Mon café préféré est le cappuccino.")
    # après « redémarrage » : nouvelle mémoire sur la même base
    h2 = HybridBrain(LocalBrain(), remote, MemoryStore(tmp_path / "m.db", audit))
    h = h2
    ask("Quel est mon café préféré ?")
    assert "[mémoire]" in remote.prompts[-1] and "cappuccino" in remote.prompts[-1]
    assert ask("Oublie mon café préféré.") == "C'est oublié."
    assert len(remote.prompts) == 2                                     # l'oubli ne passe pas par Claude
    assert remote.resets == 1                                           # et efface la conversation de Claude
    ask("Quel est mon café préféré ?")
    assert "cappuccino" not in remote.prompts[-1]
    assert ask("Oublie ma voiture.") == "Je n'avais rien retenu à ce sujet."


# --- Secrets : jamais mémorisés (filtre en dur) ---
from friday.memory import SecretRefused, contains_secret  # noqa: E402
from friday.memory.claude_extractor import ClaudeFactExtractor, parse_facts  # noqa: E402


@pytest.mark.parametrize("text", [
    "Mon mot de passe Wi-Fi est soleil42",
    "Le mdp de la box : Azerty!2026",
    "Le code de la porte, c'est 4512",
    "Mon code PIN est 1234",
    "Le digicode de l'immeuble est B2047",
    "Ma carte : 4111 1111 1111 1111",                # Luhn valide
    "Mon IBAN est FR76 3000 6000 0112 3456 7890 189",
    "Le cryptogramme est 123",
    "Ma clé API est sk-ant-api03-abcdefghijklmnop",
    "password: hunter22",
])
def test_secret_detecte(text):
    assert contains_secret(text)


@pytest.mark.parametrize("text", [
    "La sœur de l'utilisateur s'appelle Awa",
    "L'utilisateur habite à Lyon depuis 2019",
    "L'utilisateur appelle sa mère le 12 de chaque mois",
    "L'utilisateur prépare un marathon",
    "Le numéro de bus de l'utilisateur est le 1234567890123",   # pas un numéro Luhn
])
def test_fait_anodin_accepte(text):
    assert not contains_secret(text)


def test_remember_refuse_un_secret_et_audite(mem, audit):
    with pytest.raises(SecretRefused):
        mem.remember("Mon code PIN est 1234")
    assert mem.all() == []
    refused = [e for e in audit.entries() if e.event == "memory.refused"]
    assert refused and "1234" not in str(refused[0].payload)


def test_learn_ignore_les_secrets(tmp_path, audit):
    class Leaky:
        def extract(self, utterance):
            return [ExtractedFact("Le mot de passe de l'utilisateur est soleil42"),
                    ExtractedFact("L'utilisateur aime le jazz")]

    store = MemoryStore(tmp_path / "m.db", audit, extractor=Leaky())
    assert [f.text for f in store.learn("…")] == ["L'utilisateur aime le jazz"]
    assert b"soleil42" not in _raw_bytes(tmp_path / "m.db")
    store.close()


# --- Extraction par Claude ---
def test_parse_facts():
    raw = 'Voici : {"facts": [{"text": "La sœur de l\'utilisateur s\'appelle Awa", "category": "proches", ' \
          '"key": "Proches.Sœur.Prénom", "confidence": 0.9}, {"text": "x"}, {"text": "Fait", "category": "??", ' \
          '"key": null, "confidence": "abc"}]}'
    a, b = parse_facts(raw)
    assert (a.category, a.key, a.confidence) == ("proches", "proches.soeur.prenom", 0.9)
    assert (b.category, b.key, b.confidence) == ("general", None, 0.8)
    assert parse_facts('{"facts": []}') == []
    with pytest.raises(ValueError):
        parse_facts("pas de json")


def _fake_runner(result, calls):
    async def run(cmd, env, cwd, timeout):
        calls.append((list(cmd), cwd))
        return 0, json.dumps({"type": "result", "result": result, "session_id": "s"})
    return run


def test_extracteur_claude_appel_separe(tmp_path):
    calls = []
    ex = ClaudeFactExtractor(tmp_path / "claude", tmp_path / "claude-memory", runner=_fake_runner(
        '{"facts": [{"text": "La sœur de l\'utilisateur s\'appelle Awa", "category": "proches", '
        '"key": "proches.soeur.prenom", "confidence": 0.9}]}', calls))
    (fact,) = _asyncio.run(ex.aextract("Ma sœur s'appelle Awa", "Enchantée, Awa !"))
    assert fact.key == "proches.soeur.prenom"
    cmd, cwd = calls[0]
    assert cmd[cmd.index("--model") + 1] == "haiku"
    assert "--resume" not in cmd and cmd[cmd.index("--tools") + 1] == ""   # one-shot, sans outils
    assert "--no-session-persistence" in cmd                                 # rien de l'échange gardé sur disque
    assert cwd == tmp_path / "claude-memory"                                 # sessions à part
    assert "Ma sœur s'appelle Awa" in cmd[cmd.index("-p") + 1]


def _deep(facts=None, fail=False, calls=None):
    class Deep:
        async def aextract(self, utterance, reply="", known=()):
            if calls is not None:
                calls.append((utterance, reply, list(known)))
            if fail:
                raise RuntimeError("Claude absent")
            return facts or []
    return Deep()


def test_alearn_claude_puis_repli_sur_les_regles(tmp_path, audit):
    calls = []
    store = MemoryStore(tmp_path / "m.db", audit, deep_extractor=_deep(
        [ExtractedFact("La sœur de l'utilisateur s'appelle Awa", "proches", "proches.soeur.prenom", 0.9),
         ExtractedFact("Le code de la porte est 4512")], calls=calls))
    facts = _asyncio.run(store.alearn("Ma sœur s'appelle Awa", "Bonjour Awa"))
    assert [f.text for f in facts] == ["La sœur de l'utilisateur s'appelle Awa"]   # secret filtré
    assert calls[0][:2] == ("Ma sœur s'appelle Awa", "Bonjour Awa")
    # un passage secret ne part jamais à l'extracteur, le reste si
    _asyncio.run(store.alearn("Je bois mon café sans sucre, et mon code de carte bleue est 4821."))
    assert calls[1][0] == "Je bois mon café sans sucre" and "4821" not in str(calls[1])
    _asyncio.run(store.alearn("Mon code PIN est 1234."))
    assert len(calls) == 2                                                   # tout est secret : aucun appel
    store.close()

    broken = MemoryStore(tmp_path / "b.db", audit, deep_extractor=_deep(fail=True))
    assert [f.text for f in _asyncio.run(broken.alearn("J'habite à Dakar"))] == ["L'utilisateur habite à Dakar"]
    broken.close()


def test_cerveau_extrait_en_tache_de_fond_apres_la_reponse(tmp_path, audit):
    order = []

    class SlowDeep:
        async def aextract(self, utterance, reply="", known=()):
            order.append(("extract", reply))
            return [ExtractedFact("La sœur de l'utilisateur s'appelle Awa", "proches", "proches.soeur.prenom", 0.9)]

    remote = EchoBrain()
    store = MemoryStore(tmp_path / "m.db", audit, deep_extractor=SlowDeep())
    h = HybridBrain(LocalBrain(), remote, store)
    d = Conductor().handle("x")

    async def scenario():
        out = []
        async for delta in h.stream("Ma sœur s'appelle Awa.", d):
            out.append(delta)
            order.append(("delta", delta))
        assert store.all() == []                  # rien n'a encore bloqué la réponse
        await h.settle()
        return out

    assert _asyncio.run(scenario()) == ["ok"]
    assert order == [("delta", "ok"), ("extract", "ok")]
    h2 = HybridBrain(LocalBrain(), remote, MemoryStore(tmp_path / "m.db", audit, deep_extractor=SlowDeep()))
    _asyncio.run(h2.respond("Comment s'appelle ma sœur ?", d))
    assert "Awa" in remote.prompts[-1] and "[mémoire]" in remote.prompts[-1]


# --- Protocole app ↔ cœur : memory_list / memory_forget ---
from friday.voice import CoreServer, parse_app_message  # noqa: E402


def test_protocole_memoire(tmp_path, audit):
    assert parse_app_message('{"type":"memory_list"}') == {"type": "memory_list"}
    assert parse_app_message('{"type":"memory_forget","id":3}')["id"] == 3
    assert parse_app_message('{"type":"memory_forget"}') is None
    assert parse_app_message('{"type":"memory_forget","id":true}') is None

    remote = EchoBrain()
    store = MemoryStore(tmp_path / "m.db", audit)
    a = store.remember("L'utilisateur aime le jazz")
    store.remember("La sœur de l'utilisateur s'appelle Awa")
    server = CoreServer(Conductor(), HybridBrain(LocalBrain(), remote, store))
    listed = _asyncio.run(server.handle({"type": "memory_list"}))
    assert listed["available"] and [f["text"] for f in listed["facts"]] == [
        "La sœur de l'utilisateur s'appelle Awa", "L'utilisateur aime le jazz"]
    assert set(listed["facts"][0]) == {"id", "text", "category", "created_at"}
    out = _asyncio.run(server.handle({"type": "memory_forget", "id": a.id}))
    assert out["forgot"] and [f["text"] for f in out["facts"]] == ["La sœur de l'utilisateur s'appelle Awa"]
    assert remote.resets == 1                     # la conversation de Claude est effacée aussi
    assert not _asyncio.run(server.handle({"type": "memory_forget", "id": 999}))["forgot"]
    assert remote.resets == 1
    no_mem = CoreServer(Conductor(), LocalBrain())
    assert _asyncio.run(no_mem.handle({"type": "memory_list"})) == {"type": "memory", "facts": [], "available": False}


def test_claude_sait_qu_il_a_une_memoire(tmp_path, audit):
    from friday.claude_brain import PersistentClaudeBrain, system_prompt
    assert "[mémoire]" not in system_prompt({}, None)
    remote = PersistentClaudeBrain(tmp_path / "claude", {}, tmp_path)
    HybridBrain(LocalBrain(), remote, MemoryStore(tmp_path / "m.db", audit))
    prompt = remote.persistent_command()
    assert "[mémoire]" in prompt[prompt.index("--system-prompt") + 1]


def test_redact_secrets():
    from friday.memory.secrets import redact_secrets
    assert redact_secrets("J'aime le jazz.") == "J'aime le jazz."
    assert redact_secrets("Ma sœur s'appelle Awa et mon mot de passe est soleil42.") == "Ma sœur s'appelle Awa"
    assert redact_secrets("Mon code PIN est 1234") == ""


def test_soeur_retrouvee_malgre_la_ligature(mem):
    mem.remember("L'utilisateur a une sœur prénommée Awa.", category="proches")
    assert [f.text for f in mem.recall("Comment s'appelle ma sœur ?")] == ["L'utilisateur a une sœur prénommée Awa."]
    assert mem.recall("ma soeur") and mem.forget("oublie ma sœur") == 1
