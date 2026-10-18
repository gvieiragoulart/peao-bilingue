"""Turns entities into text and table rows. No Tk: testable directly."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from peao_bilingue import factories
from peao_bilingue.application.filters import matched_keywords
from peao_bilingue.config import settings
from peao_bilingue.domain.analysis import JobAnalysis, SavedAnalysis
from peao_bilingue.domain.collection import (
    JobSource,
    ManualSession,
    Run,
    RunStatus,
    Trigger,
)
from peao_bilingue.domain.errors import UnknownName
from peao_bilingue.domain.jobs import NEW_AT_SOURCE, Job, JobStatus, ListedJob, Posting
from peao_bilingue.domain.privacy import Removed
from peao_bilingue.domain.profile import ProfileSource
from peao_bilingue.domain.searches import Search
from peao_bilingue.i18n import _

TABLE_ERROR_SIZE = 80
NEW_MARK = "●"

# One color per search, (light theme, dark theme), all dark enough for white text.
SEARCH_COLORS: tuple[tuple[str, str], ...] = (
    ("#1f6aa5", "#1f6aa5"),
    ("#2e7d32", "#388e3c"),
    ("#7b1fa2", "#8e24aa"),
    ("#c62828", "#d32f2f"),
    ("#00796b", "#00897b"),
    ("#d84315", "#e64a19"),
    ("#3949ab", "#3f51b5"),
    ("#ad1457", "#c2185b"),
)


def _now() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))


def ago(when: datetime, now: datetime) -> str:
    """How long ago, by calendar day in the user's timezone: "today", "3 d ago"..."""
    zone = ZoneInfo(settings.timezone)
    days = (now.astimezone(zone).date() - when.astimezone(zone).date()).days
    if days <= 0:
        return _("today")
    if days == 1:
        return _("yesterday")
    if days < 30:
        return _("{days} d ago").format(days=days)
    if days < 365:
        months = days // 30
        if months == 1:
            return _("1 month ago")
        return _("{months} months ago").format(months=months)
    years = days // 365
    if years == 1:
        return _("1 year ago")
    return _("{years} years ago").format(years=years)


def published_label(item: ListedJob, now: datetime) -> str:
    """The age at the source, marked when the job was new there when we found it."""
    published = item.published
    if published is None:
        return "?"
    age = ago(published, now)
    return f"{NEW_MARK} {age}" if item.new_at_source else age


def _dates(item: ListedJob, now: datetime) -> list[str]:
    found = ago(item.seen_at, now)
    published = item.published
    if published is None:
        lines = [
            _("Found {found} · the source doesn't give the publication date.").format(
                found=found
            )
        ]
    else:
        lines = [
            _("Found {found} · published at the source {published}.").format(
                found=found, published=ago(published, now)
            )
        ]
    if item.new_at_source:
        lines.append(
            _(
                "{mark} New at the source: published at most {days} days before we "
                "found it."
            ).format(mark=NEW_MARK, days=NEW_AT_SOURCE.days)
        )
    return lines


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


def source_label(name: str) -> str:
    """The source's display name; the bare name if its adapter no longer exists (an
    old run, a stale setting)."""
    try:
        return factories.sources.class_of(name).label
    except UnknownName:
        return name


def source_features(cls: type[JobSource]) -> list[str]:
    """What a source needs and does, as short tags: the Sources tab's chips and the
    guide's hint."""
    features = []
    if issubclass(cls, ManualSession):
        features.append(_("needs your login"))
    else:
        features.append(_("no account needed"))
    if cls.needs_browser:
        features.append(_("browser"))
    if issubclass(cls, ProfileSource):
        features.append(_("reads your profile"))
    return features


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


def job_row(item: ListedJob, now: datetime | None = None) -> tuple[str, ...]:
    now = now or _now()
    return (
        "" if item.fit_score is None else str(item.fit_score),
        item.job.title,
        ago(item.seen_at, now),
        published_label(item, now),
        item.job.location or "",
        item.job.source,
        job_status_labels()[item.status],
    )


@dataclass(frozen=True)
class KeywordGroup:
    """The keywords of one search that show up in a job."""

    search: str
    keywords: list[str]


def job_keywords(item: ListedJob, searches: list[Search]) -> list[KeywordGroup]:
    """For each search the job was found by, the keywords that show up in it. A
    search deleted since, or one whose keywords no longer show up, is left out."""
    by_name = {search.name: search for search in searches}
    groups = []
    for name in item.searches:
        search = by_name.get(name)
        if search is None:
            continue
        found = matched_keywords(item.job, search)
        if found:
            groups.append(KeywordGroup(name, found))
    return groups


def search_colors(names: list[str]) -> dict[str, tuple[str, str]]:
    """A color per search, by its position: the same search keeps its color."""
    return {
        name: SEARCH_COLORS[index % len(SEARCH_COLORS)]
        for index, name in enumerate(names)
    }


def job_count(count: int) -> str:
    return _(
        "{count} job(s). Click one to see it or analyze it; tick the boxes to discard "
        "several at once."
    ).format(count=count)


def _also_on(postings: list[Posting]) -> list[str]:
    return [
        _("Also on {source}: {url}").format(source=posting.source, url=posting.url)
        for posting in postings
    ]


def _details(job: Job) -> str:
    return " | ".join(
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


def analysis_text(
    job: Job,
    analysis: JobAnalysis,
    also_on: list[Posting] | None = None,
    dates: list[str] | None = None,
) -> str:
    # No title: the job's dialog shows it as its header.
    return "\n".join(
        [
            _details(job),
            job.url,
            *_also_on(also_on or []),
            *(dates or []),
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


def job_detail(
    item: ListedJob, analysis: SavedAnalysis | None, now: datetime | None = None
) -> str:
    dates = _dates(item, now or _now())
    if analysis is None:
        # No description: the dialog shows the keywords found, and the job reads
        # better on its own site.
        return "\n".join(
            [
                _details(item.job),
                item.job.url,
                *_also_on(item.also_on),
                *dates,
                "",
                _(
                    "Not analyzed yet: pick the LLM and the profile, then click Analyze."
                ),
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
    text = analysis_text(item.job, analysis.analysis, item.also_on, dates)
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
        ", ".join(source_label(name) for name in run.sources),
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


def removed_summary(removed: Removed) -> str:
    """ "1 email, 2 phone numbers": what the cleanup took out of a text."""
    parts = []
    if removed.email:
        parts.append(_("{count} email(s)").format(count=removed.email))
    if removed.phone:
        parts.append(_("{count} phone number(s)").format(count=removed.phone))
    if removed.link:
        parts.append(_("{count} link(s)").format(count=removed.link))
    if removed.cpf:
        parts.append(_("{count} CPF number(s)").format(count=removed.cpf))
    return ", ".join(parts)


def saved_without_contact_data(removed: Removed) -> str:
    """The notice after saving a pasted profile or notes."""
    check = _("Also check that your name, address and documents aren't in it.")
    if not removed.any():
        return _("Saved.") + " " + check
    return (
        _("Saved. Removed from the text: {items}.").format(
            items=removed_summary(removed)
        )
        + " "
        + check
    )
