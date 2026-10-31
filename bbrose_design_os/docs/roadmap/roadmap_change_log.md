# Roadmap Change Log

## 2026-08-03 — Master Roadmap V3 (roadmap rebase)

Baseline audited: `5512cdc` (399 commits, 5,003-test suite, ledger 226 /
$27.0542). Material differences from the previous master roadmap:

1. **Corrected currency.** Previous text carried `96bdd19` as latest and
   VQR-2A as "authorized, not complete". Reality: VQR-2A implemented +
   validated at `5512cdc`. Historical text preserved; master state
   corrected.
2. **Five-dimension progress replaces single percentages.** The old
   "Product Container 95% / visual quality 35–45%" pair becomes computed,
   evidence-weighted numbers: impl 51.5 / validation 51.4 / visual 9.4 /
   owner 14.0 / production 0. The visual number FELL because detection
   infrastructure and standalone M3 work no longer count as output
   quality. Overall Design OS: 53.2 / 53.3 / 15.8 / 14.6 / 0.5.
3. **One machine-readable authority.** `progress_tracker.json` (77 nodes,
   validated by `manage.py roadmap_status` + 25 tests) supersedes
   `b4b_2_progress.json` as master state. The old file is preserved as
   history and stops accumulating new state.
4. **Recovery sequence revised** (see master_roadmap_v3.md §6):
   - VQR-1 stays first (geometry is the first divergence).
   - VQR-2B is split: concept-side measurement + golden fixtures may run
     in PARALLEL with VQR-1; reconstruction-side comparison follows VQR-1.
   - Design Graph 2.0 inserted as an explicit prerequisite of VQR-3
     (previously implicit and unscheduled — the same omission that left
     M3 unintegrated).
   - Typography authority service moved BEFORE composition (VQR-4 keeps
     the measurement/refinement half).
   - Design Adjustment Studio inserted after VQR-3/4, before VQR-5.
   - Concept Quality Gate added before the new acceptance run.
5. **Stopped/parked list made explicit** (gap analysis §3): supplier
   workflow stays parked; PC UI polish frozen until quality recovers;
   per-slice progress-record schemas merged into the tracker; Pacdora
   stays quarantined.
6. **Acceptance rubric formalized** (master_roadmap_v3.md §8) — owner
   acceptance now has a reusable checklist; averages can never override
   blocking defects.
7. **New backlog adopted** (quality_improvement_backlog.md) — Design
   Graph 2.0, golden visual fixtures, typography authority, concept gate,
   adjustment studio ranked into the recovery path; Target SDK and
   artifact lineage scheduled before target #4, not now.
8. **Weights policy** — quality-critical nodes structurally outweigh
   administrative nodes (validator-enforced), so future micro-slices
   cannot inflate progress.

Owner decisions this rebase does NOT make: authorizing VQR-1; accepting
VQR-2A; changing any target's activation status.

## 2026-08-03 — V3 tracker amendments (owner review result)

Owner accepted Master Roadmap V3 with mandatory amendments; VQR-2A
OWNER_ACCEPTED; VQR-1 AUTHORIZED_AFTER_TRACKER_AMENDMENT. Schema bumped to
`bbrose_progress_tracker/3.1` (86 nodes). Changes:

1. **Rejected capability split from recovery work** — four
   `pc.current_*` REJECTED nodes (historical evidence attached) beside
   `pc.vqr1_m3_integration`, `pc.vqr2b_*`, `pc.vqr3/4/5_*` NOT_STARTED
   recovery nodes. Future progress accrues only on recovery nodes.
2. **Owner-acceptance semantics** — `pc.owner_acceptance` split into
   `pc.acceptance_workflow` (VALIDATED mechanism) and
   `pc.acceptance_outcome` (REJECTED, vq 0, oa 0). End-to-end rejection
   gates (`meta.acceptance_gates`) force the pc and design_os
   owner-acceptance rollups to **0** while the outcome is REJECTED;
   accepted subsystem reviews are reported separately as
   `component_review_coverage_percent` (pc 12.0%, program 16.3%).
3. **Critical-path nodes added** — `pc.design_adjustment_studio` (deps
   VQR-3+VQR-4), `pc.vqr2b_concept_analysis` /
   `pc.vqr2b_reconstruction_measurement`, `quality.golden_concept_fixtures`
   (renamed), `review_board.minimum_fidelity_comparison` (VQR-2B
   deliverable). `meta.critical_path_nodes` is now validator-checked for
   existence and dependency order.
4. **Minimum Brand Component Library** (`brand_gov.minimum_component_
   library`) is a VQR-3 dependency in R3; expanded library stays
   post-acceptance.
5. **Confidence** — estimated partial visual grades carry MEDIUM +
   `confidence_basis: EVIDENCE_INFORMED_ESTIMATE`.
6. **Parent statuses** — future targets NOT_STARTED, Complete Product
   PRESERVED, Manufacturing DEFERRED; validator forbids IN_PROGRESS
   parents with no active descendant.
7. **Percentage effects** — PC visual quality 9.4 → **2.2%** (recovery
   nodes no longer blend with current-output estimates); PC owner
   acceptance 14 → **0** (gated); Design OS owner acceptance 14.6 → **0**
   (gated); Design OS visual 15.8 → 12.4%.

Pending owner decisions reduced to exactly one: start VQR-1 after this
correction validates (authorization already granted).
