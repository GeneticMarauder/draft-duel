# Schemas

Machine-readable contracts. Change the schema in the same commit as the code it describes.

| Schema | Describes | Checked by |
| --- | --- | --- |
| [skill-manifest.schema.json](skill-manifest.schema.json) | `SKILL.md` frontmatter | `tests/test_registry.py` |
| [card-gmnotes.schema.json](card-gmnotes.schema.json) | JSON in each card's GMNotes (`tts_save.card_note`, token notes) | review |
| [global-script-state.schema.json](global-script-state.schema.json) | `table.lua`'s `onSave` payload | review (keys must also default in `onLoad`) |
