---
skill_id: "shared.counters-and-tokens"
name: "Counters and Tokens"
description: "Life counters per seat and card-created tokens (right-click Create, unique tokens, placement); use when a feature adds counters, markers or tokens that appear during play."
layer: "shared"
type: "pattern"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.objects.spawn-and-find"
  - "core.interaction.buttons-and-menus"
  - "shared.table-layout"
samples:
  - "scripts/life_counters.lua"
  - "scripts/token_spawner.lua"
side_effects: []
---

# Counters and Tokens

## Purpose

Game-time objects that come and go: life totals, markers, and tokens that cards create.

## When to use

- Adding a counter (life, poison, energy) or a marker (initiative, monarch).
- "This card should create a token" — new token, new maker.
- Tokens landing in the wrong place or duplicating when they should be unique.

## How it works

**Counters**: `spawnObject{type="Counter"}`; set the value in the callback via
`obj.Counter.setValue`. Name + tag them so they can be found and removed later.

**Tokens**: data-driven. `tokens` maps a label to spawnable object data;
`makers` maps a card id to the labels it makes. A card's right-click menu gets
"Create <label>" per token; clicking spawns the data next to the card. Unique
tokens are found and moved instead.

In this repo: tokens are curated in `src/draft_duel/data/tokens.csv`
(one row per token, "Made by" lists cube card names), linked to card ids by
`tokens.match_makers`, rendered onto token sheets and embedded as `TOKENS_JSON`.
`createToken` places tokens with `tokenSpot` (free-space search). To add a token:
[`knowledge/prompts/add-token.md`](../../knowledge/prompts/add-token.md).

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/life_counters.lua`](scripts/life_counters.lua) | `spawnLifeCounters`, `lifeOf`, `adjustLife`, `removeLifeCounters` (tag-based) | Global. |
| [`scripts/token_spawner.lua`](scripts/token_spawner.lua) | `TOKENS` tables, `createToken` with unique-token handling, `addTokenMenu` + events | Global; swap `placeBeside` for `freeSpotNear`. |

## Gotchas

- (verified) Counter methods are on `obj.Counter`.
- (verified) Fixed offsets drop tokens onto neighbouring cards — search for space ([`shared.table-layout`](../table-layout/SKILL.md)).
- (verified) Token GMNotes `{"token": label}` without `id` keep tokens out of the deck editor.
- (verified) Menus must be re-added after draws, flips and reloads.

## Testing

The mock's `spawnObject` gives `Counter` objects a `Counter.setValue`; the mod
tests cover token menus, placement and unique tokens. Token images loading is a TTS check.

## Related

- [`shared.table-layout`](../table-layout/SKILL.md)
- [`core.interaction.buttons-and-menus`](../../core/interaction/buttons-and-menus/SKILL.md)
