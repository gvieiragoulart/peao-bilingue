"""Hacker News "Ask HN: Who is hiring?": the monthly thread where companies post jobs,
one top-level comment each, read through the HN Search API (Algolia), the search that
Hacker News itself links to.

Two calls per collection, with the base's cache (12 h): the latest threads by the
`whoishiring` account (`search_by_date`), then the newest "Who is hiring?" thread
whole (`items/<id>`, ~270 posts, ~0.5 MB). Fetching each post from the official
Firebase API would take hundreds of calls.

Most posts are for the US or Europe, so a post stays only when its text names one of
`hackernews_places` (Brazil, LATAM, worldwide, anywhere...). "Visa" isn't a place: posts
say "we're not able to sponsor visas" as often as they offer it.

Posts are free text: the first paragraph is the header ("Company | Role | Place |
REMOTE"), which becomes the title, and its first part the company. The text goes
through `remove_contact_data`: posts often give a founder's email. Usernames aren't
kept.
"""

import asyncio
import re
from pathlib import Path
from typing import Any, ClassVar

import httpx

from peao_bilingue.adapters.sources.api import ApiSource, Json, unexpected_format
from peao_bilingue.adapters.sources.html import html_to_text
from peao_bilingue.config import settings
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job, JobSummary, strip_accents
from peao_bilingue.domain.privacy import remove_contact_data
from peao_bilingue.factories import sources
from peao_bilingue.i18n import _

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
SEARCH_PARAMS = {"tags": "story,author_whoishiring", "hitsPerPage": "10"}
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"
POST_URL = "https://news.ycombinator.com/item?id={id}"
THREAD_TITLE = "Ask HN: Who is hiring?"
MAX_TITLE = 140
# "Company | Role", "Company - Role", "Company (Remote) — Role": where the company ends.
_COMPANY_END = re.compile(r"\s*(?:\||—|–| - |\(|<|https?://)")


@sources.register("hackernews")
class HackerNews(ApiSource):
    name = "hackernews"
    label = "Hacker News: Who is hiring?"
    description = _(
        "The monthly thread where companies post jobs on Hacker News; only posts "
        "open to Brazil, Latin America or anywhere. No account."
    )
    about = _(
        "Two calls per collection, through the HN Search API by Algolia: one finds "
        "the newest thread, the other brings it whole; kept for 12 hours. A post "
        "stays only when it names one of the places (one per line, without "
        "accents). Not visa: as many posts say they cannot sponsor one as offer it."
    )
    site = "https://news.ycombinator.com/submitted?id=whoishiring"
    fields: ClassVar[dict[str, str]] = {
        "hackernews_places": _("Places"),
    }
    brand = "Hacker News"
    url = SEARCH_URL
    validity_s = 12 * 3600

    def __init__(
        self,
        *,
        places: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
        cache: Path | None = None,
    ) -> None:
        super().__init__(client=client, cache=cache)
        chosen = settings.hackernews_places if places is None else places
        self.places = [strip_accents(place) for place in chosen if place.strip()]

    def params(self) -> dict[str, str]:
        return SEARCH_PARAMS

    async def search(self, term: str) -> list[JobSummary]:
        if self._all_jobs is None:
            # The thread to read depends on the first answer; the base then filters.
            thread = await self._latest_thread()
            self._all_jobs = await self._query(ITEM_URL.format(id=thread), {})
        return await super().search(term)

    async def _latest_thread(self) -> str:
        found = await self._query_raw(SEARCH_URL, SEARCH_PARAMS)
        hits = found.get("hits") if isinstance(found, dict) else None
        if not isinstance(hits, list):
            raise unexpected_format(self.brand, _("an object"))
        for hit in hits:
            if str(hit.get("title") or "").startswith(THREAD_TITLE):
                return str(hit["objectID"])
        raise CollectionError(_("Hacker News: no Who is hiring? thread found."))

    async def _query_raw(self, url: str, params: dict[str, str]) -> Json:
        """A cached call whose answer isn't jobs (the thread lookup)."""
        query = {"url": url, "params": params}
        file = self._cache_file(url, params)
        data = await asyncio.to_thread(self._read_cache, file, query)
        if data is None:
            data = await self._download(url, params)
            await asyncio.to_thread(self._write_cache, file, query, data)
        return data

    def convert(self, data: Json) -> list[Job]:
        if not isinstance(data, dict) or not isinstance(data.get("children"), list):
            raise unexpected_format(self.brand, _("an object"))
        thread = str(data.get("title") or "")
        jobs = [
            _job(post, thread)
            for post in data["children"]
            if isinstance(post, dict) and post.get("text") and post.get("id")
        ]
        return [job for job in jobs if self._open_here(job)]

    def _open_here(self, job: Job) -> bool:
        if not self.places:
            return True
        text = strip_accents(f"{job.title}\n{job.description}")
        return any(place in text for place in self.places)


def _header(html: str) -> str:
    # The first paragraph: "Company | Role | Place | REMOTE".
    return html_to_text(html.partition("<p>")[0])


def _company(header: str) -> str | None:
    company = _COMPANY_END.split(header, maxsplit=1)[0].strip(" |-")
    return company or None


def _job(post: dict[str, Any], thread: str) -> Job:
    header = _header(str(post["text"]))
    text, _removed = remove_contact_data(html_to_text(str(post["text"])))
    title, _removed = remove_contact_data(header)
    if len(title) > MAX_TITLE:
        title = title[: MAX_TITLE - 1].rstrip() + "…"
    return Job(
        source=HackerNews.name,
        external_id=str(post["id"]),
        url=POST_URL.format(id=post["id"]),  # the post on Hacker News
        title=title or _("(untitled)"),
        company=_company(header),
        published_at=post.get("created_at"),
        description=text,
        extras={"via": HackerNews.brand, "thread": thread},
    )
