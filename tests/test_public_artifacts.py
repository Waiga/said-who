from __future__ import annotations

import io
import stat
import tarfile
import warnings
import zipfile
from pathlib import Path

from scripts.audit_public_artifacts import (
    EXPECTED_SDIST_MEMBERS,
    EXPECTED_WHEEL_MEMBERS,
    audit_distribution_set,
    audit_sdist,
    audit_wheel,
    main,
    public_surface_findings,
)

ROOT = Path(__file__).resolve().parent.parent

PERMITTED_UUIDS = (
    "4f3a2b1c-6d7e-4f80-9a1b-2c3d4e5f6071",
    "8e7d6c5b-4a39-4f28-a1b0-c9d8e7f60514",
    "11223344-5566-4788-99aa-bbccddeeff00",
    "22334455-6677-4889-aabb-ccddeeff0011",
    "33445566-7788-499a-bbcc-ddeeff001122",
    "44556677-8899-4aab-8ccd-eeff00112233",
    "55667788-99aa-4bbc-8dde-ff0011223344",
    "66778899-aabb-4ccd-8eef-001122334455",
)
OTHER_UUID = "abcdef01-2345-4789-8abc-def012345678"


def _readme() -> str:
    return """# Sample package

> Correction, fictional record.

This information never left the machine in the measured corpus.

### Fictional example

## Use

```
sample --fictional
```
"""


def _design() -> str:
    return """# Sample design

This information never left the machine in the measured corpus.
"""


def _write_project(
    root: Path,
    *,
    readme: str | None = None,
    design: str | None = None,
    conftest: str | None = None,
    refusals: str = "from conftest import INVENTED_LOCATOR\n",
    forgery: str = "from conftest import INVENTED_LOCATOR\n",
) -> None:
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nauthors = [{ name = "Sample Author" }]\n', encoding="utf-8"
    )
    (root / "README.md").write_text(readme or _readme(), encoding="utf-8")
    (root / "docs/superpowers/specs/2026-09-24-said-who-design.md").write_text(
        design or _design(), encoding="utf-8"
    )
    (root / "tests/conftest.py").write_text(
        conftest or "\n".join(PERMITTED_UUIDS), encoding="utf-8"
    )
    (root / "tests/test_refusals.py").write_text(refusals, encoding="utf-8")
    (root / "tests/test_forgery.py").write_text(forgery, encoding="utf-8")


def test_synthetic_exact_permitted_fixture_uuids_are_accepted(tmp_path: Path):
    _write_project(tmp_path)

    assert public_surface_findings(tmp_path) == []


def test_synthetic_fixture_uuid_counts_are_reported(tmp_path: Path):
    _write_project(tmp_path, conftest="\n".join((*PERMITTED_UUIDS[1:], OTHER_UUID)))

    assert public_surface_findings(tmp_path) == [
        "public fixtures are missing 1 permitted synthetic UUID(s)",
        "public fixtures contain 1 non permitted UUID(s)",
    ]


def test_synthetic_readme_and_design_uuid_counts_are_reported(tmp_path: Path):
    _write_project(
        tmp_path,
        readme=f"{_readme()}\n## Notes\n\n{OTHER_UUID}\n",
        design=f"{_design()}\n{OTHER_UUID}\n",
    )

    assert public_surface_findings(tmp_path) == [
        "README.md contains 1 UUID shaped value(s)",
        "docs/superpowers/specs/2026-09-24-said-who-design.md contains 1 UUID shaped value(s)",
    ]


def test_synthetic_readme_usage_context_is_required(tmp_path: Path):
    _write_project(
        tmp_path,
        readme=_readme()
        .replace("### Fictional example\n\n", "")
        .replace("sample --fictional", f"sample --fictional {OTHER_UUID}"),
    )

    assert public_surface_findings(tmp_path) == [
        "README usage is not labelled Fictional example",
        "README fictional example contains a UUID shaped locator",
        "README.md contains 1 UUID shaped value(s)",
    ]


def test_synthetic_literal_fixture_locators_are_reported(tmp_path: Path):
    _write_project(tmp_path, refusals=OTHER_UUID, forgery=OTHER_UUID)

    assert public_surface_findings(tmp_path) == [
        "public fixtures contain 1 non permitted UUID(s)",
        "tests/test_refusals.py contains a literal UUID instead of importing the invented locator",
        "tests/test_forgery.py contains a literal UUID instead of importing the invented locator",
    ]


def test_synthetic_fixture_and_design_context_are_reported(tmp_path: Path):
    _write_project(
        tmp_path,
        conftest="\n".join(PERMITTED_UUIDS) + "\nSample Author\n27K\nQ2 2040\n",
        design=f"{_design()}\nSample Author\nprivate predecessor\n",
    )

    assert public_surface_findings(tmp_path) == [
        "public fixtures contain the package author name",
        "public design contains the package author name in working context",
        "public design names a private predecessor",
        "public fixtures contain a compact business value",
        "public fixtures contain a quarter and year value",
    ]


def test_synthetic_readme_author_name_is_reported(tmp_path: Path):
    _write_project(tmp_path, readme=f"{_readme()}\nSample Author\n")

    assert public_surface_findings(tmp_path) == [
        "README.md contains the package author name in public prose"
    ]


def test_synthetic_privacy_scope_is_required(tmp_path: Path):
    _write_project(
        tmp_path,
        readme=_readme().replace("measured corpus", "example dataset"),
        design=_design().replace("measured corpus", "example dataset"),
    )

    assert public_surface_findings(tmp_path) == [
        "README.md does not scope the privacy claim to the measured corpus",
        (
            "docs/superpowers/specs/2026-09-24-said-who-design.md does not scope the privacy "
            "claim to the measured corpus"
        ),
    ]


def test_synthetic_correction_paragraph_is_required(tmp_path: Path):
    _write_project(tmp_path, readme=_readme().replace("> Correction, fictional record.\n\n", ""))

    assert public_surface_findings(tmp_path) == ["README correction paragraph is missing"]


def test_synthetic_correction_cannot_name_an_exact_historical_version(tmp_path: Path):
    _write_project(tmp_path, readme=_readme().replace("fictional record", "fictional 0.0.1 record"))

    assert public_surface_findings(tmp_path) == [
        "README correction paragraph names an exact historical version"
    ]


def test_current_public_surfaces_contain_only_fictional_scoped_context():
    assert public_surface_findings(ROOT) == []


def _write_sdist(path: Path, members: dict[str, str]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            payload = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def test_distribution_set_requires_one_exact_wheel_and_one_exact_sdist(tmp_path):
    good = [
        tmp_path / "said_who-0.1.1-py3-none-any.whl",
        tmp_path / "said_who-0.1.1.tar.gz",
    ]
    assert audit_distribution_set(good) == []
    assert audit_distribution_set(good + [tmp_path / "extra.whl"])
    assert audit_distribution_set(good + [good[0]])


def _safe_member_text(name: str) -> str:
    if name.endswith("/METADATA"):
        return (
            "Metadata-Version: 2.3\nName: said-who\nVersion: 0.1.1\n\n"
            "### Fictional example\n"
            "The measured corpus left the machine only as aggregate counts.\n"
        )
    if name.endswith(("README.md", "PKG-INFO")):
        return (
            "### Fictional example\n"
            "The measured corpus left the machine only as aggregate counts.\n"
            "Version: 0.1.1\n"
        )
    return "synthetic text\n"


def test_wheel_rejects_every_unexpected_member(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = _safe_member_text(name)
            archive.writestr(name, content)
        archive.writestr("tests/should_not_ship.py", "synthetic content\n")
    assert any("unexpected wheel member" in item for item in audit_wheel(path))


def test_sdist_rejects_every_unexpected_member(tmp_path):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    _write_sdist(
        path,
        {
            "said_who-0.1.1/README.md": (
                "### Fictional example\n"
                "The measured corpus left the machine only as aggregate counts.\n"
            ),
            "said_who-0.1.1/LICENSE": "MIT\n",
            "said_who-0.1.1/pyproject.toml": "version = \"0.1.1\"\n",
            "said_who-0.1.1/PKG-INFO": "Version: 0.1.1\n",
            "said_who-0.1.1/said_who/__init__.py": "VALUE = 1\n",
            "said_who-0.1.1/tests/should_not_ship.py": "synthetic content\n",
        },
    )
    assert any("unexpected sdist member" in item for item in audit_sdist(path))


def test_wheel_scans_every_decodable_member(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = _safe_member_text(name)
            if name == "said_who/store.py":
                content = "synthetic locator 12345678-1234-4123-8123-123456789abc\n"
            archive.writestr(name, content)
    assert any(
        "said_who/store.py contains a UUID shaped locator" in item
        for item in audit_wheel(path)
    )


def test_sdist_scans_every_decodable_member(tmp_path):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    members = {
        f"said_who-0.1.1/{name}": _safe_member_text(name) for name in EXPECTED_SDIST_MEMBERS
    }
    members["said_who-0.1.1/said_who/store.py"] = (
        "synthetic locator 12345678-1234-4123-8123-123456789abc\n"
    )
    _write_sdist(path, members)
    assert any(
        "said_who/store.py contains a UUID shaped locator" in item
        for item in audit_sdist(path)
    )


def test_project_declares_patch_release_and_sdist_allowlist():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.1.1"' in project
    assert "[tool.hatch.build.targets.sdist]" in project
    for path in ('"said_who"', '"README.md"', '"LICENSE"', '"pyproject.toml"'):
        assert path in project


def test_wheel_rejects_an_allowed_name_with_a_non_file_mode(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            if name == "said_who/store.py":
                member = zipfile.ZipInfo(name)
                member.create_system = 3
                member.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(member, "said_who/cli.py")
            else:
                archive.writestr(name, _safe_member_text(name))

    assert "unexpected wheel non file member said_who/store.py" in audit_wheel(path)


def test_sdist_rejects_wrong_embedded_versions(tmp_path):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    members = {
        f"said_who-0.1.1/{name}": _safe_member_text(name) for name in EXPECTED_SDIST_MEMBERS
    }
    members["said_who-0.1.1/PKG-INFO"] = (
        "Metadata-Version: 2.3\nVersion: 0.1.0\n\n### Fictional example\n"
        "The measured corpus left the machine only as aggregate counts.\n"
    )
    members["said_who-0.1.1/pyproject.toml"] = 'version = "0.1.0"\n'
    _write_sdist(path, members)

    findings = audit_sdist(path)
    assert "sdist metadata version must be 0.1.1" in findings
    assert "sdist pyproject version must be 0.1.1" in findings


def test_sdist_allowlist_includes_hatch_forced_gitignore():
    assert ".gitignore" in EXPECTED_SDIST_MEMBERS


def test_cli_reports_missing_expected_artifacts(tmp_path, monkeypatch, capsys):
    wheel = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    sdist = tmp_path / "said_who-0.1.1.tar.gz"
    monkeypatch.setattr(
        "sys.argv",
        ["audit_public_artifacts.py", "--root", str(ROOT), "--dist", str(wheel), str(sdist)],
    )

    assert main() == 1
    output = capsys.readouterr().out
    assert f"distribution artifact is not a file {wheel}" in output
    assert f"distribution artifact is not a file {sdist}" in output


def test_wheel_rejects_unsafe_duplicates_and_scans_each_physical_member(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "said_who/store.py",
                "synthetic locator 12345678-1234-4123-8123-123456789abc\n",
            )
            for name in EXPECTED_WHEEL_MEMBERS:
                archive.writestr(name, _safe_member_text(name))
            archive.writestr("C:/escape.py", "synthetic text\n")

    findings = audit_wheel(path)
    assert "wheel contains duplicate member names" in findings
    assert "said_who/store.py contains a UUID shaped locator" in findings
    assert "unsafe wheel member path C:/escape.py" in findings


def test_sdist_rejects_unsafe_duplicates_non_files_and_scans_each_member(tmp_path):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    root = "said_who-0.1.1"
    with tarfile.open(path, "w:gz") as archive:
        duplicate_payload = b"synthetic locator 12345678-1234-4123-8123-123456789abc\n"
        duplicate = tarfile.TarInfo(f"{root}/said_who/store.py")
        duplicate.size = len(duplicate_payload)
        archive.addfile(duplicate, io.BytesIO(duplicate_payload))
        for name in EXPECTED_SDIST_MEMBERS:
            payload = _safe_member_text(name).encode()
            member = tarfile.TarInfo(f"{root}/{name}")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        unsafe_payload = b"synthetic text\n"
        unsafe = tarfile.TarInfo(f"{root}/../escape.py")
        unsafe.size = len(unsafe_payload)
        archive.addfile(unsafe, io.BytesIO(unsafe_payload))
        link = tarfile.TarInfo(f"{root}/said_who/link.py")
        link.type = tarfile.SYMTYPE
        link.linkname = "store.py"
        archive.addfile(link)

    findings = audit_sdist(path)
    assert "sdist contains duplicate member names" in findings
    assert "said_who/store.py contains a UUID shaped locator" in findings
    assert f"unsafe sdist member path {root}/../escape.py" in findings
    assert f"unexpected sdist non file member {root}/said_who/link.py" in findings
