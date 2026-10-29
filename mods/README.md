# Mods

One folder per Tabletop Simulator mod built in this repo. A mod skill is a
**map**: features → code → state → tests → change recipe. It links to the mod's
architecture (in `AGENTS.md`) instead of repeating it, and builds on `shared`
and `core` skills.

| Mod | Skill | Code |
| --- | --- | --- |
| Draft Duel | [draft-duel/SKILL.md](draft-duel/SKILL.md) | `src/draft_duel/` |

Starting another mod? Use [`knowledge/prompts/new-mod.md`](../knowledge/prompts/new-mod.md).
