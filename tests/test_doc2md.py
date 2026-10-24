import sys

from agent_toolkit import doc2md


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["doc2md", *args])
    return doc2md.main()


def test_converts_html_to_markdown(tmp_path, monkeypatch, capsys):
    src = tmp_path / "page.html"
    src.write_text("<h1>Title</h1><p>Hello <b>world</b></p>", encoding="utf-8")

    assert run(monkeypatch, str(src), "-o", str(tmp_path / "out")) == 0

    dst = tmp_path / "out" / "page.md"
    assert capsys.readouterr().out.strip() == str(dst)
    md = dst.read_text(encoding="utf-8")
    assert "# Title" in md
    assert "**world**" in md


def test_missing_file_fails_with_stderr(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, str(tmp_path / "nope.docx")) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope.docx" in captured.err


def test_same_stem_gets_extension_suffix(tmp_path, monkeypatch, capsys):
    for name in ("page.html", "page.htm"):
        (tmp_path / name).write_text("<p>hi</p>", encoding="utf-8")
    out = tmp_path / "out"

    assert (
        run(monkeypatch, str(tmp_path / "page.html"), str(tmp_path / "page.htm"), "-o", str(out))
        == 0
    )

    assert capsys.readouterr().out.split() == [str(out / "page.md"), str(out / "page.htm.md")]


def test_third_collision_is_skipped(tmp_path, monkeypatch, capsys):
    srcs = []
    for d in ("a", "b", "c"):
        (tmp_path / d).mkdir()
        srcs.append(tmp_path / d / "page.html")
        srcs[-1].write_text("<p>hi</p>", encoding="utf-8")
    out = tmp_path / "out"

    assert run(monkeypatch, *map(str, srcs), "-o", str(out)) == 1

    captured = capsys.readouterr()
    assert captured.out.split() == [str(out / "page.md"), str(out / "page.html.md")]
    assert "c/page.html: skipped" in captured.err
