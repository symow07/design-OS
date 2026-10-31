# DIP-0C4b — completion report

**System-font suspicion, source packages, licence evidence, quarantine
recommendations, batch leverage, review queues.** Builds on C4a (`2447a72`).

---

## System-font suspicion — from the name table, never the filename

| outcome | faces |
|---|---|
| `SUSPECTED_SYSTEM_FONT_COPY` | **706** |
| `SYSTEM_FONT_EVIDENCE_PRESENT` | 127 |
| `SYSTEM_FONT_STATUS_UNCERTAIN` | 0 |
| `NO_SYSTEM_FONT_EVIDENCE` | 3,133 |

**706 faces / 669 files / 324 families** are suspected. Foundries named in the name
tables: **Microsoft 359** · Monotype 196 · Adobe 172 · URW 73 · Agfa Monotype 21 ·
Linotype 20.

`filename_used: false` on every record. Confidence capped at **0.85** — never certainty.
`legal_conclusion: None`, and no machine may set it. **A suspicion is not a finding of
wrongdoing:** a Microsoft font may be perfectly licensed to BBROSE, or ship with a tool
BBROSE owns, or be an internal system dependency.

## A bug I introduced and caught: folder location was changing the answer

`EV_DUMP_FOLDER` is weighted **0.0**. That was not enough.

On the first run **2,972 faces** landed in `SYSTEM_FONT_STATUS_UNCERTAIN` — not because
the folder had weight, but because its mere **presence in the evidence list** pushed them
out of `NO_SYSTEM_FONT_EVIDENCE`. Location was changing the outcome through the back
door, and nearly three thousand innocent faces were flagged for **living in the wrong
directory** — the exact inference this project has refused since C3a, committed by me.

The outcome is now decided by **substantive evidence only** (weight > 0). Location is
recorded, shown to the reviewer, and moves nothing. Queue B fell from **3,099 items to
127**.

## Proximity is not relevance — the finding that changed the licence model

DIP-0A rated a licence file "strong" when it sat in the same directory as a font. On this
corpus that is sometimes wrong in a way that matters.
`DOWNLOADS 12-2025/animal-bookmarks/License free.txt` opens:

> *"This license only applies if you downloaded this **vector** as an unsubscribed user…"*

It is a **stock-vector licence**. It says nothing about the font beside it.

C4b **re-reads every evidence document** and classifies what it actually is. The result:

> **97 fonts have some licence evidence. Only 72 have evidence that mentions fonts at
> all. 4,786 fonts have none whatsoever.**

Types found: `UNKNOWN_LICENSE_TEXT` 38 · `SIL_OPEN_FONT_LICENSE` 28 · `APACHE_LICENSE` 18
· **`DEMO_OR_TRIAL` 12** · `VENDOR_URL_ONLY` 7 · `README_OR_NOTES` 4. Demo/trial and
personal-use terms are surfaced as **restrictions** — a font shipped as a demo is not one
BBROSE may use commercially.

Every association carries `grants_permission: false` and `review_status: NOT_REVIEWED`. An
OFL does not set `LICENSE_APPROVED`. **Possession is not permission.**

## Source packages, and the duplicated dump

**47 packages**: 46 `DOWNLOAD_PACKAGE` (credible rights batches) + **1
`SUSPECTED_DUPLICATED_DUMP`**. 31 have licence evidence.

`materials/Fonts` is **92.5% byte-identical** to `materials/Fonts/3333` — 933 shared
hashes of 1,009. They are **one** package, both paths preserved,
`is_credible_rights_batch: false`, and **neither folder's evidence clears the other**.

## EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS

I first claimed *"exact duplicates are safe as one rights decision — identical bytes are
identical rights."* **That was wrong, and it was the most dangerous sentence in C4b.**

A SHA-256 match proves the **files** are the same. It says nothing about where each copy
came from, what was signed to obtain it, or what that licence permits. The same TTF bought
from a foundry under a paid licence and scraped from a warez site is **byte-identical and
legally nothing alike**. **Rights attach to PROVENANCE and ACQUISITION, not to content.**

Every duplicate group now splits into:

* **A. one TECHNICAL IDENTITY group** — bytes, parsed metadata, glyph structure, technical
  health, script coverage, `fsType`, family/face identity. Safely shared, **technical
  scope only**.
* **B. N PROVENANCE-RIGHTS subgroups** — by source package, original path, acquisition
  source, licence evidence, vendor provenance. Batchable **only** where every copy shares
  one *credible* package **and** one evidence set.

Measured: **941 duplicate groups → 1,880 provenance-rights subgroups. ZERO are
rights-batchable** — nearly every duplicate spans the unverified dump. My "942 files saved"
rights claim was worth **exactly nothing**.

## Batch leverage — and what stops each batch

| lever | scale | safe as one decision? |
|---|---|---|
| exact duplicates — **TECHNICAL identity** | 942 files | **yes** — *technical only* |
| exact duplicates — **RIGHTS** | **0 of 941** batchable | **no** — provenance-aware |
| suspected system-font batch | 706 faces | **no** — a licensed Microsoft font is legal |
| download packages with evidence | 31 batches | **no** — evidence that doesn't mention fonts governs nothing |
| family groups | 2,832 | **no** — 190 carry conflicting evidence |
| family × source package | 30 split families | **no** — this *splits* work |

## Fail-closed operational policy

Any font without **reviewed and accepted** rights evidence: `LICENSE_UNVERIFIED`,
retrieval / automatic use / production use / embedding / redistribution all **disabled**.
That is **4,786 of 4,883 fonts**. New postures `RIGHTS_REVIEW_REQUIRED` and
`PROVENANCE_MISSING`. Nothing is permanently rejected or deleted.

**"No system-font suspicion" is never "safe" or "licensed."** *Not suspected* means *not
examined*.

## The dump quarantine is a PROPOSAL, not a disposition

`is_applied: false`, `applied_by_machine: false`. The reviewer sees totals, duplicate
overlap, vendor and copyright evidence, the 32 `.fon` files, contradictory evidence, known
exceptions — and the **false-positive risk in plain sight**: the batch is defined by
*folder*, suspicion by *name table*, and most files in the folder carry no suspicion at
all. Accepting it quarantines fonts never individually implicated. That may still be right
for an unverified dump — but it is a judgement, and it is not the machine's.

## Recommendation: curate forward, do not try to clear the dump

98% of the corpus has no licence evidence. Clearing 4,786 fonts of unknown provenance is
not a review task, it is an archaeology project — and it would produce a library nobody
can defend. **Keep the dump operationally disabled** (it already is), prioritise the 46
organised packages, review the 72 fonts with font-relevant evidence first, select a small
starter collection (Latin / Arabic / CJK / display / body / luxury), require known
provenance and explicit approval, and **rebuild the operational library gradually from
verified sources**. The dump may remain **archived** — it must not become the active BBROSE
font library by default.

## Queues

| | queue_id | items | files | priority |
|---|---|---|---|---|
| A | `FONT_SUSPECTED_SYSTEM_COPY` | 706 | 706 | HIGH |
| B | `FONT_SYSTEM_STATUS_UNCERTAIN` | 127 | 127 | MEDIUM |
| C | `FONT_MISSING_LICENSE_EVIDENCE` | 16 | **3,848** | HIGH |
| D | `FONT_LICENSE_EVIDENCE_PRESENT` | 26 | 70 | MEDIUM |
| E | `FONT_SOURCE_PACKAGE_REVIEW` | 46 | 161 | MEDIUM |
| F | `FONT_FAMILY_RELATIONSHIP_REVIEW` | 190 | 630 | MEDIUM |
| G | `FONT_UNPARSEABLE` | 32 | 32 | LOW |
| H | `FONT_QUARANTINE_CANDIDATE` | 1 | **3,780** | HIGH |
| I | `FONT_DUPLICATE_BATCH` | 941 | 1,883 | LOW |
| J | `FONT_RIGHTS_CONFLICT` | 30 | 0 | HIGH |

`queue_id` is identity; the letter is a display label. Every queue records its shared
reason, evidence, **exceptions**, roles and recommended action. **No queue applies a
decision** (`applies_decision_automatically: false` on all ten).

## Safety

**0 files moved. 0 files deleted. 0 fonts installed. 0 rendered. 0 exposed.** Every
permission `false`, derived from the canonical `PermissionSet` — no count hardcoded.

`machine_font_state()` raises on `LICENSE_APPROVED`, `COMMERCIAL_USE_APPROVED`,
`APPROVED_BRAND_FONT`, `BBROSE_OWNED_CONFIRMED` **and `PERMANENTLY_REJECTED`** — a machine
may not condemn a font any more than it may bless one. The five permitted human outcomes
are recorded; none is taken.

Style tagging **deferred to C4c**, as permitted — it would have distracted from the rights
audit.

## Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c/tests/test_c4b.py` | **35 passed** |
| `pytest tools/dip0c` | **559 passed** |
| DIP-0A + DIP-0B | **343 passed** |
| Django | **537 passed**, 1 skipped |
| `ruff check tools/` | clean |
| `materials/` integrity | **unchanged** |
| runtime | 0.6 s |
| committed output | 69 KB (heavy → `var/`, git-ignored) |

## Findings requiring adjustment before C4c

1. **4,786 fonts — 98% of the corpus — have no licence evidence of any kind.** C4b can say
   so loudly; it cannot conjure paperwork that does not exist. The answer is either BBROSE
   finds it, or the library is quarantined and rebuilt from fonts whose provenance is
   known. **That is the most consequential decision in DIP-0C4, and it is a business one.**
2. **"No suspicion" must not be read as "clean".** The foundry list is hand-written; a
   system font from an unlisted foundry is not suspected. C4b errs toward silence.
3. **The biggest batch is also the riskiest.** Quarantining the dump is one decision
   covering 3,780 files. It is *offered*, not taken.

**HOLD for review before C4c.**
