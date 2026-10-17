"""Registry-based adapter factories.

Each adapter registers itself with a decorator; whoever creates one only knows the
name. The window lists what is available without importing any concrete class.
"""

import importlib
from collections.abc import Callable
from functools import cache

from peao_bilingue.domain.analysis import LLMProvider
from peao_bilingue.domain.collection import JobSource
from peao_bilingue.domain.errors import UnknownName
from peao_bilingue.domain.notifications import Notifier
from peao_bilingue.i18n import _


@cache
def load_adapters() -> None:
    """Imports the adapters package, which runs the registrations."""
    importlib.import_module("peao_bilingue.adapters")


class Registry[T]:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._classes: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._classes:
                raise ValueError(f"{self.kind} {name!r} registered twice")
            self._classes[name] = cls
            return cls

        return decorator

    def class_of(self, name: str) -> type[T]:
        load_adapters()
        try:
            return self._classes[name]
        except KeyError:
            available = ", ".join(self.available()) or _("none")
            raise UnknownName(
                _("Unknown {kind}: {name!r}. Available: {available}.").format(
                    kind=self.kind, name=name, available=available
                )
            ) from None

    def create(self, name: str, **config: object) -> T:
        return self.class_of(name)(**config)

    def available(self) -> list[str]:
        load_adapters()
        return sorted(self._classes)


# The language is picked when the app starts, so these labels are translated once.
sources: Registry[JobSource] = Registry(_("job source"))
llms: Registry[LLMProvider] = Registry(_("LLM provider"))
notifiers: Registry[Notifier] = Registry(_("notifier"))
