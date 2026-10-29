# Prompt: Add a token

**Use when:** a cube card should create a token, or a token is missing or wrong.
**Routes to:** `mods.draft-duel` (Tokens row) → `shared.counters-and-tokens`.

```text
Make <cube card name> create the token <token name, P/T, colors, type, rules text>
in the Draft Duel mod.

1. Add or update the row in src/draft_duel/data/tokens.csv: one row per token;
   "Made by (cube cards)" lists cube card names separated by ";" (DFCs as "Front // Back");
   fill the Scryfall ID and image URL(s) of the token printing.
2. If only one may exist on the table, add it to UNIQUE_TOKENS in table.lua.
3. uv run pytest (test_bundled_token_list_parses, test_makers_match_cube_cards_by_any_face_name).
4. Rebuild with uv run draft-duel --push (token sheets change) and check the build
   output doesn't list the maker as no longer in the cube.
5. Test plan: start a game with the maker in play, right-click it, Create <token>.
```

**Done when:** tests pass, the build links the maker, and the sheets are pushed
(with the user's OK).
