# Core

One TTS API area per skill: how it works, what bites, and a Lua sample ready to paste.
Core skills know nothing about any mod.

| Skill | Area | Samples |
| --- | --- | --- |
| [lua-runtime](lua-runtime/SKILL.md) | MoonSharp dialect, `Wait`, coroutines | `wait_patterns.lua` |
| [state/save-and-load](state/save-and-load/SKILL.md) | `onSave` / `onLoad`, rebuilding after reload | `persistent_state.lua` |
| [objects/spawn-and-find](objects/spawn-and-find/SKILL.md) | Spawning tiles and cards, finding objects | `spawn_custom_tile.lua`, `spawn_card_from_data.lua`, `find_objects.lua` |
| [objects/decks-and-containers](objects/decks-and-containers/SKILL.md) | Dealing, returning, grouping, merge control | `deck_operations.lua`, `prevent_merging.lua` |
| [interaction/buttons-and-menus](interaction/buttons-and-menus/SKILL.md) | Object buttons, context menus | `object_buttons.lua`, `context_menus.lua` |
| [ui/xml-ui](ui/xml-ui/SKILL.md) | Screen UI in XML, driven from Lua | `seat_panel.xml`, `seat_panel.lua` |
| [players/seats-and-cameras](players/seats-and-cameras/SKILL.md) | Seats, private messages, orientation, cameras | `seat_helpers.lua` |
| [events/event-hooks](events/event-hooks/SKILL.md) | Event catalog and logger | `event_logger.lua` |
| [debug/chat-commands](debug/chat-commands/SKILL.md) | `!command` test hooks | `chat_commands.lua` |
| [lua-testing](lua-testing/SKILL.md) | `lupa` + TTS mock tests | `template_lua_test.py` |
| [build-and-install](build-and-install/SKILL.md) | Build, install, inspect saves | `save_inspect.py` |
