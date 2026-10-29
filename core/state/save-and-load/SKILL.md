---
skill_id: "core.state.save-and-load"
name: "Save and Load Script State"
description: "Persist script state with onSave/onLoad and rebuild what TTS doesn't save; use when adding any state that must survive a save, reload, rewind or host migration."
layer: "core"
type: "reference"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.lua-runtime"
samples:
  - "scripts/persistent_state.lua"
side_effects: []
---

# Save and Load Script State

## Purpose

Make a script resumable: the game state lives in a JSON string TTS stores in
the save, and everything TTS doesn't store is rebuilt on load.

## When to use

- Adding a variable the game needs after a reload ("who is ready", "which mat").
- "After loading the save, the buttons/menus are gone" or "cards are visible again".
- Changing the shape of saved state (needs a default or a migration).

## How it works

TTS calls `onSave()` whenever it saves (manual save, autosave, rewind snapshot)
and stores the returned string as the script's state. On load it calls
`onLoad(savedState)` with that string (`""` for a fresh save). Each script —
Global and every object — has its own state.

What **is** saved with objects: position, rotation, lock, name, description,
GMNotes, memo, tags, custom images, deck contents, states.
What is **not**: object buttons, context menu items, `setInvisibleTo` /
`setHiddenFrom`, `interactable`, pending `Wait`s, XML UI attribute changes.

In this repo: `table.lua` encodes `draft`, `ready`, `piles`, `playing`, `booster`,
`owned`, `tutored`, `gameNumber`, `mats` (see
[`schemas/global-script-state.schema.json`](../../../schemas/global-script-state.schema.json))
and rebuilds buttons, menus and visibility 10 frames after `onLoad`.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/persistent_state.lua`](scripts/persistent_state.lua) | `DEFAULT_STATE` + `withDefaults`, `migrate` for old saves, safe `decode`, `rebuildTransient` example (button on a saved object) | Paste into Global; replace the example fields. |

## Gotchas

- (verified) Buttons, menus, visibility and `interactable` are lost on reload; rebuild them.
- (verified) Old saves and autosaves keep the **script** they were made with. Testing a
  script change means loading the freshly built save.
- (verified) Keep objects by GUID. A card that enters a deck and comes out again keeps
  its GUID; a DFC flipped to another state gets a new one (`onObjectStateChange(obj, oldGuid)`).
- (docs) `obj.memo` is a per-object string TTS saves — handy for object-local state
  without a script on the object.
- (docs) Empty Lua tables encode as `[]`; arrays with holes become objects with string keys.

## Testing

Round-trip in `lupa`: call `onSave()`, start a fresh runtime, call `onLoad(saved)`,
flush `Wait`s and assert. `tests/test_draft_lua.py` does this mid-draft; copy
its shape (see [`core.lua-testing`](../../lua-testing/SKILL.md)). In TTS: save,
*Games → Save & Load* the same save, check rebuilt UI and visibility.

## Related

- [`shared.card-privacy`](../../../shared/card-privacy/SKILL.md) — visibility must be reapplied on load.
- [`core.interaction.buttons-and-menus`](../../interaction/buttons-and-menus/SKILL.md) — rebuilding menus.
