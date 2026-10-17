"""Reusable widgets: a themed table and forms bound to Settings."""

from collections.abc import Callable
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Any, Literal

import customtkinter as ctk

from peao_bilingue.config import SECRETS, Settings
from peao_bilingue.domain.analysis import LLMProvider
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.i18n import _

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


class Table(ctk.CTkFrame):
    """A ttk.Treeview with the theme's colors (CustomTkinter has no table)."""

    def __init__(
        self, master: Any, columns: list[tuple[str, str, int]], **kwargs: Any
    ) -> None:
        super().__init__(master, **kwargs)
        style = ttk.Style(self)
        style.theme_use("default")
        background = theme_color("CTkFrame", "fg_color")
        text = theme_color("CTkLabel", "text_color")
        highlight = theme_color("CTkButton", "fg_color")
        style.configure(
            "Peao.Treeview",
            background=background,
            fieldbackground=background,
            foreground=text,
            rowheight=26,
            borderwidth=0,
        )
        style.map("Peao.Treeview", background=[("selected", highlight)])
        style.configure(
            "Peao.Treeview.Heading",
            background=background,
            foreground=text,
            relief="flat",
        )

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
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def fill(self, rows: list[tuple[str, tuple[str, ...]]]) -> None:
        """`rows` = [(id, values)]; the id comes back from `selected()`."""
        self.tree.delete(*self.tree.get_children())
        for identifier, values in rows:
            self.tree.insert("", "end", iid=identifier, values=values)

    def selected(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def on_select(self, callback: Callable[[], None]) -> None:
        self.tree.bind("<<TreeviewSelect>>", lambda _event: callback())


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
