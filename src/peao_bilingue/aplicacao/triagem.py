"""Triagem: nota rápida de um LLM barato antes da análise completa.

Com Ollama na triagem e Claude na análise, só as vagas acima do limiar gastam
crédito. O prompt é curto de propósito — modelos de 7–8B rodando em 6 GB de VRAM
lidam mal com contexto longo e tarefas compostas.
"""

from peao_bilingue.aplicacao.analise import gerar_validado
from peao_bilingue.dominio.entidades import Triagem, Vaga
from peao_bilingue.dominio.portas import ProvedorLLM

SISTEMA_TRIAGEM = """Você faz a triagem de vagas para um engenheiro de software brasileiro.
Dê uma nota de encaixe de 0 a 100 entre o perfil e a vaga, e um motivo de uma frase.
Seja rigoroso: requisito obrigatório ausente no perfil derruba a nota.
Responda apenas com o JSON pedido, em português do Brasil."""

LIMITE_DESCRICAO = 2_500


def montar_prompt_triagem(vaga: Vaga, perfil_texto: str) -> str:
    obrigatorias = ", ".join(skill.nome for skill in vaga.skills_obrigatorias) or "-"
    desejaveis = ", ".join(skill.nome for skill in vaga.skills_desejaveis) or "-"
    return "\n".join(
        [
            "# Perfil",
            perfil_texto,
            "",
            "# Vaga",
            f"Título: {vaga.titulo}",
            f"Local: {vaga.local or '-'} | Modalidade: {vaga.modalidade or '-'}",
            f"Skills obrigatórias: {obrigatorias}",
            f"Skills desejáveis: {desejaveis}",
            f"Descrição: {vaga.descricao[:LIMITE_DESCRICAO]}",
        ]
    )


async def triar(vaga: Vaga, perfil_texto: str, provedor: ProvedorLLM) -> Triagem:
    return await gerar_validado(
        provedor, SISTEMA_TRIAGEM, montar_prompt_triagem(vaga, perfil_texto), Triagem
    )
