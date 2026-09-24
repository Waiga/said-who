"""The two refusals. Everything else in this package is filing.

A write is refused, not flagged. A flag is something a downstream reader has to
notice, and the failure this tool exists to prevent is exactly a downstream reader
believing a plausible looking entry.

Refusal one, the citation check: a claim that a person decided something must come
with a locator and a quote, and the quote must be found in a turn the harness
itself recorded as human.

Refusal two, the laundering check: a body filed under a weaker class may not assert
that a person approved, decided or confirmed anything. Without this, refusal one
buys nothing, because the same fabrication is simply filed as derived.

The laundering check is text matching. It is a speed bump on the obvious path and
it is documented as exactly that, here and in the README. A determined agent beats
it by writing around it, and no claim to the contrary is made anywhere.
"""

from __future__ import annotations

import re

from said_who.entries import WEAKER_CLASSES, SourceClass, normalise
from said_who.harness import Turn

WHY_CITATION = (
    "A claim that a person decided something needs a locator and a quote, and the "
    "quoted words have to be in a turn the harness recorded as human."
)

WHY_LAUNDERING = (
    "This body says a person approved, decided or confirmed something, under a class "
    "that carries no citation. File it as --src human with --cite and --quote, or as "
    "--src human-unverified, which records it honestly as hearsay."
)


class Refused(Exception):
    """A write that was not made, with a code a caller can branch on."""

    def __init__(self, code: str, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def report(self) -> str:
        lines = [f"REFUSED [{self.code}] {self.message}"]
        if self.detail:
            lines.append(f"  {self.detail}")
        return "\n".join(lines)


# --------------------------------------------------------------- refusal one


def quote_is_in(quote: str, text: str | None) -> bool:
    """Literal containment after whitespace is collapsed, and nothing looser."""
    if not quote:
        return False
    return normalise(quote) in normalise(text or "")


def check_citation(
    src: SourceClass,
    cite: str | None,
    quote: str | None,
    turn: Turn | None,
) -> None:
    """Refuse a human claim whose citation does not hold up.

    ``turn`` is whatever the harness adapter gave back for ``cite``. Passing None
    means no adapter could be asked, which is itself a refusal.
    """
    if src is not SourceClass.HUMAN:
        return

    if not cite:
        raise Refused("NO_CITATION", "--src human needs --cite.", WHY_CITATION)
    if not quote:
        raise Refused("NO_QUOTE", "--src human needs --quote.", WHY_CITATION)
    if turn is None:
        raise Refused(
            "NO_ADAPTER",
            "No harness adapter could resolve that locator.",
            WHY_CITATION,
        )
    if turn.status.startswith("NOT_HUMAN_TURN"):
        raise Refused(
            "NOT_HUMAN_TURN",
            f"That turn exists, and the harness did not record it as human ({turn.status}).",
            "The origin stamp is written by the harness. A turn without it proves nothing.",
        )
    if turn.status != "OK":
        raise Refused(
            turn.status,
            f"The citation {cite} did not resolve ({turn.status}).",
            WHY_CITATION,
        )
    if not turn.human:
        raise Refused(
            "NOT_HUMAN_TURN",
            "The harness did not record that turn as human.",
            WHY_CITATION,
        )
    if not quote_is_in(quote, turn.text):
        raise Refused(
            "QUOTE_NOT_IN_MESSAGE",
            "Those words are not in the cited turn.",
            "The comparison collapses whitespace and ignores case. It is not fuzzy, "
            "because a paraphrase is not somebody's own words.",
        )


# --------------------------------------------------------------- refusal two

# Verbs that assert a person's consent or decision. Kept narrow on purpose: a verb
# list that swallows ordinary reporting ("the run confirmed the fix") turns the
# guard into a nuisance, and a nuisance gets switched off.
_VERBS = (
    r"(?:approved|approves|approve|decided|decides|confirmed|confirms|"
    r"authorised|authorizes|authorized|authorises|instructed|instructs|"
    r"directed|directs|mandated|mandates|agreed|agrees|consented|consents|"
    r"rejected|rejects|greenlit|green-?lit|okayed|signed\s+off|sign-?off|"
    r"chose|chooses|told|promised|promises|committed\s+to|ruled)"
)

# A subject that looks like a person. Two shapes, because a name is capitalised and
# a role is not.
_NAME = r"(?:[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?)"
_ROLE = (
    r"(?:he|she|they|the\s+(?:founder|owner|client|customer|director|ceo|cto|coo|"
    r"chair|manager|head|boss|lead|partner|investor|approver|user|reviewer|"
    r"principal|sponsor))"
)

# Capitalised words that start a sentence without naming a person. Without this the
# check fires on ordinary prose, and a guard that cries wolf is a guard that gets
# removed.
_NOT_A_PERSON = {
    "a", "all", "an", "and", "another", "any", "because", "both", "but", "ci",
    "claude", "codex", "each", "either", "everything", "github", "however", "if",
    "it", "its", "neither", "no", "none", "not", "nothing", "one", "or", "our",
    "pytest", "python", "ruff", "several", "she is", "since", "some", "that",
    "the", "their", "then", "there", "these", "they", "this", "those", "we",
    "what", "when", "which", "while", "who", "why", "you", "your", "i",
}

_PATTERNS = [
    # Somebody approved something. The lookahead keeps the passive out: in
    # "prices decided by the market" the capitalised word is the thing decided,
    # not the decider, and the pattern below handles the real passive case.
    (
        re.compile(rf"\b(?P<who>{_NAME})\s+(?:has\s+|have\s+|had\s+)?{_VERBS}\b(?!\s+by\b)"),
        True,
    ),
    (
        re.compile(
            rf"\b(?P<who>{_ROLE})\s+(?:has\s+|have\s+|had\s+)?{_VERBS}\b(?!\s+by\b)", re.I
        ),
        False,
    ),
    # Approved by somebody.
    (re.compile(rf"\b{_VERBS}\s+by\s+(?P<who>{_NAME})\b"), True),
    (re.compile(rf"\b{_VERBS}\s+by\s+(?P<who>{_ROLE})\b", re.I), False),
    # Per somebody, or somebody's decision.
    (re.compile(rf"\b[Pp]er\s+(?P<who>{_NAME})\b"), True),
    (
        re.compile(
            rf"\b(?P<who>{_NAME})'s\s+"
            r"(?:decision|call|instruction|approval|consent|sign-?off|go-?ahead|"
            r"blessing|say-?so)\b"
        ),
        True,
    ),
    (
        re.compile(
            rf"\b(?P<who>{_ROLE})'s\s+"
            r"(?:decision|call|instruction|approval|consent|sign-?off|go-?ahead|"
            r"blessing|say-?so)\b",
            re.I,
        ),
        False,
    ),
    # On somebody's instruction, with somebody's approval.
    (
        re.compile(
            rf"\b(?:on|with|under)\s+(?P<who>{_NAME})'s\s+"
            r"(?:instruction|authority|approval|consent|orders?)\b"
        ),
        True,
    ),
]


def find_attribution(text: str) -> str | None:
    """Give back the phrase that asserts a person's consent, if there is one."""
    for pattern, capitalised_subject in _PATTERNS:
        for match in pattern.finditer(text or ""):
            who = (match.group("who") or "").strip()
            if capitalised_subject and who.split()[0].lower() in _NOT_A_PERSON:
                continue
            return " ".join(match.group(0).split())
    return None


def check_laundering(src: SourceClass, title: str, body: str) -> None:
    """Refuse a person's decision filed under a class that carries no citation.

    This runs on the title and the body together. Only the weaker classes are
    checked: an entry already filed as human or human-unverified is saying openly
    what this check is looking for.
    """
    if src not in WEAKER_CLASSES:
        return
    hit = find_attribution(f"{title}\n{body}")
    if hit:
        raise Refused(
            "LAUNDERED_ATTRIBUTION",
            f"Filed as {src.value}, and the text says: {hit!r}",
            WHY_LAUNDERING,
        )
