"""The candidate's profile: the CV the user pastes or imports in Settings, kept as
snapshots so an analysis knows when the CV changed after it.

Older databases also hold profiles read from sources (VanHack's): they are kept only
because old analyses point at them."""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel

# The profile the user writes or pastes in the app (their CV): every job is analyzed
# with it.
MANUAL_SOURCE = "manual"


def profile_hash(data: dict[str, Any]) -> str:
    """A hash of the profile's canonical JSON: it changes only when the content does."""
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Profile(BaseModel):
    source: str  # MANUAL_SOURCE for the CV
    data: dict[str, Any]
    text: str  # readable version, used in the prompt
    content_hash: str
    # When the snapshot was saved: set by the repository, None before saving.
    saved_at: datetime | None = None


class ProfileRepository(ABC):
    @abstractmethod
    def save_profile(self, profile: Profile) -> tuple[int, bool]:
        """Saves a new snapshot only if the content changed since the source's
        last one. Returns (id, changed)."""

    @abstractmethod
    def last_profile(self, source: str) -> tuple[int, Profile] | None: ...
