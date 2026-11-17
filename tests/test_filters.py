from typing import Any

from builders import job

from peao_bilingue.application import filters
from peao_bilingue.domain.jobs import Skill
from peao_bilingue.domain.searches import Search

JOB = job(
    title="Fullstack Developer",
    description="We work with Django and queues.",
    skills=["Aws", "React.js"],
    required_skills=[Skill(name="Python", years="4 Year(s)")],
    extras={"headline": "FULL STACK ENGINEER · 5+ YEARS"},
)


def search(**overrides: Any) -> Search:
    return Search(**{"name": "Remote Python", "keywords": ["python"], **overrides})


def test_matches_keyword_in_any_field() -> None:
    assert filters.matches(JOB, search(keywords=["python"]))  # required skills
    assert filters.matches(JOB, search(keywords=["django"]))  # description
    assert filters.matches(JOB, search(keywords=["fullstack"]))  # title
    assert filters.matches(JOB, search(keywords=["engineer"]))  # headline (extras)


def test_ignores_case() -> None:
    assert filters.matches(JOB, search(keywords=["PYTHON"]))


def test_no_match_without_any_keyword() -> None:
    assert not filters.matches(JOB, search(keywords=["cobol"]))


def test_any_keyword_is_enough() -> None:
    assert filters.matches(JOB, search(keywords=["cobol", "python"]))


def test_exclude_beats_keyword() -> None:
    assert not filters.matches(JOB, search(keywords=["python"], exclude=["developer"]))


def test_exclude_only_looks_at_the_title() -> None:
    # "django" is in the description: a developer job that mentions it stays
    assert filters.matches(JOB, search(keywords=["python"], exclude=["django"]))


def test_exclude_ignores_accents_and_case() -> None:
    senior = job(title="Engenheiro de Software Sênior", description="Python")
    assert not filters.matches(senior, search(exclude=["SENIOR"]))


def test_roles_must_be_in_the_title() -> None:
    assert filters.matches(JOB, search(roles=["engineer", "developer"]))
    # Python is in the job, but the title isn't a role the search wants
    assert not filters.matches(JOB, search(roles=["designer"]))


def test_a_data_analyst_asking_for_python_is_not_a_developer_job() -> None:
    analyst = job(title="Data Analyst", description="SQL and Python required.")
    assert filters.matches(analyst, search())  # keywords alone let it in
    assert not filters.matches(analyst, search(roles=["engineer", "developer"]))


def test_a_keyword_in_the_title_counts_as_a_role() -> None:
    assert filters.matches(JOB, search(keywords=["fullstack"], roles=["designer"]))


def test_roles_ignore_accents_and_case() -> None:
    backend = job(title="Desenvolvedora Back-end Pleno", description="Python, Django")
    assert filters.matches(backend, search(roles=["DESENVOLVEDOR"]))
    engenheira = job(title="Engenheira de Software", description="Python")
    assert filters.matches(engenheira, search(roles=["engenhéir"]))


def test_search_without_sources_applies_to_all() -> None:
    assert filters.matches(JOB, search(sources=[]))


def test_restricted_search_ignores_other_sources() -> None:
    assert filters.matches(JOB, search(sources=["vanhack"]))
    assert not filters.matches(JOB, search(sources=["remotive"]))


def test_lists_matching_searches() -> None:
    searches = [
        search(name="Python", keywords=["python"]),
        search(name="Go", keywords=["golang"]),
        search(name="React", keywords=["react.js"]),
    ]
    assert filters.matching_searches(JOB, searches) == ["Python", "React"]


def test_matched_keywords_in_search_order() -> None:
    found = filters.matched_keywords(
        JOB, search(keywords=["Django", "cobol", "python", "django"])
    )
    assert found == ["Django", "python"]


def test_no_matched_keywords() -> None:
    assert filters.matched_keywords(JOB, search(keywords=["cobol"])) == []
