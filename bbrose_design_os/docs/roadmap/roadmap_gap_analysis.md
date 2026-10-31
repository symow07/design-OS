# Roadmap Gap Analysis — 2026-08-03

Audit of where the previous roadmap and its execution were weak, what the
repository actually shows, and what should stop. Ground truth: 399 commits
through `5512cdc`, 5,003-test suite, rejection record `7624255`, provider
ledger 226 rows / $27.0542 (zero calls across the entire recovery arc).

## 1. Conflicts found between roadmap statements and repository state

| Roadmap statement | Real state (evidence) | Correction |
|---|---|---|
| "Latest validated commit 96bdd19; VQR-2A authorized, not yet complete" | VQR-2A implemented + validated at `5512cdc` (27 server + 5 browser tests; live tasks 53–56 verified) | Master state corrected; historical statement preserved in the pasted roadmap text |
| "Product Container visual reconstruction quality 35–45%" | Evidence-weighted computation: **9.4%** (structural 25, fidelity 10, artwork 5, typography 10, materials 0, acceptance 0) | The old estimate silently credited detection infrastructure and standalone M3 work to output quality. Detection ≠ quality |
| "Full suite 4,971" | 5,003 at `5512cdc` | Rebased |
| "Complete Product capability 35–45%" | Pipeline preserved and golden-fixture validated (impl ≈ 60%), but visual quality 0% (its container stage rejected in the 2C pilot, task 52) | Split the number: engineering vs quality |
| Prior fidelity claim "task 53 overall MEASURED_PASS" | Semantically invalid — 7/8 axes UNMEASURED; fixed fail-closed in `5512cdc`; historical report preserved untouched | Recorded as the defining example of dishonest aggregation |

## 2. Structural weaknesses of the previous roadmap

### W1 — One-number progress (CRITICAL, root cause of misreporting)
"95% complete" described mechanics while the output was unusable.
**Fix (done):** five-dimension tracker; validator forbids the collapse.

### W2 — Technical completion mistaken for client value (CRITICAL)
Nine owner-accepted slices (B4b…UI-2B-2B) built a flawless corridor to a
rejected design. Nothing in the milestone structure asked "would a client
approve the output?" until the end-to-end walkthrough.
**Fix:** visual_quality dimension + fail-closed gate on the critical path
(done), acceptance rubric (Master Roadmap V3 §8), concept-quality gate
proposed in the backlog.

### W3 — Reactive sequencing (HIGH)
The owner-accepted M3 backbone existed since VQ-1 closeout but was never
scheduled into `reconstruct_container`; the workflow UX was built first.
Root cause: milestones were sequenced by workflow adjacency, not by
quality dependency.
**Fix:** revised critical path puts geometry (VQR-1) first among all
remaining work; Design Graph 2.0 explicitly precedes composition.

### W4 — Micro-slicing overhead (MEDIUM)
The B4b/UI-2 arc averaged ~1 commit per slice with full stop-point reports
each time. Auditability was excellent; velocity cost was real; several
"progress record" JSONs duplicate state (`b4b_2_progress.json` grew into a
de-facto master state file it was never designed to be).
**Fix:** `progress_tracker.json` is now the ONE machine state; slice
reports stay but reference it. Recovery slices are sized M/L (VQR-1,
VQR-2B, VQR-3), not micro.

### W5 — Duplicated authority logic (MEDIUM, now mostly resolved)
Four independent availability derivations produced rejection defect I.
VQR-6 centralized artifact/status authority; VQR-2A centralized quality.
Residual: readiness vocabulary exists in reconstruction_status, 2B-3D
production readiness, and packaging validators — acceptable while targets
differ, but a Target SDK should formalize the pattern before target #4.

### W6 — Manufacturing bureaucracy ahead of a real supplier (LOW impact,
already corrected)
Five supplier packages, .eml composition, sent-evidence validators — none
sendable because no real BBROSE factory was selected. Correctly parked as
OPTIONAL_FUTURE_MANUFACTURING_WORKFLOW; keep parked.

### W7 — Golden fixtures exist for structure, not for vision (HIGH)
`test_container_native_golden.py` pins graph/projection shape; nothing
pins what output should LOOK like. The rejected A4/placeholder output
passed every golden.
**Fix:** golden visual fixture library scheduled with VQR-2B.

### W8 — Deployment/test-infra gaps (MEDIUM)
Dev migration drift (0026 found unapplied pre-acceptance), manual parity
ritual, shared test Postgres forbidding concurrent pytest. Tracked as
`ops.*` nodes; scheduled before production deployment, not on the
acceptance critical path.

## 3. Work that should stop, merge, or stay parked (§17)

| Item | Verdict | Reason |
|---|---|---|
| Supplier outreach workflow (5 packages, validators) | **STAY PARKED** | No real supplier; reuse when one exists |
| Further Packaging archetype expansion (beyond STE/RTE 1.2, Skynte, opposed) | **DEFER** | Packaging is not the constraint; task-50 FIT_PASS input is the only open loop |
| `b4b_2_progress.json` as master state | **SUPERSEDED** | Preserved as history; `progress_tracker.json` is authoritative |
| Additional micro-sliced UI polish on Product Container | **STOP until quality recovers** | Zero effect on the rejection |
| New status/progress record schemas per slice | **MERGE** | Update the tracker instead |
| Pacdora integration | **STAY QUARANTINED** | Superseded by native pipeline |
| 2A-6 vector packaging flag-ON rollout | **DEFER** | Two open decisions (cut/fold defect, ICC) — bundle with a Packaging quality pass after PC acceptance |
| Legacy STE/RTE 1.1 surface | **KEEP AS-IS** | LEGACY_REPRODUCTION_ONLY already correct; removal is churn |
| Provider fallback automation | **DEFER** | Explicit-only fallback is a feature, not a gap, until acceptance volume exists |

## 4. Missing quality-critical work the old roadmap under-specified

1. **Design Graph 2.0** — bounds, closure inventory, provenance, material
   zones. Without it, five of eight quality axes are UNMEASURABLE forever.
2. **Typography authority service** — fonts/licensing/fallback BEFORE
   composition, not as a later VQR-4 afterthought.
3. **Concept suitability gate** — reject unreconstructable concepts before
   the owner selects one (cheap, prevents wasted provider spend + doomed
   reconstructions).
4. **Golden visual fixture library** — good AND deliberately-bad outputs.
5. **Owner adjustment loop** — manual correction studio so acceptance does
   not require perfect automation on the first pass.
6. **Brand component library** — the approved BBROSE logo as governed
   vector components; VQR-3 should compose from it, not re-derive.
