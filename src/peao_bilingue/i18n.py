"""User-facing text: written in English in the code, shown in the user's language.

Every string the user reads (windows, CLI output, notices, error messages) goes through
`_()`. The English text is the lookup key; `locales/<locale>.py` maps it to the
translation, and a missing entry falls back to English. Placeholders use `str.format`
names, so translators can reorder them:

    _("Run {id}: {status}").format(id=run.id, status=run.status)

Logs are for whoever maintains the app and stay in English, untranslated.
`tests/test_i18n.py` checks that every `_()` string has a translation.
"""

from peao_bilingue.locales import pt_BR

# The app ships in Brazilian Portuguese; English is the fallback.
LOCALE = "pt_BR"

CATALOGS: dict[str, dict[str, str]] = {"pt_BR": pt_BR.MESSAGES}

# How to ask an LLM to answer in the user's language.
RESPONSE_LANGUAGE = {"pt_BR": "Brazilian Portuguese", "en": "English"}


def _(message: str) -> str:
    return CATALOGS.get(LOCALE, {}).get(message, message)


def response_language() -> str:
    return RESPONSE_LANGUAGE.get(LOCALE, "English")
