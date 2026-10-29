# Skill Design Standards

A **skill** is one folder with a `SKILL.md` manifest that teaches an agent one
responsibility in Tabletop Simulator (TTS) modding. Skills are how work is
coordinated here: the router picks skills, skills point at samples, samples are
the code you copy.

## Layers

| Layer | Holds | Example |
| --- | --- | --- |
| `router` | Entry points that classify a request and pick the skills to use. | `router.tts-change-router` |
| `core` | One TTS API area each: how it works, its traps, a ready-to-paste Lua sample. | `core.state.save-and-load` |
| `shared` | Gameplay patterns built from several core areas, reusable by any mod. | `shared.card-privacy` |
| `mods` | A specific mod's map: features, code anchors, state, tests, change recipes. | `mods.draft-duel` |
| `knowledge` | Facts and prompts: verified TTS behaviours, API links, prompt templates. | `knowledge/verified-behaviours.md` |
| `schemas` | Machine-readable contracts (manifest, GMNotes, script state). | `schemas/skill-manifest.schema.json` |
| `governance` | These standards, checklists and templates. | this file |

Dependencies point downward only: `router` → `mods` → `shared` → `core`.
A core skill never depends on a shared skill or a mod.

## Folder shape

```text
<layer>/<area>/<skill-name>/
  SKILL.md          manifest (frontmatter) + guide
  scripts/          ready-to-use samples: *.lua, *.xml, or *.py tools
  references/       longer reference notes the guide links to (optional)
```

Single-level skills (`core/lua-runtime/`) are fine when the area has one skill.

## Manifest

Every `SKILL.md` starts with YAML frontmatter that matches
[`schemas/skill-manifest.schema.json`](../schemas/skill-manifest.schema.json).
Copy [`templates/SKILL.template.md`](templates/SKILL.template.md).

| Field | Rule |
| --- | --- |
| `skill_id` | `<layer>.<path-with-dots>`, exactly the folder path (`core/state/save-and-load` → `core.state.save-and-load`). |
| `name` | Short title. |
| `description` | One sentence: what it does and **when to use it** (agents choose skills from this line). |
| `layer` | `router`, `core`, `shared` or `mods`. |
| `type` | `orchestration`, `reference`, `pattern`, `feature-map` or `tooling`. |
| `execution_mode` | `advisory` (guidance only), `assisted` (produces code/plans for review) or `automated` (runs tools). |
| `version` | Semver; bump minor when guidance changes, major when a sample's public functions change. |
| `verified` | `in-game` if every sample was seen working in TTS, otherwise `docs-only`. |
| `depends_on` | Other `skill_id`s this skill builds on (may be empty). |
| `samples` | Paths of this skill's `scripts/` files, relative to the skill folder. |
| `side_effects` | What using it changes (files, the TTS Saves folder, git pushes). Empty for pure guidance. |

## Body sections

In this order; skip a section only when it has nothing to say.

1. **Purpose** — one paragraph.
2. **When to use** — the requests or symptoms that should land here.
3. **How it works** — the mental model, short.
4. **Samples** — a table: file, what it gives you, how to drop it in.
5. **Gotchas** — traps, each one tagged `(verified)` or `(docs)`.
6. **Testing** — how to cover it under `lupa` + the mock, and what only TTS can show.
7. **Related** — links to neighbouring skills and knowledge.

## Design rules

1. One responsibility per skill. If the guide needs two "How it works" sections, split it.
2. Samples are the deliverable. Guidance explains the sample; it doesn't replace it.
3. Every sample follows [lua-sample-standards.md](lua-sample-standards.md) and is
   smoke-tested by `tests/test_registry.py`.
4. Claims about TTS behaviour are tagged `(verified)` only if seen in game; record
   them in [`knowledge/verified-behaviours.md`](../knowledge/verified-behaviours.md).
5. Mod-specific rules live under `mods/<mod>/`, never in `core` or `shared`.
6. Don't duplicate the mod's architecture: `AGENTS.md` owns it, mod skills link to it.
7. No secrets, tokens or personal data in samples, saves or docs.
