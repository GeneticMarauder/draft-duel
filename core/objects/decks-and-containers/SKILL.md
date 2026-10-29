---
skill_id: "core.objects.decks-and-containers"
name: "Decks and Containers"
description: "Deal, draw, return, group and search cards in decks and bags, and control when cards merge into piles; use for any feature that moves cards between decks, hands and the table."
layer: "core"
type: "reference"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.objects.spawn-and-find"
  - "core.lua-runtime"
samples:
  - "scripts/deck_operations.lua"
  - "scripts/prevent_merging.lua"
side_effects: []
---

# Decks and Containers

## Purpose

Move cards between decks, the table and hands without losing track of them.

## When to use

- Dealing packs or hands, drawing to positions, putting cards back, shuffling.
- "Cards stacked into a pile when I dropped them" (merge rules).
- "My deck GUID stopped working" (deck collapsed to a single card).
- Grouping a deck/sideboard into a pile (Ready to play, Next game).

## How it works

A `Deck` or `Bag` holds cards as *data*, not objects. `takeObject{…}` turns one
into a real object at a position; `putObject(card)` turns it back into data.
Cards inside keep their GUIDs, so you can route them by GUID later. `group(objs)`
merges loose objects into one deck. TTS asks `tryObjectEnterContainer(container, obj)`
before any merge — return `false` to refuse.

In this repo: the cube deck (`cubeGuid`, `c00001` until players switch cubes) is non-interactable; packs come from
`takeObject`, Booster Tutor leftovers go back via `returnToCube` (unlock → put →
shuffle → lock), `readyUp` groups the deck and sideboard, and `tryObjectEnterContainer`
keeps the deck editor's cards separate.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/deck_operations.lua`](scripts/deck_operations.lua) | `drawRow`, `takeNamed`, `dealToSeats`, `returnCards` (locked decks ok), `groupInto`, `isStillDeck` | Global. |
| [`scripts/prevent_merging.lua`](scripts/prevent_merging.lua) | `tryObjectEnterContainer` with an allow-list and a middle strip | Global; merge with an existing handler. |

## Gotchas

- (verified) A locked deck refuses `putObject`.
- (verified) Cards dropped or placed on each other merge unless `tryObjectEnterContainer` says no.
- (verified) A deck reduced to one card becomes that card; the deck GUID is gone (the mock models this).
- (verified) `tryObjectEnterContainer` returning `false` blocks your own `putObject` too.
- (docs) `takeObject{ smooth = true }` animates; the card arrives later than the call returns.

## Testing

The mock's decks support `takeObject`, `putObject`, `shuffle`, `deal`, `group`
and the one-card collapse; `tests/test_draft_lua.py` drives full drafts through
them. Physical stacking (what merges when dropped by hand) is TTS-only.

## Related

- [`core.objects.spawn-and-find`](../spawn-and-find/SKILL.md)
- [`shared.card-privacy`](../../../shared/card-privacy/SKILL.md) — cards coming out of a deck need re-hiding.
