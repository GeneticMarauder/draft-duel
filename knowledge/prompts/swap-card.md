# Prompt: Swap a cube card

**Use when:** the group plays a different card in place of one in the CubeCobra list.
**Routes to:** `mods.draft-duel` (Cube, card data row).

```text
In Draft Duel, play <replacement card> instead of <cube card>.

1. Add "<cube card>": "<replacement card>" to CARD_SWAPS in src/draft_duel/sources.py
   (swaps apply to every cube that contains the card).
2. If the replacement needs script support (like Booster Tutor), plan that as a feature
   (knowledge/prompts/add-feature.md); tokens it makes go in data/tokens.csv.
3. uv run pytest (test_swap_cards_replaces_by_name_in_place), then
   uv run draft-duel --push and check the build prints the swap.
```

**Done when:** the build prints the swap and the sheets are pushed (with the user's OK).
