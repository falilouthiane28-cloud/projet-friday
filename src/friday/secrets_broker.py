"""Courtier de secrets : seul point d'accès au trousseau macOS.

- Seuls les services `friday-*` peuvent être lus (pas les mots de passe du maître).
- Le secret est lu au moment de l'appel réseau, jamais gardé en attribut, jamais écrit
  dans la configuration, les logs, l'audit ou la mémoire ; Claude ne le voit jamais (les
  outils ne renvoient que le résultat de l'appel).
- Aucun outil MCP n'expose le courtier : un agent ne manipule que des noms de service.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence

CommandRunner = Callable[[Sequence[str]], Awaitable[tuple[int, str, str]]]

ACCOUNT = "friday"
_SERVICE = re.compile(r"^friday-[a-z0-9][a-z0-9\-]{1,60}$")


class SecretUnavailable(Exception):
    """Secret absent du trousseau, ou service non autorisé."""


def add_command(service: str) -> str:
    """Commande à donner au maître pour ranger un secret (saisi par lui, jamais par Friday)."""
    return f"security add-generic-password -U -s {service} -a {ACCOUNT} -w"


class SecretBroker:
    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner

    @staticmethod
    def allowed(service: str) -> bool:
        return bool(_SERVICE.match(service))

    async def read(self, service: str) -> str:
        if not self.allowed(service):
            raise SecretUnavailable(f"Service de trousseau non autorisé : {service!r} (seuls les services friday-*).")
        try:
            code, out, _ = await self._runner(["security", "find-generic-password", "-s", service, "-a", ACCOUNT, "-w"])
        except OSError:
            code, out = 1, ""
        secret = out.strip()
        if code != 0 or not secret:
            raise SecretUnavailable(f"Secret absent du trousseau. Le ranger avec : {add_command(service)}.")
        return secret
