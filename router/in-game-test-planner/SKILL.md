---
skill_id: "router.in-game-test-planner"
name: "In-Game Test Planner"
description: "Write the short, numbered test plan the user runs in Tabletop Simulator after a change, covering setup, shortcuts, expected results, the reload check and what to report; use at the end of every change the user will try in game."
layer: "router"
type: "orchestration"
execution_mode: "advisory"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.debug.chat-commands"
  - "core.build-and-install"
samples: []
side_effects: []
---

# In-Game Test Planner

## Purpose

The mock can't show physics, visibility, UI clicks or image loading; the user
can. Give them a plan that takes minutes and tells you exactly what broke.

## When to use

At the end of any change the user will try in TTS, and when they ask
"how do I test this?".

## Plan template

```markdown
**Setup**
1. Load *<save name>* fresh from Games → Save & Load (old saves keep the old script).
2. Sit at <White/Red>; leave <seat> empty for a bot.
3. Shortcut to the right phase: `!draftauto` (finishes the draft), …

**Check**
4. <action> → you should see <result>.
5. <edge case: other seat / right-click / flip / tapped card> → <result>.

**Reload**
6. Save, load that save again → <what must still be true>.

**If it fails**, send: a screenshot, the chat log, and which step.
```

## Rules

- Under 12 steps. One behaviour per step, each with an observable result.
- Always include the fresh-load step and a reload check if the change touches state,
  buttons, menus or visibility.
- Privacy changes: include a step from the *other* seat (switch color, or a second player).
- Use shortcuts so the user doesn't play 96 picks: `!draftauto [n]`, `!draftdebug`,
  `!hide`; add a new chat command if the phase is hard to reach
  ([`core.debug.chat-commands`](../../core/debug/chat-commands/SKILL.md)).
- Don't drive the user's screen to run the plan unless they ask
  ([`governance/in-game-testing.md`](../../governance/in-game-testing.md)).
