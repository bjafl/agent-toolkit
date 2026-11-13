---
name: learn2md
description: Fetch Microsoft Learn (learn.microsoft.com) articles as clean Markdown with the learn2md CLI, one page or a whole doc set from its toc.json. Use when the user gives a learn.microsoft.com URL to read, summarize or quote exactly, when building a local reference copy of a Microsoft docs section, or when exact names, values and XML/code samples from Microsoft documentation are needed.
---

# learn2md

Downloads Learn pages, keeps only the article (`<main>` → `div.content`, no navigation or "Ask Learn" chrome) and writes Markdown. The Markdown is the page as published, so code samples, table values and names are exact; prefer it to a PDF export or a summarising fetch.

## Running it

Use `learn2md` if it is on PATH (`command -v learn2md`). Otherwise run it from this plugin's project, two levels up from this skill's base directory, without changing the working directory:

```sh
uv run --project <skill base dir>/../.. learn2md <args>
```

## Usage

```sh
learn2md https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/microsoft-windows-deployment-deviceform -o docs/
learn2md URL1 URL2 -o docs/                                  # one .md per URL
learn2md --toc https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/toc.json -o unattend/
learn2md --toc toc.json --base https://learn.microsoft.com/en-us/<doc-root>/ -o docs/   # toc from a file
```

`learn2md --help` has the full option list.

- **stdout**: only the written paths, one per line (in toc mode also `TOC.md`). Read those files afterwards.
- **stderr**: errors as `learn2md: <url>: <reason>`. Exit code 1 if any page failed; the others are still written.
- Each file starts with `# <title>`, then `Source: <url> · Last updated <date>` (and `Path:` in toc mode), then the body.
- Links keep their original `href`. Relative ones are slugs of other pages in the same doc set.

## Whole doc sets (`--toc`)

Every Learn doc set has a navigation tree at `<doc-root>/toc.json`, for example `https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/toc.json`. Nodes carry `toc_title`, optional `href` and `children`. An `href` is a slug appended to the doc root (the toc URL's folder, or `--base`): `<doc-root>/<href>`. Find a doc root by opening any article of the set and removing the last path segment.

- Layout: a directory per node with children (`_index.md` is the node's own page), `<title>.md` for leaves, hierarchy as in the toc. Nodes without `href` are directories only.
- `TOC.md` lists `title -> file | url-slug` for every node. Use it to find a page; `grep -i <name> TOC.md`.
- Raw `<main>` HTML is cached in `--cache` (default `<out>/.cache`), so converting again needs no network. `--refresh` downloads again.
- Fetching is polite: `--workers 4` by default, short pause, retries with backoff, generic User-Agent. A large set (1000+ pages) takes a few minutes; run it in the background and do not raise `--workers` much.

## Pitfalls

- **Source errors are reproduced**: some pages have a wrong "Parent Hierarchy" line (copy-paste from a sibling), or titles with a stray `(microsoft-windows-...)` suffix. In toc mode trust the `Path:` line and `TOC.md`, which come from the toc.
- **`\*`**: literal asterisks in prose are escaped. Pages that write `**true**` as plain text show `\*\*true\*\*`; inline code is not escaped.
- **Tables without header**: Learn tables without `<thead>` get an empty header row (`|  |  |`), since GFM requires one. Cell content with several paragraphs is joined with `<br>`.
- **Alert boxes in tables**: inside a table cell a NOTE/Caution box is rendered as bold label plus text, not as a blockquote, to keep the row intact.
- **Pages that are not articles** (landing pages, API refs with other layouts) may come out nearly empty; check the file size.
- **Large pages**: a single page can be hundreds of KB. `grep -n` and read with offset and limit.
