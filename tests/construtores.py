"""Construtores de entidades para os testes."""

from peao_bilingue.dominio.entidades import JobAnalysis, Perfil, Skill, Vaga


def vaga(
    id_externo: str = "12030",
    titulo: str = "Fullstack Staff Engineer",
    *,
    fonte: str = "vanhack",
    **ajustes,
) -> Vaga:
    base = {
        "fonte": fonte,
        "id_externo": id_externo,
        "url": f"https://exemplo.com/job/{id_externo}",
        "titulo": titulo,
        "local": "Toronto - Canada",
        "modalidade": "Hybrid",
        "salario": "CAD $160k–200k /yr",
        "descricao": "Série B, plataforma de comissões em Python e React.",
        "skills_obrigatorias": [Skill(nome="Python", anos="4 Year(s)")],
    }
    return Vaga(**{**base, **ajustes})


def analise(fit: int = 82, **ajustes) -> JobAnalysis:
    base = {
        "fit_score": fit,
        "resumo": "Bom encaixe em Python e React.",
        "preparacao": [
            "Revisar React 18",
            "Praticar system design",
            "Estudar o domínio",
        ],
        "perguntas": [f"Pergunta {n}" for n in range(1, 21)],
        "gaps": ["Sem experiência com comissionamento"],
        "melhorias_perfil": [
            "Adicionar Django às skills",
            "Citar escala no headline",
            "Atualizar o LinkedIn",
        ],
    }
    return JobAnalysis(**{**base, **ajustes})


def perfil(cargo: str = "Software Developer") -> Perfil:
    return Perfil(
        dados={"cargo": cargo},
        texto=f"Cargo: {cargo}\nSkills principais: Python (5 years)",
        content_hash=f"hash-{cargo}",
    )
