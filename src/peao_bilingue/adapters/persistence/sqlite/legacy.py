"""Moves a database from before the code was in English to the current schema.

Until 2026-10-17 the tables, columns, enum values and the keys inside the JSON columns
were in Portuguese (`vaga`, `titulo`, `nova`...). On the first open after the update,
this copies everything into the English tables and drops the old ones, in a single
transaction, after backing up the file next to it.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, inspect, text
from sqlmodel import SQLModel

from peao_bilingue.domain.profile import profile_hash

logger = logging.getLogger(__name__)

LEGACY_TABLES = ("analise", "vaga", "perfil", "busca", "execucao")

# Keys inside the JSON of a job (the Job model, its skills and the sources' extras).
JOB_KEYS = {
    "fonte": "source",
    "id_externo": "external_id",
    "titulo": "title",
    "local": "location",
    "modalidade": "work_mode",
    "salario": "salary",
    "publicada_em": "published_at",
    "empresa": "company",
    "descricao": "description",
    "skills_obrigatorias": "required_skills",
    "skills_desejaveis": "preferred_skills",
    "idiomas": "languages",
    "nome": "name",
    "anos": "years",
    "chamada": "headline",
    "local_exigido": "required_location",
    "fatos": "facts",
    "tipo": "job_type",
    "tipos": "job_types",
    "categoria": "category",
    "paises": "countries",
    "visto": "visa_sponsorship",
    "senioridade": "seniority",
}
ANALYSIS_KEYS = {
    "resumo": "summary",
    "preparacao": "preparation",
    "perguntas": "questions",
    "melhorias_perfil": "profile_improvements",
}
PROFILE_KEYS = {
    "cargo": "role",
    "anos_como_profissional_ti": "it_years",
    "lideranca": "leadership",
    "anos_de_lideranca": "leadership_years",
    "aberto_a_remoto": "open_to_remote",
    "skills_principais": "main_skills",
    "skills_secundarias": "secondary_skills",
    "idiomas": "languages",
    "idioma": "language",
    "nivel": "level",
    "ingles_avaliado_no_video": "video_english_level",
    "experiencias": "experiences",
    "empresa": "company",
    "setor": "industry",
    "cargos": "roles",
    "cargo_e_periodo": "role_and_period",
    "descricao": "description",
    "formacao": "education",
    "outros_campos": "other_fields",
    "anos": "years",
}
# The keys of these maps are the questions as VanHack words them: never renamed.
VERBATIM = {"outros_campos", "other_fields"}

JOB_STATUS = {
    "nova": "new",
    "estudando": "studying",
    "aplicada": "applied",
    "descartada": "discarded",
}
TRIGGERS = {"manual": "manual", "agendado": "scheduled"}
RUN_STATUS = {
    "rodando": "running",
    "ok": "ok",
    "erro": "error",
    "login_required": "login_required",
}


def needs_migration(engine: Engine) -> bool:
    return inspect(engine).has_table("vaga")


def migrate_legacy_schema(engine: Engine) -> None:
    """Copies a Portuguese-schema database into the current tables, once."""
    if not needs_migration(engine):
        return
    backup = _backup(engine)
    with engine.begin() as connection:
        SQLModel.metadata.create_all(connection)
        _copy_searches(connection)
        _copy_profiles(connection)
        _copy_jobs(connection)
        _copy_analyses(connection)
        _copy_runs(connection)
        for table in LEGACY_TABLES:
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')
    logger.info("Database moved to the English schema (backup: %s).", backup)


def rename_keys(value: Any, keys: dict[str, str]) -> Any:
    """Renames dict keys at every level, except inside the VERBATIM maps."""
    if isinstance(value, list):
        return [rename_keys(item, keys) for item in value]
    if not isinstance(value, dict):
        return value
    renamed = {}
    for key, item in value.items():
        new_key = keys.get(key, key)
        renamed[new_key] = item if key in VERBATIM else rename_keys(item, keys)
    return renamed


def _backup(engine: Engine) -> Path | None:
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    source = Path(database)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    target = source.with_name(f"{source.stem}.before-english-{stamp}.db")
    # The backup API copies a consistent snapshot, even with pages still in the WAL.
    with sqlite3.connect(source) as origin, sqlite3.connect(target) as copy:
        origin.backup(copy)
    return target


def _rows(connection: Connection, table: str) -> list[dict[str, Any]]:
    if not inspect(connection).has_table(table):
        return []
    return [
        dict(row)
        for row in connection.exec_driver_sql(f'SELECT * FROM "{table}"').mappings()
    ]


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _job_key(key: str | None) -> str | None:
    # Himalayas ids used "sem-empresa" when the company had no slug.
    return key.replace(":sem-empresa/", ":no-company/") if key else key


def _copy_searches(connection: Connection) -> None:
    for row in _rows(connection, "busca"):
        connection.execute(
            text(
                "INSERT INTO search (id, name, keywords, exclude, sources, active, "
                "created_at) VALUES (:id, :name, :keywords, :exclude, :sources, "
                ":active, :created_at)"
            ),
            {
                "id": row["id"],
                "name": row["nome"],
                "keywords": row["keywords"],
                "exclude": row["exclude"],
                "sources": row.get("fontes") or "[]",
                "active": row.get("ativa", 1),
                "created_at": row["criada_em"],
            },
        )


def _copy_profiles(connection: Connection) -> None:
    for row in _rows(connection, "perfil"):
        data = rename_keys(_json(row["dados"]) or {}, PROFILE_KEYS)
        connection.execute(
            text(
                "INSERT INTO profile (id, source, data, text, content_hash, read_at) "
                "VALUES (:id, :source, :data, :text, :content_hash, :read_at)"
            ),
            {
                "id": row["id"],
                "source": row.get("fonte") or "vanhack",
                "data": _dump(data),
                # The readable text stays as it was; the next change rewrites it.
                "text": row.get("texto") or "",
                # Recomputed so the next reading doesn't look like a change.
                "content_hash": profile_hash(data),
                "read_at": row["lido_em"],
            },
        )


def _copy_jobs(connection: Connection) -> None:
    for row in _rows(connection, "vaga"):
        data = rename_keys(_json(row["dados"]) or {}, JOB_KEYS)
        if isinstance(data.get("external_id"), str):
            data["external_id"] = data["external_id"].replace(
                "sem-empresa/", "no-company/"
            )
        connection.execute(
            text(
                "INSERT INTO job (key, source, data, searches, status, seen_at, "
                "fingerprint, duplicate_of) VALUES (:key, :source, :data, :searches, "
                ":status, :seen_at, NULL, :duplicate_of)"
            ),
            {
                "key": _job_key(row["chave"]),
                "source": row["fonte"],
                "data": _dump(data),
                "searches": row.get("buscas") or "[]",
                "status": JOB_STATUS.get(row.get("status") or "", "new"),
                "seen_at": row["vista_em"],
                # The fingerprint is recalculated on open; the merge is kept.
                "duplicate_of": _job_key(row.get("repete")),
            },
        )


def _copy_analyses(connection: Connection) -> None:
    for row in _rows(connection, "analise"):
        connection.execute(
            text(
                "INSERT INTO analysis (id, job_key, data, provider, model, profile_id, "
                "created_at) VALUES (:id, :job_key, :data, :provider, :model, "
                ":profile_id, :created_at)"
            ),
            {
                "id": row["id"],
                "job_key": _job_key(row["vaga_chave"]),
                "data": _dump(rename_keys(_json(row["dados"]) or {}, ANALYSIS_KEYS)),
                "provider": row["provedor"],
                "model": row["modelo"],
                "profile_id": row.get("perfil_id"),
                "created_at": row["criada_em"],
            },
        )


def _copy_runs(connection: Connection) -> None:
    for row in _rows(connection, "execucao"):
        connection.execute(
            text(
                'INSERT INTO run (id, "trigger", status, started_at, finished_at, '
                "listed_jobs, new_jobs, error, artifact) VALUES (:id, :trigger, "
                ":status, :started_at, :finished_at, :listed_jobs, :new_jobs, :error, "
                ":artifact)"
            ),
            {
                "id": row["id"],
                "trigger": TRIGGERS.get(row.get("gatilho") or "", "manual"),
                "status": RUN_STATUS.get(row.get("status") or "", "error"),
                "started_at": row["iniciada_em"],
                "finished_at": row.get("finalizada_em"),
                "listed_jobs": row.get("vagas_listadas") or 0,
                "new_jobs": row.get("vagas_novas") or 0,
                "error": row.get("erro"),
                "artifact": row.get("artefato"),
            },
        )
