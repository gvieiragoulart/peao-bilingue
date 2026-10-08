from peao_bilingue.dominio.entidades import Busca, Vaga


def aplica_a_fonte(busca: Busca, fonte: str) -> bool:
    """Busca sem fontes escolhidas vale para todas."""
    return not busca.fontes or fonte in busca.fontes


def casa(vaga: Vaga, busca: Busca) -> bool:
    """Passa se a busca vale para a fonte, alguma keyword aparece e nenhum excluído."""
    if not aplica_a_fonte(busca, vaga.fonte):
        return False
    texto = vaga.texto_pesquisavel()
    if any(termo.lower() in texto for termo in busca.exclude):
        return False
    return any(termo.lower() in texto for termo in busca.keywords)


def buscas_que_casam(vaga: Vaga, buscas: list[Busca]) -> list[str]:
    return [busca.nome for busca in buscas if casa(vaga, busca)]
