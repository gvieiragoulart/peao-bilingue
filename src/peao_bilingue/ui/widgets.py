"""Reusable widgets: headings and hints, cards, a themed table, an in-window notice and
forms bound to Settings."""

from collections.abc import Callable
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Any, Literal

import customtkinter as ctk

from peao_bilingue.config import SECRETS, Settings
from peao_bilingue.domain.analysis import LLMProvider
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.i18n import _
from peao_bilingue.ui import theme

FieldKind = Literal["text", "integer", "boolean", "secret", "options"]


def field_type(name: str) -> FieldKind:
    """The widget type comes from Settings itself: no parallel list to keep in sync."""
    if name in SECRETS:
        return "secret"
    annotation: object = Settings.model_fields[name].annotation
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    return "text"


def theme_color(widget: str, prop: str) -> str:
    """The theme stores [light, dark]; picks by the current mode."""
    pair = ctk.ThemeManager.theme[widget][prop]
    return str(pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0])


class Heading(ctk.CTkLabel):
    """A section's title, on the scrollable tabs (LLMs, Settings)."""

    def __init__(self, master: Any, text: str) -> None:
        super().__init__(master, text=text, font=theme.section())


class Hint(ctk.CTkLabel):
    """A gray explanation next to what it explains."""

    def __init__(self, master: Any, text: str, **kwargs: Any) -> None:
        kwargs.setdefault("text_color", theme.MUTED)
        super().__init__(master, text=text, **kwargs)


class OutlineButton(ctk.CTkButton):
    """A secondary button: transparent with a border. The theme's text and hover are
    made for the accent's fill, so it sets its own, readable in both modes."""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.STRONG_BORDER)
        kwargs.setdefault("text_color", theme.TEXT)
        kwargs.setdefault("hover_color", theme.RAISED)
        super().__init__(master, **kwargs)


class Card(ctk.CTkFrame):
    """A surface with a rounded border: a section of a page."""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        kwargs.setdefault("fg_color", theme.SURFACE)
        kwargs.setdefault("corner_radius", 12)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.BORDER)
        super().__init__(master, **kwargs)


def section_card(master: Any) -> Card:
    """A card packed in a scrollable page, for one section to be packed inside it
    with padding (`pack(fill="x", padx=SECTION_PADDING, pady=SECTION_PADDING)`)."""
    card = Card(master)
    card.pack(fill="x", pady=(0, 16))
    return card


SECTION_PADDING = 18
TABLE_ROW_HEIGHT = 34


class Table(Card):
    """A ttk.Treeview with the theme's colors (CustomTkinter has no table), in a card.
    The style is applied again on every fill: a switch between light and dark
    reaches it on the next refresh."""

    def __init__(
        self, master: Any, columns: list[tuple[str, str, int]], **kwargs: Any
    ) -> None:
        super().__init__(master, **kwargs)
        self._scale = float(ctk.ScalingTracker.get_widget_scaling(self))
        self._style()

        self.tree = ttk.Treeview(
            self,
            columns=[c[0] for c in columns],
            show="headings",
            style="Peao.Treeview",
        )
        # Only the widest column stretches (or shrinks): the others keep their width,
        # or the ones on the right vanish past the edge when the panel is narrow.
        widest = max(columns, key=lambda column: column[2])[0]
        for identifier, title, width in columns:
            self.tree.heading(identifier, text=title, anchor="w")
            self.tree.column(
                identifier,
                width=width,
                minwidth=40,
                stretch=identifier == widest,
                anchor="w",
            )
        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=8)

    def _style(self) -> None:
        style = ttk.Style(self)
        # Switching the theme tells every ttk widget, even ones being destroyed:
        # only once per process.
        if style.theme_use() != "default":
            style.theme_use("default")
        background = theme.pick(theme.SURFACE)
        family = theme.text_family()
        style.layout("Peao.Treeview", [("Peao.Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Peao.Treeview",
            background=background,
            fieldbackground=background,
            foreground=theme.pick(theme.TEXT),
            rowheight=round(TABLE_ROW_HEIGHT * self._scale),
            borderwidth=0,
            font=(family, -round(13 * self._scale)),
        )
        style.map(
            "Peao.Treeview",
            background=[("selected", theme.pick(theme.ACCENT_SOFT))],
            foreground=[("selected", theme.pick(theme.ACCENT_TEXT))],
        )
        style.configure(
            "Peao.Treeview.Heading",
            background=background,
            foreground=theme.pick(theme.MUTED),
            relief="flat",
            borderwidth=0,
            padding=(4, 6),
            font=(family, -round(12 * self._scale), "bold"),
        )
        style.map("Peao.Treeview.Heading", background=[("active", background)])

    def fill(self, rows: list[tuple[str, tuple[str, ...]]]) -> None:
        """`rows` = [(id, values)]; the id comes back from `selected()`."""
        self._style()
        self.tree.delete(*self.tree.get_children())
        for identifier, values in rows:
            self.tree.insert("", "end", iid=identifier, values=values)

    def selected(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def on_select(self, callback: Callable[[], None]) -> None:
        self.tree.bind("<<TreeviewSelect>>", lambda _event: callback())


TOAST_SECONDS = 5
CHECK_ICON = ""


class Toast(ctk.CTkFrame):
    """A short notice at the bottom of the window, gone after a few seconds, with an
    optional action (Undo). Instead of a box that waits for a click."""

    def __init__(self, master: Any) -> None:
        super().__init__(
            master,
            fg_color=("#1F232A", "#343A44"),
            corner_radius=10,
            border_width=1,
            border_color=("#1F232A", "#454C57"),
        )
        self._timer: str | None = None
        self._action: Callable[[], None] | None = None
        ctk.CTkLabel(
            self,
            text=theme.icon(CHECK_ICON),
            font=theme.icons(14),
            text_color=("#5DD39E", "#5DD39E"),
            width=20,
        ).pack(side="left", padx=(14, 6), pady=10)
        self.message = ctk.CTkLabel(
            self,
            text="",
            text_color=("#F2F4F7", "#F2F4F7"),
            wraplength=520,
            justify="left",
        )
        self.message.pack(side="left", padx=(0, 14), pady=10)
        self.action = ctk.CTkButton(
            self,
            text="",
            width=70,
            height=28,
            fg_color="transparent",
            hover_color=("#343A44", "#454C57"),
            text_color=theme.ACCENT,
            font=ctk.CTkFont(weight="bold"),
            command=self._act,
        )

    def show(
        self,
        message: str,
        action: tuple[str, Callable[[], None]] | None = None,
        seconds: float = TOAST_SECONDS,
    ) -> None:
        self.message.configure(text=message)
        if action is None:
            self._action = None
            self.action.pack_forget()
        else:
            label, self._action = action
            self.action.configure(text=label)
            self.action.pack(side="left", padx=(0, 8))
        self.place(relx=0.5, rely=1.0, anchor="s", y=-24)
        self.lift()
        if self._timer is not None:
            self.after_cancel(self._timer)
        self._timer = self.after(round(seconds * 1000), self.hide)

    def hide(self) -> None:
        self._timer = None
        self.place_forget()

    @property
    def visible(self) -> bool:
        return bool(self.winfo_manager())

    def _act(self) -> None:
        action = self._action
        self.hide()
        if action is not None:
            action()


@dataclass
class Field:
    name: str  # the field's name in Settings
    label: str
    kind: FieldKind = "text"
    options: list[str] = field(default_factory=list)


def adapter_fields(cls: type[LLMProvider] | type[Notifier]) -> list[Field]:
    """An adapter's form, from what it declares in `fields`."""
    return [Field(name, label, field_type(name)) for name, label in cls.fields.items()]


class Form(ctk.CTkFrame):
    """A form bound to Settings fields: loads and returns the typed values."""

    def __init__(self, master: Any, fields: list[Field], **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.fields = fields
        self._widgets: dict[str, Any] = {}
        self.grid_columnconfigure(1, weight=1)
        for row, form_field in enumerate(fields):
            ctk.CTkLabel(self, text=form_field.label, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(8, 12), pady=4
            )
            self._widgets[form_field.name] = self._create(form_field)
            self._widgets[form_field.name].grid(
                row=row, column=1, sticky="ew", padx=(0, 8), pady=4
            )

    # Any: a CustomTkinter widget, from a library with no types.
    def _create(self, form_field: Field) -> Any:
        if form_field.kind == "boolean":
            return ctk.CTkSwitch(self, text="")
        if form_field.kind == "options":
            return ctk.CTkOptionMenu(self, values=form_field.options)
        return ctk.CTkEntry(self, show="•" if form_field.kind == "secret" else "")

    def load(self, current: Settings) -> None:
        for form_field in self.fields:
            value = getattr(current, form_field.name)
            widget = self._widgets[form_field.name]
            if form_field.kind == "boolean":
                widget.select() if value else widget.deselect()
            elif form_field.kind == "options":
                widget.set(str(value) if value else form_field.options[0])
            else:
                widget.delete(0, "end")
                widget.insert(0, "" if value is None else str(value))

    def values(self) -> dict[str, Any]:
        """Reads the widgets, already converted; an invalid integer becomes a readable
        ValueError."""
        values: dict[str, Any] = {}
        for form_field in self.fields:
            widget = self._widgets[form_field.name]
            if form_field.kind == "boolean":
                values[form_field.name] = bool(widget.get())
            elif form_field.kind == "integer":
                text = widget.get().strip()
                try:
                    values[form_field.name] = int(text)
                except ValueError:
                    raise ValueError(
                        _("'{field}' must be a whole number.").format(
                            field=form_field.label
                        )
                    ) from None
            else:
                values[form_field.name] = widget.get().strip()
        return values
