"""The VanHack profile (/profile): an editable form, read without PII."""

import re
from typing import Any

from playwright.async_api import Locator, Page

from peao_bilingue.adapters.sources.vanhack import auth, selectors
from peao_bilingue.config import settings
from peao_bilingue.domain.profile import profile_hash

RENDER_TIMEOUT_MS = 20_000


async def scrape(page: Page) -> dict[str, Any]:
    """Opens /profile and returns the structured profile, already without PII."""
    await auth.goto(page, settings.vanhack_profile_url)
    await page.wait_for_selector(
        selectors.PROFILE_READY, state="attached", timeout=RENDER_TIMEOUT_MS
    )
    return await extract(page)


async def extract(page: Page) -> dict[str, Any]:
    fields = await _field_map(page)
    return {
        "role": fields.get(selectors.LABEL_ROLE),
        "it_years": fields.get(selectors.LABEL_IT_YEARS),
        "leadership": fields.get(selectors.LABEL_LEADERSHIP),
        "leadership_years": fields.get(selectors.LABEL_LEADERSHIP_YEARS),
        "open_to_remote": fields.get(selectors.LABEL_REMOTE),
        "main_skills": await _skills(page, selectors.MAIN_SKILLS_GROUP),
        "secondary_skills": await _skills(page, selectors.SECONDARY_SKILLS_GROUP),
        "languages": await _languages(page),
        "video_english_level": await _english_level(page),
        "experiences": await _experiences(page),
        "education": await _education(page),
        "links": await _links(page),
        "other_fields": fields,
    }


def to_text(data: dict[str, Any]) -> str:
    """A readable version of the profile, used in the analysis prompt."""
    lines = [
        f"Role: {data.get('role') or 'not given'}",
        f"Years as an IT professional: {data.get('it_years') or '-'}",
        (
            f"Leadership: {data.get('leadership') or '-'} "
            f"({data.get('leadership_years') or '-'})"
        ),
        f"Education: {data.get('education') or '-'}",
        f"Open to remote: {data.get('open_to_remote') or '-'}",
        f"English level assessed in the video: {data.get('video_english_level') or '-'}",
        "",
        "Main skills: " + _inline_skills(data.get("main_skills")),
        "Secondary skills: " + _inline_skills(data.get("secondary_skills")),
        "Languages: "
        + ", ".join(
            f"{item['language']} ({item.get('level') or '-'})"
            for item in data.get("languages") or []
        ),
    ]

    # Only whether the link is there: the URL carries the real name, and the model
    # can't open it anyway.
    links = data.get("links") or {}
    if links:
        lines.append(
            "Profile links: "
            + ", ".join(
                f"{name} {'filled in' if url else 'empty'}"
                for name, url in links.items()
            )
        )

    lines += ["", "Experience:"]
    for experience in data.get("experiences") or []:
        industry = f" ({experience['industry']})" if experience.get("industry") else ""
        lines.append(f"- {experience.get('company') or 'company not given'}{industry}")
        for role in experience.get("roles") or []:
            lines.append(f"  {role.get('role_and_period') or '-'}")
            if role.get("description"):
                lines.append(f"  {role['description']}")
            if role.get("skills"):
                lines.append("  Skills: " + ", ".join(role["skills"]))

    others = data.get("other_fields") or {}
    if others:
        lines += ["", "Preferences stated on VanHack:"]
        lines += [
            f"- {key}: {_value_as_text(value)}"
            for key, value in others.items()
            if value
        ]

    return "\n".join(lines)


def content_hash(data: dict[str, Any]) -> str:
    return profile_hash(data)


def _inline_skills(skills: list[dict[str, Any]] | None) -> str:
    return ", ".join(f"{s['skill']} ({s.get('years') or '-'})" for s in skills or [])


def _value_as_text(value: object) -> str:
    return ", ".join(value) if isinstance(value, list) else str(value)


def _sensitive(label: str) -> bool:
    return any(term in label.lower() for term in selectors.PII_LABELS)


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())
    return None if not text or text in selectors.EMPTY_VALUES else text


def _drop_empty_separators(text: str | None) -> str | None:
    """ "Internet - -" becomes "Internet": VanHack joins empty subfields."""
    return _clean(re.sub(r"(\s*-\s*)+$", "", text)) if text else None


def _reduce(values: list[str | None]) -> str | list[str] | None:
    """One value becomes a scalar; several become a list; none becomes None."""
    clean = [v for v in values if v]
    if not clean:
        return None
    return clean[0] if len(clean) == 1 else clean


async def _texts_of(locator: Locator) -> list[str | None]:
    return [_clean(await item.inner_text()) for item in await locator.all()]


async def _values(locator: Locator) -> list[str | None]:
    return [_clean(await item.input_value()) for item in await locator.all()]


async def _value(field: Locator) -> str | list[str] | None:
    for selector in (selectors.RADIO_CHECKED, selectors.CHECKBOX_CHECKED):
        checked = field.locator(selector)
        if await checked.count():
            return _reduce(await _texts_of(checked))
    dropdowns = field.locator(selectors.DROPDOWN)
    if await dropdowns.count():
        return _reduce(await _texts_of(dropdowns))
    entries = field.locator(selectors.AUTOCOMPLETE_INPUT)
    if await entries.count():
        return _reduce(await _values(entries))
    return None


async def _field_map(page: Page) -> dict[str, str | list[str] | None]:
    """Every question/answer pair on the page, minus the sensitive ones.

    Keeping the whole map (not only the known labels) makes the snapshot survive
    VanHack rewording its questions.
    """
    mapping: dict[str, str | list[str] | None] = {}
    for field in await page.locator(selectors.FIELD).all():
        label = field.locator(selectors.FIELD_LABEL)
        if not await label.count():
            continue
        key = _clean(await label.first.inner_text())
        if key and not _sensitive(key):
            mapping[key] = await _value(field)
    return mapping


async def _skills(page: Page, title: str) -> list[dict[str, str | None]]:
    for group in await page.locator(selectors.SKILL_GROUP).all():
        header = _clean(
            await group.locator(selectors.SKILL_GROUP_TITLE).first.inner_text()
        )
        if header != title:
            continue
        skills = []
        for row in await group.locator(selectors.SKILL_ROW).all():
            name = _clean(
                await row.locator(selectors.SKILL_SELECT)
                .locator(selectors.AUTOCOMPLETE_INPUT)
                .first.input_value()
            )
            if name:
                years = row.locator(selectors.SKILL_YEARS)
                skills.append(
                    {
                        "skill": name,
                        "years": _clean(await years.first.inner_text())
                        if await years.count()
                        else None,
                    }
                )
        return skills
    return []


async def _languages(page: Page) -> list[dict[str, str | None]]:
    languages = []
    for row in await page.locator(selectors.LANG_ROW).all():
        name = _clean(
            await row.locator(selectors.LANG_SELECT)
            .locator(selectors.AUTOCOMPLETE_INPUT)
            .first.input_value()
        )
        if name:
            languages.append(
                {
                    "language": name,
                    "level": _clean(
                        await row.locator(selectors.LANG_LEVEL).first.inner_text()
                    ),
                }
            )
    return languages


async def _experiences(page: Page) -> list[dict[str, Any]]:
    experiences = []
    for block in await page.locator(selectors.EXPERIENCE).all():
        roles = []
        for role in await block.locator(selectors.EXP_ROLE).all():
            description = role.locator(selectors.EXP_ROLE_DESC)
            roles.append(
                {
                    "role_and_period": _clean(
                        await role.locator(selectors.EXP_ROLE_HEAD).first.inner_text()
                    ),
                    "description": _clean(await description.first.inner_text())
                    if await description.count()
                    else None,
                    "skills": [
                        chip
                        for chip in await _texts_of(
                            role.locator(selectors.EXP_ROLE_CHIPS)
                        )
                        if chip
                    ],
                }
            )
        industry = _clean(
            await block.locator(selectors.EXP_INDUSTRY).first.inner_text()
        )
        experiences.append(
            {
                "company": _clean(
                    await block.locator(selectors.EXP_COMPANY).first.inner_text()
                ),
                "industry": _drop_empty_separators(industry),
                "roles": roles,
            }
        )
    return experiences


async def _english_level(page: Page) -> str | None:
    card = page.locator(selectors.INTRO_VIDEO_CARD)
    if not await card.count():
        return None
    found = re.search(selectors.INTRO_VIDEO_LEVEL, await card.first.inner_text())
    return found.group(1) if found else None


async def _education(page: Page) -> str | None:
    degree = page.locator(selectors.EDUCATION_DEGREE).locator(selectors.DROPDOWN)
    return _clean(await degree.first.inner_text()) if await degree.count() else None


async def _links(page: Page) -> dict[str, str | None]:
    links = {}
    for name, selector in selectors.LINK_INPUTS.items():
        field = page.locator(selector)
        links[name] = (
            _clean(await field.first.input_value()) if await field.count() else None
        )
    return links
