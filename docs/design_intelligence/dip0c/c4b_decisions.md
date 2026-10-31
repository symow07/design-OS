# DIP-0C4b — decisions

## D1. Suspicion is raised from the name table. The filename is never read.
`achVendID`, copyright, trademark, manufacturer — those are the evidence. My own first
probe "detected" system fonts in *Barista **Script*** and *ALLOVER **MODERN** DEMO* by
substring, which is precisely the class of mistake this project has refused since C3a.

`filename_used: false` is recorded on **every** suspicion record, and a test feeds the
assessor `microsoft-lookalike.ttf` and `arial-clone.ttf` and asserts it stays silent.

## D2. Folder location carries zero weight — and zero *effect*
`EV_DUMP_FOLDER` is weighted `0.0`. That was not enough.

In the first run, **2,972 faces** landed in `SYSTEM_FONT_STATUS_UNCERTAIN` — not because
the folder had weight, but because its mere **presence in the evidence list** pushed them
out of `NO_SYSTEM_FONT_EVIDENCE`. Location was changing the answer through the back door,
and nearly three thousand innocent faces were flagged for living in the wrong directory.

The outcome is now decided by **substantive** evidence only (weight > 0). Location is
recorded, shown to the reviewer, and moves nothing. Queue B fell from 3,099 items to 127.

## D3. A suspicion is never a finding of wrongdoing
`SUSPECTED_SYSTEM_FONT_COPY` means *"the name table says Microsoft, and a human should
look"*. It does **not** mean the font was copied illegally. A Microsoft font may be
perfectly licensed to BBROSE, or ship with a tool BBROSE owns, or be an internal system
dependency.

`legal_conclusion` is `None` and no machine may set it. Confidence is capped at **0.85** —
never certainty, because certainty is not available from four bytes of self-declared
metadata.

## D4. PROXIMITY IS NOT RELEVANCE — the finding that changed the licence model
DIP-0A rated a licence file "strong" evidence when it sat in the same directory as a
font. On this corpus that is sometimes wrong in a way that matters.
`DOWNLOADS 12-2025/animal-bookmarks/License free.txt` opens:

> *"This license only applies if you downloaded this **vector** as an unsubscribed user…"*

It is a **stock-vector licence**. It says nothing about the font beside it. Same-directory
is a fact about the *filesystem*; whether the document governs the *font* is a fact about
the *text* — and only reading the text can tell them apart.

So C4b **re-reads every evidence document**, classifies what it actually is, and if it
never mentions fonts it is flagged `EVIDENCE_MAY_NOT_COVER_FONTS` and its association
confidence is cut by 0.4. Measured: **97 fonts have some evidence; only 72 have evidence
that mentions fonts at all.**

## D5. Evidence is evidence. It grants nothing.
An OFL, an Apache licence, a EULA, a readme, a vendor URL — every association carries
`grants_permission: false` and `review_status: NOT_REVIEWED`. The presence of an OFL does
not set `LICENSE_APPROVED`, does not approve commercial use, embedding or redistribution,
and never will from machine code. **Possession is not permission.**

Detected across the corpus: `UNKNOWN_LICENSE_TEXT` 38 · `SIL_OPEN_FONT_LICENSE` 28 ·
`APACHE_LICENSE` 18 · `DEMO_OR_TRIAL` 12 · `VENDOR_URL_ONLY` 7 · `README_OR_NOTES` 4.
**`DEMO_OR_TRIAL` and `PERSONAL_USE_ONLY` are surfaced as restrictions** — a font shipped
as a demo is not a font BBROSE may use commercially.

## D6. The dump is ONE package, not two
`materials/Fonts` is **92.5% byte-identical** to `materials/Fonts/3333` (933 shared
hashes of 1,009). Treating them as two rights batches would let one folder's evidence
"clear" the other. They are recorded as a single `SUSPECTED_DUPLICATED_DUMP`, both paths
preserved, `is_credible_rights_batch: false`, and **neither clears the other**.

## D7. Three independent review units
**Family** (technical) · **source package** (rights) · **family × package** (where they
disagree). The same family from two packages is **two rights units** — 30 families are
split across packages, and a licence approval **never** propagates across a package
boundary because two family names match.

## D8. EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS — the correction that mattered most

I first wrote: *"exact duplicates are safe as one rights decision — identical bytes are
identical rights."* **That was wrong, and it was the most dangerous sentence in C4b.**

A SHA-256 match proves the **files** are the same. It says nothing about where each copy
came from, what was signed to obtain it, or what that licence permits. The same TTF
bought from a foundry under a paid licence and scraped from a warez site is
**byte-identical and legally nothing alike**. **Rights attach to PROVENANCE and
ACQUISITION, not to content.**

So every duplicate group now splits in two:

* **A. one TECHNICAL IDENTITY group** — bytes, parsed metadata, glyph structure,
  technical health, script coverage, `fsType`, family/face identity. Safely shared,
  `safe_as_one_decision: true`, **scope: technical only**.
* **B. N PROVENANCE-RIGHTS subgroups** — split by source package, original path,
  acquisition source, licence-evidence association, vendor provenance. A rights decision
  may be batched **only** where every copy shares one *credible* package **and** one
  evidence set.

**One package's licence never clears an identical file that arrived from an unverified
source.**

Measured on the real corpus: **941 duplicate groups → 1,880 provenance-rights subgroups,
and ZERO are rights-batchable** — because nearly every duplicate spans the unverified
dump. My "942 files saved" rights claim was worth exactly nothing.

## D8b. Reducing workload is not evidence that a batch is safe
Every lever records its **shared evidence** and its **exceptions**:

| lever | scale | safe alone? |
|---|---|---|
| exact duplicates — **TECHNICAL identity** | 942 files | **yes** — but *technical only* |
| exact duplicates — **RIGHTS** | 0 of 941 batchable | **no** — provenance-aware |
| suspected system-font batch | 706 faces | no — a licensed Microsoft font is legal |
| download packages with evidence | 31 batches | no — evidence that doesn't mention fonts governs nothing |
| family groups | 2,832 | no — 190 have conflicting evidence |
| family × package | 30 split | no — this **splits** work, it does not save it |

## D8c. Fail-closed operational policy
Any font without **reviewed and accepted** rights evidence is `LICENSE_UNVERIFIED` with
retrieval, automatic use, production use, embedding and redistribution all **disabled**.
That is the standing state of **4,786 of 4,883 fonts**. New postures
`RIGHTS_REVIEW_REQUIRED` and `PROVENANCE_MISSING` join the machine-allowed set.

**"No system-font suspicion" is never read as "safe" or "licensed."** The foundry list is
hand-written; *not suspected* means *not examined*, never *cleared*.

## D8d. The dump quarantine is a PROPOSAL, never an applied disposition
`is_applied: false`, `applied_by_machine: false`. The reviewer is shown totals, the
duplicate overlap, vendor and copyright evidence, the 32 `.fon` files, contradictory
evidence, known exceptions — and the **false-positive risk in plain sight**: the batch is
defined by *folder*, but suspicion is defined by *name table*, and most files in the
folder carry no suspicion at all. Accepting it quarantines fonts never individually
implicated. That may still be right for an unverified dump — but it is a judgement, and it
is not the machine's.

## D9. Machine code may recommend quarantine. It may never delete, reject or clear.
`QUARANTINE_CANDIDATE` is a recommendation with reasons. `machine_font_state()` raises on
`LICENSE_APPROVED`, `COMMERCIAL_USE_APPROVED`, `APPROVED_BRAND_FONT`,
`BBROSE_OWNED_CONFIRMED` **and `PERMANENTLY_REJECTED`** — a machine may not condemn a font
any more than it may bless one. **0 files moved. 0 files deleted.** The five permitted
human outcomes are recorded and none is taken.

## D10. Style tagging is deferred to C4c
The business allowed it "only if technically justified" and said to defer it rather than
force it. It would have distracted from the rights audit, which is the point of C4b. It
is not implemented, and no style tag exists.
