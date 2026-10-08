"""Importar este pacote registra todos os adapters nas fábricas."""

from peao_bilingue.adaptadores.fontes import remotive as _remotive  # noqa: F401
from peao_bilingue.adaptadores.fontes.vanhack import fonte as _vanhack  # noqa: F401
from peao_bilingue.adaptadores.llm import anthropic as _anthropic  # noqa: F401
from peao_bilingue.adaptadores.llm import gemini as _gemini  # noqa: F401
from peao_bilingue.adaptadores.llm import ollama as _ollama  # noqa: F401
from peao_bilingue.adaptadores.llm import openai as _openai  # noqa: F401
from peao_bilingue.adaptadores.notificacao import email as _email  # noqa: F401
from peao_bilingue.adaptadores.notificacao import whatsapp as _whatsapp  # noqa: F401
