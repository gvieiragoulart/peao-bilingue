"""The real window, hidden, over an in-memory repository."""

import json
import os
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import customtkinter as ctk
import keyring
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
    notices: dict[str, list[str]] = {"errors": [], "infos": [], "questions": []}
    # A messagebox is modal: it would leave the suite waiting for a click.
    monkeypatch.setattr(
        App, "show_error", lambda self, f: notices["errors"].append(str(f))
    )
    monkeypatch.setattr(App, "inform", lambda self, m: notices["infos"].append(m))

    def confirm(self: App, question: str) -> bool:
        notices["questions"].append(question)
        return True

    monkeypatch.setattr(App, "confirm", confirm)
    # Fakes: the tests never touch Windows Task Scheduler or call the download site.
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


def click_at(x: int, y: int) -> "tk.Event[tk.Canvas]":
    # Generated mouse events don't reach the hidden test window, so the handlers get
    # the event directly.
    event: tk.Event[tk.Canvas] = tk.Event()
    event.x = x
    event.y = y
    return event


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
    assert tab.preview.ring.score == 82
    tab.preview.pick_section("questions")
    assert "20. Question 20" in tab.preview.detail.get("1.0", "end")


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


def test_clicking_a_row_opens_the_dialog(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_search(Search(name="Python", keywords=["python"]))
    repository.save_job(job("1"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    window.update()

    # A click on the first row's title (past the selection box).
    tab.table._click(click_at(200, 5))
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
    assert tab.table.row(new.key)[-1] == "Applied"


def test_status_filter_starts_on_new(window: App, repository: SQLiteRepository) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2"), ["Python"])
    repository.change_status("vanhack:2", JobStatus.studying)
    tab = window.panels["jobs"]
    tab.refresh()

    assert tab.filters.status.get() == "New"
    assert tab.table.keys() == ["vanhack:1"]


def test_status_is_drawn_as_a_chip(window: App, repository: SQLiteRepository) -> None:
    new = with_analyzed_job(repository)
    repository.change_status(new.key, JobStatus.studying)
    tab = window.panels["jobs"]
    tab.filters.status.set("All")
    tab.refresh()

    assert tab.table.status_chip(new.key) == "Studying"


def test_ticking_boxes_selects_without_opening_the_dialog(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    first, second = tab.table.keys()
    assert tab.discard_checked.cget("state") == "disabled"

    tab.table._click(click_at(5, 5))  # the first row's box

    assert tab.table.checked() == [first]
    assert tab.table.box_ticked(first)
    assert not tab.table.box_ticked(second)
    assert not tab.dialog.is_open
    assert tab.checked_count.cget("text") == "1 selected"
    assert tab.discard_checked.cget("state") == "normal"

    # The header's box ticks every job, then unticks them all.
    tab.table._click_header(click_at(5, 5))
    assert tab.table.checked() == [first, second]
    tab.table._click_header(click_at(5, 5))
    assert tab.table.checked() == []


def test_discards_the_selected_jobs_at_once(
    window: App, repository: SQLiteRepository
) -> None:
    for external_id in ("1", "2", "3"):
        repository.save_job(job(external_id), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    tab.table.toggle("vanhack:1")
    tab.table.toggle("vanhack:3")

    tab._discard_checked()

    assert window.notices["questions"] == ["Discard 2 job(s)?"]
    discarded = repository.list_jobs(status=JobStatus.discarded)
    assert sorted(item.job.key for item in discarded) == ["vanhack:1", "vanhack:3"]
    assert tab.table.keys() == ["vanhack:2"]  # the list shows only the new ones
    assert tab.table.checked() == []
    assert tab.discard_checked.cget("state") == "disabled"


def test_discarded_jobs_can_be_deleted_for_good(
    window: App, repository: SQLiteRepository
) -> None:
    for external_id in ("1", "2", "3"):
        repository.save_job(job(external_id), ["Python"])
    repository.change_statuses(["vanhack:1", "vanhack:2"], JobStatus.discarded)
    tab = window.panels["jobs"]
    tab.refresh()
    tab.table.toggle("vanhack:3")
    # Outside the Discarded filter, the selection can be discarded, not deleted.
    assert tab.discard_checked.winfo_manager()
    assert not tab.delete_checked.winfo_manager()

    tab.filters.status.set("Discarded")
    tab.refresh()
    tab.open_job("vanhack:1")
    tab.table.toggle("vanhack:1")
    tab.table.toggle("vanhack:2")
    assert tab.delete_checked.winfo_manager()
    assert not tab.discard_checked.winfo_manager()

    tab._delete_checked()

    assert window.notices["questions"][0].startswith("Delete 2 job(s) for good?")
    assert window.notices["infos"] == ["2 job(s) deleted."]
    assert not repository.job_exists("vanhack:1")
    assert not repository.job_exists("vanhack:2")
    assert repository.job_exists("vanhack:3")
    assert tab.table.keys() == []
    assert not tab.dialog.is_open  # its job is gone


def test_discarding_the_open_job_closes_the_panel(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    tab.open_job("vanhack:1")
    window.update()

    tab._change_status(JobStatus.discarded)

    assert not tab.dialog.is_open
    assert not window.bind("<Escape>")
    assert tab.table.keys() == ["vanhack:2"]
    assert window.notices["questions"] == []  # Undo instead of asking first
    assert window.toast.message.cget("text") == "Job discarded."

    window.toast.action.invoke()  # Undo

    assert sorted(tab.table.keys()) == ["vanhack:1", "vanhack:2"]
    assert repository.list_jobs(status=JobStatus.discarded) == []


def test_discarding_the_open_job_from_the_selection_closes_the_panel(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    tab.open_job("vanhack:1")
    window.update()
    tab.table.toggle("vanhack:1")

    tab._discard_checked()

    assert not tab.dialog.is_open
    assert tab.table.keys() == ["vanhack:2"]


def test_refresh_keeps_the_boxes_of_jobs_still_listed(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1", "Backend Laravel"), ["PHP"])
    repository.save_job(job("2", "Data Engineer"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    tab.table.toggle_all()

    tab.filters.search_text.insert(0, "laravel")
    tab.refresh()

    assert tab.table.checked() == ["vanhack:1"]


def test_published_header_sorts_by_date_at_the_source(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("old", published_at="2026-09-01"), ["Python"])
    repository.save_job(job("undated", published_at=None), ["Python"])
    repository.save_job(job("recent", published_at="2026-10-10"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    table = tab.table
    found_order = table.keys()
    assert table.header_title("published") == "Published ↕"

    # The x of the Published header's cell.
    columns = [column.identifier for column in table._columns]
    widths = table._widths()
    x = sum(widths[: columns.index("published")]) + 5

    table._click_header(click_at(x, 5))
    assert table.keys() == ["vanhack:recent", "vanhack:old", "vanhack:undated"]
    assert table.header_title("published") == "Published ▼"

    table._click_header(click_at(x, 5))
    assert table.keys() == ["vanhack:old", "vanhack:recent", "vanhack:undated"]
    assert table.header_title("published") == "Published ▲"

    # Kept across a refresh.
    tab.refresh()
    assert table.keys() == ["vanhack:old", "vanhack:recent", "vanhack:undated"]

    # A third click goes back to the order they were found in.
    table._click_header(click_at(x, 5))
    assert table.keys() == found_order
    assert table.order() is None


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
    tab.filters.status.set("All")
    tab.refresh()
    tab.open_job(new.key)
    window.update()

    tab._change_status(JobStatus.applied)

    assert repository.list_jobs(status=JobStatus.applied)[0].job.key == new.key
    assert tab.table.selected() == new.key
    assert tab.dialog.is_open
    assert tab.dialog.status_chip.cget("text") == "Applied"
    applied = tab.preview.status_buttons.buttons[JobStatus.applied]
    assert applied.cget("fg_color") != "transparent"


def test_marked_job_that_left_the_list_stays_open_with_its_status(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()  # the filter shows only the new ones
    tab.open_job("vanhack:1")
    window.update()

    tab._change_status(JobStatus.studying)

    assert tab.table.keys() == []
    assert tab.dialog.is_open
    assert tab.dialog.status_chip.cget("text") == "Studying"


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


def test_the_default_llm_is_picked_in_settings(window: App) -> None:
    tab = window.panels["settings"]
    assert tab.analysis.llm.get() == "Claude (Anthropic)"
    tab.analysis.llm.set("Ollama (local, free)")
    tab._save()

    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded["analysis_llm"] == "ollama"
    assert settings.analysis_llm == "ollama"
    # the Jobs tab's picker and the LLMs tab's Default follow it
    assert window.panels["jobs"].preview.llm.get() == "Ollama (local, free)"
    cards = window.panels["llms"].cards
    assert cards["ollama"].is_default
    assert not cards["anthropic"].is_default


def test_llm_cards_have_short_titles_and_no_save_button(window: App) -> None:
    tab = window.panels["llms"]
    titles = {name: card.title.cget("text") for name, card in tab.cards.items()}
    assert titles == {
        "anthropic": "Claude",
        "gemini": "Gemini",
        "ollama": "Ollama",
        "openai": "OpenAI",
    }
    buttons = [
        child for child in tab.winfo_children() if isinstance(child, ctk.CTkButton)
    ]
    assert buttons == []  # Save lives in each LLM's modal


def test_the_llm_modal_saves_its_settings(window: App) -> None:
    tab = window.panels["llms"]
    tab.open("ollama")
    assert tab.dialog is not None
    model = tab.dialog.form._widgets["ollama_model"]
    model.delete(0, "end")
    model.insert(0, "llama3.1:8b")
    tab.dialog.save()

    assert settings.ollama_model == "llama3.1:8b"
    assert tab.dialog is None  # saved: closed
    assert window.notices["infos"] == ["LLM settings saved."]


def test_an_llm_key_goes_to_the_vault_not_the_file(window: App) -> None:
    tab = window.panels["llms"]
    tab.open("anthropic")
    assert tab.dialog is not None
    tab.dialog.form._widgets["anthropic_api_key"].insert(0, "sk-test")
    tab.dialog.save()

    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert "anthropic_api_key" not in recorded
    assert keyring.get_password(config.KEYRING_SERVICE, "anthropic_api_key") == (
        "sk-test"
    )
    keyring.delete_password(config.KEYRING_SERVICE, "anthropic_api_key")


def test_an_invalid_number_keeps_the_llm_modal_open(window: App) -> None:
    tab = window.panels["llms"]
    tab.open("ollama")
    assert tab.dialog is not None
    context = tab.dialog.form._widgets["ollama_context"]
    context.delete(0, "end")
    context.insert(0, "lots")
    tab.dialog.save()

    assert tab.dialog is not None
    assert any("whole number" in error for error in window.notices["errors"])
    tab.dialog.close()


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


REMOTIVE = "Remotive"


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


def test_source_card_shows_description_and_state(window: App) -> None:
    card = window.panels["sources"].cards["remotive"]
    assert card.title.cget("text") == REMOTIVE
    assert card.description.cget("text").startswith("Fully remote jobs")
    accent = ctk.ThemeManager.theme["CTkButton"]["fg_color"]

    # The switch says nothing: its position does; the border follows it.
    card.set_enabled(True)
    assert card.switch.cget("text") == ""
    assert card.cget("border_color") == accent
    card.set_enabled(False)
    assert card.cget("border_color") != accent


def test_clicking_a_card_opens_its_dialog(window: App) -> None:
    tab = window.panels["sources"]
    tab.cards["himalayas"].open()
    dialog = tab.dialog
    assert dialog is not None
    assert dialog.name == "himalayas"
    assert dialog.title.cget("text") == "Himalayas"
    assert dialog.about is not None
    assert dialog.about.cget("text").startswith("Searched once per keyword")
    # Its settings, and no login: only sources with a manual login have one.
    assert dialog.form is not None
    assert [field.name for field in dialog.form.fields] == ["himalayas_country"]
    assert dialog.status is None

    # Another card swaps it; Esc closes it (the binding: the hidden test window
    # gets no generated keys).
    tab.cards["vanhack"].open()
    assert tab.dialog is not None
    assert tab.dialog.name == "vanhack"
    assert tab.dialog.status is not None
    assert window.bind("<Escape>")
    tab.dialog.close()
    assert tab.dialog is None
    assert not window.bind("<Escape>")


def test_the_dialog_saves_the_source_settings(window: App) -> None:
    tab = window.panels["sources"]
    tab.open("company_boards")
    assert tab.dialog is not None and tab.dialog.form is not None
    boards = tab.dialog.form._widgets["company_boards"]
    assert boards.get("1.0", "end").splitlines()[0] == "ashby:nubank=Nubank"
    boards.delete("1.0", "end")
    # One per line; blank lines and spaces around go.
    boards.insert("1.0", "lever:toptal=Toptal\n\n  greenhouse:vtex  \n")
    tab.dialog.save()

    assert settings.company_boards == ["lever:toptal=Toptal", "greenhouse:vtex"]
    assert tab.dialog is None  # saved: closed
    assert window.notices["infos"] == ["Settings saved."]


def test_the_dialog_switch_is_the_card_switch(window: App) -> None:
    tab = window.panels["sources"]
    tab.open("remotive")
    assert tab.dialog is not None
    tab.dialog.switch.toggle()  # what a click does: flips it and calls back
    assert tab.cards["remotive"].enabled
    assert "remotive" in settings.enabled_sources
    assert REMOTIVE in window.panels["runs"].collect_bar.source.cget("values")


def test_the_session_status_survives_closing_the_dialog(window: App) -> None:
    tab = window.panels["sources"]
    tab.open("vanhack")
    tab._show_status("vanhack", "Valid session")
    assert tab.dialog is not None and tab.dialog.status is not None
    assert tab.dialog.status.cget("text") == "Valid session"
    tab.dialog.close()
    tab.open("vanhack")
    assert tab.dialog is not None and tab.dialog.status is not None
    assert tab.dialog.status.cget("text") == "Valid session"


def test_the_jobs_table_draws_each_source_icon(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2", source="remoteok"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()

    assert tab.table.icon_items("vanhack:1") == 1  # its logo
    assert tab.table.icon_items("remoteok:2") == 2  # a monogram: tile and letters


def test_source_cards_reflow_in_a_grid(window: App) -> None:
    tab = window.panels["sources"]
    names = list(tab.cards)

    def place(name: str) -> tuple[int, int]:
        info = tab.cards[name].grid_info()
        return int(info["row"]), int(info["column"])

    tab.arrange(3)
    assert [place(name) for name in names[:4]] == [(0, 0), (0, 1), (0, 2), (1, 0)]
    tab.arrange(1)
    assert [place(name) for name in names[:2]] == [(0, 0), (1, 0)]
    # Never more columns than the maximum, never fewer than one.
    tab.arrange(9)
    assert tab.columns == 3
    tab.arrange(0)
    assert tab.columns == 1


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

    tab.collect()

    assert built == [expected]
    assert tab.collect_bar.button.cget("state") == "disabled"
    assert process_until(
        window, lambda: tab.collect_bar.button.cget("state") == "normal"
    )
    assert window.notices["errors"] == []


@pytest.mark.parametrize("saved", [True, False])
def test_collect_with_screenshots_opens_their_folder(
    window: App, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, saved: bool
) -> None:
    folder = tmp_path / "captures" / "20261017_100000"
    received: list[Path | None] = []
    opened: list[Path] = []

    def build(*, capture_to: Path | None, **_kwargs: object) -> object:
        received.append(capture_to)
        return object()

    async def collect(_services: Services, trigger: Trigger) -> Run:
        if saved and received[-1]:  # a source that reads web pages saved its searches
            received[-1].mkdir(parents=True)
        return Run(
            id=1, trigger=trigger, status=RunStatus.ok, started_at=datetime.now(UTC)
        )

    monkeypatch.setattr(runs_tab, "capture_folder", lambda: folder)
    monkeypatch.setattr(runs_tab, "build_services", build)
    monkeypatch.setattr(runs_tab, "run_collection", collect)
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    tab = window.panels["runs"]

    tab.collect()  # unchecked: no screenshots
    assert process_until(
        window, lambda: tab.collect_bar.button.cget("state") == "normal"
    )
    tab.collect_bar.screenshots.select()
    tab.collect()
    assert process_until(
        window, lambda: tab.collect_bar.button.cget("state") == "normal"
    )
    window._drain_log()

    assert received == [None, folder]
    log = tab.log.box.get("1.0", "end")
    if saved:
        assert opened == [folder]
        assert f"Screenshots saved in {folder}." in log
    else:
        assert opened == []
        assert "No screenshots" in log


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

    assert process_until(window, lambda: tab.preview.ring.score == 74)
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

    assert (
        window.title() == f"Peão Bilíngue {__version__}"
    )  # "job radar" is by the logo


def test_window_takes_the_app_icon_before_customtkinter(window: App) -> None:
    # CustomTkinter puts its own icon on the window 200 ms after it opens, unless
    # iconbitmap was called first: this flag is what it checks.
    assert window._iconbitmap_method_called


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
    assert not new_user_window.content.winfo_manager()


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
    assert new_user_window.content.winfo_manager() == "pack"
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


def test_appearance_is_saved_and_applied(
    window: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[str] = []
    # The mode is process-wide: recorded, not changed, so other tests keep theirs.
    monkeypatch.setattr(ctk, "set_appearance_mode", applied.append)
    tab = window.panels["settings"]
    assert tab.about.appearance.get() == "Same as Windows"

    tab.about.appearance.set("Dark")
    tab._save()

    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded["appearance"] == "dark"
    assert applied == ["dark"]


# --- the sidebar ------------------------------------------------------------------------


def test_the_sidebar_switches_sections(window: App) -> None:
    assert window.current == "jobs"
    assert window.panels["jobs"].winfo_manager() == "pack"

    window.sidebar.items["runs"].invoke()

    assert window.current == "runs"
    assert window.panels["runs"].winfo_manager() == "pack"
    assert not window.panels["jobs"].winfo_manager()
    assert window.sidebar.active() == "runs"
    assert window.page_title.cget("text") == "Runs"


def test_the_sidebar_counts_the_jobs_not_opened_yet(
    window: App, repository: SQLiteRepository
) -> None:
    for external_id in ("1", "2", "3"):
        repository.save_job(job(external_id), ["Python"])
    window.on_change()
    assert window.sidebar.items["jobs"].badge.cget("text").strip() == "3"

    # Opening one counts at once, with no refresh.
    window.panels["jobs"].open_job("vanhack:1")
    assert window.sidebar.items["jobs"].badge.cget("text").strip() == "2"

    repository.change_statuses(["vanhack:2", "vanhack:3"], JobStatus.discarded)
    window.on_change()
    assert not window.sidebar.items["jobs"].badge.winfo_manager()


def test_opening_a_job_marks_it_seen(window: App, repository: SQLiteRepository) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    assert tab.table.marked_unseen("vanhack:1")

    tab.open_job("vanhack:1")

    assert not tab.table.marked_unseen("vanhack:1")
    assert tab.table.marked_unseen("vanhack:2")
    viewed = {item.job.key: item.viewed for item in repository.list_jobs()}
    assert viewed == {"vanhack:1": True, "vanhack:2": False}


def test_collect_now_from_the_sidebar_opens_runs(
    window: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[bool] = []
    monkeypatch.setattr(window.panels["runs"], "collect", lambda: started.append(True))

    window.sidebar.collect_button.invoke()

    assert started == [True]
    assert window.current == "runs"


def test_selection_bar_shows_only_with_ticked_boxes(
    window: App, repository: SQLiteRepository
) -> None:
    repository.save_job(job("1"), ["Python"])
    repository.save_job(job("2"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    assert not tab.selection_bar.winfo_manager()

    tab.table.toggle("vanhack:1")
    assert tab.selection_bar.winfo_manager() == "pack"

    tab.table.clear_checked()
    assert not tab.selection_bar.winfo_manager()


def test_marks_the_selected_jobs_with_a_status(
    window: App, repository: SQLiteRepository
) -> None:
    for external_id in ("1", "2", "3"):
        repository.save_job(job(external_id), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()
    tab.table.toggle("vanhack:1")
    tab.table.toggle("vanhack:2")

    tab._mark_checked("Studying")

    studying = repository.list_jobs(status=JobStatus.studying)
    assert sorted(item.job.key for item in studying) == ["vanhack:1", "vanhack:2"]
    assert window.notices["questions"] == []  # only discarding asks first
    assert tab.table.checked() == []
    assert tab.mark_checked.get() == "Mark as…"


def test_fit_is_drawn_as_a_chip(window: App, repository: SQLiteRepository) -> None:
    analyzed = with_analyzed_job(repository, "1", fit=82)
    repository.save_job(job("2"), ["Python"])
    tab = window.panels["jobs"]
    tab.refresh()

    assert tab.table.fit_chip(analyzed.key) == "82"
    assert tab.table.fit_chip("vanhack:2") is None


def test_the_panel_swaps_to_another_job_while_open(
    window: App, repository: SQLiteRepository
) -> None:
    analyzed = with_analyzed_job(repository, "1", fit=82)
    repository.save_job(job("2", "Data Engineer"), ["Python"])
    repository.change_status("vanhack:2", JobStatus.studying)
    tab = window.panels["jobs"]
    tab.filters.status.set("All")
    tab.refresh()

    tab.open_job(analyzed.key)
    assert tab.preview.fit_card.winfo_manager() == "pack"
    tab.open_job("vanhack:2")
    window.update()

    assert tab.dialog.is_open
    assert tab.dialog.heading.cget("text") == "Data Engineer"
    assert not tab.preview.fit_card.winfo_manager()  # not analyzed
    assert tab.dialog.status_chip.cget("text") == "Studying"
    studying = tab.preview.status_buttons.buttons[JobStatus.studying]
    assert studying.cget("fg_color") != "transparent"


def test_marking_several_jobs_can_be_undone(
    window: App, repository: SQLiteRepository
) -> None:
    for external_id in ("1", "2"):
        repository.save_job(job(external_id), ["Python"])
    repository.change_status("vanhack:2", JobStatus.studying)
    tab = window.panels["jobs"]
    tab.filters.status.set("All")
    tab.refresh()
    tab.table.toggle("vanhack:1")
    tab.table.toggle("vanhack:2")

    tab._mark_checked("Applied")
    assert window.toast.visible
    assert window.toast.message.cget("text") == "2 job(s) marked as Applied."

    window.toast.action.invoke()  # Undo

    assert not window.toast.winfo_manager()
    assert [item.job.key for item in repository.list_jobs(status=JobStatus.new)] == [
        "vanhack:1"
    ]
    assert [
        item.job.key for item in repository.list_jobs(status=JobStatus.studying)
    ] == ["vanhack:2"]


def test_the_toast_goes_away_by_itself(window: App) -> None:
    window.toast.show("Saved.", seconds=0)
    assert window.toast.visible
    assert process_until(window, lambda: not window.toast.visible)


def test_the_sidebar_button_switches_light_and_dark(
    window: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[str] = []
    # The mode is process-wide: recorded, not changed, so other tests keep theirs.
    monkeypatch.setattr(ctk, "set_appearance_mode", applied.append)
    monkeypatch.setattr(ctk, "get_appearance_mode", lambda: "Dark")

    window.sidebar.mode_button.invoke()

    assert applied == ["light"]
    assert settings.appearance == "light"
    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded["appearance"] == "light"

    monkeypatch.setattr(ctk, "get_appearance_mode", lambda: "Light")
    window.sidebar.mode_button.invoke()
    assert applied == ["light", "dark"]
    recorded = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert recorded["appearance"] == "dark"
