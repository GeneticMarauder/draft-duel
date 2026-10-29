# LSV Cube Duel Draft (Tabletop Simulator)

A two-player draft of [LSV's powered cube](https://cubecobra.com/cube/list/LSVCube) for Tabletop Simulator.

## The format

Each pack, the starting player (S) and the other player (O) take turns like this:

| Step | Who | Pack | Action |
|---|---|---|---|
| 1 | S | draw 4 from the cube | take 1 |
| 2 | O | top up to 4 | take 1 |
| 3 | O | top up to 4 | take 1 |
| 4 | S | top up to 4 | take 1; the other 3 are discarded face-up |

The starting player alternates every pack. 24 packs gives each player 48 cards.

## Playing

1. The host loads **LSV Cube Duel Draft** from *Games → Save & Load*. Your opponent just joins the game.
2. One player sits at **White** and the other at **Red**. Either of them presses **Start Draft**.
   To practise alone, leave a seat empty: a bot drafts random cards for any seat that is empty at Start Draft.
3. When it's your pick, your 4 pack cards are laid out large in front of you. Click **Draft** under
   the card you want (or right-click it → **Draft this card**). Your opponent sees only card backs.
4. Your picks go into a grid below the pack, invisible to your opponent. The discard pile in the
   middle is open: right-click it and choose **Search** to look through it.
5. When the draft ends you switch to **deck building**: your cards are sorted into columns by mana
   value, with lands last. Your deck is on your left and your sideboard on your right; drag cards
   between them. Drag basic lands out of the land bags along your edge; drop a basic on the
   sideboard to remove it. The panel at the bottom shows your deck and sideboard counts.
6. Hold **Alt** while hovering a card for a large preview. **Reset view** (top right) re-frames your camera.

Testing helpers (type in chat): `!draftauto 10` makes 10 random picks for you; `!draftdebug` prints
the table and zone geometry.

## Building and updating the cube

```bash
uv run lsv-duel-draft --push
```

This downloads the current list from CubeCobra, gets card data and images from Scryfall, renders the
card sheets into `sheets/`, pushes them to GitHub (Tabletop Simulator loads the images from there),
and writes the save to `dist/` and to your Tabletop Simulator Saves folder.

Use `--cube <CubeCobra id>` to build a different cube.

## Development

```bash
uv sync
uv run pytest
```

The tests run the real in-game Lua against a mock of the Tabletop Simulator API, including a full
48-pick draft and a save/reload partway through. See `AGENTS.md` for the architecture.

Card images © Wizards of the Coast; card data from Scryfall and CubeCobra. This is an unofficial fan project.
