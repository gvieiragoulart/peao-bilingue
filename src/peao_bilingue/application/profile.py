"""A profile the user writes or pastes (their CV), for sources that don't have one."""

from peao_bilingue.domain.privacy import Removed, remove_contact_data
from peao_bilingue.domain.profile import MANUAL_SOURCE, Profile, profile_hash


def manual_profile(text: str) -> tuple[Profile, Removed]:
    """The pasted text as the `manual` profile, without contact data, and what was
    removed so the screen can say so."""
    clean, removed = remove_contact_data(text)
    data = {"text": clean}
    profile = Profile(
        source=MANUAL_SOURCE,
        data=data,
        text=clean,
        content_hash=profile_hash(data),
    )
    return profile, removed


def clean_notes(text: str) -> tuple[str, Removed]:
    """The user's notes go into every prompt: the same cleanup as the profile."""
    return remove_contact_data(text)
