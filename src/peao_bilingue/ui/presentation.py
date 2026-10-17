"""Turns entities into text and table rows. No Tk: testable directly."""

from peao_bilingue.domain.analysis import JobAnalysis, SavedAnalysis
from peao_bilingue.domain.collection import Run, RunStatus, Trigger
from peao_bilingue.domain.jobs import Job, JobStatus, ListedJob, Posting
from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _

TABLE_ERROR_SIZE = 80


def all_label() -> str:
    return _("All")


def job_status_labels() -> dict[JobStatus, str]:
    return {
        JobStatus.new: _("New"),
        JobStatus.studying: _("Studying"),
        JobStatus.applied: _("Applied"),
        JobStatus.discarded: _("Discarded"),
    }


def run_status_labels() -> dict[RunStatus, str]:
    return {
        RunStatus.running: _("running"),
        RunStatus.ok: _("ok"),
        RunStatus.error: _("error"),
        RunStatus.login_required: _("login required"),
    }


def trigger_labels() -> dict[Trigger, str]:
    return {Trigger.manual: _("manual"), Trigger.scheduled: _("scheduled")}


def status_options() -> list[str]:
    """The status filter: "All" first, then each status by its label."""
    return [all_label(), *job_status_labels().values()]


def status_from_label(label: str) -> JobStatus | None:
    for status, shown in job_status_labels().items():
        if shown == label:
            return status
    return None


def job_row(item: ListedJob) -> tuple[str, ...]:
    return (
        "" if item.fit_score is None else str(item.fit_score),
        item.job.title,
        item.job.location or "",
        item.job.source,
        job_status_labels()[item.status],
    )


def _also_on(postings: list[Posting]) -> list[str]:
    return [
        _("Also on {source}: {url}").format(source=posting.source, url=posting.url)
        for posting in postings
    ]


def analysis_text(
    job: Job, analysis: JobAnalysis, also_on: list[Posting] | None = None
) -> str:
    details = " | ".join(
        part
        for part in (
            job.company,
            job.location,
            job.work_mode,
            job.salary,
            job.extras.get("required_location"),
        )
        if part
    )
    return "\n".join(
        [
            job.title,
            details,
            job.url,
            *_also_on(also_on or []),
            "",
            _("Fit: {score}/100").format(score=analysis.fit_score),
            "",
            _("SUMMARY"),
            analysis.summary,
            "",
            _("PREPARATION"),
            *(f"- {step}" for step in analysis.preparation),
            "",
            _("INTERVIEW QUESTIONS ({count})").format(count=len(analysis.questions)),
            *(f"{n}. {question}" for n, question in enumerate(analysis.questions, 1)),
            "",
            _("GAPS"),
            *(f"- {gap}" for gap in analysis.gaps or [_("(none found)")]),
            "",
            _("WHAT TO IMPROVE IN THE PROFILE"),
            *(f"- {improvement}" for improvement in analysis.profile_improvements),
        ]
    )


def job_detail(item: ListedJob, analysis: SavedAnalysis | None) -> str:
    if analysis is None:
        return "\n".join(
            [
                item.job.title,
                item.job.url,
                *_also_on(item.also_on),
                "",
                _(
                    "Not analyzed yet: pick the LLM and the profile, then click Analyze."
                ),
                "",
                _("DESCRIPTION"),
                item.job.description or _("(no description)"),
            ]
        )

    footer = _("Analysis by {provider} ({model}) on {when}").format(
        provider=analysis.provider,
        model=analysis.model,
        when=f"{analysis.created_at:%d/%m/%Y %H:%M}",
    )
    if analysis.profile_source:
        footer += _(", with the {source} profile").format(
            source=analysis.profile_source
        )
    footer += "."
    if analysis.profile_outdated:
        footer += "\n" + _(
            "The {source} profile changed after this analysis: analyze again to update "
            "it."
        ).format(source=analysis.profile_source)
    text = analysis_text(item.job, analysis.analysis, item.also_on)
    return f"{text}\n\n{footer}"


def search_row(search: Search) -> tuple[str, ...]:
    return (
        search.name,
        ", ".join(search.keywords),
        ", ".join(search.exclude),
        ", ".join(search.sources) or _("all"),
        _("yes") if search.active else _("no"),
    )


def run_row(run: Run) -> tuple[str, ...]:
    error = run.error or ""
    if len(error) > TABLE_ERROR_SIZE:
        error = error[: TABLE_ERROR_SIZE - 1] + "…"
    return (
        f"{run.started_at:%d/%m %H:%M}",
        trigger_labels()[run.trigger],
        run_status_labels()[run.status],
        str(run.listed_jobs),
        str(run.new_jobs),
        error,
    )


def terms(text: str) -> list[str]:
    """ "python, django ,," -> ["python", "django"]."""
    return [term.strip() for term in text.split(",") if term.strip()]


def parse_min_score(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError:
        raise ValueError(_("The minimum fit must be a number from 0 to 100.")) from None
    if not 0 <= value <= 100:
        raise ValueError(_("The minimum fit must be a number from 0 to 100."))
    return value
