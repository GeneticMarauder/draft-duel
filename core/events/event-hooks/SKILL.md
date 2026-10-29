---
skill_id: "core.events.event-hooks"
name: "Event Hooks"
description: "Which TTS events fire when, their signatures and return values, and a logger to observe them; use when a feature must react to players' actions or when unsure what TTS does during a draw, drop, flip or merge."
layer: "core"
type: "reference"
execution_mode: "advisory"
version: "0.1.0"
verified: "docs-only"
depends_on:
  - "core.lua-runtime"
samples:
  - "scripts/event_logger.lua"
side_effects: []
---

# Event Hooks

## Purpose

React to what players do. TTS calls global functions with fixed names when
things happen; this skill lists them and gives you a way to watch them fire.

## When to use

- "When a player drops / draws / flips a card, do X."
- Debugging order-of-events surprises (a menu vanishing, privacy lost after a flip).
- Before adding a handler: check whether the mod already defines it (it would be replaced).

## How it works

One function per event name per script. Signatures and return-value semantics
are in [references/event-catalog.md](references/event-catalog.md). Handlers run
before TTS has finished its own handling, so changes that must "stick" are often
re-applied a few frames later.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/event_logger.lua`](scripts/event_logger.lua) | Logs every common event with readable arguments; `!events on/off` | A scratch save's Global — not the mod. |

## Gotchas

- (verified) Defining a handler a second time in the same script replaces the first — `table.lua` already defines ten; extend them.
- (verified) Flipping a DFC fires `onObjectStateChange(obj, oldGuid)` and the card's GUID changes; `table.lua` follows the GUID in `owned` / `tutored`.
- (verified) A card taken out of a deck fires `onObjectSpawn` and `onObjectLeaveContainer`; its menus must be re-added there.
- (docs) `onChat` returning `false` hides the message from chat.

## Testing

Call handlers directly from Python (`lua.globals().onObjectDrop("White", card)`)
then `Mock.flush()`. The *order* TTS fires events in can only be learnt in game —
the logger exists for that.

## Related

- [`core.debug.chat-commands`](../../debug/chat-commands/SKILL.md)
- [`core.interaction.buttons-and-menus`](../../interaction/buttons-and-menus/SKILL.md)
