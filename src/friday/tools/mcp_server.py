"""Serveur MCP stdio de Friday : simple relais vers le cœur, sans dépendance.

Claude Code le lance (via `--mcp-config`) ; il parle JSON-RPC 2.0 sur stdin/stdout
(une ligne par message) et transmet `tools/list` et `tools/call` au cœur par le socket
Unix de `ToolGateway`. Toute la logique (outils, guardrails, confirmation, audit) reste
dans le cœur : ce fichier ne décide rien et n'importe pas le paquet `friday`.

    python -I mcp_server.py --socket /chemin/tools.sock
"""

from __future__ import annotations

import json
import socket
import sys
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "friday", "version": "0.1.0"}
CALL_TIMEOUT_S = 120          # au-delà des 60 s d'attente de confirmation


def ask_core(sock_path: str, request: dict[str, Any], timeout: float = CALL_TIMEOUT_S) -> dict[str, Any]:
    """Une requête JSON par connexion, une réponse JSON en retour."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(sock_path)
        s.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.decode() or "{}")


def handle(msg: dict[str, Any], sock_path: str) -> dict[str, Any] | None:
    """Message JSON-RPC → réponse (None pour une notification)."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:                              # notification (initialized, cancelled…)
        return None

    def ok(result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return ok({"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        try:
            tools = ask_core(sock_path, {"op": "list"}).get("tools", [])
        except OSError:
            tools = []
        return ok({"tools": tools})
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            res = ask_core(sock_path, {"op": "call", "name": params.get("name"),
                                       "arguments": params.get("arguments") or {}})
            text, is_error = str(res.get("text", "")), not res.get("ok", False)
        except (OSError, ValueError) as exc:
            text, is_error = f"Le cœur de Friday est injoignable ({exc}).", True
        return ok({"content": [{"type": "text", "text": text}], "isError": is_error})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"méthode inconnue : {method}"}}


def main(argv: list[str]) -> int:
    if "--socket" not in argv or argv.index("--socket") + 1 >= len(argv):
        print("usage : mcp_server.py --socket <chemin>", file=sys.stderr)
        return 2
    sock_path = argv[argv.index("--socket") + 1]
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out: dict[str, Any] | None = {"jsonrpc": "2.0", "id": None,
                                          "error": {"code": -32700, "message": "JSON invalide"}}
        else:
            out = handle(msg, sock_path) if isinstance(msg, dict) else None
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
