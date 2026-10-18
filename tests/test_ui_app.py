"""The real window, hidden, over an in-memory repository."""

import json
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from builders import analysis, job, profile
from fakes import FakeProvider, FakeReleaseFeed, FakeScheduler
from queries import saved_analysis

from peao_bilingue import config
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.application.collect import Services
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import Run, RunStatus, Trigger
from peao_bilingue.domain.jobs import Job, JobStatus
from peao_bilingue.domain.searches import Search
from peao_bilingue.domain.updates import Release
from peao_bilingue.ui.app import App, tabs
from peao_bilingue.ui.onboarding import Onboarding
from peao_bilingue.ui.tabs.jobs import tab as jobs_tab
from peao_bilingue.ui.tabs.runs import tab as runs_tab

# A real Tk window (hidden): it needs a graphical session.
pytestmark = pytest.mark.integration


def open_window(repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch) -> App:
    notices: dict[str, list[str]] = {"errors": [], "infos": []}
    # A messagebox is modal: it would leave the suite waiting for a click.
    monkeypatch.setattr(
        App, "show_error", lambda self, f: notices["errors"].append(str(f))
    )
    monkeypatch.setattr(App, "inform", lambda self, m: notices["infos"].append(m))
    # Fakes: the tests never touch Windows Task Scheduler or call GitHub.
    app = App(
        repository=repository,
        scheduler=FakeScheduler(),
        release_feed=FakeReleaseFeed(),
    )
    app.withdraw()
    app.update()
    app.notices = notices
    return app


@pytest.fixture
def window(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> Iterator[App]:
    # Someone past the first-run guide: the tabs are on screen.
    monkeypatch.setattr(settings, "onboarding_done", True)
    app = open_window(repository, monkeypatch)
    yield app
    app.close()
    config.CONFIG_PATH.unlink(missing_ok=True)
    config.reload()


@pytest.fixture
def new_user_window(
    repository: SQLiteRepository, monkeypatch: pytest.MonkeyPatch
) -> Iterator[App]:
    app = open_window(repository, monkeypatch)
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

    assert tab.table.row(new.key)[0] == "82"
    tab.open_job(new.key)
    window.update()
    assert tab.dialog.is_open
    assert "INTERVIEW QUESTIONS (20)" in tab.preview.detail.get("1.0", "end")


def test_table_shows_keywords_found_as_chips(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_search(Search(name="Python", keywords=["python", "react", "go"]))
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2", description="Nothing in common."), ["Other"])
    tab = window.panels["jobs"]
    tab.refresh()

    assert tab.table.chips("vanhack:1") == ["python", "react"]
    assert tab.table.chips("vanhack:2") == []
    assert tab.count.cget("text").startswith("2 job(s).")


def test_clicking_a_row_opens_the_dialog(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_search(Search(name="Python", keywords=["python"]))
    repository.save_job(job("1"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    window.update()

    # A click on the first row. Generated mouse events don't reach the hidden test
    # window, so the handler gets the event directly.
    click: tk.Event[tk.Canvas] = tk.Event()
    click.y = 5
    tab.table._click(click)
    window.update()

    assert tab.dialog.is_open
    assert tab.table.selected() == "vanhack:1"
    assert tab.dialog.heading.cget("text") == "Fullstack Staff Engineer"
    assert tab.dialog.keyword_chips() == ["python"]
    assert "Not analyzed yet" in tab.preview.detail.get("1.0", "end")

    # Esc is bound while it's open (the key itself can't reach the hidden window).
    assert window.bind("<Escape>")
    tab.dialog.close()
    assert not tab.dialog.is_open
    assert not window.bind("<Escape>")


def test_search_text_filters_the_list(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1", "Backend Laravel"), ["PHP"])
    repository.save_job(job("2", "Data Engineer"), ["Python"])
    tab = window.panels["jobs"]

    tab.filters.search_text.insert(0, "laravel")
    tab.refresh()

    assert tab.table.keys() == ["vanhack:1"]
    # Enter filters. The binding sits on the Tk Entry inside the CTkEntry; the key
    # itself can't be simulated: the test window doesn't get the system's focus.
    assert tab.filters.search_text._entry.bind("<Return>")


def test_status_filter_and_column_use_labels(
    window: App, repository: SQLiteRepository
) -> None:
    new = with_analyzed_job(repository)
    repository.change_status(new.key, JobStatus.applied)
    tab = window.panels["jobs"]

    tab.filters.status.set("Applied")
    tab.refresh()

    assert tab.table.keys() == [new.key]
    assert tab.table.row(new.key)[6] == "Applied"


def test_invalid_min_fit_warns_without_crashing(window: App) -> None:
    tab = window.panels["jobs"]
    tab.filters.score.insert(0, "abc")
    tab.refresh()
    assert any("0 to 100" in error for error in window.notices["errors"])


def test_marking_status_saves_and_keeps_selection(
    window: App, repository: SQLiteRepository
) -> None:
    new = with_analyzed_job(repository)
    tab = window.panels["jobs"]
    tab.refresh()
    tab.open_job(new.key)
    window.update()

    tab._change_status(JobStatus.applied)

    assert repository.list_jobs(status=JobStatus.applied)[0].job.key == new.key
    assert tab.table.selected() == new.key
    assert tab.dialog.is_open


def test_creates_search_from_screen(window: App, repository: SQLiteRepository) -> None:
    tab = window.panels["searches"]
    tab.form.name.insert(0, "Go")
    tab.form.keywords.insert(0, "golang, go ")
    tab.form.sources["vanhack"].select()
    tab._save()

    [search] = repository.list_searches()
    assert search.name == "Go"
    assert search.keywords == ["golang", "go"]
    assert search.sources == ["vanhack"]


def test_search_without_keyword_warns(
    window: App, repository: SQLiteRepository
) -> None:
    tab = window.panels["searches"]
    tab.form.name.insert(0, "Empty")
    tab._save()
    assert repository.list_searches() == []
    assert window.notices["errors"]


def test_saves_llm_settings(window: App) -> None:
    tab = window.panels["llms"]
    tab.default_llm.form._widgets["analysis_llm"].set("ollama")
    tab._save()

    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded["analysis_llm"] == "ollama"
    assert settings.analysis_llm == "ollama"
    # the key goes to the vault, never to the file
    assert "anthropic_api_key" not in recorded
    # the Jobs tab's picker now shows the new default
    assert window.panels["jobs"].preview.llm.get() == "Ollama (local, free)"


def test_invalid_integer_in_settings_is_not_saved(window: App) -> None:
    tab = window.panels["settings"]
    field = tab.limits.form._widgets["max_details_per_run"]
    field.delete(0, "end")
    field.insert(0, "ten")
    tab._save()

    assert not config.CONFIG_PATH.exists()
    assert any("whole number" in error for error in window.notices["errors"])


def test_messages_from_other_threads_reach_the_log(window: App) -> None:
    window.log("from the worker")
    window._drain_log()
    assert "from the worker" in window.panels["runs"].log.box.get("1.0", "end")


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

    tab._on_pick("linkedin")  # as a click on the picker
    assert "Tech Lead" in tab.text.get("1.0", "end")

    tab._on_pick("vanhack")  # as a click on the picker
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
    tab.schedule.time.delete(0, "end")
    tab.schedule.time.insert(0, "07:45")
    tab._schedule()

    assert process_until(window, lambda: "07:45" in tab.schedule.status.cget("text"))
    status = window.scheduler.status()
    assert status is not None and status.time == "07:45"
    assert settings.collection_time == "07:45"


def test_cancel_from_screen(window: App) -> None:
    window.scheduler.schedule("08:00")
    tab = window.panels["runs"]
    tab._cancel_schedule()

    assert process_until(
        window, lambda: "No collection" in tab.schedule.status.cget("text")
    )
    assert window.scheduler.status() is None


def test_invalid_time_warns(window: App) -> None:
    tab = window.panels["runs"]
    tab.schedule.time.delete(0, "end")
    tab.schedule.time.insert(0, "8h")
    tab._schedule()

    assert process_until(window, lambda: bool(window.notices["errors"]))
    assert window.scheduler.status() is None


REMOTIVE = "Remotive (public API, remote jobs)"


def test_collect_picker_offers_only_enabled_sources(window: App) -> None:
    tab = window.panels["runs"]
    sources = window.panels["sources"]
    assert tab.collect_bar.source.cget("values") == ["All enabled sources", "VanHack"]

    # Turning a source on in the Sources tab reaches the picker.
    sources.cards["remotive"].set_enabled(True)
    sources._save()
    assert tab.collect_bar.source.cget("values") == [
        "All enabled sources",
        REMOTIVE,
        "VanHack",
    ]

    # The chosen source turned off: back to all of them.
    tab.collect_bar.source.set(REMOTIVE)
    sources.cards["remotive"].set_enabled(False)
    sources._save()
    assert tab.collect_bar.source.get() == "All enabled sources"
    assert tab.collect_bar.chosen_source() is None


@pytest.mark.parametrize(
    ("choice", "expected"), [(REMOTIVE, ["remotive"]), (None, None)]
)
def test_collect_now_runs_the_chosen_source(
    window: App,
    monkeypatch: pytest.MonkeyPatch,
    choice: str | None,
    expected: list[str] | None,
) -> None:
    built: list[list[str] | None] = []

    def build(*, sources: list[str] | None, **_kwargs: object) -> object:
        built.append(sources)
        return object()

    async def collect(_services: Services, trigger: Trigger) -> Run:
        return Run(
            id=1, trigger=trigger, status=RunStatus.ok, started_at=datetime.now(UTC)
        )

    monkeypatch.setattr(runs_tab, "build_services", build)
    monkeypatch.setattr(runs_tab, "run_collection", collect)
    monkeypatch.setattr(settings, "enabled_sources", ["remotive", "vanhack"])
    tab = window.panels["runs"]
    tab.refresh()
    if choice:
        tab.collect_bar.source.set(choice)

    tab._collect()

    assert built == [expected]
    assert tab.collect_bar.button.cget("state") == "disabled"
    assert process_until(
        window, lambda: tab.collect_bar.button.cget("state") == "normal"
    )
    assert window.notices["errors"] == []


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
    tab.open_job(key)
    window.update()
    return tab


def test_analyze_uses_chosen_llm_and_profile(
    window: App, repository: SQLiteRepository, requested_llms: list[str]
) -> None:
    repository.save_profile(profile("Staff Engineer"))
    repository.save_job(job("1"), ["Python"])
    tab = select(window, "vanhack:1")
    assert tab.preview.profile.get() == "vanhack"  # by default, the job's source's

    tab.preview.llm.set("Ollama (local, free)")
    tab._analyze()

    assert process_until(
        window, lambda: "INTERVIEW QUESTIONS" in tab.preview.detail.get("1.0", "end")
    )
    assert requested_llms == ["ollama"]
    saved = saved_analysis(repository, "vanhack:1")
    assert (saved.analysis.fit_score, saved.provider, saved.profile_source) == (
        74,
        "ollama",
        "vanhack",
    )
    assert tab.preview.analyze_button.cget("state") == "normal"


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
    window.panels["jobs"]._remember_llm("ollama")
    assert settings.analysis_llm == "ollama"


# --- updates ------------------------------------------------------------------------


def test_banner_shows_only_when_a_newer_version_is_out(window: App) -> None:
    assert not window.update_banner.winfo_ismapped()

    window.show_update(Release(version="v9.0.0", url="https://example.com/v9"))
    window.update()

    assert window.update_banner.winfo_manager() == "pack"
    assert "v9.0.0" in window.update_text.cget("text")


def test_title_has_the_version(window: App) -> None:
    from peao_bilingue import __version__

    assert __version__ in window.title()


# --- the pasted CV and the notes ----------------------------------------------------


def test_pasted_cv_is_saved_without_contact_data(
    window: App, repository: SQLiteRepository
) -> None:
    tab = window.panels["profile"]
    tab._on_pick("My CV (pasted)")  # as a click on the picker

    tab.text.insert("1.0", "Senior Python Engineer\nme@mail.com | (11) 98765-4321")
    tab._save_manual()

    saved = repository.last_profile("manual")
    assert saved is not None
    assert saved[1].text == "Senior Python Engineer"
    assert "1 email(s), 1 phone number(s)" in window.notices["infos"][0]


def test_an_unsaved_paste_survives_a_refresh(window: App) -> None:
    tab = window.panels["profile"]
    tab._on_pick("My CV (pasted)")  # as a click on the picker
    tab.text.insert("1.0", "half written")

    window.on_change()  # e.g. a collection ended

    assert "half written" in tab.text.get("1.0", "end")


def test_notes_are_saved_clean(
    window: App, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "profile_notes_path", str(tmp_path / "notes.md"))
    tab = window.panels["profile"]
    tab.notes.box.delete("1.0", "end")
    tab.notes.box.insert("1.0", "Remote only. Reach me at me@mail.com")

    tab._save_notes()

    assert (tmp_path / "notes.md").read_text(
        encoding="utf-8"
    ) == "Remote only. Reach me at\n"


# --- the first-run guide ----------------------------------------------------------------


def the_guide(window: App) -> Onboarding:
    assert window.onboarding is not None
    return window.onboarding


def test_a_new_user_gets_the_guide_in_place_of_the_tabs(new_user_window: App) -> None:
    guide = the_guide(new_user_window)
    assert guide.winfo_manager() == "pack"
    assert not new_user_window.tabs.winfo_manager()


def test_the_guide_saves_everything_at_the_end(
    new_user_window: App, repository: SQLiteRepository
) -> None:
    guide = the_guide(new_user_window)
    guide.search_keywords.insert(0, "python, django")
    guide.search_exclude.insert(0, "intern")
    for name, box in guide.source_boxes.items():
        box.select() if name in ("remotive", "vanhack") else box.deselect()
    guide.cv.insert("1.0", "Senior Python Engineer\nme@mail.com")
    guide.pick_llm("ollama")
    guide.time.delete(0, "end")
    guide.time.insert(0, "07:30")

    for _step in guide.steps:  # Next on every step, Finish on the last
        guide.next()

    assert new_user_window.onboarding is None
    assert new_user_window.tabs.winfo_manager() == "pack"
    [search] = repository.list_searches()
    assert (search.name, search.keywords, search.exclude) == (
        "python, django",
        ["python", "django"],
        ["intern"],
    )
    assert set(settings.enabled_sources) == {"remotive", "vanhack"}
    assert settings.analysis_llm == "ollama"
    assert settings.onboarding_done
    saved = repository.last_profile("manual")
    assert saved is not None and saved[1].text == "Senior Python Engineer"
    scheduler = new_user_window.scheduler
    assert isinstance(scheduler, FakeScheduler)
    assert process_until(new_user_window, lambda: scheduler.current is not None)
    assert scheduler.current is not None and scheduler.current.time == "07:30"
    [message] = new_user_window.notices["infos"]
    assert "Collect now" in message and "log in" in message
    assert new_user_window.notices["errors"] == []


def test_a_step_filled_wrong_stays_on_screen(new_user_window: App) -> None:
    guide = the_guide(new_user_window)
    guide.next()  # to the search
    guide.search_exclude.insert(0, "intern")  # but no keyword

    guide.next()

    assert guide.current == 1
    assert "at least one keyword" in new_user_window.notices["errors"][0]


def test_nothing_is_saved_until_finish(
    new_user_window: App, repository: SQLiteRepository
) -> None:
    guide = the_guide(new_user_window)
    guide.search_keywords.insert(0, "python")
    guide.time.delete(0, "end")
    guide.time.insert(0, "8h")
    for _step in guide.steps:
        guide.next()

    assert "Invalid time" in new_user_window.notices["errors"][0]
    assert new_user_window.onboarding is guide
    assert repository.list_searches() == []
    assert not settings.onboarding_done


def test_skipping_only_remembers_the_choice(
    new_user_window: App, repository: SQLiteRepository
) -> None:
    before = list(settings.enabled_sources)
    the_guide(new_user_window).skip()

    assert new_user_window.onboarding is None
    assert settings.onboarding_done
    assert settings.enabled_sources == before
    assert repository.list_searches() == []


def test_the_guide_opens_again_from_settings(window: App) -> None:
    assert window.onboarding is None
    window.open_onboarding()
    the_guide(window).skip()
    assert window.onboarding is None
