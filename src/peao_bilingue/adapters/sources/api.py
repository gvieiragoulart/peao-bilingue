"""Base for sources that read a public JSON API (Remotive, Remote OK...).

These APIs ask for few calls, so:

- **one call per collection** when the API returns the whole list: each term is
  filtered here, against the same text the search filter looks at;
- **one call per term** when the API only searches (e.g. Himalayas, 20 per page): the
  source defines `params_for_term`, and there is a pause between calls;
- **a few fixed calls** when the list comes in parts (e.g. one RSS feed per category
  on We Work Remotely): the source defines `queries`;
- **a disk cache** per query (`validity_s`): collecting several times a day doesn't
  call again;
- `detail` calls nothing: the listing already has the whole job.

Each source only says the URL, the parameters and how a response becomes jobs.
"""

import asyncio
import hashlib
import json
import time
from abc import abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Self

import httpx

from peao_bilingue.config import DATA_DIR
from peao_bilingue.domain.collection import JobSource
from peao_bilingue.domain.errors import CollectionError
from peao_bilingue.domain.jobs import Job, JobSummary
from peao_bilingue.i18n import _

# What an API's JSON has at the top level; each source checks the contents.
Json = dict[str, Any] | list[Any]

AGENT = "peao-bilingue/0.1 (personal job radar)"
TIMEOUT_S = 30


def fix_encoding(text: str) -> str:
    """Undoes UTF-8 read as Latin-1 (an en dash showing up as three odd characters),
    which some APIs send. Text without that defect comes back unchanged."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


class ApiSource(JobSource):
    url: ClassVar[str]
    brand: ClassVar[str]  # how the source asks to be credited ("Remote OK")
    validity_s: ClassVar[int] = 6 * 3600
    # Pause between two real calls in the same collection (cache hits don't count).
    pause_s: ClassVar[float] = 0.0

    def __init__(
        self, *, client: httpx.AsyncClient | None = None, cache: Path | None = None
    ) -> None:
        self.cache = cache or DATA_DIR / "cache" / f"{self.name}.json"
        self._external_client = client
        self._client: httpx.AsyncClient | None = None
        self._seen: dict[str, Job] = {}
        self._all_jobs: dict[str, Job] | None = None
        self._already_called = False

    def params(self) -> dict[str, str]:
        """The single query, when the API returns the whole list."""
        return {}

    def params_for_term(self, term: str) -> dict[str, str] | None:
        """The query for one term, when the API only searches. None = single query."""
        return None

    def queries(self) -> list[tuple[str, dict[str, str]]]:
        """(url, parameters) of each call that builds the whole list."""
        return [(self.url, self.params())]

    def decode(self, response: httpx.Response) -> Json:
        """The response body as Json; sources that don't speak JSON (RSS) override it."""
        data = response.json()
        if not isinstance(data, dict | list):
            raise ValueError("the top of the response is neither an object nor a list")
        return data

    @abstractmethod
    def convert(self, data: Json) -> list[Job]:
        """The API's response (already parsed) becomes jobs."""

    async def __aenter__(self) -> Self:
        self._client = self._external_client or httpx.AsyncClient(
            timeout=TIMEOUT_S, headers={"User-Agent": AGENT}
        )
        return self

    async def __aexit__(self, *exception: object) -> None:
        if self._client is not None and self._external_client is None:
            await self._client.aclose()
        self._client = None

    async def search(self, term: str) -> list[JobSummary]:
        term_params = self.params_for_term(term)
        if term_params is not None:
            # The API itself already searched for the term.
            found: list[JobSummary] = list(
                (await self._query(self.url, term_params)).values()
            )
            return found
        if self._all_jobs is None:
            self._all_jobs = {}
            for url, params in self.queries():
                self._all_jobs.update(await self._query(url, params))
        searched = term.lower()
        return [
            job for job in self._all_jobs.values() if searched in job.searchable_text()
        ]

    async def detail(self, summary: JobSummary) -> Job:
        return self._seen[summary.external_id]

    async def _query(self, url: str, params: dict[str, str]) -> dict[str, Job]:
        query = {"url": url, "params": params}
        file = self._cache_file(url, params)
        data = await asyncio.to_thread(self._read_cache, file, query)
        if data is None:
            data = await self._download(url, params)
            await asyncio.to_thread(self._write_cache, file, query, data)
        jobs = {job.external_id: job for job in self.convert(data)}
        self._seen.update(jobs)
        return jobs

    def _cache_file(self, url: str, params: dict[str, str]) -> Path:
        if (url, params) == self.queries()[0]:
            return self.cache
        # The other queries (per term or per part): one file each.
        key = hashlib.sha1(
            json.dumps([url, params], sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return self.cache.with_name(f"{self.cache.stem}-{key}{self.cache.suffix}")

    async def _download(self, url: str, params: dict[str, str]) -> Json:
        response = await self._get(url, params)
        try:
            data = self.decode(response)
        except ValueError as failure:
            raise CollectionError(
                _("{source} is down or there is no network: {error}").format(
                    source=self.brand, error=failure
                )
            ) from failure
        if not isinstance(data, dict | list):
            raise CollectionError(
                _("{source} answered in an unexpected format.").format(
                    source=self.brand
                )
            )
        return data

    async def _get(self, url: str, params: dict[str, str]) -> httpx.Response:
        """A real call, with the pause between calls and the errors made readable."""
        if self._client is None:
            raise RuntimeError("Use the source inside `async with`.")
        if self._already_called and self.pause_s:
            await asyncio.sleep(self.pause_s)
        self._already_called = True
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as failure:
            code = failure.response.status_code
            if code == 429:
                raise CollectionError(
                    _("{source} refused: too many calls. Try again later.").format(
                        source=self.brand
                    )
                ) from failure
            raise CollectionError(
                _("{source} answered with error {code}.").format(
                    source=self.brand, code=code
                )
            ) from failure
        except httpx.HTTPError as failure:
            raise CollectionError(
                _("{source} is down or there is no network: {error}").format(
                    source=self.brand, error=failure
                )
            ) from failure
        return response

    def _read_cache(self, file: Path, query: dict[str, Any]) -> Json | None:
        if not file.exists():
            return None
        if time.time() - file.stat().st_mtime > self.validity_s:
            return None
        saved = json.loads(file.read_text(encoding="utf-8"))
        # A cache for another query (e.g. another category), or in an older format,
        # doesn't count.
        if saved.get("query") != query:
            return None
        data = saved.get("data")
        return data if isinstance(data, dict | list) else None

    def _write_cache(self, file: Path, query: dict[str, Any], data: Json) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            json.dumps({"query": query, "data": data}, ensure_ascii=False),
            encoding="utf-8",
        )


def unexpected_format(source: str, expected: str) -> CollectionError:
    """The API changed the shape of its response."""
    return CollectionError(
        _("{source} changed its response format (expected {expected}).").format(
            source=source, expected=expected
        )
    )
