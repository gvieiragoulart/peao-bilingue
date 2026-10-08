import pytest
from construtores import vaga

from peao_bilingue.adaptadores.notificacao import formatacao
from peao_bilingue.adaptadores.notificacao.email import Email
from peao_bilingue.adaptadores.notificacao.whatsapp import WhatsApp


def test_email_lista_as_vagas_novas_com_link_e_skills():
    assunto, corpo = formatacao.montar_email(
        [vaga("1", "Backend Python"), vaga("2", "Staff Engineer")]
    )

    assert assunto == "Peão Bilíngue — 2 vaga(s) nova(s)"
    assert "Backend Python (vanhack)" in corpo and "Staff Engineer (vanhack)" in corpo
    assert "https://exemplo.com/job/1" in corpo
    assert "Skills: Python" in corpo
    assert "Toronto - Canada | Hybrid | CAD $160k–200k /yr" in corpo
    assert "analisar" in corpo  # a análise é pedida no app


def test_email_cita_empresa_so_quando_a_fonte_publica():
    _, com_empresa = formatacao.montar_email([vaga(empresa="Acme Corp")])
    _, sem_empresa = formatacao.montar_email([vaga(empresa=None)])
    assert "Acme Corp" in com_empresa
    assert "None" not in sem_empresa


def test_digest_traz_titulo_link_e_fonte():
    digest = formatacao.montar_digest([vaga("1", "Alta"), vaga("2", "Baixa")])

    assert digest.startswith("Peão Bilíngue — 2 vaga(s) nova(s)")
    assert "Alta — Toronto - Canada (vanhack)" in digest
    assert "https://exemplo.com/job/2" in digest


def test_digest_respeita_o_limite_do_whatsapp():
    muitas = [vaga(str(n), f"Vaga numero {n} com titulo longo") for n in range(40)]
    digest = formatacao.montar_digest(muitas)

    assert len(digest) <= formatacao.LIMITE_WHATSAPP
    assert "no app" in digest  # avisa quantas ficaram de fora


def test_digest_sem_empresa_nao_imprime_none():
    # várias fontes não publicam a contratante
    assert "None" not in formatacao.montar_digest([vaga(empresa=None)])


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


async def test_email_manda_uma_mensagem_por_coleta(enviados: dict):
    await Email().notificar([vaga("1"), vaga("2")])
    assert enviados["email"] == ["Peão Bilíngue — 2 vaga(s) nova(s)"]


async def test_whatsapp_manda_um_unico_resumo(enviados: dict):
    await WhatsApp().notificar([vaga("1"), vaga("2")])
    assert len(enviados["whatsapp"]) == 1
