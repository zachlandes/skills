# S0 interpretation log

## T1 — F23 stays local

### Spec Text

"If he would rather keep even those out of the public repo, F23 reads the file from his local skill at run time and the record keeps its hash only."

### Alternatives

Publish the two lists, or require the existing local file.

### Choice

Require an explicit banlist path at registration and feature extraction, verify its registered hash, and publish neither list nor personal notes.
The installed checker also requires that same hash when applying a promoted profile.
This preserves the registered feature without deciding to publish personal material.

### Risk: 15

The captain might prefer the lists copied into the public skill for portability.

## T2 — Preserve the legacy splitter API

### Spec Text

"Keep the current single-sentence checker working unchanged for existing callers."

### Alternatives

Add positional keys to all splitter output, or expose positional output as an opt-in using the same parser.

### Choice

Use `positional=True` on `textsplit.extract` for profile callers, leaving existing output dictionaries unchanged.
Both paths use the same extraction and sentence boundaries.

### Risk: 5

The captain likely prefers positional metadata everywhere if it does not break callers; exact dictionary compatibility favors opt-in.

## T3 — Historical outcomes and the hit floor

### Spec Text

"Records for tells rejected on fewer than 25 hits a side should say 'inconclusive on HAP-E-2'"

### Alternatives

Invalidate past kept tells too, or reclassify only non-kept records while preserving the historical keep rule.

### Choice

The promote migration reclassifies non-kept records below the floor as inconclusive and makes them askable leads.
Historical kept records remain kept.
New profile-corpus decisions use the four outcome classes and the 25-hit floor before any keep or rejection.

### Risk: 5

The captain most likely means only past rejections, as explicitly stated.

## I1 — Public source acquisition

### Spec Text

"the corpus builder with pinned revisions and hashes"

### Alternatives

Download public repositories and Stack Exchange exports automatically, or consume explicit local snapshots and verify them.

### Choice

Consume local public repository checkouts with the report's commit prefixes, resolving and recording full Git object ids and blob hashes.
Consume a public Stack Exchange Posts.xml export with an explicitly supplied SHA-256.
No network acquisition or paid generation is implicit in the builder.
The output records item ids, attribution, licences, raw and rendered hashes, and deterministic sampling and pair splits.

### Risk: 20

The captain may expect automatic public downloads; verified local snapshots keep acquisition separate from measurement.

## I2 — Co-occurrence expectation

### Spec Text

"minus the share expected from the page's own rates if tells fell independently across sentences"

### Alternatives

Treat paragraph and section questions as sentence events, or respect their eligible positional units when calculating the expectation.

### Choice

Use independent Bernoulli occurrences at each feature's own eligible units within each paragraph.
Calculate the probability of at least two distinct rhetorical members being present from their page-level rates and eligible opportunities.
List items participate in formatting features but are not prose paragraphs for rhetorical paragraph questions.

### Risk: 20

The captain may prefer mapping positional questions onto sentences before computing the expectation; respecting their denominators preserves the feature definitions.

## I3 — Window boundaries without headings

### Spec Text

"A longer page is split at headings into windows of 250 to 1,200 words (short sections merged)"

### Alternatives

Leave an oversized section unscored, or split oversized sections at paragraphs and then sentence/word boundaries.

### Choice

Prefer headings, then paragraph boundaries, then sentence boundaries, and finally words for a single oversized sentence.
Merge short sections whenever the 1,200-word ceiling permits; rebalance a short tail at sentence boundaries.
Keep source sentence ids in explanations and report the median window score as length-extrapolated rather than calibrated authorship probability.

### Risk: 10

The captain most likely expects the ceiling to apply even when a page has no headings.
