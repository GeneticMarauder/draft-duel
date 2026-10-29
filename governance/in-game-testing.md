# In-Game Testing

The mock proves logic; only Tabletop Simulator proves behaviour (physics,
visibility, UI clicks, image loading). This is how in-game testing works here.

## Who drives

The user tests in TTS themselves. Don't take over their screen to test unless
they ask; if you are asked to drive and the screen starts changing on its own,
stop and wait for their report.

## The loop

1. Build: `uv run draft-duel` (add `--push` when card sheets or images changed).
   The save lands in `dist/` and in the TTS Saves folder.
2. In TTS: *Games → Save & Load* → load the save **fresh**. Old saves and
   autosaves embed the old script and won't show your change.
3. Run the test plan the agent wrote (`router.in-game-test-planner`).
4. Report back what happened, ideally with a screenshot or chat log.

## Tools inside TTS

| Tool | Use |
| --- | --- |
| `/execute <lua>` in chat | Runs Lua in Global (host only). Lines over ~240 characters get cut. |
| `!draftdebug`, `!draftauto [n]` | This mod's debug commands (see `core.debug.chat-commands` to add your own). |
| *Scripting → Global* (editor) | Read the script that is actually loaded. |
| `log(value)` / `print(value)` | Writes to the in-game console / chat. |
| Atom/VS Code TTS plugins | Push scripts to a running game on port 39999 (optional). |

After typing in chat, the next click on the table only takes focus away from
the chat box; click again.

## Recording what you learned

Anything TTS did that surprised you goes into
[`knowledge/verified-behaviours.md`](../knowledge/verified-behaviours.md) with the
date and what you saw. Flip a sample's `Verified:` to `in-game` once it has worked.
