from __future__ import annotations

from pathlib import Path

from scripts.audit_public_artifacts import public_surface_findings

ROOT = Path(__file__).resolve().parent.parent


def test_current_public_surfaces_contain_only_fictional_scoped_context():
    assert public_surface_findings(ROOT) == []
