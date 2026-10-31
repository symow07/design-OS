# Phase 2B-3C — Quantitative Fidelity, Reference Attribution & True Wrap Geometry

Completes the measurable container-design relationships deferred through 2B-3A/B.
Zero migrations (additive `spec_sheet` keys + explicit schema versions). No
provider calls. Every finding here is a **production-readiness** code — never a
reconstruction `blocker`, so a first-pass container still reaches Gate 2. Gate-2
aggregation itself remains 2B-3D.

## §0 Authority-source correction

A production technique a human explicitly chose/confirmed (zone source
`EXPLICIT_USER_FACT`) is recorded as `EXPLICIT_USER_REQUEST` /
`USER_REQUESTED_UNVERIFIED` (design intent, no manufacturer authority); a
machine-proposed technique stays `INFERRED_NONAUTHORITATIVE`. Both branches are
reachable (the confirm endpoint can set a zone's source) and tested; neither
clears the gate — only `VERIFIED_MANUFACTURER_CAPABILITY` does. Applied on
regeneration; historical records untouched.

## §2–§6 Quantitative fidelity — gate only against reliable targets

`container_quantitative_fidelity/1.0` measures the EMITTED geometry but gates an
axis ONLY when the selected-concept visual graph carries a **reliable** target
(§2). For a no-provider first-pass concept the graph carries almost none, so
most axes are `UNMEASURED` **by construction** — never fabricated from INFERRED
pixel noise. The axes that can gate today:

- **motif coverage** vs a VERIFIED `decorative_coverage_pct`;
- **logo zone** vs a VERIFIED `logo_zone` string (the emitter centres the logo,
  so an "upper-left" concept is a real `CONTAINER_LOGO_ZONE_MISMATCH`);
- **product-name zone / scale** measured against the confirmed **print zone**
  (never the silhouette, §4).

Two firing paths are proven end-to-end: a missed VERIFIED coverage target →
`CONTAINER_MOTIF_COVERAGE_FAILED`, and an upper-left logo target vs the centred
emission → `CONTAINER_LOGO_ZONE_MISMATCH`. Everything without a reliable target
(density, centroid, scale/rotation distribution, movement, colour-role,
continuation, cap/body, front/back) is `UNMEASURED`.

> §BH50(f)(5), 2026-09-16 (annotation, §AZ0(u) — the paragraphs above are history):
> an `UNMEASURED` axis of this report, of the base fidelity report, of the motif and
> typography reports and of the concept report BLOCKS ACCEPTANCE — Gate-2 approval —
> through `container_production_readiness.fidelity_unmeasured`, one code per axis,
> derived at read time and never persisted; it never blocks the reconstruction. Rule
> 4's `UNMEASURED_BLOCKING` names that scope in `blocking_scope`. The base report's
> `wrap_alignment` axis reads NOT_APPLICABLE, with its reason, on a product with no
> wrapped surface (§BH50(f)(6)). The seventeen axes here stay blocking as ruled.

## §7–§10 True seam-aware wrap geometry

`container_wrap_geometry/1.0` is a production-geometry **data record** (radius /
circumference / usable width / seam + safe / front-back anchors / exclusions /
text-safe regions / arc-mapping / projection hash) — NOT a re-emission of the
concept sheet. CYLINDRICAL maps flat x → arc degrees with an explicit seam;
TAPERED carries top/bottom width + exclusion bands + a distortion-review flag;
ROUNDED_RECT a flat-centre inset; OVAL front/back only; CUSTOM/UNKNOWN →
`CONTAINER_SURFACE_PROJECTION_REVIEW_REQUIRED`. `validate_wrap_alignment` fires
`CONTAINER_TEXT_CROSSES_SEAM` / `CONTAINER_WRAP_SEAM_CONFLICT` when a mark runs
into the seam-safe band, and the distortion-review code for tapered/oval/custom.
No manufacturer-grade compensation is claimed without verified tolerances.

> §BH50(f)(6), 2026-09-16 (annotation, §AZ0(u) — the paragraph above is history):
> the seam-safe rule applies to WRAPPED surfaces — `BODY_WRAP` and `CAP_WRAP`, the
> surfaces the contract develops by π. On a product whose every zone is a projected
> face, `validate_wrap_alignment` records `seam_check` NOT_APPLICABLE with its reason
> (never PASS: `aligned` is None; never silence); a wrapped record with no seam band
> reads UNMEASURED; the distortion and projection reviews keep firing on every
> curved zone. Task 52's two seam codes were fired off its BODY_FRONT by this rule.

## §11–§14 Coverage, registration, complete colour count, density

`container_production_metrics/1.0`:
- **coverage** per method/zone vs the permitted maximum →
  `CONTAINER_MAXIMUM_COVERAGE_EXCEEDED`;
- **complete colour count** = process (when colour-limited) + spot inks + white
  underbase, excluding technical guides → `CONTAINER_COLOR_COUNT_EXCEEDED` with
  the full swatch list (upgrades 2B-3B's process-only count);
- **registration** returns `REVIEW_REQUIRED` when registered separations
  interact and manufacturer capability is unverified (always this phase) —
  never a pretended production-safe geometry;
- **label density** reports printed/text/whitespace ratios per zone with the
  surface role (back = regulatory, front = hero); gated only against a reliable
  target (none this phase → reported, `UNMEASURED`).

## §15–§17 Precise per-reference attribution

Additive over the 2B-3A `material_influence_realization/1.0`:
`material_influence_plan/1.1` adds the container dimensions and makes each
approved reference **claim only** the dimensions its metadata supports (a
palette reference does not claim cap orientation). `material_influence_realization
/1.1` maps each reference, per claimed dimension, to an emitted manifestation —
so distinct references get **distinct** records; a load-bearing claim with no
emitted evidence → `MATERIAL_INFLUENCE_NOT_REALIZED`. `similarity_risk` flags
`CONTAINER_REFERENCE_SIMILARITY_REVIEW_REQUIRED` when one reference realizes many
dimensions (principle-based, never pixel similarity; never auto-removes).

## Golden fixtures (§21)

Per archetype, the deterministic wrap-set hash + surfaces are frozen alongside
the 2B-2/2B-2A/2B-3B blocks, plus tests proving the coverage MEASURED_FAIL path
and distinct per-reference attribution.

## Known bounds (honest)

- Quantitative axes without a reliable selected-concept target are `UNMEASURED`
  by construction (the common first-pass path) — the engine fires only where a
  VERIFIED target exists.
- `CONTAINER_REGISTRATION_TOLERANCE_FAILED` and `CONTAINER_LABEL_DENSITY_FAILED`
  are defined but not computed this phase (no verified tolerance / reliable
  density target); registration returns the REVIEW code instead. A real
  geometric-offset registration check needs verified manufacturer data.
- Wrap/coverage/colour are measured over the confirmed zones + emitted
  placements; they are data/contract records — the named-layer `.ai` emission
  is the 2B-4 handoff, and Gate-2 aggregation of all readiness codes is 2B-3D.
