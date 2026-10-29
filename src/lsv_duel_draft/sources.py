"""Network sources: the cube list from CubeCobra, card data and images from Scryfall.

Scryfall rejects generic HTTP-library user agents (including the one Tabletop
Simulator sends), so every request here identifies this app, and requests are
paced to stay under Scryfall's published rate limit.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from lsv_duel_draft.models import Card, Face

USER_AGENT = "lsv-duel-draft/0.1 (+https://github.com/GeneticMarauder/lsv-duel-draft)"
SCRYFALL_BATCH = 75
SCRYFALL_DELAY_S = 0.12
# The standard Magic card back (Scryfall card_back_id 0aeebaf5-...), large size.
MAGIC_CARD_BACK = "https://backs.scryfall.io/large/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg"
# Cards we play in place of ones on the CubeCobra list: cube card name -> replacement name.
CARD_SWAPS = {"Cogwork Librarian": "Booster Tutor"}


def make_client() -> httpx.Client:
    """HTTP client with the identifying headers Scryfall requires."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json;q=0.9,*/*;q=0.8"},
        timeout=30.0,
        follow_redirects=True,
    )


def fetch_cube_ids(client: httpx.Client, cube_id: str) -> tuple[list[str], list[str]]:
    """Scryfall ids of the cube's mainboard and its basic lands (printings as chosen by the cube owner)."""
    resp = client.get(f"https://cubecobra.com/cube/api/cubeJSON/{cube_id}")
    resp.raise_for_status()
    cards = resp.json()["cards"]
    return [c["cardID"] for c in cards["mainboard"]], [c["cardID"] for c in cards.get("basics", [])]


def _face_text(face: dict[str, Any]) -> str:
    """Hover text for a face: type line, cost, rules text and P/T or loyalty."""
    lines = [f"{face.get('type_line', '')} {face.get('mana_cost', '')}".strip()]
    if face.get("oracle_text"):
        lines.append(face["oracle_text"])
    if face.get("power") is not None:
        lines.append(f"[b]{face['power']}/{face['toughness']}[/b]")
    elif face.get("loyalty") is not None:
        lines.append(f"[b]Loyalty {face['loyalty']}[/b]")
    return "\n".join(lines)


def card_from_scryfall(data: dict[str, Any]) -> Card:
    """Convert a Scryfall card object into a :class:`Card`.

    Double-faced cards (faces with their own images) get a ``back``; split,
    adventure and flip cards share one image, so their faces' text is joined.
    """
    faces = data.get("card_faces") or []
    front_type = faces[0].get("type_line", "") if faces else data.get("type_line", "")
    common = {"scryfall_id": data["id"], "cmc": data.get("cmc", 0), "is_land": "Land" in front_type}
    if faces and "image_uris" not in data:
        front, back = faces[0], faces[1]
        return Card(
            front=Face(front["name"], _face_text(front), front["image_uris"]["normal"]),
            back=Face(back["name"], _face_text(back), back["image_uris"]["normal"]),
            **common,
        )
    text = "\n\n".join(f"{f['name']}\n{_face_text(f)}" for f in faces) if faces else _face_text(data)
    return Card(front=Face(data["name"], text, data["image_uris"]["normal"]), **common)


def fetch_cards(client: httpx.Client, ids: list[str]) -> list[Card]:
    """Look up cards by Scryfall id (batched), returned in the same order as ``ids``."""
    by_id: dict[str, Card] = {}
    unique = list(dict.fromkeys(ids))
    for start in range(0, len(unique), SCRYFALL_BATCH):
        batch = unique[start : start + SCRYFALL_BATCH]
        resp = client.post(
            "https://api.scryfall.com/cards/collection",
            json={"identifiers": [{"id": i} for i in batch]},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("not_found"):
            raise RuntimeError(f"Scryfall could not find: {body['not_found']}")
        for data in body["data"]:
            by_id[data["id"]] = card_from_scryfall(data)
        time.sleep(SCRYFALL_DELAY_S)
    return [by_id[i] for i in ids]


def fetch_cards_by_name(client: httpx.Client, names: list[str]) -> dict[str, Card]:
    """Look up cards by exact name; returns them keyed by the requested name."""
    if not names:
        return {}
    resp = client.post("https://api.scryfall.com/cards/collection",
                       json={"identifiers": [{"name": n} for n in names]})
    resp.raise_for_status()
    body = resp.json()
    if body.get("not_found"):
        raise RuntimeError(f"Scryfall could not find: {body['not_found']}")
    time.sleep(SCRYFALL_DELAY_S)
    by_name = {c.front.name: c for c in map(card_from_scryfall, body["data"])}
    return {n: by_name[n] for n in names}


def swap_cards(cards: list[Card], swaps: dict[str, Card]) -> tuple[list[Card], list[str]]:
    """Replace cube cards by name (same position in the list); also returns swap names not in the cube."""
    out = [swaps.get(c.front.name, c) for c in cards]
    present = {c.front.name for c in cards}
    return out, [name for name in swaps if name not in present]


def download_image(client: httpx.Client, url: str, cache_dir: Path) -> Path:
    """Download a card image once; later builds reuse the cached file."""
    # Front and back faces share an id, so keep the "front/b/d/" path parts in the name.
    name = "_".join(url.split("?")[0].rstrip("/").split("/")[-4:])
    path = cache_dir / name
    if path.exists() and path.stat().st_size > 0:
        return path
    cache_dir.mkdir(parents=True, exist_ok=True)
    resp = client.get(url, headers={"Accept": "image/*"})
    resp.raise_for_status()
    path.write_bytes(resp.content)
    time.sleep(SCRYFALL_DELAY_S)
    return path
