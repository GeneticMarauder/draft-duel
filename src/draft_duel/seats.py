"""Where the players sit: the 1v1 table and the four-player table.

Every save is built for one ``Table``. A seat's ``side`` is -1 at the table's
-z edge (looking toward +z) and +1 at the +z edge; ``x`` is the centre of its
part of the table. Owner-relative positions elsewhere (``u`` across, positive =
the owner's right; ``d`` from the middle line toward the owner's hand) are
measured from that centre, so the zone board, playmat and deck editor work the
same at every seat. The in-game script gets the seats as ``SEATS_JSON``.

The four-player table copies the MTG EDH table: White and Red along the -z
edge, Green and Blue along the +z edge, each with a quarter of the table.
Seats are listed in passing order (each passes left to the next).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAT_D = 16.0      # playmat depth (table units) at every table; the width follows the image


@dataclass(frozen=True)
class Seat:
    """One player's place at the table."""

    color: str
    side: int          # -1: the -z edge, +1: the +z edge
    x: float = 0.0     # centre of the seat's part of the table


@dataclass(frozen=True)
class Table:
    """A table layout: its save name, seats, hand-zone distance and playmat width."""

    name: str
    seats: tuple[Seat, ...]
    hand_d: float      # hand zones' distance from the middle line
    hand_w: float      # hand zones' width
    mat_w: float       # playmat width (its depth is MAT_D)
    panel_w: float     # the painted mat on the table image (wider than the playmat)

    @property
    def colors(self) -> tuple[str, ...]:
        """Seat colors in passing order."""
        return tuple(s.color for s in self.seats)

    def script_header(self) -> dict[str, Any]:
        """``SEATS_JSON`` for the in-game script."""
        return {"hand": self.hand_d, "mat_w": self.mat_w,
                "seats": [{"color": s.color, "side": s.side, "x": s.x} for s in self.seats]}


QUARTER_X = 22.1  # a four-player seat's centre: half of the table image's 44.2 half-width

DUEL = Table("Draft Duel", (Seat("White", -1), Seat("Red", 1)),
             hand_d=20.0, hand_w=24.0, mat_w=44.0, panel_w=62.0)
FOUR = Table("Draft Duel 4P",
             (Seat("White", -1, QUARTER_X), Seat("Red", -1, -QUARTER_X),
              Seat("Green", 1, -QUARTER_X), Seat("Blue", 1, QUARTER_X)),
             hand_d=23.5, hand_w=18.0, mat_w=38.0, panel_w=43.0)
TABLES = {2: DUEL, 4: FOUR}
