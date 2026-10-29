# Prompt: Start a new mod

**Use when:** building a different Tabletop Simulator game in this repo.
**Routes to:** `shared.rules-engine-pattern`, `core.build-and-install`, `core.lua-testing`, `mods/`.

```text
Start a new Tabletop Simulator mod: <game, players, the core loop in 3 sentences>.

1. Ask me where it should live (a new package beside src/draft_duel/, or its own repo
   created with New-AgentProject) before creating anything.
2. Rules first: a pure engine from shared/rules-engine-pattern/scripts/pure_core_template.lua,
   with tests from core/lua-testing/scripts/template_lua_test.py.
3. Adapter: start from the core/shared samples it needs (seats, layout, buttons, privacy, save/load).
4. Builder: a Python module that writes the save JSON (core/build-and-install/references/
   save-file-format.md) and embeds Lua + XML like tts_save.global_lua does.
5. Add mods/<mod>/SKILL.md (same shape as mods/draft-duel/SKILL.md) and an AGENTS.md
   architecture section; list the mod in mods/README.md and SKILLS_TAXONOMY.md.
```

**Done when:** engine and adapter tests pass, a save builds, and the mod map exists.
