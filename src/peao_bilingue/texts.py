"""User-facing text shared by the CLI and the window (no Tk).

The CLI imports nothing from `ui/`: the two are independent entry points.
"""

from peao_bilingue.domain.schedule import ScheduleStatus
from peao_bilingue.i18n import _


def describe_schedule(status: ScheduleStatus | None) -> str:
    if status is None:
        return _("No collection scheduled.")
    parts = [
        _("Every day at {time} (task: {state}).").format(
            time=status.time, state=status.state
        )
    ]
    if status.next_run:
        parts.append(_("Next: {when}.").format(when=f"{status.next_run:%d/%m %H:%M}"))
    if status.last_run:
        result = (
            _("ok")
            if status.last_result == 0
            else _("code {code}").format(code=status.last_result)
        )
        parts.append(
            _("Last: {when} ({result}).").format(
                when=f"{status.last_run:%d/%m %H:%M}", result=result
            )
        )
    return " ".join(parts)
