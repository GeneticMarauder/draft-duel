"""Tokens the cube's cards make, from the curated list in ``data/tokens.csv``.

One CSV row per token: its label, type line, P/T, rules text, image URLs and
the cube cards that make it ("Made by", separated by ``;``). Makers are matched
to cube cards by name, so the mapping survives reprints and cube reshuffles.
"""

from __future__ import annotations

import csv
import io
from importlib import resources

from draft_duel.models import Card, Token


def load_tokens(text: str | None = None) -> list[Token]:
    """Parse the token CSV (the bundled ``data/tokens.csv`` unless ``text`` is given)."""
    if text is None:
        text = (resources.files("draft_duel") / "data" / "tokens.csv").read_text(encoding="utf-8-sig")
    tokens = []
    for row in csv.DictReader(io.StringIO(text)):
        type_line = f"{row['Type']}  {row['P/T']}".strip()
        rules = row["Rules text"].strip()
        makers = tuple(m.strip() for m in row["Made by (cube cards)"].split(";") if m.strip())
        tokens.append(Token(
            label=row["Token"].strip(),
            text=f"{type_line}\n{rules}" if rules else type_line,
            front_url=row["Image front"].strip(),
            back_url=row["Image back"].strip() or None,
            makers=makers,
        ))
    return tokens


def card_names(card: Card) -> list[str]:
    """Every name a maker can be listed under: the front, the back, and "front // back"."""
    names = [card.front.name]
    if card.back is not None:
        names += [card.back.name, f"{card.front.name} // {card.back.name}"]
    return names


def match_makers(tokens: list[Token], cards: list[Card]) -> tuple[list[Token], dict[str, list[str]], list[str]]:
    """Link tokens to cube cards.

    Returns the tokens at least one cube card makes (in CSV order), a map of
    cube card Scryfall id -> token labels it makes, and maker names that are not
    in the cube (worth a warning: the CSV may need updating).
    """
    by_name: dict[str, list[str]] = {}
    for card in cards:
        for name in card_names(card):
            by_name.setdefault(name.lower(), []).append(card.scryfall_id)
    used: list[Token] = []
    makers: dict[str, list[str]] = {}
    missing: list[str] = []
    for token in tokens:
        found = False
        for name in token.makers:
            ids = by_name.get(name.lower())
            if not ids:
                missing.append(name)
                continue
            found = True
            for card_id in ids:
                labels = makers.setdefault(card_id, [])
                if token.label not in labels:
                    labels.append(token.label)
        if found:
            used.append(token)
    return used, makers, sorted(set(missing))


def token_faces(tokens: list[Token]) -> list[str]:
    """Image URLs in sheet order: every front, then the backs of double-faced tokens."""
    return [t.front_url for t in tokens] + [t.back_url for t in tokens if t.back_url]
