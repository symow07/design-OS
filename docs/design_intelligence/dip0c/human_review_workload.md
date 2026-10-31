# Human review workload

## Counted once — never by queue membership

| | |
|---|---|
| **unique review items** | **6,089** |
| total queue memberships | 6,795 |
| items in multiple queues | 706 |
| unique blocking items | 5,780 |
| unique HIGH-priority items | 5,688 |
| items requiring **dual control** | **3** |
| items requiring evidence before review | 5,983 |
| **ESTIMATED HUMAN DECISIONS** | **6,089** |

**Estimated decisions = unique review items.** Not the sum of queue memberships. C4c's
fourteen queues summed to **6,921 "decisions" for 4,883 files** — a number that flattered
nobody and misled everybody, because one face sits in four queues at once.

## By domain

| domain | items |
|---|---|
| `CANONICAL_MASTER_CANDIDATE` | 2 |
| `COLOR_PALETTE` | 1 |
| `FONT_FACE` | 3,966 |
| `FONT_FAMILY` | 192 |
| `FONT_SOURCE_PACKAGE` | 47 |
| `PROVENANCE_RIGHTS_GROUP` | 1,880 |
| `QUARANTINE_BATCH` | 1 |

## Why the font numbers dominate

`FONT_FACE` (3,966) and `PROVENANCE_RIGHTS_GROUP` (1,880) are **different questions about
the same files**: *is this typographically what we think it is?* and *do we know where this
copy came from?* They are deliberately **not** collapsed — collapsing them is exactly the
C4b defect.

Most `FONT_FACE` items are **batchable**; `PROVENANCE_RIGHTS_GROUP` items are **not**, and
that is the irreducible core of the work.

## The honest bottom line

**The workload is large and no framing makes it small.** The single biggest reduction —
accepting the dump quarantine as one decision — is also the one carrying the most risk.
**The recommended path is not to review 4,786 unverifiable fonts; it is to disable them and
rebuild from verified sources.**
