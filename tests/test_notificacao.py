import pytest
from construtores import analise, vaga

from peao_bilingue.adaptadores.notificacao import formatacao
from peao_bilingue.adaptadores.notificacao.email import Email
from peao_bilingue.adaptadores.notificacao.whatsapp import WhatsApp
from peao_bilingue.dominio.entidades import ResultadoAnalise


def resultado(
    fit: int = 82, *, fit_anterior: int | None = None, **ajustes_vaga
) -> ResultadoAnalise:
    return ResultadoAnalise(
        vaga=vaga(**ajustes_vaga), analise=analise(fit), fit_anterior=fit_anterior
    )


def test_email_tem_secoes_e_as_vinte_perguntas():
    assunto, corpo = formatacao.montar_email(resultado())

    assert assunto == "[82] Fullstack Staff Engineer · vanhack"
    for secao in ("RESUMO", "PREPARAÇÃO", "GAPS", "O QUE MELHORAR NO PERFIL"):
        assert secao in corpo
    assert "PERGUNTAS DE ENTREVISTA (20)" in corpo
    assert "20. Pergunta 20" in corpo
    assert "https://exemplo.com/job/12030" in corpo


def test_reanalise_mostra_o_fit_anterior():
    assunto, corpo = formatacao.montar_email(resultado(90, fit_anterior=70))

    assert assunto.startswith("[70→90]")
    assert "70 → 90/100" in corpo
    assert "reanálise" in corpo


def test_email_cita_empresa_quando_a_fonte_publica():
    _, corpo = formatacao.montar_email(resultado(empresa="Acme Corp"))
    assert "Acme Corp" in corpo


def test_digest_ordena_por_fit_e_traz_link_e_fonte():
    digest = formatacao.montar_digest(
        [
            resultado(40, id_externo="1", titulo="Baixa"),
            resultado(95, id_externo="2", titulo="Alta"),
        ]
    )

    assert digest.index("Alta") < digest.index("Baixa")
    assert "95 · Alta" in digest
    assert "https://exemplo.com/job/2" in digest
    assert "(vanhack)" in digest


def test_digest_avisa_quando_o_perfil_mudou():
    assert "Perfil atualizado" in formatacao.montar_digest(
        [resultado()], perfil_mudou=True
    )


def test_digest_respeita_o_limite_do_whatsapp():
    muitas = [
        resultado(50 + n, id_externo=str(n), titulo=f"Vaga numero {n} com titulo longo")
        for n in range(40)
    ]
    digest = formatacao.montar_digest(muitas)

    assert len(digest) <= formatacao.LIMITE_WHATSAPP
    assert "no app" in digest  # avisa quantas ficaram de fora


def test_digest_sem_empresa_nao_imprime_none():
    # várias fontes não publicam a contratante
    assert "None" not in formatacao.montar_digest([resultado(empresa=None)])


@pytest.fixture
def enviados(monkeypatch: pytest.MonkeyPatch) -> dict:
    capturado: dict = {"email": [], "whatsapp": []}

    async def email_fake(self, assunto, corpo):
        capturado["email"].append(assunto)

    async def whatsapp_fake(self, texto):
        capturado["whatsapp"].append(texto)

    monkeypatch.setattr(Email, "enviar", email_fake)
    monkeypatch.setattr(WhatsApp, "enviar", whatsapp_fake)
    return capturado


async def test_email_manda_uma_mensagem_por_vaga(enviados: dict):
    await Email().notificar(
        [resultado(60, id_externo="1"), resultado(80, id_externo="2")],
        perfil_mudou=False,
    )
    assert len(enviados["email"]) == 2


async def test_whatsapp_manda_um_unico_resumo(enviados: dict):
    await WhatsApp().notificar(
        [resultado(60, id_externo="1"), resultado(80, id_externo="2")],
        perfil_mudou=False,
    )
    assert len(enviados["whatsapp"]) == 1
