"""Both refusals, one by one.

The laundering check gets the longer suite. It is the one that matters more: the
citation check alone is beaten by filing the same fabrication as derived, so if
only one of these two is working, this is the wrong one to have.
"""

from __future__ import annotations

import pytest

from said_who.entries import SourceClass
from said_who.gate import accept
from said_who.refusals import (
    Refused,
    check_laundering,
    find_attribution,
    quote_is_weak,
    weak_quote_notice,
)
from tests.conftest import BLOCK_TEXT, HUMAN_TEXT, HUMAN_UUID, NOTIFICATION_UUID, SESSION


def add(store, **kwargs):
    defaults = {
        "topic": "t",
        "title": "a claim",
        "body": "a body",
        "src": "measured",
    }
    defaults.update(kwargs)
    return accept(store, **defaults)


# ------------------------------------------------------- refusal one, citation


def test_human_with_a_good_citation_is_written(store, transcripts):
    result = add(
        store,
        src="human",
        title="the target",
        body="The monthly target is the one named in the cited turn.",
        cite=f"{SESSION}#{HUMAN_UUID}",
        quote="next PR",
    )
    assert result.status == "OK"
    assert result.entry.src is SourceClass.HUMAN


def test_quote_matching_collapses_whitespace_and_case(store, transcripts):
    result = add(
        store,
        src="human",
        title="whitespace",
        body="A quote is compared after whitespace is collapsed.",
        cite=f"{SESSION}#{HUMAN_UUID}",
        quote="  LET'S   WORK on   NEXT pr  ",
    )
    assert result.status == "OK"


def test_human_without_a_citation_is_refused(store, transcripts):
    with pytest.raises(Refused) as caught:
        add(store, src="human", title="no cite", body="somebody decided this")
    assert caught.value.code == "NO_CITATION"


def test_human_without_a_quote_is_refused(store, transcripts):
    with pytest.raises(Refused) as caught:
        add(store, src="human", cite=f"{SESSION}#{HUMAN_UUID}")
    assert caught.value.code == "NO_QUOTE"


def test_invented_locator_is_refused(store, transcripts):
    with pytest.raises(Refused) as caught:
        add(
            store,
            src="human",
            cite="deadbeef-0000-4000-8000-000000000000#feedface-0000-4000-8000-000000000000",
            quote=HUMAN_TEXT,
        )
    assert caught.value.code == "NO_SUCH_SESSION"


def test_malformed_locator_is_refused(store, transcripts):
    with pytest.raises(Refused) as caught:
        add(store, src="human", cite="i made this up", quote=HUMAN_TEXT)
    assert caught.value.code == "BAD_LOCATOR_FORMAT"


def test_quote_not_in_the_cited_turn_is_refused(store, transcripts):
    with pytest.raises(Refused) as caught:
        add(
            store,
            src="human",
            cite=f"{SESSION}#{HUMAN_UUID}",
            quote="reset the target to 115K",
        )
    assert caught.value.code == "QUOTE_NOT_IN_MESSAGE"


def test_a_quote_from_the_wrong_turn_is_refused(store, transcripts):
    # Both turns are real and both are human. The quote still has to be in the
    # turn that was actually cited.
    with pytest.raises(Refused) as caught:
        add(store, src="human", cite=f"{SESSION}#{HUMAN_UUID}", quote=BLOCK_TEXT)
    assert caught.value.code == "QUOTE_NOT_IN_MESSAGE"


def test_non_human_turn_is_refused(store, transcripts):
    with pytest.raises(Refused) as caught:
        add(
            store,
            src="human",
            cite=f"{SESSION}#{NOTIFICATION_UUID}",
            quote="a background task finished",
        )
    assert caught.value.code == "NOT_HUMAN_TURN"


def test_unsupported_harness_is_stored_as_hearsay_and_said_out_loud(store, transcripts):
    result = add(
        store,
        src="human",
        harness="some-other-harness",
        cite="whatever#whatever",
        quote="whatever",
    )
    assert result.status == "OK"
    assert result.entry.src is SourceClass.HUMAN_UNVERIFIED
    assert result.entry.downgraded_from == "human"
    assert any("human-unverified" in n for n in result.notices)


def test_weaker_classes_need_no_citation(store, transcripts):
    for src in ("measured", "derived", "external"):
        assert add(store, src=src, title=f"a {src} claim").status == "OK"


# ---------------------------------------------------- refusal two, laundering


LAUNDERED = [
    "Waiga approved the reset to 115K.",
    "Per Waiga, the November target moves to Q2.",
    "The reset was approved by Waiga on Friday.",
    "This follows Waiga's decision last week.",
    "She confirmed the budget yesterday.",
    "The founder agreed to the new deadline.",
    "We proceed on Anna's instruction.",
    "Rahul Mehta signed off on the invoice.",
    "The client rejected the second option.",
    "He told us to ship on Monday.",
]

INNOCENT = [
    "The suite ran clean, 47 of 47.",
    "Two writers doing read modify write lost 18 of 20 entries.",
    "The benchmark confirmed the figure after a rerun.",
    "Pytest confirmed the regression is gone.",
    "CI approved nothing, it just went green.",
    "The API returned a 403 on every write call.",
    "Prices decided by the market, not by anybody here.",
    "This module decides which adapter to use.",
]


@pytest.mark.parametrize("body", LAUNDERED)
def test_laundered_attribution_is_refused(store, body):
    with pytest.raises(Refused) as caught:
        add(store, src="derived", body=body)
    assert caught.value.code == "LAUNDERED_ATTRIBUTION"


@pytest.mark.parametrize("body", INNOCENT)
def test_ordinary_reporting_is_not_refused(store, body):
    assert add(store, src="measured", body=body).status == "OK"


def test_laundering_is_checked_in_the_title_too(store):
    with pytest.raises(Refused) as caught:
        add(store, src="external", title="Waiga approved the vendor", body="See the invoice.")
    assert caught.value.code == "LAUNDERED_ATTRIBUTION"


def test_every_weaker_class_is_checked(store):
    for src in ("measured", "derived", "external"):
        with pytest.raises(Refused):
            add(store, src=src, body="Waiga decided the reset.")


def test_hearsay_may_say_a_person_decided_something(store):
    # This is the honest filing for an uncitable attribution, so it is not
    # laundering and must not be refused.
    result = add(store, src="human-unverified", body="Waiga decided the reset, no citation.")
    assert result.status == "OK"


def test_verified_human_entry_may_say_a_person_decided_something(store, transcripts):
    result = add(
        store,
        src="human",
        body="He decided to work on the next PR.",
        cite=f"{SESSION}#{HUMAN_UUID}",
        quote="next PR",
    )
    assert result.status == "OK"


def test_the_refusal_names_the_phrase_it_caught(store):
    with pytest.raises(Refused) as caught:
        add(store, src="derived", body="The reset was approved by Waiga.")
    assert "approved by Waiga" in caught.value.message


def test_find_attribution_gives_back_the_phrase():
    assert find_attribution("Waiga approved it") == "Waiga approved"
    assert find_attribution("nothing here") is None


def test_check_laundering_is_a_no_op_for_attribution_classes():
    check_laundering(SourceClass.HUMAN, "Waiga approved", "Waiga approved")
    check_laundering(SourceClass.HUMAN_UNVERIFIED, "Waiga approved", "Waiga approved")


def test_a_capitalised_non_person_is_a_known_false_positive(store):
    # Recorded rather than hidden. The check cannot tell a person from a product
    # name, so a sentence like this one is refused although nobody approved
    # anything. The cost is a rephrase; the alternative is a guard that misses the
    # case it exists for. If this test ever fails, the check got looser, and that
    # is a decision somebody should make on purpose.
    with pytest.raises(Refused) as caught:
        add(store, src="measured", body="Gradle decided to rebuild everything.")
    assert caught.value.code == "LAUNDERED_ATTRIBUTION"


# --------------------------------------------------------- weak quote notice
#
# Found by running against 1,313 real human turns rather than by thinking about
# it. 4.4 per cent of them carried one word or none. A one word quote passes the
# citation check and proves close to nothing, because an agent can guess "yes".
# The entry is still stored. The writer is told the evidence is thin.



def test_one_word_quote_is_weak():
    assert quote_is_weak("boop")
    assert weak_quote_notice("boop") is not None
    assert "1 word" in weak_quote_notice("boop")


def test_two_word_quote_is_still_weak():
    assert quote_is_weak("go ahead")
    assert "2 words" in weak_quote_notice("go ahead")


def test_three_words_is_enough_to_stop_warning():
    assert not quote_is_weak("yes approve the split")
    assert weak_quote_notice("yes approve the split") is None


def test_empty_quote_counts_as_weak():
    assert quote_is_weak("")
    assert quote_is_weak(None)


def test_weak_quote_is_a_notice_and_never_a_refusal(store, good_cite, transcripts):
    """The entry must still be written. Refusing here would lose real decisions."""
    from said_who.gate import accept

    result = accept(
        store, "t", "short but real", "A body.", "human", cite=good_cite, quote="jaan"
    )
    assert result.entry is not None
    assert any("inside guessing range" in n for n in result.notices)
