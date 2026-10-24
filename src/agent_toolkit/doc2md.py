"""Convert DOCX/PDF/EML/etc. to Markdown.

PDF via pymupdf4llm, e-mail via agent_toolkit.eml, pandoc formats via pypandoc,
everything else via markitdown.
Prints each written .md path to stdout; errors go to stderr.
"""

import argparse
import contextlib
import sys
from pathlib import Path

PANDOC_EXT = {".docx", ".odt", ".rtf", ".html", ".htm", ".epub"}


def convert(src: Path, media: Path | None) -> str:
    ext = src.suffix.lower()
    if ext == ".pdf":
        import pymupdf4llm

        kw = {"write_images": True, "image_path": str(media)} if media else {}
        return pymupdf4llm.to_markdown(str(src), **kw)
    if ext == ".eml":
        from agent_toolkit.eml import eml_to_markdown

        return eml_to_markdown(src, media)
    if ext in PANDOC_EXT:
        import pypandoc

        args = ["--wrap=none"] + ([f"--extract-media={media}"] if media else [])
        fmt = "html" if ext == ".htm" else None  # pandoc doesn't infer html from .htm
        return pypandoc.convert_file(str(src), "gfm", format=fmt, extra_args=args)
    from markitdown import MarkItDown  # fallback: pptx, xlsx, ...

    return MarkItDown().convert(str(src)).text_content


def output_stem(src: Path, outdir: Path, used: set[Path]) -> str | None:
    """Pick the output name (without .md) for src, or None to skip it.

    `used` holds the .md paths already written in this run, so e.g. report.pdf
    and report.docx going to the same outdir don't overwrite each other.
    """
    # report.md, then report.docx.md on collision; skip if both are taken.
    for stem in (src.stem, src.name):
        if (outdir / f"{stem}.md").resolve() not in used:
            return stem
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert documents to Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
formats:
  .pdf                                    pymupdf (OCR for scanned pages: RapidOCR with the
                                          [ocr] extra, else Tesseract if installed)
  .docx .odt .rtf .html .htm .epub        pandoc
  .eml                                    e-mail: YAML frontmatter (from, to, date,
                                          attachments) + body; --images saves
                                          attachments and inline images
  anything else (.pptx .xlsx .xls ...)    markitdown

output:
  Writes <name>.md per input; if two inputs share a name, the second becomes
  <name>.<ext>.md. Prints each written path on stdout, one per line;
  diagnostics and errors go to stderr. Exit code 1 if any file failed.

examples:
  doc2md report.pdf                       # -> report.md next to the input
  doc2md *.docx -o notes/                 # batch into notes/
  doc2md slides.pptx --images -o out/     # images to out/slides_media/, linked relatively
""",
    )
    ap.add_argument("files", nargs="+", type=Path, help="input files")
    ap.add_argument("-o", "--outdir", type=Path, help="output dir (default: next to input)")
    ap.add_argument(
        "--images",
        action="store_true",
        help="save images (and e-mail attachments) to <name>_media/",
    )
    a = ap.parse_args()

    failed = 0
    used: set[Path] = set()
    for src in a.files:
        outdir = a.outdir or src.parent
        outdir.mkdir(parents=True, exist_ok=True)
        stem = output_stem(src, outdir, used)
        if stem is None:
            failed += 1
            print(f"doc2md: {src}: skipped, output name already used", file=sys.stderr)
            continue
        dst = outdir / f"{stem}.md"
        used.add(dst.resolve())
        # Relative media dir + cwd=outdir so image links resolve from the .md file.
        media = Path(f"{stem}_media") if a.images else None
        abs_src = src.resolve()
        try:
            # Converters print diagnostics to stdout; keep stdout for result paths only.
            with contextlib.chdir(outdir), contextlib.redirect_stdout(sys.stderr):
                md = convert(abs_src, media)
            dst.write_text(md, encoding="utf-8")
            print(dst)
        except Exception as e:
            failed += 1
            print(f"doc2md: {src}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
