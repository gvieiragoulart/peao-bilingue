"""The real window, hidden, over an in-memory repository."""

import json
import time
from collections.abc import Callable, Iterator

import pytest
from builders import analysis, job, profile
from fakes import FakeProvider, FakeScheduler
from queries import saved_analysis

from peao_bilingue import config
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.config import settings
from peao_bilingue.domain.jobs import Job, JobStatus
from peao_bilingue.ui.app import App, tabs
from peao_bilingue.ui.tabs import jobs as jobs_tab

# A real Tk window (hidden): it needs a graphical session.
pytestmark = pytest.mark.integration


@pytest.fixture
def window(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> Iterator[App]:
    notices: dict[str, list[str]] = {"errors": [], "infos": []}
    # A messagebox is modal: it would leave the suite waiting for a click.
    monkeypatch.setattr(
        App, "show_error", lambda self, f: notices["errors"].append(str(f))
    )
    monkeypatch.setattr(App, "inform", lambda self, m: notices["infos"].append(m))
    # A fake scheduler: the tests never read or touch Windows Task Scheduler.
    app = App(repository=repository, scheduler=FakeScheduler())
    app.withdraw()
    app.update()
    app.notices = notices
    yield app
    app.close()
    config.CONFIG_PATH.unlink(missing_ok=True)
    config.reload()


def with_analyzed_job(
    repository: SQLiteRepository, external_id: str = "1", fit: int = 82
) -> Job:
    new = job(external_id)
    repository.save_job(new, ["Python"])
    repository.save_analysis(
        new.key, analysis(fit), provider="anthropic", model="m", profile_id=None
    )
    return new


def test_opens_with_all_tabs(window: App) -> None:
    assert list(window.panels) == [identifier for identifier, _, _ in tabs()]


def test_jobs_show_and_detail_has_analysis(
    window: App, repository: SQLiteRepository
) -> None:
    new = with_analyzed_job(repository)
    tab = window.panels["jobs"]
    tab.refresh()

    assert tab.table.tree.item(new.key)["values"][0] == 82
    tab.table.tree.selection_set(new.key)
    window.update()
    assert "INTERVIEW QUESTIONS (20)" in tab.detail.get("1.0", "end")


def test_search_text_filters_the_list(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1", "Backend Laravel"), ["PHP"])
    repository.save_job(job("2", "Data Engineer"), ["Python"])
    tab = window.panels["jobs"]

    tab.search_text.insert(0, "laravel")
    tab.refresh()

    assert tab.table.tree.get_children() == ("vanhack:1",)
    # Enter filters. The binding sits on the Tk Entry inside the CTkEntry; the key
    # itself can't be simulated: the test window doesn't get the system's focus.
    assert tab.search_text._entry.bind("<Return>")


def test_status_filter_and_column_use_labels(
    window: App, repository: SQLiteRepository
) -> None:
    new = with_analyzed_job(repository)
    repository.change_status(new.key, JobStatus.applied)
    tab = window.panels["jobs"]

    tab.status.set("Applied")
    tab.refresh()

    assert tab.table.tree.get_children() == (new.key,)
    assert tab.table.tree.item(new.key)["values"][4] == "Applied"


def test_invalid_min_fit_warns_without_crashing(window: App) -> None:
    tab = window.panels["jobs"]
    tab.score.insert(0, "abc")
    tab.refresh()
    assert any("0 to 100" in error for error in window.notices["errors"])


def test_marking_status_saves_and_keeps_selection(
    window: App, repository: SQLiteRepository
) -> None:
    new = with_analyzed_job(repository)
    tab = window.panels["jobs"]
    tab.refresh()
    tab.table.tree.selection_set(new.key)
    window.update()

    tab._change_status(JobStatus.applied)

    assert repository.list_jobs(status=JobStatus.applied)[0].job.key == new.key
    assert tab.table.selected() == new.key


def test_creates_search_from_screen(window: App, repository: SQLiteRepository) -> None:
    tab = window.panels["searches"]
    tab.name.insert(0, "Go")
    tab.keywords.insert(0, "golang, go ")
    tab.sources["vanhack"].select()
    tab._save()

    [search] = repository.list_searches()
    assert search.name == "Go"
    assert search.keywords == ["golang", "go"]
    assert search.sources == ["vanhack"]


def test_search_without_keyword_warns(
    window: App, repository: SQLiteRepository
) -> None:
    tab = window.panels["searches"]
    tab.name.insert(0, "Empty")
    tab._save()
    assert repository.list_searches() == []
    assert window.notices["errors"]


def test_saves_llm_settings(window: App) -> None:
    tab = window.panels["llms"]
    tab.general._widgets["analysis_llm"].set("ollama")
    tab._save()

    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded["analysis_llm"] == "ollama"
    assert settings.analysis_llm == "ollama"
    # the key goes to the vault, never to the file
    assert "anthropic_api_key" not in recorded
    # the Jobs tab's picker now shows the new default
    assert window.panels["jobs"].llm.get() == "Ollama (local, free)"


def test_invalid_integer_in_settings_is_not_saved(window: App) -> None:
    tab = window.panels["settings"]
    field = tab.limits._widgets["max_details_per_run"]
    field.delete(0, "end")
    field.insert(0, "ten")
    tab._save()

    assert not config.CONFIG_PATH.exists()
    assert any("whole number" in error for error in window.notices["errors"])


def test_messages_from_other_threads_reach_the_log(window: App) -> None:
    window.log("from the worker")
    window._drain_log()
    assert "from the worker" in window.panels["runs"].log_box.get("1.0", "end")


def test_profile_shows_latest_snapshot(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_profile(profile("Staff Engineer"))
    tab = window.panels["profile"]
    tab.refresh()
    assert "Staff Engineer" in tab.text.get("1.0", "end")


def test_profile_is_shown_per_source(window: App, repository: SQLiteRepository) -> None:
    repository.save_profile(profile("Staff Engineer", source="vanhack"))
    repository.save_profile(profile("Tech Lead", source="linkedin"))
    tab = window.panels["profile"]

    tab.source.set("linkedin")
    tab.refresh()
    assert "Tech Lead" in tab.text.get("1.0", "end")

    tab.source.set("vanhack")
    tab.refresh()
    assert "Staff Engineer" in tab.text.get("1.0", "end")
    assert "Tech Lead" not in tab.text.get("1.0", "end")


def process_until(
    window: App, condition: Callable[[], bool], limit: float = 5.0
) -> bool:
    """Runs Tk's mainloop until the condition holds (the work goes through the
    executor and back)."""
    deadline = time.time() + limit
    while time.time() < deadline:
        window.update()
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_scheduling_from_screen_registers_and_saves_time(window: App) -> None:
    tab = window.panels["runs"]
    tab.time.delete(0, "end")
    tab.time.insert(0, "07:45")
    tab._schedule()

    assert process_until(window, lambda: "07:45" in tab.schedule_status.cget("text"))
    status = window.scheduler.status()
    assert status is not None and status.time == "07:45"
    assert settings.collection_time == "07:45"


def test_cancel_from_screen(window: App) -> None:
    window.scheduler.schedule("08:00")
    tab = window.panels["runs"]
    tab._cancel_schedule()

    assert process_until(
        window, lambda: "No collection" in tab.schedule_status.cget("text")
    )
    assert window.scheduler.status() is None


def test_invalid_time_warns(window: App) -> None:
    tab = window.panels["runs"]
    tab.time.delete(0, "end")
    tab.time.insert(0, "8h")
    tab._schedule()

    assert process_until(window, lambda: bool(window.notices["errors"]))
    assert window.scheduler.status() is None


# --- analysis requested on screen ---------------------------------------------------


@pytest.fixture
def requested_llms(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """No real LLM: the screen gets a fake with the chosen name."""
    requests: list[str] = []

    def build(name: str) -> FakeProvider:
        requests.append(name)
        return FakeProvider(fit=74, name=name)

    monkeypatch.setattr(jobs_tab, "build_llm", build)
    return requests


def select(window: App, key: str) -> jobs_tab.JobsTab:
    tab: jobs_tab.JobsTab = window.panels["jobs"]
    tab.refresh()
    tab.table.tree.selection_set(key)
    window.update()
    return tab


def test_analyze_uses_chosen_llm_and_profile(
    window: App, repository: SQLiteRepository, requested_llms: list[str]
) -> None:
    repository.save_profile(profile("Staff Engineer"))
    repository.save_job(job("1"), ["Python"])
    tab = select(window, "vanhack:1")
    assert tab.profile.get() == "vanhack"  # by default, the job's source's

    tab.llm.set("Ollama (local, free)")
    tab._analyze()

    assert process_until(
        window, lambda: "INTERVIEW QUESTIONS" in tab.detail.get("1.0", "end")
    )
    assert requested_llms == ["ollama"]
    saved = saved_analysis(repository, "vanhack:1")
    assert (saved.analysis.fit_score, saved.provider, saved.profile_source) == (
        74,
        "ollama",
        "vanhack",
    )
    assert tab.analyze_button.cget("state") == "normal"


def test_analyze_without_profile_explains_what_to_do(
    window: App, repository: SQLiteRepository, requested_llms: list[str]
) -> None:
    repository.save_job(job("1"), ["Python"])
    tab = select(window, "vanhack:1")

    tab._analyze()

    assert process_until(window, lambda: bool(window.notices["errors"]))
    assert "Profile tab" in window.notices["errors"][0]
    assert repository.current_analysis("vanhack:1") is None


def test_analyze_without_selected_job_warns(
    window: App, requested_llms: list[str]
) -> None:
    window.panels["jobs"]._analyze()
    assert window.notices["errors"] == ["Pick a job to analyze."]
    assert requested_llms == []


def test_chosen_llm_becomes_default(window: App) -> None:
    window.panels["jobs"]._remember_llm("Ollama (local, free)")
    assert settings.analysis_llm == "ollama"
