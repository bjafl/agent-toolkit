"""Convert an RFC 822 e-mail (.eml) to Markdown with YAML frontmatter.

The stdlib parser with policy.default handles quoted-printable/base64 bodies,
charsets and RFC 2047 encoded headers. HTML bodies go through pandoc.
"""

import json
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

CID_IMG = re.compile(r"<img\b[^>]*\bsrc=[\"']cid:[^\"']*[\"'][^>]*>", re.I)


def eml_to_markdown(src: Path, media: Path | None) -> str:
    """Return Markdown for the e-mail; with media, save attachments and inline images there."""
    with src.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    body = msg.get_body(preferencelist=("html", "plain"))
    parts = [p for p in msg.walk() if not p.is_multipart() and not _is_text_body(p, body)]
    html = body.get_content() if body and body.get_content_type() == "text/html" else None

    names = _unique_names(parts)
    cids = {_cid(p): name for p, name in zip(parts, names, strict=True) if _cid(p)}
    inline = {cid for cid in cids if html and f"cid:{cid}" in html}
    attachments = [n for p, n in zip(parts, names, strict=True) if _cid(p) not in inline]

    if media:
        media.mkdir(parents=True, exist_ok=True)
        for part, name in zip(parts, names, strict=True):
            (media / name).write_bytes(part.get_payload(decode=True) or b"")

    if html is not None:
        text = _html_to_markdown(html, cids, media)
    else:
        text = body.get_content() if body else ""

    header = _frontmatter(msg, attachments)
    title = f"# {msg['Subject']}\n\n" if msg["Subject"] else ""
    return f"{header}{title}{_tidy(text)}\n"


def _is_text_body(part: EmailMessage, body: EmailMessage | None) -> bool:
    # The chosen body and its text/plain or text/html alternative; text parts
    # with a filename are real attachments.
    if part is body:
        return True
    return part.get_content_type() in ("text/plain", "text/html") and not part.get_filename()


def _cid(part: EmailMessage) -> str | None:
    cid = part.get("Content-ID")
    return cid.strip().strip("<>") if cid else None


def _unique_names(parts: list[EmailMessage]) -> list[str]:
    names: list[str] = []
    for i, part in enumerate(parts, 1):
        # Path(...).name drops directories, so a hostile filename can't escape media/.
        name = Path(part.get_filename() or f"part{i}").name or f"part{i}"
        stem, suffix, n = Path(name).stem, Path(name).suffix, 2
        while name in names:
            name, n = f"{stem}-{n}{suffix}", n + 1
        names.append(name)
    return names


def _html_to_markdown(html: str, cids: dict[str, str], media: Path | None) -> str:
    import pypandoc

    if media:
        for cid, name in cids.items():
            html = html.replace(f"cid:{cid}", (media / name).as_posix())
    else:
        html = CID_IMG.sub("", html)
    md = pypandoc.convert_text(html, "gfm-raw_html", format="html", extra_args=["--wrap=none"])
    if not media:
        # Links left empty once their image was dropped, e.g. social media logos.
        md = re.sub(r"(?<!!)\[\]\([^)]*\)", "", md)
    return md


def _frontmatter(msg: EmailMessage, attachments: list[str]) -> str:
    def q(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)  # JSON strings are valid YAML

    def addrs(field: str) -> list[str]:
        # Outlook often repeats the address as display name: "a@b" <a@b> -> a@b
        return [
            a.addr_spec if a.display_name in ("", a.addr_spec) else str(a)
            for a in msg[field].addresses
        ]

    lines = ["---"]
    if msg["Subject"]:
        lines.append(f"subject: {q(str(msg['Subject']))}")
    if msg["From"]:
        lines.append(f"from: {q(addrs('From')[0])}")
    for field in ("To", "Cc"):
        if msg[field]:
            lines.append(f"{field.lower()}:")
            lines += [f"  - {q(a)}" for a in addrs(field)]
    if msg["Date"]:
        date = msg["Date"].datetime
        lines.append(f"date: {date.isoformat() if date else q(str(msg['Date']))}")
    if attachments:
        lines.append("attachments:")
        lines += [f"  - {q(name)}" for name in attachments]
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _tidy(md: str) -> str:
    # Outlook pads paragraphs with &nbsp;-only lines; collapse them.
    md = re.sub(r"^[ \t ]+$", "", md, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", md).strip()
