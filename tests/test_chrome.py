"""The title bar's color, as Windows wants it."""

from peao_bilingue.ui.chrome import colorref


def test_colorref_is_blue_green_red() -> None:
    assert colorref("#15171C") == 0x1C1715
    assert colorref("#FFFFFF") == 0xFFFFFF
    assert colorref("#010203") == 0x030201
