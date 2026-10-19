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
from peao_bilingue.domain.schedule import ScheduleStatus
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


def short_source_label(name: str) -> str:
    """The display name without what follows it: "Remotive (public API, remote
    jobs)" -> "Remotive", "Hacker News: Who is hiring? (...)" -> "Hacker News"."""
    return source_label(name).split(" (")[0].split(":")[0]


def short_llm_label(name: str) -> str:
    """The LLM's name without what follows it: "Ollama (local, free)" -> "Ollama"."""
    try:
        label = factories.llms.class_of(name).label
    except UnknownName:
        return name
    return label.split(" (")[0]


def source_features(cls: type[JobSource]) -> list[str]:
    """What a source needs and does, as short tags: the guide's hint."""
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


def job_meta(item: ListedJob, now: datetime) -> str:
    """The line under the job's title: where it is, where it came from, when."""
    parts = [
        item.job.company,
        item.job.location,
        short_source_label(item.job.source),
        _("found {when}").format(when=ago(item.seen_at, now)),
    ]
    return " · ".join(part for part in parts if part)


def job_row(item: ListedJob, now: datetime | None = None) -> tuple[str, ...]:
    """(fit, title, the line under it, published, status)."""
    now = now or _now()
    return (
        "" if item.fit_score is None else str(item.fit_score),
        item.job.title,
        job_meta(item, now),
        published_label(item, now),
        job_status_labels()[item.status],
    )


# The fit's color by range: good, worth a look, weak.
FIT_COLORS: tuple[tuple[int, tuple[str, str]], ...] = (
    (75, ("#2e7d32", "#3fae6a")),
    (50, ("#b26a00", "#e0a43a")),
    (0, ("#c62828", "#e05a6a")),
)


def fit_color(score: int) -> tuple[str, str]:
    return next(color for floor, color in FIT_COLORS if score >= floor)


def blend(color: str, ground: str, amount: float) -> str:
    """`amount` of `color` over `ground`: what an alpha would show, which Tk lacks."""
    mixed = (
        round(
            int(color[i : i + 2], 16) * amount
            + int(ground[i : i + 2], 16) * (1 - amount)
        )
        for i in (1, 3, 5)
    )
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def soft(
    color: tuple[str, str], ground: tuple[str, str]
) -> tuple[tuple[str, str], tuple[str, str]]:
    """A chip's soft look from its base color: a tinted background over `ground` and
    the text in a deeper (light mode) or lighter (dark mode) shade of the same color.
    Returns (background, text), each a (light, dark) pair."""
    light, dark = color
    background = (blend(light, ground[0], 0.16), blend(dark, ground[1], 0.3))
    text = (blend(light, "#000000", 0.78), blend(dark, "#ffffff", 0.55))
    return background, text


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


def _also_on(postings: list[Posting]) -> list[str]:
    return [
        _("Also on {source}: {url}").format(source=posting.source, url=posting.url)
        for posting in postings
    ]


def _details(job: Job) -> str:
    return " · ".join(
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


@dataclass(frozen=True)
class AnalysisSection:
    """One part of the analysis, behind its own button on the job's panel."""

    key: str
    title: str
    text: str


@dataclass(frozen=True)
class JobPanel:
    """What the job's panel shows, already as text."""

    status: str
    facts: str  # the line beside the status: source and when it was found
    details: str  # company | place | work mode | salary
    notes: list[str]  # the dates explained, and the other sites with the job
    fit: int | None
    fit_label: str
    summary: str
    sections: list[AnalysisSection]
    # Who analyzed it and when; without an analysis, how to get one.
    footer: str
    outdated: str  # empty unless the profile changed after the analysis


def fit_label(score: int) -> str:
    if score >= FIT_COLORS[0][0]:
        return _("Good fit")
    if score >= FIT_COLORS[1][0]:
        return _("Worth a look")
    return _("Weak fit")


def analysis_sections(analysis: JobAnalysis) -> list[AnalysisSection]:
    gaps = analysis.gaps or [_("(none found)")]
    return [
        AnalysisSection(
            "preparation",
            _("Preparation"),
            "\n".join(f"• {step}" for step in analysis.preparation),
        ),
        AnalysisSection(
            "questions",
            _("Questions ({count})").format(count=len(analysis.questions)),
            "\n\n".join(
                f"{n}. {question}" for n, question in enumerate(analysis.questions, 1)
            ),
        ),
        AnalysisSection(
            "gaps",
            _("Gaps ({count})").format(count=len(analysis.gaps)),
            "\n".join(f"• {gap}" for gap in gaps),
        ),
        AnalysisSection(
            "profile",
            _("Improve the profile"),
            "\n".join(f"• {item}" for item in analysis.profile_improvements),
        ),
    ]


def _analysis_footer(analysis: SavedAnalysis) -> str:
    footer = _("Analysis by {provider} ({model}) on {when}").format(
        provider=analysis.provider,
        model=analysis.model,
        when=f"{analysis.created_at:%d/%m/%Y %H:%M}",
    )
    if analysis.profile_source:
        footer += _(", with the {source} profile").format(
            source=analysis.profile_source
        )
    return footer + "."


def job_panel(
    item: ListedJob, analysis: SavedAnalysis | None, now: datetime | None = None
) -> JobPanel:
    now = now or _now()
    facts = " · ".join(
        [
            short_source_label(item.job.source),
            _("found {when}").format(when=ago(item.seen_at, now)),
        ]
    )
    status = job_status_labels()[item.status]
    details = _details(item.job)
    notes = [*_dates(item, now), *_also_on(item.also_on)]
    if analysis is None:
        # No description: the panel shows the keywords found, and the job reads
        # better on its own site.
        return JobPanel(
            status,
            facts,
            details,
            notes,
            fit=None,
            fit_label="",
            summary="",
            sections=[],
            footer=_(
                "Not analyzed yet: pick the LLM and the profile, then click Analyze."
            ),
            outdated="",
        )
    outdated = ""
    if analysis.profile_outdated:
        outdated = _(
            "The {source} profile changed after this analysis: analyze again to update "
            "it."
        ).format(source=analysis.profile_source)
    result = analysis.analysis
    return JobPanel(
        status,
        facts,
        details,
        notes,
        fit=result.fit_score,
        fit_label=fit_label(result.fit_score),
        summary=result.summary,
        sections=analysis_sections(result),
        footer=_analysis_footer(analysis),
        outdated=outdated,
    )


def schedule_line(status: ScheduleStatus | None) -> str:
    """The sidebar's short version of the schedule."""
    if status is None:
        return _("No daily collection")
    return _("Daily collection at {time}").format(time=status.time)


def last_run_line(run: Run | None, now: datetime | None = None) -> str:
    if run is None:
        return _("No collection yet")
    zone = ZoneInfo(settings.timezone)
    when = (
        f"{ago(run.started_at, now or _now())}, {run.started_at.astimezone(zone):%H:%M}"
    )
    if run.status is RunStatus.running:
        return _("Collecting since {when}").format(when=when)
    if run.status is not RunStatus.ok:
        return _("Last: {when} · {status}").format(
            when=when, status=run_status_labels()[run.status]
        )
    return _("Last: {when} · {count} new").format(when=when, count=run.new_jobs)


def badge(count: int) -> str:
    """A count in a small badge: empty for none, capped so it stays small."""
    if count <= 0:
        return ""
    return str(count) if count < 100 else "99+"


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
