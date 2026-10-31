# DIP-0C3a — Decisions

## 1. C3a decides nothing about rights

Ownership, licence, canonical status and permission are **NOT_ASSESSED_IN_C3A**.
They are C3b/C3d questions. Every permission in the matrix is `false`, and
`BBROSE_OWNED_CONFIRMED`, `LICENSE_APPROVED` and `CANONICAL_BRAND_MASTER` raise
`HumanOnlyStateViolation` if machine code so much as tries.

## 2. A brand name comes from a known token, or from nobody

Taking the largest live-text span and calling it "the brand" produced `BBROSE.pdf`
→ *"OIL"* and `ATC PRESENTATION` → *"A"*. **A headline is not a wordmark.**

So a brand name is asserted **only** when the live text contains a *known brand
token* (BBROSE / ATC / JOJIA). Otherwise:

- the extracted text is recorded **as evidence**, with page/font/size/bbox
  provenance, and handed to the reviewer;
- `brand_name` is `null` and the tier is `REQUIRES_HUMAN`.

An **outlined** wordmark (0 live-text spans) is likewise `REQUIRES_HUMAN`. **No
OCR** — deferred to DIP-0E — and the filename is *never* used to assert a name.

## 3. Filename and folder are supporting evidence, never decisive

`is_decisive: false` on every record. The probe is the argument: three of the five
vector logos in the BBROSE office folder are **third-party**, and the two biggest,
most BBROSE-named files are the **worst** master candidates.

## 4. DIP-0A is never rewritten

`BBROSE.pdf` / `BBROSE-1.pdf` keep their original `BRAND_MASTER` label as the
historical record. The correction lives in a C3 override
(`DESIGN_COMPOSITION` / `REFERENCE_ONLY`) with evidence, confidence, a blank
`human_confirmed_category`, and `cannot_be_canonical_master: true`. **Both** the
original label and the contradictory evidence go to the review queue.

## 5. Nomination requires being a brand asset in the first place

Clean isolated vector geometry is **necessary but never sufficient**. A background
and a sticker sheet were briefly nominated as brand-master candidates purely for
being tidy vector art. Nomination is now restricted to brand-role files, and never
fires for a composition or a third-party mark.

## 6. Third-party is a property of a FILE, not of a pair

Emitting `POSSIBLE_THIRD_PARTY_ASSET` per pair produced 119 near-identical
"hypotheses" that said nothing about the pair. It is recorded once per record.
Brand relationships are proposed only **between brand assets** — comparing a
baby-pattern with a logo was pure noise (184 edges → 83).

## 7. Every hypothesis carries contradictory evidence

Because the honest answer is usually "these two sit in one folder, and that tells
us almost nothing". Folder-only edges are emitted at confidence 0.1 with the
explicit contradiction that a shared folder never proves a brand relationship.
