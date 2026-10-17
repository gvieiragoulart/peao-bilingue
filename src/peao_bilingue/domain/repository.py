"""The whole repository, for whoever uses all of it (the window and composition).

Each use case depends only on the ports it needs (`JobRepository`,
`ProfileRepository`...); this union exists so the window doesn't have to carry
five objects that, in SQLite, are the same database.
"""

from abc import ABC

from peao_bilingue.domain.analysis import AnalysisRepository
from peao_bilingue.domain.collection import RunRepository
from peao_bilingue.domain.jobs import JobRepository
from peao_bilingue.domain.profile import ProfileRepository
from peao_bilingue.domain.searches import SearchRepository


class Repository(
    SearchRepository,
    JobRepository,
    AnalysisRepository,
    ProfileRepository,
    RunRepository,
    ABC,
):
    pass
