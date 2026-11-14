import pytest

from friday.conductor import AGENT_BY_INTENT, Conductor, Intent, KeywordIntentClassifier


@pytest.mark.parametrize(
    "text, intent",
    [
        ("Allume la lumière du salon", Intent.HOME),
        ("Éteins le chauffage de la chambre", Intent.HOME),
        ("Turn on the kitchen lights", Intent.HOME),
        ("Quelle est l'utilisation du CPU ?", Intent.SYSTEM),
        ("Il reste combien de batterie sur mon Mac ?", Intent.SYSTEM),
        ("Rappelle-moi d'appeler le dentiste demain à 9h", Intent.SCHEDULE),
        ("Ajoute une réunion dans mon agenda vendredi", Intent.SCHEDULE),
        ("Envoie un e-mail à Paul pour confirmer", Intent.COMMUNICATION),
        ("Lis mes derniers messages WhatsApp", Intent.COMMUNICATION),
        ("Corrige ce bug dans mon script Python", Intent.CODE),
        ("Fais un commit avec les tests", Intent.CODE),
        ("Cherche les dernières actualités sur Apple", Intent.RESEARCH),
        ("Quelle est la météo à Paris ?", Intent.RESEARCH),
        ("Bonjour Friday, comment allez-vous ?", Intent.CONVERSATION),
        ("Merci beaucoup", Intent.CONVERSATION),
    ],
)
def test_classifie_message_texte(text, intent):
    result = KeywordIntentClassifier().classify(text)
    assert result.intent is intent, (text, result)
    assert result.confidence > 0


def test_message_sans_indice_retombe_sur_conversation():
    result = KeywordIntentClassifier().classify("hmm")
    assert result.intent is Intent.CONVERSATION
    assert result.matched == ()


def test_message_vide():
    assert KeywordIntentClassifier().classify("   ").intent is Intent.CONVERSATION


def test_insensible_aux_accents_et_a_la_casse():
    c = KeywordIntentClassifier()
    assert c.classify("ETEINS LA LUMIERE").intent is c.classify("éteins la lumière").intent is Intent.HOME


def test_conductor_route_vers_le_bon_agent_et_audite(audit):
    conductor = Conductor(audit=audit)
    decision = conductor.handle("Allume les lampes du salon")
    assert decision.intent is Intent.HOME
    assert decision.agent == AGENT_BY_INTENT[Intent.HOME] == "home_controller"
    entries = audit.entries()
    assert entries[-1].event == "intent.classified"
    assert entries[-1].payload["intent"] == "home"
    assert "Allume" not in str(entries[-1].payload)   # pas de texte brut dans l'audit
