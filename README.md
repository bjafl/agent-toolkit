# agent-toolkit

CLI tools for AI agents, usable by humans too. Each tool is a command on PATH and a Claude Code skill that tells Claude when to use it.

## Tools

| Command | Description |
|---------|-------------|
| `doc2md` | Convert PDF, DOCX, ODT, HTML, EPUB, PPTX, XLSX … to Markdown. |

Run `<command> --help` for usage and examples.

## Install

**Commands on PATH** (for you, scripts and any agent with a shell):

```sh
uv tool install --editable .     # from a clone; code changes apply immediately
uv tool install git+https://github.com/bjafl/agent-toolkit   # without a clone
```

Add the `ocr` extra for better OCR of scanned PDFs (RapidOCR, about 100 MB extra):
`uv tool install --editable '.[ocr]'`.

Re-run the install after a new command or dependency is added. Commands land in `~/.local/bin`.

**Claude Code plugin** (adds the skills), typed at the Claude Code prompt:

```
/plugin install agent-toolkit --marketplace bjafl/agent-toolkit
```

The repository is private, so both installs need GitHub access set up locally. The skills use the command on PATH if present and otherwise fall back to `uv run` inside the plugin.

## Development

See [AGENTS.md](AGENTS.md) for conventions and how to add a tool.

## License

MIT for this repository's code. Dependencies keep their own licenses: notably PyMuPDF (AGPL-3.0) and pandoc, bundled via pypandoc-binary (GPL-2.0).
