import asyncio
from datetime import datetime

import pytest

from friday.brain import LocalBrain, dire_date, dire_heure
from friday.conductor import Conductor


@pytest.mark.parametrize(
    "h, m, attendu",
    [(10, 5, "Il est 10 heures 05."), (1, 0, "Il est une heure."), (0, 0, "Il est minuit."), (12, 0, "Il est midi.")],
)
def test_dire_heure(h, m, attendu):
    assert dire_heure(datetime(2026, 11, 14, h, m)) == attendu


def test_dire_date():
    assert dire_date(datetime(2026, 11, 14)) == "Nous sommes le samedi 14 novembre 2026."
    assert dire_date(datetime(2026, 12, 1)) == "Nous sommes le mardi 1er décembre 2026."


def test_local_brain_repond_a_l_heure():
    brain = LocalBrain(clock=lambda: datetime(2026, 11, 14, 9, 30))
    text = "quelle heure est-il"
    reply = asyncio.run(brain.respond(text, Conductor().handle(text)))
    assert reply == "Il est 9 heures 30."
