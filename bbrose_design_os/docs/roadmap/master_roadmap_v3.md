# BBROSE Design OS — Master Roadmap V3

**Rebased 2026-08-03 against commit `5512cdc`** (399 commits, 5,003-test
suite, provider ledger 226 rows / $27.0542 — zero calls across the entire
recovery arc). Machine state: `docs/roadmap/progress_tracker.json`
(`bbrose_progress_tracker/3.0`), validated by `manage.py roadmap_status`.
Companion documents: `roadmap_gap_analysis.md`,
`quality_improvement_backlog.md`, `progress_methodology.md`,
`roadmap_change_log.md`. All previous roadmap files are preserved as
history.

## 1. The one objective

> BBROSE Design OS must produce **client-approvable, premium cosmetic
> design with editable Illustrator authority.**

Faithful to the selected concept, professionally composed, brand-accurate,
typographically refined, structurally editable, placeholder-free, on a
product-derived artboard, honest about production authority. **A valid AI
file containing poor design is a failed result** — the owner rejection
(`7624255`) and the Gate-A lesson both proved file validity and design
quality are different tests. Every milestone below is judged against this
objective, not against whether its code merged.

## 2. Program state (authoritative)

```
PRODUCT_CONTAINER_END_TO_END_ACCEPTANCE: REJECTED
PRODUCT_CONTAINER_WORKFLOW:              IMPLEMENTED_BUT_NOT_OWNER_ACCEPTED
GATE_2:                                  NOT_READY_FOR_OWNER_APPROVAL
VQR_6 / VQR_2A:                          IMPLEMENTED (VQR-6 owner-accepted;
                                         VQR-2A awaiting owner review)
PACKAGING_PRODUCTION:                    NOT_STARTED
COMPLETE_PRODUCT_CREATION:               DEFERRED_UNTIL_DEDICATED_UX
```

Program percentages (computed, see methodology; impl / validated / visual
/ owner / production):

```
Design OS overall     53.2   53.3   15.8   14.6    0.5
Product Container     51.5   51.4    9.4   14.0    0.0
Packaging             75.0   75.0   60.0   25.0    5.5
Complete Product      59.5   62.3    0.0    0.0    0.0
Core Platform         99.0   99.0    n/a   45.0    0.0
IRE                   75.5   75.5   39.0   30.0    0.0
Quality System        50.0   50.0    0.0   20.0    0.0
Review Board          62.5   62.5   20.0   20.0    0.0
Brand & Governance    75.5   75.5    n/a    0.0    0.0
Security              80.0   80.0    n/a    0.0    0.0
Ops                   37.5   35.5    n/a    0.0    0.0
Manufacturing         30.0   30.0    n/a    0.0    0.0
Future targets (5)     0.0 across the board
```

Confidence: HIGH for implementation/validation (commit+test evidence);
MEDIUM for visual-quality leaf grades of partially built items (30±10
bands); exact 0s and 100s are HIGH.

The headline correction versus every earlier roadmap: **Product Container
visual quality is 9.4%, not 35–45%.** Detection infrastructure (VQR-2A)
and the standalone owner-accepted M3 backbone do not become output quality
until they shape what the reconstruction emits.

## 3. Current-state reconciliation (all milestones)

Full per-node data (status, five percentages, evidence commits/tests/
screenshots, dependencies, blockers, next action) lives in
`progress_tracker.json` — 77 nodes. Summary by controlled vocabulary:

**OWNER_ACCEPTED** — shared front half; B4a target selector (`edf4fa0`);
reference system B4b-1/2/3 (`b3fa487`→`8249298`); reconstruction
single-authority VQR-6 (`96bdd19`); Packaging archetypes STE/RTE 1.2 arc
(`d4bec1b`, `f6c0570`, `cf37853`); IRE M3 backbone standalone (`32cedf9`,
identity `4ecc8e9df1d1`); Illustrator Gate A (`5820d6c`); Review Board
reference presentation (`f7436ca`).

**VALIDATED** (implemented + proven, not owner-accepted as results) —
lifecycle/gate plumbing; cost ledger; live updates; PC workflow mechanics,
profile workflow (UI-1…2B-2B), retry/recovery; VQR-2A fail-closed gate
(`5512cdc`, owner review pending); IRE engine core + target strategies;
Review Board core; reference/artifact/gate security; brand governance
audits (DIP-0A `01312b6`).

**IMPLEMENTED** (working, known gaps) — Packaging pipeline (open: generic
template cut/fold defect, ICC decision); provider adapters (no fallback
policy); Design Graph v1 (no bounds/closure/material data); Review Board
comparison (static only); font/colour governance (no authority service);
runtime parity (manual); roadmap tracking (this rebase).

**REJECTED** (the active recovery surface) — PC structural geometry,
concept fidelity, artwork composition, typography (all rejected with the
end-to-end acceptance, `7624255`); PC owner acceptance itself; Complete
Product pilot container stage (task 52, `6d1b685`).

**NOT_STARTED** — PC materials (VQR-5); Design Graph 2.0; golden visual
fixtures; concept gate; observatory; gate summary/timeline; asset
registry/component library; ops hardening (migration guard, health,
test-DB isolation); security production hardening; all five future
targets; Packaging production.

**DEFERRED / PRESERVED / BLOCKED** — Complete Product creation UX
(deferred until dedicated multi-stage UX; pipeline PRESERVED and
golden-fixture-tested); supplier workflow (deferred, 0 of 5 sent);
production evidence gates B–E (blocked on supplier selection); Other
custom archetype (OTHER_CUSTOM_PROFILE_RECONSTRUCTION_PENDING); Pacdora
(quarantined/superseded); STE/RTE 1.1 (LEGACY_REPRODUCTION_ONLY).

## 4. Quality-first architecture (nine layers)

Per-layer state and required work. (A) **Input quality** — references
secure and manifested; missing: concept-suitability gate (Q4), brand
component/asset registry (Q7). (B) **Design-intent extraction** — colors/
identity/motifs extracted; silhouette/composition of the selected concept
NEVER reaches geometry (the root cause); required: VQR-2B mask/feature
extraction. (C) **Design Graph** — v1 counts primitives; required: 2.0
with bounds, closure inventory, provenance, material zones (Q1) — without
it five of eight quality axes stay UNMEASURABLE. (D) **Structural
reconstruction** — coarse parametric backbone + A4 artboard in production
while the accepted M3 sits unused; required: VQR-1. (E) **Artwork
reconstruction** — placeholder zone-fill presented as final; required:
VQR-3 composing from the component library over Graph 2.0. (F)
**Typography engine** — run-count evidence only; required: authority
service (Q3) then VQR-4 measurement. (G) **Material realization** —
absent; required: VQR-5 via a reusable preview engine (Q13), strictly
non-manufacturing. (H) **Quality validation** — VQR-2A gate live and
fail-closed; required: measurements to feed it (2B/3/4) + golden visual
fixtures (Q2). (I) **Human correction & approval** — gates exist; missing:
adjustment studio (Q5) so acceptance does not demand perfect automation.

## 5. Design-quality acceptance rubric (§18 standard)

Owner acceptance of a Product Container result requires ALL of:

| # | Criterion | Verified by |
|---|---|---|
| 1 | Silhouette faithful to selected concept | VQR-2B metrics + eye |
| 2 | Closure family correct (real dropper assembly) | closure axis + eye |
| 3 | Product-derived artboard | artboard axis (already live) |
| 4 | BBROSE logo intact, professionally placed | logo axis + eye |
| 5 | Typography legible, refined, licensed | typography axis + authority service |
| 6 | Front artwork complete — zero placeholders | front-artwork axis (already live) |
| 7 | Intentional hierarchy and composition | composition axis + eye |
| 8 | Credible material presentation | VQR-5 preview + eye |
| 9 | Editable AI structure (meaningful named layers) | structural checks + Illustrator open |
| 10 | Presentation-quality PNG | eye |
| 11 | Honest authority language everywhere | VQR-6 contracts (already live) |
| 12 | All required axes MEASURED; all blocking axes PASS | `container_visual_quality_gate` |
| 13 | Explicit owner ACCEPT per category | acceptance walkthrough |

No average, score, or subset may override a blocking failure. Human
rejection is always authoritative over automated PASS.

## 6. Revised recovery sequence and critical path

Evaluated against the brief's alternative (§8) — changes adopted:
2B split for parallelism; Graph 2.0 + typography authority pulled forward;
adjustment studio inserted post-composition; concept gate added
pre-acceptance. VQR-1 confirmed first (geometry is the first divergence;
every measurement compares against what geometry emits).

```
                     ┌──────────────────────────────────────────┐
NOW ──► OWNER REVIEW │ Master Roadmap V3 + VQR-2A report        │
                     └──────────────┬───────────────────────────┘
                                    ▼
        R1  VQR-1  M3 backbone → reconstruct_container            [M, CRITICAL]
            product-scale artboard · dropper assembly · no generic caps
            ║ parallel: R2a VQR-2B-a concept-side masks + golden  [M, HIGH]
            ║                visual fixtures (Q2)
                                    ▼
        R2b VQR-2B-b reconstruction-side fidelity measurement     [M, CRITICAL]
            (aspect, contour, coverage, closure comparison → gate axes)
                                    ▼
        R3  Graph 2.0 (Q1) + Typography Authority (Q3)            [L, CRITICAL]
                                    ▼
        R4  VQR-3 front-artwork composition                       [L, CRITICAL]
            (component library Q7 feeds this; placeholder axis flips)
                                    ▼
        R5  VQR-4 typography measurement + refinement             [M, HIGH]
            ║ parallel: Q4 concept quality gate                   [S, HIGH]
                                    ▼
        R6  Q5 design adjustment studio (minimal)                 [L, HIGH]
                                    ▼
        R7  VQR-5 material realization (preview engine Q13)       [L, HIGH]
                                    ▼
        R8  ACC-2 new owner acceptance (fresh task; old evidence  [M, CRITICAL]
            preserved; rubric §5; explicit decisions)
```

Critical path: **R1 → R2b → R3 → R4 → R5 → R6 → R7 → R8** (R2a and Q4 off
the path). Owner reviews expected at: R1 exit (geometry vs M3 fixture),
R2b exit (measured fidelity), R4 exit (first real composition — likely the
highest-risk review), R6 (studio usability), R8 (acceptance). Principal
risks: R3 schema churn (mitigate: versioned graph, 1.1 kept readable); R4
is the largest quality jump (mitigate: R6 studio absorbs imperfection); R8
depends on concept suitability (mitigate: Q4).

**After acceptance** (per-target critical paths): Complete Product
(dedicated multi-stage UX over the preserved pipeline → composite
acceptance) → Display Stand (structural grid + product-fit engine; the
72-unit eyeliner display is the pilot brief) → Gift Set (tray/insert
geometry over Container+Packaging) → Marketing Material (asset reuse,
low structure) → Social Media (preset/frame system) → Exhibition Booth
(spatial reasoning; last deliberately). Target SDK (Q11) before Display
Stand — the fourth target must not be a fourth copy-paste.

## 7. Milestone detail — next five (entry/exit level)

**R1 · VQR-1 M3 integration** — Purpose: production geometry = accepted
geometry. Entry: owner authorization; M3 identity `4ecc8e9df1d1`
untouched. Deliverables: `reconstruct_container` builds bottles from the
M3 backbone + dropper assembly; artboard derived from confirmed profile +
margin policy (thresholds already centralized in `vqr2a_thresholds/1.0`);
Jar/Tube keep current backbone behind the same interface (explicitly
scoped follow-ups); artboard + closure axes flip to measurable. Exclusions:
artwork, typography, materials, thresholds tuning. Tests: golden
structural comparison vs the M3 fixture; gate-axis regressions; tasks
53–56 untouched. Rollback: strategy flag back to parametric backbone.
Effort M · Priority CRITICAL · Quality impact CRITICAL.

**R2a/R2b · VQR-2B fidelity measurement** — Purpose: silhouette/
composition become measured, not asserted. Deliverables: concept ink-mask
+ reconstruction mask extraction (local raster analysis, zero provider),
normalized aspect/contour/coverage metrics feeding the existing gate axes;
golden visual fixture library (good + deliberately bad). Exit: silhouette
axis PASS/FAIL on real measurement for the M3-integrated output. Effort
M+M · CRITICAL.

**R3 · Design Graph 2.0 + Typography Authority** — Purpose: the substrate
VQR-3/4 compose against and the gate measures against. Deliverables:
`container_design_graph/2.0` (components, bounds, provenance,
constraints); typography authority service over the 2B-3A font records
(allowed fonts, licensing, fallback, minimum sizes). Effort L · CRITICAL.

**R4 · VQR-3 composition** — Purpose: real front artwork; the placeholder
axis flips by construction, not by exception. Deliverables: approved-logo
placement from the component library, product name, supporting copy,
divider, motifs, hierarchy — independent editable objects in named layers
(01_STRUCTURE… 10_GUIDES_NONPRINTING). Guide zones never render as final
art. Effort L · CRITICAL.

**R5 · VQR-4 typography quality** — measurement + refinement over R3
output (scale, clipping, overlap, hierarchy, contrast, counters). Run
count is never a metric. Effort M · HIGH.

## 8. Architecture recommendations by horizon (§19)

**Immediate (inside recovery):** Graph 2.0 versioning discipline; keep
quality thresholds single-sourced; tracker updated every milestone
(validator enforces honesty); golden visual fixtures.
**After PC acceptance:** Target SDK; comparison mode + gate summary +
timeline in Review Board; component library expansion; design quality
score + observatory; artifact lineage registry (once revisions coexist);
Complete Product UX.
**Before production deployment:** startup migration guard (the 0026 drift
must be unrepeatable); automated revision parity; health endpoints;
structured logging with stable codes; CSP; upload malware scanning;
retention policy; backup/restore drills; test-DB isolation (per-worker
databases) to retire the exclusive-run constraint.
**Long-term:** provider-neutral contracts with explicit fallback;
reproducibility records (prompt hash, model, params, manifest identity);
central authorization policy service; performance passes.

## 9. Definitions of completion (unchanged, now tracker-enforced)

*Technically implemented* ≠ *visually validated* ≠ *owner accepted* ≠
*manufacturing-ready*. The tracker carries all four separately; the
validator forbids collapsing them. Manufacturing readiness additionally
requires supplier geometry/compatibility/materials/print-zone/tolerance
evidence and remains intentionally outside software acceptance.

---

## AMENDMENT — 2026-08-05: Strategic pivot to the palette programme

**P1 (dropper serum bottle) is FROZEN as an engine-validation reference.**
`P1_ENGINE_VALIDATION_REFERENCE: IMPLEMENTED` ·
`P1_GEOMETRY_PIPELINE: VALIDATED_PROVISIONALLY` ·
`P1_MATERIAL_SYSTEM: PROVEN_BUT_REQUIRES_GENERALIZATION` ·
`P1_OWNER_VISUAL_APPROVAL: NOT_GRANTED` ·
`P1_FURTHER_VISUAL_POLISH: DEFERRED` · `GATE_2: BLOCKED`.
No P1 V5. All P1 versions and evidence preserved unchanged. P1 is now a
regression fixture, not the active design priority.

**Two new programmes enter the roadmap:**

1. **GME-M1 — Generalized Material & Colour Engine** (`quality.generalized_material_engine`).
   Converts P1-specific hard-coded material logic into a parameter-driven
   system. Load-bearing rule: *geometry identity must not change when only
   material parameters change*. Adds `MATERIAL_SPECIFICATION_AUTHORITY` and
   `COLOUR_AUTHORITY` to the authority set; no render material ever confers
   manufacturing authority.

2. **PALT-M1..M7 — Palette Programme** (`palettes.*`). Eyeshadow, pressed
   powder, blush, contour, highlighter, mixed face, baked and refillable
   palettes as a **first-class Design Target**, explicitly not a bottle
   archetype. Architecture recommendation: **HYBRID** — a dedicated palette
   target owning geometry/layout/mechanism contracts, sitting on the shared
   engine layers proven by P1.

**Revised critical path:** PALT-M1 (owner architecture decision) → GME-M1 →
PALT-M2 (geometry + pan layout) → PALT-M3 (mechanism/open state) → PALT-M4
(powder finishes) → PALT-M5 (P1 pilot evidence) → PALT-M6 (artwork/.AI) →
PALT-M7 (P2/P3 pilots).

**Honest tracker effect:** design_os implementation 56.1 → 49.6, validation
56.2 → 47.3, visual quality 15.6 → 12.8, component review coverage 17.0 →
14.4. The delivered work did not shrink; the scope widened by a large
programme entering at 0%.

Full milestone documents: `docs/roadmap/palt_m1/`.
