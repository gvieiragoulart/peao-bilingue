"""The .exe's entry point: no arguments opens the window; with arguments it's the CLI.

One executable serves both: the shortcut opens the app, and the scheduled task calls
`PeaoBilingue.exe run --scheduled` with no window at all (the .exe is a GUI app with no
console; with `--scheduled` the log goes to `collection.log`).
"""

import sys


def main() -> None:
    # Imported here: the scheduled collection doesn't need to load Tk.
    if len(sys.argv) > 1:
        from peao_bilingue.cli import main as cli

        cli()
    else:
        from peao_bilingue.ui.app import main as open_window

        open_window()


if __name__ == "__main__":
    main()
