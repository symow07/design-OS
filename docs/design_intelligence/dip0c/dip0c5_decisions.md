# DIP-0C5 — decisions

## D1. "Complete" is qualified, and the coverage table leads
DIP-0 is complete as an **audit framework**, a **governance framework**, a **full
inventory** and a **full font audit** — with **pilot-validated** methods for historical
designs and reusable assets.

**The materials library is not fully audited**, and the completion report says so in its
first section, before anything else. Five status labels keep the four meanings of
"complete" apart: `COMPLETE_FULL_CORPUS` · `COMPLETE_FRAMEWORK` · `PILOT_VALIDATED` ·
`NOT_RUN_AT_CORPUS_SCALE` · `DEFERRED_TO_DIP1_OR_FOLLOW_UP`.

Measured, not asserted: **DIP-0C1/C2 covered 24 of 2,305 reusable files (1.0%)** and
**DIP-0B covered 14 of 91 historical designs (15.4%)**. Those numbers are uncomfortable and
they are the truth. Two outstanding workstreams are named as **planned expansion, not
hidden omissions**.

## D2. A review item is `(review_domain, canonical_subject_id)`
Stable, content-derived, deterministic. **Queue membership never creates a review item** —
it is a separate many-to-many relation, and a decision attaches to the **item**, not the
membership. Remove a membership and the item and its decision history survive.

**Estimated decisions = unique review items.** Measured: **6,089 unique items across 6,795
queue memberships.** C4c's queues summed to 6,921 "decisions" for 4,883 files — a number
that flattered nobody and misled everybody. Never again, and a test enforces it.

## D3. The same subject in two domains is two review items
`FONT_FACE:face-x` asks *"is this typographically what we think it is?"*.
`PROVENANCE_RIGHTS_GROUP:sha+package` asks *"do we know where this copy came from?"*.
**Different decisions.** Collapsing them would let a technical confirmation imply a rights
one — the C4b defect, one layer up.

## D4. Machine recommendations and human decisions are disjoint vocabularies
13 recommendations, 14 decisions, **zero overlap**, asserted at import. A shared value would
be a doorway from "the machine thinks" to "a human decided". `machine_disposition()` raises
on every human decision; `human_decision()` raises on every machine recommendation.

**No human decision grants a permission.** Not one.

## D5. Automatic use is strictly harder than retrieval, and they never collapse
Retrieval: *a human may find this*. Automatic use: *the system may reach for it unasked*.
Automatic use requires retrieval **plus** an explicit separate grant, plus eight further
conditions. A test satisfies **every** retrieval condition and asserts automatic use is
**still denied**.

Font installation, embedding and production use are separate again, implied by neither.

## D6. Historical designs are REFERENCE MEMORY ONLY, enforced by a raise
`assert_memory_safe()` raises on exact placement coordinates, complete layouts, reusable
dieline paths, copied artwork paths, template instructions and automatic reproduction.
**A historical design teaches; it never templates.** A design library that can reproduce its
own past is a copying machine with extra steps.

## D7. Milestone records are read, never regenerated
C3/C4 have machine-readable reconciliations; **DIP-0B, C1 and C2 do not** — they predate
the convention and left markdown. That is a fact about the project's history, recorded as
such. `regenerated_any_old_artifact: false`, and a test asserts it.
