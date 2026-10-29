---
skill_id: "core.objects.spawn-and-find"
name: "Spawn and Find Objects"
description: "Spawn custom tiles and cards from data and look objects up by GUID, type, name, tag or GMNotes; use when a feature creates objects at runtime or needs to locate them again."
layer: "core"
type: "reference"
execution_mode: "assisted"
version: "0.1.0"
verified: "docs-only"
depends_on:
  - "core.lua-runtime"
samples:
  - "scripts/spawn_custom_tile.lua"
  - "scripts/spawn_card_from_data.lua"
  - "scripts/find_objects.lua"
side_effects: []
---

# Spawn and Find Objects

## Purpose

Create objects from a script and get hold of them again later, reliably and
across reloads.

## When to use

- Adding something that appears mid-game: tokens, counters, playmats, a revealed booster.
- A spawned object "doesn't load", shows a blank face, or lands in the wrong place.
- Code needs to find "the life counter" or "every token" again.

## How it works

Two spawn calls:

| Call | Use for | Notes |
| --- | --- | --- |
| `spawnObject({type=…})` | Built-in objects and custom objects you configure right away (`Custom_Tile`, `Custom_Model`, `Counter`). | Follow with `setCustomObject{…}` **in the same frame**. |
| `spawnObjectData({data=…})` | Exact copies of save-file JSON (cards with GMNotes, states, decks). | Data shape is the save format; build it in Python and embed it. |

Both return the object immediately (still loading) and call `callback_function(obj)`
when it exists. To find objects: GUID for the ones you saved, tags for categories
you own, GMNotes JSON for game data, `type` + name as a last resort.

In this repo: tokens and basic lands are `spawnObjectData` from JSON the builder
embeds (`TOKENS_JSON`, `BASIC_LANDS_JSON`); playmats are `spawnObject` +
`setCustomObject`; cards are identified by the `id` in their GMNotes
([`schemas/card-gmnotes.schema.json`](../../../schemas/card-gmnotes.schema.json)).

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/spawn_custom_tile.lua`](scripts/spawn_custom_tile.lua) | `spawnImageTile`, `replaceImageTile` — a locked, click-through image tile | Global; keep the GUID in state. |
| [`scripts/spawn_card_from_data.lua`](scripts/spawn_card_from_data.lua) | `sheetCardData`, `singleCardData`, `spawnCard`, `readNotes` | Global; or build the data in Python. |
| [`scripts/find_objects.lua`](scripts/find_objects.lua) | `byGuid`, `byTag`, `findAll` / `findFirst` filters, `findInContainer` | Anywhere. |

## Gotchas

- (verified) `setCustomObject` works on a tile spawned in the same frame; raw
  `spawnObjectData` tile data without every field failed to load.
- (verified) A `Custom_Tile` is 2 units deep at scale 1; width follows the image aspect.
- (verified) `interactable = false` isn't saved; reapply on load.
- (docs) `CardID = sheetId * 100 + index`; the same `sheetId` must mean the same sheet everywhere in a save.
- (docs) Cards in a deck aren't objects: use `deck.getObjects()` then `takeObject{guid=…}`.

## Testing

The mock implements `spawnObject`, `spawnObjectData`, `getObjects`,
`getObjectFromGUID`; `tts_mock_registry.lua` adds tags. Image loading,
aspect ratio and physics settling are TTS-only checks.

## Related

- [`core.objects.decks-and-containers`](../decks-and-containers/SKILL.md)
- [`shared.custom-assets`](../../../shared/custom-assets/SKILL.md) — hosting images TTS can load.
- [`shared.counters-and-tokens`](../../../shared/counters-and-tokens/SKILL.md)
