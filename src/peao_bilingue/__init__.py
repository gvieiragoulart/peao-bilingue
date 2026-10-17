"""Peão Bilíngue: a desktop job radar."""

from importlib.metadata import PackageNotFoundError, version

APP_NAME = "Peão Bilíngue"

try:
    __version__ = version("peao-bilingue")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"
