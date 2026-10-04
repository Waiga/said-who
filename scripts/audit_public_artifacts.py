from __future__ import annotations

import argparse
import email
import re
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

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


PACKAGE_MEMBERS = {
    "said_who/__init__.py",
    "said_who/cli.py",
    "said_who/doctor.py",
    "said_who/entries.py",
    "said_who/gate.py",
    "said_who/refusals.py",
    "said_who/store.py",
    "said_who/harness/__init__.py",
    "said_who/harness/claude_code.py",
}
DIST_INFO = "said_who-0.1.1.dist-info"
EXPECTED_WHEEL_MEMBERS = PACKAGE_MEMBERS | {
    f"{DIST_INFO}/METADATA",
    f"{DIST_INFO}/WHEEL",
    f"{DIST_INFO}/entry_points.txt",
    f"{DIST_INFO}/licenses/LICENSE",
    f"{DIST_INFO}/RECORD",
}
EXPECTED_SDIST_MEMBERS = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "PKG-INFO",
} | PACKAGE_MEMBERS
EXPECTED_WHEEL_NAME = "said_who-0.1.1-py3-none-any.whl"
EXPECTED_SDIST_NAME = "said_who-0.1.1.tar.gz"


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
            findings.append(
                f"{path} contains a literal UUID instead of importing the invented locator"
            )
    if _author(root).casefold() in fixture_text.casefold():
        findings.append("public fixtures contain the package author name")
    if _author(root).casefold() in readme.casefold():
        findings.append("README.md contains the package author name in public prose")
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


def _shape_findings(name: str, text: str) -> list[str]:
    findings = []
    if UUID_SHAPED.search(text):
        findings.append(f"{name} contains a UUID shaped locator")
    if COMPACT_VALUE.search(text):
        findings.append(f"{name} contains a compact business value")
    if QUARTER_YEAR.search(text):
        findings.append(f"{name} contains a quarter and year value")
    return findings


def _scan_decodable(name: str, payload: bytes) -> list[str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return []
    findings = _shape_findings(name, text)
    if name.endswith(("README.md", "/METADATA", "PKG-INFO")):
        if "### Fictional example" not in text:
            findings.append(f"{name} is missing the fictional example label")
        paragraph = _privacy_paragraph(text)
        if not paragraph or "measured corpus" not in paragraph.casefold():
            findings.append(f"{name} does not scope privacy to the measured corpus")
    return findings


def _archive_path_is_safe(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\x00" not in name
        and "\\" not in name
        and re.match(r"^[A-Za-z]:", name) is None
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in name.split("/"))
    )


def _wheel_member_is_file(member: zipfile.ZipInfo) -> bool:
    if member.is_dir():
        return False
    if member.create_system != 3:
        return True
    file_type = stat.S_IFMT(member.external_attr >> 16)
    return file_type in {0, stat.S_IFREG}


def audit_sdist(path: Path) -> list[str]:
    findings = []
    root = "said_who-0.1.1"
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        raw_names = [member.name for member in members]
        if len(raw_names) != len(set(raw_names)):
            findings.append("sdist contains duplicate member names")
        for member in members:
            if not _archive_path_is_safe(member.name):
                findings.append(f"unsafe sdist member path {member.name}")
            if not member.isfile():
                findings.append(f"unexpected sdist non file member {member.name}")
        files = [member for member in members if member.isfile()]
        relative = [
            (member.name[len(root) + 1 :], member)
            for member in files
            if member.name.startswith(root + "/")
        ]
        if len(relative) != len(files):
            findings.append("sdist contains a file outside the expected root")
        relative_names = {name for name, _member in relative}
        for name in sorted(relative_names - EXPECTED_SDIST_MEMBERS):
            findings.append(f"unexpected sdist member {name}")
        for name in sorted(EXPECTED_SDIST_MEMBERS - relative_names):
            findings.append(f"missing sdist member {name}")
        for member in files:
            name = (
                member.name[len(root) + 1 :]
                if member.name.startswith(root + "/")
                else member.name
            )
            extracted = archive.extractfile(member)
            assert extracted is not None
            payload = extracted.read()
            findings.extend(_scan_decodable(name, payload))
            if name == "PKG-INFO":
                metadata = email.message_from_bytes(payload)
                if metadata.get("Version") != "0.1.1":
                    findings.append("sdist metadata version must be 0.1.1")
            elif name == "pyproject.toml":
                project = payload.decode("utf-8", errors="replace")
                match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', project, re.MULTILINE)
                if match is None or match.group(1) != "0.1.1":
                    findings.append("sdist pyproject version must be 0.1.1")
    return findings


def audit_wheel(path: Path) -> list[str]:
    findings = []
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        raw_names = [member.filename for member in members]
        names = set(raw_names)
        if len(raw_names) != len(names):
            findings.append("wheel contains duplicate member names")
        for member in members:
            if not _archive_path_is_safe(member.filename):
                findings.append(f"unsafe wheel member path {member.filename}")
            if not _wheel_member_is_file(member):
                findings.append(f"unexpected wheel non file member {member.filename}")
        for name in sorted(names - EXPECTED_WHEEL_MEMBERS):
            findings.append(f"unexpected wheel member {name}")
        for name in sorted(EXPECTED_WHEEL_MEMBERS - names):
            findings.append(f"missing wheel member {name}")
        for member in members:
            payload = archive.read(member)
            findings.extend(_scan_decodable(member.filename, payload))
            if member.filename == f"{DIST_INFO}/METADATA":
                metadata = email.message_from_bytes(payload)
                if metadata.get("Version") != "0.1.1":
                    findings.append("wheel metadata version must be 0.1.1")
    return findings


def audit_distribution_set(paths: list[Path]) -> list[str]:
    names = [path.name for path in paths]
    findings = []
    if names.count(EXPECTED_WHEEL_NAME) != 1:
        findings.append(f"expected exactly one {EXPECTED_WHEEL_NAME}")
    if names.count(EXPECTED_SDIST_NAME) != 1:
        findings.append(f"expected exactly one {EXPECTED_SDIST_NAME}")
    if len(names) != 2:
        findings.append("distribution set must contain exactly two files")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    findings = public_surface_findings(args.root)
    findings.extend(audit_distribution_set(args.dist))
    for artifact in args.dist:
        if not artifact.is_file():
            findings.append(f"distribution artifact is not a file {artifact}")
            continue
        try:
            if artifact.name == EXPECTED_WHEEL_NAME:
                findings.extend(audit_wheel(artifact))
            elif artifact.name == EXPECTED_SDIST_NAME:
                findings.extend(audit_sdist(artifact))
        except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
            findings.append(f"cannot audit distribution artifact {artifact}: {exc}")
    if findings:
        for finding in findings:
            print(f"FAIL: {finding}")
        return 1
    print("public artifact audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
