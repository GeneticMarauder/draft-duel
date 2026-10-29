"""The cubes a save offers and where their card lists come from.

Two kinds of source:

- ``cubecobra``: a CubeCobra cube id (cards come with the owner's chosen printings).
- ``mtgo``: Magic Online's official Vintage Cube page, which always shows the
  latest iteration; card names are looked up on Scryfall.

Add a cube by adding it to :data:`CUBES`, or pass ``cubecobra:<id>`` on the command line.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import httpx

from draft_duel.models import Card
from draft_duel.sources import fetch_cards, fetch_cards_by_name, fetch_cube_ids

MTGO_VINTAGE_URL = "https://www.mtgo.com/vintage-cube-cardlist"


@dataclass(frozen=True)
class CubeSource:
    """Where a cube's list comes from. ``key`` is short and stable: it is saved with the game."""

    key: str
    name: str
    kind: str  # "cubecobra" or "mtgo"
    ref: str  # CubeCobra cube id, or the MTGO card-list URL


CUBES: dict[str, CubeSource] = {
    "lsv": CubeSource("lsv", "LSV Cube", "cubecobra", "LSVCube"),
    "vintage": CubeSource("vintage", "MTGO Vintage Cube", "mtgo", MTGO_VINTAGE_URL),
}
DEFAULT_CUBES = ("lsv", "vintage")  # the first one is on the table when the save loads


def resolve(spec: str) -> CubeSource:
    """A known cube key (``lsv``), or ``cubecobra:<id>`` for any CubeCobra cube."""
    if spec in CUBES:
        return CUBES[spec]
    if spec.startswith("cubecobra:") and spec.removeprefix("cubecobra:"):
        cube_id = spec.removeprefix("cubecobra:")
        return CubeSource(re.sub(r"[^a-z0-9]+", "-", cube_id.lower()), cube_id, "cubecobra", cube_id)
    raise ValueError(f"unknown cube {spec!r}: use one of {', '.join(CUBES)} or cubecobra:<id>")


def parse_mtgo_cardlist(page: str) -> list[str]:
    """Card names from MTGO's Vintage Cube page.

    The page has three tables: the current full list (Color | Card), the
    changelist, and the previous full list. The first Color | Card table is
    the latest iteration.
    """
    for table in re.findall(r"<table.*?</table>", page, flags=re.DOTALL | re.IGNORECASE):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", table, flags=re.DOTALL | re.IGNORECASE):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[dh].*?</t[dh]>", tr, flags=re.DOTALL | re.IGNORECASE)]
            rows.append(cells)
        if rows and [c.lower() for c in rows[0]] == ["color", "card"]:
            names = [r[1].replace("’", "'") for r in rows[1:] if len(r) == 2 and r[1]]
            if len(names) < 100:
                raise ValueError(f"MTGO card list looks truncated ({len(names)} cards)")
            return names
    raise ValueError("no Color | Card table found on the MTGO Vintage Cube page")


def load_cube(client: httpx.Client, source: CubeSource) -> tuple[list[Card], list[Card]]:
    """The cube's cards and its basic lands (MTGO lists have no basics)."""
    if source.kind == "cubecobra":
        ids, basic_ids = fetch_cube_ids(client, source.ref)
        return fetch_cards(client, ids), fetch_cards(client, basic_ids)
    if source.kind == "mtgo":
        resp = client.get(source.ref, headers={"Accept": "text/html"})
        resp.raise_for_status()
        names = parse_mtgo_cardlist(resp.text)
        by_name = fetch_cards_by_name(client, names)
        return [by_name[n] for n in names], []
    raise ValueError(f"unknown cube source kind {source.kind!r}")
