from __future__ import annotations

from pathlib import Path

from scripts.audit_public_artifacts import public_surface_findings

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
