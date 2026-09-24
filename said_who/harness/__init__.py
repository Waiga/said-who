"""Harness adapters: how a locator becomes a turn that can be checked.

## Adding a harness

One function, fixed shape:

    def resolve(locator: str, root: pathlib.Path | None = None) -> Turn

Given a locator string, it returns a :class:`Turn`. It must set ``human`` to True
only when the harness itself recorded that turn as coming from a person. If the
flag is written by the agent that also writes the memory entry, the adapter proves
nothing and must not be shipped.

Register it by adding the module to :data:`ADAPTERS` under the harness name.

No adapter ships for a harness that has not been run against that harness's real
transcripts. An entry naming a harness with no adapter is stored as
``human-unverified``, and said so out loud.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Turn:
    """What an adapter gives back about one cited turn.

    status  OK, or a code naming exactly what failed
    text    the turn's text when it was found, otherwise None
    human   True only when the harness itself marked this turn as human
    source  where the adapter found it, for the doctor to report
    """

    status: str
    text: str | None = None
    human: bool = False
    source: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "OK" and self.human


# Status codes an adapter may return. They are part of the interface because the
# refusal messages quote them back to the caller.
STATUS_OK = "OK"
STATUS_BAD_LOCATOR = "BAD_LOCATOR_FORMAT"
STATUS_NO_SESSION = "NO_SUCH_SESSION"
STATUS_NO_MESSAGE = "NO_SUCH_MESSAGE"
STATUS_NOT_HUMAN = "NOT_HUMAN_TURN"

from said_who.harness import claude_code  # noqa: E402  (registry needs the module)

Resolver = Callable[..., Turn]

#: Every harness this tool can verify. Version one has exactly one entry, and
#: that is the honest scope rather than a gap waiting to be filled quietly.
ADAPTERS: dict[str, Resolver] = {
    "claude-code": claude_code.resolve,
}

DEFAULT_HARNESS = "claude-code"


def resolver_for(harness: str) -> Resolver | None:
    return ADAPTERS.get(harness)


def supported() -> list[str]:
    return sorted(ADAPTERS)


__all__ = [
    "ADAPTERS",
    "DEFAULT_HARNESS",
    "STATUS_BAD_LOCATOR",
    "STATUS_NOT_HUMAN",
    "STATUS_NO_MESSAGE",
    "STATUS_NO_SESSION",
    "STATUS_OK",
    "Turn",
    "resolver_for",
    "supported",
]
