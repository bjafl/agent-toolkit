---
name: doc2md
description: Convert documents (PDF, DOCX, ODT, RTF, HTML, EPUB, PPTX, XLSX, ...) to Markdown with the doc2md CLI. Use when the user asks to convert, read, summarize or extract text from a document file that is not already plain text, or when you need to read a binary office/PDF file yourself.
---

# doc2md

Converts documents to Markdown files. One `.md` per input, written next to the input or into `-o <dir>`.

## Running it

Use `doc2md` if it is on PATH (`command -v doc2md`). Otherwise run it from this plugin's project, two levels up from this skill's base directory, without changing the working directory:

```sh
uv run --project <skill base dir>/../.. doc2md <files...>
```

The first `uv run` creates the plugin's environment and can take a while.

## Usage

```sh
doc2md report.pdf                     # -> report.md next to the input
doc2md a.docx b.pdf -o out/           # batch into out/
doc2md slides.pptx --images -o out/   # also extract images to out/slides_media/
```

`doc2md --help` has the full option list.

- **stdout** is only the written `.md` paths, one per line. Read those files afterwards; don't expect the Markdown on stdout.
- **stderr** carries converter diagnostics and per-file errors (`doc2md: <file>: <reason>`).
- **Exit code** 1 if any file failed; the other files are still converted.
- Use `--images` only when the images matter. Image links in the `.md` are relative to the `.md` file.

## Engines

| Input | Engine | Notes |
|---|---|---|
| `.pdf` | pymupdf | Keeps headings, tables and reading order. Scanned pages are OCR'd: RapidOCR if installed with the `ocr` extra (stderr says `Using RapidOCR`), otherwise Tesseract, which is slower and less accurate. |
| `.docx .odt .rtf .html .htm .epub` | pandoc | Highest fidelity. Complex formatting can come out as inline HTML. |
| everything else | markitdown | `.pptx` gives one section per slide, `.xlsx` and `.xls` one table per sheet, `.msg` the Outlook e-mail. Plain text formats (`.csv`, `.json`, `.xml`) also work. Audio, images and YouTube are not installed. |

## Pitfalls

- **Large outputs**: a long PDF can produce a very large `.md`. Check the size (`wc -c`) before reading the whole file, and read it in parts if needed.
- **Same base name**: if `report.pdf` and `report.docx` go to the same output dir, the first becomes `report.md` and the second `report.docx.md`. Take the names from stdout rather than guessing them.
- **Existing files**: an existing `<name>.md` from an earlier run is overwritten without asking.
- **Poor OCR result**: if stderr says `Using Tesseract`, suggest installing the `ocr` extra (see README).
