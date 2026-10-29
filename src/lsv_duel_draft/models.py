"""Plain data types shared by the builder stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Face:
    """One printed face of a card: what the player sees and hovers."""

    name: str
    text: str
    image_url: str


@dataclass(frozen=True)
class Card:
    """A cube card. ``back`` is set only for double-faced cards."""

    scryfall_id: str
    front: Face
    back: Face | None = None
    cmc: float = 0
    is_land: bool = False


@dataclass(frozen=True)
class Token:
    """A token (or emblem / marker card) and the names of the cube cards that make it.

    ``label`` is unique per token ("Cat 1/1 White") and is what players see in
    the right-click menu. ``back_url`` is set only for double-faced tokens.
    """

    label: str
    text: str
    front_url: str
    back_url: str | None = None
    makers: tuple[str, ...] = ()


@dataclass(frozen=True)
class SheetSlot:
    """Where one face lives on a Tabletop Simulator deck sheet."""

    sheet_id: int
    index: int

    @property
    def card_id(self) -> int:
        """TTS CardID: sheet id * 100 + position on the sheet."""
        return self.sheet_id * 100 + self.index


@dataclass(frozen=True)
class Sheet:
    """A rendered deck sheet image and its public URL."""

    sheet_id: int
    filename: str
    url: str
