# Prompts

Fill-in prompts for the changes this repo sees most. Copy the block, replace the
`<…>` parts, and give it to an agent (or follow it yourself). Each prompt names
the skills it routes through and what "done" means, so any agent lands on the
same workflow.

| Prompt | Use when |
| --- | --- |
| [add-feature.md](add-feature.md) | A new in-game behaviour for an existing mod. |
| [fix-in-game-bug.md](fix-in-game-bug.md) | Something went wrong while playing in TTS. |
| [add-token.md](add-token.md) | A card should create a token (or a token is missing). |
| [add-playmat.md](add-playmat.md) | A new playmat, from a picture or a generated theme. |
| [swap-card.md](swap-card.md) | Play a different card in place of one in the cube. |
| [add-cube.md](add-cube.md) | Offer another cube in the in-game cube picker. |
| [new-lua-sample.md](new-lua-sample.md) | Capture a reusable TTS technique as a registry sample. |
| [new-mod.md](new-mod.md) | Start a different Tabletop Simulator mod in this repo. |
| [review-change.md](review-change.md) | Review a change before it goes to the user for testing. |
| [in-game-test-plan.md](in-game-test-plan.md) | Write the steps the user follows in TTS to check a change. |

All prompts start from [`router/tts-change-router`](../../router/tts-change-router/SKILL.md).
