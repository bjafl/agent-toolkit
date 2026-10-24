import re
import sys
import zipfile

import pymupdf
import pytest

from agent_toolkit import md2doc

A4_HEIGHT_PT = 842


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["md2doc", *args])
    return md2doc.main()


@pytest.fixture
def doc(tmp_path):
    """notes/doc.md with one image beside it and one in the parent dir."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), 0)
    pix.save(tmp_path / "up.png")
    (tmp_path / "notes").mkdir()
    pix.save(tmp_path / "notes" / "here.png")
    src = tmp_path / "notes" / "doc.md"
    src.write_text(
        "---\ntitle: Møtereferat\nlang: nb\n---\n\n"
        "Tekst med æøå.\n\n![a](here.png)\n\n![b](../up.png)\n",
        encoding="utf-8",
    )
    return src


def test_pdf_is_a4_with_images_and_text(doc, tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"

    assert run(monkeypatch, str(doc), "-o", str(out)) == 0

    assert capsys.readouterr().out.split() == [str(out / "doc.pdf")]
    page = pymupdf.open(out / "doc.pdf")[0]
    assert round(page.rect.height) == A4_HEIGHT_PT
    assert "Møtereferat" in page.get_text()
    assert "æøå" in page.get_text()
    assert len(page.get_image_info()) == 2


def test_docx_is_a4_with_embedded_images(doc, monkeypatch, capsys):
    assert run(monkeypatch, str(doc), "--to", "docx") == 0

    dst = doc.with_suffix(".docx")
    assert capsys.readouterr().out.split() == [str(dst)]
    with zipfile.ZipFile(dst) as z:
        xml = z.read("word/document.xml").decode()
        media = [n for n in z.namelist() if n.startswith("word/media/")]
    assert re.search(r'<w:pgSz[^>]*w:h="16838"', xml)
    assert "æøå" in xml
    assert len(media) == 2


def test_template_must_match_a_requested_format(doc, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, str(doc), "--to", "pdf", "--template", "style.docx")
    assert exc.value.code == 2
    assert "only applies to --to docx" in capsys.readouterr().err


def test_missing_file_fails_with_stderr(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, str(tmp_path / "nope.md"), "--to", "docx") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope.md -> docx" in captured.err
