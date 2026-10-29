"""core.build-and-install :: save_inspect.py

Inspect a Tabletop Simulator save file (read-only): summary, object list, and
optionally dump every embedded Lua script / XML UI to a folder so you can read
or diff them. Useful to check which script a save *actually* contains (old
saves and autosaves keep the script they were made with).

Examples (from the repo root)::

    uv run python core/build-and-install/scripts/save_inspect.py "dist/Draft Duel.json"
    uv run python core/build-and-install/scripts/save_inspect.py SAVE.json --objects
    uv run python core/build-and-install/scripts/save_inspect.py SAVE.json --dump out/scripts
    uv run python core/build-and-install/scripts/save_inspect.py --saves-dir

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def tts_saves_dirs() -> list[Path]:
    """Existing TTS Saves folders (including OneDrive-redirected Documents on Windows)."""
    home = Path.home()
    candidates = [home / "Documents", home / "OneDrive" / "Documents"]
    if os.environ.get("OneDrive"):
        candidates.append(Path(os.environ["OneDrive"]) / "Documents")
    dirs = [d / "My Games" / "Tabletop Simulator" / "Saves" for d in candidates]
    return [d for d in dict.fromkeys(dirs) if d.is_dir()]


def walk(objects: list[dict[str, Any]], depth: int = 0) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (depth, object) for every object, including deck contents and alternate states."""
    for obj in objects:
        yield depth, obj
        yield from walk(obj.get("ContainedObjects") or [], depth + 1)
        for state in (obj.get("States") or {}).values():
            yield from walk([state], depth + 1)


def label(obj: dict[str, Any]) -> str:
    """One-line description of a save object."""
    name = obj.get("Nickname") or ""
    return f"{obj.get('GUID', '??????')} {obj.get('Name', '?')}" + (f" '{name}'" if name else "")


def summary(save: dict[str, Any]) -> list[str]:
    """Headline facts about a save."""
    objs = list(walk(save.get("ObjectStates") or []))
    types = Counter(o.get("Name", "?") for _, o in objs)
    scripted = [o for _, o in objs if o.get("LuaScript")]
    lua = save.get("LuaScript") or ""
    return [
        f"SaveName : {save.get('SaveName')}",
        f"Date     : {save.get('Date')}",
        f"Table    : {save.get('Table')}   Sky: {save.get('Sky')}",
        (f"Global   : {len(lua.splitlines())} Lua lines, {len(save.get('XmlUI') or '')} chars of XML UI, "
         f"state {len(save.get('LuaScriptState') or '')} chars"),
        f"UI assets: {len(save.get('CustomUIAssets') or [])}",
        f"Objects  : {len(objs)} incl. contents -> "
        + ", ".join(f"{n} {t}" for t, n in types.most_common(8)),
        f"Scripted objects: {len(scripted)}",
    ]


def safe_name(text: str) -> str:
    """File-system safe version of an object label."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")[:80] or "object"


def dump(save: dict[str, Any], out: Path) -> list[Path]:
    """Write Global and per-object scripts/UI into ``out``; return written paths."""
    out.mkdir(parents=True, exist_ok=True)
    written = []

    def write(name: str, text: str) -> None:
        path = out / name
        path.write_text(text, encoding="utf-8")
        written.append(path)

    if save.get("LuaScript"):
        write("Global.lua", save["LuaScript"])
    if save.get("XmlUI"):
        write("Global.xml", save["XmlUI"])
    if save.get("LuaScriptState"):
        write("Global.state.json", save["LuaScriptState"])
    for _, obj in walk(save.get("ObjectStates") or []):
        base = safe_name(label(obj))
        if obj.get("LuaScript"):
            write(f"{base}.lua", obj["LuaScript"])
        if obj.get("XmlUI"):
            write(f"{base}.xml", obj["XmlUI"])
    return written


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2], allow_abbrev=False)
    parser.add_argument("save", nargs="?", type=Path, help="path to a TTS save .json")
    parser.add_argument("--objects", action="store_true", help="list every object (indented by nesting)")
    parser.add_argument("--dump", type=Path, metavar="DIR", help="write embedded scripts/UI into DIR")
    parser.add_argument("--saves-dir", action="store_true", help="print the TTS Saves folder(s) and exit")
    args = parser.parse_args(argv)

    if args.saves_dir:
        dirs = tts_saves_dirs()
        print("\n".join(str(d) for d in dirs) or "No Tabletop Simulator Saves folder found.")
        return 0
    if args.save is None:
        parser.error("a save path is required (or --saves-dir)")
    if not args.save.is_file():
        print(f"Not a file: {args.save}", file=sys.stderr)
        return 2
    try:
        save = json.loads(args.save.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Not valid JSON: {exc}", file=sys.stderr)
        return 2

    print("\n".join(summary(save)))
    if args.objects:
        print()
        for depth, obj in walk(save.get("ObjectStates") or []):
            if depth <= 1:
                print("  " * depth + label(obj))
    if args.dump:
        paths = dump(save, args.dump)
        print(f"\nWrote {len(paths)} file(s) to {args.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
