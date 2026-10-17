"""Personal data that must stay out of the profile and the prompt.

What a pattern can find reliably is removed: emails, phone numbers, links (they often
carry the person's name, like a LinkedIn URL) and CPF numbers. A name or an address
can't be found that way, so whoever pastes the text is asked to check.
"""

import re
from collections import Counter

from pydantic import BaseModel

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
# At least 9 digits with the usual separators: "(11) 98765-4321", "+55 11 98765 4321",
# "+1 (555) 123-4567". Year ranges like "2019-2023" have too few digits to match.
PHONE = re.compile(
    r"(?<![\w-])(?:\+\d{1,3}[\s.-]?)?\(?\d{2,3}\)?[\s.-]?\d{3,5}[\s.-]?\d{4}(?![\w-])"
)
CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")

PATTERNS = {"email": EMAIL, "link": URL, "cpf": CPF, "phone": PHONE}


class Removed(BaseModel):
    """How many of each kind were taken out of a text."""

    email: int = 0
    link: int = 0
    phone: int = 0
    cpf: int = 0

    def any(self) -> bool:
        return bool(self.email or self.link or self.phone or self.cpf)


def remove_contact_data(text: str) -> tuple[str, Removed]:
    """The text without emails, links, CPF and phone numbers, and what was removed.
    The order matters: an email or a link may contain digits that look like a phone."""
    counts: Counter[str] = Counter()
    for kind, pattern in PATTERNS.items():
        text, found = pattern.subn("", text)
        counts[kind] += found
    lines = (" ".join(line.split()) for line in text.splitlines())
    # A line left with only separators ("me@mail.com | (11) 9...-..." becomes "|") goes.
    kept = (line for line in lines if not line or any(c.isalnum() for c in line))
    return "\n".join(kept).strip(), Removed(**counts)
