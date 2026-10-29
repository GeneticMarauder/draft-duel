# Naming Conventions

| Thing | Convention | Example |
| --- | --- | --- |
| Skill folder | lowercase kebab-case | `core/objects/decks-and-containers/` |
| Skill manifest | always `SKILL.md` (upper case) | `SKILL.md` |
| Skill id | layer + folder path, dot-separated | `core.objects.decks-and-containers` |
| Lua sample | snake_case `.lua` | `prevent_merging.lua` |
| XML sample | snake_case `.xml`, paired with its `.lua` | `seat_panel.xml` + `seat_panel.lua` |
| Python tool | snake_case `.py`, stdlib only, `--help` works | `save_inspect.py` |
| Prompt | kebab-case `.md` under `knowledge/prompts/` | `fix-in-game-bug.md` |
| Lua constants | `UPPER_SNAKE` | `PACK_SCALE` |
| Lua globals TTS calls | camelCase, `on` prefix for handlers | `onMatPick`, `onLoad` |
| Lua locals | camelCase | `spotIsFree` |
| XML UI ids | `<thing>_<Color>` or `<thing>_<Color>_<index>` so handlers can parse them | `matPick_White_3` |
| Card GMNotes | JSON object, see `schemas/card-gmnotes.schema.json` | `{"id":"…","cmc":3}` |
| Chat commands | `!` + lowercase word | `!draftdebug` |
| Hosted images | `<kind><nn>-<content-hash>.jpg` so TTS's URL cache never serves a stale one | `front01-1318008f450b.jpg` |
