"""Job description HTML (APIs and feeds) to text, one line per paragraph.

Flattening everything into one line makes the description unreadable on screen and
takes the structure (responsibilities, requirements) away from the LLM; the VanHack
scraper does the same.
"""

from html.parser import HTMLParser

# Tags that start a new line: paragraphs, breaks, list items, headings.
LINE_BREAK_TAGS = {
    "p", "br", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "blockquote", "pre",
}  # fmt: skip
IGNORED = {"script", "style"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignoring = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in IGNORED:
            self._ignoring += 1
        elif tag in LINE_BREAK_TAGS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in IGNORED:
            self._ignoring = max(0, self._ignoring - 1)
        elif tag in LINE_BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignoring:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    extractor = _Extractor()
    extractor.feed(html)
    extractor.close()
    return tidy_lines("".join(extractor.parts))


def tidy_lines(text: str) -> str:
    """One space between words, no empty lines."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    # A line with only the bullet (e.g. an empty <li>) says nothing.
    return "\n".join(line for line in lines if line and line != "-")
