"""Which saved searches a job matches."""

from peao_bilingue.domain.jobs import Job
from peao_bilingue.domain.searches import Search


def applies_to_source(search: Search, source: str) -> bool:
    """A search with no sources picked applies to all of them."""
    return not search.sources or source in search.sources


def matches(job: Job, search: Search) -> bool:
    """True when the search applies to the source, some keyword shows up and no
    excluded term does."""
    if not applies_to_source(search, job.source):
        return False
    text = job.searchable_text()
    if any(term.lower() in text for term in search.exclude):
        return False
    return any(term.lower() in text for term in search.keywords)


def matching_searches(job: Job, searches: list[Search]) -> list[str]:
    return [search.name for search in searches if matches(job, search)]
