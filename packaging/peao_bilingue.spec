# PyInstaller spec for Peão Bilíngue: one folder on Windows and Linux.
#
#   uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm
#
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH comes from PyInstaller
# Built by packaging/app_icon.py: the .exe's icon, and the window's (ui/chrome.py).
ICON = ROOT / "src" / "peao_bilingue" / "ui" / "peao_bilingue.ico"

datas = [
    (str(ICON), "peao_bilingue/ui"),
    # The Playwright driver (node + the JS package). Chromium is NOT bundled: the app
    # uses the installed Chrome (BROWSER_CHANNEL=chrome), the one Cloudflare accepts.
    *collect_data_files("playwright"),
    # keyring finds the OS vault backend through entry points.
    *copy_metadata("keyring"),
    # The app reads its own version from the package metadata.
    *copy_metadata("peao-bilingue"),
]

hiddenimports = [
    # The adapters are imported by the registry (importlib), not by a direct import.
    *collect_submodules("peao_bilingue"),
    *collect_submodules("keyring.backends"),
    *(["win32ctypes.core"] if sys.platform == "win32" else []),
    # SQLAlchemy loads the dialect from the URL's name ("sqlite://").
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(
    [str(ROOT / "src" / "peao_bilingue" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "_pytest", "IPython", "mypy", "ruff"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PeaoBilingue",
    icon=str(ICON) if sys.platform == "win32" else None,
    console=False,  # ignored on Linux; Windows has no console window
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PeaoBilingue", upx=False)
