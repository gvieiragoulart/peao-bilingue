"""When a job was published at the source, and whether it was new there when found."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from builders import job

from peao_bilingue.domain.jobs import JobStatus, ListedJob, published_on

FOUND = datetime(2026, 10, 17, 8, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The APIs: ISO dates; a naive one (Remotive) is UTC.
        ("2026-10-15T12:00:00+00:00", datetime(2026, 10, 15, 12, tzinfo=UTC)),
        ("2026-10-15T12:00:00", datetime(2026, 10, 15, 12, tzinfo=UTC)),
        # VanHack: the age on the card, relative to when it was read.
        ("1 h ago", FOUND - timedelta(hours=1)),
        ("20 d ago", FOUND - timedelta(days=20)),
        ("3 mo ago", FOUND - timedelta(days=90)),
        ("2 w ago", FOUND - timedelta(weeks=2)),
        ("1 y ago", FOUND - timedelta(days=365)),
        ("15 MIN AGO", FOUND - timedelta(minutes=15)),
    ],
)
def test_published_on_reads_every_shape(text: str, expected: datetime) -> None:
    assert published_on(text, FOUND) == expected


@pytest.mark.parametrize("text", [None, "", "recently", "ago", "3 eons ago"])
def test_published_on_unknown_is_none(text: str | None) -> None:
    assert published_on(text, FOUND) is None


def listed(published_at: str | None) -> ListedJob:
    return ListedJob(
        job=job(published_at=published_at),
        status=JobStatus.new,
        fit_score=None,
        searches=[],
        seen_at=FOUND,
    )


def test_new_at_source_up_to_three_days_before_we_found_it() -> None:
    assert listed("3 d ago").new_at_source is True
    assert listed("4 d ago").new_at_source is False
    assert listed("2026-10-16T09:00:00+00:00").new_at_source is True
    assert listed("2026-09-01T09:00:00+00:00").new_at_source is False


def test_new_at_source_is_unknown_without_a_date() -> None:
    item = listed(None)
    assert item.published is None
    assert item.new_at_source is None
