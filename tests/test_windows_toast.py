"""Windows notifications: the toast's XML and the PowerShell that shows it, with no
real toast (the PowerShell runner is a fake)."""

from xml.etree import ElementTree as ET

from builders import job

from peao_bilingue.adapters.notification.windows_toast import (
    APP_ID,
    WindowsToast,
    jobs_toast,
    problems_toast,
    toast_xml,
)


class Recorder:
    """Keeps the scripts instead of running PowerShell."""

    def __init__(self) -> None:
        self.scripts: list[str] = []

    def __call__(self, code: str) -> str:
        self.scripts.append(code)
        return ""


def texts(xml: str) -> list[str]:
    return [node.text or "" for node in ET.fromstring(xml).iter("text")]


def test_text_is_escaped_into_valid_xml() -> None:
    xml = toast_xml("R&D <jobs>", ['Say "hi" & bye'], launch="https://a.com/?x=1&y=2")
    root = ET.fromstring(xml)  # it parses: nothing broke the XML
    assert texts(xml) == ["R&D <jobs>", 'Say "hi" & bye']
    assert root.get("launch") == "https://a.com/?x=1&y=2"
    assert root.get("activationType") == "protocol"


def test_a_single_job_opens_when_clicked() -> None:
    xml = jobs_toast([job("1", "Backend Python")])
    assert texts(xml) == ["Peão Bilíngue — 1 new job(s)", "Backend Python (vanhack)"]
    assert ET.fromstring(xml).get("launch") == "https://example.com/job/1"


def test_many_jobs_list_a_few_and_count_the_rest() -> None:
    xml = jobs_toast([job(str(n), f"Job {n}") for n in range(5)])
    assert texts(xml) == [
        "Peão Bilíngue — 5 new job(s)",
        "Job 0 (vanhack)",
        "Job 1 (vanhack)",
        "+3 job(s) in the app",
    ]
    assert ET.fromstring(xml).get("launch") is None


def test_problem_toast_lists_what_failed() -> None:
    xml = problems_toast(["VanHack: session expired"])
    assert texts(xml) == [
        "Peão Bilíngue — the collection needs attention",
        "VanHack: session expired",
    ]


async def test_registers_the_app_and_shows_the_toast() -> None:
    powershell = Recorder()
    notifier = WindowsToast(runner=powershell)

    await notifier.notify([job("1", "Engineer's job")])

    [code] = powershell.scripts
    assert f"AppUserModelId\\{APP_ID}" in code  # the identity Windows needs
    assert "-Name DisplayName -Value 'Peão Bilíngue'" in code
    assert f"CreateToastNotifier('{APP_ID}')" in code
    # inside PowerShell single quotes, ' becomes ''
    assert "Engineer''s job" in code
    assert code.rstrip().endswith("exit 0")


async def test_problem_notice_goes_through_the_same_path() -> None:
    powershell = Recorder()
    notifier = WindowsToast(runner=powershell)

    await notifier.notify_problem(["Remotive: 429"])

    assert "Remotive: 429" in powershell.scripts[0]
