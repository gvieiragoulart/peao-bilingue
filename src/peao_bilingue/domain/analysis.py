"""An LLM's fit analysis of a job: the result, the provider and storage."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    """The output of a job analysis.

    The limits (20 questions, fit 0-100) are validated here, on the client: no
    provider enforces `minItems`/`maxItems` on the server.
    """

    fit_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1)
    preparation: list[str] = Field(min_length=3)
    questions: list[str] = Field(min_length=20, max_length=20)
    gaps: list[str]
    profile_improvements: list[str] = Field(min_length=3)


class SavedAnalysis(BaseModel):
    analysis: JobAnalysis
    provider: str
    model: str
    created_at: datetime
    # Which source the profile came from, and whether it changed afterwards.
    profile_source: str | None = None
    profile_outdated: bool = False


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    text: str
    refused: bool = False
    reason: str | None = None


class LLMProvider(ABC):
    """Only translates the call to the SDK. Validation and retries live in the
    application layer."""

    name: ClassVar[str]
    label: ClassVar[str]
    # Settings fields that configure the adapter -> label on screen. This way the
    # window builds the form for a new provider without being changed.
    fields: ClassVar[dict[str, str]] = {}
    model: str

    @abstractmethod
    async def generate_json(
        self, system: str, messages: list[Message], schema: type[BaseModel]
    ) -> LLMResponse: ...


class AnalysisRepository(ABC):
    @abstractmethod
    def save_analysis(
        self,
        key: str,
        analysis: JobAnalysis,
        *,
        provider: str,
        model: str,
        profile_id: int | None,
    ) -> None: ...

    @abstractmethod
    def current_analysis(self, key: str) -> SavedAnalysis | None:
        """The job's latest one, with the profile used and whether it changed
        since."""
