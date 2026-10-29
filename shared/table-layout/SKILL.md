---
skill_id: "shared.table-layout"
name: "Table Layout and Placement"
description: "Measure the table, lay out rows and grids in seat-relative coordinates that mirror for each seat, and find free spots for new cards; use whenever a feature places objects on the table."
layer: "shared"
type: "pattern"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.players.seats-and-cameras"
  - "core.objects.spawn-and-find"
samples:
  - "scripts/seat_relative_layout.lua"
  - "scripts/free_spot.lua"
side_effects: []
---

# Table Layout and Placement

## Purpose

Put objects where they belong for each player — mirrored, upright, above the
felt and not on top of each other.

## When to use

- A feature adds a row, grid, pile or panel area to the table.
- "Cards overlap / land on other cards / appear on the wrong side / upside down."
- Adapting a layout to a different table or card scale.

## How it works

1. **Measure, don't guess**: card size and felt height from a reference deck's
   bounds, table size from `Tables.getTableObject()`.
2. **Seat-relative coordinates**: describe positions as `u` (to the seat's right)
   and `v` (from the middle line toward the seat); one function converts to world.
   The opposite seat mirrors automatically.
3. **Search for space** when the spot depends on what's already there
   (tokens, revealed cards): try candidate offsets nearest-first and check each
   against every card's rotated bounds.

In this repo: `computeLayout` measures from the cube; `packPosition`,
`slotPosition`, `boosterPosition`, deck-editor columns and `tokenSpot` all use
`sideSign` / `ownerU` / `worldX`. Distances are named constants at the top of
each section of `table.lua` (`PACK_ROW_Z`, `PICK_GRID_Z`, `DECK_TOP_Z`, `MAT_Z`…).

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/seat_relative_layout.lua`](scripts/seat_relative_layout.lua) | `measureLayout`, `toWorld`, `ownerU`, `rowPosition`, `gridPosition`, `seatYaw`, `placeFor` | Global. |
| [`scripts/free_spot.lua`](scripts/free_spot.lua) | `freeSpotNear(anchor, opts)`, `spotIsFree` with rotated bounds, bounded search | Global. |

## Gotchas

- (verified) Table_RPG felt top y ≈ 0.96, table 64 x 43.
- (verified) A fixed fan-out dropped tokens on neighbouring cards; search for free space instead.
- (verified) Bounds follow rotation — tapped cards are wide.
- (docs) Objects placed exactly at felt height can be pushed by physics; lift slightly.

## Testing

Positions are pure maths: assert them in `lupa` (the mock gives every object
`getBounds` 2.2 x 3.1). Visual fit — overlap with TTS's own hand display, camera
framing — needs a screenshot from the user. `!draftdebug` dumps live geometry.

## Related

- [`core.players.seats-and-cameras`](../../core/players/seats-and-cameras/SKILL.md)
- [`shared.counters-and-tokens`](../counters-and-tokens/SKILL.md)
