"""The Claude Code adapter, against synthetic transcripts in the shapes measured."""

from __future__ import annotations

from said_who.harness import claude_code
from tests.conftest import (
    ASSISTANT_UUID,
    BLOCK_TEXT,
    BLOCKS_UUID,
    HUMAN_TEXT,
    HUMAN_UUID,
    NOTIFICATION_UUID,
    OTHER_SESSION,
    SESSION,
)


def test_string_content_resolves(transcripts):
    turn = claude_code.resolve(f"{SESSION}#{HUMAN_UUID}")
    assert turn.status == "OK"
    assert turn.human is True
    assert turn.text == HUMAN_TEXT


def test_block_content_resolves(transcripts):
    turn = claude_code.resolve(f"{SESSION}#{BLOCKS_UUID}")
    assert turn.status == "OK"
    assert turn.text == BLOCK_TEXT


def test_task_notification_is_not_human(transcripts):
    turn = claude_code.resolve(f"{SESSION}#{NOTIFICATION_UUID}")
    assert turn.status.startswith("NOT_HUMAN_TURN")
    assert "task-notification" in turn.status
    assert turn.human is False


def test_assistant_turn_is_not_human(transcripts):
    turn = claude_code.resolve(f"{SESSION}#{ASSISTANT_UUID}")
    assert turn.status.startswith("NOT_HUMAN_TURN")
    assert turn.human is False


def test_unknown_message_in_known_session(transcripts):
    turn = claude_code.resolve(f"{SESSION}#{HUMAN_UUID[:-1]}9")
    assert turn.status == "NO_SUCH_MESSAGE"


def test_unknown_session(transcripts):
    turn = claude_code.resolve(f"{OTHER_SESSION[:-1]}9#{HUMAN_UUID}")
    assert turn.status == "NO_SUCH_SESSION"


def test_empty_session_file_finds_nothing(transcripts):
    turn = claude_code.resolve(f"{OTHER_SESSION}#{HUMAN_UUID}")
    assert turn.status == "NO_SUCH_MESSAGE"


def test_bad_locators(transcripts):
    for locator in ("", "nohash", "not-hex-at-all#" + HUMAN_UUID, f"{SESSION}#", "#"):
        assert claude_code.resolve(locator).status == "BAD_LOCATOR_FORMAT"


def test_a_torn_line_does_not_stop_the_search(transcripts):
    # The torn line sits between the two human turns in the fixture, so finding
    # the second one proves the parser walked past it.
    assert claude_code.resolve(f"{SESSION}#{BLOCKS_UUID}").status == "OK"


def test_missing_transcript_root(tmp_path, monkeypatch):
    monkeypatch.setenv(claude_code.ENV_ROOT, str(tmp_path / "nothing-here"))
    assert claude_code.resolve(f"{SESSION}#{HUMAN_UUID}").status == "NO_SUCH_SESSION"
