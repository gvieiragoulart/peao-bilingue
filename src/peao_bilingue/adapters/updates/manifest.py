"""Releases announced by the download site's latest.json.

The release workflow (.github/workflows/release.yml) uploads each installer to the site
and rewrites `latest.json` next to it:

    {"version": "0.2.0", "page": "https://<site>/", "installer": "...", "sha256": "...",
     "size": 59282241, "published": "2026-10-19T20:00:00Z"}

The app reads only `version` and `page` (where the user downloads it). No identifier is
sent: it is a plain GET of a static file, once when the app opens.
"""

import logging

import httpx

from peao_bilingue.domain.updates import Release, ReleaseFeed

logger = logging.getLogger(__name__)

MANIFEST = "{site}/latest.json"
TIMEOUT_S = 10


class SiteManifest(ReleaseFeed):
    def __init__(
        self, site_url: str, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self._client = client

    async def latest(self) -> Release | None:
        url = MANIFEST.format(site=self.site_url)
        headers = {"Accept": "application/json", "User-Agent": "peao-bilingue"}
        try:
            if self._client is not None:
                response = await self._client.get(url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                    response = await client.get(url, headers=headers)
        except httpx.HTTPError as failure:
            # Offline or the site down: no update notice, and the app goes on.
            logger.info("Couldn't check for updates: %s", failure)
            return None
        if response.status_code != 200:
            # 404: nothing released yet.
            logger.info("Update check answered %s.", response.status_code)
            return None
        try:
            data = response.json()
        except ValueError:
            logger.info("The update manifest isn't JSON.")
            return None
        if not isinstance(data, dict):
            logger.info("The update manifest isn't a JSON object.")
            return None
        version, page = data.get("version"), data.get("page")
        if not isinstance(version, str) or not version:
            logger.info("The update manifest has no version.")
            return None
        if not isinstance(page, str) or not page:
            page = f"{self.site_url}/"
        return Release(version=version, url=page)
