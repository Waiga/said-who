from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
README = Path("README.md")
DESIGN = Path("docs/superpowers/specs/2026-09-24-said-who-design.md")
FIXTURES = (
    Path("tests/conftest.py"),
    Path("tests/test_refusals.py"),
    Path("tests/test_forgery.py"),
)
UUID_SHAPED = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
PERMITTED_FIXTURE_UUIDS = frozenset(
    {
        "4f3a2b1c-6d7e-4f80-9a1b-2c3d4e5f6071",
        "8e7d6c5b-4a39-4f28-a1b0-c9d8e7f60514",
        "11223344-5566-4788-99aa-bbccddeeff00",
        "22334455-6677-4889-aabb-ccddeeff0011",
        "33445566-7788-499a-bbcc-ddeeff001122",
        "44556677-8899-4aab-8ccd-eeff00112233",
        "55667788-99aa-4bbc-8dde-ff0011223344",
        "66778899-aabb-4ccd-8eef-001122334455",
    }
)
COMPACT_VALUE = re.compile(r"\b\d+(?:\.\d+)?\s*[Kk]\b")
QUARTER_YEAR = re.compile(r"\bQ[1-4]\s+20\d{2}\b", re.IGNORECASE)
SEMANTIC_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")


EXPECTED_WHEEL_MEMBERS: frozenset[str] = frozenset()
EXPECTED_SDIST_MEMBERS: frozenset[str] = frozenset()


def _read(root: Path, relative: Path) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _author(root: Path) -> str:
    match = re.search(
        r'authors\s*=\s*\[\{\s*name\s*=\s*"([^"]+)"',
        _read(root, Path("pyproject.toml")),
    )
    if match is None:
        raise ValueError("project author is missing")
    return match.group(1)


def _usage_block(readme: str) -> str:
    use_heading = readme.find("## Use")
    if use_heading < 0:
        return ""
    next_heading = readme.find("\n## ", use_heading + 1)
    section = readme[use_heading : next_heading if next_heading >= 0 else len(readme)]
    opening = section.find("```")
    closing = section.find("```", opening + 3)
    return section[opening : closing + 3] if opening >= 0 and closing >= 0 else ""


def _privacy_paragraph(text: str) -> str:
    return next(
        (paragraph for paragraph in text.split("\n\n") if "left the machine" in paragraph),
        "",
    )


def _correction_paragraph(text: str) -> str:
    return next(
        (paragraph for paragraph in text.split("\n\n") if paragraph.startswith("> Correction,")),
        "",
    )


def public_surface_findings(root: Path) -> list[str]:
    findings: list[str] = []
    readme = _read(root, README)
    design = _read(root, DESIGN)
    block = _usage_block(readme)
    fixture_texts = {path: _read(root, path) for path in FIXTURES}
    fixture_text = "\n".join(fixture_texts.values())
    if "### Fictional example" not in readme:
        findings.append("README usage is not labelled Fictional example")
    if not block:
        findings.append("README usage block is missing")
    elif UUID_SHAPED.search(block):
        findings.append("README fictional example contains a UUID shaped locator")
    for path, text in ((README, readme), (DESIGN, design)):
        count = len(UUID_SHAPED.findall(text))
        if count:
            findings.append(f"{path} contains {count} UUID shaped value(s)")
    fixture_uuids = {match.casefold() for match in UUID_SHAPED.findall(fixture_text)}
    missing = PERMITTED_FIXTURE_UUIDS - fixture_uuids
    unexpected = fixture_uuids - PERMITTED_FIXTURE_UUIDS
    if missing:
        findings.append(f"public fixtures are missing {len(missing)} permitted synthetic UUID(s)")
    if unexpected:
        findings.append(f"public fixtures contain {len(unexpected)} non permitted UUID(s)")
    for path in (Path("tests/test_refusals.py"), Path("tests/test_forgery.py")):
        if UUID_SHAPED.search(fixture_texts[path]):
            findings.append(f"{path} contains a literal UUID instead of importing the invented locator")
    if _author(root).casefold() in fixture_text.casefold():
        findings.append("public fixtures contain the package author name")
    if _author(root).casefold() in design.casefold():
        findings.append("public design contains the package author name in working context")
    if "private predecessor" in design.casefold():
        findings.append("public design names a private predecessor")
    if COMPACT_VALUE.search(fixture_text):
        findings.append("public fixtures contain a compact business value")
    if QUARTER_YEAR.search(fixture_text):
        findings.append("public fixtures contain a quarter and year value")
    for name, text in ((str(README), readme), (str(DESIGN), design)):
        paragraph = _privacy_paragraph(text)
        if not paragraph or "measured corpus" not in paragraph.casefold():
            findings.append(f"{name} does not scope the privacy claim to the measured corpus")
    correction = _correction_paragraph(readme)
    if not correction:
        findings.append("README correction paragraph is missing")
    elif SEMANTIC_VERSION.search(correction):
        findings.append("README correction paragraph names an exact historical version")
    return findings


def audit_sdist(path: Path) -> list[str]:
    raise NotImplementedError("sdist audit is implemented in Task 4")


def audit_wheel(path: Path) -> list[str]:
    raise NotImplementedError("wheel audit is implemented in Task 4")


def audit_distribution_set(paths: list[Path]) -> list[str]:
    raise NotImplementedError("distribution set audit is implemented in Task 4")
