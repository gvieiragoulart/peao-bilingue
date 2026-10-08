"""Análise de uma vaga por um LLM, pedida pelo usuário vaga a vaga.

O prompt, a validação e o retry ficam aqui, iguais para todos os provedores.
"""

import json
import re

from pydantic import BaseModel, ValidationError

from peao_bilingue.dominio.analise import JobAnalysis, Mensagem, ProvedorLLM
from peao_bilingue.dominio.erros import AnaliseInvalida, PerfilAusente
from peao_bilingue.dominio.repositorio import Repositorio
from peao_bilingue.dominio.vagas import Vaga

TENTATIVAS = 3

SISTEMA = """Você é um mentor técnico de carreira especializado em vagas internacionais \
remotas e em relocação para engenheiros de software brasileiros.

Analise o encaixe entre o perfil do candidato e a vaga, sempre em português do Brasil.
Responda apenas com o JSON pedido.

Regras da análise:
- `fit_score` de 0 a 100, honesto: não infle para agradar.
- `preparacao`: ao menos 3 passos concretos de estudo e preparação para esta vaga específica.
- `perguntas`: exatamente 20 perguntas de entrevista sobre os temas desta vaga,
  misturando técnicas e comportamentais.
- `gaps`: requisitos da vaga que faltam no perfil ou estão fracos.
- `melhorias_perfil`: ao menos 3 mudanças no perfil, no CV e no LinkedIn para esta vaga.
  Cite itens concretos do perfil atual (ex.: "a skill X não aparece na lista de skills",
  "o headline não menciona Y"). Nada de conselho genérico.

Se a vaga não informa a empresa contratante, não invente o nome dela."""

_CERCA_DE_CODIGO = re.compile(r"^```(?:json)?\s*|\s*```$")


def montar_prompt(vaga: Vaga, perfil_texto: str, notas: str = "") -> str:
    partes = ["# Perfil do candidato", perfil_texto]
    if notas.strip():
        partes += ["", "# Notas do candidato (complemento manual)", notas.strip()]
    partes += [
        "",
        "# Vaga",
        json.dumps(
            vaga.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=1,
        ),
        "",
        "Analise o encaixe entre o candidato e esta vaga.",
    ]
    return "\n".join(partes)


def _sem_cerca(texto: str) -> str:
    """Modelos menores às vezes embrulham o JSON em ```json ... ```."""
    return _CERCA_DE_CODIGO.sub("", texto.strip())


async def gerar_validado[M: BaseModel](
    provedor: ProvedorLLM, sistema: str, prompt: str, schema: type[M]
) -> M:
    """Pede JSON ao provedor e valida, devolvendo o erro ao modelo se falhar.

    A validação mora aqui, e não no provedor: nenhum deles garante no servidor
    limites como "exatamente 20 perguntas".
    """
    mensagens = [Mensagem(role="user", content=prompt)]
    erro: ValidationError | None = None
    for _ in range(TENTATIVAS):
        resposta = await provedor.gerar_json(sistema, mensagens, schema)
        if resposta.recusou:
            raise AnaliseInvalida(f"O modelo recusou a análise: {resposta.motivo}")
        try:
            return schema.model_validate_json(_sem_cerca(resposta.texto))
        except ValidationError as falha:
            erro = falha
            mensagens += [
                Mensagem(
                    role="assistant", content=resposta.texto or "(resposta vazia)"
                ),
                Mensagem(
                    role="user",
                    content=(
                        "A resposta anterior foi rejeitada na validação:\n"
                        f"{falha}\n\nRefaça respeitando exatamente o schema."
                    ),
                ),
            ]
    raise AnaliseInvalida(f"Resposta inválida após {TENTATIVAS} tentativas: {erro}")


async def analisar(
    vaga: Vaga,
    perfil_texto: str,
    provedor: ProvedorLLM,
    *,
    notas: str = "",
) -> JobAnalysis:
    """`notas`: complemento que o usuário escreve sobre si (vem de fora: a
    aplicação não lê arquivo nem configuração)."""
    prompt = montar_prompt(vaga, perfil_texto, notas)
    return await gerar_validado(provedor, SISTEMA, prompt, JobAnalysis)


async def analisar_vaga(
    repositorio: Repositorio,
    provedor: ProvedorLLM,
    chave: str,
    *,
    perfil_de: str | None = None,
    notas: str = "",
) -> JobAnalysis:
    """Analisa uma vaga guardada e grava a análise junto do perfil usado.

    O perfil é o cadastrado na fonte da própria vaga; `perfil_de` escolhe o de
    outra fonte (o caminho para fontes sem perfil, como as APIs públicas).
    """
    vaga = repositorio.obter_vaga(chave)
    if vaga is None:
        raise LookupError(f"Vaga {chave} não encontrada.")
    fonte = perfil_de or vaga.fonte
    salvo = repositorio.ultimo_perfil(fonte)
    if salvo is None:
        raise PerfilAusente(
            f"Nenhum perfil da fonte {fonte} foi lido ainda. Leia na aba Perfil "
            "ou escolha o perfil de outra fonte."
        )
    perfil_id, perfil = salvo
    analise = await analisar(vaga, perfil.texto, provedor, notas=notas)
    repositorio.salvar_analise(
        chave,
        analise,
        provedor=provedor.nome,
        modelo=provedor.modelo,
        perfil_id=perfil_id,
    )
    return analise
