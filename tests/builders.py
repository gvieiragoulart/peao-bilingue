"""Entity builders for the tests."""

from typing import Any

from peao_bilingue.domain.analysis import JobAnalysis
from peao_bilingue.domain.jobs import Job, Skill
from peao_bilingue.domain.profile import Profile


def job(
    external_id: str = "12030",
    title: str = "Fullstack Staff Engineer",
    *,
    source: str = "vanhack",
    **overrides: Any,
) -> Job:
    base = {
        "source": source,
        "external_id": external_id,
        "url": f"https://example.com/job/{external_id}",
        "title": title,
        "location": "Toronto - Canada",
        "work_mode": "Hybrid",
        "salary": "CAD $160k–200k /yr",
        "description": "Series B, a commissions platform in Python and React.",
        "required_skills": [Skill(name="Python", years="4 Year(s)")],
    }
    return Job(**{**base, **overrides})


def analysis(fit: int = 82, **overrides: Any) -> JobAnalysis:
    base = {
        "fit_score": fit,
        "summary": "Good fit in Python and React.",
        "preparation": [
            "Review React 18",
            "Practice system design",
            "Study the domain",
        ],
        "questions": [f"Question {n}" for n in range(1, 21)],
        "gaps": ["No experience with commissions"],
        "profile_improvements": [
            "Add Django to the skills",
            "Mention scale in the headline",
            "Update LinkedIn",
        ],
    }
    return JobAnalysis(**{**base, **overrides})


def profile(role: str = "Software Developer", *, source: str = "vanhack") -> Profile:
    return Profile(
        source=source,
        data={"role": role},
        text=f"Role: {role}\nMain skills: Python (5 years)",
        content_hash=f"hash-{role}",
    )
