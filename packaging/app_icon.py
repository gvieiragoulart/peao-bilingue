"""Builds the app's icon, the .exe's and the window's, from an SVG in packaging/icons/.

    uv run --with pillow python packaging/app_icon.py [name]

`name` is one of the SVGs there, without the extension (default: APP_ICON). Each SVG
is rendered by Playwright's Chromium, which the project already has, straight from the
vector at every size the .ico carries: 16 px is drawn at 16 px, not shrunk from 256.
The chosen one becomes src/peao_bilingue/ui/peao_bilingue.ico, which the spec embeds
in PeaoBilingue.exe and the window shows in its title bar and on the taskbar. Every
SVG also gets a 256 px PNG preview next to it.

The SVGs are the candidates drawn on the design canvas (packaging/icons/README.md).
"""

import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).parent.parent
ICONS = ROOT / "packaging" / "icons"
OUTPUT = ROOT / "src" / "peao_bilingue" / "ui" / "peao_bilingue.ico"
APP_ICON = "p-bubble"
# What Windows picks from: 16-64 for the title bar, taskbar, Start and the desktop
# at 100-200 % scaling, 256 for Explorer's large views.
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
PREVIEW = 256


def render(page: Page, svg: str, size: int) -> Image.Image:
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(
        "<style>html,body{margin:0;background:transparent}"
        f"svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}"
    )
    png = page.screenshot(
        omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size}
    )
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> None:
    chosen = sys.argv[1] if len(sys.argv) > 1 else APP_ICON
    svgs = {path.stem: path.read_text(encoding="utf-8") for path in ICONS.glob("*.svg")}
    if chosen not in svgs:
        sys.exit(f"No {chosen}.svg in {ICONS}; there are: {', '.join(sorted(svgs))}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        for name, svg in sorted(svgs.items()):
            render(page, svg, PREVIEW).save(ICONS / f"{name}.png", optimize=True)
        frames = [render(page, svgs[chosen], size) for size in SIZES]
        browser.close()
    # 32-bit BMP frames, not PNG: with PNG frames Tk's `wm iconbitmap` loads the
    # 16 px icon but hands Windows an empty 32 px one, the taskbar's and Alt+Tab's
    # (seen by reading the window's class icons back).
    frames[-1].save(
        OUTPUT,
        format="ICO",
        sizes=[frame.size for frame in frames],
        append_images=frames[:-1],
        bitmap_format="bmp",
    )
    print(f"{OUTPUT.relative_to(ROOT)} from {chosen}.svg; previews in {ICONS}")


if __name__ == "__main__":
    main()
