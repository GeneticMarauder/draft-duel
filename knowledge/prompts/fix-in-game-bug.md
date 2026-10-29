# Prompt: Fix an in-game bug

**Use when:** something misbehaved while playing in TTS.
**Routes to:** `router.tts-change-router` → `mods.<mod>` → `core.lua-testing`, plus the
skill for the area (privacy, layout, decks, UI…).

```text
In the <mod> mod, while <what I was doing: phase, seat, action>, <what happened>.
I expected <what should have happened>.
Screenshot / chat output: <attach or paste>. Save loaded fresh after the last build: <yes/no>.

Follow AGENTS.md:
1. If I didn't load a fresh save, check that first (old saves keep the old script; see
   core/build-and-install — save_inspect.py --dump to compare).
2. Read knowledge/verified-behaviours.md — the cause may already be known.
3. Reproduce it as a failing test against tests/lua/tts_mock.lua. If the mock can't express
   what TTS did, extend the mock to match TTS and note it in verified-behaviours.md.
4. Fix, uv run pytest, rebuild, and tell me exactly what to retry in game.
```

**Done when:** a regression test fails before and passes after the fix, the save
is rebuilt, and any newly learnt TTS behaviour is recorded.
