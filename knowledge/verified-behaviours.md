# Verified TTS Behaviours

Facts about Tabletop Simulator that were **seen in the game** while building
this repo. Docs and forum posts are often wrong or out of date; these aren't.
Read this before changing in-game Lua. Add to it whenever TTS surprises you:
one line, what you saw, where it matters, and the date if you know it.

## Table and geometry (Table_RPG)

- Felt top is at y ≈ 0.96; the table is 64 x 43 units.
- The cube deck's centre sits at y = 2.01 with the deck 2.1 thick. A save that starts it lower (it used
  to say 1.2) leaves it half inside the table, non-interactable, so a layout measured from it read the
  felt as 0.15 (2026-10-29). A non-interactable deck does not fall: lifted to y=2.8 it stayed there.
  A switched-in cube measured while still dropping put the felt at 1.72 and the playmat then covered
  every card. So `computeLayout` no longer measures the felt: it is the constant `FELT_Y` 0.96.
- A `Custom_Tile`'s bounds run from its position up by its thickness (a mat at y=1.01, thickness 0.1,
  has its top at 1.11): cards floating with gravity off must sit above that (2026-10-29).
- A freshly spawned `Custom_Tile` has `loading_custom` true and bounds of size 0 (no collider) until its
  image loads, 20-30 frames later. A playmat spawned where cards already lay on the felt covered them:
  something has to lift them onto it once it has loaded (2026-10-30).
- A playmat tile turned to `seatYaw` shows its image as the owner sees it: the image's top toward the
  middle line (Synthwave's sun beyond the grid, seen from White). A centred mat covers the zone column the
  table image paints at u 18.7..21.7, so the mats carry that art themselves (2026-10-30).
- A `Custom_Tile` is 2 units deep at scale 1; its width follows the image's aspect ratio
  (a 2048 x 744 image at scale 8 makes a 44 x 16 mat).

- `Table_Custom` (custom rectangle, as the MTG EDH table uses): felt also at y = 0.96, flat to about
  x ±55, z ±37; the image covers 88.4 x 52.2 units, centred (fitted to the EDH mod's objects on its
  image), top edge toward +z, not mirrored (2026-10-29).
- `Tables.setTable(...)` in a running game removed both hand zones: set the table in the save instead.

## Objects, decks and containers

- Cards dropped or placed on each other merge into a deck unless `tryObjectEnterContainer` returns false.
  Cards stacked with `setPosition` merge by themselves as they land: 0.6 s later every card object is
  gone (they compare equal to nil), so `group()` had nothing to group and code holding the card list never
  found the pile. Find the pile by position and check it holds every card (2026-10-29).
- A locked deck refuses `putObject` — unlock, put, re-lock.
- `deck.putObject(card)` with the card turned like the deck: from above (y + 2) it becomes the top card
  (index 1 of `getObjects`, the next `takeObject` / deal), from below (y - 2) the bottom; at the same
  height it went on top. A card left at its own rotation once went to the bottom instead (2026-10-30).
- `takeObject{}` takes the top card (index 1); `takeObject{ top = false }` the bottom one (2026-10-30).
- A deck reduced to one card becomes that card (the deck's GUID is gone).
- Flipping a multi-state card (DFC) fires `onObjectStateChange(obj, oldGuid)` with a new GUID.
- `spawnObject` + `setCustomObject` in the same frame makes a working custom tile;
  hand-written `spawnObjectData` tile data failed to load.
- `interactable = false` is not saved; reapply after load.

- An object's buttons may sit outside its bounds: the zone board's Scry / Surveil / Mulligan float
  beside the tile and render and take real clicks there. A button's local +x on a tile turned to
  `seatYaw` is the owner's right (TTS mirrors button x) (2026-10-30).

## Visibility and privacy

- TTS can lose an object's `setInvisibleTo` list when a player picks it up, moves it or flips it:
  re-apply on every pickup/drop/state change, and again ~3 frames later.
- Hidden zones are drawn as solid blocks in the owner's color and ignore their tint.
- `setHiddenFrom(others)` lets others see the card back; `setInvisibleTo(others)` hides it entirely.

## Scripting lifecycle

- Buttons, context menus and visibility are not kept across a reload — rebuild them in `onLoad`.
- Context menu items are lost when a card enters a deck.
- Old saves and autosaves keep the script they were made with; test changes from a freshly built save.
- `onLoad` runs before objects are ready; this mod waits 10 frames before laying out.

## UI

- XML UI in the top-right corner (under TTS's player list) does not receive clicks.
- `UI.setValue` does not relabel a `Button`; use `UI.setAttribute(id, "text", …)`.
- TTS's `Dropdown` opened off-screen and couldn't be re-selected after a reload; a panel of buttons works.
- XML entities in labels show literally (`&amp;`); keep labels free of `<>&"`.
- The top ~70 px of the screen is TTS's own toolbar.

## Images and hosting

- Scryfall returns HTTP 400 for TTS's user agent (and generic library agents): download with a
  proper `User-Agent` and re-host.
- TTS caches images by URL; a changed image needs a new URL (content-hashed file names).

## Testing in game

- `/execute <lua>` in chat runs in Global (host only); lines over ~240 characters get cut.
- The external-editor API needs no screen: TTS listens on localhost:39999 and answers on 39998.
  `uv run draft-duel-live exec "<lua>"` runs Lua in Global and prints the game's prints and errors;
  script-local variables are not reachable from it. `uv run draft-duel-live load` is the editor's
  Save & Play: it swaps in the new script and reloads, and it can write the open game into the save
  file. It is **not** reliably a fresh load (once it came back fresh, once in an older session's
  sideboarding state): print the status bar after it, and reinstall the clean save afterwards (2026-10-29).
- In TTS, Start Draft was pressed while `onLoad`'s 10-frame layout had not run (`L` nil in `dealTo`):
  never rely on the delayed layout at a button press; `onStartClicked` re-measures (2026-10-29).
- After typing in chat, the next click on the table only takes focus away from the chat box.

## Lua dialect

- TTS runs MoonSharp (Lua 5.2): no `//`, no `goto`, numbers are doubles.
