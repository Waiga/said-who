# said-who

A memory store for AI agents that refuses to save a claim about what a person decided unless it can
point at a real message that person actually typed, and quote their words back.

It supports **Claude Code and nothing else**. Claude Code writes its transcripts to disk and stamps
every turn with an origin the agent does not author, which is the only reason any of this can be
checked. For any other harness the entry is stored as hearsay and labelled as hearsay. Everything
runs on your machine: no network, no database, no daemon, no account.

## Why

An agent wrote a business target into a decision log that the person it was attributed to had never
said. Four further agents read it, believed it, and copied it into three more files. It was not
stale. It was hours old and invented. A human noticed and killed it.

No expiry rule catches that, because the entry was new. No review cadence catches it, because every
reader downstream had a plausible looking source. The only thing that catches it is provenance the
agent making the claim cannot write.

A message id is a string, and an agent can invent one. A timestamp is a string, and an agent can
invent one. What an agent cannot easily invent is the literal text a person typed, in a transcript
the harness wrote, in a turn the harness marked as human. So an entry claiming a person decided
something needs three things at once: a locator, a literal quote, and a transcript on disk where
both hold. If any of the three fails, the write is refused. Not flagged. Refused.

## What it does not prove

It proves the cited message exists, that the harness recorded it as a human turn, and that it
contains the quoted words.

It does not prove the entry is a fair reading of that message. An agent can quote six real words of
yours and attach a conclusion you never reached. That gap is irreducible, and it closes only by
quoting enough. This makes forgery expensive. It does not make misinterpretation impossible.

It also proves nothing at all outside Claude Code, and it says so on every entry it cannot check.

## Install

```
pip install said-who
```

## Use

```
said-who add targets --title "the monthly target" --src human \
  --cite 4f3c1a22-0b77-4a10-9f21-77bd2c9b1e04#0e191373-9c11-4d2a-b0d5-6a1f2e77c3aa \
  --quote "200k a month by the end of october" <<'BODY'
The target for the quarter is the one in the cited message.
BODY
```

The body arrives on stdin, because that is how an agent will actually use it.

Without a citation, the same entry is refused:

```
REFUSED [NO_CITATION] --src human needs --cite.
  A claim that a person decided something needs a locator and a quote, and the quoted
  words have to be in a turn the harness recorded as human.
```

The six commands:

```
said-who add <topic> --title T --src CLASS [--cite LOC --quote Q] [--tier T] [--review DATE]
said-who list [<topic>] [--src CLASS] [--due]
said-who verify [<topic>]
said-who review
said-who verdict <topic> <id> --confirm|--revise|--kill --by WHO [--reason R]
said-who doctor
```

`verify` re-resolves every citation in the store and reports which no longer hold, which is how you
find out that a store carried to another machine has no proof behind it any more.

## Source classes

Every entry declares one.

| class | means | extra requirement |
|---|---|---|
| `measured` | something was run and can be run again | none |
| `derived` | reasoned from other entries | none |
| `external` | a third party system said it | none |
| `human` | a person decided it | locator, quote, and a verified transcript |
| `human-unverified` | attributed to a person, not citable | none, and permanently flagged as hearsay |

## The two refusals

**One, the citation check.** `--src human` without a resolvable, verified citation is refused. The
quote is compared literally, after whitespace is collapsed and case is ignored. It is deliberately
not fuzzy, because a paraphrase is not somebody's own words.

**Two, the laundering check.** A body filed under `measured`, `derived` or `external` may not assert
that a person approved, decided or confirmed something. Without this, refusal one buys nothing: the
same fabrication is simply filed as `derived` and the store is no better off.

The laundering check is text matching, and it is **a speed bump on the obvious path, not a
guarantee**. A determined agent beats it by writing around it. It also has a false positive class it
cannot avoid, because it cannot tell a person from a product name, so a sentence like "Gradle
decided to rebuild everything" is refused although nobody approved anything. The cost is a rephrase.
No claim is made here that it is airtight, and the package's own test suite records both the cases
it catches and the one it gets wrong.

## Writing, and why it is append only

Concurrent agents are the normal case, not the edge case, and a memory file written by two of them
at once loses entries silently.

Measured on this machine by `tests/test_concurrency.py`, which implements the defective writer as
well as the real one. Twenty writers, each a separate process, started together, each adding one
distinct entry to one topic file. The naive writer reads the file, spends 0.4 seconds building the
new content, then writes the whole file back. The real writer appends under an exclusive `flock`.

| writer | entries surviving out of 20 |
|---|---|
| naive read, modify, write | 1 |
| append under a lock | 20 |

Three consecutive runs gave the same figures. Rerun it with `pytest tests/test_concurrency.py`.

Every accepted entry is also mirrored to an append only JSONL journal that is never rewritten, so
the record survives anything that later happens to the readable file.

## Expiry: a verdict, never a quiet deletion

Different claims go stale for different reasons, so one clock is wrong.

| tier | review after | for |
|---|---|---|
| `permanent` | never | how a person works, house rules, prohibitions |
| `doctrine` | 180 days | engineering and design rules, the default |
| `situation` | 60 days | org state, ownership, what tool exists |
| `number` | 30 days | any figure |
| `commitment` | its own date | an open loop with a real deadline |

When something is due it needs a verdict: confirm, revise or kill. A kill requires a reason and an
author. Killed entries move to an archive file with their reason, the journal keeps the original
permanently, and every rebuild refuses to put a killed entry back.

Killing a claim is a recorded decision with an author, exactly like making one.

## Storage

Plain files in a directory you choose, set with `--store` or `SAID_WHO_STORE`, defaulting to
`~/.said-who`.

```
<store>/<topic>.md                   the readable log
<store>/journal/<topic>.ndjson       append only, never rewritten
<store>/archive/<topic>.retired.md   killed entries, with their reason
```

Human readable, greppable, and friendly to git. A memory that needs a server running is a memory
that is silently empty when the server is down.

The lock is POSIX `flock`, so this runs on macOS and Linux. Windows is not supported and is not
tested, and claiming it without testing it would be the same kind of unearned claim the tool exists
to refuse.

## Adding a harness

One function, fixed shape, documented in `said_who/harness/__init__.py`:

```python
def resolve(locator: str, root: pathlib.Path | None = None) -> Turn
```

It must set `human` to True only when the harness itself recorded that turn as coming from a
person. If the flag is written by the agent that also writes the memory entry, the adapter proves
nothing.

No adapter ships for a harness that has not been run against that harness's real transcripts. One
verified harness is worth more than six unverified ones.

## Proof

The suite is the tool's own evidence. It is not enough on its own, so this section reports what
happened when the tool was pointed at real transcripts it did not write.

### Run against a real corpus, 24 September 2026

893 Claude Code transcript files, 95,131 records, 578 MB. Counts only are recorded here. No message
text, no quotes and no private content left the machine, and none of it is in this repository.

| what was tried | n | result |
|---|---|---|
| transcript lines the reader could not parse | 95,131 read | 0 |
| human turns found | 1,313 | resolved with text 1,311, resolved with empty text 2, failed 0 |
| a genuine quote from a genuine human turn | 400 sampled | accepted 377, wrongly refused 0, no usable text 23 |
| an invented quote against a real human turn | 200 | refused 200, wrongly accepted 0 |
| a real turn the harness did not mark human | 200 | refused 200, wrongly accepted 0 |
| an invented locator | 200 | refused 200, wrongly accepted 0 |
| a real quote filed as `derived` with an approval claim in the body | 93 | refused 93, wrongly accepted 0 |

Resolving all 1,313 human turns took 9.1 seconds.

### What the real corpus found that the tests did not

**Short turns are ordinary.** Of 1,313 real human turns, 4.4 per cent carried one word or none and
22.2 per cent carried two to five. The fixtures were all full sentences, so no test could have
raised this.

It matters because a one word quote passes the citation check and proves very little. An agent
guessing "yes", "go" or "approved" would land it. The check reported success and the success was
worth less than it looked, which is the failure this tool exists to prevent, sitting inside the tool
itself.

The fix is not a refusal, because refusing would throw away real decisions that were genuinely made
in one word. A quote under three words is stored and the writer is told, in plain words, that the
evidence is thin and to quote more where the turn allows it. `WEAK_QUOTE_WORDS` in `refusals.py`
carries the threshold and the reason.

### The rest of the evidence, all repeatable with `pytest`

* 142 tests, including one per refusal and the five forgery attempts in `tests/test_forgery.py`
* the concurrency figures above, with the defective writer implemented and actually run, not asserted
* three guards were removed on purpose and the named tests watched to fail, then restored and watched
to pass: the citation check, the laundering check, and the weak quote notice

### What is still unproven

The corpus above is one person's transcripts from one machine. It is broad enough to have found a
real defect and it is not a sample of how other people use Claude Code. Nobody outside this
repository has run this tool against their own transcripts yet, and nothing here should be read as
evidence that it survives contact with a setup that is not this one.

## Built with an AI assistant

This package was written by Claude Code working to a written design. The commit trailers are the
evidence: every commit carries a `Co-Authored-By` line naming the model. The design, the decisions
and the responsibility are Waiga Arya's.

## Licence

MIT. See `LICENSE`.
