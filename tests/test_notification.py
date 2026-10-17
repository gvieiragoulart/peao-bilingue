from typing import Any

import pytest
from builders import job

from peao_bilingue.adapters.notification import formatting
from peao_bilingue.adapters.notification.email import Email
from peao_bilingue.adapters.notification.whatsapp import WhatsApp


def test_email_lists_new_jobs_with_link_and_skills() -> None:
    subject, body = formatting.build_email(
        [job("1", "Backend Python"), job("2", "Staff Engineer")]
    )

    assert subject == "Peão Bilíngue — 2 new job(s)"
    assert "Backend Python (vanhack)" in body and "Staff Engineer (vanhack)" in body
    assert "https://example.com/job/1" in body
    assert "Skills: Python" in body
    assert "Toronto - Canada | Hybrid | CAD $160k–200k /yr" in body
    assert "analyze" in body  # analysis is requested in the app


def test_email_shows_company_only_when_source_publishes_it() -> None:
    _subject, with_company = formatting.build_email([job(company="Acme Corp")])
    _subject, without_company = formatting.build_email([job(company=None)])
    assert "Acme Corp" in with_company
    assert "None" not in without_company


def test_digest_has_title_link_and_source() -> None:
    digest = formatting.build_digest([job("1", "High"), job("2", "Low")])

    assert digest.startswith("Peão Bilíngue — 2 new job(s)")
    assert "High — Toronto - Canada (vanhack)" in digest
    assert "https://example.com/job/2" in digest


def test_digest_respects_whatsapp_limit() -> None:
    many = [job(str(n), f"Job number {n} with a long title") for n in range(40)]
    digest = formatting.build_digest(many)

    assert len(digest) <= formatting.WHATSAPP_LIMIT
    assert "in the app" in digest  # says how many were left out


def test_digest_without_company_does_not_print_none() -> None:
    # several sources don't publish the hiring company
    assert "None" not in formatting.build_digest([job(company=None)])


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {"email": [], "whatsapp": []}

    async def email_fake(self: Email, subject: str, body: str) -> None:
        captured["email"].append(subject)

    async def whatsapp_fake(self: WhatsApp, text: str) -> None:
        captured["whatsapp"].append(text)

    monkeypatch.setattr(Email, "send", email_fake)
    monkeypatch.setattr(WhatsApp, "send", whatsapp_fake)
    return captured


async def test_email_sends_one_message_per_collection(sent: dict[str, Any]) -> None:
    await Email().notify([job("1"), job("2")])
    assert sent["email"] == ["Peão Bilíngue — 2 new job(s)"]


async def test_whatsapp_sends_a_single_digest(sent: dict[str, Any]) -> None:
    await WhatsApp().notify([job("1"), job("2")])
    assert len(sent["whatsapp"]) == 1


def test_problem_notice_lists_what_failed() -> None:
    subject, body = formatting.build_problem_email(
        ["VanHack: session expired", "Remotive: 429"]
    )
    assert "attention" in subject
    assert "- VanHack: session expired\n- Remotive: 429" in body
    assert "Runs tab" in body


def test_problem_notice_respects_whatsapp_limit() -> None:
    text = formatting.build_problem_digest(["x" * 3_000])
    assert len(text) == formatting.WHATSAPP_LIMIT
    assert text.endswith("…")


async def test_both_channels_send_problem_notice(
    sent: dict[str, Any],
) -> None:
    await Email().notify_problem(["VanHack: session expired"])
    await WhatsApp().notify_problem(["VanHack: session expired"])
    assert sent["email"] == ["Peão Bilíngue — the collection needs attention"]
    assert "VanHack: session expired" in sent["whatsapp"][0]
