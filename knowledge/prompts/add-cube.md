# Prompt: Add a cube

**Use when:** players should be able to draft another cube in Draft Duel.
**Routes to:** `mods.draft-duel` (Cube choice row) → `shared.custom-assets`, `core.build-and-install`.

```text
Add <cube name> to Draft Duel's cube picker. Its list lives at <CubeCobra cube id | URL of an official list>.

1. Try it without code first: uv run draft-duel --cubes lsv,vintage,cubecobra:<id>
   (any CubeCobra cube works this way).
2. To make it permanent, add a CubeSource to CUBES in src/draft_duel/cubes.py with a short, stable key
   (it is saved with games: never rename a key once released) and the in-game name.
   A CubeCobra cube needs only the id. A list published elsewhere needs a parser like
   parse_mtgo_cardlist, a new `kind` in load_cube, and a test with a saved snippet of the page.
3. Add the key to DEFAULT_CUBES if it should be in every build (order = picker order; the first
   loads on the table).
4. Check the build output: every name must resolve on Scryfall; token makers in the new cube need rows
   in data/tokens.csv (add-token.md) or they get no Create menu.
5. Sheets: front sheets 1-40 hold 2,760 cards across all cubes; build_save raises if they'd overflow.
6. uv run pytest; rebuild with --push (with my OK); test plan: load fresh, Cube button, pick it, Start Draft.
```

**Done when:** the cube appears in the picker, a draft deals from it, and the sheets are pushed
(with the user's OK).
