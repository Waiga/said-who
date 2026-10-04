from __future__ import annotations

import argparse
import base64
import binascii
import email
import os
import re
import stat
import tarfile
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

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
BASE64_TOKEN = re.compile(
    r"(?<![A-Za-z0-9+/])(?:[A-Za-z0-9+/]{2,4096}={0,2})(?![A-Za-z0-9+/=])"
)
URLSAFE_BASE64_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9_-]{2,4096}={0,2})(?![A-Za-z0-9_=-])"
)
HEX_TOKEN = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{4,4096}(?![0-9A-Fa-f])")
PERCENT_TOKEN = re.compile(r"(?:%[0-9A-Fa-f]{2}){2,1365}")
MAX_ENCODED_TOKEN_LENGTH = 4096
MAX_ENCODING_DEPTH = 2
EXPECTED_VERSION = "0.1.1"
ASCII_SCAN_TRANSLATION = bytes(range(128)) + b" " * 128


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
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "PKG-INFO",
} | PACKAGE_MEMBERS
EXPECTED_WHEEL_NAME = "said_who-0.1.1-py3-none-any.whl"
EXPECTED_SDIST_NAME = "said_who-0.1.1.tar.gz"


def _read(root: Path, relative: Path) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _project_table(payload: bytes) -> dict[str, Any]:
    try:
        import tomllib as toml_reader
    except ModuleNotFoundError:  # pragma: no cover, exercised on Python 3.9 and 3.10
        import tomli as toml_reader

    document = toml_reader.loads(payload.decode("utf-8"))
    project = document.get("project")
    if not isinstance(project, dict):
        raise ValueError("[project] table is missing")
    return project


def _project_author(project: dict[str, Any]) -> str:
    authors = project.get("authors")
    if not isinstance(authors, list) or not authors or not isinstance(authors[0], dict):
        raise ValueError("project author is missing")
    author = authors[0].get("name")
    if not isinstance(author, str) or not author:
        raise ValueError("project author is missing")
    return author


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
    try:
        project = _project_table((root / "pyproject.toml").read_bytes())
        author = _project_author(project)
    except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as exc:
        findings.append(f"source pyproject is not valid project TOML: {exc}")
        project = {}
        author = ""
    if project.get("version") != EXPECTED_VERSION:
        findings.append(f"source pyproject version must be {EXPECTED_VERSION}")
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
    if author and author.casefold() in fixture_text.casefold():
        findings.append("public fixtures contain the package author name")
    if author and author.casefold() in readme.casefold():
        findings.append("README.md contains the package author name in public prose")
    if author and author.casefold() in design.casefold():
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


def _decode_reversible_base64(token: str, *, urlsafe: bool) -> bytes | None:
    if len(token) > MAX_ENCODED_TOKEN_LENGTH:
        return None
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = base64.b64decode(
            padded,
            altchars=b"-_" if urlsafe else None,
            validate=True,
        )
    except (binascii.Error, ValueError):
        return None
    encoded = (
        base64.urlsafe_b64encode(decoded) if urlsafe else base64.b64encode(decoded)
    ).decode()
    return decoded if encoded.rstrip("=") == token.rstrip("=") else None


def _decoded_tokens(text: str) -> list[bytes]:
    decoded: list[bytes] = []
    seen: set[bytes] = set()

    for pattern, urlsafe in ((BASE64_TOKEN, False), (URLSAFE_BASE64_TOKEN, True)):
        for match in pattern.finditer(text):
            payload = _decode_reversible_base64(match.group(), urlsafe=urlsafe)
            if payload is not None and payload not in seen:
                seen.add(payload)
                decoded.append(payload)

    for match in HEX_TOKEN.finditer(text):
        token = match.group()
        if len(token) % 2:
            continue
        payload = bytes.fromhex(token)
        if payload.hex() == token.casefold() and payload not in seen:
            seen.add(payload)
            decoded.append(payload)

    for match in PERCENT_TOKEN.finditer(text):
        token = match.group()
        payload = urllib.parse.unquote_to_bytes(token)
        encoded = "".join(f"%{byte:02X}" for byte in payload)
        if encoded == token.upper() and payload not in seen:
            seen.add(payload)
            decoded.append(payload)

    return decoded


def _canonical_utf8(payload: bytes) -> str | None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\x00" in text or text.startswith("\ufeff"):
        return None
    return text


def _scan_encoded_text(name: str, text: str, depth: int) -> list[str]:
    if depth >= MAX_ENCODING_DEPTH:
        return []
    findings: list[str] = []
    for payload in _decoded_tokens(text):
        findings.extend(
            _shape_findings(
                f"{name} encoded content",
                payload.translate(ASCII_SCAN_TRANSLATION).decode("ascii"),
            )
        )
        decoded = _canonical_utf8(payload)
        if decoded is None:
            continue
        findings.extend(_scan_encoded_text(name, decoded, depth + 1))
    return findings


def _scan_decodable(name: str, payload: bytes) -> list[str]:
    text = _canonical_utf8(payload)
    if text is None:
        return [f"{name} is not canonical UTF-8 text"]
    findings = _shape_findings(name, text)
    findings.extend(_scan_encoded_text(name, text, 0))
    if name.endswith(("README.md", "/METADATA", "PKG-INFO")):
        if "### Fictional example" not in text:
            findings.append(f"{name} is missing the fictional example label")
        paragraph = _privacy_paragraph(text)
        if not paragraph or "measured corpus" not in paragraph.casefold():
            findings.append(f"{name} does not scope privacy to the measured corpus")
    return list(dict.fromkeys(findings))


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
        if archive.pax_headers:
            findings.append("sdist global PAX headers must be empty")
        members = archive.getmembers()
        raw_names = [member.name for member in members]
        if len(raw_names) != len(set(raw_names)):
            findings.append("sdist contains duplicate member names")
        for member in members:
            if member.pax_headers:
                findings.append(f"sdist member PAX headers must be empty {member.name}")
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
                try:
                    project = _project_table(payload)
                except (UnicodeDecodeError, ValueError, RuntimeError) as exc:
                    findings.append(f"sdist pyproject is not valid project TOML: {exc}")
                else:
                    if project.get("version") != EXPECTED_VERSION:
                        findings.append(
                            f"sdist pyproject version must be {EXPECTED_VERSION}"
                        )
    return findings


def audit_wheel(path: Path) -> list[str]:
    findings = []
    with zipfile.ZipFile(path) as archive:
        if archive.comment:
            findings.append("wheel archive comment must be empty")
        members = archive.infolist()
        raw_names = [member.filename for member in members]
        names = set(raw_names)
        if len(raw_names) != len(names):
            findings.append("wheel contains duplicate member names")
        for member in members:
            if member.comment:
                findings.append(f"wheel member comment must be empty {member.filename}")
            if member.extra:
                findings.append(f"wheel member extra field must be empty {member.filename}")
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


class CustomBuildHook(BuildHookInterface):
    """Remove Hatchling's source archive VCS control-file force include before building."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        force_include = build_data.get("force_include")
        if not isinstance(force_include, dict):
            raise TypeError("sdist force_include build data must be a mapping")

        expected_source = os.path.abspath(os.path.join(self.root, ".gitignore"))
        for source, destination in tuple(force_include.items()):
            if destination != ".gitignore":
                continue
            if os.path.abspath(source) != expected_source:
                raise ValueError("refusing to remove a non-root .gitignore force include")
            del force_include[source]


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
