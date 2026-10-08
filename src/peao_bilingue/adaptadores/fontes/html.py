"""HTML de descrição de vaga (APIs e feeds) para texto, uma linha por parágrafo.

Achatar tudo numa linha só deixa a descrição ilegível na tela e tira do LLM a
estrutura (responsabilidades, requisitos); o scraper da VanHack faz o mesmo.
"""

from html.parser import HTMLParser

# Tags que começam linha nova: parágrafos, quebras, itens de lista, títulos.
QUEBRAM_LINHA = {
    "p", "br", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "blockquote", "pre",
}  # fmt: skip
IGNORADAS = {"script", "style"}


class _Extrator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in IGNORADAS:
            self._ignorando += 1
        elif tag in QUEBRAM_LINHA:
            self.partes.append("\n")
        if tag == "li":
            self.partes.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in IGNORADAS:
            self._ignorando = max(0, self._ignorando - 1)
        elif tag in QUEBRAM_LINHA:
            self.partes.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self.partes.append(data)


def html_para_texto(html: str) -> str:
    extrator = _Extrator()
    extrator.feed(html)
    extrator.close()
    linhas = (
        " ".join(linha.split()) for linha in "".join(extrator.partes).splitlines()
    )
    # Linha só com o marcador de item (ex.: <li> vazio) não diz nada.
    return "\n".join(linha for linha in linhas if linha and linha != "-")
