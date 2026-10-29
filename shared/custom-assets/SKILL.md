---
skill_id: "shared.custom-assets"
name: "Custom Images and Asset Hosting"
description: "Make card sheets, playmats, thumbnails and other images that TTS can load and never shows stale; use when adding or changing any image a mod uses."
layer: "shared"
type: "pattern"
execution_mode: "advisory"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.build-and-install"
samples: []
side_effects: []
---

# Custom Images and Asset Hosting

## Purpose

Every image in a TTS mod is a URL the game downloads on each player's machine.
Get the size, the host and the URL right once, and images just work.

## When to use

- Adding a playmat, card sheet, token, card back or UI thumbnail.
- "The image is blank / shows an error icon / shows the old picture."

## How it works

| Rule | Why |
| --- | --- |
| Host on a public URL every player can fetch (this repo: `raw.githubusercontent.com/.../sheets/…`). | Players download images themselves; local paths only work for you. |
| Never point TTS at Scryfall. | Scryfall rejects TTS's user agent (verified); download with our client, re-host. |
| Put a content hash in the file name (`front01-<hash>.jpg`). | TTS caches by URL forever; a new image needs a new URL. |
| Keep sheets ≤ 4096 px per side. | Larger textures fail or are downscaled. |
| Deck sheets: up to 10 x 7 cells, last cell is the hidden-card slot. | TTS's `CustomDeck` grid. |
| JPEG for photos/cards, PNG only when you need transparency. | Size and load time. |
| Draw generated art deterministically (seeded). | Same pixels → same hash → no re-upload, no cache churn. |
| UI images are save-level `CustomUIAssets` referenced by name. | XML UI can't take arbitrary URLs everywhere. |

In this repo: `sheets.py` (card sheets, 409 x 570 per card), `playmats.py`
(2048 x 744 mats matching the 44 x 16 in-game tile, seeded themes, user pictures
from `playmats/`), `tts_save.ui_assets` (`matthumb<i>`), all pushed by
`uv run draft-duel --push`.

## Samples

None of its own: images are produced by the Python builder. The Lua that shows
an image is [`core/objects/spawn-and-find/scripts/spawn_custom_tile.lua`](../../core/objects/spawn-and-find/scripts/spawn_custom_tile.lua)
(tiles) and [`spawn_card_from_data.lua`](../../core/objects/spawn-and-find/scripts/spawn_card_from_data.lua) (cards).

## Gotchas

- (verified) The images must be pushed before the save works for anyone — build with `--push`.
- (verified) Copyrighted art: generate procedurally or use pictures the user supplies (`playmats/`).
- (docs) TTS's cache lives in `Documents/My Games/Tabletop Simulator/Mods/Images`; deleting a file there forces a re-download.

## Testing

`tests/test_builder.py` checks hashing and sizes. Whether an image loads is a TTS
check: the user sees an error icon or a blank face if not.

## Related

- [`core.build-and-install`](../../core/build-and-install/SKILL.md)
- [`knowledge/prompts/add-playmat.md`](../../knowledge/prompts/add-playmat.md)
