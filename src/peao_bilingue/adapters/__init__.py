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
from peao_bilingue.adapters.sources import (
    company_boards as _company_boards,  # noqa: F401
)
from peao_bilingue.adapters.sources import getonbrd as _getonbrd  # noqa: F401
from peao_bilingue.adapters.sources import github as _github  # noqa: F401
from peao_bilingue.adapters.sources import hackernews as _hackernews  # noqa: F401
from peao_bilingue.adapters.sources import himalayas as _himalayas  # noqa: F401
from peao_bilingue.adapters.sources import jobicy as _jobicy  # noqa: F401
from peao_bilingue.adapters.sources import remoteok as _remoteok  # noqa: F401
from peao_bilingue.adapters.sources import remotive as _remotive  # noqa: F401
from peao_bilingue.adapters.sources import strider as _strider  # noqa: F401
from peao_bilingue.adapters.sources import (
    weworkremotely as _weworkremotely,  # noqa: F401
)
from peao_bilingue.adapters.sources.vanhack import source as _vanhack  # noqa: F401
