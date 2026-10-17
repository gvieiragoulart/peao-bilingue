"""Text out of the CV file the user imports."""

from pathlib import Path

import pytest

from peao_bilingue.adapters.documents import read_document


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF with `text` in Helvetica, written by hand: no PDF library is
    needed to create the fixture."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + content + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    body += b"startxref\n%d\n%%%%EOF\n" % xref
    return body


def test_reads_a_pdf(tmp_path: Path) -> None:
    path = tmp_path / "cv.pdf"
    path.write_bytes(minimal_pdf("Senior Python Engineer"))
    assert "Senior Python Engineer" in read_document(path)


def test_reads_utf8_and_windows_text(tmp_path: Path) -> None:
    utf8 = tmp_path / "cv.md"
    utf8.write_text("# Experiência\nLíder técnico", encoding="utf-8")
    ansi = tmp_path / "cv.txt"
    ansi.write_bytes("Experiência em São Paulo".encode("cp1252"))

    assert read_document(utf8) == "# Experiência\nLíder técnico"
    assert read_document(ansi) == "Experiência em São Paulo"


def test_other_formats_are_explained(tmp_path: Path) -> None:
    path = tmp_path / "cv.docx"
    path.write_bytes(b"PK")
    with pytest.raises(ValueError, match=r"\.txt, \.md or \.pdf"):
        read_document(path)
