"""Writes THIRD_PARTY_NOTICES.txt for the installer: what the .exe bundles, and its terms.

    uv run --no-sync python packaging/third_party_notices.py dist/installer/THIRD_PARTY_NOTICES.txt

The MIT, BSD and Apache licenses of the bundled libraries ask that their notices go
along with every copy, so the installer ships them next to the program. The list is
peao-bilingue's runtime dependencies, walked from its own metadata (markers evaluated
for this interpreter, so only what this build really has), plus what isn't a Python
package: the interpreter itself, Tcl/Tk and PyInstaller's bootloader. Playwright's
driver (node.js and its JavaScript packages) already carries its own notices in
_internal/playwright/driver/.

Run it with the same environment PyInstaller used (it needs `packaging`, which comes
with PyInstaller).
"""

import sys
from collections import deque
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT_PACKAGE = "peao-bilingue"
LICENSE_PREFIXES = ("license", "licence", "copying", "notice", "authors")
RULE = "=" * 78
INTRO = (
    "Peão Bilíngue bundles the following third-party software. Each part is "
    "distributed under its own license, reproduced below.\n\n"
    "Playwright's driver (node.js and the Playwright JavaScript package) carries "
    "its own notices in _internal/playwright/driver/ (LICENSE, package/NOTICE and "
    "package/ThirdPartyNotices.txt).\n\n"
)


def runtime_distributions() -> list[metadata.Distribution]:
    """peao-bilingue's dependencies, transitively, without the project itself."""
    found: dict[str, metadata.Distribution] = {}
    seen: set[tuple[str, frozenset[str]]] = set()
    queue: deque[tuple[str, frozenset[str]]] = deque([(ROOT_PACKAGE, frozenset())])
    while queue:
        name, extras = queue.popleft()
        if (canonicalize_name(name), extras) in seen:
            continue
        seen.add((canonicalize_name(name), extras))
        distribution = metadata.distribution(name)
        found[canonicalize_name(distribution.metadata["Name"])] = distribution
        for line in distribution.requires or []:
            requirement = Requirement(line)
            wanted = extras or {""}
            if requirement.marker is not None and not any(
                requirement.marker.evaluate({"extra": extra}) for extra in wanted
            ):
                continue
            queue.append((requirement.name, frozenset(requirement.extras)))
    found.pop(canonicalize_name(ROOT_PACKAGE), None)
    return sorted(found.values(), key=lambda d: canonicalize_name(d.metadata["Name"]))


def license_name(distribution: metadata.Distribution) -> str:
    meta = distribution.metadata
    if expression := meta.get("License-Expression"):
        return str(expression)
    classifiers = [
        c.split(" :: ")[-1]
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    # Some packages paste the whole text in this field: keep only a short one.
    text = str(meta.get("License") or "").strip()
    return text if text and "\n" not in text and len(text) < 80 else "see below"


def license_texts(distribution: metadata.Distribution) -> list[str]:
    texts = []
    for file in distribution.files or []:
        parts = file.parts
        in_metadata = len(parts) >= 2 and parts[0].endswith(".dist-info")
        if not in_metadata:
            continue
        name = parts[-1].lower()
        if "licenses" in parts[1:-1] or name.startswith(LICENSE_PREFIXES):
            path = Path(str(distribution.locate_file(file)))
            if path.is_file():
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
    return texts


def section(title: str, body: str) -> str:
    return f"{RULE}\n{title}\n{RULE}\n\n{body.strip()}\n\n"


def runtime_sections() -> list[str]:
    base = Path(sys.base_prefix)
    sections = []
    python_license = next(
        (base / name for name in ("LICENSE.txt", "LICENSE") if (base / name).is_file()),
        None,
    )
    sections.append(
        section(
            f"Python {sys.version.split()[0]} (the interpreter, its standard library "
            "and the libraries its Windows build bundles)",
            python_license.read_text(encoding="utf-8", errors="replace")
            if python_license
            else "PSF License Agreement: https://docs.python.org/3/license.html",
        )
    )
    for library in ("tcl", "tk"):
        terms = sorted(base.glob(f"tcl/{library}8*/license.terms"))
        if terms:
            sections.append(
                section(
                    f"{library.capitalize()} (the window toolkit)",
                    terms[0].read_text(encoding="utf-8", errors="replace"),
                )
            )
    try:
        pyinstaller = metadata.distribution("pyinstaller")
    except metadata.PackageNotFoundError:
        pass
    else:
        sections.append(
            section(
                f"PyInstaller {pyinstaller.version} (its bootloader starts the program)",
                "\n\n".join(license_texts(pyinstaller)) or license_name(pyinstaller),
            )
        )
    return sections


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    output = Path(sys.argv[1])
    distributions = runtime_distributions()
    parts = [
        INTRO,
        section(
            "Summary",
            "\n".join(
                f"{d.metadata['Name']} {d.version}: {license_name(d)}"
                for d in distributions
            ),
        ),
        *runtime_sections(),
    ]
    for distribution in distributions:
        texts = license_texts(distribution)
        parts.append(
            section(
                f"{distribution.metadata['Name']} {distribution.version} "
                f"({license_name(distribution)})",
                "\n\n".join(texts) if texts else "No license file shipped.",
            )
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(parts), encoding="utf-8-sig")
    print(f"{output}: {len(distributions)} packages.")


if __name__ == "__main__":
    main()
