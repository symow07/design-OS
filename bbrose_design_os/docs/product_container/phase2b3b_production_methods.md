# Phase 2B-3B — Production Methods & Finish/Separation Contracts

Adds the production-method + separation contract layer over the native
container reconstruction. Zero migrations (additive `spec_sheet` keys). No
provider calls. All codes here are **production-readiness** codes — they never
enter the reconstruction `blockers`, so concept review still reaches Gate 2
(the Gate-2 refusal that consumes them is 2B-3D).

## The load-bearing invariant

Production methods are **derived from the confirmed decoration zones'
`permitted_techniques`** — the only source that exists (there is no method
picker). A technique that was a `propose_zones` machine default, confirmed only
as part of zone geometry, is **never manufacturer authority**. Therefore:

- authority defaults to `INFERRED_NONAUTHORITATIVE` (source
  `INFERRED_NONAUTHORITATIVE` — not `EXPLICIT_USER_REQUEST`);
- only `VERIFIED_MANUFACTURER_CAPABILITY` (from `VERIFIED_MANUFACTURER_SPEC` /
  `VERIFIED_SUPPLIER_CONFIRMATION`) clears a readiness blocker, and **this
  phase has no channel to obtain manufacturer evidence** — so every container's
  production-method authority stays UNVERIFIED by construction and the gate
  stays blocked. That is the intended, honest state (it mirrors the font
  fallback UNVERIFIED and the packaging `PRODUCTION_AUTHORITY_PENDING_EXTERNAL_
  EVIDENCE` state).

Manufacturer capability is never inferred from a photo, a concept render, a
historical design, or "what similar containers usually use".

## `container_production_method/1.0` (§1–§5)

`method_type_for` maps technique + surface/zone → method_type (pad on a cap
surface → `CAP_PRINT`; a `BOTTOM_CODE_ZONE` → `BOTTOM_INKJET_CODE`). Each record
carries the full field list + INFERRED type-default constraints (colour cap,
min line weight, min text size, coverage, registration) and a deterministic
`method_hash`.

`validate_production_methods` measures the **emitted geometry** (not declared
values): the minimum emitted stroke weight, the minimum product-name text size,
and the distinct printed colours. A constraint PASS never clears the gate; a
FAIL is a real advisory signal. Codes: `CONTAINER_TECHNIQUE_UNVERIFIED` (always,
by construction), `…_UNSUPPORTED`, `…_METHOD_ZONE_MISMATCH`,
`…_METHOD_SURFACE_MISMATCH`, `…_MATERIAL_TECHNIQUE_MISMATCH`,
`…_COLOR_COUNT_EXCEEDED`, `…_MINIMUM_LINE_WEIGHT_FAILED`,
`…_MINIMUM_TEXT_SIZE_FAILED`, `…_TRAPPING_REVIEW_REQUIRED`,
`…_OVERPRINT_REVIEW_REQUIRED`. The design-language motif strokes (min 0.18 mm)
sit below a typical 0.2 mm screen minimum, so a motif'd container legitimately
reports `…_MINIMUM_LINE_WEIGHT_FAILED` — a real measured signal, never silently
scaled.

## `container_production_separations/1.0` (§6–§8/§11–§14)

A data manifest, not visible paint (§7): `PROCESS_ARTWORK` is the one visible
separation; ink/finish separations (SCREEN_INK_1/2, PAD_PRINT_INK_1,
HOT_STAMP/CAP_HOT_STAMP foil, EMBOSS/DEBOSS, BOTTOM_CODE) are **hidden** named
separations with a visibility default — nothing opaque is drawn over the
design. The swatch/spot registry classifies process vs spot vs technical, keeps
names **unique**, and holds spot values as `TECHNICAL_PLACEHOLDER` pending
manufacturer review (§8).

- **White underbase (§11)** is keyed off **confirmed** profile transparency,
  never assumed: unknown/inferred → `REVIEW_REQUIRED`
  (`CONTAINER_WHITE_UNDERBASE_REQUIRED`, not generated); confirmed transparent →
  a hidden `WHITE_UNDERBASE` spot separation over the body zones.
- **Label geometry (§12)**: `LABEL_CUT`/`LABEL_BLEED`/`LABEL_SAFE` around a
  confirmed label zone, `confirmed_cutline: false` — never auto-promoted to a
  production cutline.
- **Shrink sleeve (§13)**: seam + top/bottom exclusion bands + a distortion
  review flag (`CONTAINER_PROJECTION_DISTORTION_REVIEW_REQUIRED`) — no
  production-ready compensation claim without manufacturer specs.
- **Hashing (§14)**: deterministic per-separation, set, and combined
  method+separation hashes; a change to any method/separation invalidates the
  combined confirmation.

## Failure semantics (§17)

A method/separation failure preserves the selected concept, profile, zones and
native reconstruction, persists all diagnostics, keeps the task reviewable, and
does not globally fail the task or create a raster fallback. These belong to
production readiness, not reconstruction identity.

## Golden fixtures (§16)

`container_native_golden.json` freezes, per archetype, the method types +
`method_set_hash`, the separation names + `separation_set_hash`, and the
underbase state: bottle → SCREEN_PRINT ×2 + CAP_PRINT; jar → WRAP_LABEL (+
LABEL_CUT/BLEED/SAFE) + CAP_PRINT; tube → SCREEN_PRINT ×2 + BOTTOM_INKJET_CODE.
Every fixture asserts authority UNVERIFIED, `CONTAINER_TECHNIQUE_UNVERIFIED`
present, underbase `REVIEW_REQUIRED`, and zero decorative rasters.

## Known bounds (honest)

- **Authority is UNVERIFIED by design** — no manufacturer-evidence channel this
  phase; Gate-2 enforcement of these codes is 2B-3D.
- Colour-count / line-weight / text-size are measured over the **decoration
  artwork as a whole**, reported per method (not yet per-zone-precise).
- **§5 codes actively computed:** `TECHNIQUE_UNVERIFIED`, `TECHNIQUE_UNSUPPORTED`,
  `METHOD_SURFACE_MISMATCH`, `MATERIAL_TECHNIQUE_MISMATCH`,
  `COLOR_COUNT_EXCEEDED`, `MINIMUM_LINE_WEIGHT_FAILED`,
  `MINIMUM_TEXT_SIZE_FAILED`, `TRAPPING_REVIEW_REQUIRED`,
  `OVERPRINT_REVIEW_REQUIRED`. **Defined but not yet computed → 2B-3C:**
  `METHOD_ZONE_MISMATCH` (structurally can't fire — methods are derived from
  zones), `REGISTRATION_TOLERANCE_FAILED` (no registration measurement yet),
  `MAXIMUM_COVERAGE_EXCEEDED` (per-method coverage not yet validated).
- **§9 colour-count** currently counts distinct **process-artwork** colours,
  not the spot / white-underbase / foil separation colours — a real but
  narrower basis than §9's full definition (→ 2B-3C).
- Separations are a **contract manifest** with visibility defaults + technical
  geometry data; emitting them as named layers in the `.ai` is the 2B-4
  handoff step. Nothing is painted over the visible artwork.
- Deferred to **2B-3C** (per the accepted 2B-3A review): the container-specific
  influence dimensions (logo scale, front/back balance, cap/body coordination,
  label density, wrap continuation) + per-reference realization attribution.
