"""Which saved searches a job matches."""

from peao_bilingue.domain.jobs import Job, strip_accents
from peao_bilingue.domain.searches import Search


def applies_to_source(search: Search, source: str) -> bool:
    """A search with no sources picked applies to all of them."""
    return not search.sources or source in search.sources


def matches(job: Job, search: Search) -> bool:
    """True when the search applies to the source, no excluded term is in the title,
    the title names one of the roles (if the search has any) and some keyword shows
    up anywhere.

    A keyword in the title also counts as a role: "Python Developer" or "APAC
    Python" for a Python search. The title is compared without accents or case.
    """
    if not applies_to_source(search, job.source):
        return False
    title = strip_accents(job.title)
    if _in_title(title, search.exclude):
        return False
    if search.roles and not _in_title(title, [*search.roles, *search.keywords]):
        return False
    return bool(_found(job.searchable_text(), search.keywords))


def _in_title(title: str, terms: list[str]) -> bool:
    return any(strip_accents(term) in title for term in terms)


def matched_keywords(job: Job, search: Search) -> list[str]:
    """The search's keywords that show up in the job, in the search's order, each
    once whatever its case."""
    return _found(job.searchable_text(), search.keywords)


def _found(text: str, terms: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for term in terms:
        lowered = term.lower()
        if lowered in text and lowered not in seen:
            seen.add(lowered)
            found.append(term)
    return found


def matching_searches(job: Job, searches: list[Search]) -> list[str]:
    return [search.name for search in searches if matches(job, search)]
