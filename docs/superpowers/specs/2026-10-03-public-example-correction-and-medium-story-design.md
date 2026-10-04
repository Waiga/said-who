# Said Who public example correction and Medium story design

Written 3 October 2026 after the current public repository, package page, project memory and
approved two track public relations design were checked again.

## 1. Objective

Correct the current Said Who public surfaces, prevent the same class of private context from
entering public examples again, publish a corrected package release, and only then publish one
Medium article about the limit of quote provenance.

The correction comes before the story. The story is held until the corrected repository and package
are live and independently verified.

## 2. The public contradiction

The current README and package description use a real business decision and a real source locator
as the usage example. The same README later says that no message text, quotes or private content
left the machine. Public tests also use the author's name and target language that can be mistaken
for current business facts.

The measured corpus may still have remained private. The public sentence is nevertheless too broad
because the example contradicts it.

A normal pull request changes the current branch. A new package release changes the default package
page. Neither action erases earlier Git history or the first package release. No completion claim
may say that the earlier material was erased.

## 3. Scope

### Current repository correction

1. Replace the README usage example with neutral fictional data and label it fictional.
2. Add a correction note near the top of the README. It must distinguish corrected current surfaces
   from historical artifacts that remain public.
3. Replace every locator and locator prefix derived from private material in `tests/conftest.py` with
   new fictional values.
4. Replace personal attribution and target language in public test fixtures with neutral fictional
   people, decisions and dates.
5. Update the original design document where it names private working context, while preserving the
   reason the tool exists.
6. Narrow the corpus statement so it says that no message text, quotes or private content from the
   measured corpus left the machine.
7. Add one regression test that checks the public example, fixture and design surfaces without
   embedding the removed material in the test.
8. Limit the new source archive to the package, build metadata, README and licence. Public tests,
   design files and workflows do not belong in an installable source archive.
9. Add a package job to continuous integration. It builds, checks and audits the exact wheel and
   source archive before merge.
10. Bump the package version from 0.1.0 to 0.1.1.
11. Add a release guard that refuses to publish a tag whose commit is not the current main commit.
12. Use Waiga's GitHub no reply address for every new commit. The personal email address in existing
   commit metadata remains a historical exposure and is not corrected by this work.

### Repository safeguards

Before release, protect main with pull requests, all six existing matrix checks, current branch
enforcement, conversation resolution, administrator enforcement, and no force push or deletion.
Zero approving GitHub reviews remains acceptable because Waiga is the only collaborator, but an
independent agent review is still required as a procedural gate.

Protect the `pypi` environment with Waiga as required reviewer, no administrator bypass, and a `v*`
tag deployment policy. Self review remains enabled because Waiga is the sole collaborator and must
approve the release himself. The environment setting therefore does not prove independent account
approval.

Verify the exact PyPI trusted publisher binding before any tag is pushed: owner `Waiga`, repository
`said-who`, workflow `release.yml`, and environment `pypi`.

### Corrected package release

Build and inspect both the wheel and source archive. The current source tree, README, public tests,
design document, wheel metadata and source archive must pass the public context scan. Publish 0.1.1
through the existing trusted publishing workflow from an annotated tag on the exact protected main
commit.

Verify the rendered 0.1.1 page, both release files, trusted publishing provenance, exact publishing
commit and a fresh installation from the public package index. After 0.1.1 is verified, yank 0.1.0
with a short reason directing readers to 0.1.1. Yanking is reversible and discourages ordinary
selection. It does not delete the release, and an exact version request can still retrieve it.

The source archive audit uses an allowlisted manifest and verifies that `tests`, `docs` and `.github`
are absent. The wheel audit reads its metadata and package files. The same audit runs in pull request
continuous integration and again in the release workflow before publishing.

## 4. Regression guard

The guard covers `README.md`, the original public design document, `tests/conftest.py`,
`tests/test_refusals.py` and `tests/test_forgery.py`.

It must prove these conditions:

1. The README labels its usage block as fictional.
2. The README usage block contains no UUID shaped locator.
3. Test fixtures do not contain the package author's real name.
4. Test fixtures do not contain compact business values such as a number followed by `K` or a
   quarter followed by a year.
5. The design and README scope privacy claims specifically to the measured corpus.

The test must first fail against the current public files. After the correction it must pass. A
separate mutation check inserts a synthetic forbidden sentinel, watches the test fail for the
expected reason, restores the file, and watches it pass again.

The guard is not a privacy proof. It protects the exact public surfaces and failure classes that
caused this correction.

The measured corpus aggregates remain intentionally public because they are the evidence for the
published test result. They must be labelled as aggregate measurements from one person's machine.
No source record, message text, quote, locator or private business fact may accompany them. This is
a deliberate retention decision, not an assumption that aggregate data is automatically harmless.

The public guard must use structural rules and synthetic sentinels. It must not contain the removed
target, locator, locator prefix or a reversible encoding of them.

## 5. Medium article

### Thesis

A fresh AI memory can be false. Said Who reduces that risk by refusing a decision entry presented
as human sourced unless an independently recorded transcript confirms the cited words. It labels an
unsupported harness as hearsay. Even then, a real quote can support an unfair interpretation.

This is track one. It is about inspectable work, a public correction and the boundary of the tool.
It is not a company story.

### Working title

**A fresh AI memory can still be false**

### Structure

1. Open with the correction and link only the corrected repository and corrected package page.
2. Explain that a fabricated business claim entered a durable record and was copied by other
   agents. Do not reveal the underlying business detail.
3. Explain why freshness and review schedules cannot repair false provenance at creation.
4. Explain the verified human source class, the hearsay class and refusal behaviour in plain
   language.
5. State what the tool proves and what it cannot prove about interpretation.
6. Explain that real corpus testing exposed the weakness of very short quotations that the original
   fixtures missed.
7. State that the public example itself exposed private working context, what was corrected, what
   automated guard was added and what remains in historical artifacts.
8. Close with the single supported harness boundary and the absence of evidence from another
   person's setup.

### Required correction paragraph

The opening must say, in substance:

> Before publishing this story, I found that the public usage example in Said Who contained details
> drawn from a private working context. I replaced the example and related test fixtures with
> fictional data, narrowed the privacy statement to the measured corpus, and added a guard against
> the same class of leak. The current repository and package page are corrected. Earlier repository
> history and the first package release remain public.

The final wording may improve for rhythm, but it may not weaken any fact or add a claim of erasure.

### Forbidden article material

The article, title, subtitle, preview, image text and captions must not include any private amount,
date, deadline, objective, quotation, locator, file location, private name, company operating fact,
customer, vendor, supplier, partner, brand market map or internal record.

It must not claim that the entire private corpus was exposed, that old artifacts were erased, that
the tool proves intent or fairness, that unsupported harnesses are verified, or that outside
adoption exists.

No generated cover image is needed. The corrective source change is the evidence, and a decorative
image would add no proof.

The article must not quote, screenshot or deep link to the old release, old commit, correction pull
request or source diff. Those surfaces remain public, but the article must not make the removed
material easier to discover.

## 6. Publication and discovery sequence

1. Merge and release the corrected current surfaces.
2. Verify the public correction from signed out reader views.
3. Draft and independently challenge the Medium article against the corrected public sources.
4. Publish the Medium article under Waiga's current instruction to close this exact loop.
5. Add the published article to the GitHub profile writing list and the personal site writing list
   through their normal protected pull request paths.
6. Verify that Medium, the GitHub profile, the tool repository, the package page and the personal
   site resolve to the intended current surfaces.

No LinkedIn, Substack or The Private Saloon action is in scope.

## 7. Final evidence gate

The correction and story close only when all of these are true:

1. The exact pull request head passes the complete test and lint suite.
2. The regression test has a recorded fail, pass, mutation fail and restored pass cycle.
3. The corrected tree, wheel and source archive pass the public context scan.
4. The pull request has no unresolved comments after the required reviewer window.
5. The protected main commit equals the annotated release tag target.
6. The publish run succeeds through trusted publishing and the protected environment.
7. The current package page renders only fictional examples and scoped privacy wording.
8. A fresh package installation and command check succeed.
9. Every article fact has a public source opened again on the final review day.
10. Every article figure carries its denominator and scope, or is removed.
11. The final article passes scans for private context and punctuation dashes.
12. An independent reviewer reads the evidence before reading the article and returns GO.
13. The article and its owned discovery links are verified after publication.
14. Project memory and live state record what changed, what remains historically accessible and
    what was not touched.

## 8. Non goals

This work does not rewrite public Git history, delete 0.1.0, claim confidentiality was restored, add
another harness, change Said Who behaviour, publish a company story, or take any action on LinkedIn,
Substack or The Private Saloon.

Jaan's residual risk decision under Waiga's instruction to close this loop is to leave Git history
intact, leave the `v0.1.0` tag intact, publish 0.1.1, and then yank rather than delete 0.1.0. History
rewriting would not remove PyPI artifacts or every clone and cache, while damaging existing release
provenance. Deletion would be permanent and still would not guarantee erasure. The closeout must
name old Git history, the old tag, PyPI 0.1.0 files, mirrors, caches, clones and immutable metadata
datasets as potentially retrievable.
