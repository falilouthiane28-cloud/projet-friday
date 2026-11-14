"""Mémoire de Friday (phase 4) : stockage, rappel, oubli, extraction, audit."""

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
    mem.remember("Le code de la porte du garage est zorglubium", category="maison")
    mem.remember("L'utilisateur aime le jazz")
    assert b"zorglubium" in _raw_bytes(db)

    assert mem.forget("oublie le code du garage") == 1
    assert mem.recall("garage zorglubium") == []
    assert mem._conn.execute(
        "SELECT count(*) FROM facts_fts WHERE facts_fts MATCH 'zorglubium'").fetchone()[0] == 0
    assert [f.text for f in mem.all()] == ["L'utilisateur aime le jazz"]
    mem.close()

    assert b"zorglubium" not in _raw_bytes(db)  # ni dans la base, ni dans le WAL
    again = MemoryStore(db, audit)
    assert again.recall("code garage") == []
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
