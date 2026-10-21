"""Unopened UI sections should not add widgets or refresh work at startup."""

from typing import Any, cast

from peao_bilingue.ui.app import Panels


def test_panels_build_and_refresh_only_when_first_accessed() -> None:
    created: list[str] = []

    class First:
        def __init__(self, _host: object, _app: object) -> None:
            created.append("first")
            self.refreshes = 0

        def refresh(self) -> None:
            self.refreshes += 1

    class Second(First):
        def __init__(self, host: object, app: object) -> None:
            super().__init__(host, app)
            created[-1] = "second"

    panels = Panels(
        cast(Any, object()),
        cast(Any, object()),
        [("first", "First", First), ("second", "Second", Second)],
    )

    assert list(panels) == ["first", "second"]
    assert panels.loaded() == []
    assert created == []

    first = panels["first"]
    assert panels["first"] is first
    assert first.refreshes == 1
    assert panels.loaded() == [first]
    assert created == ["first"]

    second = panels["second"]
    assert second.refreshes == 1
    assert panels.loaded() == [first, second]
    assert created == ["first", "second"]
