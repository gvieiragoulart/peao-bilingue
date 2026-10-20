"""Check the latest published GitHub Release for an available update."""

import logging

import httpx

from peao_bilingue.domain.updates import Release, ReleaseFeed

logger = logging.getLogger(__name__)

API = "https://api.github.com/repos/{repository}/releases/latest"
TIMEOUT_S = 10


class GitHubReleases(ReleaseFeed):
    def __init__(
        self, repository: str, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self.repository = repository
        self._client = client

    async def latest(self) -> Release | None:
        url = API.format(repository=self.repository)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "peao-bilingue",
        }
        try:
            if self._client is not None:
                response = await self._client.get(url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                    response = await client.get(url, headers=headers)
        except httpx.HTTPError as failure:
            # Offline or GitHub down: no update notice, and the app goes on.
            logger.info("Couldn't check for updates: %s", failure)
            return None
        if response.status_code != 200:
            logger.info("Update check answered %s.", response.status_code)
            return None
        try:
            data = response.json()
        except ValueError:
            logger.info("The GitHub release response isn't JSON.")
            return None
        if not isinstance(data, dict):
            logger.info("The GitHub release response isn't a JSON object.")
            return None
        tag, page = data.get("tag_name"), data.get("html_url")
        if not isinstance(tag, str) or not tag or not isinstance(page, str) or not page:
            logger.info("The GitHub release response has no tag or page.")
            return None
        return Release(version=tag, url=page)
