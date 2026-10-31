# Phase 2A-9E — Safe 1.2 Activation & Physical Qualification — CLOSEOUT

Date: 2026-07-23. Five focused commits. STE/RTE 1.2 are now RECOMMENDED for
new tasks (requiring explicit confirmation), 1.1 is legacy-reproduction
only, the version is visible everywhere, Gate 2 clears the physical blocker
only on an exact-hash FIT_PASS, and a physical pilot is staged. Nothing was
auto-selected, no authority beyond TECHNICALLY_QUALIFIED_DOMAIN was granted.

## Commits
| # | hash | content |
|---|---|---|
| 1+2 | fb8caa8 | registry new-selection metadata + selection policy (recommend 1.2, require version confirmation, 1.2 resolves for confirmation/artwork, confirm-flag preserves task #50) |
| 3 | 8e2cf77 | version visible everywhere + recommended/legacy chooser |
| 4 | 5533d65 | Gate-2 exact-hash FIT_PASS clearance (narrowly scoped) |
| 5 | (this) | physical pilot PDFs + fixture matrices + authority report + closeout |

## New-task selection policy (§1/§2)
- A bare STE/RTE `user_template` no longer silently resolves to legacy 1.1;
  it returns `STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED` with 1.2 as
  `RECOMMENDED_CORRECTED_VERSION` and 1.1 as `LEGACY_REPRODUCTION_ONLY`
  (`SUPERSEDED_FOR_NEW_SELECTION_BY_1_2`, advanced-only). Neither is
  auto-selected.
- An explicit version confirmation resolves (1.2 lands a 1.2 record).
- `_CURRENT` stays 1.1 so `resolve()` is historical-reproduction-safe;
  pinned/historical jobs are untouched; no migration.
- Driven by an EXPLICIT registry mapping (`recommended_corrected_version`),
  never an inferred version count.

## Version visibility (§3)
The version + its new-selection class appear in structure_presentation
(structure review), the Review Board specification, the physical-test PDF
(`template_key`), and the native handoff manifest (added `template` +
`template_version`). The chooser renders 1.2 RECOMMENDED vs 1.1 legacy with
the W-derived limitation spelled out.

## Gate behavior (§6)
A technically-qualified 1.2 structure proceeds through structural preview,
confirmation and artwork mapping (its `confirmation_requires_physical_fit_
pass` is False; the customer-grade opposed/ecma archetypes keep True, so
task #50's flow is preserved). Gate 2 stays blocked by
`PHYSICAL_SAMPLE_VALIDATION_REQUIRED` and clears ONLY when the exact
geometry hash has a recorded FIT_PASS (reuses `promotion_blockers`).
Clearing it does not open Gate 2 — the output-intent/ICC, font-licence and
content blockers still apply. Nothing clears live (no FIT_PASS exists).

## Physical pilot (§4/§5)
`physical_pilot_1_2/`: 3 priority samples per archetype (normal cosmetics,
the wide-short carton 1.1 rejected but 1.2 supports, a boundary-near
carton) — 6 exact-100%-scale test PDFs with calibration square, geometry
hash, dimensions, assembly + closure sequence and a physical-validation
form. Outcome vocabulary is a superset (adds TUCK_ENTRY_FAILURE,
SLIT_OR_NOTCH_FAILURE). One exact-hash FIT_PASS grants only
PHYSICALLY_VALIDATED_INSTANCE; `dimensional_family_blockers` requires
multiple representative passes; no result grants manufacturer authority.

## Authority states
STE 1.2 and RTE 1.2: `TECHNICALLY_QUALIFIED_DOMAIN` only. Not granted:
`PHYSICALLY_VALIDATED_INSTANCE`, `PHYSICALLY_VALIDATED_DIMENSIONAL_FAMILY`,
`PRODUCTION_AUTHORIZED_BY_MANUFACTURER`.

## Non-regression (§7/§8)
task #47 (`2be58c7b…`) and task #50 (`0f5b8bf6…`, still
`APPROVED_FOR_PHYSICAL_TEST`, not validated, no artwork remap, test PDF not
regenerated, Gate 2 not approved) unchanged; STE/RTE 1.1 + Skynte 1.0 +
opposed 0.1 byte-stable; auto-bottom excluded (no adapter, not shown as a
qualified choice); no provider calls.

## Stop
Stopped before: making 1.2 auto-selected, hiding 1.1 completely, granting
dimensional-family physical authority, granting manufacturer production
authority — each awaits separate approval.
