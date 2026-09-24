# said-who: design

Written 24 September 2026 by Jaan, under Waiga's instruction to start something new, choose it,
build it, test it and publish it.

## 1. What it is, in one sentence

A memory store for AI agents that refuses to save a claim about what a person decided unless it can
point at a real message that person actually typed, and quote their words back.

## 2. Why it exists

On 23 August 2026 an agent wrote a business target into Waiga Arya's decision log that he had never
said. Four further agents read it, believed it, and propagated it into three more files. It was not
stale. It was hours old and invented. A human noticed and killed it.

No expiry rule catches that, because the entry was new. No review cadence catches it, because every
reader downstream had a plausible looking source. The only thing that catches it is provenance that
cannot be written by the agent making the claim.

That is the whole tool.

## 3. The core idea, stated so it can be attacked

**A citation is only worth something if forging it requires something the forger does not have.**

A message id is a string. An agent can invent one. A timestamp is a string. An agent can invent one.
What an agent cannot easily invent is the literal text a human typed, in a transcript the harness
wrote, stamped by the harness as a human turn.

So `said-who` requires three things together for any entry claiming a human decided something:

1. a locator for the message,
2. a literal fragment of that message, quoted,
3. a transcript, found on disk, in which the harness itself marked that turn as human and which
   contains the quoted fragment.

If any of the three fails, the write is refused. Not flagged. Refused.

## 4. What it does NOT prove, stated up front

This is load bearing and goes in the README, not only here.

It proves the cited message exists, that the harness recorded it as a human turn, and that it
contains the quoted words. **It does not prove the entry is a fair reading of that message.** An
agent can quote six real words of yours and attach a conclusion you never reached. That gap is
irreducible and it closes only by quoting enough. The tool makes forgery expensive; it does not make
misinterpretation impossible.

It also does not verify anything outside a supported harness. See section 6.

## 5. Source classes

Every entry declares one, with `--src`:

| class | means | extra requirement |
|---|---|---|
| `measured` | something was run and can be re-run | none |
| `derived` | reasoned from other entries | none |
| `external` | a third party system said it | none |
| `human` | **a person decided it** | locator + quote + verified transcript |
| `human-unverified` | attributed to a person, not citable | none, and permanently flagged as hearsay |

Two refusals, not one:

1. `--src human` without a resolvable, verified citation is refused.
2. **A body that asserts a person approved, decided or confirmed something under a weaker class is
   also refused.** This is the laundering check and it matters more than the first. Without it an
   agent simply files the same fabrication as `derived` and nothing has been gained.

The laundering check is a text rule and text rules are beatable. It is a speed bump on the obvious
path, it is documented as exactly that, and it is not presented as airtight.

## 6. Harness support, and the honest scope

**Version one supports Claude Code and nothing else.** Claude Code writes JSONL transcripts under
`~/.claude/projects/` and stamps turns with an origin the agent does not author. That is the only
place this tool can currently do what it claims.

For every other harness it stores the entry as `human-unverified` and says so. It does not pretend.

Adding a harness is one function with a fixed shape: given a locator, return the turn's text and
whether the harness itself marked it human. The interface is documented. No adapter ships for a
harness that has not been tested against real transcripts.

This is the same discipline as the eight-tools article: ship what can be proved, name the gap in the
first paragraph, do not pad the claim.

## 7. Writing, and why it is append only

Concurrent agents are the normal case, not the edge case. Measured on the private predecessor: two
writers doing naive read-modify-write on one file lost about 90 per cent of entries under
contention, 2 of 20 surviving. Through an append-only writer under an exclusive lock, 20 of 20
survived.

So: append only, under `flock`, with a content hash for deduplication, and every accepted entry
mirrored to an append-only JSONL journal that is never rewritten.

## 8. Expiry, and why nothing is deleted

Different claims go stale for different reasons, so one clock is wrong. Tiers, set with `--tier`:

| tier | review after | for |
|---|---|---|
| `permanent` | never | how a person works, house rules, prohibitions |
| `doctrine` | 180 days | engineering and design rules (default) |
| `situation` | 60 days | org state, ownership, what tool exists |
| `number` | 30 days | any figure |
| `commitment` | its own date | an open loop with a real deadline |

When something is due, it needs a **verdict**, not a deletion: confirm, revise, or kill. A kill
requires a reason and an author. Killed entries move to an archive file with their reason; the
journal keeps the original permanently; compaction and reconciliation both refuse to resurrect them.

**Killing a lesson is a recorded decision with an author, exactly like making one.**

## 9. Commands

```
said-who add <topic> --title T --src CLASS [--cite LOC --quote Q] [--tier T] [--review DATE]
said-who list [<topic>] [--src CLASS] [--due]
said-who verify [<topic>]          re-resolve every citation, report which no longer hold
said-who review                    what is due for a verdict
said-who verdict <topic> <id> --confirm|--revise|--kill --by WHO [--reason R]
said-who doctor                    is the harness adapter working, is the store consistent
```

Body text arrives on stdin, which is how an agent will actually use it.

## 10. Storage

Plain files, human readable, greppable, git friendly. One markdown file per topic, one JSONL journal
per topic, one archive file per topic. No database, no daemon, no network. The store is a directory
the user chooses.

A memory that needs a server running is a memory that is silently empty when the server is down.

## 11. Boundaries

**In:** the five source classes, both refusals, the Claude Code adapter, append-only writing with
the journal, the tiers, verdicts and archive, and the six commands.

**Out, deliberately:** anything about north stars, directors, decision logs, org state, Postgres,
rendered replicas, or any concept from the private predecessor that only makes sense inside one
person's setup. Also out: embeddings, similarity search, and retrieval ranking. This is a store with
a conscience, not a retrieval engine, and every retrieval feature added before the conscience is
proven makes the conscience harder to audit.

## 12. How it gets proved before publication

Waiga's standing rule for this portfolio: publish only what has been run against real material it
did not author, not merely against its own tests.

So, in order, and all three must pass:

1. **Its own suite**, including a test for every refusal, and a concurrency test that puts the real
   defect back: run the naive read-modify-write writer and watch entries disappear, then run the
   real writer and watch them survive.
2. **A forgery suite.** For each of these the tool must refuse: an invented locator; a real locator
   with a quote that is not in it; a real locator pointing at a turn the harness did not mark human;
   a real human turn quoted correctly but filed under a weaker class with an approval claim in the
   body; and a killed entry offered again.
3. **Real transcripts and a real store, neither authored by this tool.** Run against Waiga's actual
   Claude Code transcripts and his actual memory files. **Only counts, rates and failure classes are
   recorded. No content, no quotes, no business facts leave the machine.** The corpus manifest
   carries the counts and the date and nothing else.

Step 3 is run by Jaan directly and not delegated, because the material is private.

## 13. What the README must say

1. What it does, in the first two lines.
2. That it supports Claude Code only, in the first paragraph.
3. What it cannot prove, before any example of what it can.
4. The measured concurrency figures with their method.
5. The laundering check described as a speed bump, not a guarantee.
6. That it was built with an AI assistant, with the commit trailers as the evidence.

No punctuation dashes anywhere.

## 14. Risks, named

- **Agent memory is a crowded field.** The differentiator is narrow and must stay narrow: this is
  the only one that refuses a write it cannot substantiate.
- **The laundering check is text matching.** Beatable by a determined agent. Documented as such.
- **One harness is a small audience.** Accepted, on the grounds that a verified claim for one
  harness is worth more than an unverified claim for six.
- **The tool could be wrong about the transcript format**, which would make it refuse valid entries
  or accept invalid ones. This is what step 3 of section 12 exists to find, and it is exactly the
  class the eight-tools article says only real files catch.
