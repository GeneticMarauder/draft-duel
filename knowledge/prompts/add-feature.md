# Prompt: Add a feature

**Use when:** the user wants new in-game behaviour in an existing mod.
**Routes to:** `router.tts-change-router` → `mods.<mod>` → the shared/core skills it names.

```text
Add this feature to the <mod> Tabletop Simulator mod: <what players should be able to do>.

Who triggers it: <which seat / any player / automatic>, via <button | right-click | screen UI | chat>.
When it's available: <game phase, e.g. only while playing>.
It must survive a save/reload: <yes/no>. Private to a player: <yes/no>.

Follow AGENTS.md and router/tts-change-router/SKILL.md:
1. Find the feature's neighbours in mods/<mod>/SKILL.md and read their AGENTS.md paragraphs.
2. Read knowledge/verified-behaviours.md and the skills the router selects; start from their samples.
3. Write failing tests first (tests/test_draft_lua.py with the TTS mock), then implement.
4. New saved state: onSave + default in onLoad + schemas/global-script-state.schema.json.
5. uv run pytest; rebuild with uv run draft-duel.
6. Update AGENTS.md and the mod map; give me an in-game test plan.
```

**Done when:** tests pass, the save is rebuilt, `AGENTS.md` and the mod map are
updated, and the user has a test plan. Ask before adding dependencies or pushing.
