"""The candidate's profile: one per source, with a history of changes."""

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

# The profile the user writes or pastes in the app (their CV): used for the jobs of
# sources that don't have a profile of their own.
MANUAL_SOURCE = "manual"


def profile_hash(data: dict[str, Any]) -> str:
    """A hash of the profile's canonical JSON: it changes only when the content does."""
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Profile(BaseModel):
    # Each source has its own: the profile on VanHack is not the one on LinkedIn.
    source: str
    data: dict[str, Any]
    text: str  # readable version, used in the prompt
    content_hash: str


class ProfileSource(ABC):
    """A source that can read the profile the user keeps there (e.g. VanHack)."""

    @abstractmethod
    async def read_profile(self) -> Profile:
        """The profile kept in this source, with `source` set to its name."""


class ProfileRepository(ABC):
    @abstractmethod
    def save_profile(self, profile: Profile) -> tuple[int, bool]:
        """Saves a new snapshot only if the content changed since the source's
        last one. Returns (id, changed)."""

    @abstractmethod
    def last_profile(self, source: str) -> tuple[int, Profile] | None: ...

    @abstractmethod
    def profile_history(self, source: str) -> list[dict[str, Any]]:
        """The source's snapshots, newest first, with the fields that changed."""

    @abstractmethod
    def sources_with_profile(self) -> list[str]: ...
