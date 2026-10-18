"""The first-run guide: from an empty app to a first collection, in six steps.

It takes the place of the tabs instead of opening a window of its own (Windows may
open a second window behind the first). Nothing is saved until Finish: skipping
leaves everything as it was. Settings → "Run the setup guide again" reopens it.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING, Any

import customtkinter as ctk
from pydantic import ValidationError

from peao_bilingue import APP_NAME, config, factories
from peao_bilingue.adapters.documents import read_document
from peao_bilingue.application.profile import manual_profile
from peao_bilingue.config import settings
from peao_bilingue.domain.collection import ManualSession
from peao_bilingue.domain.profile import ProfileSource
from peao_bilingue.domain.repository import Repository
from peao_bilingue.domain.schedule import check_time
from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _
from peao_bilingue.ui import presentation
from peao_bilingue.ui.widgets import Form, OutlineButton, adapter_fields

if TYPE_CHECKING:
    from peao_bilingue.ui.app import App

WINDOWS_NOTICE = "windows"
WRAP = 760


def needs_onboarding(repository: Repository) -> bool:
    """A new user: the guide was never finished or skipped, and there's no search and
    no profile. Whoever set the app up before the guide existed doesn't get it."""
    return not (
        settings.onboarding_done
        or repository.list_searches()
        or repository.sources_with_profile()
    )


@dataclass
class Answers:
    """What the guide saves at the end."""

    search: Search | None
    sources: list[str]
    cv: str
    llm: str
    llm_settings: dict[str, Any]
    windows_notice: bool
    collection_time: str | None  # None = leave the daily collection as it is


@dataclass
class Step:
    title: str
    frame: Any  # a CustomTkinter frame
    check: Callable[[], object]  # raises ValueError when the step isn't filled right


class Onboarding(ctk.CTkFrame):
    def __init__(self, master: Any, app: "App", on_close: Callable[[], None]) -> None:
        super().__init__(master)
        self.app = app
        self.on_close = on_close
        self.current = 0

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))
        self.step_label = ctk.CTkLabel(header, text="", text_color="gray55")
        self.step_label.pack(anchor="w")
        self.title_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(anchor="w")

        # Packed before the content, so a tall step never pushes the buttons away.
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=(8, 20))
        OutlineButton(
            footer,
            text=_("Skip the guide"),
            width=130,
            command=self.skip,
        ).pack(side="left")
        self.next_button = ctk.CTkButton(
            footer, text=_("Next"), width=120, command=self.next
        )
        self.next_button.pack(side="right")
        self.back_button = OutlineButton(
            footer,
            text=_("Back"),
            width=100,
            command=self.back,
        )
        self.back_button.pack(side="right", padx=8)

        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=16)

        self.steps = [
            Step(_("Welcome"), self._welcome(), lambda: None),
            Step(_("What are you looking for?"), self._search(), self.read_search),
            Step(_("Where to look"), self._sources(), self.read_sources),
            Step(_("Your profile"), self._profile(), self.read_cv),
            Step(_("Who analyzes the jobs"), self._llm(), self.read_llm),
            Step(_("Collection and notices"), self._notices(), self.read_notices),
        ]
        self._show(0)

    # --- navigation ------------------------------------------------------------------

    def _show(self, index: int) -> None:
        self.steps[self.current].frame.pack_forget()
        self.current = index
        step = self.steps[index]
        step.frame.pack(fill="both", expand=True, padx=8)
        self.step_label.configure(
            text=_("Step {number} of {total}").format(
                number=index + 1, total=len(self.steps)
            )
        )
        self.title_label.configure(text=step.title)
        last = index == len(self.steps) - 1
        self.next_button.configure(text=_("Finish") if last else _("Next"))
        self.back_button.configure(state="normal" if index else "disabled")

    def next(self) -> None:
        try:
            self.steps[self.current].check()
        except ValueError as failure:
            self.app.show_error(failure)
            return
        if self.current == len(self.steps) - 1:
            self.finish()
        else:
            self._show(self.current + 1)

    def back(self) -> None:
        if self.current:
            self._show(self.current - 1)

    def skip(self) -> None:
        config.save({"onboarding_done": True})
        self.on_close()

    # --- the steps ---------------------------------------------------------------------

    def _page(self) -> Any:
        return ctk.CTkFrame(self.content, fg_color="transparent")

    @staticmethod
    def _text(master: Any, text: str, **kwargs: Any) -> None:
        ctk.CTkLabel(master, text=text, wraplength=WRAP, justify="left", **kwargs).pack(
            anchor="w", pady=(0, 8)
        )

    def _welcome(self) -> Any:
        page = self._page()
        self._text(
            page,
            _(
                "{app} collects jobs from several sites every day, keeps the ones that "
                "match your searches and tells you about the new ones. When a job "
                "interests you, an LLM compares it with your profile: a fit score, what "
                "to prepare and 20 interview questions."
            ).format(app=APP_NAME),
        )
        self._text(page, _("How your data is treated"), font=ctk.CTkFont(weight="bold"))
        for line in (
            _(
                "Everything stays on this computer: the jobs, your profile and the "
                "settings. Keys and passwords go to Windows Credential Manager."
            ),
            _(
                "The collection calls no LLM. Your profile only goes to the LLM you "
                "pick, when you click Analyze on a job."
            ),
            _(
                "Emails, phone numbers and links are removed from your CV before it's "
                "saved."
            ),
            _(
                "Sites that need an account use your own manual login: the app never "
                "types a password or solves a human check."
            ),
        ):
            self._text(page, "•  " + line)
        self._text(
            page,
            _("It takes about 3 minutes, and everything can be changed later."),
            text_color="gray55",
        )
        return page

    def _search(self) -> Any:
        page = self._page()
        self._text(
            page,
            _(
                "Jobs whose title, skills or description have one of the keywords are "
                "kept. You can add more searches later, on the Searches tab."
            ),
        )

        def entry(label: str, example: str) -> ctk.CTkEntry:
            ctk.CTkLabel(page, text=label).pack(anchor="w")
            widget = ctk.CTkEntry(page, width=420, placeholder_text=example)
            widget.pack(anchor="w", pady=(0, 10))
            return widget

        self.search_keywords = entry(
            _("Keywords (comma separated)"), _("e.g. python, django, backend")
        )
        self.search_exclude = entry(
            _("Exclude when present (optional)"), _("e.g. intern, wordpress")
        )
        self.search_name = entry(_("Name (optional)"), _("e.g. Python backend"))
        return page

    def _sources(self) -> Any:
        page = self._page()
        self._text(
            page,
            _(
                "Public APIs need no account. Sites with a login use yours: after the "
                "guide, log in on the Sources tab."
            ),
        )
        self.source_boxes: dict[str, ctk.CTkCheckBox] = {}
        for name in factories.sources.available():
            cls = factories.sources.class_of(name)
            box = ctk.CTkCheckBox(page, text=cls.label)
            box.pack(anchor="w", pady=(6, 0))
            if name in settings.enabled_sources:
                box.select()
            self.source_boxes[name] = box
            features = []
            if issubclass(cls, ManualSession):
                features.append(_("needs your login"))
            if issubclass(cls, ProfileSource):
                features.append(_("reads your profile"))
            if features:
                ctk.CTkLabel(page, text=" · ".join(features), text_color="gray55").pack(
                    anchor="w", padx=(30, 0)
                )
        return page

    def _profile(self) -> Any:
        page = self._page()
        self._text(
            page,
            _(
                "Paste your CV or LinkedIn profile, or import a .pdf, .txt or .md file. "
                "It's what the LLM compares each job with. Emails, phone numbers, links "
                "and CPF are removed automatically; remove your name and address "
                "yourself. You can also skip this and do it later, on the Profile tab."
            ),
        )
        OutlineButton(
            page,
            text=_("Import file…"),
            width=130,
            command=self._import,
        ).pack(anchor="w", pady=(0, 8))
        self.cv = ctk.CTkTextbox(page, wrap="word", height=260)
        self.cv.pack(fill="x")
        return page

    def _import(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self,
            title=_("Import your CV"),
            filetypes=[(_("CV or profile"), "*.pdf *.txt *.md")],
        )
        if not chosen:
            return
        try:
            text = read_document(Path(chosen))
        except Exception as failure:  # noqa: BLE001 - a broken file is a notice
            self.app.show_error(failure)
            return
        if not text:
            self.app.show_error(
                ValueError(
                    _(
                        "No text found in the file (a scanned PDF is an image). Paste "
                        "the text instead."
                    )
                )
            )
            return
        self.cv.delete("1.0", "end")
        self.cv.insert("1.0", text)

    def _llm(self) -> Any:
        page = self._page()
        self._text(
            page,
            _(
                "Ollama runs on your computer, for free, but needs installing "
                "(ollama.com) and a good graphics card. Claude, OpenAI and Gemini need "
                "an API key and charge per analysis (cents each). Nothing is spent until "
                "you click Analyze on a job."
            ),
        )
        self._llm_names = {
            factories.llms.class_of(name).label: name
            for name in factories.llms.available()
        }
        self.llm_menu = ctk.CTkOptionMenu(
            page,
            values=list(self._llm_names),
            width=260,
            command=lambda _label: self._show_llm_form(),
        )
        self.llm_menu.pack(anchor="w", pady=(0, 8))
        self.llm_forms: dict[str, Form] = {}
        for name in self._llm_names.values():
            form = Form(page, adapter_fields(factories.llms.class_of(name)))
            form.load(settings)
            self.llm_forms[name] = form
        current = next(
            (
                label
                for label, name in self._llm_names.items()
                if name == settings.analysis_llm
            ),
            next(iter(self._llm_names)),
        )
        self.llm_menu.set(current)
        self._show_llm_form()
        self._text(
            page,
            _("The keys live in Windows Credential Manager, not in a file."),
            text_color="gray55",
        )
        return page

    def pick_llm(self, name: str) -> None:
        """Picks a provider as a click on the menu would."""
        label = next(label for label, value in self._llm_names.items() if value == name)
        self.llm_menu.set(label)
        self._show_llm_form()

    def _show_llm_form(self) -> None:
        picked = self._llm_names[self.llm_menu.get()]
        for name, form in self.llm_forms.items():
            if name == picked:
                form.pack(fill="x", pady=(0, 8), after=self.llm_menu)
            else:
                form.pack_forget()

    def _notices(self) -> Any:
        page = self._page()
        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(anchor="w")
        self.daily = ctk.CTkSwitch(row, text=_("Collect every day at"))
        self.daily.pack(side="left")
        self.daily.select()
        self.time = ctk.CTkEntry(row, width=70)
        self.time.insert(0, settings.collection_time)
        self.time.pack(side="left", padx=8)
        self._text(
            page,
            _(
                "Even with the app closed (Windows Task Scheduler). If the computer is "
                "off at that time, it collects when it's turned on."
            ),
            text_color="gray55",
        )
        notifier = factories.notifiers.class_of(WINDOWS_NOTICE)
        self.windows_notice = ctk.CTkSwitch(page, text=notifier.label)
        self.windows_notice.pack(anchor="w", pady=(8, 0))
        if WINDOWS_NOTICE in settings.notifiers:
            self.windows_notice.select()
        self._text(
            page,
            _("Email and WhatsApp can be set up later, on the Settings tab."),
            text_color="gray55",
        )
        return page

    # --- reading the answers -------------------------------------------------------------

    def read_search(self) -> Search | None:
        keywords = presentation.terms(self.search_keywords.get())
        exclude = presentation.terms(self.search_exclude.get())
        name = self.search_name.get().strip() or ", ".join(keywords)
        if not (keywords or exclude or name):
            return None  # left blank: added later on the Searches tab
        try:
            return Search(name=name, keywords=keywords, exclude=exclude)
        except ValidationError:
            raise ValueError(
                _("Give it at least one keyword, or leave the search blank.")
            ) from None

    def read_sources(self) -> list[str]:
        sources = [name for name, box in self.source_boxes.items() if box.get()]
        if not sources:
            raise ValueError(_("Pick at least one source."))
        return sources

    def read_cv(self) -> str:
        return str(self.cv.get("1.0", "end")).strip()

    def read_llm(self) -> tuple[str, dict[str, Any]]:
        name = self._llm_names[self.llm_menu.get()]
        return name, self.llm_forms[name].values()

    def read_notices(self) -> tuple[bool, str | None]:
        time = self.time.get().strip() if self.daily.get() else None
        if time is not None:
            check_time(time)
        return bool(self.windows_notice.get()), time

    def answers(self) -> Answers:
        llm, llm_settings = self.read_llm()
        windows_notice, collection_time = self.read_notices()
        return Answers(
            search=self.read_search(),
            sources=self.read_sources(),
            cv=self.read_cv(),
            llm=llm,
            llm_settings=llm_settings,
            windows_notice=windows_notice,
            collection_time=collection_time,
        )

    # --- saving --------------------------------------------------------------------

    def finish(self) -> None:
        try:
            answers = self.answers()
        except ValueError as failure:
            self.app.show_error(failure)
            return
        repository = self.app.repository
        if answers.search is not None:
            repository.save_search(answers.search)
        cleaned = None
        if answers.cv:
            profile, removed = manual_profile(answers.cv)
            repository.save_profile(profile)
            cleaned = presentation.saved_without_contact_data(removed)

        # Email or WhatsApp turned on earlier stay as they are.
        notifiers = [name for name in settings.notifiers if name != WINDOWS_NOTICE]
        if answers.windows_notice:
            notifiers.insert(0, WINDOWS_NOTICE)
        changes: dict[str, Any] = {
            **answers.llm_settings,
            "enabled_sources": answers.sources,
            "analysis_llm": answers.llm,
            "notifiers": notifiers,
            "onboarding_done": True,
        }
        if answers.collection_time is not None:
            changes["collection_time"] = answers.collection_time
        config.save(changes)

        if answers.collection_time is not None:
            # PowerShell takes about a second: off the window's thread.
            self.app.run(
                asyncio.to_thread(self.app.scheduler.schedule, answers.collection_time),
                on_done=lambda _result: self.app.on_change(),
            )
        self.on_close()
        message = _(
            'All set. Click "Collect now" on the Runs tab for the first collection, '
            "or wait for the daily one."
        )
        if any(
            issubclass(factories.sources.class_of(name), ManualSession)
            for name in answers.sources
        ):
            message += "\n\n" + _(
                "Before the first collection, log in to the sources that need it, on "
                "the Sources tab."
            )
        if cleaned:
            message += "\n\n" + _("Your CV:") + " " + cleaned
        self.app.inform(message)
