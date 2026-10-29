---
skill_id: "shared.card-privacy"
name: "Card Privacy on an Open Table"
description: "Keep specific cards hidden or invisible to everyone but their owner, through pickups, flips and reloads; use for drafts, private piles, sideboards, or any 'only you can see this' feature."
layer: "shared"
type: "pattern"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.players.seats-and-cameras"
  - "core.events.event-hooks"
  - "core.state.save-and-load"
samples:
  - "scripts/private_cards.lua"
side_effects: []
---

# Card Privacy on an Open Table

## Purpose

Show a card to one player only, anywhere on the table, and keep it that way.

## When to use

- Drafting (pack visible to the picker only), private pick piles, sideboards.
- "My opponent could see my card after I moved/flipped it" or "after a reload".
- Choosing between hand zones, hidden zones and per-card privacy:

| Option | Result | Use |
| --- | --- | --- |
| Hand zone | Cards in it show backs to others; TTS manages it. | Real hands. |
| Hidden zone | Opaque block in the owner's color (tint ignored). | Rarely — it looks bad (verified). |
| `setHiddenFrom(others)` | Others see the card back. | Opponent should know a card is there (the pack). |
| `setInvisibleTo(others)` | Others see nothing. | Private piles, picks, sideboards. |

## How it works

Privacy is a property of the object that TTS neither saves nor reliably keeps
when a player handles the card. So the pattern is: remember the rule per GUID in
script state, re-apply it on every pickup, drop and state change (now and a few
frames later), and re-apply everything on load.

In this repo: `privateOwner(obj)` derives the rule from game state (picks, piles,
deck-editor side) instead of a table; `rehide` and `rehideAll` apply it; `!hide`
is the manual escape hatch.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/private_cards.lua`](scripts/private_cards.lua) | `makePrivate(obj, owner, mode)`, `makePublic`, `rehide`, `rehideAll`, handlers, save/load of the rules | Global; merge `onSave`/`onLoad`/handlers with yours. |

## Gotchas

- (verified) TTS can lose an object's invisible list on pickup/move/flip: re-apply, then re-apply after ~3 frames.
- (verified) Hidden zones render as solid colored blocks and ignore their tint.
- (verified) A DFC flip changes the GUID — carry the rule to the new GUID.
- (docs) A card in someone's hand zone follows hand rules, not your lists.

## Testing

The mock records `hiddenFrom` / `invisibleTo` on objects; assert them after
calling handlers and `Mock.flush()`. What the opponent actually sees needs two
seats in TTS — ask the user to check from the other seat (or with a friend).

## Related

- [`core.players.seats-and-cameras`](../../core/players/seats-and-cameras/SKILL.md) — `othersThan`.
- [`core.state.save-and-load`](../../core/state/save-and-load/SKILL.md)
