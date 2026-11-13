import sys
import urllib.request
from pathlib import Path

import pytest

from agent_toolkit import learn2md

FIX = Path(__file__).parent / "fixtures" / "learn"
BASE = "https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/"
SOUND = "microsoft-windows-authentication-authui-disablestartupsound"
FORM = "microsoft-windows-deployment-deviceform"
RESEAL = "microsoft-windows-deployment-reseal-forceshutdownnow"


def fixture(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def wrap(body: str) -> str:
    return f'<main><div class="content">{body}</div></main>'


def test_page_structure_and_chrome_removed():
    md = learn2md.convert_page(fixture(SOUND), source=BASE + SOUND, path=["A", "B"])

    assert md.startswith("# DisableStartupSound\n\nPath: A > B\nSource: " + BASE + SOUND)
    assert "Last updated 2021-06-24" in md
    assert "## Valid Configuration Passes\n\nspecialize" in md
    assert "```xml\n<DisableStartupSound>true</DisableStartupSound>\n```" in md
    for chrome in ("Ask Learn", "Reading mode", "Table of contents", "Additional resources"):
        assert chrome not in md


def test_links_are_kept():
    md = learn2md.convert_page(fixture(SOUND))

    assert (
        "[Microsoft-Windows-Authentication-AuthUI](microsoft-windows-authentication-authui)" in md
    )


def test_tables_are_gfm_with_empty_header_when_no_thead():
    md = learn2md.convert_page(fixture(SOUND))

    assert "|  |  |\n|---|---|\n| true |" in md


def test_table_with_thead_uses_it():
    md = learn2md.convert_page(fixture(FORM))

    assert "| Value | Device form | Description |\n|---|---|---|" in md


def test_admonition_becomes_blockquote():
    md = learn2md.convert_page(fixture(FORM))

    assert "> **Warning**\n>\n> This field should be populated" in md


def test_alert_in_table_cell_stays_inside_the_row():
    md = learn2md.convert_page(fixture(RESEAL))

    row = next(ln for ln in md.splitlines() if "Unsupported, do not use" in ln)
    assert row.startswith("|") and row.endswith("|")
    assert "**Caution**" in row
    assert "> **Caution**" not in md


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("<p>a <strong>b</strong> <em>c</em> <code>d|e</code></p>", "a **b** *c* `d|e`"),
        ("<p>set to an asterisk (*)</p>", r"set to an asterisk (\*)"),
        ("<ul><li>one</li><li>two<ul><li>x</li></ul></li></ul>", "- one\n- two\n  - x"),
        ("<ol><li>one</li><li>two</li></ol>", "1. one\n2. two"),
        (
            '<pre><code class="lang-xml">&lt;A&gt;\n  &lt;B/&gt;\n&lt;/A&gt;\n</code></pre>',
            "```xml\n<A>\n  <B/>\n</A>\n```",
        ),
        ("<p>x<br>y</p>", "x  \ny"),
        ("<h2>Values</h2><p>t</p>", "## Values\n\nt"),
    ],
)
def test_block_and_inline_conversion(body, expected):
    assert expected in learn2md.convert_page(wrap(body))


def test_pipe_in_cell_is_escaped():
    md = learn2md.convert_page(wrap("<table><tr><td>a|b</td></tr></table>"))

    assert r"| a\|b |" in md


def test_single_url_writes_md_and_prints_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        learn2md, "fetch_main", lambda url, cache=None, refresh=False: fixture(SOUND)
    )
    monkeypatch.setattr(sys, "argv", ["learn2md", BASE + SOUND, "-o", str(tmp_path)])

    assert learn2md.main() == 0

    out = tmp_path / f"{SOUND}.md"
    assert capsys.readouterr().out.split() == [str(out)]
    assert out.read_text().startswith("# DisableStartupSound")


def test_single_url_failure_exits_1_with_error_line(tmp_path, monkeypatch, capsys):
    def boom(url, cache=None, refresh=False):
        raise ValueError("no <main> element in the page")

    monkeypatch.setattr(learn2md, "fetch_main", boom)
    monkeypatch.setattr(sys, "argv", ["learn2md", BASE + "x", "-o", str(tmp_path)])

    assert learn2md.main() == 1

    err = capsys.readouterr().err
    assert err.strip() == f"learn2md: {BASE}x: no <main> element in the page"


def test_toc_mode_builds_tree_from_cache_without_network(tmp_path, monkeypatch, capsys):
    toc = {
        "items": [
            {
                "toc_title": "Root",
                "href": "./",
                "children": [
                    {"toc_title": "Group", "children": [{"toc_title": "Sound", "href": SOUND}]},
                    {"toc_title": "Form", "href": FORM},
                ],
            }
        ]
    }
    toc_file = tmp_path / "toc.json"
    toc_file.write_text(__import__("json").dumps(toc))
    cache = tmp_path / "cache"
    cache.mkdir()
    for href in ("", SOUND, FORM):
        url = BASE + href
        (cache / f"{learn2md._cache_name(url)}.html").write_text(
            fixture(SOUND if href != FORM else FORM)
        )

    def no_network(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        ["learn2md", "--toc", str(toc_file), "--base", BASE, "-o", str(out), "--cache", str(cache)],
    )

    assert learn2md.main() == 0

    assert (out / "Root" / "_index.md").is_file()
    assert (out / "Root" / "Group" / "Sound.md").read_text().startswith("# DisableStartupSound")
    assert (out / "Root" / "Form.md").is_file()
    assert not (out / "Root" / "Group" / "_index.md").exists()  # group node has no page
    toc_md = (out / "TOC.md").read_text()
    assert "  - Group -> - | \n" in toc_md
    assert f"    - Sound -> Root/Group/Sound.md | {SOUND}\n" in toc_md
    assert str(out / "TOC.md") in capsys.readouterr().out.split()


def test_toc_file_without_base_is_a_usage_error(tmp_path, monkeypatch):
    (tmp_path / "toc.json").write_text('{"items": []}')
    monkeypatch.setattr(sys, "argv", ["learn2md", "--toc", str(tmp_path / "toc.json")])

    with pytest.raises(SystemExit) as e:
        learn2md.main()
    assert e.value.code == 2
