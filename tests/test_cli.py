"""The six commands, through the command line."""

from __future__ import annotations

import json

from said_who.cli import main
from tests.conftest import HUMAN_UUID, SESSION


def run(store, capsys, *argv):
    code = main(["--store", str(store.root), *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def add_one(store, capsys, topic="t", title="a claim", src="measured", body="a body", *extra):
    return run(
        store, capsys, "add", topic, "--title", title, "--src", src, "--body", body, *extra
    )


def test_add_reports_what_it_stored(store, capsys):
    code, out, _ = add_one(store, capsys)
    assert code == 0
    assert "stored" in out
    assert "measured" in out


def test_add_reads_the_body_from_stdin(store, capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("a body from stdin"))
    code, out, _ = run(store, capsys, "add", "t", "--title", "piped", "--src", "measured")
    assert code == 0
    assert store.entries("t")[0].body == "a body from stdin"


def test_add_twice_says_nothing_was_written(store, capsys):
    add_one(store, capsys)
    code, out, _ = add_one(store, capsys)
    assert code == 0
    assert "already stored" in out


def test_list_shows_entries_and_filters_by_class(store, capsys):
    add_one(store, capsys, title="one", src="measured")
    add_one(store, capsys, title="two", src="derived", body="a different body")

    code, out, _ = run(store, capsys, "list")
    assert code == 0
    assert "one" in out and "two" in out

    code, out, _ = run(store, capsys, "list", "--src", "derived")
    assert "two" in out and "one" not in out


def test_list_as_json(store, capsys):
    add_one(store, capsys)
    code, out, _ = run(store, capsys, "list", "--json")
    payload = json.loads(out)
    assert payload[0]["src"] == "measured"
    assert payload[0]["title"] == "a claim"


def test_list_of_an_empty_store(store, capsys):
    code, out, _ = run(store, capsys, "list")
    assert code == 0
    assert "nothing stored" in out


def test_verify_reports_a_citation_that_holds(store, capsys, transcripts):
    run(
        store,
        capsys,
        "add",
        "t",
        "--title",
        "cited",
        "--src",
        "human",
        "--cite",
        f"{SESSION}#{HUMAN_UUID}",
        "--quote",
        "next PR",
        "--body",
        "The next piece of work is the one named in the cited turn.",
    )
    code, out, _ = run(store, capsys, "verify")
    assert code == 0
    assert "holds" in out


def test_verify_reports_a_citation_that_has_gone(store, capsys, transcripts, tmp_path, monkeypatch):
    run(
        store,
        capsys,
        "add",
        "t",
        "--title",
        "cited",
        "--src",
        "human",
        "--cite",
        f"{SESSION}#{HUMAN_UUID}",
        "--quote",
        "next PR",
        "--body",
        "The next piece of work is the one named in the cited turn.",
    )
    # The transcripts are gone, as they would be on another machine.
    monkeypatch.setenv("SAID_WHO_CLAUDE_PROJECTS", str(tmp_path / "elsewhere"))
    code, out, _ = run(store, capsys, "verify")
    assert code == 1
    assert "BROKEN" in out
    assert "NO_SUCH_SESSION" in out


def test_verify_with_nothing_cited(store, capsys):
    add_one(store, capsys)
    code, out, _ = run(store, capsys, "verify")
    assert code == 0
    assert "no cited entries" in out


def test_review_lists_what_is_due(store, capsys):
    run(
        store,
        capsys,
        "add",
        "t",
        "--title",
        "a promise",
        "--src",
        "measured",
        "--tier",
        "commitment",
        "--review",
        "2020-01-01",
        "--body",
        "due long ago",
    )
    code, out, _ = run(store, capsys, "review")
    assert code == 0
    assert "a promise" in out
    assert "confirm, revise or kill" in out


def test_review_when_nothing_is_due(store, capsys):
    add_one(store, capsys)
    code, out, _ = run(store, capsys, "review")
    assert "nothing is due" in out


def test_verdict_confirm_and_kill(store, capsys):
    add_one(store, capsys)
    entry_id = store.entries("t")[0].id

    code, out, _ = run(store, capsys, "verdict", "t", entry_id, "--confirm", "--by", "a reviewer")
    assert code == 0
    assert "confirmed" in out

    code, out, _ = run(
        store,
        capsys,
        "verdict",
        "t",
        entry_id,
        "--kill",
        "--by",
        "a reviewer",
        "--reason",
        "superseded",
    )
    assert code == 0
    assert "killed" in out
    assert store.entries("t") == []


def test_doctor_on_a_healthy_store(store, capsys, transcripts):
    add_one(store, capsys)
    code, out, _ = run(store, capsys, "doctor")
    assert code == 0
    assert "adapter" in out
    assert "journal:t" in out


def test_doctor_notices_a_live_entry_the_journal_never_saw(store, capsys, transcripts):
    add_one(store, capsys)
    store.journal_path("t").write_text("", encoding="utf-8")
    code, out, _ = run(store, capsys, "doctor")
    assert code == 2
    assert "not in the journal" in out


def test_doctor_notices_a_resurrected_entry(store, capsys, transcripts):
    add_one(store, capsys)
    entry = store.entries("t")[0]
    run(
        store,
        capsys,
        "verdict",
        "t",
        entry.id,
        "--kill",
        "--by",
        "a reviewer",
        "--reason",
        "wrong",
    )
    path = store.topic_path("t")
    path.write_text(path.read_text() + entry.to_markdown(), encoding="utf-8")
    code, out, _ = run(store, capsys, "doctor", "--json")
    assert code == 2
    assert any(c["name"] == "killed:t" for c in json.loads(out))


def test_doctor_on_a_store_that_does_not_exist_yet(store, capsys, transcripts):
    code, out, _ = run(store, capsys, "doctor")
    assert code == 0
    assert "does not exist yet" in out


def test_doctor_names_an_unknown_harness(store, capsys, transcripts):
    code, out, _ = run(store, capsys, "doctor", "--harness", "some-other-harness")
    assert code == 2
    assert "No adapter" in out


def test_a_bad_topic_name_is_refused_at_the_command_line(store, capsys):
    code, _, err = add_one(store, capsys, "../escape")
    assert code == 1
    assert "BAD_TOPIC" in err


def test_list_due_says_nothing_is_due_rather_than_nothing_stored(store, capsys):
    add_one(store, capsys)
    code, out, _ = run(store, capsys, "list", "--due")
    assert code == 0
    assert "nothing is due" in out
