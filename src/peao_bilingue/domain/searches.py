"""Searches: the terms the user looks for, and in which sources."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, field_validator

from peao_bilingue.i18n import _


class Search(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    exclude: list[str] = []
    sources: list[str] = []  # empty = every enabled source
    active: bool = True

    @field_validator("keywords", "exclude")
    @classmethod
    def drop_empty_terms(cls, terms: list[str]) -> list[str]:
        clean = [term.strip() for term in terms if term.strip()]
        if not clean and terms:
            raise ValueError(_("Terms can't be just spaces."))
        return clean


class SearchRepository(ABC):
    @abstractmethod
    def list_searches(self, *, only_active: bool = False) -> list[Search]: ...

    @abstractmethod
    def save_search(self, search: Search) -> Search: ...

    @abstractmethod
    def remove_search(self, search_id: int) -> None: ...
