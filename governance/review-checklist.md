# Review Checklist

Run through this before handing a change back.

## Every change

- [ ] `uv run pytest` passes (mod tests and `tests/test_registry.py`).
- [ ] `uv run ruff check` is clean for any Python touched.
- [ ] `git diff --check` shows no whitespace errors.
- [ ] `AGENTS.md` still describes the code (update the Architecture section in the same change).

## Lua (in-game script)

- [ ] MoonSharp-safe: no `//`, `goto`, bitwise operators, `<const>` (the registry test checks samples; eyeball `src/`).
- [ ] Objects captured in `Wait` callbacks are `nil`-checked.
- [ ] New persistent state is in `onSave` **and** restored in `onLoad` with a default
      (old saves won't have the key) — and listed in `schemas/global-script-state.schema.json`.
- [ ] Buttons, context menus, `interactable` and visibility are reapplied in `onLoad`
      (TTS doesn't save them).
- [ ] Anything that must stay private is re-hidden after pickup/drop/flip (`shared.card-privacy`).
- [ ] New TTS calls the tests hit are in `tests/lua/tts_mock.lua`.
- [ ] Clickable XML UI is not in the top-right corner (it doesn't receive clicks).

## Samples and skills

- [ ] Header block present and accurate (`governance/lua-sample-standards.md`).
- [ ] `Verified: in-game` only if you watched it work in TTS.
- [ ] Manifest `samples:` lists every file in `scripts/`; `SKILLS_TAXONOMY.md` lists the skill.
- [ ] Relative links resolve (the registry test checks).

## Before the user tests in TTS

- [ ] Rebuilt with `uv run draft-duel` (add `--push` if sheets/images changed).
- [ ] Told the user to load the **fresh** save: old saves and autosaves keep their old embedded script.
- [ ] Gave them a short test plan (`router.in-game-test-planner`).
