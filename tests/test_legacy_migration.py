"""A database from before the code was in English moves to the current schema intact.

The old schema below is the one the app created up to 2026-10-16 (Portuguese tables,
columns, enum values and JSON keys), including leftover columns from older versions.
"""

import json
from pathlib import Path

import pytest
from queries import saved_analysis, saved_profile
from sqlalchemy import Engine, inspect
from sqlmodel import create_engine

from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.adapters.persistence.sqlite.legacy import rename_keys
from peao_bilingue.domain.collection import RunStatus, Trigger
from peao_bilingue.domain.jobs import JobStatus
from peao_bilingue.domain.profile import profile_hash

OLD_SCHEMA = [
    (
        "CREATE TABLE busca (id INTEGER PRIMARY KEY, nome VARCHAR NOT NULL, keywords JSON, "
        "exclude JSON, fontes JSON, ativa BOOLEAN NOT NULL, criada_em DATETIME NOT NULL)"
    ),
    (
        "CREATE TABLE vaga (chave VARCHAR PRIMARY KEY, fonte VARCHAR NOT NULL, dados JSON, "
        "buscas JSON, status VARCHAR NOT NULL, vista_em DATETIME NOT NULL, triagem JSON, "
        "assinatura VARCHAR, repete VARCHAR)"
    ),
    (
        "CREATE TABLE perfil (id INTEGER PRIMARY KEY, fonte VARCHAR NOT NULL, dados JSON, "
        "texto VARCHAR NOT NULL, content_hash VARCHAR NOT NULL, lido_em DATETIME NOT NULL)"
    ),
    (
        "CREATE TABLE analise (id INTEGER PRIMARY KEY, vaga_chave VARCHAR NOT NULL, "
        "dados JSON, provedor VARCHAR NOT NULL, modelo VARCHAR NOT NULL, perfil_id INTEGER, "
        "criada_em DATETIME NOT NULL)"
    ),
    (
        "CREATE TABLE execucao (id INTEGER PRIMARY KEY, gatilho VARCHAR NOT NULL, "
        "status VARCHAR NOT NULL, iniciada_em DATETIME NOT NULL, finalizada_em DATETIME, "
        "vagas_listadas INTEGER NOT NULL, vagas_novas INTEGER NOT NULL, "
        "vagas_analisadas INTEGER NOT NULL, perfil_mudou BOOLEAN NOT NULL, erro VARCHAR, "
        "artefato VARCHAR, vagas_barradas_na_triagem INTEGER NOT NULL DEFAULT 0)"
    ),
]

OLD_JOB = {
    "fonte": "remotive",
    "id_externo": "1",
    "url": "https://remotive.com/job/1",
    "titulo": "Backend Python",
    "local": "Worldwide",
    "modalidade": "Remote",
    "salario": "$90k",
    "skills": ["python"],
    "publicada_em": "2026-10-01",
    "extras": {"via": "Remotive", "tipo": "full_time", "chamada": "BACKEND"},
    "empresa": "Acme",
    "descricao": "Python and Django.",
    "skills_obrigatorias": [{"nome": "Python", "anos": "5 Year(s)"}],
    "skills_desejaveis": [],
    "idiomas": ["English"],
}
OLD_PROFILE = {
    "cargo": "Software Developer",
    "anos_como_profissional_ti": "5 years",
    "skills_principais": [{"skill": "Python", "anos": "5 years"}],
    "idiomas": [{"idioma": "English", "nivel": "Advanced"}],
    "experiencias": [
        {
            "empresa": "Acme",
            "setor": "Internet",
            "cargos": [
                {"cargo_e_periodo": "Engineer 2025", "descricao": "Built things"}
            ],
        }
    ],
    # the keys of this map are VanHack's own questions: never renamed
    "outros_campos": {"Pronouns": "He/Him", "cargo": "kept as is"},
}
OLD_ANALYSIS = {
    "fit_score": 77,
    "resumo": "Good fit.",
    "preparacao": ["a", "b", "c"],
    "perguntas": [f"Q{n}" for n in range(20)],
    "gaps": [],
    "melhorias_perfil": ["x", "y", "z"],
}


def _old_database(path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in OLD_SCHEMA:
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql(
            "INSERT INTO busca VALUES (1, 'Python', '[\"python\"]', '[]', '[]', 1, "
            "'2026-10-06 10:00:00')"
        )
        connection.exec_driver_sql(
            "INSERT INTO perfil VALUES (1, 'vanhack', ?, 'Cargo: Software Developer', "
            "'old-hash', '2026-10-06 10:00:00')",
            (json.dumps(OLD_PROFILE),),
        )
        connection.exec_driver_sql(
            "INSERT INTO vaga VALUES ('remotive:1', 'remotive', ?, '[\"Python\"]', "
            "'aplicada', '2026-10-06 10:00:00', NULL, NULL, NULL)",
            (json.dumps(OLD_JOB),),
        )
        connection.exec_driver_sql(
            "INSERT INTO vaga VALUES ('himalayas:sem-empresa/dev', 'himalayas', ?, "
            "'[]', 'nova', '2026-10-06 11:00:00', NULL, NULL, NULL)",
            (
                json.dumps(
                    {**OLD_JOB, "fonte": "himalayas", "id_externo": "sem-empresa/dev"}
                ),
            ),
        )
        connection.exec_driver_sql(
            "INSERT INTO analise VALUES (1, 'remotive:1', ?, 'anthropic', 'claude', 1, "
            "'2026-10-06 12:00:00')",
            (json.dumps(OLD_ANALYSIS),),
        )
        connection.exec_driver_sql(
            "INSERT INTO execucao VALUES (7, 'agendado', 'erro', '2026-10-06 08:00:00', "
            "'2026-10-06 08:01:00', 18, 3, 0, 0, 'Falhas parciais: x', NULL, 0)"
        )
    return engine


@pytest.fixture
def migrated(tmp_path: Path) -> SQLiteRepository:
    return SQLiteRepository(_old_database(tmp_path / "peao.db"))


def test_old_tables_are_gone_and_a_backup_is_left(tmp_path: Path) -> None:
    engine = _old_database(tmp_path / "peao.db")
    SQLiteRepository(engine)

    tables = set(inspect(engine).get_table_names())
    assert {"search", "job", "profile", "analysis", "run"} <= tables
    assert not tables & {"busca", "vaga", "perfil", "analise", "execucao"}
    [backup] = tmp_path.glob("peao.before-english-*.db")
    assert "vaga" in inspect(create_engine(f"sqlite:///{backup}")).get_table_names()


def test_searches_and_runs_keep_their_ids_and_values(
    migrated: SQLiteRepository,
) -> None:
    [search] = migrated.list_searches()
    assert (search.id, search.name, search.keywords, search.active) == (
        1,
        "Python",
        ["python"],
        True,
    )
    [run] = migrated.list_runs()
    assert (run.id, run.trigger, run.status) == (7, Trigger.scheduled, RunStatus.error)
    assert (run.listed_jobs, run.new_jobs) == (18, 3)


def test_jobs_keep_status_and_get_english_fields(migrated: SQLiteRepository) -> None:
    [applied] = migrated.list_jobs(status=JobStatus.applied)
    job = applied.job
    assert (job.title, job.company, job.location, job.work_mode) == (
        "Backend Python",
        "Acme",
        "Worldwide",
        "Remote",
    )
    assert job.required_skills[0].name == "Python"
    assert job.required_skills[0].years == "5 Year(s)"
    assert job.extras == {
        "via": "Remotive",
        "job_type": "full_time",
        "headline": "BACKEND",
    }
    assert applied.searches == ["Python"]


def test_himalayas_ids_without_a_company_are_renamed(
    migrated: SQLiteRepository,
) -> None:
    assert migrated.job_exists("himalayas:no-company/dev")
    assert not migrated.job_exists("himalayas:sem-empresa/dev")


def test_analysis_and_profile_survive(migrated: SQLiteRepository) -> None:
    saved = saved_analysis(migrated, "remotive:1")
    assert saved.analysis.fit_score == 77
    assert saved.analysis.summary == "Good fit."
    assert (saved.profile_source, saved.profile_outdated) == ("vanhack", False)

    profile = saved_profile(migrated, "vanhack")
    assert profile.data["role"] == "Software Developer"
    assert profile.data["languages"] == [{"language": "English", "level": "Advanced"}]
    assert (
        profile.data["experiences"][0]["roles"][0]["role_and_period"] == "Engineer 2025"
    )
    assert profile.data["other_fields"] == {"Pronouns": "He/Him", "cargo": "kept as is"}
    # recomputed: reading the same profile again doesn't look like a change
    assert profile.content_hash == profile_hash(profile.data)


def test_a_current_database_is_left_alone(repository: SQLiteRepository) -> None:
    # the in-memory fixture is already current: opening it again changes nothing
    assert repository.list_searches() == []


def test_rename_keys_reaches_nested_lists() -> None:
    assert rename_keys([{"a": [{"a": 1}]}], {"a": "b"}) == [{"b": [{"b": 1}]}]
