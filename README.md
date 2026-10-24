# agent-toolkit

CLI tools for AI agents, usable by humans too. Each tool is a plain command (stdout for results, stderr for diagnostics, meaningful exit codes) and a Claude Code skill that tells Claude when to use it.

## Tools

| Command | Description |
|---------|-------------|
| `doc2md` | Convert documents and e-mails to Markdown: PDF, DOCX, ODT, RTF, HTML, EPUB, PPTX, XLSX, EML, MSG … |

```sh
doc2md report.pdf                    # -> report.md next to the input
doc2md mail.eml --images -o notes/   # e-mail with frontmatter; attachments to notes/mail_media/
```

Run `<command> --help` for all options and examples.

## Install

Requires [uv](https://docs.astral.sh/uv/).

**Try without installing:**

```sh
uvx --from git+https://github.com/bjafl/agent-toolkit doc2md report.pdf
```

**Commands on PATH** (for you, scripts and any agent with a shell):

```sh
uv tool install git+https://github.com/bjafl/agent-toolkit
uv tool install 'agent-toolkit[ocr] @ git+https://github.com/bjafl/agent-toolkit'   # + better OCR
```

Commands land in `~/.local/bin`. Update with `uv tool upgrade agent-toolkit`.

The `ocr` extra adds RapidOCR for scanned PDFs (about 100 MB). Without it, scanned pages fall back to Tesseract if it is installed.

**Claude Code plugin** (adds the skills), typed at the Claude Code prompt:

```
/plugin install agent-toolkit --marketplace bjafl/agent-toolkit
```

The skills use the command on PATH if present and otherwise fall back to `uv run` inside the plugin, so the plugin works on its own as long as uv is installed.

## Development

```sh
git clone https://github.com/bjafl/agent-toolkit && cd agent-toolkit
uv sync
uv tool install --editable '.[ocr]'   # commands on PATH, code changes apply immediately
uv run pytest
```

See [AGENTS.md](AGENTS.md) for conventions and how to add a tool.

## License

MIT for this repository's code. Dependencies keep their own licenses: notably PyMuPDF (AGPL-3.0) and pandoc, bundled via pypandoc-binary (GPL-2.0).
