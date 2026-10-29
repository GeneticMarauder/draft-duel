# TTS Save File Format (the parts mods touch)

A save is one JSON file in `Documents/My Games/Tabletop Simulator/Saves/`
(on this machine possibly under `OneDrive/Documents`). `tts_save.build_save`
writes one; `core/build-and-install/scripts/save_inspect.py` reads one.

## Top level

| Key | Meaning |
| --- | --- |
| `SaveName`, `GameMode`, `Date`, `Note`, `Rules` | Shown in *Save & Load*; `Note` appears in the Notebook. |
| `Table`, `Sky` | `Table_RPG` here: felt top y ≈ 0.96, bounds 64 x 43 (verified). |
| `Gravity`, `PlayArea` | 0..1. |
| `Hands` | `{Enable, DisableUnused, Hiding}`. |
| `LuaScript` | The **Global** script, as one string. Here: a JSON header + `draft_core.lua` + `table.lua`. |
| `LuaScriptState` | The string `onSave` returned last time. Empty for a fresh build. |
| `XmlUI` | The Global UI (`ui.xml` with generated pickers). |
| `CustomUIAssets` | `[{Type: 0, Name, URL}]` images the XML UI references by `Name`. |
| `ObjectStates` | Every object on the table. |

## Objects

Common fields: `GUID` (6 hex chars, unique per save), `Name` (the object type:
`Card`, `CardCustom`, `Deck`, `Custom_Tile`, `HandTrigger`, `Counter`…),
`Transform` (`posX/Y/Z`, `rotX/Y/Z`, `scaleX/Y/Z`), `Nickname`, `Description`,
`GMNotes`, `Memo`, `Tags`, `Locked`, `LuaScript`, `LuaScriptState`, `XmlUI`.

Cards: `CardID` (`sheetId * 100 + index`) and `CustomDeck` `{ "<sheetId>": {FaceURL, BackURL,
NumWidth, NumHeight, BackIsHidden, UniqueBack, Type} }`. Multi-state objects
(double-faced cards) carry `States: { "2": {…object…} }`.

Decks: `DeckIDs` (the CardIDs, in the same order as `ContainedObjects`), `CustomDeck` for every sheet
used, `ContainedObjects` (one full card object each).

Hand zones: `Name: "HandTrigger"`, `FogColor` = the seat color, a Transform
whose scale is the zone size.

## Embedding data for the script

Python computes data, Lua reads it. The builder prepends globals to the Global script:

```lua
BASIC_LANDS_JSON = [==[ ...json... ]==]
TOKENS_JSON = [==[ ...json... ]==]
MATS_JSON = [==[ ...json... ]==]
CUBES_JSON = [==[ [{"key": "lsv", "name": "LSV Cube", "count": 515}, ...] ]==]
CUBE_DECKS = { ["lsv"] = [==[ ...deck object json... ]==], ["vintage"] = [==[ ... ]==] }
```

`[==[ … ]==]` long strings need no escaping; `tts_save.lua_long_string` adds `=` signs until the
text can't close the string early. The script decodes the small ones in `onLoad` with `JSON.decode`;
`CUBE_DECKS` stay strings and go straight to `spawnObjectJSON` when players switch cubes, so a
1–2 MB save loads without decoding the other cubes. Error line numbers
in TTS count these header lines.

## Caching

TTS caches every image URL it has loaded (`Documents/My Games/Tabletop Simulator/Mods/Images`).
Changing an image without changing its URL shows the old one — hence
content-hashed file names (`front01-<hash>.jpg`).
