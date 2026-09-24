"""said-who: a memory store that refuses to save a claim it cannot substantiate.

An entry saying a person decided something is written only when a locator, a
literal quote and a transcript the harness wrote all agree. It proves that the
cited message exists, that the harness recorded it as a human turn, and that it
contains the quoted words. It does not prove the entry is a fair reading of that
message, and it says so wherever it can be read.
"""

# Read from the installed package rather than repeated here. A hand written copy
# drifts the moment a release is cut, and a tool that misreports itself is exactly
# the kind of unsourced claim this one exists to refuse.
try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _installed_version

    try:
        __version__ = _installed_version("said-who")
    except PackageNotFoundError:  # running from a source tree, not installed
        __version__ = "unknown (not installed)"
except ImportError:  # pragma: no cover
    __version__ = "unknown"

from said_who.entries import TIERS, Entry, SourceClass, Verdict, VerdictRecord
from said_who.refusals import Refused

__all__ = [
    "TIERS",
    "Entry",
    "Refused",
    "SourceClass",
    "Verdict",
    "VerdictRecord",
    "__version__",
]
