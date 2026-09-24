"""The vocabulary of the store: source classes, tiers, entries and verdicts.

Nothing in this module touches the disk. It defines what an entry is, how its
identity is computed, how it is written down and how it is read back, so that the
storage layer and the refusal layer can both be reasoned about on their own.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum

SCHEMA = "said-who/1"


class SourceClass(str, Enum):
    """Where a claim came from. Every entry declares exactly one.

    MEASURED          something was run and can be run again
    DERIVED           reasoned from other entries
    EXTERNAL          a third party system said it
    HUMAN             a person decided it, and a citation proves they said so
    HUMAN_UNVERIFIED  attributed to a person and not citable, kept as hearsay
    """

    MEASURED = "measured"
    DERIVED = "derived"
    EXTERNAL = "external"
    HUMAN = "human"
    HUMAN_UNVERIFIED = "human-unverified"

    @property
    def needs_citation(self) -> bool:
        return self is SourceClass.HUMAN

    @property
    def is_attribution(self) -> bool:
        """True when the class already says a person is being quoted."""
        return self in (SourceClass.HUMAN, SourceClass.HUMAN_UNVERIFIED)


#: The classes a fabricated human decision would be laundered through. A body
#: filed under one of these may not assert that a person approved anything.
WEAKER_CLASSES = (SourceClass.MEASURED, SourceClass.DERIVED, SourceClass.EXTERNAL)


#: Tier name to (days until review, why this interval). A claim's shelf life is set
#: by what makes it go stale, never by how important it feels, so there is more than
#: one clock.
TIERS: dict[str, tuple[int | None, str]] = {
    "permanent": (
        None,
        "How a person works, house rules, prohibitions. A timer here is pure nagging.",
    ),
    "doctrine": (
        180,
        "Engineering and design rules. Slow moving, but the ground underneath still moves.",
    ),
    "situation": (
        60,
        "Org state, ownership, what tool exists. One admin action can flip it.",
    ),
    "number": (
        30,
        "Any figure. A measured fact is true as at its measurement date and no longer.",
    ),
    "commitment": (
        0,
        "An open loop with a real deadline. Its own date is the review date, so "
        "--review is required.",
    ),
}

DEFAULT_TIER = "doctrine"


class Verdict(str, Enum):
    """What a due entry was given. A kill is a recorded decision, not a deletion."""

    CONFIRM = "confirm"
    REVISE = "revise"
    KILL = "kill"


def normalise(text: str) -> str:
    """Collapse whitespace and lowercase, for hashing and for quote matching.

    Deliberately not fuzzy. A fuzzy comparison would let a paraphrase pass as
    somebody's own words, which is the one thing this tool exists to stop.
    """
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def entry_id(topic: str, title: str, body: str) -> str:
    """Content identity. Two writers appending the same thing produce one entry."""
    payload = normalise(topic) + "|" + normalise(title) + "|" + normalise(body)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def today() -> str:
    return datetime.date.today().isoformat()


def review_date_for(tier: str, dated: str, explicit: str | None = None) -> str | None:
    """When an entry of this tier, written on this date, next needs a verdict."""
    if explicit:
        return explicit
    days = TIERS[tier][0]
    if not days:
        return None
    try:
        base = datetime.date.fromisoformat(dated)
    except ValueError:
        return None
    return (base + datetime.timedelta(days=days)).isoformat()


def valid_iso_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        return False
    return True


@dataclass
class Entry:
    """One claim, with everything needed to judge whether to believe it."""

    topic: str
    title: str
    body: str
    src: SourceClass
    tier: str = DEFAULT_TIER
    dated: str = field(default_factory=today)
    review: str | None = None
    cite: str | None = None
    quote: str | None = None
    harness: str | None = None
    downgraded_from: str | None = None
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = entry_id(self.topic, self.title, self.body)
        if self.review is None:
            self.review = review_date_for(self.tier, self.dated)

    def meta(self) -> dict:
        out = {
            "schema": SCHEMA,
            "kind": "entry",
            "id": self.id,
            "topic": self.topic,
            "date": self.dated,
            "src": self.src.value,
            "tier": self.tier,
        }
        if self.review:
            out["review"] = self.review
        if self.cite:
            out["cite"] = self.cite
        if self.quote:
            out["quote"] = self.quote
        if self.harness:
            out["harness"] = self.harness
        if self.downgraded_from:
            out["downgraded_from"] = self.downgraded_from
        return out

    def to_markdown(self) -> str:
        """The block that is appended to the topic file.

        Heading first so the file reads as a log, then one metadata line, then the
        body exactly as the caller wrote it.
        """
        meta = json.dumps(self.meta(), ensure_ascii=False, sort_keys=True)
        body = self.body.strip("\n")
        return f"## {self.dated} {self.title}\n\n<!-- said-who {meta} -->\n\n{body}\n\n"

    def is_due(self, on: str | None = None) -> bool:
        if not self.review:
            return False
        return self.review <= (on or today())

    @classmethod
    def from_meta(cls, meta: dict, title: str, body: str) -> Entry:
        src_raw = meta.get("src", "")
        try:
            src = SourceClass(src_raw)
        except ValueError:
            raise ValueError(f"unknown source class {src_raw!r}")
        return cls(
            topic=meta.get("topic", ""),
            title=title,
            body=body,
            src=src,
            tier=meta.get("tier", DEFAULT_TIER),
            dated=meta.get("date", ""),
            review=meta.get("review"),
            cite=meta.get("cite"),
            quote=meta.get("quote"),
            harness=meta.get("harness"),
            downgraded_from=meta.get("downgraded_from"),
            id=meta.get("id", ""),
        )


@dataclass
class VerdictRecord:
    """A verdict given to a due entry. It names its author, always."""

    topic: str
    target: str
    verdict: Verdict
    by: str
    reason: str | None = None
    dated: str = field(default_factory=today)

    def meta(self) -> dict:
        out = {
            "schema": SCHEMA,
            "kind": "verdict",
            "topic": self.topic,
            "target": self.target,
            "verdict": self.verdict.value,
            "by": self.by,
            "date": self.dated,
        }
        if self.reason:
            out["reason"] = self.reason
        return out

    def to_markdown(self) -> str:
        meta = json.dumps(self.meta(), ensure_ascii=False, sort_keys=True)
        head = f"## {self.dated} verdict {self.verdict.value} on {self.target}"
        reason = f"\n{self.reason.strip()}\n" if self.reason else ""
        return f"{head}\n\n<!-- said-who {meta} -->\n\nBy {self.by}.\n{reason}\n"


META_LINE = re.compile(r"^<!--\s*said-who\s+(\{.*\})\s*-->\s*$")


def parse_blocks(text: str) -> list[tuple[dict, str, str]]:
    """Read a topic file into (meta, title, body) triples.

    A block the parser cannot understand is skipped rather than raised on. These
    files are appended to by more than one process and are meant to survive a
    half written line without taking the whole store down with them.
    """
    blocks: list[tuple[dict, str, str]] = []
    title = ""
    meta: dict | None = None
    body: list[str] = []

    def flush() -> None:
        if meta is not None:
            blocks.append((meta, title, "\n".join(body).strip("\n")))

    for line in (text or "").splitlines():
        if line.startswith("## "):
            flush()
            title, meta, body = line[3:].strip(), None, []
            continue
        match = META_LINE.match(line.strip())
        if match and meta is None:
            try:
                meta = json.loads(match.group(1))
            except json.JSONDecodeError:
                meta = None
            continue
        if meta is not None:
            body.append(line)
    flush()

    out = []
    for m, t, b in blocks:
        if isinstance(m, dict) and m.get("kind") in ("entry", "verdict"):
            out.append((m, t, b))
    return out


def title_without_date(heading: str) -> str:
    """Headings carry the date as a prefix. Give back just the title."""
    parts = heading.split(" ", 1)
    if len(parts) == 2 and valid_iso_date(parts[0]):
        return parts[1]
    return heading
