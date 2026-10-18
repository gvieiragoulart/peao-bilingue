"""Each source's icon and what its dialog configures."""

import tkinter as tk

import pytest

from peao_bilingue import factories
from peao_bilingue.config import Settings
from peao_bilingue.ui import source_icons
from peao_bilingue.ui.source_logos import LOGOS
from peao_bilingue.ui.widgets import adapter_fields, field_type


def test_every_source_has_a_logo_or_a_monogram() -> None:
    for name in factories.sources.available():
        assert source_icons.has_logo(name) or name in source_icons.MONOGRAMS, name
    # Remote OK's terms ask not to use its logo.
    assert not source_icons.has_logo("remoteok")
    assert source_icons.monogram("remoteok")[0] == "RO"


def test_a_source_without_an_icon_gets_its_first_letter() -> None:
    letters, color = source_icons.monogram("unknown")
    assert letters == "U"
    assert color == source_icons.monogram("unknown")[1]  # always the same one


def test_every_field_a_source_declares_is_a_setting() -> None:
    for name in factories.sources.available():
        cls = factories.sources.class_of(name)
        assert set(cls.fields) <= Settings.model_fields.keys(), name


def test_list_settings_get_one_item_per_line() -> None:
    assert field_type("company_boards") == "list"
    assert field_type("himalayas_country") == "text"
    vanhack = factories.sources.class_of("vanhack")
    assert [(f.name, f.kind) for f in adapter_fields(vanhack)] == [
        ("headless", "boolean"),
        ("max_listing_scrolls", "integer"),
    ]


@pytest.mark.integration
def test_every_logo_is_a_png_tk_reads() -> None:
    root = tk.Tk()
    try:
        for name, sizes in LOGOS.items():
            for size, data in sizes.items():
                image = tk.PhotoImage(master=root, data=data)
                assert (image.width(), image.height()) == (size, size), name
        # The nearest size is drawn (a tie goes to the bigger one), made once per root.
        nearest = source_icons.logo(root, "github", 30)
        assert nearest is not None
        assert nearest.width() == 32
        assert source_icons.logo(root, "github", 30) is nearest
        assert source_icons.logo(root, "remoteok", 30) is None
    finally:
        root.destroy()
