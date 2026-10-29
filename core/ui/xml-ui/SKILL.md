---
skill_id: "core.ui.xml-ui"
name: "XML UI (Screen Panels and Buttons)"
description: "Build screen UI with TTS's XML UI and drive it from Lua (per-seat visibility, relabelling, confirm clicks, generated pickers); use for any on-screen panel, prompt, status bar or button."
layer: "core"
type: "reference"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.lua-runtime"
  - "core.players.seats-and-cameras"
samples:
  - "scripts/seat_panel.xml"
  - "scripts/seat_panel.lua"
side_effects: []
---

# XML UI (Screen Panels and Buttons)

## Purpose

Screen-space UI: status bars, prompts, per-seat panels and buttons, written in
XML and controlled from Lua.

## When to use

- A new button or panel on screen (not on an object).
- "My button doesn't respond" — check placement (top-right dead zone) and handler signature.
- "The label didn't change" — Buttons need `setAttribute(id, "text", …)`.
- A UI that depends on data (one thumbnail per playmat) — generate the XML in Python.

## How it works

The Global UI is an XML document (save field `XmlUI`). Elements have ids; Lua
reads and writes their attributes with `UI.setAttribute` / `UI.getAttribute`,
text with `UI.setValue`, and show/hide them via the `active` attribute.
`onClick="fnName"` calls the Global function `fnName(player, value, id)`.
`visibility="White|Red"` limits who sees an element. Images used by the UI are
save-level `CustomUIAssets` referenced by name.

In this repo: `src/draft_duel/lua/ui.xml` is the static UI; `tts_save.mat_pickers`
generates the playmat pickers into the `<!--MAT_PICKERS-->` marker, and their
thumbnails are `CustomUIAssets` named `matthumb<i>`.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/seat_panel.xml`](scripts/seat_panel.xml) | `<Defaults>`, two per-seat panels with text + buttons, ids ending `_<Color>` | Global UI. |
| [`scripts/seat_panel.lua`](scripts/seat_panel.lua) | `showSeatPanel`, `setSeatText`, `setButtonLabel`, seat-checked handlers, a two-click confirm | Global script. |

## Gotchas

- (verified) Top-right corner UI (under TTS's player list) does not receive clicks.
- (verified) `UI.setValue` does not relabel a `Button`; use `setAttribute(id, "text", …)`.
- (verified) TTS's `Dropdown` opened off-screen and couldn't be re-selected after a reload — a panel of buttons is more reliable.
- (verified) XML entities show literally in labels; `mat_pickers` rejects names needing escaping.
- (docs) `setAttribute` changes aren't saved; re-apply UI state in `onLoad`.
- (docs) Replacing the whole UI with `UI.setXml` takes a frame and resets every attribute.

## Testing

The mock stores `UI.setValue(id, v)` in `Mock.ui[id]` and `setAttribute` in
`Mock.ui[id .. "." .. attr]`; assert on those. Layout, overlap and clickability
are TTS-only checks — ask the user for a screenshot.

## Related

- [`core.interaction.buttons-and-menus`](../../interaction/buttons-and-menus/SKILL.md) — on-object alternatives.
- [`core.players.seats-and-cameras`](../../players/seats-and-cameras/SKILL.md)
- [TTS UI docs](https://api.tabletopsimulator.com/ui/introUI/)
