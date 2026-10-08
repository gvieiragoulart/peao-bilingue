from typing import Any

from sqlmodel import Session, col, select

from peao_bilingue.adaptadores.persistencia.sqlite.banco import BaseSQLite
from peao_bilingue.adaptadores.persistencia.sqlite.tabelas import PerfilTabela
from peao_bilingue.dominio.perfil import Perfil, RepositorioPerfis


def ultimo_perfil_da_fonte(sessao: Session, fonte: str) -> PerfilTabela | None:
    consulta = (
        select(PerfilTabela)
        .where(PerfilTabela.fonte == fonte)
        .order_by(col(PerfilTabela.id).desc())
    )
    return sessao.exec(consulta).first()


def _id(linha: PerfilTabela) -> int:
    # Linha lida do banco ou já gravada: o id existe; None aqui seria bug.
    if linha.id is None:
        raise RuntimeError("Snapshot de perfil sem id.")
    return linha.id


def _diferencas(antes: dict[str, Any], depois: dict[str, Any]) -> list[str]:
    chaves = set(antes) | set(depois)
    return sorted(chave for chave in chaves if antes.get(chave) != depois.get(chave))


class PerfisSQLite(BaseSQLite, RepositorioPerfis):
    def salvar_perfil(self, perfil: Perfil) -> tuple[int, bool]:
        with self._sessao() as sessao:
            atual = ultimo_perfil_da_fonte(sessao, perfil.fonte)
            if atual and atual.content_hash == perfil.content_hash:
                return _id(atual), False
            linha = PerfilTabela(**perfil.model_dump())
            sessao.add(linha)
            sessao.commit()
            sessao.refresh(linha)
            return _id(linha), True

    def ultimo_perfil(self, fonte: str) -> tuple[int, Perfil] | None:
        with self._sessao() as sessao:
            linha = ultimo_perfil_da_fonte(sessao, fonte)
            if linha is None:
                return None
            return _id(linha), Perfil.model_validate(linha, from_attributes=True)

    def fontes_com_perfil(self) -> list[str]:
        consulta = select(PerfilTabela.fonte).distinct().order_by(PerfilTabela.fonte)
        with self._sessao() as sessao:
            return list(sessao.exec(consulta))

    def historico_perfil(self, fonte: str) -> list[dict[str, Any]]:
        consulta = (
            select(PerfilTabela)
            .where(PerfilTabela.fonte == fonte)
            .order_by(col(PerfilTabela.id).desc())
        )
        with self._sessao() as sessao:
            linhas = list(sessao.exec(consulta))
        historico = []
        for indice, linha in enumerate(linhas):
            anterior = linhas[indice + 1] if indice + 1 < len(linhas) else None
            historico.append(
                {
                    "id": linha.id,
                    "lido_em": linha.lido_em,
                    "content_hash": linha.content_hash,
                    "campos_alterados": _diferencas(
                        anterior.dados if anterior else {}, linha.dados
                    ),
                }
            )
        return historico
