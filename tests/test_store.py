"""Writing, reading, deduplicating, and the tiers."""

from __future__ import annotations

import datetime
import json

import pytest

from said_who.entries import (
    TIERS,
    Entry,
    SourceClass,
    entry_id,
    parse_blocks,
    review_date_for,
)
from said_who.gate import accept, due, effective_review
from said_who.refusals import Refused
from said_who.store import Store, check_topic


def an_entry(**kwargs) -> Entry:
    defaults = {
        "topic": "t",
        "title": "a title",
        "body": "a body",
        "src": SourceClass.MEASURED,
    }
    defaults.update(kwargs)
    return Entry(**defaults)


def test_an_entry_round_trips_through_markdown():
    entry = an_entry(body="two lines\nof body")
    blocks = parse_blocks(entry.to_markdown())
    assert len(blocks) == 1
    meta, heading, body = blocks[0]
    assert meta["id"] == entry.id
    assert entry.title in heading
    assert body == "two lines\nof body"


def test_identity_is_content(store):
    assert entry_id("t", "a", "b") == entry_id("t", " A ", "B\n")
    assert entry_id("t", "a", "b") != entry_id("t", "a", "c")


def test_the_same_entry_twice_is_stored_once(store):
    assert store.add(an_entry()) == "OK"
    assert store.add(an_entry()) == "DUPLICATE"
    assert len(store.entries("t")) == 1


def test_every_entry_reaches_the_journal(store):
    store.add(an_entry())
    records = [r for r in store.journal_records("t") if r.get("kind") == "entry"]
    assert len(records) == 1
    assert records[0]["body"] == "a body"
    assert store.missing_from_journal("t") == []


def test_the_journal_survives_a_torn_line(store):
    store.add(an_entry())
    path = store.journal_path("t")
    path.write_text(path.read_text() + "{ half a line\n", encoding="utf-8")
    assert len(store.journal_records("t")) == 1


def test_topics_are_checked_before_they_become_paths(store):
    for bad in ("../escape", "has space", "", "UPPER/lower", "a" * 100):
        with pytest.raises(Refused) as caught:
            check_topic(bad)
        assert caught.value.code == "BAD_TOPIC"


def test_store_reads_every_topic_when_none_is_named(store):
    store.add(an_entry(topic="one"))
    store.add(an_entry(topic="two"))
    assert {e.topic for e in store.entries()} == {"one", "two"}


def test_tier_sets_the_review_date():
    for tier, (days, _) in TIERS.items():
        when = review_date_for(tier, "2026-01-01")
        if days:
            expected = (datetime.date(2026, 1, 1) + datetime.timedelta(days=days)).isoformat()
            assert when == expected
        else:
            assert when is None


def test_permanent_never_comes_due(store):
    store.add(an_entry(tier="permanent"))
    assert due(store, "t", on="2099-01-01") == []


def test_a_number_comes_due_in_thirty_days(store):
    store.add(an_entry(tier="number", dated="2026-01-01"))
    assert due(store, "t", on="2026-01-30") == []
    assert len(due(store, "t", on="2026-01-31")) == 1


def test_a_commitment_needs_its_own_date(store):
    with pytest.raises(Refused) as caught:
        accept(store, "t", "a promise", "by friday", "measured", tier="commitment")
    assert caught.value.code == "NO_REVIEW_DATE"
    assert accept(
        store, "t", "a promise", "by friday", "measured", tier="commitment", review="2026-10-01"
    ).status == "OK"


def test_an_unknown_tier_is_refused(store):
    with pytest.raises(Refused) as caught:
        accept(store, "t", "x", "y", "measured", tier="whenever")
    assert caught.value.code == "UNKNOWN_TIER"


def test_an_unknown_source_class_is_refused(store):
    with pytest.raises(Refused) as caught:
        accept(store, "t", "x", "y", "hearsay-ish")
    assert caught.value.code == "UNKNOWN_SOURCE_CLASS"


def test_a_bad_review_date_is_refused(store):
    with pytest.raises(Refused) as caught:
        accept(store, "t", "x", "y", "measured", review="next tuesday")
    assert caught.value.code == "BAD_REVIEW_DATE"


def test_an_empty_title_or_body_is_refused(store):
    with pytest.raises(Refused) as caught:
        accept(store, "t", "   ", "y", "measured")
    assert caught.value.code == "NO_TITLE"
    with pytest.raises(Refused) as caught:
        accept(store, "t", "x", "  \n ", "measured")
    assert caught.value.code == "NO_BODY"


def test_an_unreadable_class_in_a_file_is_skipped_not_fatal(store):
    store.add(an_entry())
    path = store.topic_path("t")
    text = path.read_text()
    broken = text.replace('"src": "measured"', '"src": "vibes"')
    path.write_text(broken + "\n## 2026-01-01 junk\n\nno metadata here\n", encoding="utf-8")
    assert store.entries("t") == []


def test_effective_review_uses_the_entry_when_there_is_no_verdict(store):
    entry = an_entry(tier="number", dated="2026-01-01")
    store.add(entry)
    assert effective_review(store, store.entries("t")[0]) == "2026-01-31"


def test_the_store_directory_is_the_users_choice(tmp_path):
    somewhere = tmp_path / "a" / "b" / "c"
    other = Store(somewhere)
    other.add(an_entry())
    assert (somewhere / "t.md").exists()
    assert (somewhere / "journal" / "t.ndjson").exists()


def test_the_metadata_line_is_valid_json(store):
    store.add(an_entry())
    for line in store.topic_path("t").read_text().splitlines():
        if line.startswith("<!-- said-who "):
            json.loads(line[len("<!-- said-who ") : -len(" -->")])
