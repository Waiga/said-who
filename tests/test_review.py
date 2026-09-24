"""Verdicts, the archive, and the promise that a kill stays killed."""

from __future__ import annotations

import pytest

from said_who.entries import Entry, SourceClass, Verdict, VerdictRecord, today
from said_who.gate import due, effective_review
from said_who.refusals import Refused


def an_entry(**kwargs) -> Entry:
    defaults = {
        "topic": "t",
        "title": "a title",
        "body": "a body",
        "src": SourceClass.MEASURED,
        "tier": "number",
        "dated": "2026-01-01",
    }
    defaults.update(kwargs)
    return Entry(**defaults)


def kill(store, entry, reason="it was never true", by="a reviewer"):
    return store.record_verdict(
        VerdictRecord(
            topic=entry.topic, target=entry.id, verdict=Verdict.KILL, by=by, reason=reason
        )
    )


def test_confirm_restarts_the_clock(store):
    entry = an_entry()
    store.add(entry)
    assert len(due(store, "t")) == 1
    store.record_verdict(
        VerdictRecord(topic="t", target=entry.id, verdict=Verdict.CONFIRM, by="a reviewer")
    )
    assert due(store, "t") == []
    assert effective_review(store, store.entries("t")[0]) > today()


def test_a_verdict_is_written_into_the_readable_file_too(store):
    entry = an_entry()
    store.add(entry)
    store.record_verdict(
        VerdictRecord(topic="t", target=entry.id, verdict=Verdict.REVISE, by="a reviewer")
    )
    text = store.topic_path("t").read_text()
    assert "verdict revise" in text
    assert "a reviewer" in text


def test_a_verdict_names_its_author_in_the_journal(store):
    entry = an_entry()
    store.add(entry)
    store.record_verdict(
        VerdictRecord(topic="t", target=entry.id, verdict=Verdict.CONFIRM, by="Meera")
    )
    verdicts = store.verdicts("t")
    assert len(verdicts) == 1
    assert verdicts[0].by == "Meera"


def test_a_verdict_on_an_unknown_entry_is_refused(store):
    store.add(an_entry())
    with pytest.raises(Refused) as caught:
        store.record_verdict(
            VerdictRecord(topic="t", target="000000000000", verdict=Verdict.CONFIRM, by="x")
        )
    assert caught.value.code == "NO_SUCH_ENTRY"


def test_a_kill_moves_the_entry_to_the_archive_with_its_reason(store):
    entry = an_entry()
    store.add(entry)
    kill(store, entry, reason="the figure was never measured")

    assert store.entries("t") == []
    archive = store.archive_path("t").read_text()
    assert entry.id in archive
    assert "the figure was never measured" in archive
    assert "a reviewer" in archive
    assert "a body" in archive


def test_a_kill_keeps_the_original_in_the_journal_permanently(store):
    entry = an_entry()
    store.add(entry)
    kill(store, entry)
    originals = [r for r in store.journal_records("t") if r.get("kind") == "entry"]
    assert originals and originals[0]["id"] == entry.id


def test_a_killed_entry_offered_again_is_refused(store):
    entry = an_entry()
    store.add(entry)
    kill(store, entry, reason="fabricated")
    with pytest.raises(Refused) as caught:
        store.add(an_entry())
    assert caught.value.code == "KILLED_ENTRY"
    assert "fabricated" in caught.value.detail


def test_a_rebuild_refuses_to_resurrect_a_killed_entry(store):
    survivor = an_entry(title="kept")
    doomed = an_entry(title="doomed")
    store.add(survivor)
    store.add(doomed)
    kill(store, doomed)

    # Somebody pastes the killed block back into the live file by hand. The next
    # rebuild must drop it again rather than carry it forward.
    path = store.topic_path("t")
    path.write_text(path.read_text() + doomed.to_markdown(), encoding="utf-8")
    assert [e.id for e in store.resurrected("t")] == [doomed.id]

    store._rewrite_without_locked("t", set())
    assert [e.title for e in store.entries("t")] == ["kept"]


def test_the_live_file_keeps_a_note_of_what_was_killed(store):
    entry = an_entry()
    store.add(entry)
    kill(store, entry)
    assert '"kind": "tombstone"' in store.topic_path("t").read_text()
    assert entry.id in store.topic_path("t").read_text()


def test_killing_one_entry_leaves_the_others_alone(store):
    first = an_entry(title="first")
    second = an_entry(title="second")
    third = an_entry(title="third", body="a different body")
    for entry in (first, second, third):
        store.add(entry)
    kill(store, second)
    assert sorted(e.title for e in store.entries("t")) == ["first", "third"]
    assert len(store.entries("t")) == 2
