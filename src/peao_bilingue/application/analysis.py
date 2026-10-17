"""An LLM's analysis of a job, requested by the user one job at a time.

The prompt, validation and retries live here, the same for every provider.
"""

import json
import re

from pydantic import BaseModel, ValidationError

from peao_bilingue.domain.analysis import (
    AnalysisRepository,
    JobAnalysis,
    LLMProvider,
    Message,
)
from peao_bilingue.domain.errors import InvalidAnalysis, MissingProfile
from peao_bilingue.domain.jobs import Job, JobRepository
from peao_bilingue.domain.profile import ProfileRepository
from peao_bilingue.i18n import _, response_language

ATTEMPTS = 3

SYSTEM = """You are a technical career mentor who specializes in remote international \
jobs and relocation for Brazilian software engineers.

Analyze how well the candidate's profile fits the job. Write every text field of the \
answer in {language}. Reply with the requested JSON only.

Analysis rules:
- `fit_score` from 0 to 100, honest: don't inflate it to please.
- `preparation`: at least 3 concrete study and preparation steps for this specific job.
- `questions`: exactly 20 interview questions about this job's topics, mixing technical
  and behavioral ones.
- `gaps`: job requirements that are missing from the profile or weak in it.
- `profile_improvements`: at least 3 changes to the profile, CV and LinkedIn for this
  job. Point at concrete items of the current profile (e.g. "skill X is not in the
  skills list", "the headline doesn't mention Y"). No generic advice.

If the job doesn't name the hiring company, don't make one up."""

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def system_prompt() -> str:
    return SYSTEM.format(language=response_language())


def build_prompt(job: Job, profile_text: str, notes: str = "") -> str:
    parts = ["# Candidate profile", profile_text]
    if notes.strip():
        parts += ["", "# Candidate notes (written by hand)", notes.strip()]
    parts += [
        "",
        "# Job",
        json.dumps(
            job.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=1,
        ),
        "",
        "Analyze how well the candidate fits this job.",
    ]
    return "\n".join(parts)


def _strip_fence(text: str) -> str:
    """Smaller models sometimes wrap the JSON in ```json ... ```."""
    return _CODE_FENCE.sub("", text.strip())


async def generate_validated[M: BaseModel](
    provider: LLMProvider, system: str, prompt: str, schema: type[M]
) -> M:
    """Asks the provider for JSON and validates it, sending the error back to the
    model when it fails.

    Validation lives here, not in the provider: none of them enforces limits like
    "exactly 20 questions" on the server.
    """
    messages = [Message(role="user", content=prompt)]
    error: ValidationError | None = None
    for _attempt in range(ATTEMPTS):
        response = await provider.generate_json(system, messages, schema)
        if response.refused:
            raise InvalidAnalysis(
                _("The model refused the analysis: {reason}").format(
                    reason=response.reason
                )
            )
        try:
            return schema.model_validate_json(_strip_fence(response.text))
        except ValidationError as failure:
            error = failure
            messages += [
                Message(role="assistant", content=response.text or "(empty response)"),
                Message(
                    role="user",
                    content=(
                        "The previous answer failed validation:\n"
                        f"{failure}\n\nDo it again, following the schema exactly."
                    ),
                ),
            ]
    raise InvalidAnalysis(
        _("Invalid answer after {attempts} attempts: {error}").format(
            attempts=ATTEMPTS, error=error
        )
    )


async def analyze(
    job: Job,
    profile_text: str,
    provider: LLMProvider,
    *,
    notes: str = "",
) -> JobAnalysis:
    """`notes`: what the user writes about themselves (passed in: the application
    layer reads no files and no configuration)."""
    prompt = build_prompt(job, profile_text, notes)
    return await generate_validated(provider, system_prompt(), prompt, JobAnalysis)


async def analyze_job(
    key: str,
    provider: LLMProvider,
    *,
    jobs: JobRepository,
    profiles: ProfileRepository,
    analyses: AnalysisRepository,
    profile_source: str | None = None,
    notes: str = "",
) -> JobAnalysis:
    """Analyzes a saved job and stores the analysis with the profile it used.

    The profile is the one from the job's own source; `profile_source` picks another
    source's (the way to analyze jobs from sources without a profile, like the
    public APIs).
    """
    job = jobs.get_job(key)
    if job is None:
        raise LookupError(_("Job {key} not found.").format(key=key))
    source = profile_source or job.source
    saved = profiles.last_profile(source)
    if saved is None:
        raise MissingProfile(
            _(
                "No profile has been read from {source} yet. Read it on the Profile "
                "tab, or pick another source's profile."
            ).format(source=source)
        )
    profile_id, profile = saved
    analysis = await analyze(job, profile.text, provider, notes=notes)
    analyses.save_analysis(
        key,
        analysis,
        provider=provider.name,
        model=provider.model,
        profile_id=profile_id,
    )
    return analysis
