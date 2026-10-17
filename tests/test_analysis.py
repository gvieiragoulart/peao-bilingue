from typing import Any

import pytest
from builders import analysis, job, profile
from fakes import FakeProvider
from pydantic import BaseModel, ValidationError
from queries import saved_analysis

from peao_bilingue import i18n
from peao_bilingue.adapters.persistence.sqlite import SQLiteRepository
from peao_bilingue.application import analysis as module
from peao_bilingue.domain.analysis import (
    JobAnalysis,
    LLMProvider,
    LLMResponse,
    Message,
)
from peao_bilingue.domain.errors import InvalidAnalysis, MissingProfile

PROFILE = "Role: Software Developer\nMain skills: Python (5 years)"


def json_of(obj: BaseModel) -> LLMResponse:
    return LLMResponse(text=obj.model_dump_json())


async def test_analyzes_job_successfully() -> None:
    provider = FakeProvider([json_of(analysis())])
    result = await module.analyze(job(), PROFILE, provider, notes="")

    assert result.fit_score == 82
    assert len(result.questions) == 20
    assert len(provider.calls) == 1


async def test_sends_profile_job_notes_and_schema() -> None:
    provider = FakeProvider([json_of(analysis())])
    await module.analyze(job(), PROFILE, provider, notes="I want remote jobs.")

    call = provider.calls[0]
    prompt = call["messages"][0].content
    assert "Software Developer" in prompt
    assert "Fullstack Staff Engineer" in prompt
    assert "I want remote jobs." in prompt
    assert call["schema"] is JobAnalysis


async def test_asks_for_the_answer_in_the_user_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(i18n, "LOCALE", "pt_BR")
    provider = FakeProvider([json_of(analysis())])

    await module.analyze(job(), PROFILE, provider, notes="")

    assert "in Brazilian Portuguese" in provider.calls[0]["system"]


async def test_accepts_json_wrapped_in_code_fence() -> None:
    # smaller models (Ollama) sometimes answer ```json ... ```
    provider = FakeProvider(
        [LLMResponse(text=f"```json\n{analysis().model_dump_json()}\n```")]
    )
    result = await module.analyze(job(), PROFILE, provider, notes="")
    assert result.fit_score == 82


async def test_retries_telling_model_the_error() -> None:
    provider = FakeProvider(
        [
            LLMResponse(text='{"fit_score": 999, "summary": "x"}'),
            json_of(analysis()),
        ]
    )
    result = await module.analyze(job(), PROFILE, provider, notes="")

    assert result.fit_score == 82
    assert len(provider.calls) == 2
    complaint = provider.calls[1]["messages"][-1]
    assert complaint.role == "user"
    assert "failed validation" in complaint.content


async def test_gives_up_after_attempts() -> None:
    provider = FakeProvider([LLMResponse(text="{}") for _ in range(module.ATTEMPTS)])

    with pytest.raises(InvalidAnalysis, match="after 3 attempts"):
        await module.analyze(job(), PROFILE, provider, notes="")
    assert len(provider.calls) == module.ATTEMPTS


async def test_model_refusal_becomes_clear_error() -> None:
    provider = FakeProvider([LLMResponse(text="", refused=True, reason="cyber")])

    with pytest.raises(InvalidAnalysis, match="refused"):
        await module.analyze(job(), PROFILE, provider, notes="")


async def test_empty_response_does_not_break_history() -> None:
    # the API rejects an empty assistant message; it needs a placeholder
    provider = FakeProvider([LLMResponse(text=""), json_of(analysis())])
    await module.analyze(job(), PROFILE, provider, notes="")

    assistant = provider.calls[1]["messages"][1]
    assert assistant.role == "assistant" and assistant.content


def test_schema_requires_exactly_twenty_questions() -> None:
    with pytest.raises(ValidationError):
        analysis(questions=[f"Q{n}" for n in range(19)])
    with pytest.raises(ValidationError):
        analysis(questions=[f"Q{n}" for n in range(21)])


def test_schema_bounds_fit_score() -> None:
    with pytest.raises(ValidationError):
        analysis(fit=101)
    with pytest.raises(ValidationError):
        analysis(fit=-1)


def test_schema_requires_preparation_and_improvements() -> None:
    with pytest.raises(ValidationError):
        analysis(preparation=["just one step"])
    with pytest.raises(ValidationError):
        analysis(profile_improvements=["just one improvement"])


# --- analysis requested in the window, one job at a time -----------------------------


async def analyze_job(
    repository: SQLiteRepository, provider: LLMProvider, key: str, **options: Any
) -> JobAnalysis:
    # the in-memory SQLite plays the three ports the use case asks for
    return await module.analyze_job(
        key,
        provider,
        jobs=repository,
        profiles=repository,
        analyses=repository,
        **options,
    )


def prompt_sent(provider: FakeProvider) -> str:
    message: Message = provider.calls[0]["messages"][0]
    return message.content


async def test_uses_profile_of_job_source(repository: SQLiteRepository) -> None:
    repository.save_profile(profile("Staff Engineer", source="vanhack"))
    repository.save_profile(profile("Tech Lead", source="linkedin"))
    repository.save_job(job("1", source="vanhack"), ["Python"])
    provider = FakeProvider(fit=77)

    result = await analyze_job(repository, provider, "vanhack:1")

    assert result.fit_score == 77
    assert "Staff Engineer" in prompt_sent(provider)
    assert "Tech Lead" not in prompt_sent(provider)
    saved = saved_analysis(repository, "vanhack:1")
    assert (saved.provider, saved.profile_source) == ("fake", "vanhack")


async def test_profile_from_other_source_on_request(
    repository: SQLiteRepository,
) -> None:
    repository.save_profile(profile("Tech Lead", source="linkedin"))
    # e.g. a job from a public API, a source with no profile
    repository.save_job(job("1", source="remotive"), ["Python"])
    provider = FakeProvider()

    await analyze_job(repository, provider, "remotive:1", profile_source="linkedin")

    assert "Tech Lead" in prompt_sent(provider)
    assert saved_analysis(repository, "remotive:1").profile_source == "linkedin"


async def test_without_source_profile_explains_what_to_do(
    repository: SQLiteRepository,
) -> None:
    repository.save_job(job("1", source="remotive"), ["Python"])
    provider = FakeProvider()

    with pytest.raises(MissingProfile, match="Profile tab"):
        await analyze_job(repository, provider, "remotive:1")
    assert provider.calls == []  # doesn't even spend on the LLM


async def test_missing_job_raises(repository: SQLiteRepository) -> None:
    with pytest.raises(LookupError, match="not found"):
        await analyze_job(repository, FakeProvider(), "vanhack:999")


async def test_invalid_analysis_saves_nothing(repository: SQLiteRepository) -> None:
    repository.save_profile(profile())
    repository.save_job(job("1"), ["Python"])
    provider = FakeProvider(responses=[LLMResponse(text="{}")] * 3)

    with pytest.raises(InvalidAnalysis):
        await analyze_job(repository, provider, "vanhack:1")
    assert repository.current_analysis("vanhack:1") is None


async def test_user_notes_go_into_prompt(
    repository: SQLiteRepository,
) -> None:
    # they come from outside (composition reads profile_notes.md): the application
    # layer reads no files
    repository.save_profile(profile())
    repository.save_job(job("1"), ["Python"])
    provider = FakeProvider()

    await analyze_job(repository, provider, "vanhack:1", notes="I prefer 100% remote.")

    assert "I prefer 100% remote." in prompt_sent(provider)


async def test_a_source_without_profile_uses_the_pasted_cv(
    repository: SQLiteRepository,
) -> None:
    repository.save_profile(profile("Data Engineer", source="manual"))
    repository.save_job(job("1", source="remotive"), ["Python"])
    provider = FakeProvider()

    await analyze_job(repository, provider, "remotive:1")

    assert "Data Engineer" in prompt_sent(provider)
    assert saved_analysis(repository, "remotive:1").profile_source == "manual"


async def test_the_source_profile_comes_before_the_cv(
    repository: SQLiteRepository,
) -> None:
    repository.save_profile(profile("Data Engineer", source="manual"))
    repository.save_profile(profile("Staff Engineer", source="vanhack"))
    repository.save_job(job("1", source="vanhack"), ["Python"])
    provider = FakeProvider()

    await analyze_job(repository, provider, "vanhack:1")

    assert "Staff Engineer" in prompt_sent(provider)
