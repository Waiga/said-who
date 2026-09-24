"""The Claude Code adapter.

Claude Code writes one JSONL file per session under ``~/.claude/projects``, one
JSON object per line. A turn typed by a person carries an ``origin`` object whose
``kind`` is ``human``. That field is written by the harness, not by the agent, and
that is the entire basis of anything this tool claims.

The shapes handled here were read from a real transcript on 24 September 2026:

* ``origin`` is an object, and ``origin["kind"]`` is ``"human"`` on a typed turn.
  The only other kind seen was ``task-notification``.
* the record carries ``uuid`` and ``sessionId``.
* ``message.content`` is sometimes a plain string and sometimes a list of blocks,
  each with a ``text`` key. Both are handled.
* a malformed line is skipped, never fatal.
"""

from __future__ import annotations

import json
import os
import pathlib
import re

from said_who.harness import (
    STATUS_BAD_LOCATOR,
    STATUS_NO_MESSAGE,
    STATUS_NO_SESSION,
    STATUS_NOT_HUMAN,
    STATUS_OK,
    Turn,
)

#: Tests and other machines point this at a different tree. Nothing else in the
#: tool ever needs to know where transcripts live.
ENV_ROOT = "SAID_WHO_CLAUDE_PROJECTS"

SESSION_RE = re.compile(r"[0-9a-fA-F-]{8,64}")
UUID_RE = re.compile(r"[0-9a-fA-F-]{8,64}")


def default_root() -> pathlib.Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return pathlib.Path(override).expanduser()
    return pathlib.Path.home() / ".claude" / "projects"


def split_locator(locator: str) -> tuple[str, str] | None:
    """A locator is ``<sessionId>#<messageUuid>`` and nothing else."""
    if not locator or "#" not in locator:
        return None
    session, _, message = locator.partition("#")
    session, message = session.strip(), message.strip()
    if not SESSION_RE.fullmatch(session) or not UUID_RE.fullmatch(message):
        return None
    return session, message


def find_session(session: str, root: pathlib.Path) -> pathlib.Path | None:
    if not root.is_dir():
        return None
    hits = sorted(root.glob(f"**/{session}.jsonl"))
    return hits[0] if hits else None


def turn_text(record: dict) -> str:
    """Pull the text out of a record whose content may be a string or blocks."""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return " ".join(parts)
    return ""


def resolve(locator: str, root: pathlib.Path | None = None) -> Turn:
    """Look one cited turn up on disk and report what the harness recorded."""
    parts = split_locator(locator)
    if parts is None:
        return Turn(STATUS_BAD_LOCATOR)
    session, message = parts

    root = root or default_root()
    path = find_session(session, root)
    if path is None:
        return Turn(STATUS_NO_SESSION)

    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return Turn(STATUS_NO_SESSION, source=str(path))

    with handle:
        for line in handle:
            line = line.strip()
            # Cheap reject first. These files run to thousands of lines and only
            # one of them can possibly match.
            if not line or f'"{message}"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # a half written line must not end the search
            if not isinstance(record, dict) or record.get("uuid") != message:
                continue
            origin = record.get("origin")
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if kind != "human":
                return Turn(
                    f"{STATUS_NOT_HUMAN}(origin={kind})",
                    text=turn_text(record),
                    human=False,
                    source=str(path),
                )
            return Turn(STATUS_OK, text=turn_text(record), human=True, source=str(path))
    return Turn(STATUS_NO_MESSAGE, source=str(path))
