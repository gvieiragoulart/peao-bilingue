from datetime import datetime
from zoneinfo import ZoneInfo

from peao_bilingue.domain.schedule import ScheduleStatus
from peao_bilingue.texts import describe_schedule

NOW = datetime(2026, 10, 6, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_describes_empty_schedule() -> None:
    assert describe_schedule(None) == "No collection scheduled."


def test_describes_schedule_with_next_and_last() -> None:
    status = ScheduleStatus(
        time="08:00",
        state="Ready",
        next_run=NOW,
        last_run=NOW,
        last_result=1,
    )
    text = describe_schedule(status)
    assert "Every day at 08:00" in text
    assert "Next: 06/10 09:30" in text
    assert "code 1" in text  # the last run failed
