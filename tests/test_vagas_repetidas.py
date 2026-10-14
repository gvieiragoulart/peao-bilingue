"""A mesma vaga publicada em sites diferentes: guardada uma vez, com os outros links."""

from construtores import vaga
from dubles import FonteFake, NotificadorFake
from sqlalchemy import update
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from peao_bilingue.adaptadores.persistencia.sqlite import RepositorioSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import VagaTabela
from peao_bilingue.aplicacao.execucao import Servicos, executar
from peao_bilingue.dominio.buscas import Busca
from peao_bilingue.dominio.coleta import Gatilho
from peao_bilingue.dominio.vagas import Anuncio

# --- assinatura -------------------------------------------------------------


def test_assinatura_ignora_maiusculas_pontuacao_e_acento() -> None:
    uma = vaga("1", "Senior React Full-stack Developer", empresa="Lemon.io")
    outra = vaga("2", "senior react full stack developer", empresa="lemon io")
    assert uma.assinatura() == outra.assinatura() != ""
    assert (
        vaga("3", "Líder Técnico", empresa="Açaí").assinatura()
        == vaga("4", "lider tecnico", empresa="acai").assinatura()
    )


def test_sem_empresa_nao_tem_assinatura() -> None:
    # A VanHack nunca publica a empresa: só o título juntaria vagas diferentes.
    assert vaga("1", empresa=None).assinatura() == ""
    assert vaga("1", empresa=" - ").assinatura() == ""


def test_titulo_diferente_e_outra_vaga() -> None:
    assert (
        vaga("1", "Senior React Developer", empresa="Lemon.io").assinatura()
        != vaga("2", "Senior .NET Developer", empresa="Lemon.io").assinatura()
    )


# --- repositório ------------------------------------------------------------


def test_reconhece_a_mesma_vaga_de_outra_fonte(repositorio: RepositorioSQLite) -> None:
    original = vaga("a", "React Developer", fonte="remotive", empresa="Lemon.io")
    repositorio.salvar_vaga(original, ["React"])

    repetida = vaga("b", "React developer", fonte="himalayas", empresa="lemon.io")
    assert repositorio.original_de(repetida) == "remotive:a"


def test_na_mesma_fonte_titulo_igual_e_outra_vaga(
    repositorio: RepositorioSQLite,
) -> None:
    # Remote OK: "Frontend Engineer" na Bjak, uma em Singapura e outra na Irlanda.
    repositorio.salvar_vaga(
        vaga("1", "Frontend Engineer", fonte="remoteok", empresa="Bjak"), ["React"]
    )
    outra = vaga("2", "Frontend Engineer", fonte="remoteok", empresa="Bjak")
    assert repositorio.original_de(outra) is None


def test_sem_empresa_nunca_repete(repositorio: RepositorioSQLite) -> None:
    repositorio.salvar_vaga(vaga("1", "Backend", fonte="vanhack"), ["Python"])
    assert repositorio.original_de(vaga("2", "Backend", fonte="remotive")) is None


def test_a_repetida_some_da_lista_e_vira_link_na_original(
    repositorio: RepositorioSQLite,
) -> None:
    repositorio.salvar_vaga(vaga("a", fonte="remotive", empresa="Lemon.io"), ["X"])
    repositorio.salvar_vaga(
        vaga("b", fonte="himalayas", empresa="Lemon.io"), ["X"], repete="remotive:a"
    )

    [item] = repositorio.listar_vagas()
    assert item.vaga.chave == "remotive:a"
    assert item.tambem_em == [
        Anuncio(fonte="himalayas", url="https://exemplo.com/job/b")
    ]
    # Guardada mesmo assim: a coleta seguinte não a detalha de novo.
    assert repositorio.vaga_existe("himalayas:b")


def test_vagas_de_antes_da_assinatura_sao_juntadas_ao_abrir_o_banco() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    antigo = RepositorioSQLite(engine)
    antigo.salvar_vaga(vaga("a", "React", fonte="remotive", empresa="Lemon.io"), [])
    antigo.salvar_vaga(vaga("b", "React", fonte="himalayas", empresa="lemon.io"), [])
    antigo.salvar_vaga(vaga("c", "React", fonte="remotive", empresa=None), [])
    # Como um banco de antes da coluna: nada calculado, nada juntado.
    with Session(engine) as sessao:
        sessao.exec(update(VagaTabela).values(assinatura=None, repete=None))
        sessao.commit()
    assert len(antigo.listar_vagas()) == 3

    reaberto = RepositorioSQLite(engine)

    chaves = sorted(item.vaga.chave for item in reaberto.listar_vagas())
    assert chaves == ["remotive:a", "remotive:c"]


# --- coleta -----------------------------------------------------------------


async def test_repetida_de_outra_fonte_nao_e_nova_nem_vai_no_aviso(
    repositorio: RepositorioSQLite,
) -> None:
    repositorio.salvar_busca(Busca(nome="Python", keywords=["python"]))
    primeira = FonteFake(
        nome="remotive", vagas=[vaga("a", "Backend Python", empresa="Lemon.io")]
    )
    segunda = FonteFake(
        nome="himalayas",
        vagas=[
            vaga("b", "Backend Python", empresa="lemon.io"),
            vaga("c", "Data Python", empresa="lemon.io"),
        ],
    )
    notificador = NotificadorFake()
    servicos = Servicos(
        buscas=repositorio,
        vagas=repositorio,
        perfis=repositorio,
        execucoes=repositorio,
        fontes=[primeira, segunda],
        notificadores=[notificador],
    )

    resultado = await executar(servicos, Gatilho.agendado, avisar=True)

    assert resultado.vagas_novas == 2
    [avisadas] = notificador.recebido
    assert [v.chave for v in avisadas] == ["remotive:a", "himalayas:c"]
    assert repositorio.vaga_existe("himalayas:b")
