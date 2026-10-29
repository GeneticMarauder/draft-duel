# Skills Taxonomy

Every skill in the registry, by layer. Start at the router; it routes to the rest.
`tests/test_registry.py` checks that every `SKILL.md` in the repo is listed here.

```text
router/      entry points: classify a request, plan the in-game test
mods/        one map per mod: features -> code -> state -> tests -> recipe
shared/      gameplay patterns any mod can reuse
core/        one TTS API area each, with ready-to-paste Lua samples
knowledge/   verified TTS behaviours, API links, prompt templates
schemas/     manifest, GMNotes and script-state contracts
governance/  standards, checklists, templates
```

## router

| Skill id | Purpose |
| --- | --- |
| [`router.tts-change-router`](router/tts-change-router/SKILL.md) | Classify any change request; pick mod, skills, prompt and definition of done. |
| [`router.in-game-test-planner`](router/in-game-test-planner/SKILL.md) | Write the test plan the user runs in TTS. |

## mods

| Skill id | Purpose |
| --- | --- |
| [`mods.draft-duel`](mods/draft-duel/SKILL.md) | Feature map of the Draft Duel mod (cube picker, draft, deck editor, game, tokens, playmats). |

## shared

| Skill id | Purpose | Verified |
| --- | --- | --- |
| [`shared.card-privacy`](shared/card-privacy/SKILL.md) | Owner-only cards that stay private through handling and reloads. | in-game |
| [`shared.table-layout`](shared/table-layout/SKILL.md) | Seat-relative layout; free-spot search. | in-game |
| [`shared.rules-engine-pattern`](shared/rules-engine-pattern/SKILL.md) | Pure rules engine + TTS adapter. | in-game |
| [`shared.counters-and-tokens`](shared/counters-and-tokens/SKILL.md) | Life counters; card-created tokens. | in-game |
| [`shared.custom-assets`](shared/custom-assets/SKILL.md) | Images TTS can load and never shows stale. | in-game |

## core

| Skill id | Purpose | Verified |
| --- | --- | --- |
| [`core.lua-runtime`](core/lua-runtime/SKILL.md) | MoonSharp dialect; `Wait` and coroutines. | docs-only |
| [`core.state.save-and-load`](core/state/save-and-load/SKILL.md) | Persist state; rebuild what TTS forgets. | in-game |
| [`core.objects.spawn-and-find`](core/objects/spawn-and-find/SKILL.md) | Spawn tiles and cards; find objects. | docs-only |
| [`core.objects.decks-and-containers`](core/objects/decks-and-containers/SKILL.md) | Deal, return, group; control merging. | in-game |
| [`core.interaction.buttons-and-menus`](core/interaction/buttons-and-menus/SKILL.md) | Object buttons and context menus. | in-game |
| [`core.ui.xml-ui`](core/ui/xml-ui/SKILL.md) | Screen UI in XML driven from Lua. | in-game |
| [`core.players.seats-and-cameras`](core/players/seats-and-cameras/SKILL.md) | Seats, messages, orientation, cameras. | in-game |
| [`core.events.event-hooks`](core/events/event-hooks/SKILL.md) | Event catalog and logger. | docs-only |
| [`core.debug.chat-commands`](core/debug/chat-commands/SKILL.md) | `!command` test hooks. | docs-only |
| [`core.lua-testing`](core/lua-testing/SKILL.md) | `lupa` + TTS mock testing. | in-game |
| [`core.build-and-install`](core/build-and-install/SKILL.md) | Build, install, inspect saves. | in-game |

## Lua samples at a glance

| Sample | Gives you |
| --- | --- |
| [`wait_patterns.lua`](core/lua-runtime/scripts/wait_patterns.lua) | `afterFrames`, `every`, `whenReady`, `cancel`, `runSteps` coroutine queue |
| [`persistent_state.lua`](core/state/save-and-load/scripts/persistent_state.lua) | Versioned state with defaults, migration, safe decode, rebuild hook |
| [`spawn_custom_tile.lua`](core/objects/spawn-and-find/scripts/spawn_custom_tile.lua) | Locked, click-through image tiles (playmats, boards) |
| [`spawn_card_from_data.lua`](core/objects/spawn-and-find/scripts/spawn_card_from_data.lua) | Cards from sheet cells or single images, with JSON GMNotes |
| [`find_objects.lua`](core/objects/spawn-and-find/scripts/find_objects.lua) | Find by GUID, tag, type, name, GMNotes; search inside decks |
| [`deck_operations.lua`](core/objects/decks-and-containers/scripts/deck_operations.lua) | Draw rows, take named cards, deal, return to locked decks, group |
| [`prevent_merging.lua`](core/objects/decks-and-containers/scripts/prevent_merging.lua) | `tryObjectEnterContainer` with allow-list |
| [`object_buttons.lua`](core/interaction/buttons-and-menus/scripts/object_buttons.lua) | Action buttons, labels, seat-checked click handlers |
| [`context_menus.lua`](core/interaction/buttons-and-menus/scripts/context_menus.lua) | Right-click items that survive draws, flips and reloads |
| [`seat_panel.xml`](core/ui/xml-ui/scripts/seat_panel.xml) + [`seat_panel.lua`](core/ui/xml-ui/scripts/seat_panel.lua) | Per-seat panels, relabelling, two-click confirm |
| [`seat_helpers.lua`](core/players/seats-and-cameras/scripts/seat_helpers.lua) | `othersThan`, `say`, `seatYaw`, `handCards`, `frameCamera` |
| [`event_logger.lua`](core/events/event-hooks/scripts/event_logger.lua) | See which events fire, in order |
| [`chat_commands.lua`](core/debug/chat-commands/scripts/chat_commands.lua) | `!command` dispatcher with help and host-only |
| [`private_cards.lua`](shared/card-privacy/scripts/private_cards.lua) | Hidden/invisible per card, re-applied and saved |
| [`seat_relative_layout.lua`](shared/table-layout/scripts/seat_relative_layout.lua) | Measure the table; mirrored rows and grids |
| [`free_spot.lua`](shared/table-layout/scripts/free_spot.lua) | Nearest empty card-sized spot |
| [`pure_core_template.lua`](shared/rules-engine-pattern/scripts/pure_core_template.lua) | Engine + adapter template |
| [`life_counters.lua`](shared/counters-and-tokens/scripts/life_counters.lua) | Tagged life counters per seat |
| [`token_spawner.lua`](shared/counters-and-tokens/scripts/token_spawner.lua) | Data-driven tokens from right-click menus |

Python tools: [`save_inspect.py`](core/build-and-install/scripts/save_inspect.py) (read and dump any save),
[`template_lua_test.py`](core/lua-testing/scripts/template_lua_test.py) (test template).
