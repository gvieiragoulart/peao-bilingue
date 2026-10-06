from vanhack_watcher.models import Search


def texto_da_vaga(vaga: dict) -> str:
    """Título, chamada, skills e descrição, que é onde os termos aparecem."""
    skills = vaga.get("skills") or []
    skills += [
        item["skill"]
        for chave in ("skills_obrigatorias", "skills_desejaveis")
        for item in vaga.get(chave) or []
        if isinstance(item, dict)
    ]
    partes = [
        vaga.get("titulo") or "",
        vaga.get("chamada") or "",
        vaga.get("descricao") or "",
        " ".join(str(skill) for skill in skills),
    ]
    return " ".join(partes).lower()


def casa(vaga: dict, busca: Search) -> bool:
    """Passa se alguma keyword aparece e nenhum termo excluído aparece."""
    texto = texto_da_vaga(vaga)
    if any(termo.lower() in texto for termo in busca.exclude or []):
        return False
    return any(termo.lower() in texto for termo in busca.keywords or [])


def buscas_que_casam(vaga: dict, buscas: list[Search]) -> list[str]:
    return [busca.name for busca in buscas if casa(vaga, busca)]
