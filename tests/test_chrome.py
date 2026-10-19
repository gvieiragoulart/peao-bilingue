"""The title bar's color, as Windows wants it, and the app's icon."""

import struct

from peao_bilingue.ui.chrome import ICON, colorref


def test_colorref_is_blue_green_red() -> None:
    assert colorref("#15171C") == 0x1C1715
    assert colorref("#FFFFFF") == 0xFFFFFF
    assert colorref("#010203") == 0x030201


def test_icon_has_every_size_windows_asks_for_as_bitmaps() -> None:
    data = ICON.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)
    sizes = []
    for index in range(count):
        width, height, *_rest, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * index
        )
        sizes.append((width or 256, height or 256))
        # A BITMAPINFOHEADER, not a PNG: Tk hands Windows an empty taskbar icon
        # from PNG frames.
        assert struct.unpack_from("<I", data, offset) == (40,)
    assert {(side, side) for side in (16, 24, 32, 48, 256)} <= set(sizes)
