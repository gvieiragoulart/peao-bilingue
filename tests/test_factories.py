import pytest

from peao_bilingue import factories
from peao_bilingue.adapters.llm.anthropic import Anthropic
from peao_bilingue.adapters.sources.vanhack.source import VanHack
from peao_bilingue.domain.collection import JobSource
from peao_bilingue.domain.errors import UnknownName
from peao_bilingue.domain.jobs import Job, JobSummary


def test_real_adapters_are_registered() -> None:
    assert "vanhack" in factories.sources.available()
    assert "anthropic" in factories.llms.available()
    assert {"email", "whatsapp"} <= set(factories.notifiers.available())


def test_every_source_describes_itself() -> None:
    # The Sources tab's cards show it.
    for name in factories.sources.available():
        assert factories.sources.class_of(name).description, name


def test_creates_by_name_with_config() -> None:
    source = factories.sources.create("vanhack", headless=False)
    assert isinstance(source, VanHack) and source.headless is False

    provider = factories.llms.create(
        "anthropic", model="claude-haiku-4-5", api_key="test"
    )
    assert isinstance(provider, Anthropic) and provider.model == "claude-haiku-4-5"


def test_unknown_name_lists_available() -> None:
    with pytest.raises(UnknownName, match="vanhack"):
        factories.sources.create("linkedn")


def test_new_registration_is_listed_and_created() -> None:
    registry = factories.Registry[JobSource]("test source")

    @registry.register("mine")
    class Mine(JobSource):
        name = label = "mine"

        async def search(self, term: str) -> list[JobSummary]:
            return []

        async def detail(self, summary: JobSummary) -> Job:
            raise NotImplementedError

    assert "mine" in registry.available()
    assert isinstance(registry.create("mine"), Mine)


def test_duplicate_name_is_rejected() -> None:
    registry = factories.Registry[object]("test")
    registry.register("x")(type("A", (), {}))
    with pytest.raises(ValueError, match="registered twice"):
        registry.register("x")(type("B", (), {}))


def test_incomplete_port_cannot_be_instantiated() -> None:
    # this is what makes the ABC a real interface
    class WithoutDetail(JobSource):
        name = label = "incomplete"

        async def search(self, term: str) -> list[JobSummary]:
            return []

    with pytest.raises(TypeError, match="detail"):
        WithoutDetail()  # type: ignore[abstract]  # it's what the test proves
