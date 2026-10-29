---
skill_id: "core.debug.chat-commands"
name: "Debug Chat Commands"
description: "Add !commands to the game for testing and diagnosis (geometry dumps, auto-play, state checks); use when a feature needs a quick in-game test hook or when diagnosing a problem the user reports from TTS."
layer: "core"
type: "tooling"
execution_mode: "assisted"
version: "0.1.0"
verified: "docs-only"
depends_on:
  - "core.events.event-hooks"
samples:
  - "scripts/chat_commands.lua"
side_effects: []
---

# Debug Chat Commands

## Purpose

Give the person testing in TTS fast, scriptable shortcuts so a test that would
take 96 clicks takes one line of chat.

## When to use

- A new feature is deep into the game flow (deck building, game 2) — add a command
  that skips there, like `!draftauto`.
- You need numbers from the live game (positions, bounds, state) to fix layout bugs —
  add a dump, like `!draftdebug`.
- Recovering a stuck state for the user without a reload, like `!hide`.

## How it works

TTS calls `onChat(message, player)` for every chat line; returning `false` swallows
it. The sample turns that into a registry of `!name` commands with help text and
host-only checks, and catches errors so a broken command reports instead of crashing.

In this repo: `table.lua`'s `onChat` handles `!draftdebug`, `!draftauto [n]` and `!hide`.
Merge new commands into that function (or move it onto this dispatcher).

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/chat_commands.lua`](scripts/chat_commands.lua) | `command(name, help, fn, opts)`, dispatcher `onChat`, `!help`, `!count`, `!where <guid>` | Global; merge with an existing `onChat`. |

## Gotchas

- (verified) `/execute <lua>` runs in Global for the host; long lines get cut at ~240 characters.
- (verified) After typing in chat, the next click on the table only defocuses the chat box.
- (docs) Spectators chat as `"Grey"` and can't receive `broadcastToColor`.

## Testing

Call `onChat("!where c00001", Player.White)` from a test and inspect `Mock.messages`.
Document every command you add in the README's testing helpers line.

## Related

- [`governance/in-game-testing.md`](../../../governance/in-game-testing.md)
- [`core.events.event-hooks`](../../events/event-hooks/SKILL.md)
