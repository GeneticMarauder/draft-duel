# Draft Duel (Tabletop Simulator)

A two-player cube draft for Tabletop Simulator. Pick the cube at the table before you start:

- **LSV Cube** — [LSV's powered cube](https://cubecobra.com/cube/list/LSVCube) on CubeCobra.
- **MTGO Vintage Cube** — the latest [Magic Online Vintage Cube](https://www.mtgo.com/vintage-cube-cardlist)
  (each build reads MTGO's official list, so the Holiday edition arrives with the next rebuild).

## The format

Each pack, the starting player (S) and the other player (O) take turns like this:

| Step | Who | Pack | Action |
|---|---|---|---|
| 1 | S | draw 5 from the cube | take 1 |
| 2 | O | top up to 5 | take 1 |
| 3 | O | top up to 5 | take 1 |
| 4 | S | top up to 5 | take 1; the other 4 are discarded face-up |

The starting player alternates every pack. 24 packs gives each player 48 cards.

## Playing

1. The host loads **Draft Duel** from *Games → Save & Load*. Your opponent just joins the game.
2. One player sits at **White** and the other at **Red**. To change the cube, press **Cube: …**
   (bottom right) and choose one; either player can, until the draft starts. Then either of them
   presses **Start Draft**.
   To practise alone, leave a seat empty: a bot drafts random cards for any seat that is empty at Start Draft.
3. When it's your pick, your 5 pack cards are laid out large in front of you. Click **Draft** under
   the card you want (or right-click it → **Draft this card**). Your opponent sees only card backs.
4. Your picks go into a grid below the pack, invisible to your opponent. The discard pile in the
   middle is open: right-click it and choose **Search** to look through it.
5. When the draft ends you switch to **deck building**: your deck sits in the middle of the table in
   columns by mana value (lands last), and your sideboard is a smaller area to your right; drag
   cards between them. Add basic lands with the land buttons in the bottom panel (left-click adds
   one, right-click removes one). The panel also shows your deck and sideboard counts.
6. When your deck is done (at least 40 cards), press **Ready to play**. Your deck becomes a face-down
   library on your right and your sideboard a pile beside it (hidden from your opponent). Once both
   players are ready, the libraries are shuffled, everyone draws 7, life counters are set to 20 and a
   random player is chosen to go first.
7. Hold **Alt** while hovering a card for a large preview. **Reset view** (bottom right) re-frames your camera.

If a private card ever shows up for your opponent, type `!hide` in chat to re-hide every private card.

Testing helpers (type in chat): `!draftauto 10` makes 10 random picks for you; `!draftdebug` prints
the table and zone geometry.

## Building and updating the cubes

```bash
uv run draft-duel --push
```

This downloads each cube's current list (CubeCobra for the LSV Cube, MTGO's official page for the
Vintage Cube), gets card data and images from Scryfall, renders the card sheets into `sheets/`, pushes
them to GitHub (Tabletop Simulator loads the images from there), and writes one save, **Draft Duel**,
to `dist/` and to your Tabletop Simulator Saves folder.

`--cubes` picks which cubes the save offers; the first is on the table when it loads
(default `lsv,vintage`). Any CubeCobra cube works too: `--cubes lsv,vintage,cubecobra:<cube id>`.
To add a cube permanently, see [`knowledge/prompts/add-cube.md`](knowledge/prompts/add-cube.md).

## Development

```bash
uv sync
uv run pytest
```

The tests run the real in-game Lua against a mock of the Tabletop Simulator API, including a full
48-pick draft and a save/reload partway through. See `AGENTS.md` for the architecture.

### Skills registry

The repo doubles as a registry for Tabletop Simulator modding work, laid out like
[oracle/Fusion-Setup-Configuration-Registry](https://github.com/oracle/Fusion-Setup-Configuration-Registry):

| Folder | What's there |
| --- | --- |
| [`router/`](router/) | Where every change starts: classify it, route it, plan the in-game test. |
| [`mods/`](mods/) | Feature map of this mod: code, saved state and tests per feature. |
| [`shared/`](shared/) | Reusable patterns: card privacy, table layout, rules engine, tokens, images. |
| [`core/`](core/) | One TTS API area per skill, each with documented, ready-to-paste Lua samples. |
| [`knowledge/`](knowledge/) | What TTS really does (verified in game), API links, prompt templates. |
| [`schemas/`](schemas/), [`governance/`](governance/) | Contracts, standards, checklists, templates. |

[`SKILLS_TAXONOMY.md`](SKILLS_TAXONOMY.md) lists every skill and Lua sample.

Card images © Wizards of the Coast; card data from Scryfall and CubeCobra. This is an unofficial fan project.
