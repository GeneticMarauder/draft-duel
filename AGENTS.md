# AGENTS.md - draft-duel

Policy layer + architecture for this repo. This file is the source of truth;
`CLAUDE.md` just imports it. Keep it current as the code evolves.

## Ground truth first

Before editing: inspect the actual repo tree and align to files that exist today.
Create new modules only when the task clearly requires them. Treat any
architecture described here as the target, not proof it already exists.

## Skills registry — start here

This repo is organised as a skills registry for Tabletop Simulator work
(modelled on oracle/Fusion-Setup-Configuration-Registry). Each skill is a folder
with a `SKILL.md` manifest, ready-to-use `scripts/` samples and `references/`.

- **Every change request starts at [`router/tts-change-router/SKILL.md`](router/tts-change-router/SKILL.md)**
  (or `/tts-change`). It classifies the request and picks the mod map, skills,
  prompt and definition of done.
- Layers, dependencies pointing downward only:

  | Layer | Holds |
  | --- | --- |
  | `router/` | Entry points: change router, in-game test planner. |
  | `mods/` | One feature map per mod (`mods/draft-duel/`): feature → code → state → tests. |
  | `shared/` | Reusable gameplay patterns: privacy, layout, rules engine, tokens, assets. |
  | `core/` | One TTS API area each, with Lua samples: state, objects, decks, buttons, UI, seats, events, debug, testing, build. |
  | `knowledge/` | `verified-behaviours.md` (what TTS really does), API links, `prompts/`. |
  | `schemas/` | Manifest, card GMNotes and Global script-state contracts. |
  | `governance/` | Skill and Lua sample standards, naming, review checklist, in-game testing, templates. |

- Full list: [`SKILLS_TAXONOMY.md`](SKILLS_TAXONOMY.md). Read
  [`knowledge/verified-behaviours.md`](knowledge/verified-behaviours.md) before changing in-game Lua,
  and add to it whenever TTS surprises you.
- New reusable techniques become samples under the right skill
  ([`governance/lua-sample-standards.md`](governance/lua-sample-standards.md)); `tests/test_registry.py`
  checks manifests, links, sample headers, MoonSharp syntax, and runs every sample under the mock.
- This file keeps the policy and the mod's architecture; skills link here instead of repeating it.

## Tooling — uv only (enforced by a global hook)

- Add a dependency:      `uv add <package>`   (dev: `uv add --group dev <package>`)
- Install / sync:        `uv sync`
- Run something:         `uv run <cmd>`  (e.g. `uv run pytest`)
- **Never** `pip install`, **never** `python -m venv` — the guard hook blocks both.
- Commit `uv.lock`.

## Structure

- src-layout: code in `src/draft_duel/`, tests in `tests/`.
- Slice by concern (`config`, `io`, `services`, `models`) rather than one module.

## Shared code — reuse agent-core, don't reinvent

Deterministic building blocks (config/`.env` loading, csv/json <-> Pydantic I/O,
logging) come from **agent-core**. Import them instead of re-writing:

```python
from agent_core.config import BaseConfig
from agent_core.io import read_table, validate_records, write_records
from agent_core.utils import get_logger
```

Only add the LLM extra (`agent-core[llm]`) if this project calls an LLM at runtime.

## Definition of done

1. `uv run pytest` passes.
2. Public functions have docstrings and type hints.
3. Ask before adding any new external dependency.

## Architecture

Builds **Draft Duel**, a Tabletop Simulator (TTS) save for a 1v1 pick-from-5 cube draft, and
**Draft Duel 4P**, the same mod for four players with a queue draft. Each save
offers several cubes (default: the LSV Cube from CubeCobra and the latest MTGO Vintage Cube); players
pick one at the table before the draft. Both saves share the sheets, tokens and props. Two halves:

**Python builder** (`uv run draft-duel [--cubes lsv,vintage,cubecobra:ID] [--push]`)
- `seats.py` — the two tables: `DUEL` (White at -z, Red at +z, each half the table) and `FOUR` (as at the
  MTG EDH table: White and Red along -z, Green and Blue along +z, each a quarter centred `QUARTER_X` 22.1
  from the middle; seats in passing order). A `Table` has the save `name`, `seats` (`color`, `side`, `x`),
  `hand_d`/`hand_w`, `mat_w` (44 or 38; mats are always 16 deep) and the painted `panel_w`;
  `script_header()` reaches the script as `SEATS_JSON`.
- `cubes.py` — `CUBES` registry (`CubeSource`: `key` saved with the game, display `name`, `kind`, `ref`).
  `cubecobra` sources use `fetch_cube_ids` (owner's printings, plus the cube's basics); the `mtgo` source
  reads MTGO's official page (`MTGO_VINTAGE_URL`, always the latest iteration) with `parse_mtgo_cardlist`
  (first Color | Card table = current list; the page also has the changelist and the previous list)
  and looks names up on Scryfall. `resolve` also accepts `cubecobra:<id>`. The first cube in `--cubes`
  is on the table at load; basics come from the first cube that lists them, else by name.
- `sources.py` — CubeCobra mainboard ids → Scryfall `/cards/collection` → `Card`s; `fetch_cards_by_name`
  batches names and falls back to `/cards/named?exact=` (the collection endpoint misses some split cards
  by full name, e.g. "Life // Death"); image
  downloads cached in `.cache/images/`. `CARD_SWAPS` replaces cube cards by name with cards we play
  instead (Cogwork Librarian → Booster Tutor); the build prints each swap. Always sends `USER_AGENT`: Scryfall returns 400 for
  generic/library user agents, **including the one TTS itself sends**.
- `sheets.py` — 10x7 JPEG deck sheets (69 cards each; last slot is TTS's hidden-card slot),
  409x570 per card so sheets stay ≤4096 px; content-hashed filenames to defeat TTS's URL cache.
- `tts_save.py` — save JSON: `Table_Custom` with our table image (`Table_RPG` without one), hand zones (fixed GUIDs), the first cube's deck on the table
  (`c00001`; DFC backs as card state 2 on sheets ≥ 51), Global Lua + XML UI. `build_save(cubes, …)`:
  cards take the front sheets cube by cube, then basics; card GUIDs are offset per cube so they never
  collide; each deck's `CustomDeck` lists only its own sheets. Every cube's deck is also embedded in the
  script as a JSON string (`CUBE_DECKS[key]`, plus the `CUBES_JSON` list) — strings, so loading the save
  decodes nothing. Headers use `lua_long_string` (enough `=` that card text can't end the string).
  `cube_pickers` writes the per-seat cube pickers into `<!--CUBE_PICKERS-->` (none for a one-cube save).
  `build_save(..., table=FOUR)` makes the four-player save: four hand zones, the cube at x 0, `SEATS_JSON`,
  `zones.layout_for(38)`. `global_xml(mats, cubes, colors)` repeats every `<!--SEAT-->`…`<!--/SEAT-->`
  block of ui.xml per seat (`{seat}` = its color); the pickers are per seat too. The script always holds
  both engines (`draft_core.lua`, `queue_draft.lua`, then `table.lua`).
- `tokens.py` — tokens from the curated `data/tokens.csv` (one row per token; "Made by" lists cube
  card names separated by `;`, DFCs as "Front // Back"). `match_makers` links them to the cards of
  every cube by name → card id (one card can have a different id per cube's printing); the build prints
  maker names in no cube. Cards that make tokens but have no row (common in the Vintage Cube) simply
  get no Create menu. Token images are downloaded
  through our client like card images and rendered on their own sheets (`TOKEN_SHEET_BASE` 41+:
  fronts, then backs of double-faced tokens).
- `playmats.py` — `THEMES`: twelve playmats drawn procedurally with Pillow (seeded, so identical pixels
  and hashed names every build; no copyrighted art). `MAT_SIZE` 2048x744 matches the 44x16 in-game mat.
  Pictures in the repo's `playmats/` folder are added after the themes (`fit_image`: whole picture,
  centred, padded with its edge colour; name from the file name). `with_zones` paints the zone board's
  art onto every mat where the board lies (the mat covered the column the table paints there; a mat image
  is drawn as its owner sees it, top toward the middle). `render_narrow` draws the same mats 38 wide for the
  four-player table (themes keep the centre of their art, pictures are fitted again; `sheets/mat38w??`), sharing
  the 1v1 thumbnails. Saved to `sheets/mat??-<hash>.jpg`
  plus `matthumb??` thumbnails (plain art, no zones); names/URLs reach the script as `MATS_JSON`; thumbnails are save-level
  `CustomUIAssets` (`matthumb<i>`) used by the pickers that `mat_pickers` writes into `<!--MAT_PICKERS-->`.
- `zones.py` — the zone board (borrowed from the MTG EDH table): `LAYOUT` (owner-relative `u` across,
  `d` from the middle line) holds the board, its Library / Graveyard / Exile slots, the Draw / Untap
  button strips, the Scry / Surveil / Mulligan buttons beside it (`SIDE_U`), the scry look row (`LOOK`),
  the sideboard spot and the dice; `layout_for(mat_w)` moves the board to a narrower mat's right edge and,
  with no room beside that mat, puts the sideboard pile and dice just past its hand-side edge (d 19.6);
  `render_board` draws the image from it
  (`sheets/zones-<hash>.jpg`) and the same numbers reach the script as `ZONES_JSON` (with the image `url`).
- `tabletop.py` — the table top, a 1v1 take on the MTG EDH table: grey wood grain, one wide dark
  mat per player (`PANEL_W` 62 x 16, the 44-wide playmat lies over its middle) in a light wood frame with
  a plain gold trim (no title or logo), and the zone board's art painted where the board lies in a game.
  `TABLE_W` x `TABLE_H` (88.4 x 52.2) is the area TTS's custom rectangle table stretches the image over
  (measured in TTS); Red's half is White's panel turned 180 degrees. Saved as `sheets/table-<hash>.jpg`.
  `render_table(FOUR)` paints four 43-wide panels, one per quarter (`sheets/table4p-<hash>.jpg`).
- `props.py` — table props from the MTG EDH mod (Workshop 2425949312), at their EDH spots on the
  custom table's wooden ends: mana counters, keyword markers and counter-token bags (left), d20/d10/d6
  and coin bags, the emblem deck, an extra-cards deck (Monarch, Day // Night, Initiative…) and the
  dungeon cards (right), black-hole bins in the corners. Other people's Workshop objects, so not in
  this repo: `load_props(workshop_file())` reads `PROP_GUIDS` from the player's downloaded EDH save each
  build (none if absent; `KeyError` if the mod dropped one), locks them, and `merge` re-GUIDs any
  collision. Their card and token images were on Scryfall (the retired c1 host, or cards.scryfall.io,
  which refuses TTS): `card_faces` / `token_images` list them on the current host, the build downloads
  them, renders cards onto `props??` sheets (`PROP_SHEET_BASE` 71+, card states such as Night included)
  and the custom-token art into `proptoken??` PNGs (PNG: a token's shape is its transparency), and
  `rehost` / `rehost_tokens` repoint the objects. Left out: importers / web-fetching tools and EDH-only
  counters. Our scripts only act on cards, so the props never interfere.
- `live.py` — `uv run draft-duel-live exec "<lua>"` / `load`: tests in the running game through TTS's
  external-editor API (localhost:39999/39998), no screen needed (see verified-behaviours).
- `cli.py` — orchestrates; writes `dist/Draft Duel.json` and `dist/Draft Duel 4P.json` (`render_all` →
  `Rendered`: both tables' images and mats; it deletes every other image in `sheets/`, so one run must
  render everything both saves use), copies them into the TTS Saves
  folder when it exists, `--push` commits `sheets/` so raw.githubusercontent.com URLs resolve. Without
  `--push` the build warns about every `sheets/` image `origin/<branch>` lacks (`unpublished_sheets`):
  TTS shows a missing sheet as blank white cards ("unsupported format: UNKNOWN" in the log).
- Card images are served from this public repo (`sheets/`). TTS cannot load Scryfall images directly.

**Lua (in-game Global script)** — `src/draft_duel/lua/`
- `draft_core.lua` — pure rules engine (no TTS API). Per pack, starter S / other O:
  S picks, O picks, O picks, S picks — each from 5 cards (`PACK_SIZE`, topped up from the cube), then
  the 4 leftovers are discarded (the table destroys them: undrafted cards simply vanish). Starter alternates; 24 packs → 48 picks each (192 cards dealt).
- `queue_draft.lua` — the four-player rules engine (`QueueDraft`). Everyone opens a 16-card pack, takes 2
  (two separate picks; the turn ends on the second) and passes the rest to the back of the next seat's
  queue; a seat always picks from the front of its own queue, so fast drafters work ahead and packs pile
  up in front of a slow one. A pack goes round until empty (8 turns, two laps), so nothing is discarded.
  3 rounds (left, right, left); a seat opens its next pack as soon as it has taken its 8 turns of the round,
  without waiting for the table. 4 x 3 x 16 = 192 cards, 48 picks each. Both engines share the adapter's
  interface: `currentPack`, `queuedPacks`, `turnKey`, `canPick`, `pickers`, `addToPack(id, packId)`, and
  `pick` returning actions (`deal` with a `pack` id, `pick` with `turnOver`, `pass`, `finished`).
- `table.lua` — TTS adapter. Seats come from `SEATS_JSON` (default: the 1v1 table): `COLORS` (passing
  order), `SEAT_X`, `SEAT_SIDE`, `PLAYERS`; every placement goes through owner-relative helpers (`ownerU`,
  `worldX`, `seatPoint`) and `seatAt(p)` (whose part of the table a point is in, replacing the old z-sign
  checks), so the same code serves both tables. § four players overrides the sizes that must fit a quarter
  (pack 8 x 2 at 1.1x, queue stacks at `QUEUE_U`, deck columns u -15.8..15.8, tokens, cube parking).
  `layoutPack(color)` lays out a seat's current pack once per turn (`turnKey`: cards stay put between a
  seat's two picks), adds Draft buttons (`pickable`), and stacks queued packs face-down to its right;
  `runActions` re-lays only the seats an action touched; every bot with a pick waiting is scheduled
  (`botWaiting`). Per side, from the middle out: the cube in the middle strip, the pack row
  (current pack: 5 cards at 1.5x, side by side, locked, with an on-card **Draft** button and a
  right-click "Draft this card"), then the 12x4 pick grid (0.65x). Bots draft for seats empty at
  Start Draft. State persists via `onSave`/`onLoad` (buttons, menus and visibility are reapplied).
  Chat commands: `!draftdebug` (geometry dump), `!draftauto [n]` (random picks for testing).
  `computeLayout` measures card size and felt height from the cube (falling back to `FELT_Y` 0.96 when
  the cube hasn't settled); it runs from `onLoad` after 10 frames and again at Start Draft.
  **Deck editor** (after pick 96, and on reload of a finished draft): every card on a player's half
  is sorted into columns by mana value (0..7+, then lands), cascaded so names show, gravity off and
  non-sticky so cards stay flat and lift one at a time. The deck is centred on the table; owner-x
  beyond `SIDE_SPLIT_U` is the smaller sideboard (`AREAS`). `onObjectDrop` re-sorts. Basic lands come
  from the land buttons in the bottom panel (`onLandClicked`: left adds, right removes); a basic
  dropped in the sideboard is destroyed.
  `tryObjectEnterContainer` stops cards merging into piles. Card GMNotes carry
  `{"id","cmc","land","basic"}`; basic-land card data comes from the `BASIC_LANDS_JSON` script header, token data from `TOKENS_JSON`.
  **Ready to play**: `readyUp` (min 40 cards; bot seats ready automatically) stacks the deck into a
  face-down library and the sideboard into a pile invisible to the opponent (`gatherPile`: the cards
  merge by themselves as they land, so `settlePile` finds the pile by position — `objectAt` — and waits
  until it holds every card before naming it and recording `piles`); `startWhenPilesSettle` waits for
  every library, then `startGame` — when every seat is
  ready, `startGame` removes the land bags, moves the cube (and any discard pile from an older save) to the table edges,
  shuffles, deals 7 to each hand and spawns 20-life counters. `ready`, `piles`, `playing` persist.
  **Tokens** (only while `playing`): a card whose GMNotes id is in `TOKENS_JSON.makers` gets a
  right-click "Create <token>" per token; the token spawns in the nearest free card-sized spot beside
  the card (`tokenSpot`: along the row to the owner's right, then left, then rows toward the owner's
  hand; checked against every card/pile/counter's rotated bounds; kept on the owner's battlefield,
  `TOKEN_Z_MIN..MAX`, `|x| <= TOKEN_X_MAX`). A card in hand anchors at `TOKEN_HOME_*` on the
  clicker's side. (Fixed fan-out used to drop tokens on top of neighbouring cards — seen in TTS.) `UNIQUE_TOKENS` (The Monarch,
  Day // Night) move instead of duplicating. Menus are lost when a card enters a deck or on reload, so
  they are re-added on `onObjectSpawn` / `onObjectLeaveContainer` / state change / `onLoad`. Token
  GMNotes are `{"token": label}` (no `id`, so the deck editor ignores them). `addPlayMenu` builds
  these game-time menus.
  **Booster Tutor** (card named `BOOSTER_TUTOR`, right-click "Open a booster"): takes 15 cards from
  the undrafted cube into a face-up, locked row across the middle (revealed to all), each with a
  **Take** button / menu. Only the opener can take; the card goes to their hand, the rest are put
  back face-down into the cube (`returnToCube` unlocks the locked cube around `putObject`), which is
  shuffled. One booster open at a time; `booster` persists. The taken card's GUID goes in `tutored`:
  it only lasts one game.
  **Next game** (button in TTS's toolbar row, just left of the player list, while `playing`; second click within 4 s confirms) → `nextGame`:
  piles holding owned cards are emptied (all but the last card taken out; the last stays as a plain
  card), then every card is routed by GUID — `owned[color].main/side` (recorded at `readyUp`) back to
  that player's deck/sideboard area, `tutored` back into the cube; tokens and "<color> life" counters
  are destroyed. `building` is set first so `tryObjectEnterContainer` stops returning cards merging into
  piles (the cube is always allowed); returning cards float (gravity off) spread over the columns.
  `gameNumber` increments and the deck editor reopens ("Sideboarding for game N");
  Ready to play starts the next game via the same `readyUp`/`startGame`. `owned`, `tutored` and
  `gameNumber` persist and follow DFC flips in `onObjectStateChange`.
  **Playmats**: each seat's "Playmat: <name>" button (bottom right, `visibility` = that seat) opens a
  mid-screen picker of thumbnails (`onMatButton`); a thumbnail → `onMatPick` → `setPlaymat`
  (TTS's Dropdown opened off-screen and can't be re-selected after a reload, hence the picker): a `Custom_Tile` (spawnObject + `setCustomObject` in the same frame; raw
  `spawnObjectData` tile data failed to load in TTS) at scale `MAT_SCALE` (a tile is 2 units deep at
  scale 1 and its width follows the image), locked and non-interactable, centred `MAT_Z` from the middle.
  A replaced mat stays (`replacedMats`) until the new one's image has loaded (`whenMatLoaded`), so cards on
  it never drop to the felt; then `liftOntoPlaymat` raises every card/deck/die/counter whose bottom is
  inside the mat's footprint and below its top (a mat spawned where cards lay used to cover them all).
  `mats` persists; `onLoad` re-locks them (interactable is not saved), lifts anything buried, and
  `updateMatButtons` relabels the buttons. Next game leaves them alone.
  **Zones** (§ zones, from `ZONES_JSON`; empty header = no board, old pile spots): `readyUp` spawns the
  seat's zone board (`placeBoard`: a locked `Custom_Tile` on top of the playmat at the owner's right edge,
  scale `h/2`) before gathering the library into its Library slot; the sideboard pile goes off the mat
  (`SIDEBOARD_U/D`). The board carries real **Draw** (`drawCard`: deals 1 from `findLibrary` — the pile by
  GUID, else whatever is in the slot once the library is down to one card) and **Untap** buttons
  (`untapAll`: every unlocked card on the owner's side not in hand back to `seatYaw`, face-down kept
  face-down); only the owner may press them. Button sizes use `BUTTON_UNITS` (≈450 per table unit, an
  estimate). `boards` persists; `refreshBoards` re-adds buttons after a reload; `nextGame` removes the
  boards (the sideboard columns need that edge); `spotIsFree` keeps tokens off them. `placeDice` (onLoad)
  spawns a d20 and two d6 per seat, tinted its color, in its left corner, once (GMNotes `die:<color>:<i>`).
  **Scry / Surveil / Mulligan** (§ scry, surveil, mulligan): three more board buttons just right of the
  board (`zones.BUTTONS` entries with a `u`; the image paints no strip for them; `BUTTON_X_SIGN` maps
  owner-right to a button's local x). Scry / Surveil (`lookAtNext`) take the library's top card into the
  owner's look row (`zones.LOOK`, toward their left of the board): locked, face-up, `setHiddenFrom` the
  others; each click adds the next card. Each card has **Top** and **Bottom** (scry) or **Graveyard**
  (surveil) buttons and the same right-click items (`resolveLook`, owner only); `putInLibrary` returns a
  card with `putObject` from above (top) or below (bottom), see verified-behaviours; `putInGraveyard` drops
  it face-up on the graveyard slot. Draw and Mulligan wait until the row is empty. **Mulligan** (London,
  click twice: the label shows "Confirm?" for `MULLIGAN_CONFIRM` s) puts the hand's drafted cards back,
  shuffles and deals 7. The first mulligan of a game is free (`FREE_MULLIGANS`); each later one asks for
  one more card on the bottom (2nd: 1, 3rd: 2…), using the right-click
  "Put on bottom of library" that `addPlayMenu` now gives every drafted card in play (`putOnBottom`;
  not the opponent's card). `looks`, `mulligans`, `bottomOwed` persist; a new game clears them.
  **Cubes** (§ cubes): `CUBES` comes from `CUBES_JSON`; `cubeKey` (which cube) and `cubeGuid` (its deck —
  `c00001` only until a switch) persist; every former `CUBE_GUID` check uses `cubeGuid`. Until the draft
  starts, each seat's "Cube: <name>" button (bottom right, above the playmat button) opens its picker
  (`onCubeButton`); a choice → `onCubePick` → `switchCube`: destroys the cube deck and spawns the chosen
  one with `spawnObjectJSON(CUBE_DECKS[key])` at the old deck's position/rotation, non-interactable,
  then `computeLayout`. `updateCubeButtons` (from `updateUI`) relabels and hides the buttons once the
  draft starts or when the save has one cube. The status bar and the Start Draft broadcast name the cube.
  (Not yet seen in TTS: `spawnObjectJSON` of a full cube deck.)
- `ui.xml` — status bar (hidden once the game starts), Start Draft button, Reset view, Next game,
  per-seat playmat and cube buttons (pickers are generated). No "your pick" prompt: the pack laid out
  in front of the picker, with its Draft buttons, says it already.

**Privacy is per card, not hidden zones** (re-applied on every pickup/drop/state change via `rehide`, plus `!hide`). Pack cards use `setHiddenFrom(others)` (opponent sees
backs); picks use `setInvisibleTo(others)`. Hidden zones were dropped: TTS draws them as solid
blocks in the owner's color and ignores their tint. Hand zones exist only to define seats.

**Verified in game** — everything TTS was seen doing (Table_RPG felt y≈0.96 and 64 x 43 bounds, the
top-right UI dead zone, `UI.setValue` not relabelling Buttons, cards merging unless
`tryObjectEnterContainer` refuses, locked decks refusing `putObject`, `/execute` tips…) lives in
[`knowledge/verified-behaviours.md`](knowledge/verified-behaviours.md). Read it before changing `table.lua`;
add to it whenever TTS surprises you. (Reset view sits bottom right, above Ready to play, because of the dead zone.)

**Tests** — `tests/test_draft_lua.py` runs the real Lua under `lupa` against `tests/lua/tts_mock.lua`
(a mock of the TTS API); keep TTS-specific calls inside the mock's surface or extend the mock.
The mock's `Wait` has a clock (`Mock.now`; `flush` runs waits in time order) and can merge piles late
(`Mock.groupLate`). Passing the mock is not enough: before handing a change over, play it through in the
running game with `draft-duel-live` (fresh load → Start Draft → `autoPick(48)` → Ready → Next game → Ready).
`tests/test_registry.py` validates the skills registry and runs every Lua sample against the mock plus
`tests/lua/tts_mock_registry.lua` (extra API the samples use).
TTS Lua is MoonSharp (Lua 5.2): no `//`, no `goto`, no integer-only semantics.
<!-- Describe this project's real pipeline / modules here as it takes shape. -->
