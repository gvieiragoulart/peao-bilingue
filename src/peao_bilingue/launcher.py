"""The .exe's entry point: no arguments opens the window; with arguments it's the CLI.

One executable serves both: the shortcut opens the app, and the scheduled task calls
`PeaoBilingue.exe run --scheduled` with no window at all (the .exe is a GUI app with no
console; with `--scheduled` the log goes to `data/logs/collection.log`).
"""

import ctypes
import sys
from pathlib import Path

from peao_bilingue.config import is_frozen

ATTACH_PARENT_PROCESS = -1
UTF8_CODE_PAGE = 65001


def attach_parent_console() -> bool:
    """A GUI .exe has no console, so its CLI prints nowhere. When it was started from
    a terminal, write to that terminal. False when there is none (e.g. Task
    Scheduler), and printing stays silent."""
    if sys.platform != "win32" or not is_frozen() or sys.stdout is not None:
        return False
    kernel32 = ctypes.windll.kernel32
    if not kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        return False
    kernel32.SetConsoleOutputCP(UTF8_CODE_PAGE)
    # The console's own device: these handles live as long as the process.
    sys.stdout = Path("CONOUT$").open("w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stderr = Path("CONOUT$").open("w", encoding="utf-8", buffering=1)  # noqa: SIM115
    return True


def main() -> None:
    # Imported here: the scheduled collection doesn't need to load Tk.
    if len(sys.argv) > 1:
        from peao_bilingue.cli import main as cli

        attach_parent_console()
        cli()
    else:
        from peao_bilingue.ui.app import main as open_window

        open_window()


if __name__ == "__main__":
    main()
