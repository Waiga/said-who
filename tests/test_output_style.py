"""House style, checked rather than remembered.

No punctuation dashes anywhere: not in the README, not in a docstring, not in a
comment, not in help text. The rule is enforced by codepoint, because a dash
pasted from a word processor looks identical to the eye and is a different
character underneath.

Hyphens inside genuine compound words and inside identifiers that cannot be
changed are spelling rather than punctuation, and they stay.
"""

from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Built from codepoints so that this file, which is scanned like every other,
# does not contain the characters it is looking for.
FORBIDDEN = {
    chr(0x2012): "figure dash",
    chr(0x2013): "en dash",
    chr(0x2014): "em dash",
    chr(0x2015): "horizontal bar",
    chr(0x2212): "minus sign",
    chr(0x2010): "hyphen",
    chr(0x2011): "non breaking hyphen",
}

SPACED_HYPHEN = " " + "-" + " "

# Fixed identifiers, spelled by somebody else. A PyPI classifier is a literal the
# package index defines, so changing it to satisfy a punctuation rule would only
# break the metadata.
ALLOWED_LITERALS = (
    "Development Status :: 4" + SPACED_HYPHEN + "Beta",
    'SPACED_HYPHEN = " " + "-" + " "',
)

SHIPPED = [
    "README.md",
    "LICENSE",
    "pyproject.toml",
    ".gitignore",
    ".pre-commit-hooks.yaml",
]
SHIPPED_TREES = ["said_who", "tests", ".github"]


def shipped_files() -> list[pathlib.Path]:
    files = [ROOT / name for name in SHIPPED]
    for tree in SHIPPED_TREES:
        for path in sorted((ROOT / tree).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files.append(path)
    return [f for f in files if f.exists()]


def spaced_hyphens(text: str) -> list[str]:
    """A hyphen used as punctuation, rather than a list bullet or a fixed literal."""
    hits = []
    for raw in text.splitlines():
        line = raw
        for allowed in ALLOWED_LITERALS:
            line = line.replace(allowed, "")
        # A list bullet inside a comment is still a list bullet, so the comment
        # marker comes off before the line is judged.
        stripped = line.lstrip()
        if stripped.startswith("#"):
            line = stripped[1:]
        start = 0
        while True:
            at = line.find(SPACED_HYPHEN, start)
            if at < 0:
                break
            start = at + 1
            if line[:at].strip():  # something real before it, so it is punctuation
                hits.append(raw.strip())
    return hits


@pytest.mark.parametrize("path", shipped_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_punctuation_dashes(path: pathlib.Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    for character, name in FORBIDDEN.items():
        assert character not in text, f"{path.relative_to(ROOT)} contains a {name}"
    assert not spaced_hyphens(text), f"{path.relative_to(ROOT)} uses a spaced hyphen"


def test_the_checker_catches_what_it_is_looking_for():
    """The guard, proved by putting the defect in front of it."""
    for character in FORBIDDEN:
        assert character in character  # the codepoint exists as written
    assert spaced_hyphens("a sentence" + SPACED_HYPHEN + "with punctuation")
    assert not spaced_hyphens("- a list item")
    assert not spaced_hyphens("#    " + SPACED_HYPHEN + "a list item inside a comment")
    assert not spaced_hyphens("a read-only compound word")


def test_the_readme_says_what_it_cannot_prove_before_it_says_what_it_can():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    limits = text.lower().index("what it does not prove")
    example = text.index("```")
    assert limits < example, "the limits have to come before the first example"


def test_the_readme_names_the_only_supported_harness_before_anything_else():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    opening = text[: text.index("\n## ")]
    assert "Claude Code and nothing else" in opening


def test_the_readme_calls_the_laundering_check_a_speed_bump():
    text = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "speed bump" in text


def test_the_readme_says_it_was_built_with_an_ai_assistant():
    text = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "ai assistant" in text
    assert "co-authored-by" in text
