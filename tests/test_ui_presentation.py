from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from builders import analysis, job

from peao_bilingue import factories
from peao_bilingue.domain.analysis import SavedAnalysis
from peao_bilingue.domain.collection import Run, RunStatus, Trigger
from peao_bilingue.domain.jobs import JobStatus, ListedJob, Posting
from peao_bilingue.domain.schedule import ScheduleStatus
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
    assert row[2] == "Toronto - Canada · VanHack · found today"
    assert row[4] == "New"


def test_job_row_shows_fit() -> None:
    assert presentation.job_row(listed(fit=82), NOW)[0] == "82"


def test_job_row_shows_when_found_and_age_at_the_source() -> None:
    later = NOW + timedelta(days=2)
    fresh = presentation.job_row(listed(published_at="1 d ago"), later)
    old = presentation.job_row(listed(published_at="3 mo ago"), later)
    unknown = presentation.job_row(listed(), later)

    assert fresh[2].endswith("found 2 d ago")
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


def test_panel_shows_the_dates_and_explains_the_mark() -> None:
    fresh = presentation.job_panel(listed(published_at="1 d ago"), None, NOW)
    assert "Found today · published at the source yesterday." in fresh.notes
    assert any(
        "● New at the source: published at most 3 days" in n for n in fresh.notes
    )
    assert fresh.facts == "VanHack · found today"

    old = presentation.job_panel(listed(published_at="3 mo ago"), saved(), NOW)
    assert "published at the source 3 months ago." in old.notes[0]
    assert not any("New at the source" in note for note in old.notes)

    unknown = presentation.job_panel(listed(), None, NOW)
    assert "the source doesn't give the publication date" in unknown.notes[0]


def test_every_status_has_a_label_and_comes_back_from_it() -> None:
    for status in JobStatus:
        label = presentation.job_status_labels()[status]
        assert presentation.status_from_label(label) == status
    assert presentation.status_from_label(presentation.all_label()) is None


def test_panel_with_analysis_has_the_fit_and_its_parts() -> None:
    panel = presentation.job_panel(listed(fit=82), saved())

    assert (panel.fit, panel.fit_label) == (82, "Good fit")
    assert panel.summary
    assert [section.key for section in panel.sections] == [
        "preparation",
        "questions",
        "gaps",
        "profile",
    ]
    questions = panel.sections[1]
    assert questions.title == "Questions (20)"
    assert "20. Question 20" in questions.text
    assert "anthropic (claude-x)" in panel.footer
    assert "06/10/2026 09:30" in panel.footer
    assert "with the vanhack profile" in panel.footer
    assert panel.outdated == ""


def test_panel_warns_when_profile_changed_after_analysis() -> None:
    panel = presentation.job_panel(listed(), saved(profile_outdated=True))
    assert "The vanhack profile changed after this analysis" in panel.outdated


def test_panel_shows_company_when_source_publishes_it() -> None:
    panel = presentation.job_panel(listed(company="Acme Corp"), saved())
    assert panel.details.startswith("Acme Corp · ")


def test_panel_of_unanalyzed_job_explains_how_to_analyze() -> None:
    panel = presentation.job_panel(listed(), None)
    assert panel.fit is None and panel.sections == []
    assert "Not analyzed yet" in panel.footer
    assert "Analyze" in panel.footer


@pytest.mark.parametrize(
    ("score", "label"), [(90, "Good fit"), (60, "Worth a look"), (10, "Weak fit")]
)
def test_fit_label(score: int, label: str) -> None:
    assert presentation.fit_label(score) == label


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
    assert row[:4] == ("06/10 09:30", "scheduled", "", "error")
    assert len(row[-1]) == presentation.TABLE_ERROR_SIZE
    assert row[-1].endswith("…")


def test_run_row_shows_source_labels() -> None:
    run = Run(
        id=1,
        trigger=Trigger.manual,
        status=RunStatus.ok,
        started_at=NOW,
        sources=["remotive", "gone"],
    )
    # A source whose adapter no longer exists shows its bare name.
    assert presentation.run_row(run)[2] == "Remotive, gone"


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
    assert "Also on himalayas: https://h/1" in presentation.job_panel(item, None).notes
    assert (
        "Also on himalayas: https://h/1" in presentation.job_panel(item, saved()).notes
    )


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


def test_every_status_has_its_own_color() -> None:
    colors = [status.color for status in JobStatus]
    assert all(len(pair) == 2 for pair in colors)
    assert len(set(colors)) == len(JobStatus)


def test_source_features() -> None:
    vanhack = factories.sources.class_of("vanhack")
    remotive = factories.sources.class_of("remotive")
    assert presentation.source_features(vanhack) == [
        "needs your login",
        "browser",
        "reads your profile",
    ]
    assert presentation.source_features(remotive) == ["no account needed"]


def test_badge_is_empty_for_none_and_capped() -> None:
    assert presentation.badge(0) == ""
    assert presentation.badge(7) == "7"
    assert presentation.badge(150) == "99+"


def test_schedule_line() -> None:
    assert presentation.schedule_line(None) == "No daily collection"
    status = ScheduleStatus(time="08:00", state="Ready")
    assert presentation.schedule_line(status) == "Daily collection at 08:00"


def test_last_run_line() -> None:
    zone = ZoneInfo("America/Sao_Paulo")
    now = datetime(2026, 10, 18, 12, 0, tzinfo=zone)
    run = Run(
        id=1,
        trigger=Trigger.scheduled,
        status=RunStatus.ok,
        started_at=datetime(2026, 10, 18, 8, 2, tzinfo=zone),
        new_jobs=12,
    )
    assert presentation.last_run_line(None) == "No collection yet"
    assert presentation.last_run_line(run, now) == "Last: today, 08:02 · 12 new"
    failed = run.model_copy(update={"status": RunStatus.login_required})
    assert (
        presentation.last_run_line(failed, now) == "Last: today, 08:02 · login required"
    )


def test_blend_mixes_like_an_alpha() -> None:
    assert presentation.blend("#ffffff", "#000000", 0.5) == "#808080"
    assert presentation.blend("#1f6aa5", "#ffffff", 1) == "#1f6aa5"
    assert presentation.blend("#1f6aa5", "#ffffff", 0) == "#ffffff"


def test_soft_chip_tints_the_ground_and_deepens_the_text() -> None:
    background, text = presentation.soft(("#1f6aa5", "#1f6aa5"), ("#ffffff", "#1f232a"))
    assert background[0] == presentation.blend("#1f6aa5", "#ffffff", 0.16)
    assert text[0] < "#1f6aa5"  # darker in light mode
    assert text[1] > "#1f6aa5"  # lighter in dark mode


@pytest.mark.parametrize(
    ("score", "floor"), [(100, 75), (75, 75), (74, 50), (50, 50), (49, 0), (0, 0)]
)
def test_fit_color_by_range(score: int, floor: int) -> None:
    assert presentation.fit_color(score) == dict(presentation.FIT_COLORS)[floor]


@pytest.mark.parametrize(
    ("name", "short"),
    [("remotive", "Remotive"), ("hackernews", "Hacker News"), ("gone", "gone")],
)
def test_short_source_label(name: str, short: str) -> None:
    assert presentation.short_source_label(name) == short
