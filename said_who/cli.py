"""Command line entry point.

Body text arrives on stdin, because that is how an agent will actually use this.
"""

from __future__ import annotations

import argparse
import json
import sys

from said_who import __version__
from said_who import doctor as doctor_module
from said_who.entries import TIERS, SourceClass, Verdict, VerdictRecord
from said_who.gate import accept, due, effective_review, recheck
from said_who.harness import DEFAULT_HARNESS, supported
from said_who.refusals import Refused
from said_who.store import Store

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_PROBLEM = 2

DESCRIPTION = (
    "A memory store that refuses to save a claim about what a person decided "
    "unless it can point at a real message that person typed."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="said-who", description=DESCRIPTION)
    parser.add_argument(
        "--store",
        default=None,
        help="the store directory (default: $SAID_WHO_STORE, else ~/.said-who)",
    )
    parser.add_argument("--version", action="version", version=f"said-who {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="write one entry, body on stdin")
    add.add_argument("topic")
    add.add_argument("--title", required=True)
    add.add_argument(
        "--src",
        required=True,
        choices=[c.value for c in SourceClass],
        help="where the claim came from",
    )
    add.add_argument("--cite", help="locator of a human turn, required by --src human")
    add.add_argument("--quote", help="literal words from that turn, required by --src human")
    add.add_argument("--tier", default="doctrine", choices=sorted(TIERS))
    add.add_argument("--review", help="review date, YYYY-MM-DD, required for a commitment")
    add.add_argument(
        "--harness",
        default=DEFAULT_HARNESS,
        help=f"which harness wrote the cited transcript (verified: {', '.join(supported())})",
    )
    add.add_argument("--body", help="body text, when stdin is not convenient")

    listing = sub.add_parser("list", help="what is in the store")
    listing.add_argument("topic", nargs="?")
    listing.add_argument("--src", choices=[c.value for c in SourceClass])
    listing.add_argument("--due", action="store_true", help="only what needs a verdict")
    listing.add_argument("--json", action="store_true")

    verify = sub.add_parser("verify", help="re-resolve every citation")
    verify.add_argument("topic", nargs="?")
    verify.add_argument("--json", action="store_true")

    review = sub.add_parser("review", help="what is due for a verdict")
    review.add_argument("topic", nargs="?")
    review.add_argument("--json", action="store_true")

    verdict = sub.add_parser("verdict", help="confirm, revise or kill a due entry")
    verdict.add_argument("topic")
    verdict.add_argument("id")
    group = verdict.add_mutually_exclusive_group(required=True)
    group.add_argument("--confirm", action="store_true")
    group.add_argument("--revise", action="store_true")
    group.add_argument("--kill", action="store_true")
    verdict.add_argument("--by", required=True, help="who gave this verdict")
    verdict.add_argument("--reason", help="why, required for a kill")

    doctor = sub.add_parser("doctor", help="is the adapter working, is the store consistent")
    doctor.add_argument("--harness", default=DEFAULT_HARNESS)
    doctor.add_argument("--json", action="store_true")

    return parser


def _body(args) -> str:
    if getattr(args, "body", None):
        return args.body
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def cmd_add(args, store: Store) -> int:
    result = accept(
        store,
        topic=args.topic,
        title=args.title,
        body=_body(args),
        src=args.src,
        tier=args.tier,
        review=args.review,
        cite=args.cite,
        quote=args.quote,
        harness=args.harness,
    )
    for notice in result.notices:
        print(f"NOTICE {notice}", file=sys.stderr)
    entry = result.entry
    if result.status == "DUPLICATE":
        print(f"already stored as {entry.id}, nothing written")
        return EXIT_OK
    review = entry.review or "never"
    print(f"stored {entry.id} in {entry.topic} as {entry.src.value}, review {review}")
    return EXIT_OK


def _entry_row(entry, review: str | None) -> str:
    bits = [entry.id, entry.src.value, entry.tier, f"review {review or 'never'}"]
    if entry.cite:
        bits.append(f"cite {entry.cite}")
    if entry.downgraded_from:
        bits.append(f"downgraded from {entry.downgraded_from}")
    return f"{entry.dated}  {entry.title}\n  " + "  ".join(bits)


def cmd_list(args, store: Store) -> int:
    entries = due(store, args.topic) if args.due else store.entries(args.topic)
    if args.src:
        entries = [e for e in entries if e.src.value == args.src]
    if args.json:
        print(
            json.dumps(
                [dict(e.meta(), title=e.title, review=effective_review(store, e)) for e in entries],
                indent=2,
                ensure_ascii=False,
            )
        )
        return EXIT_OK
    if not entries:
        print("nothing stored")
        return EXIT_OK
    for entry in entries:
        print(_entry_row(entry, effective_review(store, entry)))
    print(f"\n{len(entries)} entry(ies)")
    return EXIT_OK


def cmd_verify(args, store: Store) -> int:
    results = recheck(store, args.topic)
    broken = [r for r in results if not r.holds]
    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2, ensure_ascii=False))
        return EXIT_REFUSED if broken else EXIT_OK
    if not results:
        print("no cited entries to check")
        return EXIT_OK
    for result in results:
        mark = "holds" if result.holds else f"BROKEN {result.reason}"
        print(f"{result.entry.id}  {mark}  {result.entry.title}")
    print(f"\n{len(results)} citation(s) checked, {len(broken)} no longer hold")
    return EXIT_REFUSED if broken else EXIT_OK


def cmd_review(args, store: Store) -> int:
    entries = due(store, args.topic)
    if args.json:
        print(
            json.dumps(
                [dict(e.meta(), title=e.title, review=effective_review(store, e)) for e in entries],
                indent=2,
                ensure_ascii=False,
            )
        )
        return EXIT_OK
    if not entries:
        print("nothing is due")
        return EXIT_OK
    for entry in entries:
        print(_entry_row(entry, effective_review(store, entry)))
    print(
        f"\n{len(entries)} entry(ies) need a verdict. "
        "Each one gets confirm, revise or kill, never a quiet deletion."
    )
    return EXIT_OK


def cmd_verdict(args, store: Store) -> int:
    which = Verdict.CONFIRM if args.confirm else Verdict.REVISE if args.revise else Verdict.KILL
    if which is Verdict.KILL and not args.reason:
        raise Refused(
            "NO_REASON",
            "A kill needs --reason.",
            "Killing a claim is a recorded decision with an author, exactly like making one.",
        )
    store.record_verdict(
        VerdictRecord(
            topic=args.topic,
            target=args.id,
            verdict=which,
            by=args.by,
            reason=args.reason,
        )
    )
    if which is Verdict.KILL:
        print(
            f"killed {args.id} by {args.by}. It is in {store.archive_path(args.topic)} "
            "with its reason, and the journal keeps the original."
        )
    else:
        print(f"{which.value}ed {args.id} by {args.by}, review clock restarted")
    return EXIT_OK


def cmd_doctor(args, store: Store) -> int:
    checks = doctor_module.run(store, args.harness)
    if args.json:
        print(json.dumps([c.as_dict() for c in checks], indent=2, ensure_ascii=False))
    else:
        for check in checks:
            print(f"[{check.status.upper():>4}] {check.name}: {check.detail}")
    return EXIT_PROBLEM if doctor_module.worst(checks) == doctor_module.FAIL else EXIT_OK


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "verify": cmd_verify,
    "review": cmd_review,
    "verdict": cmd_verdict,
    "doctor": cmd_doctor,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.store)
    try:
        return COMMANDS[args.command](args, store)
    except Refused as refused:
        print(refused.report(), file=sys.stderr)
        return EXIT_REFUSED
    except OSError as problem:
        print(f"said-who: {problem}", file=sys.stderr)
        return EXIT_PROBLEM


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
