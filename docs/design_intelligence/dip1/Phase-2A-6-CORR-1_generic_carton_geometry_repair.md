# Phase 2A-6-CORR-1 — Generic Carton Cut/Fold Geometry Repair

Repairs the manufacturing defect Phase 2A-6's new cut/fold check surfaced in
the three legacy generic carton engines, and hardens the ICC output-intent
contract. `STANDARD_VECTOR_PACKAGING_PIPELINE` stays **False**.

Commits: `5fe2b1b` geometry correction + versions + fixtures · `3e4db7f`
ICC identity contract · this document.

## 1. Root cause — one shared construction, two wrong assumptions

All three generic styles share `_calculate_carton`, which emitted two
**full-width** horizontal creases:

```python
(x1, y1, x5, y1),   # top
(x1, y2, x5, y2),   # bottom
```

That single literal ignored:

1. **Which column carries a flap at that end.** A tuck carton has a flap on
   only one main panel per end; the opposite main panel's edge is a plain
   **cut**. STE: front is flapless at `y1`, back at `y2`. Reverse: mirrored.
   Auto-bottom: front is flapless at `y1` only (its lock base hinges across
   every column).
2. **The DECISION-015 lock notches.** Each active tuck flap is notched `2t`
   square at both base corners, so the outer `2t` of the base edge is cut
   away — and the crease was scored straight through it.

The defect is therefore in **generic flap-base/panel-edge crease
construction**, not in slit insertion order, segment merging, contour
normalization, or any template-specific code. It was fixed at that shared
layer; no task-specific coordinates were touched.

## 2. Geometry rule (DECISION-021)

`_hinge_creases` emits one crease per **real hinge**:

| surface | crease |
|---|---|
| tuck-carrying column | `x_l + lock_notch` → `x_r − lock_notch` |
| side columns (dust flaps) | full column width |
| flapless main panel | **none** at that end |
| glue tab | never (DECISION-008) |
| auto-lock bottom | all four columns, full width |

Folds are **shortened, never deleted** — every flap-bearing column keeps a
working hinge (asserted). Zero-length segments are dropped, so no duplicate
or empty crease can be emitted. Vertical body creases are untouched. Slit
and notch dimensions are unchanged.

## 3. Conflict length, measured exactly

W 42 × D 32 × H 140, t = 0.30, compensation on:

| template | before | after | folds |
|---|---|---|---|
| `straight_tuck_end_carton` | **87.00 mm** | **0.00 mm** | 6 → 10 |
| `reverse_tuck_end_carton` | **87.00 mm** | **0.00 mm** | 6 → 10 |
| `tuck_top_auto_bottom_carton` | **43.20 mm** | **0.00 mm** | 6 → 11 |
| `skynte_foundation_tuck_carton` | 0.00 mm | 0.00 mm | 10 (unchanged) |

The measurement itself was corrected: buffering the boundary inflated every
contact by the buffer radius (over-reporting a real conflict by ~0.4 mm and
inventing fractions of a millimetre on clean creases). Collinear overlap is
now computed exactly as a 1-D interval union per boundary edge.

## 4. Versioning decision — option B, per template

**All three generic templates: register corrected `1.1`, freeze `1.0`.**
Regenerating `1.0` in place would make historical reproduction ambiguous —
a stored configuration would silently render differently. So:

- `1.0` stays registered and buildable (`per_hinge_creases=False`), marked
  `production_ready=False`, `superseded_by="1.1"`. A historical job pinned to
  1.0 reproduces byte-for-byte.
- `1.1` is corrected and is what an **unpinned** caller resolves to.
- Gate 2 refuses `1.0` with `NON_PRODUCTION_TEMPLATE_VERSION`.
- Choosers (`all_templates()`) only offer production-ready versions.

`skynte_foundation_tuck_carton` stays at **1.0**: it was already correct
(DECISION-020), so no new version is warranted.

The registry is now keyed by `(template_id, version)` with a current-version
pointer; `DielineInputJSON` gains an optional `template_version`.
**No migration** — versions ride in the existing `structure_selection` JSON,
and no historical selection is rewritten.

## 5. Independent structural fixtures

`apps/dielines/tests/fixtures_generic_geometry.py` derives every expected
value **by hand** from the coordinate contract and the DECISION record:
panel sequence and widths, the full x/y contract, flat size, body height,
crease endpoints (defective *and* corrected), slit and notch positions, flap
orientation, glue-seam side, component ids, and the pre-correction conflict
length. 75 tests assert the engine against those fixtures — never against
its own output. The fixtures caught the measurement bug in §3: the
hand-derived 43.20 mm disagreed with the buffered 43.58 mm, and the fixture
was right.

## 6. ICC output-intent contract

`MISSING_OUTPUT_INTENT` remains a hard Gate-2 failure and **no default
profile is ever shipped**. `describe_profile()` now records the identity in
the readiness report: path, filename, SHA-256, size, ICC description (v2
`desc` and v4 `mluc`), colour space, component count, device/profile class,
profile version, validation result.

Acceptance states: `NOT_CONFIGURED` · `FILE_NOT_FOUND` · `UNREADABLE` ·
`MALFORMED` · `NOT_CMYK` · `NOT_AN_OUTPUT_PROFILE` ·
`VALID_CMYK_OUTPUT_PROFILE`. A CMYK **display** profile is refused as firmly
as an RGB one — only an output (printer) profile describes a press
condition. New failure `INVALID_OUTPUT_INTENT_PROFILE` catches a file whose
intent is present but whose configured profile no longer validates. PDFs
built without an intent are marked `PREVIEW_ONLY_NO_OUTPUT_INTENT` and can
never be presented as production deliverables.

## 7. Task #47 regression

Unchanged: `awaiting_gate_2`, not approved, zero Gate-2 decisions, sole
failure `PLACEHOLDER_REGULATORY_INFO`. Its regulatory data was not touched.
The Skynte template is pinned by fixture: panel sequence, panel widths, x/y
contract, entry slits (5 mm × 4 segments), lock notches (0.6 mm), fold
shortening (10 folds, 6 horizontal), zero conflict, version 1.0, still the
only published version.

## 8. Open items

- Real crash-lock auto-bottom geometry (interlocking panels, adhesive areas,
  diagonal folds) still needs a **measured reference die**; the current
  trapezoid remains an ECMA approximation flagged `provisional`. The
  cut/fold rule holds for it, but its four lock flaps merge into one
  continuous shape rather than being separated by cuts.
- A CMYK press profile must be configured before any file can pass
  `MISSING_OUTPUT_INTENT`.
- Generic cartons are now production-*eligible* at v1.1, but production
  readiness still requires the full Gate-2 checklist to pass.
