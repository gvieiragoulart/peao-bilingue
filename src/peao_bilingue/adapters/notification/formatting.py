"""The text of the notices: new jobs and collection problems. The analysis isn't in
the notice: it is requested in the app."""

from peao_bilingue.domain.jobs import Job
from peao_bilingue.i18n import _

WHATSAPP_LIMIT = 1_500


def _where(job: Job, *extra_parts: str | None) -> str:
    # Names the company only when the source publishes it: several (like VanHack) don't.
    parts = (job.company, job.location, *extra_parts)
    return " | ".join(part for part in parts if part)


def _new_jobs_title(count: int) -> str:
    return _("Peão Bilíngue — {count} new job(s)").format(count=count)


def build_email(jobs: list[Job]) -> tuple[str, str]:
    """Subject and body of an email with all of a collection's new jobs."""
    blocks = []
    for job in jobs:
        lines = [f"{job.title} ({job.source})"]
        details = _where(
            job, job.work_mode, job.salary, job.extras.get("required_location")
        )
        if details:
            lines.append(details)
        if job.required_skills:
            skills = ", ".join(skill.name for skill in job.required_skills)
            lines.append(f"Skills: {skills}")
        lines.append(job.url)
        blocks.append("\n".join(lines))
    blocks.append(_("Open the app to analyze the ones you're interested in."))
    return _new_jobs_title(len(jobs)), "\n\n".join(blocks)


def build_digest(jobs: list[Job]) -> str:
    """A short digest for WhatsApp, cut at the message limit."""
    text = _new_jobs_title(len(jobs))
    for index, job in enumerate(jobs):
        where = _where(job).replace(" | ", " — ")
        where = f" — {where}" if where else ""
        block = f"\n\n{job.title}{where} ({job.source})\n{job.url}"
        suffix = "\n\n" + _("+{count} job(s) in the app").format(
            count=len(jobs) - index
        )
        if len(text) + len(block) + len(suffix) > WHATSAPP_LIMIT:
            return text + suffix
        text += block
    return text


def _bullets(problems: list[str]) -> str:
    return "\n".join(f"- {problem}" for problem in problems)


def _problem_title() -> str:
    return _("Peão Bilíngue — the collection needs attention")


def build_problem_email(problems: list[str]) -> tuple[str, str]:
    """Subject and body of the notice that the scheduled collection needs attention."""
    body = (
        _("The scheduled collection couldn't read everything:")
        + f"\n\n{_bullets(problems)}\n\n"
        + _("The details are on the app's Runs tab.")
    )
    return _problem_title(), body


def build_problem_digest(problems: list[str]) -> str:
    """The same notice, short, for WhatsApp."""
    text = f"{_problem_title()}\n\n{_bullets(problems)}"
    if len(text) <= WHATSAPP_LIMIT:
        return text
    return text[: WHATSAPP_LIMIT - 1] + "…"
