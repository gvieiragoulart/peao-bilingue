"""Errors the domain knows about. Their messages are shown to the user."""


class SessionExpired(RuntimeError):
    """The source needs a login and the saved session no longer works. Login is
    always manual."""


class LoginFailed(RuntimeError):
    """The manual login didn't finish (timed out, or the session wasn't confirmed)."""


class HumanChallenge(RuntimeError):
    """A captcha or human check on the page. The app never tries to solve it."""


class CollectionError(RuntimeError):
    """Reading a source failed; `artifact` points to the saved screenshot + HTML."""

    def __init__(self, message: str, artifact: str | None = None) -> None:
        super().__init__(message)
        self.artifact = artifact


class RunInProgress(RuntimeError):
    """A run is already in progress; only one at a time."""


class SchedulingError(RuntimeError):
    """The operating system refused to create, read or remove the scheduled task."""


class ProviderUnavailable(RuntimeError):
    """The LLM provider is down or misconfigured; the message says what to do."""


class InvalidAnalysis(RuntimeError):
    """The LLM provider didn't produce a valid analysis within the attempts."""


class MissingProfile(LookupError):
    """No profile was read from the requested source, and the analysis needs one."""


class UnknownName(LookupError):
    """No adapter is registered under that name."""
