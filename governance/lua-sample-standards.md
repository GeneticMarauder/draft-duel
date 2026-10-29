# Lua Sample Standards

Samples under `*/scripts/*.lua` are meant to be pasted straight into a TTS
script (Global or an object) or copied into a mod's source. They must work
on their own and explain themselves.

## Header block

Every sample opens with this block. `tests/test_registry.py` checks it.

```lua
--[[ core.state.save-and-load :: persistent_state.lua
Purpose  : Keep script state across save/load with versioned JSON.
Attach   : Global (works on any object script unchanged)
API      : onSave, onLoad, JSON.encode, JSON.decode, Wait.frames
Verified : in-game
Use      :
  1. Paste into the Global script.
  2. Put your fields in DEFAULT_STATE.
Gotchas  :
  - Buttons and context menus are not saved; rebuild them in onLoad.
]]
```

- Line 1: `--[[ <skill_id> :: <file name>`; the skill id must be the folder's skill.
- `Verified` is `in-game` (pattern taken from code that ran in TTS) or `docs-only`
  (written from the API docs, not yet seen in TTS). Promote a sample to `in-game`
  after you watch it work, and add the fact to `knowledge/verified-behaviours.md`.

## Language: MoonSharp, Lua 5.2

TTS runs MoonSharp. The tests run Lua 5.5 under `lupa`, which accepts more, so
`tests/test_registry.py` also rejects syntax MoonSharp lacks:

| Don't use | Use instead |
| --- | --- |
| `a // b` (floor division) | `math.floor(a / b)` |
| `goto` / labels | loops with flags, early `return` |
| `&`, `\|`, `~`, `<<`, `>>` (bitwise) | arithmetic, or `bit32` |
| `local x <const>` / `<close>` | plain `local` |
| `unpack(t)` (5.1 name) | `table.unpack(t)` |
| integer/float distinctions | assume every number is a double |

## Shape

1. **Self-contained.** No `require`; TTS has none. Shared helpers are copied in.
2. **Configuration on top.** UPPER_CASE constants right after the header.
3. **Handlers and the sample's offered functions are globals; internals are `local`.**
   TTS finds `onLoad`, click functions and UI callbacks by global name, and globals
   can be called from tests and `/execute`. Internal helpers are `local` so pasting
   two samples into one script can't collide. When two samples both define a handler
   (`onLoad`, `onObjectSpawn`…), merge their bodies into one.
4. **Guard against destroyed objects.** Any object captured in a `Wait` callback
   is checked for `nil` before use.
5. **Click/UI callbacks keep TTS's signatures**:
   object button `fn(obj, playerColor, altClick)`, XML UI `fn(player, value, id)`,
   context menu `fn(playerColor, position, obj)`.
6. **No mod-specific names** (`LSV`, card names) in `core` or `shared` samples.
7. **Comment the why**, the way `table.lua` does; not every line.

## Testing

`tests/test_registry.py` runs every sample under `lupa` with
`tests/lua/tts_mock.lua` + `tests/lua/tts_mock_registry.lua`:

- the file must load and run its top level without errors;
- if it defines `onLoad`, `onLoad("")` is called and the `Wait` queue flushed;
- samples with logic worth pinning get their own assertions in the same test file.

If a sample needs an API the mocks don't have, add it to
`tests/lua/tts_mock_registry.lua` (keep `tts_mock.lua` for the mod's tests).
