from __future__ import annotations

import base64
import builtins
import io
import stat
import sys
import tarfile
import types
import warnings
import zipfile
from pathlib import Path

import pytest
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin.utils import load_plugin_from_script

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover, exercised on Python 3.9 and 3.10
    import tomli as tomllib

from scripts.audit_public_artifacts import (
    EXPECTED_SDIST_MEMBERS,
    EXPECTED_WHEEL_MEMBERS,
    MAX_DECODED_BYTE_LENGTH,
    MAX_ENCODING_CANDIDATES,
    MAX_TOTAL_DECODED_BYTES,
    CustomBuildHook,
    _project_table,
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
        '[project]\nversion = "0.1.1"\nauthors = [{ name = "Sample Author" }]\n',
        encoding="utf-8",
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


def _write_sdist(
    path: Path,
    members: dict[str, str | bytes],
    *,
    global_pax_headers: dict[str, str] | None = None,
    member_pax_headers: dict[str, str] | None = None,
    member_metadata: dict[str, str] | None = None,
) -> None:
    with tarfile.open(
        path,
        "w:gz",
        format=tarfile.PAX_FORMAT,
        pax_headers=global_pax_headers,
    ) as archive:
        for name, content in members.items():
            payload = content.encode() if isinstance(content, str) else content
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            if member_pax_headers and name.endswith("said_who/store.py"):
                info.pax_headers = member_pax_headers
            if member_metadata and name.endswith("said_who/store.py"):
                for field, value in member_metadata.items():
                    setattr(info, field, value)
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
    members["said_who-0.1.1/pyproject.toml"] = '[project]\nversion = "0.1.0"\n'
    _write_sdist(path, members)

    findings = audit_sdist(path)
    assert "sdist metadata version must be 0.1.1" in findings
    assert "sdist pyproject version must be 0.1.1" in findings


def test_sdist_allowlist_excludes_hatch_forced_gitignore():
    assert ".gitignore" not in EXPECTED_SDIST_MEMBERS


def test_sdist_declares_a_target_scoped_native_build_hook():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.hatch.build.targets.sdist.hooks.custom]" in project
    assert 'path = "scripts/audit_public_artifacts.py"' in project


def test_auditor_loads_through_hatch_custom_hook_loader():
    hook = load_plugin_from_script(
        str(ROOT / "scripts/audit_public_artifacts.py"),
        "said_who_build_hook",
        BuildHookInterface,
        "build_hook",
    )

    assert hook.__name__ == "CustomBuildHook"


def test_sdist_build_hook_removes_only_the_exact_root_gitignore(tmp_path):
    hook = CustomBuildHook(str(tmp_path), {}, None, None, str(tmp_path), "sdist")
    root_gitignore = str(tmp_path / ".gitignore")
    other_source = str(tmp_path / "README.md")
    build_data = {
        "force_include": {
            root_gitignore: ".gitignore",
            other_source: "README.md",
        }
    }

    hook.initialize("standard", build_data)

    assert build_data["force_include"] == {other_source: "README.md"}

    with pytest.raises(ValueError, match="non-root"):
        hook.initialize(
            "standard",
            {"force_include": {"/unexpected/.gitignore": ".gitignore"}},
        )


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_wheel_rejects_noncanonical_utf8_text_members(tmp_path, encoding):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            payload = _safe_member_text(name).encode()
            if name == "said_who/store.py":
                payload = f"synthetic locator {OTHER_UUID}\n".encode(encoding)
            archive.writestr(name, payload)

    assert "said_who/store.py is not canonical UTF-8 text" in audit_wheel(path)


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_sdist_rejects_noncanonical_utf8_text_members(tmp_path, encoding):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    members = {
        f"said_who-0.1.1/{name}": _safe_member_text(name) for name in EXPECTED_SDIST_MEMBERS
    }
    members["said_who-0.1.1/said_who/store.py"] = (
        f"synthetic locator {OTHER_UUID}\n".encode(encoding)
    )
    _write_sdist(path, members)

    assert "said_who/store.py is not canonical UTF-8 text" in audit_sdist(path)


@pytest.mark.parametrize(
    ("encoded", "expected"),
    [
        (
            base64.b64encode(OTHER_UUID.encode()).decode(),
            "said_who/store.py encoded content contains a UUID shaped locator",
        ),
        (
            base64.urlsafe_b64encode(("\u083f" + OTHER_UUID).encode()).decode(),
            "said_who/store.py encoded content contains a UUID shaped locator",
        ),
        (
            base64.b64encode(b"1K").decode(),
            "said_who/store.py encoded content contains a compact business value",
        ),
        (
            b"1K".hex(),
            "said_who/store.py encoded content contains a compact business value",
        ),
        (
            "".join(f"%{byte:02X}" for byte in b"1K"),
            "said_who/store.py encoded content contains a compact business value",
        ),
        (
            "".join(f"%{byte:02X}" for byte in b"synthetic Q2 2040"),
            "said_who/store.py encoded content contains a quarter and year value",
        ),
    ],
)
def test_wheel_scans_bounded_reversible_text_encodings(tmp_path, encoded, expected):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert expected in audit_wheel(path)


def test_wheel_scans_ascii_shapes_inside_binary_encoded_payloads(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    encoded = base64.b64encode(b"\xff" + OTHER_UUID.encode()).decode()
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py encoded content contains a UUID shaped locator"
        in audit_wheel(path)
    )


def test_wheel_rejects_reversible_encoding_at_the_recursion_limit(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    encoded = OTHER_UUID.encode()
    for _ in range(3):
        encoded = base64.b64encode(encoded)
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py encoded content exceeds maximum encoding depth 2"
        in audit_wheel(path)
    )


def test_wheel_scans_mixed_literal_and_percent_encoded_text(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    encoded = OTHER_UUID.replace("abcdef", "%61%62%63%64%65%66")
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py encoded content contains a UUID shaped locator"
        in audit_wheel(path)
    )


def test_wheel_rejects_overlong_canonical_base64_candidate(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    encoded = base64.b64encode(("x" * 4096 + OTHER_UUID).encode()).decode()
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py encoded candidate exceeds maximum length 4096"
        in audit_wheel(path)
    )


def test_wheel_rejects_an_overlong_decoded_candidate(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    encoded = "x" * (MAX_DECODED_BYTE_LENGTH + 1) + "%31"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py decoded candidate exceeds maximum byte length 3072"
        in audit_wheel(path)
    )


def test_wheel_rejects_too_many_encoded_candidates(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    encoded = " ".join(
        base64.b64encode(f"item-{index}".encode()).decode()
        for index in range(MAX_ENCODING_CANDIDATES + 1)
    )
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py exceeds maximum encoded candidate count 4096"
        in audit_wheel(path)
    )


def test_wheel_rejects_a_cumulative_decoded_byte_overrun(tmp_path):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    payload_size = MAX_DECODED_BYTE_LENGTH
    padding = b"x" * payload_size
    encoded = " ".join(
        base64.b64encode(f"{index:04d}".encode() + padding[4:]).decode()
        for index in range(MAX_TOTAL_DECODED_BYTES // payload_size + 1)
    )
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            content = encoded if name == "said_who/store.py" else _safe_member_text(name)
            archive.writestr(name, content)

    assert (
        "said_who/store.py exceeds cumulative decoded byte budget 65536"
        in audit_wheel(path)
    )


@pytest.mark.parametrize(
    ("metadata_channel", "expected"),
    [
        ("archive_comment", "wheel archive comment must be empty"),
        ("member_comment", "wheel member comment must be empty said_who/store.py"),
        ("member_extra", "wheel member extra field must be empty said_who/store.py"),
    ],
)
def test_wheel_rejects_unscanned_metadata_channels(tmp_path, metadata_channel, expected):
    path = tmp_path / "said_who-0.1.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in EXPECTED_WHEEL_MEMBERS:
            member = zipfile.ZipInfo(name)
            if name == "said_who/store.py" and metadata_channel == "member_comment":
                member.comment = b"synthetic hidden comment"
            if name == "said_who/store.py" and metadata_channel == "member_extra":
                member.extra = b"\xfe\xca\x01\x00X"
            archive.writestr(member, _safe_member_text(name))
        if metadata_channel == "archive_comment":
            archive.comment = b"synthetic hidden comment"

    assert expected in audit_wheel(path)


@pytest.mark.parametrize(
    ("global_pax_headers", "member_pax_headers", "expected"),
    [
        ({"synthetic": "hidden"}, None, "sdist global PAX headers must be empty"),
        (
            None,
            {"synthetic": "hidden"},
            "sdist member PAX headers must be empty said_who-0.1.1/said_who/store.py",
        ),
    ],
)
def test_sdist_rejects_unscanned_pax_headers(
    tmp_path, global_pax_headers, member_pax_headers, expected
):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    members = {
        f"said_who-0.1.1/{name}": _safe_member_text(name) for name in EXPECTED_SDIST_MEMBERS
    }
    _write_sdist(
        path,
        members,
        global_pax_headers=global_pax_headers,
        member_pax_headers=member_pax_headers,
    )

    assert expected in audit_sdist(path)


@pytest.mark.parametrize("field", ["uname", "gname", "linkname"])
def test_sdist_rejects_non_native_regular_member_metadata(tmp_path, field):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    members = {
        f"said_who-0.1.1/{name}": _safe_member_text(name) for name in EXPECTED_SDIST_MEMBERS
    }
    _write_sdist(path, members, member_metadata={field: f"synthetic-{field}"})

    assert (
        f"sdist member {field} must be empty said_who-0.1.1/said_who/store.py"
        in audit_sdist(path)
    )


def test_source_project_version_uses_the_project_table(tmp_path):
    _write_project(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.decoy]\nversion = "0.1.1"\n\n'
        '[project]\nversion = "0.1.0"\nauthors = [{ name = "Sample Author" }]\n',
        encoding="utf-8",
    )

    assert "source pyproject version must be 0.1.1" in public_surface_findings(tmp_path)


def test_dev_dependencies_cover_auditor_imports_and_old_python_toml():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = project["project"]["optional-dependencies"]["dev"]

    assert any(dependency.startswith("hatchling") for dependency in dev)
    assert any(
        dependency.startswith("tomli>=2") and "python_version < '3.11'" in dependency
        for dependency in dev
    )


def test_project_table_uses_tomli_when_tomllib_is_unavailable(monkeypatch):
    fake_tomli = types.ModuleType("tomli")
    fake_tomli.loads = tomllib.loads
    monkeypatch.setitem(sys.modules, "tomli", fake_tomli)
    real_import = builtins.__import__

    def import_without_tomllib(name, *args, **kwargs):
        if name == "tomllib":
            raise ModuleNotFoundError("No module named 'tomllib'", name="tomllib")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_tomllib)

    assert _project_table(b'[project]\nversion = "0.1.1"\n')["version"] == "0.1.1"


def test_sdist_project_version_uses_the_project_table(tmp_path):
    path = tmp_path / "said_who-0.1.1.tar.gz"
    members = {
        f"said_who-0.1.1/{name}": _safe_member_text(name) for name in EXPECTED_SDIST_MEMBERS
    }
    members["said_who-0.1.1/pyproject.toml"] = (
        '[tool.decoy]\nversion = "0.1.1"\n\n[project]\nversion = "0.1.0"\n'
    )
    _write_sdist(path, members)

    assert "sdist pyproject version must be 0.1.1" in audit_sdist(path)


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


def test_ci_builds_checks_and_audits_distributions():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "package:" in workflow
    assert "python -m build" in workflow
    assert "twine check dist/*" in workflow
    assert "audit_public_artifacts.py --root . --dist dist/*" in workflow


def test_release_refuses_a_tag_not_on_current_main_and_reaudits():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "guard:" in workflow
    assert 'git fetch --no-tags origin main' in workflow
    assert 'git rev-list -n 1 "$GITHUB_REF"' in workflow
    assert "audit_public_artifacts.py --root . --dist dist/*" in workflow
    assert "needs: [guard, test, build]" in workflow
