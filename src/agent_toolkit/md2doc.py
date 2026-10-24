"""Convert Markdown to PDF or DOCX.

PDF via pandoc's typst writer and the typst compiler (no LaTeX needed), DOCX via
pandoc. A4 by default; language from the `lang` frontmatter field or --lang.
Prints each written path to stdout; errors go to stderr.
"""

import argparse
import contextlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

FORMATS = ("pdf", "docx")
TEMPLATE_SUFFIX = {"pdf": ".typ", "docx": ".docx"}
# A4 with 2.5 cm margins, in twentieths of a point.
DOCX_A4 = (
    '<w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417"'
    ' w:header="708" w:footer="708" w:gutter="0"/>'
)
URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def to_pdf(src: Path, dst: Path, lang: str | None, template: Path | None) -> None:
    import pypandoc
    import typst

    # typst resolves image paths against its root, not the source file, so make
    # local image paths absolute and compile with / as root.
    ast = json.loads(pypandoc.convert_file(str(src), "json"))
    _absolutize_images(ast, src.parent)
    args = ["--standalone", "-V", "papersize=a4", *_common_args(lang)]
    if template:
        args.append(f"--template={template}")
    typ = pypandoc.convert_text(json.dumps(ast), "typst", format="json", extra_args=args)
    dst.write_bytes(typst.compile(typ.encode(), root="/"))


def to_docx(src: Path, dst: Path, lang: str | None, template: Path | None) -> None:
    import pypandoc

    args = [f"--resource-path={src.parent}", *_common_args(lang)]
    with tempfile.TemporaryDirectory() as tmp:
        reference = template or _a4_reference_docx(Path(tmp) / "reference.docx")
        args.append(f"--reference-doc={reference}")
        pypandoc.convert_file(str(src), "docx", outputfile=str(dst), extra_args=args)


def _common_args(lang: str | None) -> list[str]:
    return ["-M", f"lang={lang}"] if lang else []


def _absolutize_images(node: object, base: Path) -> None:
    if isinstance(node, dict):
        if node.get("t") == "Image":
            target = node["c"][2]  # [url, title]
            if not URL_SCHEME.match(target[0]):
                target[0] = str((base / target[0]).resolve())
        for value in node.values():
            _absolutize_images(value, base)
    elif isinstance(node, list):
        for value in node:
            _absolutize_images(value, base)


def _a4_reference_docx(path: Path) -> Path:
    """Write pandoc's default reference.docx with an A4 page size added."""
    import subprocess

    import pypandoc

    default = subprocess.run(
        [pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
        capture_output=True,
        check=True,
    ).stdout
    with tempfile.SpooledTemporaryFile() as buf:
        buf.write(default)
        with zipfile.ZipFile(buf) as zin, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = data.replace(b"<w:sectPr>", f"<w:sectPr>{DOCX_A4}".encode(), 1)
                zout.writestr(item, data)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert Markdown to PDF or DOCX.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
formats:
  pdf     pandoc -> typst, A4. Bundled compiler, no LaTeX needed.
  docx    pandoc, A4.

  Frontmatter title, subtitle, author and date become the title block;
  lang (e.g. nb, en) sets hyphenation and localised labels.
  Relative image paths resolve from the Markdown file.

output:
  Writes <name>.<format> per input and format. Prints each written path on
  stdout, one per line; diagnostics and errors go to stderr. Exit code 1 if
  any file failed.

templates:
  --template style.docx   Word reference doc: styles, fonts, page setup
  --template style.typ    pandoc typst template
  Each template applies to the format matching its extension.

examples:
  md2doc notes.md                          # -> notes.pdf next to the input
  md2doc notes.md --to docx --to pdf       # both formats
  md2doc *.md --to docx -o out/ --lang nb  # batch, Norwegian
  md2doc report.md --to docx --template company.docx
""",
    )
    ap.add_argument("files", nargs="+", type=Path, help="Markdown input files")
    ap.add_argument(
        "-t", "--to", action="append", choices=FORMATS, help="output format (default: pdf)"
    )
    ap.add_argument("-o", "--outdir", type=Path, help="output dir (default: next to input)")
    ap.add_argument("--lang", help="document language, overrides frontmatter (e.g. nb, en)")
    ap.add_argument(
        "--template", action="append", type=Path, default=[], help=".docx or .typ template"
    )
    a = ap.parse_args()

    formats = list(dict.fromkeys(a.to or ["pdf"]))
    templates: dict[str, Path] = {}
    for template in a.template:
        fmt = next((f for f, s in TEMPLATE_SUFFIX.items() if template.suffix == s), None)
        if fmt is None:
            ap.error(f"--template {template}: expected a .docx or .typ file")
        if fmt not in formats:
            ap.error(f"--template {template}: only applies to --to {fmt}")
        templates[fmt] = template.resolve()

    convert = {"pdf": to_pdf, "docx": to_docx}
    failed = 0
    for src in a.files:
        outdir = a.outdir or src.parent
        outdir.mkdir(parents=True, exist_ok=True)
        for fmt in formats:
            dst = outdir / f"{src.stem}.{fmt}"
            try:
                # pandoc and typst report warnings on stdout; keep it for result paths.
                with contextlib.redirect_stdout(sys.stderr):
                    convert[fmt](src.resolve(), dst.resolve(), a.lang, templates.get(fmt))
                print(dst)
            except Exception as e:
                failed += 1
                print(f"md2doc: {src} -> {fmt}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
