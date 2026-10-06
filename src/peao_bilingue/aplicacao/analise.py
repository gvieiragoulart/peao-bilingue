import json
import re
from pathlib import Path

from pydantic import ValidationError

from peao_bilingue.configuracao import settings
from peao_bilingue.dominio.entidades import JobAnalysis, Mensagem, Vaga
from peao_bilingue.dominio.erros import AnaliseInvalida
from peao_bilingue.dominio.portas import ProvedorLLM

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


def _notas_do_usuario() -> str:
    caminho = Path(settings.profile_notes_path)
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


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


async def analisar(
    vaga: Vaga,
    perfil_texto: str,
    provedor: ProvedorLLM,
    *,
    notas: str | None = None,
) -> JobAnalysis:
    """Analisa uma vaga contra o perfil, devolvendo o erro ao modelo se a validação falhar.

    A validação mora aqui, e não no provedor: nenhum deles garante no servidor
    limites como "exatamente 20 perguntas".
    """
    notas = _notas_do_usuario() if notas is None else notas
    mensagens = [
        Mensagem(role="user", content=montar_prompt(vaga, perfil_texto, notas))
    ]

    erro: ValidationError | None = None
    for _ in range(TENTATIVAS):
        resposta = await provedor.gerar_json(SISTEMA, mensagens, JobAnalysis)
        if resposta.recusou:
            raise AnaliseInvalida(f"O modelo recusou a análise: {resposta.motivo}")
        try:
            return JobAnalysis.model_validate_json(_sem_cerca(resposta.texto))
        except ValidationError as falha:
            erro = falha
            mensagens += [
                Mensagem(
                    role="assistant", content=resposta.texto or "(resposta vazia)"
                ),
                Mensagem(
                    role="user",
                    content=(
                        "A análise anterior foi rejeitada na validação:\n"
                        f"{falha}\n\nRefaça respeitando exatamente o schema."
                    ),
                ),
            ]

    raise AnaliseInvalida(f"Análise inválida após {TENTATIVAS} tentativas: {erro}")
