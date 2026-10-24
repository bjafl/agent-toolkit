# agent-toolkit — agent instructions

CLI tools for AI agents, usable by humans too. The repo is two things at once:

- a **Python package** (`src/agent_toolkit/`, one module and one `[project.scripts]` entry per tool)
- a **Claude Code plugin** (`.claude-plugin/`, one `skills/<tool>/SKILL.md` per tool)

## Commands

```sh
uv sync                    # set up .venv with dev deps
uv run pytest              # tests, must pass
uv run ruff check .        # lint, must pass
uv run ruff format .       # format
uv run <tool> --help       # run a tool from the repo
claude plugin validate .   # check plugin + marketplace manifests
```

## Tool conventions

- Core logic in a plain function with no CLI or I/O policy (e.g. `doc2md.convert`); `main() -> int` is a thin argparse adapter.
- Result on stdout, diagnostics and errors on stderr. Wrap third-party calls that print in `contextlib.redirect_stdout(sys.stderr)`.
- Prefer writing files and printing their paths over dumping large content on stdout.
- Non-zero exit code on failure; error lines as `<tool>: <subject>: <reason>`.
- `--help` has an `epilog` with `examples:`. Agents copy examples.
- `--json` when the result is structured data.
- Never prompt interactively; no colour or spinners.
- Import heavy dependencies inside functions, not at module top level, so `--help` stays fast.

## Adding a tool

1. `src/agent_toolkit/<tool>.py` with `main() -> int`.
2. Register `<tool> = "agent_toolkit.<tool>:main"` under `[project.scripts]`.
3. `uv add <deps>`.
4. `skills/<tool>/SKILL.md`: the frontmatter `description` says *when* to use the tool (it is what triggers the skill); the body gives usage, the stdout/stderr contract and pitfalls. Follow `skills/doc2md/SKILL.md`.
5. Tests in `tests/test_<tool>.py`. `tests/test_contract.py` checks steps 2 and 4 and the help epilog for every tool.
6. Add a row to the tools table in `README.md`.

Bump `version` in both `pyproject.toml` and `.claude-plugin/plugin.json` together.
