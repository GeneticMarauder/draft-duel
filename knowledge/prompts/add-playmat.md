# Prompt: Add a playmat

**Use when:** the user wants a new playmat.
**Routes to:** `mods.draft-duel` (Playmats row) → `shared.custom-assets`.

```text
Add a playmat to the Draft Duel mod: <a picture at PATH | a generated theme described as …>.

Picture: copy it into playmats/ named as it should appear (Black_Clover.png -> "Black Clover").
  Only pictures I'm happy to publish: the repo is public. Wide (~2.75:1) fills the mat.
Generated theme: add it to THEMES in src/draft_duel/playmats.py — seeded, no copyrighted art.

Then: uv run pytest (test_playmats_*, test_pictures_in_the_playmats_folder_become_mats),
rebuild with uv run draft-duel --push, and give me a test plan:
load fresh, press "Playmat: …", pick the new mat, check it covers my half.
```

**Done when:** tests pass and the sheets are pushed (with the user's OK).
