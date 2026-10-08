"""Transforma entidades em texto e linhas de tabela. Sem Tk: testável direto."""

from peao_bilingue.dominio.analise import AnaliseSalva, JobAnalysis
from peao_bilingue.dominio.buscas import Busca
from peao_bilingue.dominio.coleta import Execucao
from peao_bilingue.dominio.vagas import StatusVaga, Vaga, VagaListada

TODAS = "Todas"
OPCOES_STATUS = [TODAS, *(status.value for status in StatusVaga)]
TAMANHO_ERRO_NA_TABELA = 80


def linha_de_vaga(item: VagaListada) -> tuple[str, ...]:
    return (
        "" if item.fit_score is None else str(item.fit_score),
        item.vaga.titulo,
        item.vaga.local or "",
        item.vaga.fonte,
        item.status.value,
    )


def texto_da_analise(vaga: Vaga, analise: JobAnalysis) -> str:
    detalhes = " | ".join(
        parte
        for parte in (
            vaga.empresa,
            vaga.local,
            vaga.modalidade,
            vaga.salario,
            vaga.extras.get("local_exigido"),
        )
        if parte
    )
    return "\n".join(
        [
            vaga.titulo,
            detalhes,
            vaga.url,
            "",
            f"Fit: {analise.fit_score}/100",
            "",
            "RESUMO",
            analise.resumo,
            "",
            "PREPARAÇÃO",
            *(f"- {passo}" for passo in analise.preparacao),
            "",
            f"PERGUNTAS DE ENTREVISTA ({len(analise.perguntas)})",
            *(f"{n}. {pergunta}" for n, pergunta in enumerate(analise.perguntas, 1)),
            "",
            "GAPS",
            *(f"- {gap}" for gap in analise.gaps or ["(nenhum identificado)"]),
            "",
            "O QUE MELHORAR NO PERFIL",
            *(f"- {melhoria}" for melhoria in analise.melhorias_perfil),
        ]
    )


def detalhe_da_vaga(item: VagaListada, analise: AnaliseSalva | None) -> str:
    if analise is None:
        return "\n".join(
            [
                item.vaga.titulo,
                item.vaga.url,
                "",
                "Ainda não analisada: escolha o LLM e o perfil e clique em Analisar.",
                "",
                "DESCRIÇÃO",
                item.vaga.descricao or "(sem descrição)",
            ]
        )

    rodape = (
        f"Análise por {analise.provedor} ({analise.modelo}) "
        f"em {analise.criada_em:%d/%m/%Y %H:%M}"
    )
    if analise.perfil_fonte:
        rodape += f", com o perfil da fonte {analise.perfil_fonte}"
    rodape += "."
    if analise.perfil_desatualizado:
        rodape += (
            f"\nO perfil da fonte {analise.perfil_fonte} mudou depois desta análise: "
            "analise de novo para atualizar."
        )
    return f"{texto_da_analise(item.vaga, analise.analise)}\n\n{rodape}"


def linha_de_busca(busca: Busca) -> tuple[str, ...]:
    return (
        busca.nome,
        ", ".join(busca.keywords),
        ", ".join(busca.exclude),
        ", ".join(busca.fontes) or "todas",
        "sim" if busca.ativa else "não",
    )


def linha_de_execucao(execucao: Execucao) -> tuple[str, ...]:
    erro = execucao.erro or ""
    if len(erro) > TAMANHO_ERRO_NA_TABELA:
        erro = erro[: TAMANHO_ERRO_NA_TABELA - 1] + "…"
    return (
        f"{execucao.iniciada_em:%d/%m %H:%M}",
        execucao.gatilho.value,
        execucao.status.value,
        str(execucao.vagas_listadas),
        str(execucao.vagas_novas),
        erro,
    )


def termos(texto: str) -> list[str]:
    """ "python, django ,," -> ["python", "django"]."""
    return [termo.strip() for termo in texto.split(",") if termo.strip()]


def score_minimo(texto: str) -> int | None:
    texto = texto.strip()
    if not texto:
        return None
    try:
        valor = int(texto)
    except ValueError:
        raise ValueError("O fit mínimo precisa ser um número de 0 a 100.") from None
    if not 0 <= valor <= 100:
        raise ValueError("O fit mínimo precisa ser um número de 0 a 100.")
    return valor
