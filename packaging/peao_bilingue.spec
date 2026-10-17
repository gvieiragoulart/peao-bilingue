# PyInstaller spec for Peão Bilíngue: one folder, a GUI app (no console).
#
#   uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm
#
# Builds dist/PeaoBilingue/PeaoBilingue.exe. With no arguments it opens the window; with
# arguments it is the CLI (that is how the scheduled task runs the collection).
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH comes from PyInstaller

datas = [
    # The Playwright driver (node + the JS package). Chromium is NOT bundled: the app
    # uses the installed Chrome (BROWSER_CHANNEL=chrome), the one Cloudflare accepts.
    *collect_data_files("playwright"),
    # keyring finds the Windows vault backend through entry points.
    *copy_metadata("keyring"),
]

hiddenimports = [
    # The adapters are imported by the registry (importlib), not by a direct import.
    *collect_submodules("peao_bilingue"),
    *collect_submodules("keyring.backends"),
    "win32ctypes.core",
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
    console=False,  # a GUI app; the scheduled collection writes to collection.log
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PeaoBilingue", upx=False)
