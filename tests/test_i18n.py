"""Every user-facing string has a translation, and the code itself is in English."""

import ast
import re
import string
from pathlib import Path

from peao_bilingue import i18n
from peao_bilingue.locales import pt_BR

SRC = Path(__file__).parent.parent / "src" / "peao_bilingue"
# Letters that only show up in Portuguese text: none of them belong in the code.
PORTUGUESE = re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]")


def _messages() -> dict[str, str]:
    """Every literal passed to `_()` in the source, with where it is."""
    found: dict[str, str] = {}
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
            ):
                argument = node.args[0]
                assert isinstance(argument, ast.Constant) and isinstance(
                    argument.value, str
                ), (
                    f"{path.name}:{node.lineno}: `_()` needs a literal, or the "
                    "translation can't be found"
                )
                found[argument.value] = f"{path.name}:{node.lineno}"
    return found


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_message_has_a_translation() -> None:
    missing = {
        text: where for text, where in _messages().items() if text not in pt_BR.MESSAGES
    }
    assert not missing, f"Missing in locales/pt_BR.py: {missing}"


def test_no_unused_translations() -> None:
    unused = set(pt_BR.MESSAGES) - set(_messages())
    assert not unused, f"Translated but never used: {sorted(unused)}"


def test_translations_keep_the_placeholders() -> None:
    for english, portuguese in pt_BR.MESSAGES.items():
        assert _fields(english) == _fields(portuguese), english


def test_unknown_text_falls_back_to_english() -> None:
    assert i18n._("Not in any catalog") == "Not in any catalog"


def test_source_has_no_portuguese_outside_the_locales() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for path in SRC.rglob("*.py")
        if "locales" not in path.parts
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        # The product name is the same in every language.
        if PORTUGUESE.search(line.replace("Peão Bilíngue", ""))
    ]
    assert not offenders, f"Portuguese text outside locales/: {offenders}"
