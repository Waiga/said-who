"""The store on disk: plain files, appended to under a lock, never rewritten lightly.

Layout, for a store directory the user chooses:

    <store>/<topic>.md                   the readable log, one block per entry
    <store>/journal/<topic>.ndjson       append only, never rewritten, the record
    <store>/archive/<topic>.retired.md   killed entries, with their reason

Concurrent agents are the normal case, not the edge case. Two writers doing a read,
a modify and a write on one file lose entries, silently, with no error anywhere. So
every write here is an append under an exclusive lock, and the one operation that
must rewrite a file (a kill, which moves an entry out) takes the same lock for the
whole read and write, so it cannot interleave with an append.

No database and no daemon. A memory that needs a server running is a memory that is
silently empty when the server is down.
"""

from __future__ import annotations

import fcntl
import json
import os
import pathlib
import re
import time

from said_who.entries import (
    Entry,
    SourceClass,
    Verdict,
    VerdictRecord,
    parse_blocks,
    title_without_date,
)
from said_who.refusals import Refused

ENV_STORE = "SAID_WHO_STORE"
DEFAULT_STORE = "~/.said-who"

TOPIC_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


def default_store() -> pathlib.Path:
    return pathlib.Path(os.environ.get(ENV_STORE, DEFAULT_STORE)).expanduser()


def check_topic(topic: str) -> str:
    """Topics become file names, so they are checked before they become paths."""
    topic = (topic or "").strip().lower()
    if not TOPIC_RE.fullmatch(topic):
        raise Refused(
            "BAD_TOPIC",
            f"{topic!r} is not a usable topic name.",
            "Lowercase letters, digits, dot, dash and underscore, up to 64 characters.",
        )
    return topic


class Store:
    """Every read and write of the store goes through here."""

    def __init__(self, root: pathlib.Path | str | None = None) -> None:
        self.root = pathlib.Path(root).expanduser() if root else default_store()

    # ------------------------------------------------------------- paths

    def topic_path(self, topic: str) -> pathlib.Path:
        return self.root / f"{check_topic(topic)}.md"

    def journal_path(self, topic: str) -> pathlib.Path:
        return self.root / "journal" / f"{check_topic(topic)}.ndjson"

    def archive_path(self, topic: str) -> pathlib.Path:
        return self.root / "archive" / f"{check_topic(topic)}.retired.md"

    def lock_path(self, topic: str) -> pathlib.Path:
        return self.root / "locks" / f"{check_topic(topic)}.lock"

    def topics(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.md"))

    # ------------------------------------------------------------- locking

    def _lock(self, topic: str) -> int:
        """Take the topic's exclusive lock. The caller must release it."""
        path = self.lock_path(topic)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    @staticmethod
    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    @staticmethod
    def _append_locked(path: pathlib.Path, text: str) -> None:
        """Append with O_APPEND, which the kernel makes atomic for one write.

        The caller already holds the topic lock. Both together are what make a
        second writer wait rather than overwrite.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, text.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    # ------------------------------------------------------------- reading

    @staticmethod
    def _read(path: pathlib.Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    def entries(self, topic: str | None = None) -> list[Entry]:
        out: list[Entry] = []
        for name in [topic] if topic else self.topics():
            for meta, heading, body in parse_blocks(self._read(self.topic_path(name))):
                if meta.get("kind") != "entry":
                    continue
                meta.setdefault("topic", name)
                try:
                    out.append(Entry.from_meta(meta, title_without_date(heading), body))
                except ValueError:
                    continue  # an unknown class is not readable as an entry
        return out

    def journal_records(self, topic: str) -> list[dict]:
        out = []
        for line in self._read(self.journal_path(topic)).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn line loses itself, never the rest of the journal
            if isinstance(record, dict):
                out.append(record)
        return out

    def verdicts(self, topic: str) -> list[VerdictRecord]:
        out = []
        for record in self.journal_records(topic):
            if record.get("kind") != "verdict":
                continue
            try:
                out.append(
                    VerdictRecord(
                        topic=record.get("topic", topic),
                        target=record.get("target", ""),
                        verdict=Verdict(record.get("verdict", "")),
                        by=record.get("by", ""),
                        reason=record.get("reason"),
                        dated=record.get("date", ""),
                    )
                )
            except ValueError:
                continue
        return out

    def known_ids(self, topic: str) -> set[str]:
        return {r.get("id", "") for r in self.journal_records(topic) if r.get("kind") == "entry"}

    def killed_ids(self, topic: str) -> set[str]:
        """Entries given a kill verdict. The journal is the record, permanently."""
        return {v.target for v in self.verdicts(topic) if v.verdict is Verdict.KILL}

    def last_verdict(self, topic: str, entry_id: str) -> VerdictRecord | None:
        found = [v for v in self.verdicts(topic) if v.target == entry_id]
        return found[-1] if found else None

    # ------------------------------------------------------------- writing

    def add(self, entry: Entry) -> str:
        """Write one entry. Gives back OK, or DUPLICATE when it was already there.

        Refusals that belong to the content are made before this is called. The two
        made here belong to the store: an entry already present, and an entry that
        was killed being offered again.
        """
        topic = check_topic(entry.topic)
        fd = self._lock(topic)
        try:
            if entry.id in self.killed_ids(topic):
                verdict = self.last_verdict(topic, entry.id)
                reason = verdict.reason if verdict and verdict.reason else "no reason recorded"
                who = verdict.by if verdict else "unknown"
                raise Refused(
                    "KILLED_ENTRY",
                    f"Entry {entry.id} was killed by {who} and may not be added again.",
                    f"Reason recorded at the kill: {reason}. It is in "
                    f"{self.archive_path(topic)}, and the journal keeps the original.",
                )
            if entry.id in self.known_ids(topic):
                return "DUPLICATE"

            self._append_locked(self.topic_path(topic), entry.to_markdown())
            record = dict(entry.meta())
            record["ts"] = time.time()
            record["title"] = entry.title
            record["body"] = entry.body
            self._append_locked(
                self.journal_path(topic),
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n",
            )
            return "OK"
        finally:
            self._unlock(fd)

    def record_verdict(self, record: VerdictRecord) -> str:
        """Give a due entry its verdict.

        Confirm and revise append, like everything else. A kill also moves the
        entry out of the live file and into the archive, which is the one place
        this tool rewrites a file, under the same lock an append takes.
        """
        topic = check_topic(record.topic)
        fd = self._lock(topic)
        try:
            entries = {e.id: e for e in self.entries(topic)}
            target = entries.get(record.target)
            if target is None:
                raise Refused(
                    "NO_SUCH_ENTRY",
                    f"No entry {record.target} in topic {topic}.",
                    "Run `said-who list` to see the ids that exist.",
                )

            self._append_locked(
                self.journal_path(topic),
                json.dumps(dict(record.meta(), ts=time.time()), ensure_ascii=False, sort_keys=True)
                + "\n",
            )

            if record.verdict is Verdict.KILL:
                self._archive_locked(topic, target, record)
                self._rewrite_without_locked(topic, {record.target})
            else:
                self._append_locked(self.topic_path(topic), record.to_markdown())
            return "OK"
        finally:
            self._unlock(fd)

    def _archive_locked(self, topic: str, entry: Entry, record: VerdictRecord) -> None:
        meta = json.dumps(
            dict(record.meta(), kind="archived", entry=entry.meta()),
            ensure_ascii=False,
            sort_keys=True,
        )
        block = (
            f"## {record.dated} killed {entry.id} {entry.title}\n\n"
            f"<!-- said-who {meta} -->\n\n"
            f"Killed by {record.by} on {record.dated}.\n"
            f"Reason: {record.reason or 'none given'}\n\n"
            f"The entry as it stood:\n\n{entry.body.strip()}\n\n"
        )
        self._append_locked(self.archive_path(topic), block)

    def _rewrite_without_locked(self, topic: str, drop: set[str]) -> None:
        """Rebuild the live file without the dropped entries.

        Every rebuild in this tool goes through here, and it refuses to write back
        anything that was killed. That is what stops a compaction or a repair from
        quietly resurrecting a claim somebody recorded a reason for killing.
        """
        killed = self.killed_ids(topic) | drop
        path = self.topic_path(topic)
        kept: list[str] = []
        for meta, heading, body in parse_blocks(self._read(path)):
            ident = meta.get("id") if meta.get("kind") == "entry" else meta.get("target")
            if ident in killed:
                continue
            block_meta = json.dumps(meta, ensure_ascii=False, sort_keys=True)
            block = f"## {heading}\n\n<!-- said-who {block_meta} -->\n"
            if body.strip():
                block += f"\n{body.strip()}\n"
            kept.append(block + "\n")

        note = (
            "<!-- said-who "
            + json.dumps(
                {
                    "schema": "said-who/1",
                    "kind": "tombstone",
                    "topic": topic,
                    "killed": sorted(killed),
                    "archive": str(self.archive_path(topic)),
                },
                sort_keys=True,
            )
            + " -->\n\n"
        )
        tmp = path.with_suffix(".md.rewriting")
        tmp.write_text(note + "".join(kept), encoding="utf-8")
        os.replace(tmp, path)

    # ------------------------------------------------------------- checking

    def missing_from_journal(self, topic: str) -> list[Entry]:
        known = self.known_ids(topic)
        return [e for e in self.entries(topic) if e.id not in known]

    def resurrected(self, topic: str) -> list[Entry]:
        killed = self.killed_ids(topic)
        return [e for e in self.entries(topic) if e.id in killed]

    def cited(self, topic: str | None = None) -> list[Entry]:
        return [e for e in self.entries(topic) if e.src is SourceClass.HUMAN and e.cite]
