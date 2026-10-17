"""Checking for a newer version of the app."""

from peao_bilingue.domain.updates import Release, ReleaseFeed, is_newer


async def newer_release(feed: ReleaseFeed, current: str) -> Release | None:
    """The latest release when it is newer than `current`; otherwise None."""
    latest = await feed.latest()
    if latest is None or not is_newer(latest.version, current):
        return None
    return latest
