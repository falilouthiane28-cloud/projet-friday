"""Filtre en dur : aucun secret n'entre dans la mémoire de Friday.

Mots de passe, codes (PIN, digicode, 2FA, CVV), numéros de carte bancaire (Luhn),
IBAN, clés d'API et jetons. Le filtre préfère refuser un fait anodin que retenir
un secret. Il s'applique à l'écriture (`MemoryStore.remember`), quelle que soit la
source du fait (règles, Claude, ajout direct).
"""

from __future__ import annotations

import re
import unicodedata

from ..guardrails.tier0 import _CREDENTIAL_PATTERNS


def _fold(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in norm if not unicodedata.combining(c))


# Mots qui désignent un secret : le fait est refusé même sans valeur visible
# (« mon mot de passe Wi-Fi est soleil42 », « le code de la porte, c'est 1234 »).
_SECRET_WORDS = re.compile(
    r"\b(mots? de passe|mdp|password|passwd|passphrase|phrase secrete|identifiants?|login"
    r"|code (?:pin|secret|confidentiel|d'acces|d acces|de (?:la |l')?(?:carte|porte|portail|immeuble|alarme|coffre|telephone|deverrouillage))"
    r"|pin|digicode|cvv|cvc|cryptogramme|code (?:de )?securite|2fa|otp|code de verification|code a usage unique"
    r"|iban|rib|bic|numero de (?:carte|compte|securite sociale|passeport)|securite sociale"
    r"|cle (?:d'api|api|privee|secrete)|api key|token|jeton|seed|phrase de recuperation)\b")

_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")
_DIGITS = re.compile(r"(?:\d[ \-.]?){13,19}")
_CODE_NEAR = re.compile(r"\bcode\b[^.!?]{0,30}?\b\d{4,8}\b|\b\d{4,8}\b[^.!?]{0,15}?\bcode\b")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def contains_secret(text: str) -> bool:
    """True si le texte contient ou désigne un secret (jamais mémorisé)."""
    if any(p.search(text) for p in _CREDENTIAL_PATTERNS):
        return True
    folded = _fold(text).replace("’", "'")
    if _SECRET_WORDS.search(folded) or _CODE_NEAR.search(folded):
        return True
    if _IBAN.search(text.upper()):
        return True
    for m in _DIGITS.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return True
    return False


_CLAUSES = re.compile(r"(?<=[.!?;,])\s+|\s+(?=(?:et|mais|puis)\s)", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Retire les propositions qui contiennent un secret ; garde le reste ("" si tout est secret)."""
    if not contains_secret(text):
        return text
    kept = [c for c in _CLAUSES.split(text) if c.strip() and not contains_secret(c)]
    return " ".join(kept).strip(" ,;")
