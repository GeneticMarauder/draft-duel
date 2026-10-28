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
3. When it's your pick, the pack is in your hand. **Right-click a card → Draft this card**, or drag it
   onto your side of the table.
4. Your picks are laid out face-up in front of you, inside a hidden zone your opponent can't see.
   The discard pile in the middle is open: right-click it and choose **Search** to look through it.

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
