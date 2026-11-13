"""Fetch Microsoft Learn articles and convert them to Markdown.

Keeps the page's <main> content (the article body in `div.content`, without site chrome) and
converts it with a small lxml-based converter that follows the Learn page structure: tables become
GFM tables, `pre > code.lang-*` fenced blocks, NOTE/IMPORTANT/WARNING/TIP/alert boxes blockquotes.

Modes: one or more article URLs, or a whole doc set from its toc.json (`--toc`).
Prints each written path to stdout; progress and errors go to stderr.
"""

import argparse
import copy
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USER_AGENT = "agent-toolkit-learn2md"
INLINE_TAGS = {
    "a",
    "strong",
    "b",
    "em",
    "i",
    "code",
    "span",
    "br",
    "sub",
    "sup",
    "abbr",
    "kbd",
    "mark",
    "u",
}
ADMONITIONS = {"NOTE", "IMPORTANT", "WARNING", "TIP", "CAUTION"}
SKIP_TAGS = {"script", "style", "button", "colgroup"}


# --- HTML -> Markdown -------------------------------------------------------------------------


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " "))


def _esc(s: str) -> str:
    return s.replace("*", r"\*")


def _inline(e, in_cell: bool = False) -> str:
    """Render the inline content of element e (its text and children) as Markdown."""
    out = [_esc(_ws(e.text or ""))]
    for ch in e:
        if not isinstance(ch.tag, str):  # comment / processing instruction
            out.append(_esc(_ws(ch.tail or "")))
            continue
        t = ch.tag
        if t == "code":
            txt = _ws(ch.text_content())
            fence = "`" * (max((len(m) for m in re.findall(r"`+", txt)), default=0) + 1)
            pad = " " if txt.startswith("`") or txt.endswith("`") else ""
            body = txt if pad else txt.strip()
            out.append(f"{fence}{pad}{body}{pad}{fence}" if txt.strip() else "")
        elif t in ("strong", "b", "em", "i"):
            mark = "**" if t in ("strong", "b") else "*"
            inner = _inline(ch, in_cell)
            core = inner.strip()
            if core:
                lead = inner[: len(inner) - len(inner.lstrip())]
                trail = inner[len(inner.rstrip()) :]
                out.append(f"{lead}{mark}{core}{mark}{trail}")
            else:
                out.append(inner)
        elif t == "a":
            inner = _inline(ch, in_cell)
            href = (ch.get("href") or "").strip()
            out.append(f"[{inner.strip()}]({href})" if href and inner.strip() else inner)
        elif t == "br":
            out.append("<br>" if in_cell else "  \n")
        elif t in ("sub", "sup"):
            out.append(f"<{t}>{_inline(ch, in_cell)}</{t}>")
        else:  # span, abbr, ... and unknown inline wrappers
            out.append(_inline(ch, in_cell))
        out.append(_esc(_ws(ch.tail or "")))
    return "".join(out)


def _para(s: str) -> str:
    s = re.sub(r"[ ]{2,}(?!\n)", " ", s).strip()
    return re.sub(r"^(#{1,6} |[-+] |\d+[.)] |>)", lambda m: "\\" + m.group(0), s)


def _code_block(pre) -> str:
    code = pre.find(".//code")
    node = code if code is not None else pre
    cls = (node.get("class") or "") + " " + (pre.get("class") or "")
    m = re.search(r"lang(?:uage)?-(\w+)", cls)
    lang = m.group(1).lower() if m else ""
    txt = node.text_content().replace("\xa0", " ").replace("\r", "").strip("\n").rstrip()
    fence = "```" if "```" not in txt else "````"
    return f"{fence}{lang}\n{txt}\n{fence}"


def _list(lst) -> str:
    ordered = lst.tag == "ol"
    items = []
    for i, li in enumerate(lst.xpath("./li"), 1):
        marker = f"{i}. " if ordered else "- "
        pad = " " * len(marker)
        blocks = _blocks(li)
        if not blocks:
            continue
        text = blocks[0]
        for blk in blocks[1:]:
            nested = re.match(r"(?:- |\d+\. )", blk) is not None
            text += ("\n" if nested else "\n\n") + blk
        items.append(marker + text.replace("\n", "\n" + pad).replace("\n" + pad + "\n", "\n\n"))
    return "\n".join(items)


def _cell(cell) -> str:
    txt = "<br>".join(p.replace("\n", "<br>") for p in _blocks(cell, in_cell=True))
    return re.sub(r"(?<!\\)\|", r"\\|", txt).strip()


def _table(tbl) -> str:
    rows = []
    for tr in tbl.xpath(".//tr"):
        cells = tr.xpath("./th | ./td")
        if cells:
            only_th = bool(tr.xpath("./th")) and not tr.xpath("./td")
            rows.append(([_cell(c) for c in cells], only_th))
    if not rows:
        return ""
    width = max(len(r) for r, _ in rows)
    has_head = rows[0][1]
    head = rows[0][0] if has_head else [""] * width  # GFM needs a header row
    body = rows[1:] if has_head else rows

    def line(c):
        return "| " + " | ".join((c + [""] * width)[:width]) + " |"

    return "\n".join(
        [line(head), "|" + "|".join(["---"] * width) + "|"] + [line(r) for r, _ in body]
    )


def _blocks(container, in_cell: bool = False) -> list[str]:
    """Render the children of container as a list of Markdown blocks."""
    from lxml import html as lh

    blocks: list[str] = []
    run: list = []  # pending inline content: strings and detached element copies

    def flush():
        if run:
            parts = []
            for item in run:
                if isinstance(item, str):
                    parts.append(_esc(_ws(item)))
                else:
                    tmp = lh.Element("span")
                    tmp.append(item)
                    parts.append(_inline(tmp, in_cell))
            s = _para("".join(parts))
            if s:
                blocks.append(s)
            run.clear()

    if container.text and container.text.strip():
        run.append(container.text)
    for ch in list(container):
        if not isinstance(ch.tag, str):
            if ch.tail and ch.tail.strip():
                run.append(ch.tail)
            continue
        t = ch.tag
        cls = set((ch.get("class") or "").split())
        if t in INLINE_TAGS:
            dup = copy.deepcopy(ch)
            dup.tail = None
            run.append(dup)
            if ch.tail:
                run.append(ch.tail)
            continue
        flush()
        if t == "p":
            s = _para(_inline(ch, in_cell))
            if s:
                blocks.append(s)
        elif re.fullmatch(r"h[1-6]", t):
            s = _inline(ch, in_cell).strip()
            if s:
                blocks.append("#" * int(t[1]) + " " + s)
        elif t == "pre":
            blocks.append(_code_block(ch))
        elif t in ("ul", "ol"):
            blocks.append(_list(ch))
        elif t == "table":
            blocks.append(_table(ch))
        elif t == "blockquote" or "alert" in cls or cls & ADMONITIONS:
            inner = _blocks(ch, in_cell)
            if inner and cls & ADMONITIONS and not inner[0].startswith("**"):
                inner[0] = f"**{inner[0]}**"
            if in_cell:  # a blockquote would break the table row
                blocks.append("\n".join(inner))
            else:
                q = "\n\n".join(inner)
                blocks.append("\n".join(("> " + ln) if ln else ">" for ln in q.split("\n")))
        elif t in SKIP_TAGS:
            pass
        else:  # div, section, ...: transparent container
            blocks.extend(_blocks(ch, in_cell))
        if ch.tail and ch.tail.strip():
            run.append(ch.tail)
    flush()
    return [b for b in blocks if b]


def convert_page(
    html: str, source: str | None = None, path: list[str] | None = None, title: str | None = None
) -> str:
    """Convert a Learn page (its <main> outer HTML, or a full page) to Markdown.

    The result is `# <h1>`, then optional `Path:` and `Source:` lines (with the page's last-updated
    date), then the article body from `div.content`.
    """
    import lxml.html

    root = lxml.html.fromstring(html)
    mains = root.xpath("//main")
    main = mains[0] if mains else root
    h1 = main.xpath("//h1")
    heading = _ws(h1[0].text_content()).strip() if h1 else (title or "")
    foot = main.xpath("//*[@id='article-metadata-footer']")
    updated = ""
    if foot:
        m = re.search(r"Last updated on\s+(\d{4}-\d{2}-\d{2})", foot[0].text_content())
        updated = m.group(1) if m else ""
    body: list[str] = []
    for c in main.xpath("//div[@class='content']"):
        for h in c.xpath(".//h1"):
            h.drop_tree()
        body.extend(_blocks(c))
    head = [f"# {heading}"] if heading else []
    meta = []
    if path:
        meta.append(f"Path: {' > '.join(path)}")
    if source or updated:
        meta.append(
            "Source: " + " · ".join(x for x in (source, updated and f"Last updated {updated}") if x)
        )
    return "\n\n".join([*head, *(["\n".join(meta)] if meta else []), *body]) + "\n"


# --- fetching -------------------------------------------------------------------------------


def _read_url(url: str) -> bytes:
    last: Exception | None = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):  # not worth retrying
                raise
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2**attempt)
    raise last  # type: ignore[misc]


def fetch_main(url: str, cache: Path | None = None, refresh: bool = False) -> str:
    """Return the outer HTML of the page's <main>, from the cache or the network."""
    import lxml.html

    f = cache / f"{_cache_name(url)}.html" if cache else None
    if f and f.exists() and not refresh:
        return f.read_text(encoding="utf-8")
    mains = lxml.html.fromstring(_read_url(url)).xpath("//main")
    if not mains:
        raise ValueError("no <main> element in the page")
    html = lxml.html.tostring(mains[0], encoding="unicode")
    if f:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")
    time.sleep(0.1)  # be polite
    return html


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._()-]+", "_", name).strip("_")[:120]


def _cache_name(url: str) -> str:
    p = urllib.parse.urlparse(url)
    tail = _safe(p.path.rstrip("/").rsplit("/", 1)[-1]) or "index"
    return f"{tail}-{hashlib.sha1(url.encode()).hexdigest()[:8]}"


# --- toc mode -------------------------------------------------------------------------------


def load_toc(src: str) -> dict:
    """Load a toc.json from a URL or a file."""
    if re.match(r"https?://", src):
        return json.loads(_read_url(src))
    return json.loads(Path(src).read_text(encoding="utf-8"))


def flatten_toc(toc: dict, base: str) -> list[dict]:
    """Depth-first toc nodes: title, href (as written), url (None without href), path, depth."""
    nodes: list[dict] = []

    def walk(node, depth, path):
        title = node.get("toc_title") or node.get("name") or "untitled"
        href = node.get("href") or ""
        p = [*path, title]
        url = urllib.parse.urljoin(base, href) if href else None
        nodes.append(
            {
                "title": title,
                "href": href,
                "url": url,
                "path": p,
                "depth": depth,
                "leaf": not node.get("children"),
            }  # fmt: skip
        )
        for ch in node.get("children", []):
            walk(ch, depth + 1, p)

    for item in toc.get("items", []):
        walk(item, 0, [])
    return nodes


def plan_files(nodes: list[dict]) -> None:
    """Set node['file'] (relative path): a directory per node with children, one .md per page."""
    used: set[str] = set()

    def unique(rel: str) -> str:
        base, n = rel, 2
        while rel.lower() in used:
            stem, dot, ext = base.rpartition(".")
            rel = f"{stem}-{n}.{ext}" if dot else f"{base}-{n}"
            n += 1
        used.add(rel.lower())
        return rel

    dirs: list[str] = []  # dirs[d] = directory of the ancestor at depth d
    for n in nodes:
        del dirs[n["depth"] :]
        name = _safe(n["title"]) or "untitled"
        parent = dirs[-1] if dirs else ""
        prefix = parent + "/" if parent else ""
        if n["leaf"]:
            n["file"] = unique(f"{prefix}{name}.md") if n["url"] else None
        else:
            d = unique(f"{prefix}{name}")
            dirs.append(d)
            n["file"] = unique(f"{d}/_index.md") if n["url"] else None


def build_tree(
    toc: dict, base: str, out: Path, cache: Path | None, workers: int = 4, refresh: bool = False
) -> tuple[list[dict], list[str]]:
    """Fetch every page in the toc and write the tree under out. Returns (nodes, error lines)."""
    nodes = flatten_toc(toc, base)
    plan_files(nodes)
    errors: list[str] = []

    def get(n):
        if not n["url"]:
            return None
        try:
            return fetch_main(n["url"], cache, refresh)
        except Exception as e:  # report per page, keep going
            errors.append(f"learn2md: {n['url']}: {e}")
            return None

    with ThreadPoolExecutor(max(1, workers)) as ex:
        pages = list(ex.map(get, nodes))
    for n, html in zip(nodes, pages, strict=True):
        if html is None:
            n["ok"] = False
            continue
        n["ok"] = True
        dest = out / n["file"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(convert_page(html, n["url"], n["path"][:-1], n["title"]), encoding="utf-8")
    with (out / "TOC.md").open("w", encoding="utf-8") as f:
        f.write(
            "# Table of contents\n\nOne line per page: `title -> file | url-slug`. "
            f"File paths are relative to this directory; the online page is `{base}<url-slug>`.\n\n"
        )
        for n in nodes:
            target = n["file"] if n.get("ok") else "-"
            f.write(f"{'  ' * n['depth']}- {n['title']} -> {target} | {n['href']}\n")
    return nodes, errors


# --- CLI ------------------------------------------------------------------------------------


def _error(subject: str, reason: object) -> None:
    print(f"learn2md: {subject}: {reason}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="learn2md",
        description="Fetch Microsoft Learn articles and convert them to Markdown.",
        epilog=(
            "examples:\n"
            "  learn2md https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/"
            "unattend/microsoft-windows-deployment-deviceform\n"
            "  learn2md URL1 URL2 -o pages/\n"
            "  learn2md --toc https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/"
            "unattend/toc.json -o unattend/\n"
            "  learn2md --toc toc.json --base https://learn.microsoft.com/en-us/<doc-root>/ "
            "-o docs/ --cache .cache --workers 2 --refresh\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("urls", nargs="*", help="article URLs (one .md per URL)")
    ap.add_argument(
        "--toc", metavar="URL_OR_FILE", help="toc.json of a doc set: fetch the whole tree"
    )
    ap.add_argument(
        "--base", help="root URL the toc hrefs are relative to (default: the toc URL's folder)"
    )
    ap.add_argument(
        "-o", "--out", type=Path, default=Path("."), help="output directory (default: .)"
    )
    ap.add_argument(
        "--cache", type=Path, help="cache raw <main> HTML here (toc mode default: OUT/.cache)"
    )
    ap.add_argument(
        "--workers", type=int, default=4, help="parallel downloads in toc mode (default 4)"
    )
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and download again")
    a = ap.parse_args()

    if bool(a.toc) == bool(a.urls):
        ap.error("give article URLs or --toc, not both or neither")

    if a.toc:
        try:
            toc = load_toc(a.toc)
        except Exception as e:
            _error(a.toc, e)
            return 1
        base = a.base or (a.toc.rsplit("/", 1)[0] + "/" if re.match(r"https?://", a.toc) else None)
        if not base:
            ap.error("--base is required when --toc is a file")
        if not base.endswith("/"):
            base += "/"
        a.out.mkdir(parents=True, exist_ok=True)
        cache = a.cache or a.out / ".cache"
        nodes, errors = build_tree(toc, base, a.out, cache, a.workers, a.refresh)
        for line in errors:
            print(line, file=sys.stderr)
        for n in nodes:
            if n.get("ok"):
                print(a.out / n["file"])
        print(a.out / "TOC.md")
        return 1 if errors else 0

    failed = False
    a.out.mkdir(parents=True, exist_ok=True)
    for url in a.urls:
        try:
            html = fetch_main(url, a.cache, a.refresh)
            name = _safe(urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]) or "index"
            dest = a.out / f"{name}.md"
            dest.write_text(convert_page(html, url), encoding="utf-8")
            print(dest)
        except Exception as e:
            _error(url, e)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
