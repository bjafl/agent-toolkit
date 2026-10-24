"""Convert DOCX/PDF/etc. to Markdown.

PDF via pymupdf4llm, pandoc formats via pypandoc, everything else via markitdown.
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
    if ext in PANDOC_EXT:
        import pypandoc

        args = ["--wrap=none"] + ([f"--extract-media={media}"] if media else [])
        return pypandoc.convert_file(str(src), "gfm", extra_args=args)
    from markitdown import MarkItDown  # fallback: pptx, xlsx, ...

    return MarkItDown().convert(str(src)).text_content


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert documents to Markdown.")
    ap.add_argument("files", nargs="+", type=Path, help="input files")
    ap.add_argument("-o", "--outdir", type=Path, help="output dir (default: next to input)")
    ap.add_argument("--images", action="store_true", help="extract images to <name>_media/")
    a = ap.parse_args()

    failed = 0
    for src in a.files:
        outdir = a.outdir or src.parent
        outdir.mkdir(parents=True, exist_ok=True)
        dst = outdir / f"{src.stem}.md"
        # Relative media dir + cwd=outdir so image links resolve from the .md file.
        media = Path(f"{src.stem}_media") if a.images else None
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
