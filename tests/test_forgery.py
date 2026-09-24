"""The forgery suite.

Five ways to get a fabricated claim into the store. All five are refused, through
the command line, the way an agent would actually try them. The refusal message is
printed so a run of this file is also the evidence.

Every transcript here is written by this suite. Nothing reads a real one.
"""

from __future__ import annotations

import pytest

from said_who.cli import main
from tests.conftest import HUMAN_UUID, NOTIFICATION_UUID, SESSION

REAL_CITE = f"{SESSION}#{HUMAN_UUID}"
NOT_HUMAN_CITE = f"{SESSION}#{NOTIFICATION_UUID}"
INVENTED_CITE = "11111111-2222-4333-8444-555555555555#66666666-7777-4888-8999-aaaaaaaaaaaa"

FABRICATION = "The November target is reset to 115K and the 200K step moves to Q2 2027."


def attempt(store, capsys, *argv: str) -> tuple[int, str]:
    code = main(["--store", str(store.root), *argv])
    captured = capsys.readouterr()
    return code, (captured.err + captured.out).strip()


def report(name: str, message: str) -> None:
    print(f"\nforgery {name}:\n{message}")


def test_one_an_invented_locator(store, transcripts, capsys):
    code, message = attempt(
        store,
        capsys,
        "add",
        "targets",
        "--title",
        "the reset",
        "--src",
        "human",
        "--cite",
        INVENTED_CITE,
        "--quote",
        "reset November",
        "--body",
        FABRICATION,
    )
    report("one, an invented locator", message)
    assert code == 1
    assert "REFUSED [NO_SUCH_SESSION]" in message
    assert store.entries("targets") == []


def test_two_a_real_locator_with_a_quote_that_is_not_in_it(store, transcripts, capsys):
    code, message = attempt(
        store,
        capsys,
        "add",
        "targets",
        "--title",
        "the reset",
        "--src",
        "human",
        "--cite",
        REAL_CITE,
        "--quote",
        "reset November to 115K",
        "--body",
        FABRICATION,
    )
    report("two, a real locator with a quote that is not in it", message)
    assert code == 1
    assert "REFUSED [QUOTE_NOT_IN_MESSAGE]" in message
    assert store.entries("targets") == []


def test_three_a_real_locator_at_a_turn_the_harness_did_not_mark_human(
    store, transcripts, capsys
):
    code, message = attempt(
        store,
        capsys,
        "add",
        "targets",
        "--title",
        "the reset",
        "--src",
        "human",
        "--cite",
        NOT_HUMAN_CITE,
        "--quote",
        "a background task finished",
        "--body",
        FABRICATION,
    )
    report("three, a real locator at a turn the harness did not mark human", message)
    assert code == 1
    assert "REFUSED [NOT_HUMAN_TURN]" in message
    assert store.entries("targets") == []


def test_four_a_correct_quote_laundered_through_a_weaker_class(store, transcripts, capsys):
    # The hardest one, and the one that matters most. The citation is real, the
    # quote is real, the turn is human. The entry is filed as derived so that no
    # citation is demanded, and the body asserts a decision the quoted words do
    # not contain.
    code, message = attempt(
        store,
        capsys,
        "add",
        "targets",
        "--title",
        "the reset",
        "--src",
        "derived",
        "--body",
        "Waiga approved the reset to 115K. " + FABRICATION,
    )
    report("four, a correct quote laundered through a weaker class", message)
    assert code == 1
    assert "REFUSED [LAUNDERED_ATTRIBUTION]" in message
    assert store.entries("targets") == []


def test_five_a_killed_entry_offered_again(store, transcripts, capsys):
    body = "The target was reset in November."
    code, _ = attempt(
        store, capsys, "add", "targets", "--title", "the reset", "--src", "derived", "--body", body
    )
    assert code == 0
    entry_id = store.entries("targets")[0].id

    code, _ = attempt(
        store,
        capsys,
        "verdict",
        "targets",
        entry_id,
        "--kill",
        "--by",
        "a reviewer",
        "--reason",
        "nobody said it",
    )
    assert code == 0

    code, message = attempt(
        store, capsys, "add", "targets", "--title", "the reset", "--src", "derived", "--body", body
    )
    report("five, a killed entry offered again", message)
    assert code == 1
    assert "REFUSED [KILLED_ENTRY]" in message
    assert store.entries("targets") == []


def test_a_kill_needs_a_reason(store, transcripts, capsys):
    attempt(
        store, capsys, "add", "t", "--title", "x", "--src", "measured", "--body", "a body"
    )
    entry_id = store.entries("t")[0].id
    code, message = attempt(store, capsys, "verdict", "t", entry_id, "--kill", "--by", "someone")
    assert code == 1
    assert "REFUSED [NO_REASON]" in message
    assert len(store.entries("t")) == 1


@pytest.mark.parametrize(
    "src",
    ["measured", "derived", "external"],
)
def test_the_laundering_route_is_shut_for_every_weaker_class(store, transcripts, capsys, src):
    code, message = attempt(
        store,
        capsys,
        "add",
        "targets",
        "--title",
        "the reset",
        "--src",
        src,
        "--body",
        "Waiga confirmed the new target this morning.",
    )
    assert code == 1
    assert "REFUSED [LAUNDERED_ATTRIBUTION]" in message
