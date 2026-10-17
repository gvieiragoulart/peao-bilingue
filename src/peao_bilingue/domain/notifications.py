"""Notices from the scheduled collection: new jobs, and what needs attention."""

from abc import ABC, abstractmethod
from typing import ClassVar

from peao_bilingue.domain.jobs import Job


class Notifier(ABC):
    name: ClassVar[str]
    label: ClassVar[str]
    fields: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def notify(self, jobs: list[Job]) -> None:
        """Reports a collection's new jobs. Analysis happens in the app."""

    @abstractmethod
    async def notify_problem(self, problems: list[str]) -> None:
        """Reports that the collection needs attention: an expired session, a
        failing source."""
