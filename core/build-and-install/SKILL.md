---
skill_id: "core.build-and-install"
name: "Build, Install and Inspect Saves"
description: "Turn the repo's Lua, XML and data into a TTS save, install it into the Saves folder, publish images, and inspect what a save actually contains; use after any change that must be tried in the game."
layer: "core"
type: "tooling"
execution_mode: "automated"
version: "0.1.0"
verified: "in-game"
depends_on: []
samples:
  - "scripts/save_inspect.py"
side_effects:
  - "uv run draft-duel writes dist/ and copies the save into the TTS Saves folder."
  - "--push commits sheets/ and pushes to GitHub (public image hosting)."
  - "save_inspect.py --dump writes script files to the folder you name; otherwise read-only."
---

# Build, Install and Inspect Saves

## Purpose

Get a change from source into the game, and check what the game is running.

## When to use

- After any change the user should try in TTS.
- After changing card lists, tokens, playmats or anything image-related (needs `--push`).
- "My change isn't showing up in TTS" — inspect the save the user loaded.

## How it works

```text
src/draft_duel/lua/*.lua ─┐
src/draft_duel/lua/ui.xml ┼─ tts_save.build_save ─> dist/Draft Duel.json ─> TTS Saves folder
card/token/mat data + sheets ─┘        (cli.py)                   (copied if the folder exists)
sheets/*.jpg ── --push ──> GitHub (raw.githubusercontent.com URLs in the save)
```

| Command | Does |
| --- | --- |
| `uv run draft-duel` | Rebuild the save; reuses cached images in `.cache/images/`. |
| `uv run draft-duel --push` | Also commit + push `sheets/` so the image URLs resolve. Needed when sheets change. |
| `uv run draft-duel --cubes lsv,vintage,cubecobra:<id>` | Choose the cubes the save offers (first one on the table at load). |

The save format and the script-header convention are in
[references/save-file-format.md](references/save-file-format.md).

## Samples

| File | Gives you | Use |
| --- | --- | --- |
| [`scripts/save_inspect.py`](scripts/save_inspect.py) | Summary of any save, `--objects` list, `--dump DIR` of every embedded script/UI, `--saves-dir` | `uv run python core/build-and-install/scripts/save_inspect.py "dist/Draft Duel.json" --dump .cache/inspect` |

Diffing a user's loaded save against `dist/` (`--dump` both, then `git diff --no-index`)
answers "is the game running my new script?" in seconds.

## Gotchas

- (verified) Old saves and autosaves keep the script they were built with; the user must load the fresh save.
- (verified) TTS caches images by URL; change the URL (hashed names) when an image changes.
- (verified) Scryfall rejects TTS's user agent, so images must be self-hosted (this repo's `sheets/`).
- (verified) `--push` pushes as the GitHub account configured for this repo; confirm with the user before pushing.

## Testing

`tests/test_builder.py` checks the save structure. `save_inspect.py --help` and a
run against `dist/` are the quick checks for the tool.

## Related

- [`shared.custom-assets`](../../shared/custom-assets/SKILL.md)
- [`governance/in-game-testing.md`](../../governance/in-game-testing.md)
