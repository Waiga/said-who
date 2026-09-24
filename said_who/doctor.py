"""Is the harness adapter working, and is the store consistent.

The failure this tool is built against is a quiet one, so the checks that matter
most here are the ones that go wrong without anybody noticing: an adapter pointed
at a transcript directory that does not exist, a live file holding an entry the
journal never saw, and a killed entry that has found its way back in.
"""

from __future__ import annotations

from dataclasses import dataclass

from said_who.harness import DEFAULT_HARNESS, resolver_for, supported
from said_who.harness import claude_code as claude_code_adapter
from said_who.store import Store

OK = "ok"
WARN = "warn"
FAIL = "fail"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def run(store: Store, harness: str = DEFAULT_HARNESS) -> list[Check]:
    checks: list[Check] = []

    # The store itself.
    if not store.root.exists():
        checks.append(
            Check("store", WARN, f"{store.root} does not exist yet. The first add creates it.")
        )
    elif not store.root.is_dir():
        checks.append(Check("store", FAIL, f"{store.root} is not a directory."))
    else:
        topics = store.topics()
        checks.append(
            Check("store", OK, f"{store.root} holds {len(topics)} topic(s): {', '.join(topics)}")
            if topics
            else Check("store", OK, f"{store.root} is empty.")
        )

    # The adapter.
    resolver = resolver_for(harness)
    if resolver is None:
        checks.append(
            Check(
                "adapter",
                FAIL,
                f"No adapter for {harness!r}. Verified harnesses: {', '.join(supported())}.",
            )
        )
    else:
        checks.append(Check("adapter", OK, f"{harness} adapter loaded."))

    if harness == "claude-code":
        root = claude_code_adapter.default_root()
        if root.is_dir():
            sessions = sum(1 for _ in root.glob("**/*.jsonl"))
            checks.append(
                Check("transcripts", OK, f"{root} holds {sessions} session file(s).")
            )
        else:
            checks.append(
                Check(
                    "transcripts",
                    WARN,
                    f"{root} is not there, so no citation can be resolved on this machine.",
                )
            )

    # Consistency, per topic.
    for topic in store.topics():
        entries = store.entries(topic)
        ids = [e.id for e in entries]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            checks.append(
                Check(
                    f"topic:{topic}",
                    WARN,
                    f"{len(duplicates)} id(s) appear more than once in the live file.",
                )
            )

        missing = store.missing_from_journal(topic)
        if missing:
            checks.append(
                Check(
                    f"journal:{topic}",
                    FAIL,
                    f"{len(missing)} live entry(ies) are not in the journal. "
                    "Something wrote the file without going through this tool.",
                )
            )
        else:
            checks.append(
                Check(f"journal:{topic}", OK, f"{len(entries)} entry(ies), all journalled.")
            )

        back = store.resurrected(topic)
        if back:
            checks.append(
                Check(
                    f"killed:{topic}",
                    FAIL,
                    f"{len(back)} killed entry(ies) are back in the live file: "
                    + ", ".join(e.id for e in back),
                )
            )

    return checks


def worst(checks: list[Check]) -> str:
    if any(c.status == FAIL for c in checks):
        return FAIL
    if any(c.status == WARN for c in checks):
        return WARN
    return OK
