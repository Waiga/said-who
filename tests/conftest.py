"""Fixtures.

Every transcript in this suite is written by the suite. Nothing here reads a real
transcript, a real store or anything else belonging to a person. The shapes are
copied from a real Claude Code transcript that was inspected once, and the
inspection is recorded in the adapter's docstring rather than in the fixtures.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from said_who.harness import claude_code
from said_who.store import Store

HUMAN_TEXT = "let us review the lantern checklist"
BLOCK_TEXT = "pack the maps after the route is confirmed"

SESSION = "4f3a2b1c-6d7e-4f80-9a1b-2c3d4e5f6071"
OTHER_SESSION = "8e7d6c5b-4a39-4f28-a1b0-c9d8e7f60514"

HUMAN_UUID = "11223344-5566-4788-99aa-bbccddeeff00"
BLOCKS_UUID = "22334455-6677-4889-aabb-ccddeeff0011"
NOTIFICATION_UUID = "33445566-7788-499a-bbcc-ddeeff001122"
ASSISTANT_UUID = "44556677-8899-4aab-8ccd-eeff00112233"

INVENTED_SESSION = "55667788-99aa-4bbc-8dde-ff0011223344"
INVENTED_MESSAGE_UUID = "66778899-aabb-4ccd-8eef-001122334455"
INVENTED_LOCATOR = f"{INVENTED_SESSION}#{INVENTED_MESSAGE_UUID}"


def human_record(uuid: str, session: str, content) -> dict:
    """A turn the harness stamped as typed by a person."""
    return {
        "uuid": uuid,
        "sessionId": session,
        "type": "user",
        "userType": "external",
        "origin": {"kind": "human"},
        "message": {"role": "user", "content": content},
    }


def notification_record(uuid: str, session: str) -> dict:
    """The only other origin kind seen in a real transcript."""
    return {
        "uuid": uuid,
        "sessionId": session,
        "type": "user",
        "origin": {"kind": "task-notification"},
        "message": {"role": "user", "content": "a background task finished"},
    }


def assistant_record(uuid: str, session: str) -> dict:
    """No origin at all. An agent's own turn must never pass as a person's."""
    return {
        "uuid": uuid,
        "sessionId": session,
        "type": "assistant",
        "message": {"role": "assistant", "content": "I have decided the launch city is Alder Bay"},
    }


@pytest.fixture
def transcripts(tmp_path: pathlib.Path, monkeypatch) -> pathlib.Path:
    """A synthetic ~/.claude/projects tree, pointed at by the adapter."""
    root = tmp_path / "projects" / "-Users-someone-work-thing"
    root.mkdir(parents=True)

    lines = [
        json.dumps(human_record(HUMAN_UUID, SESSION, HUMAN_TEXT)),
        "{ this line is not json",  # a torn line must be skipped, never fatal
        json.dumps(
            human_record(
                BLOCKS_UUID,
                SESSION,
                [{"type": "text", "text": BLOCK_TEXT}],
            )
        ),
        json.dumps(notification_record(NOTIFICATION_UUID, SESSION)),
        json.dumps(assistant_record(ASSISTANT_UUID, SESSION)),
    ]
    (root / f"{SESSION}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / f"{OTHER_SESSION}.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setenv(claude_code.ENV_ROOT, str(tmp_path / "projects"))
    return tmp_path / "projects"


@pytest.fixture
def store(tmp_path: pathlib.Path, monkeypatch) -> Store:
    root = tmp_path / "store"
    monkeypatch.setenv("SAID_WHO_STORE", str(root))
    return Store(root)


@pytest.fixture
def good_cite() -> str:
    return f"{SESSION}#{HUMAN_UUID}"


@pytest.fixture
def run_cli(store, capsys):
    """Run the command line the way a user would, and give back code and output."""
    from said_who.cli import main

    def run(*argv: str, stdin: str | None = None, monkeypatch=None):
        args = ["--store", str(store.root), *argv]
        if stdin is not None:
            args = args + ["--body", stdin]
        code = main(args)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run
