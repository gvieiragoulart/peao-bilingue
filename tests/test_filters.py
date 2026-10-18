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
    assert not filters.matches(JOB, search(keywords=["python"], exclude=["django"]))


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
