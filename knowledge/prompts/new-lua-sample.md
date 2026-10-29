# Prompt: Capture a new Lua sample

**Use when:** you solved something in TTS Lua that other features or mods could reuse.
**Routes to:** `governance/lua-sample-standards.md`, `governance/skill-design-standards.md`.

```text
Turn <technique, e.g. "drag-to-reorder cards in a row"> into a registry sample.

1. Pick the skill: core (one TTS API area) or shared (a pattern across areas). If none fits,
   create one from governance/templates/SKILL.template.md.
2. Write scripts/<name>.lua from governance/templates/sample.template.lua: header block,
   config on top, offered functions global, internals local, MoonSharp-safe, no mod names.
3. Verified: in-game only if it ran in TTS; otherwise docs-only.
4. Add it to the manifest's samples list and the Samples table; add the skill to
   SKILLS_TAXONOMY.md if it is new.
5. If it needs TTS functions the mocks lack, add them to tests/lua/tts_mock_registry.lua;
   add assertions to tests/test_registry.py if the logic is worth pinning.
6. uv run pytest.
```

**Done when:** `tests/test_registry.py` passes and the taxonomy lists the sample.
