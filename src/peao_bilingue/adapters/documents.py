"""Text out of a file the user picks (their CV): .txt, .md or .pdf."""

from pathlib import Path

from pypdf import PdfReader

from peao_bilingue.i18n import _

READABLE = (".txt", ".md", ".pdf")


def read_document(path: Path) -> str:
    # Windows text has CRLF line breaks; the app works with plain ones.
    text = _read(path)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = PdfReader(path).pages
        return "\n".join(page.extract_text() or "" for page in pages).strip()
    if suffix in (".txt", ".md"):
        raw = path.read_bytes()
        try:
            return raw.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            # Notepad's "ANSI" on a Portuguese Windows.
            return raw.decode("cp1252").strip()
    raise ValueError(
        _("Can't read {name}: use a .txt, .md or .pdf file.").format(name=path.name)
    )
