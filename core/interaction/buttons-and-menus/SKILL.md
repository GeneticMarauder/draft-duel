---
skill_id: "core.interaction.buttons-and-menus"
name: "Object Buttons and Context Menus"
description: "Add clickable buttons and right-click menu items to objects and keep them through draws, flips and reloads; use when players act on a specific card or object rather than through the screen UI."
layer: "core"
type: "reference"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.lua-runtime"
  - "core.events.event-hooks"
samples:
  - "scripts/object_buttons.lua"
  - "scripts/context_menus.lua"
side_effects: []
---

# Object Buttons and Context Menus

## Purpose

Let players act on an object: a button drawn on it, or an item in its
right-click menu.

## When to use

- "Add a Draft / Take / Create token action to this card."
- "My right-click option disappeared after drawing / flipping / reloading."
- Choosing between an on-object button, a context menu and screen UI:

| Choose | When |
| --- | --- |
| Object button | The action belongs to one visible object and should be discoverable (pack cards' **Draft**). |
| Context menu | Optional actions that would clutter the object (tokens, Booster Tutor). |
| XML UI ([`core.ui.xml-ui`](../../ui/xml-ui/SKILL.md)) | Screen-level actions and per-seat panels (Start Draft, Ready, land buttons). |

## How it works

`obj.createButton{…}` draws a button in the object's local space and calls the
global named by `click_function` on `function_owner` with
`(obj, playerColor, altClick)`. `obj.addContextMenuItem(label, fn)` adds a menu
entry calling `fn(playerColor, position, obj)`. Neither is saved, and both vanish
when a card goes into a deck — so rebuild them from events.

In this repo: `makePickable` adds the **Draft** button + menu to pack cards;
`addPlayMenu` adds token/booster items while `playing`, re-run from
`onObjectSpawn`, `onObjectLeaveContainer`, `onObjectStateChange` and `onLoad`.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/object_buttons.lua`](scripts/object_buttons.lua) | `addActionButton`, `relabelButton`, `addLabel`, a seat-checked +/- counter | Global. |
| [`scripts/context_menus.lua`](scripts/context_menus.lua) | `menuItemsFor` rule hook, `applyMenu`, `refreshAllMenus`, the event wiring that keeps menus attached | Global; merge handlers you already have. |

## Gotchas

- (verified) Menus are lost when a card enters a deck and on reload.
- (verified) Buttons aren't saved; `table.lua` re-adds pack buttons in `onLoad`.
- (docs) Button `position` is local and multiplied by the object's scale — a 1.5x card moves its button too.
- (docs) A zero-size button with a label is the standard way to float text on an object.

## Testing

The mock records `createButton` params in `obj.buttons` and menu items in
`obj.menu` (`{label, fn}`); tests can call `obj.menu[i].fn("White")` to simulate a
click. Button placement and readability are TTS-only checks.

## Related

- [`core.events.event-hooks`](../../events/event-hooks/SKILL.md)
- [`core.state.save-and-load`](../../state/save-and-load/SKILL.md)
