"""Test in the running Tabletop Simulator game without touching the screen.

TTS listens on localhost:39999 for its external-editor API and answers on
localhost:39998. ``uv run draft-duel-live exec "<lua>"`` runs Lua in Global and
prints what the game says back (prints and errors); ``uv run draft-duel-live load``
loads the built save's Global script and UI into the open game (the editor's
"Save & Play": TTS saves the game to its save file, then reloads that file — so
after ``uv run draft-duel`` has installed a fresh save, this is a fresh load).
Script-local variables (``draft``, ``L``, ``piles``) are not reachable; call the
script's global functions instead.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

SEND_PORT = 39999
LISTEN_PORT = 39998
SAVE = Path(__file__).resolve().parents[2] / "dist" / "Draft Duel.json"


def _send_and_collect(message: dict, seconds: float) -> list[dict]:
    """Sends one message to TTS and returns every message it sends back within ``seconds``."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LISTEN_PORT))
    srv.listen(5)
    srv.settimeout(0.5)
    try:
        with socket.create_connection(("127.0.0.1", SEND_PORT), timeout=5) as conn:
            conn.sendall(json.dumps(message).encode())
        out: list[dict] = []
        end = time.time() + seconds
        while time.time() < end:
            try:
                conn, _ = srv.accept()
            except TimeoutError:
                continue
            data = b""
            conn.settimeout(2)
            try:
                while chunk := conn.recv(1 << 20):
                    data += chunk
            except TimeoutError:
                pass
            conn.close()
            try:
                out.append(json.loads(data.decode("utf-8", "replace")))
            except ValueError:
                out.append({"messageID": -1, "raw": data[:500].decode("utf-8", "replace")})
        return out
    finally:
        srv.close()


def _report(messages: list[dict]) -> int:
    """Prints prints (2), errors (3) and return values (5); returns 1 if TTS reported an error."""
    failed = 0
    for m in messages:
        mid = m.get("messageID")
        if mid == 2:
            print(m.get("message", ""))
        elif mid == 3:
            print("ERROR", m.get("error", ""))
            failed = 1
        elif mid == 5:
            print("RETURN", m.get("returnValue"))
        elif mid == 1:
            print("(game reloaded with:", ", ".join(s.get("name", "?") for s in m.get("scriptStates", [])) + ")")
    return failed


def main() -> int:
    """CLI: ``exec <lua> [--wait S]`` or ``load [--save PATH]``."""
    parser = argparse.ArgumentParser(prog="draft-duel-live", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("exec", help="run Lua in Global and print what the game says back")
    ex.add_argument("lua")
    ex.add_argument("--wait", type=float, default=3, help="seconds to listen for output")
    ld = sub.add_parser("load", help="load the built save's script and UI into the open game")
    ld.add_argument("--save", type=Path, default=SAVE)
    args = parser.parse_args()
    if args.cmd == "exec":
        return _report(_send_and_collect({"messageID": 3, "guid": "-1", "script": args.lua}, args.wait))
    save = json.loads(args.save.read_text(encoding="utf-8"))
    states = [{"name": "Global", "guid": "-1", "script": save["LuaScript"], "ui": save["XmlUI"]}]
    return _report(_send_and_collect({"messageID": 1, "scriptStates": states}, 10))


if __name__ == "__main__":
    raise SystemExit(main())
