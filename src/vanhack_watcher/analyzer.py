import json
from pathlib import Path

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from vanhack_watcher.config import settings
from vanhack_watcher.schemas import JobAnalysis

MAX_TOKENS = 16_000
TENTATIVAS = 3

SISTEMA = """Você é um mentor técnico de carreira especializado em vagas internacionais \
remotas e em relocação para engenheiros de software brasileiros.

Analise o encaixe entre o perfil do candidato e a vaga, sempre em português do Brasil.

Regras da análise:
- `fit_score` de 0 a 100, honesto: não infle para agradar.
- `preparacao`: passos concretos de estudo e preparação para esta vaga específica.
- `perguntas`: exatamente 20 perguntas de entrevista sobre os temas desta vaga,
  misturando técnicas e comportamentais.
- `gaps`: requisitos da vaga que faltam no perfil ou estão fracos.
- `melhorias_perfil`: o que mudar no perfil da VanHack, no CV e no LinkedIn para esta vaga.
  Cite itens concretos do perfil atual (ex.: "a skill X não aparece na lista de skills",
  "o headline não menciona Y"). Nada de conselho genérico.

A empresa contratante não é divulgada pela VanHack: não invente o nome dela."""


class AnaliseInvalida(RuntimeError):
    """O modelo não produziu uma análise válida dentro das tentativas."""


def _notas_do_usuario() -> str:
    caminho = Path(settings.profile_notes_path)
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


def montar_prompt(vaga: dict, perfil_texto: str, notas: str = "") -> str:
    partes = [
        "# Perfil do candidato (extraído da VanHack)",
        perfil_texto,
    ]
    if notas.strip():
        partes += ["", "# Notas do candidato (complemento manual)", notas.strip()]
    partes += [
        "",
        "# Vaga",
        json.dumps(vaga, ensure_ascii=False, indent=1),
        "",
        "Analise o encaixe entre o candidato e esta vaga.",
    ]
    return "\n".join(partes)


async def analisar(
    vaga: dict,
    perfil_texto: str,
    *,
    notas: str | None = None,
    client: AsyncAnthropic | None = None,
) -> JobAnalysis:
    """Analisa uma vaga contra o perfil, repetindo se a validação falhar.

    Usa structured output em vez de tool use forçado: `tool_choice` obrigatório
    devolve 400 nos modelos atuais, e aqui a ferramenta só existia para obter
    JSON validado de volta.
    """
    client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)
    notas = _notas_do_usuario() if notas is None else notas
    mensagens: list[dict] = [
        {"role": "user", "content": montar_prompt(vaga, perfil_texto, notas)}
    ]

    erro: Exception | None = None
    for _ in range(TENTATIVAS):
        resposta = None
        try:
            resposta = await client.messages.parse(
                model=settings.analysis_model,
                max_tokens=MAX_TOKENS,
                system=SISTEMA,
                messages=mensagens,
                output_format=JobAnalysis,
            )
            if resposta.stop_reason == "refusal":
                raise AnaliseInvalida(
                    f"O modelo recusou a análise: {resposta.stop_details}"
                )
            return JobAnalysis.model_validate(resposta.parsed_output)
        except ValidationError as falha:
            # O próprio SDK valida contra o schema, então a falha pode vir de lá
            # ou da revalidação; nos dois casos a correção é a mesma.
            erro = falha
            mensagens += [
                {"role": "assistant", "content": _texto_da_resposta(resposta)},
                {
                    "role": "user",
                    "content": (
                        "A análise anterior foi rejeitada na validação:\n"
                        f"{falha}\n\nRefaça respeitando exatamente o schema."
                    ),
                },
            ]

    raise AnaliseInvalida(f"Análise inválida após {TENTATIVAS} tentativas: {erro}")


def _texto_da_resposta(resposta: object) -> str:
    blocos = getattr(resposta, "content", []) or []
    return "".join(getattr(bloco, "text", "") for bloco in blocos) or "(sem texto)"
