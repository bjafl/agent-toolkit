# agent-toolkit

CLI tools for AI agents. One Python package, one command per tool.

## Install

```sh
uv tool install --editable .   # puts every command on PATH, code changes apply immediately
```

Re-run the install after adding a new command or dependency.

During development, from inside the repo: `uv run <command>`.

## Tools

| Command | Description |
|---------|-------------|
| _none yet_ | |

## Conventions

- Result on stdout, logs and progress on stderr.
- Useful `--help` — it's how agents learn the tool.
- `--json` for structured output where the result is data.
- Non-zero exit code with a clear message on failure.
- Import heavy dependencies inside `main()`, not at module top level.

## Adding a tool

1. Create `src/agent_toolkit/<tool>.py` with a `main()` function.
2. Register it under `[project.scripts]` in `pyproject.toml`.
3. `uv add <deps>`, then re-run `uv tool install --editable .`.
4. Add a row to the table above.
