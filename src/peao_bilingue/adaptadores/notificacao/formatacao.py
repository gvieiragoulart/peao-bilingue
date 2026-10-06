from peao_bilingue.dominio.entidades import ResultadoAnalise

LIMITE_WHATSAPP = 1_500


def montar_email(resultado: ResultadoAnalise) -> tuple[str, str]:
    """Assunto e corpo do email de uma vaga analisada."""
    vaga, analise, anterior = resultado.vaga, resultado.analise, resultado.fit_anterior

    if anterior is None:
        assunto = f"[{analise.fit_score}] {vaga.titulo} · {vaga.fonte}"
        linha_fit = f"Fit: {analise.fit_score}/100"
    else:
        assunto = f"[{anterior}→{analise.fit_score}] {vaga.titulo} · {vaga.fonte}"
        linha_fit = f"Fit: {anterior} → {analise.fit_score}/100 (reanálise após mudança no perfil)"

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
    corpo = [
        vaga.titulo,
        detalhes,
        vaga.url,
        "",
        linha_fit,
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
    return assunto, "\n".join(corpo)


def montar_digest(
    resultados: list[ResultadoAnalise], perfil_mudou: bool = False
) -> str:
    """Resumo curto, ordenado por fit e cortado no limite do WhatsApp.

    Cita a empresa só quando a fonte publica: várias (como a VanHack) não publicam.
    """
    ordenados = sorted(resultados, key=lambda r: r.analise.fit_score, reverse=True)
    texto = f"Peão Bilíngue — {len(ordenados)} vaga(s) nova(s)"
    if perfil_mudou:
        texto += "\nPerfil atualizado: vagas anteriores foram reanalisadas."

    for indice, resultado in enumerate(ordenados):
        vaga = resultado.vaga
        onde = " — ".join(parte for parte in (vaga.empresa, vaga.local) if parte)
        onde = f" — {onde}" if onde else ""
        bloco = f"\n\n{resultado.analise.fit_score} · {vaga.titulo}{onde} ({vaga.fonte})\n{vaga.url}"
        sufixo = f"\n\n+{len(ordenados) - indice} vaga(s) no app"
        if len(texto) + len(bloco) + len(sufixo) > LIMITE_WHATSAPP:
            return texto + sufixo
        texto += bloco
    return texto
