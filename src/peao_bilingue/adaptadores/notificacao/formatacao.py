"""Texto dos avisos de vagas novas. A análise não vai no aviso: é pedida no app."""

from peao_bilingue.dominio.vagas import Vaga

LIMITE_WHATSAPP = 1_500


def _onde(vaga: Vaga, *partes_extras: str | None) -> str:
    # Cita a empresa só quando a fonte publica: várias (como a VanHack) não publicam.
    partes = (vaga.empresa, vaga.local, *partes_extras)
    return " | ".join(parte for parte in partes if parte)


def montar_email(vagas: list[Vaga]) -> tuple[str, str]:
    """Assunto e corpo de um email com todas as vagas novas de uma coleta."""
    assunto = f"Peão Bilíngue — {len(vagas)} vaga(s) nova(s)"
    blocos = []
    for vaga in vagas:
        linhas = [f"{vaga.titulo} ({vaga.fonte})"]
        detalhes = _onde(
            vaga, vaga.modalidade, vaga.salario, vaga.extras.get("local_exigido")
        )
        if detalhes:
            linhas.append(detalhes)
        if vaga.skills_obrigatorias:
            skills = ", ".join(skill.nome for skill in vaga.skills_obrigatorias)
            linhas.append(f"Skills: {skills}")
        linhas.append(vaga.url)
        blocos.append("\n".join(linhas))
    blocos.append("Abra o app para analisar as que interessarem.")
    return assunto, "\n\n".join(blocos)


def montar_digest(vagas: list[Vaga]) -> str:
    """Resumo curto para o WhatsApp, cortado no limite da mensagem."""
    texto = f"Peão Bilíngue — {len(vagas)} vaga(s) nova(s)"
    for indice, vaga in enumerate(vagas):
        onde = _onde(vaga).replace(" | ", " — ")
        onde = f" — {onde}" if onde else ""
        bloco = f"\n\n{vaga.titulo}{onde} ({vaga.fonte})\n{vaga.url}"
        sufixo = f"\n\n+{len(vagas) - indice} vaga(s) no app"
        if len(texto) + len(bloco) + len(sufixo) > LIMITE_WHATSAPP:
            return texto + sufixo
        texto += bloco
    return texto
