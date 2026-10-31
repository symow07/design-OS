# Recommendations — DIP-0C5 and DIP-1

## DIP-1 persistence: sixteen records, and the separations that must survive

Machine inference, human confirmation, evidence and permissions live in **separate
records**. That is not tidiness — it is the only way a human correction can sit *beside*
an inference rather than erase it, and the only way "we found an OFL" can never become "we
have a licence".

| Record | Holds | Never holds |
|---|---|---|
| **FontSourceFile** | path, SHA-256, size, format, mtime, package FK | rights, permissions |
| **FontFace** | face_id, collection index, name IDs 1/2/4/6/16/17, vendor, version, weight, width, italic, glyph count, tables | rights |
| **FontCollection** | `.ttc`/`.otc` container → its faces (**a file is not a font**) | rights |
| **FontFamily** | preferred key (ID 16), fallback (ID 1), key source, state | rights |
| **FontFamilyRelationship** | supporting + conflicting evidence, `FAMILY_RELATIONSHIP_REVIEW_REQUIRED` | rights |
| **FontDuplicateGroup** | SHA-256 → member files. **TECHNICAL identity only** | **rights — never** |
| **FontSourcePackage** | package root, kind (download / dump / unclassified), credibility | permissions |
| **FontProvenanceRecord** | **the rights-bearing record**: acquisition source, original path, package, provenance kind | technical metadata |
| **FontLicenseEvidence** | document path, type, association method + confidence, `mentions_fonts`, restrictions, `grants_permission: false` | approval |
| **FontRightsDecision** | a **human** decision: ownership, licence, reviewer, timestamp, reason, evidence refs | machine inference |
| **FontScriptCoverage** | per-script codepoint counts + dominant script (supplementary planes included) | rights |
| **FontTechnicalObservation** | health, parse status, warnings, `fsType` (**metadata, not permission**) | rights |
| **FontStyleObservation** | heuristic tags, evidence, capped confidence, inference source | any influence on rights |
| **FontReviewDecision** | queue, reviewer, outcome, reasons | machine inference |
| **FontPermission** | **per-flag**, granted by a named human, with scope and expiry | defaults to true, ever |
| **FontQuarantineRecord** | proposal, evidence, exceptions, `is_applied`, human confirmation | machine-applied disposition |

**The load-bearing separation: `FontDuplicateGroup` (technical) and
`FontProvenanceRecord` (rights) must never be joined into one table.** The moment they
are, a licence attaches to a hash, and one package's paperwork silently clears an
identical file from an unknown source. That is the C4b defect, made permanent in a schema.

**Do not finalise these models in C4c.** They are a recommendation.

## The three things DIP-1 must not do

1. **Do not let `fsType` become a permission field.** It is embedding metadata. A font
   whose fsType says INSTALLABLE may still be one BBROSE has no right to use.
2. **Do not default any permission to true.** Fail closed: `LICENSE_UNVERIFIED`,
   retrieval / automatic use / production use / embedding / redistribution **disabled**,
   for every font without a reviewed and accepted rights decision.
3. **Do not read "no suspicion" as "clean."** The foundry list is hand-written. *Not
   suspected* means *not examined*.

## DIP-0C5

4. **The font queues join the existing registry** (stable `queue_id`, letters as labels).
   C5 consolidates; it does not build a parallel review system.
5. **Nothing becomes retrievable in C5.** It is a review milestone, not an activation one.
6. **The `TYPOGRAPHY_SYSTEM` authority domain slot stays open** — and stays empty until a
   real brand font is selected for human review. Building the approval path before there
   is anything to approve is how frameworks acquire features nobody asked for.

## The decision that actually matters

**4,786 fonts — 98% of the corpus — have no licence evidence of any kind.** No schema
fixes that. The choice is:

- **(a)** BBROSE finds the paperwork, or
- **(b)** the library is quarantined and **rebuilt from fonts whose provenance is known.**

C4c recommends **(b)**, and the capability gaps say why: Arabic display, CJK, a modern sans
and an elegant serif have **no candidate** that clears the bar. **The starter library
cannot be built from what is here.** Those fonts will have to be acquired — properly, with
provenance — and that is a business decision, not a technical one.
