# lsv-duel-draft

## Setup

```bash
uv sync
```

## Run

```bash
uv run python -m lsv_duel_draft      # or your entry point
uv run pytest
```

## Notes

- uv-managed (never `pip`). Deps in `pyproject.toml`, locked in `uv.lock`.
- Shared helpers come from [agent-core](https://github.com/jphittell/agent-core).
- See `AGENTS.md` for architecture and working rules.
