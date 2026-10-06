import pytest

from vanhack_watcher import notifier
from vanhack_watcher.schemas import JobAnalysis


def analise(fit: int = 82) -> JobAnalysis:
    return JobAnalysis(
        fit_score=fit,
        resumo="Bom encaixe em Python.",
        preparacao=["Revisar React", "System design", "Estudar o domínio"],
        perguntas=[f"Pergunta {n}" for n in range(1, 21)],
        gaps=["Sem experiência com comissionamento"],
        melhorias_perfil=["Adicionar Django", "Citar escala", "Atualizar LinkedIn"],
    )


def vaga(job_id: str = "12030", titulo: str = "Fullstack Staff Engineer") -> dict:
    return {
        "id": job_id,
        "titulo": titulo,
        "url": f"https://app.vanhack.com/job/{job_id}",
        "local": "Toronto - Canada",
        "modalidade": "Hybrid",
        "salario": "CAD $160k–200k /yr",
    }


@pytest.fixture
def envios(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Captura emails e mensagens em vez de mandar de verdade."""
    capturado: dict = {"emails": [], "whatsapp": []}

    async def email_fake(assunto, corpo):
        capturado["emails"].append((assunto, corpo))

    async def whatsapp_fake(texto):
        capturado["whatsapp"].append(texto)

    monkeypatch.setattr(notifier, "enviar_email", email_fake)
    monkeypatch.setattr(notifier, "enviar_whatsapp", whatsapp_fake)
    return capturado


def test_email_tem_secoes_e_as_vinte_perguntas():
    assunto, corpo = notifier.montar_email(vaga(), analise())

    assert assunto == "[VanHack 82] Fullstack Staff Engineer"
    for secao in ("RESUMO", "PREPARAÇÃO", "GAPS", "O QUE MELHORAR NO PERFIL"):
        assert secao in corpo
    assert "PERGUNTAS DE ENTREVISTA (20)" in corpo
    assert "20. Pergunta 20" in corpo
    assert "https://app.vanhack.com/job/12030" in corpo


def test_reanalise_mostra_o_fit_anterior():
    assunto, corpo = notifier.montar_email(vaga(), analise(90), fit_anterior=70)

    assert assunto.startswith("[VanHack 70→90]")
    assert "70 → 90/100" in corpo
    assert "reanálise" in corpo


def test_digest_ordena_por_fit_e_traz_o_link():
    resultados = [(vaga("1", "Baixa"), analise(40)), (vaga("2", "Alta"), analise(95))]

    digest = notifier.montar_digest(resultados)

    assert digest.index("Alta") < digest.index("Baixa")
    assert "95 · Alta" in digest
    assert "https://app.vanhack.com/job/2" in digest


def test_digest_avisa_quando_o_perfil_mudou():
    digest = notifier.montar_digest([(vaga(), analise())], perfil_mudou=True)
    assert "Perfil atualizado" in digest


def test_digest_respeita_o_limite_do_whatsapp():
    muitas = [
        (vaga(str(n), f"Vaga numero {n} com titulo longo"), analise(50 + n))
        for n in range(40)
    ]

    digest = notifier.montar_digest(muitas)

    assert len(digest) <= notifier.LIMITE_WHATSAPP
    assert "no painel" in digest  # avisa quantas ficaram de fora


def test_digest_nao_cita_empresa():
    # a VanHack não publica a contratante; o formato não pode depender dela
    digest = notifier.montar_digest([(vaga(), analise())])
    assert "empresa" not in digest.lower()
    assert "None" not in digest


async def test_envia_um_email_por_vaga_e_um_digest(envios: dict):
    resultados = [(vaga("1"), analise(60)), (vaga("2"), analise(80))]

    await notifier.notificar(resultados, dry_run=False)

    assert len(envios["emails"]) == 2
    assert len(envios["whatsapp"]) == 1


async def test_dry_run_nao_envia_nada(envios: dict):
    await notifier.notificar([(vaga(), analise())], dry_run=True)

    assert envios["emails"] == []
    assert envios["whatsapp"] == []


async def test_sem_resultados_nao_manda_digest_vazio(envios: dict):
    await notifier.notificar([], dry_run=False)

    assert envios["emails"] == []
    assert envios["whatsapp"] == []


async def test_fit_anterior_chega_ao_email_da_reanalise(envios: dict):
    await notifier.notificar(
        [(vaga("12030"), analise(88))], fits_anteriores={"12030": 61}, dry_run=False
    )

    assunto, _ = envios["emails"][0]
    assert assunto.startswith("[VanHack 61→88]")
