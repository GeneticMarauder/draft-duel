---
skill_id: "mods.draft-duel"
name: "Draft Duel — Mod Map"
description: "Where each feature of the Draft Duel mod lives (Lua section, Python module, state keys, tests) and the recipe for changing it; use before changing anything in this mod."
layer: "mods"
type: "feature-map"
execution_mode: "assisted"
version: "0.2.0"
verified: "in-game"
depends_on:
  - "shared.rules-engine-pattern"
  - "shared.card-privacy"
  - "shared.table-layout"
  - "shared.counters-and-tokens"
  - "shared.custom-assets"
  - "core.build-and-install"
  - "core.lua-testing"
samples: []
side_effects: []
---

# Draft Duel — Mod Map

## Purpose

A finding aid. The **architecture** — what each feature does and why — is in
[`AGENTS.md`](../../AGENTS.md#architecture) and stays there; this page tells you
where to look and what to touch for a change.

## When to use

Before any change to this mod: find the feature below, read its `AGENTS.md`
paragraph, open the code anchor, run its tests.

## Feature map

`table.lua` is split by `-- ---- <section>` banners; search for the section name.

| Feature | Lua (`src/draft_duel/lua/`) | Python (`src/draft_duel/`) | State keys | Tests (`tests/`) | Patterns |
| --- | --- | --- | --- | --- | --- |
| Draft rules (pick order, packs) | `draft_core.lua` | — | `draft` | `test_full_draft_follows_pick_order_and_counts`, `test_rejects_out_of_turn_and_foreign_cards`, `test_serialize_restore_round_trip` | [rules engine](../../shared/rules-engine-pattern/SKILL.md) |
| Pack row, Draft button, bots | `table.lua` § pack cards, flow | — | `draft`, `bots` | `test_table_adapter_runs_a_whole_draft`, `test_leftover_pack_cards_vanish`, `test_empty_seat_is_drafted_by_a_bot`, `test_pack_is_laid_out_on_the_table_for_its_holder_only` | [buttons](../../core/interaction/buttons-and-menus/SKILL.md), [layout](../../shared/table-layout/SKILL.md) |
| Privacy (pack hidden, picks invisible) | `table.lua` § privacy | — | derived | `test_picks_*`, `test_deck_editor_cards_moved_stay_hidden`, `test_flipped_double_faced_pick_stays_hidden_and_tracked`, `test_hide_command_rehides_everything` | [card privacy](../../shared/card-privacy/SKILL.md) |
| Deck editor (columns, sideboard, lands) | `table.lua` § deck editor | `tts_save.basic_land_objects` | `ready` | `test_deck_editor_*`, `test_land_buttons_add_and_remove_basics`, `test_cards_do_not_merge_into_piles_while_deck_building` | [decks](../../core/objects/decks-and-containers/SKILL.md) |
| Ready to play, game start, life | `table.lua` § ready & play | — | `ready`, `piles`, `playing`, `firstPlayer`, `owned` | `test_ready_*`, `test_game_state_survives_a_reload` | [counters](../../shared/counters-and-tokens/SKILL.md) |
| Tokens | `table.lua` § tokens | `tokens.py`, `data/tokens.csv` | — | `test_right_click_creates_the_cards_tokens_beside_it`, `test_tokens_*`, `test_the_monarch_moves_instead_of_duplicating`, `test_makers_match_cube_cards_by_any_face_name` | [tokens](../../shared/counters-and-tokens/SKILL.md), [free spot](../../shared/table-layout/SKILL.md) |
| Booster Tutor | `table.lua` § booster tutor | `sources.CARD_SWAPS` | `booster`, `tutored` | `test_booster_tutor_opens_15_cards_and_puts_the_choice_in_hand`, `test_open_booster_survives_a_reload` | [decks](../../core/objects/decks-and-containers/SKILL.md) |
| Next game / sideboarding | `table.lua` § next game | — | `owned`, `tutored`, `gameNumber` | `test_next_game_*` | [XML UI confirm](../../core/ui/xml-ui/SKILL.md) |
| Playmats | `table.lua` § playmats | `playmats.py`, `tts_save.mat_pickers`, `playmats/` | `mats` | `test_players_choose_replace_and_remove_their_playmat`, `test_playmat_survives_a_reload_and_ignores_the_game`, `test_a_new_or_switched_playmat_lifts_the_cards_it_would_cover`, `test_switching_playmats_quickly_leaves_only_the_last_one`, `test_playmats_*`, `test_pictures_in_the_playmats_folder_become_mats` | [custom tile](../../core/objects/spawn-and-find/SKILL.md), [assets](../../shared/custom-assets/SKILL.md) |
| Zone board, Draw / Untap, dice | `table.lua` § zones (+ `readyUp`, `nextGame`, `spotIsFree`) | `zones.py` (`LAYOUT` → `ZONES_JSON`) | `boards` | `test_each_seat_gets_a_zone_board_*`, `test_draw_button_*`, `test_untap_button_*`, `test_zone_boards_survive_*`, `test_tokens_are_not_created_on_a_zone_board`, `test_each_seat_has_its_dice_*`, `test_zone_board_image_*` | [custom tile](../../core/objects/spawn-and-find/SKILL.md), [buttons](../../core/interaction/buttons-and-menus/SKILL.md), [layout](../../shared/table-layout/SKILL.md) |
| Scry, Surveil, Mulligan (beside Untap / Draw), "Put on bottom of library" | `table.lua` § scry, surveil, mulligan (+ `addBoardButtons`, `addPlayMenu`, `drawCard`) | `zones.py` (`BUTTONS` with `u`, `LOOK`) | `looks`, `mulligans`, `bottomOwed` | `test_scry_*`, `test_surveil_*`, `test_mulligan_*`, `test_cards_being_scried_*` | [buttons](../../core/interaction/buttons-and-menus/SKILL.md), [privacy](../../shared/card-privacy/SKILL.md), [decks](../../core/objects/decks-and-containers/SKILL.md) |
| Table top and props | — | `tabletop.py`, `props.py`, `tts_save.build_save` | — | `test_table_image_*`, `test_props_*` | [assets](../../shared/custom-assets/SKILL.md) |
| Cube choice (LSV, MTGO Vintage, …) | `table.lua` § cubes | `cubes.py`, `tts_save.build_save` / `cube_pickers`, `cli --cubes` | `cubeKey`, `cubeGuid` | `test_players_switch_the_cube_before_the_draft`, `test_chosen_cube_survives_a_reload_and_the_draft_continues_from_it`, `test_switching_back_restores_the_first_cube`, `test_save_offers_every_cube_with_the_first_on_the_table`, `test_mtgo_page_gives_the_latest_full_list`, `test_cubes_resolve_by_key_or_cubecobra_id` | [spawn](../../core/objects/spawn-and-find/SKILL.md), [XML UI](../../core/ui/xml-ui/SKILL.md) |
| Screen UI | `ui.xml`, `table.lua` § UI | `tts_save.global_xml` | — | `test_ui_xml_is_well_formed_and_unescaped` | [XML UI](../../core/ui/xml-ui/SKILL.md) |
| Debug commands | `table.lua` § debug, `onChat` | — | — | `test_debug_command_prints_geometry`, `test_draftauto_command_finishes_the_draft_against_a_bot` | [chat commands](../../core/debug/chat-commands/SKILL.md) |
| Card data, sheets | — | `sources.py`, `sheets.py`, `models.py` | — | `test_parses_normal_dfc_and_split_cards`, `test_slots_fill_sheets_in_order`, `test_render_sheet_size`, `test_swap_cards_replaces_by_name_in_place` | [assets](../../shared/custom-assets/SKILL.md) |
| Save assembly & install | — | `tts_save.py`, `cli.py` | — | `test_save_structure`, `test_cards_carry_deck_editor_data_and_basics_reach_the_script` | [build](../../core/build-and-install/SKILL.md) |

State keys are documented in [`schemas/global-script-state.schema.json`](../../schemas/global-script-state.schema.json);
card GMNotes in [`schemas/card-gmnotes.schema.json`](../../schemas/card-gmnotes.schema.json).

## Fixed identifiers

| Thing | Value |
| --- | --- |
| Seats | `COLORS = { "White", "Red" }`; White's half is `z < 0` |
| Cube deck GUID | `c00001` for the first cube in a fresh save; after a switch, whatever `cubeGuid` holds (non-interactable) |
| Cube keys | `lsv` (CubeCobra `LSVCube`), `vintage` (mtgo.com/vintage-cube-cardlist); first in `--cubes` loads on the table |
| Hand zone GUIDs | `a00001` (White), `a00002` (Red) |
| Sheet ids | fronts 1–40, tokens 41–50, DFC backs 51+ |
| Script headers | `BASIC_LANDS_JSON`, `TOKENS_JSON`, `MATS_JSON`, `CUBES_JSON`, `CUBE_DECKS` (key → deck JSON string) |
| Table | `Table_RPG` (felt y ≈ 0.96, 64 x 43) |

## Change recipe

1. Find the row above; read the feature's paragraph in `AGENTS.md`.
2. Write or adjust a failing test in `tests/test_draft_lua.py` (Lua) or `tests/test_builder.py` (Python).
3. Change the code. New TTS calls → extend `tests/lua/tts_mock.lua`. New saved state →
   `onSave` + default in `onLoad` + the state schema.
4. `uv run pytest`, then rebuild with `uv run draft-duel` (`--push` if images changed).
5. Update `AGENTS.md` (architecture) and this table if files, keys or tests moved.
6. Hand the user a test plan ([`router.in-game-test-planner`](../../router/in-game-test-planner/SKILL.md)).

Common changes have ready prompts: [add a token](../../knowledge/prompts/add-token.md),
[add a playmat](../../knowledge/prompts/add-playmat.md), [swap a card](../../knowledge/prompts/swap-card.md),
[add a cube](../../knowledge/prompts/add-cube.md).

## Related

- [`router.tts-change-router`](../../router/tts-change-router/SKILL.md)
- [`knowledge/verified-behaviours.md`](../../knowledge/verified-behaviours.md)
