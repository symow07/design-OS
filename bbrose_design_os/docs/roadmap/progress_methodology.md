# Progress Methodology — bbrose_progress_tracker/3.0

**Effective 2026-08-03.** This methodology exists because the previous
roadmap reported one number per area and that number hid the only thing
that mattered: a Product Container workflow at "95%" was rejected outright
by the owner. Progress reporting must never again let technical completion
impersonate design success.

## 1. Five dimensions, never one

Every tracker node carries five independent percentages:

| Dimension | Question it answers |
|---|---|
| `implementation_percent` | Is the code written? |
| `validation_percent` | Do automated tests + evidence prove it behaves as written? |
| `visual_quality_percent` | Would the OUTPUT survive the fail-closed visual quality gate and professional scrutiny? |
| `owner_acceptance_percent` | Has the owner explicitly accepted the result? |
| `production_readiness_percent` | Could this go to manufacturing/production with real-world authority? |

`null` means the dimension is **not applicable** to that node (e.g. visual
quality of the cost ledger). Null dimensions are excluded from parent
rollups with sibling-weight renormalization — they neither inflate nor
drag.

The canonical demonstration is Product Container itself:
implementation ≈ 51%, validation ≈ 51%, **visual quality ≈ 9%, owner
acceptance 14%, production 0%**. All five are true simultaneously. Any
single-number summary of that situation is a lie.

## 2. Rollup formula

For node *p* with children *c₁…cₙ* (weights *w₁…wₙ*, Σw = 1 within every
parent, enforced to 1e-6):

```
percent_d(p) = Σ ( wᵢ × percent_d(cᵢ) )  over children where percent_d(cᵢ) ≠ null
               ─────────────────────────
               Σ wᵢ                       over those same children
```

Rollups are always computed from **leaf** values. Parent/stored values in
`computed_views` are caches: the validator and the test suite recompute
them and fail on drift > 0.51 (one rounding step). There is no hand-edited
program percentage anywhere.

## 3. Weights

Weights encode importance, not file count. Rules:

- Quality-critical nodes must outweigh administrative nodes. In Product
  Container, the five design-quality nodes (structural geometry, concept
  fidelity, artwork composition, typography, materials = 0.59) outweigh
  the five mechanics nodes (0.31) — enforced by
  `test_quality_weight_dominates_administrative_weight`.
- Creating many small completed nodes cannot inflate a parent: new nodes
  take weight FROM siblings (weights must re-sum to 1), so adding
  administrative work dilutes itself, not quality.
- Domain weights at the root (Product Container 0.20, Packaging 0.10,
  IRE 0.08, Quality 0.07, Complete Product 0.07, Core 0.10, future
  targets 0.19 combined, governance/security/ops/mfg 0.19 combined) encode
  that the whole eight-target vision is the denominator — the overall
  Design OS number stays honest about how much does not exist yet.

## 4. Status vocabulary and rules

`NOT_STARTED, AUDITED, DESIGNED, IN_PROGRESS, IMPLEMENTED, VALIDATED,
OWNER_ACCEPTED, PRODUCTION_AUTHORIZED, BLOCKED, DEFERRED, PRESERVED,
REJECTED, SUPERSEDED`

Hard rules (validator-enforced):

1. `VALIDATED` / `OWNER_ACCEPTED` / `PRODUCTION_AUTHORIZED` require
   evidence (commits or tests) and 100% implementation on leaves.
2. `REJECTED`, `DEFERRED`, `PRESERVED`, `NOT_STARTED`, `BLOCKED` can never
   carry `owner_acceptance_percent > 0`.
3. `PRODUCTION_AUTHORIZED` requires `owner_acceptance_percent == 100`.
4. While the program records an active rejection, `pc.owner_acceptance`
   must be `REJECTED` at 0%.
5. Exactly one primary active milestone; active/next milestones must point
   at non-completed nodes.
6. "COMPLETE" is not a status. The closest legal claims are `IMPLEMENTED`
   (code exists), `VALIDATED` (proven to behave), `OWNER_ACCEPTED`
   (accepted result). A rejected end-to-end result keeps its engineering
   percentages and loses its quality/acceptance percentages — rejection
   does not erase work, and work does not erase rejection.

## 5. Confidence

Each node carries `confidence` (HIGH/MEDIUM/LOW) — how solid the
percentage evidence is. Nodes graded from commits + passing suites + owner
statements are HIGH. Estimates for unstarted work are inherently LOW and
their percentages are 0 anyway.

## 6. Update protocol (after every milestone)

1. Edit leaf nodes touched by the milestone (percentages, status,
   evidence, blockers, next_action, last_updated).
2. Regenerate `computed_views` (or edit and let validation catch drift).
3. Update `meta`: latest_validated_commit, active/next milestones,
   owner_decisions_pending, calculated_at.
4. Run `python manage.py roadmap_status` — it fails closed on any
   inconsistency.
5. Run `pytest apps/pipeline/tests/test_roadmap_tracker.py`.
6. Append to `roadmap_change_log.md`.

The tracker is committed with the milestone, so `git log` on
`progress_tracker.json` is the progress history.

## 7. Program views quoted anywhere else

Any percentage quoted in a report, README or conversation must come from
`manage.py roadmap_status` output at a named commit. Percentages that do
not trace to the tracker are estimates and must be labeled as such.
