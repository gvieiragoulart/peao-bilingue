"""Importing this package registers every adapter in the factories."""

from peao_bilingue.adapters.llm import anthropic as _anthropic  # noqa: F401
from peao_bilingue.adapters.llm import gemini as _gemini  # noqa: F401
from peao_bilingue.adapters.llm import ollama as _ollama  # noqa: F401
from peao_bilingue.adapters.llm import openai as _openai  # noqa: F401
from peao_bilingue.adapters.notification import email as _email  # noqa: F401
from peao_bilingue.adapters.notification import whatsapp as _whatsapp  # noqa: F401
from peao_bilingue.adapters.notification import (
    windows_toast as _windows_toast,  # noqa: F401
)
from peao_bilingue.adapters.sources import arbeitnow as _arbeitnow  # noqa: F401
from peao_bilingue.adapters.sources import himalayas as _himalayas  # noqa: F401
from peao_bilingue.adapters.sources import remoteok as _remoteok  # noqa: F401
from peao_bilingue.adapters.sources import remotive as _remotive  # noqa: F401
from peao_bilingue.adapters.sources import (
    weworkremotely as _weworkremotely,  # noqa: F401
)
from peao_bilingue.adapters.sources.vanhack import source as _vanhack  # noqa: F401
