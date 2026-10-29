---
skill_id: "core.players.seats-and-cameras"
name: "Seats, Players and Cameras"
description: "Seat-aware helpers for player colors, private messages, seat orientation, hand contents and camera framing; use whenever behaviour depends on who clicked, who sits where, or what a player sees."
layer: "core"
type: "reference"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.lua-runtime"
samples:
  - "scripts/seat_helpers.lua"
side_effects: []
---

# Seats, Players and Cameras

## Purpose

Turn player colors into game seats: who may act, which half of the table is
theirs, which way their cards face, and where their camera points.

## When to use

- An action must be limited to a seat ("only the opener can take").
- Laying things out per player (mirror positions for the opposite seat).
- Private messages, empty-seat bots, spectators.
- "The camera points the wrong way" / reframing after someone sits down.

## How it works

`Player[color]` exists for every color; `.seated` says if someone is there,
`.host` if they host. A seat is defined by its **hand zone** (a `HandTrigger`
object in the save); `getHandTransform()` gives its position and rotation, which
tells you which way the seat faces. Two-seat games mirror the table: one seat's
half is `z < 0`, the other's `z > 0`.

In this repo: `COLORS = {"White","Red"}`, hand zones `a00001` / `a00002`, and
`sideSign` / `ownerU` / `worldX` convert seat-relative coordinates to world ones
(see [`shared.table-layout`](../../../shared/table-layout/SKILL.md)).

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/seat_helpers.lua`](scripts/seat_helpers.lua) | `isSeat`, `seatedSeats`, `othersThan`, `say`, `seatYaw`, `sideSign`, `handCards`, `frameCamera`, `onPlayerChangeColor` | Global. |

## Gotchas

- (verified) Hand zones decide what counts as "in hand"; moving them moves the hand.
- (verified) Privacy lists must name every other color (spectators too) — `othersThan` uses all 12.
- (verified) Reframing right after a seat change needs a few frames' delay.
- (docs) Spectators are `"Grey"`; the Game Master is `"Black"`.

## Testing

The mock seats `White` and `Red` with hand zones at z = ∓19 and records
`lookAt` params in `Player[color].camera`. Set `Player.Red.seated = false` to test
empty-seat paths. Whether the view *looks* right is a TTS check.

## Related

- [`shared.table-layout`](../../../shared/table-layout/SKILL.md)
- [`shared.card-privacy`](../../../shared/card-privacy/SKILL.md)
