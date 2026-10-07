"""Transforma entidades em texto e linhas de tabela. Sem Tk: testável direto."""

from peao_bilingue.adaptadores.notificacao.formatacao import montar_email
from peao_bilingue.dominio.entidades import (
    AnaliseSalva,
    Busca,
    Execucao,
    ResultadoAnalise,
    SituacaoAgenda,
    StatusVaga,
    VagaListada,
)

TODAS = "Todas"
OPCOES_STATUS = [TODAS, *(status.value for status in StatusVaga)]
TAMANHO_ERRO_NA_TABELA = 80


def linha_de_vaga(item: VagaListada) -> tuple[str, ...]:
    triagem = ""
    if item.triagem is not None:
        marca = "passou" if item.triagem.passou else "barrada"
        triagem = f"{item.triagem.triagem.fit_score} ({marca})"
    return (
        "" if item.fit_score is None else str(item.fit_score),
        item.vaga.titulo,
        item.vaga.local or "",
        item.vaga.fonte,
        item.status.value,
        triagem,
    )


def detalhe_da_vaga(item: VagaListada, analise: AnaliseSalva | None) -> str:
    if analise is not None:
        _, corpo = montar_email(
            ResultadoAnalise(vaga=item.vaga, analise=analise.analise)
        )
        rodape = (
            f"Análise por {analise.provedor} ({analise.modelo}) "
            f"em {analise.criada_em:%d/%m/%Y %H:%M}."
        )
        return f"{corpo}\n\n{rodape}"

    partes = [item.vaga.titulo, item.vaga.url, ""]
    if item.triagem is not None and not item.triagem.passou:
        partes.append(
            f"Barrada na triagem com nota {item.triagem.triagem.fit_score} "
            f"({item.triagem.provedor}): {item.triagem.triagem.motivo}"
        )
    else:
        partes.append("Ainda não analisada.")
    partes += ["", "DESCRIÇÃO", item.vaga.descricao or "(sem descrição)"]
    return "\n".join(partes)


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
        str(execucao.vagas_analisadas),
        str(execucao.vagas_barradas_na_triagem),
        erro,
    )


def descrever_agenda(situacao: SituacaoAgenda | None) -> str:
    if situacao is None:
        return "Nenhuma coleta agendada."
    partes = [f"Todo dia às {situacao.horario} (tarefa: {situacao.estado})."]
    if situacao.proxima_execucao:
        partes.append(f"Próxima: {situacao.proxima_execucao:%d/%m %H:%M}.")
    if situacao.ultima_execucao:
        resultado = (
            "ok"
            if situacao.ultimo_resultado == 0
            else f"código {situacao.ultimo_resultado}"
        )
        partes.append(f"Última: {situacao.ultima_execucao:%d/%m %H:%M} ({resultado}).")
    return " ".join(partes)


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
