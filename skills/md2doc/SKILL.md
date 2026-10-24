---
name: md2doc
description: Export Markdown to PDF or Word (DOCX) with the md2doc CLI. Use when the user wants a document, report, letter, notes or a Markdown file delivered as PDF or DOCX, or asks to "make a PDF/Word file" of something you wrote.
---

# md2doc

Converts Markdown files to PDF and/or DOCX. A4 by default. No LaTeX or Word needed.

## Running it

Use `md2doc` if it is on PATH (`command -v md2doc`). Otherwise run it from this plugin's project, two levels up from this skill's base directory, without changing the working directory:

```sh
uv run --project <skill base dir>/../.. md2doc <files...>
```

## Usage

```sh
md2doc notes.md                           # -> notes.pdf next to the input
md2doc notes.md --to docx --to pdf        # both formats
md2doc *.md --to docx -o out/ --lang nb   # batch, Norwegian
md2doc report.md --to docx --template company.docx
```

`md2doc --help` has the full option list.

- **stdout** is only the written file paths, one per line.
- **stderr** carries pandoc/typst warnings and per-file errors (`md2doc: <file> -> <format>: <reason>`).
- **Exit code** 1 if any conversion failed; the others still run.

## Writing Markdown for export

When you write the Markdown yourself, it is worth getting these right:

- **Frontmatter** sets the title block and language:
  ```yaml
  ---
  title: "Møtereferat"
  subtitle: "Styremøte 24. oktober"
  author: "Kari Nordmann"
  date: "2026-10-24"
  lang: nb
  ---
  ```
  With `title` in frontmatter, don't repeat it as a `# Heading` in the body. `lang` gives correct hyphenation and localised labels (`nb`, `nn`, `en`, ...). `--lang` overrides it.
- **Images**: relative paths resolve from the Markdown file. Remote (`https://`) images are not fetched for PDF: download them first.
- **Tables**: pipe tables work in both formats. Keep them narrow, because wide tables overflow on A4 portrait.

## Styling

- `--template style.docx`: a Word *reference doc*. Its styles (Normal, Heading 1, ...), fonts and page setup are used. Making one: run `md2doc x.md --to docx`, edit the styles in Word or LibreOffice, then save it as the template.
- `--template style.typ`: a pandoc typst template (`pandoc -D typst` prints the default).
- Each template only applies to the format matching its extension.

## Pitfalls

- `doc2md` output has e-mail frontmatter (`subject`, `from`, `date` …). Only `date` is shown in the title block. Edit the frontmatter (e.g. add `title:`) if the result should look like a document.
- Existing output files are overwritten without asking.
