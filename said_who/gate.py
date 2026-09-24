"""The gate: what has to be true before an entry is written, and how it is rechecked.

Everything an agent asks the tool to remember arrives here first. The order is
deliberate. The cheap structural checks run before anything touches the disk, the
citation is resolved against the harness, the laundering check runs on the text,
and only then does the store get asked to write.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from said_who.entries import (
    DEFAULT_TIER,
    TIERS,
    Entry,
    SourceClass,
    review_date_for,
    today,
    valid_iso_date,
)
from said_who.harness import DEFAULT_HARNESS, Turn, resolver_for, supported
from said_who.refusals import Refused, check_citation, check_laundering, weak_quote_notice
from said_who.store import Store


@dataclass
class Accepted:
    """What happened to one offered entry."""

    status: str
    entry: Entry
    notices: list[str] = field(default_factory=list)


def _source_class(src: str) -> SourceClass:
    try:
        return SourceClass(src)
    except ValueError:
        raise Refused(
            "UNKNOWN_SOURCE_CLASS",
            f"{src!r} is not a source class.",
            "One of: " + ", ".join(c.value for c in SourceClass),
        )


def _check_tier(tier: str, review: str | None) -> None:
    if tier not in TIERS:
        raise Refused(
            "UNKNOWN_TIER",
            f"{tier!r} is not a tier.",
            "One of: " + ", ".join(TIERS),
        )
    if tier == "commitment" and not review:
        raise Refused(
            "NO_REVIEW_DATE",
            "A commitment is reviewed on its own date, so --review is required.",
            "Give the date the loop actually closes.",
        )
    if review and not valid_iso_date(review):
        raise Refused("BAD_REVIEW_DATE", f"{review!r} is not a date.", "Use YYYY-MM-DD.")


def resolve_citation(cite: str | None, harness: str) -> Turn | None:
    """Ask the named harness about a locator. None means no adapter exists."""
    resolver = resolver_for(harness)
    if resolver is None or not cite:
        return None
    return resolver(cite)


def accept(
    store: Store,
    topic: str,
    title: str,
    body: str,
    src: str,
    tier: str = DEFAULT_TIER,
    review: str | None = None,
    cite: str | None = None,
    quote: str | None = None,
    harness: str = DEFAULT_HARNESS,
    dated: str | None = None,
) -> Accepted:
    """Run every check, then write. Any failure raises Refused and writes nothing."""
    notices: list[str] = []

    if not (title or "").strip():
        raise Refused("NO_TITLE", "An entry needs a title.", "Pass --title.")
    if not (body or "").strip():
        raise Refused("NO_BODY", "An entry needs a body.", "The body arrives on stdin.")

    source = _source_class(src)
    _check_tier(tier, review)
    dated = dated or today()
    downgraded_from = None

    if source is SourceClass.HUMAN and resolver_for(harness) is None:
        # Honest scope, out loud. Storing this as human would be a claim the tool
        # cannot back, and quietly dropping the entry would be worse.
        notices.append(
            f"No adapter for harness {harness!r}, so this is stored as "
            f"human-unverified and is hearsay, not proof. "
            f"Verified harnesses: {', '.join(supported())}."
        )
        downgraded_from = SourceClass.HUMAN.value
        source = SourceClass.HUMAN_UNVERIFIED

    turn = resolve_citation(cite, harness) if source is SourceClass.HUMAN else None
    check_citation(source, cite, quote, turn)
    check_laundering(source, title, body)

    if source is SourceClass.HUMAN:
        weak = weak_quote_notice(quote)
        if weak:
            notices.append(weak)

    entry = Entry(
        topic=topic,
        title=title.strip(),
        body=body.strip(),
        src=source,
        tier=tier,
        dated=dated,
        review=review_date_for(tier, dated, review),
        cite=cite,
        quote=quote,
        harness=harness if source.is_attribution else None,
        downgraded_from=downgraded_from,
    )
    status = store.add(entry)
    return Accepted(status=status, entry=entry, notices=notices)


@dataclass
class Recheck:
    """One cited entry, re-resolved against the harness as it stands now."""

    entry: Entry
    holds: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            "id": self.entry.id,
            "topic": self.entry.topic,
            "title": self.entry.title,
            "cite": self.entry.cite,
            "holds": self.holds,
            "reason": self.reason,
        }


def recheck(store: Store, topic: str | None = None) -> list[Recheck]:
    """Re-resolve every citation in the store and report what no longer holds.

    A citation is not a one time gate. Transcripts move, sessions get cleared, and
    a store carried to another machine has no transcripts behind it at all. An
    entry whose proof has gone is worth knowing about before somebody quotes it.
    """
    out = []
    for entry in store.cited(topic):
        try:
            check_citation(
                entry.src,
                entry.cite,
                entry.quote,
                resolve_citation(entry.cite, entry.harness or DEFAULT_HARNESS),
            )
        except Refused as refused:
            out.append(Recheck(entry=entry, holds=False, reason=refused.code))
            continue
        out.append(Recheck(entry=entry, holds=True, reason="OK"))
    return out


def effective_review(store: Store, entry: Entry) -> str | None:
    """When this entry next needs a verdict, counting the verdicts it already had.

    A confirm or a revise is a judgement made on a date, so the clock restarts from
    that date rather than from the day the entry was written. Without this, an
    entry confirmed this morning is still listed as due this afternoon, and a
    review list that is wrong is a review list nobody reads.
    """
    verdict = store.last_verdict(entry.topic, entry.id)
    if verdict is None or not valid_iso_date(verdict.dated):
        return entry.review
    return review_date_for(entry.tier, verdict.dated, None)


def due(store: Store, topic: str | None = None, on: str | None = None) -> list[Entry]:
    """Entries whose review date has arrived and which still need a verdict."""
    on = on or today()
    out = []
    for entry in store.entries(topic):
        when = effective_review(store, entry)
        if when and when <= on:
            out.append(entry)
    return out
