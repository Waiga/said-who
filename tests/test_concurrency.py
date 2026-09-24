"""The concurrency test, with the real defect put back.

Concurrent agents are the normal case. The claim this package makes is that a
naive read, modify and write on one file loses entries under contention, and that
an append under an exclusive lock does not. A claim like that is worth nothing
asserted, so this file implements the naive writer, runs it, and measures what it
loses before measuring what the real writer keeps.

Both writers are real processes, started at the same moment, writing the same
blocks into the same store. The only difference between them is how they write.
"""

from __future__ import annotations

import subprocess
import sys

from said_who.store import Store

WRITERS = 20
TOPIC = "race"

# The defect, in full. Read the file, spend a moment building the new content, then
# write the whole file back. Every writer that read before any other wrote has a
# stale copy in hand, and the last write wins.
NAIVE_WRITER = '''
import pathlib
import sys
import time

from said_who.entries import Entry, SourceClass

path = pathlib.Path(sys.argv[1])
number = sys.argv[2]
entry = Entry(topic="race", title=f"entry {number}", body=f"body {number}",
              src=SourceClass.MEASURED, dated="2026-01-01")

text = path.read_text(encoding="utf-8") if path.exists() else ""   # read
time.sleep(0.4)                                                    # modify
path.write_text(text + entry.to_markdown(), encoding="utf-8")      # write
'''

# The real writer. Same entries, same moment, through the store.
REAL_WRITER = '''
import sys
import time

from said_who.entries import Entry, SourceClass
from said_who.store import Store

root = sys.argv[1]
number = sys.argv[2]
entry = Entry(topic="race", title=f"entry {number}", body=f"body {number}",
              src=SourceClass.MEASURED, dated="2026-01-01")

time.sleep(0.4)
Store(root).add(entry)
'''


def _run_together(script: str, target: str, writers: int) -> None:
    processes = [
        subprocess.Popen([sys.executable, "-c", script, target, str(n)])
        for n in range(writers)
    ]
    for process in processes:
        assert process.wait(timeout=120) == 0


def test_the_naive_writer_loses_entries_and_the_real_one_does_not(tmp_path, capsys):
    naive_root = tmp_path / "naive"
    naive_root.mkdir()
    naive_file = naive_root / f"{TOPIC}.md"
    _run_together(NAIVE_WRITER, str(naive_file), WRITERS)
    naive_survivors = len(Store(naive_root).entries(TOPIC))

    real_root = tmp_path / "real"
    real_root.mkdir()
    _run_together(REAL_WRITER, str(real_root), WRITERS)
    real_survivors = len(Store(real_root).entries(TOPIC))

    with capsys.disabled():
        print(
            f"\nconcurrency, {WRITERS} writers at once:"
            f"\n  naive read modify write: {naive_survivors} of {WRITERS} survived"
            f"\n  append under a lock:     {real_survivors} of {WRITERS} survived"
        )

    assert naive_survivors < WRITERS, "the naive writer was supposed to lose entries"
    assert real_survivors == WRITERS, "the real writer lost an entry"


def test_the_journal_matches_the_live_file_after_contention(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    _run_together(REAL_WRITER, str(root), WRITERS)
    store = Store(root)
    assert len(store.known_ids(TOPIC)) == WRITERS
    assert store.missing_from_journal(TOPIC) == []


def test_every_concurrent_entry_is_readable(tmp_path):
    """A half written block would show up as a missing or malformed entry."""
    root = tmp_path / "store"
    root.mkdir()
    _run_together(REAL_WRITER, str(root), WRITERS)
    titles = sorted(e.title for e in Store(root).entries(TOPIC))
    assert titles == sorted(f"entry {n}" for n in range(WRITERS))
