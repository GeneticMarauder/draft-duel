# AGENTS.md - lsv-duel-draft

Policy layer + architecture for this repo. This file is the source of truth;
`CLAUDE.md` just imports it. Keep it current as the code evolves.

## Ground truth first

Before editing: inspect the actual repo tree and align to files that exist today.
Create new modules only when the task clearly requires them. Treat any
architecture described here as the target, not proof it already exists.

## Tooling — uv only (enforced by a global hook)

- Add a dependency:      `uv add <package>`   (dev: `uv add --group dev <package>`)
- Install / sync:        `uv sync`
- Run something:         `uv run <cmd>`  (e.g. `uv run pytest`)
- **Never** `pip install`, **never** `python -m venv` — the guard hook blocks both.
- Commit `uv.lock`.

## Structure

- src-layout: code in `src/lsv_duel_draft/`, tests in `tests/`.
- Slice by concern (`config`, `io`, `services`, `models`) rather than one module.

## Shared code — reuse agent-core, don't reinvent

Deterministic building blocks (config/`.env` loading, csv/json <-> Pydantic I/O,
logging) come from **agent-core**. Import them instead of re-writing:

```python
from agent_core.config import BaseConfig
from agent_core.io import read_table, validate_records, write_records
from agent_core.utils import get_logger
```

Only add the LLM extra (`agent-core[llm]`) if this project calls an LLM at runtime.

## Definition of done

1. `uv run pytest` passes.
2. Public functions have docstrings and type hints.
3. Ask before adding any new external dependency.

## Architecture

<!-- Describe this project's real pipeline / modules here as it takes shape. -->
