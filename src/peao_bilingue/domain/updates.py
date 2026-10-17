"""Updates: whether a newer version of the app has been released."""

import re
from abc import ABC, abstractmethod

from pydantic import BaseModel


class Release(BaseModel):
    version: str
    url: str  # the page the user downloads it from


class ReleaseFeed(ABC):
    """Where releases are published (e.g. GitHub Releases)."""

    @abstractmethod
    async def latest(self) -> Release | None:
        """The latest release, or None when there is none or it can't be reached."""


def version_tuple(text: str) -> tuple[int, ...]:
    """ "v0.2.10" -> (0, 2, 10). Anything after the numbers (e.g. "-beta") is ignored."""
    found = re.match(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(part) for part in found.group(1).split(".")) if found else ()


def is_newer(candidate: str, current: str) -> bool:
    new, old = version_tuple(candidate), version_tuple(current)
    return bool(new) and new > old
