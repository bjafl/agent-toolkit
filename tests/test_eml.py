from pathlib import Path

from agent_toolkit.eml import eml_to_markdown

# Outlook-style export: quoted-printable latin-1, RFC 2047 header, inline cid
# image (signature logo inside a link) and a real attachment.
EML = b"""\
From: =?iso-8859-1?Q?Kari_Nordmann?= <kari@example.no>
To: "ola@example.no" <ola@example.no>, Per <per@example.no>
Subject: =?iso-8859-1?Q?M=F8te_p=E5_fredag?=
Date: Mon, 19 Oct 2026 12:04:11 +0000
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="MIX"

--MIX
Content-Type: multipart/related; boundary="REL"

--REL
Content-Type: multipart/alternative; boundary="ALT"

--ALT
Content-Type: text/plain; charset="iso-8859-1"
Content-Transfer-Encoding: quoted-printable

Hei, vi m=F8tes p=E5 fredag.

--ALT
Content-Type: text/html; charset="iso-8859-1"
Content-Transfer-Encoding: quoted-printable

<html><body><p>Hei, vi m=F8tes p=E5 <b>fredag</b>.</p><p>&nbsp;</p>
<p><a href=3D"https://example.no"><img src=3D"cid:logo@x"></a></p></body></html>

--ALT--

--REL
Content-Type: image/png; name="logo.png"
Content-Disposition: inline; filename="logo.png"
Content-ID: <logo@x>
Content-Transfer-Encoding: base64

iVBORw0KGgo=

--REL--

--MIX
Content-Type: application/pdf; name="../agenda.pdf"
Content-Disposition: attachment; filename="../agenda.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK

--MIX--
"""


def write_eml(tmp_path: Path) -> Path:
    src = tmp_path / "mail.eml"
    src.write_bytes(EML.replace(b"\n", b"\r\n"))
    return src


def test_decodes_headers_body_and_lists_attachments(tmp_path):
    md = eml_to_markdown(write_eml(tmp_path), None)

    assert md.startswith(
        '---\nsubject: "Møte på fredag"\nfrom: "Kari Nordmann <kari@example.no>"\n'
    )
    assert 'to:\n  - "ola@example.no"\n  - "Per <per@example.no>"\n' in md
    assert "date: 2026-10-19T12:04:11+00:00\n" in md
    assert 'attachments:\n  - "agenda.pdf"\n---' in md  # inline logo not listed
    assert "# Møte på fredag" in md
    assert "Hei, vi møtes på **fredag**." in md
    assert "cid:" not in md
    assert "[](" not in md  # link emptied by the dropped logo is removed


def test_media_saves_parts_and_rewrites_cid(tmp_path, monkeypatch):
    src = write_eml(tmp_path)
    monkeypatch.chdir(tmp_path)

    md = eml_to_markdown(src, Path("mail_media"))

    assert "[![](mail_media/logo.png)](https://example.no)" in md
    assert (tmp_path / "mail_media" / "logo.png").read_bytes().startswith(b"\x89PNG")
    # Path traversal in the attachment filename is neutralised.
    assert (tmp_path / "mail_media" / "agenda.pdf").read_bytes().startswith(b"%PDF")
    assert not (tmp_path / "agenda.pdf").exists()
