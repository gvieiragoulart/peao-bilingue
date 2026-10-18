from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from builders import analysis, job

from peao_bilingue.domain.analysis import SavedAnalysis
from peao_bilingue.domain.collection import Run, RunStatus, Trigger
from peao_bilingue.domain.jobs import JobStatus, ListedJob, Posting
from peao_bilingue.domain.searches import Search
from peao_bilingue.ui import presentation

NOW = datetime(2026, 10, 6, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))


def listed(fit: int | None = None, **overrides: Any) -> ListedJob:
    return ListedJob(
        job=job(**overrides),
        status=JobStatus.new,
        fit_score=fit,
        searches=["Python"],
        seen_at=NOW,
    )


def saved(**overrides: Any) -> SavedAnalysis:
    base = {
        "analysis": analysis(82),
        "provider": "anthropic",
        "model": "claude-x",
        "created_at": NOW,
        "profile_source": "vanhack",
    }
    return SavedAnalysis(**{**base, **overrides})


def test_job_row_without_analysis_has_empty_fit() -> None:
    row = presentation.job_row(listed(), NOW)
    assert row[0] == ""
    assert row[1] == "Fullstack Staff Engineer"
    assert row[5] == "vanhack" and row[6] == "New"


def test_job_row_shows_fit() -> None:
    assert presentation.job_row(listed(fit=82), NOW)[0] == "82"


def test_job_row_shows_when_found_and_age_at_the_source() -> None:
    later = NOW + timedelta(days=2)
    fresh = presentation.job_row(listed(published_at="1 d ago"), later)
    old = presentation.job_row(listed(published_at="3 mo ago"), later)
    unknown = presentation.job_row(listed(), later)

    assert fresh[2] == "2 d ago"
    assert fresh[3] == "● 3 d ago"  # new at the source when we found it
    assert old[3] == "3 months ago"
    assert unknown[3] == "?"


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (NOW, "today"),
        (NOW.replace(hour=0, minute=1), "today"),
        (NOW.replace(day=5, hour=23, minute=59), "yesterday"),
        (NOW - timedelta(days=29), "29 d ago"),
        (NOW - timedelta(days=30), "1 month ago"),
        (NOW - timedelta(days=95), "3 months ago"),
        (NOW - timedelta(days=365), "1 year ago"),
        (NOW - timedelta(days=800), "2 years ago"),
        (NOW + timedelta(hours=1), "today"),
    ],
)
def test_ago_counts_calendar_days(when: datetime, expected: str) -> None:
    assert presentation.ago(when, NOW) == expected


def test_detail_shows_the_dates_and_explains_the_mark() -> None:
    fresh = presentation.job_detail(listed(published_at="1 d ago"), None, NOW)
    assert "Found today · published at the source yesterday." in fresh
    assert "● New at the source: published at most 3 days" in fresh

    old = presentation.job_detail(listed(published_at="3 mo ago"), saved(), NOW)
    assert "published at the source 3 months ago." in old
    assert "New at the source" not in old

    unknown = presentation.job_detail(listed(), None, NOW)
    assert "the source doesn't give the publication date" in unknown


def test_every_status_has_a_label_and_comes_back_from_it() -> None:
    for status in JobStatus:
        label = presentation.job_status_labels()[status]
        assert presentation.status_from_label(label) == status
    assert presentation.status_from_label(presentation.all_label()) is None


def test_detail_with_analysis_shows_provider_and_profile() -> None:
    text = presentation.job_detail(listed(fit=82), saved())

    assert "Fit: 82/100" in text
    assert "INTERVIEW QUESTIONS (20)" in text
    assert "20. Question 20" in text
    for section in ("SUMMARY", "PREPARATION", "GAPS", "WHAT TO IMPROVE IN THE PROFILE"):
        assert section in text
    assert "anthropic (claude-x)" in text
    assert "06/10/2026 09:30" in text
    assert "with the vanhack profile" in text
    assert "changed after" not in text


def test_detail_warns_when_profile_changed_after_analysis() -> None:
    text = presentation.job_detail(listed(), saved(profile_outdated=True))
    assert "The vanhack profile changed after this analysis" in text


def test_detail_shows_company_when_source_publishes_it() -> None:
    text = presentation.job_detail(listed(company="Acme Corp"), saved())
    assert "Acme Corp" in text


def test_detail_of_unanalyzed_job_explains_how_to_analyze() -> None:
    text = presentation.job_detail(listed(), None)
    assert "Not analyzed yet" in text
    assert "Analyze" in text
    # Only the keywords: the description reads better on the job's site.
    assert "commissions platform" not in text


def test_search_row() -> None:
    search = Search(
        name="Python", keywords=["python", "django"], exclude=["intern"], sources=[]
    )
    assert presentation.search_row(search) == (
        "Python",
        "python, django",
        "intern",
        "all",
        "yes",
    )


def test_run_row_truncates_long_error() -> None:
    run = Run(
        id=1,
        trigger=Trigger.scheduled,
        status=RunStatus.error,
        started_at=NOW,
        error="x" * 500,
    )
    row = presentation.run_row(run)
    assert row[:3] == ("06/10 09:30", "scheduled", "error")
    assert len(row[-1]) == presentation.TABLE_ERROR_SIZE
    assert row[-1].endswith("…")


def test_comma_separated_terms() -> None:
    assert presentation.terms(" python, django ,, ") == ["python", "django"]


@pytest.mark.parametrize(
    ("text", "expected"), [("", None), ("  ", None), ("70", 70), ("0", 0)]
)
def test_valid_min_score(text: str, expected: int | None) -> None:
    assert presentation.parse_min_score(text) == expected


@pytest.mark.parametrize("text", ["abc", "101", "-1"])
def test_invalid_min_score_explains(text: str) -> None:
    with pytest.raises(ValueError, match="0 to 100"):
        presentation.parse_min_score(text)


def test_detail_shows_where_else_job_was_posted() -> None:
    item = listed().model_copy(
        update={"also_on": [Posting(source="himalayas", url="https://h/1")]}
    )
    assert "Also on himalayas: https://h/1" in presentation.job_detail(item, None)
    assert "Also on himalayas" in presentation.job_detail(item, saved())


def test_job_keywords_by_search_the_job_was_found_by() -> None:
    item = listed().model_copy(update={"searches": ["Python", "Frontend", "Gone"]})
    searches = [
        Search(name="Python", keywords=["Django", "python", "cobol"]),
        Search(name="Frontend", keywords=["react", "vue"]),
        Search(name="Go", keywords=["python"]),  # the job wasn't found by it
    ]
    assert presentation.job_keywords(item, searches) == [
        presentation.KeywordGroup("Python", ["python"]),
        presentation.KeywordGroup("Frontend", ["react"]),
    ]


def test_job_keywords_leave_out_a_search_with_none_left() -> None:
    searches = [Search(name="Python", keywords=["cobol"])]
    assert presentation.job_keywords(listed(), searches) == []


def test_each_search_keeps_its_color() -> None:
    names = [f"search {n}" for n in range(len(presentation.SEARCH_COLORS) + 1)]
    colors = presentation.search_colors(names)
    assert colors["search 0"] == presentation.SEARCH_COLORS[0]
    assert colors["search 1"] != colors["search 0"]
    assert colors[names[-1]] == presentation.SEARCH_COLORS[0]  # the palette cycles
