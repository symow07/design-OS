# Quality Improvement Backlog — 2026-08-03

New capabilities beyond the existing VQR list, ranked by quality impact ×
owner value ÷ effort, with architectural leverage noted. Nothing here is
authorized; each item starts only on explicit owner instruction. No score
or ranking ever overrides a fail-closed blocking defect.

Effort scale: XS < 1 session · S ≈ 1 session · M ≈ 2–3 · L ≈ 4–6 · XL > 6.

## Tier 1 — on or beside the acceptance critical path

### Q1. Design Graph 2.0 (rank #1)
Semantic components with bounds, provenance, constraints: silhouette,
body/shoulder/neck/collar/bulb/closure, logo, typography runs, artwork
zones, motifs, material zones, alignment anchors, hierarchy.
**Value:** unlocks measurement for 5 of 8 quality axes AND gives VQR-3 a
composition substrate. **Effort:** L. **Risk:** medium (schema churn) —
mitigate by versioning (`container_design_graph/2.0`) and keeping 1.1
readable. **Timing: NOW-adjacent — prerequisite for VQR-3; start after
VQR-1.** Tracker: `ire.design_graph_v2`.

### Q2. Golden visual fixture library (rank #2)
Curated good + deliberately-bad outputs (wrong cap, A4 canvas, tiny logo,
clipped text, placeholder label, distorted wordmark…), pinned as
regression fixtures for the quality gate.
**Value:** makes the gate's thresholds calibratable and every future
regression visible. **Effort:** M. **Risk:** low. **Timing: with VQR-2B.**
Tracker: `quality.golden_fixtures`.

### Q3. Typography Authority Service (rank #3)
Central allowed-fonts/weights/licensing/fallback/minimum-size service;
consumes the existing 2B-3A font-authority records; feeds composition and
the VQR-4 axis.
**Value:** typography can never silently regress to unlicensed or
illegible text. **Effort:** M. **Risk:** low. **Timing: before/with
VQR-3.** Tracker: `brand_gov.font_governance`.

### Q4. Concept Quality Gate (rank #4)
Pre-selection suitability check: unclear silhouette, hidden closure,
unreadable branding, impossible geometry, excessive perspective →
concept flagged not-reconstructable BEFORE the owner selects it.
**Value:** stops doomed reconstructions and wasted provider spend at the
cheapest point. **Effort:** S–M (heuristics first, no provider calls).
**Risk:** low. **Timing: before the new acceptance run; parallelizable.**
Tracker: `quality.concept_gate`.

### Q5. Design Adjustment Studio (rank #5)
Human-in-the-loop editor before final AI export: move/scale logo, adjust
zones, reposition text, swap closure components, tweak proportions/colors;
writes back to the Design Graph, re-runs the quality gate.
**Recommendation on timing (the brief's open question):** AFTER the first
automatic composition pass (post-VQR-3), BEFORE material realization —
building the editor first would mean building against placeholder output,
and manual correction of composition should precede cosmetic dressing.
**Value:** acceptance no longer requires perfect automation; the owner
gains agency instead of a binary accept/reject. **Effort:** L (reuses the
profile-editor + dialog patterns). **Risk:** medium (graph mutation
integrity — mitigated by the gate re-running on every save). Timing:
between VQR-3/4 and VQR-5.

## Tier 2 — high value, after acceptance

### Q6. Concept↔Reconstruction comparison mode (Review Board)
Side-by-side/overlay/opacity/masks/bounding boxes. Builds directly on
VQR-2B measurements — schedule immediately after them (the data exists;
the UI is thin). Effort M. Tracker: `review_board.comparison`.

### Q7. Brand Component Library
Approved BBROSE logo/medallion/divider/motif/closure assemblies as
governed vector components (extends the DIP governance work; possession ≠
permission rules apply). Effort M. Feeds VQR-3 composition and every
future target. Tracker: `brand_gov.asset_registry`.

### Q8. Design Quality Score (supplementary, never overriding)
Weighted scorecard beside the fail-closed gate for trend visibility.
Effort S once axes are measured. Explicit rule: no score overrides a
blocking failure. Tracker: `quality.observatory`.

### Q9. Visual Quality Observatory
Rates over time: silhouette deviation, closure mismatch, typography
failures, placeholder detections, rejection reasons, provider concept
quality. Effort M. Needs several acceptance cycles of data to be useful.

### Q10. Unified gate summary + audit timeline (Review Board)
The §16 table view + event timeline. Effort S–M. After acceptance.

## Tier 3 — platform leverage, before target #4

### Q11. Target SDK
Formalized contracts (creation schema, reference policy, strategy, graph
schema, artifact roles, quality axes, board sections, gates). The three
existing targets ARE the SDK's test cases. Effort L. Do this before Gift
Set/Display Stand to stop per-target copy-paste divergence.

### Q12. Artifact lineage registry
Dedicated artifact rows (task, run, role, hash, validation, superseded-by,
authority). Justified once multiple targets × revisions coexist — not
before (the brief's own criterion). Effort M–L.

### Q13. Material Preview Engine
Controlled non-production renderer (frosted/clear glass, metals,
rose-gold, rubber bulb). This IS VQR-5's engine — listed here because it
should be built as a reusable service, not a container-only special case.
Effort L.

### Q14. Roadmap & Quality Dashboard (owner-facing, read-only)
`roadmap_status --json` already computes everything; a dashboard page can
render it. Effort S. After acceptance (the CLI + this document set serve
the need now).

## Explicit "never" list

- Auto-approval of any gate by score or AI judgment.
- Silent provider fallback.
- Automatic brand-master promotion from filenames.
- Image Trace or mass raster vectorization as a composition strategy.
- SVG output resurrection.
