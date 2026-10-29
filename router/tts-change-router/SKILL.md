---
skill_id: "router.tts-change-router"
name: "TTS Change Router"
description: "Entry point for any change request in this repo: classifies it, picks the mod, shared and core skills and the prompt to follow, and sets the definition of done; start here for every Tabletop Simulator change."
layer: "router"
type: "orchestration"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "mods.draft-duel"
  - "core.lua-testing"
  - "core.build-and-install"
  - "router.in-game-test-planner"
samples: []
side_effects: []
---

# TTS Change Router

## Purpose

Turn a request ("tokens land on my cards", "add a mulligan button", "new playmat")
into a route: which mod, which skills, which prompt, which tests, what done means.
Every agent follows the same path, so work done in parallel lands consistently.

## Step 1 — Classify

| Request looks like… | Class | Prompt |
| --- | --- | --- |
| New behaviour players can trigger | feature | [add-feature](../../knowledge/prompts/add-feature.md) |
| "In game, X happened" | bug | [fix-in-game-bug](../../knowledge/prompts/fix-in-game-bug.md) |
| Token for a card | content: token | [add-token](../../knowledge/prompts/add-token.md) |
| Playmat / image | content: asset | [add-playmat](../../knowledge/prompts/add-playmat.md) |
| Play card A instead of B | content: card | [swap-card](../../knowledge/prompts/swap-card.md) |
| Another cube to draft | content: cube | [add-cube](../../knowledge/prompts/add-cube.md) |
| Reusable technique worth keeping | registry | [new-lua-sample](../../knowledge/prompts/new-lua-sample.md) |
| A different game | new mod | [new-mod](../../knowledge/prompts/new-mod.md) |
| "Check this before I test" | review | [review-change](../../knowledge/prompts/review-change.md) |
| "How do I… in TTS?" | question | answer from the skills below; no change |

## Step 2 — Pick the mod

Only one mod today: [`mods.draft-duel`](../../mods/draft-duel/SKILL.md).
Use its feature map to find the code, state keys and tests for the request.

## Step 3 — Pick the skills

Match what the change touches. Most changes need two or three.

| The change involves… | Skill |
| --- | --- |
| Game rules, phases, turn order, legality | [`shared.rules-engine-pattern`](../../shared/rules-engine-pattern/SKILL.md) |
| Something only one player may see | [`shared.card-privacy`](../../shared/card-privacy/SKILL.md) |
| Where things go on the table | [`shared.table-layout`](../../shared/table-layout/SKILL.md) |
| Counters, markers, tokens | [`shared.counters-and-tokens`](../../shared/counters-and-tokens/SKILL.md) |
| Images: sheets, mats, thumbnails | [`shared.custom-assets`](../../shared/custom-assets/SKILL.md) |
| Spawning or finding objects | [`core.objects.spawn-and-find`](../../core/objects/spawn-and-find/SKILL.md) |
| Decks, dealing, merging, piles | [`core.objects.decks-and-containers`](../../core/objects/decks-and-containers/SKILL.md) |
| Buttons on objects, right-click menus | [`core.interaction.buttons-and-menus`](../../core/interaction/buttons-and-menus/SKILL.md) |
| Screen panels, prompts, UI buttons | [`core.ui.xml-ui`](../../core/ui/xml-ui/SKILL.md) |
| Seats, who clicked, cameras | [`core.players.seats-and-cameras`](../../core/players/seats-and-cameras/SKILL.md) |
| Reacting to player actions | [`core.events.event-hooks`](../../core/events/event-hooks/SKILL.md) |
| Anything that must survive a reload | [`core.state.save-and-load`](../../core/state/save-and-load/SKILL.md) |
| Timing, deferring, big loops, Lua dialect | [`core.lua-runtime`](../../core/lua-runtime/SKILL.md) |
| In-game test shortcuts | [`core.debug.chat-commands`](../../core/debug/chat-commands/SKILL.md) |

Always also: [`core.lua-testing`](../../core/lua-testing/SKILL.md),
[`core.build-and-install`](../../core/build-and-install/SKILL.md) and
[`knowledge/verified-behaviours.md`](../../knowledge/verified-behaviours.md).

## Step 4 — Work

1. Read the selected skills' **Gotchas** and start from their **samples**.
2. Test first under `lupa` + the mock; keep TTS calls within the mock or extend it.
3. Follow [`governance/review-checklist.md`](../../governance/review-checklist.md).

## Step 5 — Done

- `uv run pytest` passes; `git diff --check` is clean.
- `AGENTS.md`, the mod map and schemas match the code.
- Save rebuilt (`uv run draft-duel`; `--push` only with the user's OK).
- The user has an in-game test plan from [`router.in-game-test-planner`](../in-game-test-planner/SKILL.md).
- Anything new TTS taught you is in `knowledge/verified-behaviours.md`; anything reusable
  became a sample.

## Boundaries

- Ask before adding a dependency, pushing to GitHub, or driving the user's screen.
- Don't commit unless asked.
