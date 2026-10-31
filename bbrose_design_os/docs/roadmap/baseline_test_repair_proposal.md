# Baseline Test-Repair Proposal — 2026-08-04

**Status: DECLINED_BY_OWNER 2026-08-04 — DO NOT EXECUTE.**
Owner ruling (docs/roadmap/test_runner_policy.json): pytest is the canonical
runner; `manage.py test` is a non-canonical diagnostic runner; the R1–R4
manage.py-test repair below is NOT begun. This document is preserved as the
diagnostic record of the 14 unittest-runner findings. Only failures that
reproduce under FULL PYTEST are investigated (separately, app-defect vs
test-isolation defect, never mixed into intake records).

Original proposal text follows, unmodified:

**Status: PROPOSAL ONLY — NOT_STARTED, AWAITING_OWNER_AUTHORIZATION.**
No repair has been made. No fix was placed in any intake commit.

Record (per owner review of the reference intake):

- `BRANCH_TEST_HEALTH: DEGRADED`
- Observed baseline under `manage.py test` (unittest discovery, 1,316 tests):
  **6 failures + 8 errors**
- `INTAKE_INTRODUCED_NEW_FAILURES: false` — the identical 14-item set exists
  before and after the docs-only intake commit `407a5d0`.
- The full repository is **not** declared green.

## Central diagnostic finding (changes the shape of the repair)

The repository has **two test runners** with different semantics:

1. **pytest** (canonical: `pytest.ini` sets `DJANGO_SETTINGS_MODULE`, collects
   `test_*.py` + `tests.py`; historical suite counts ~5,0xx incl. 5,120 green
   at `644a44c` come from pytest).
2. **`manage.py test`** (unittest discovery; runs 1,316 tests; does NOT
   execute pytest fixtures and orders/isolates tests differently).

All 14 findings appeared under runner (2). Under pytest, **all 70 tests in the
four affected files pass today (verified 2026-08-04, isolated run, 9.8 s)**.
So the baseline degradation is a **runner-compatibility / test-isolation
problem in the test harness**, with one open question (F-2/F-3/F-4 order
dependence) that must be pinned down before anyone claims there is no
application defect underneath.

## Findings

### F-1 — `test_artwork_segments.py` · 5 ERRORS · CONFIRMED harness defect

- Tests: `test_discs_become_separate_segments`, `test_element_cap_respected`,
  `test_full_bleed_gradient_returns_empty`,
  `test_single_element_keeps_single_raster`, `test_uniform_image_returns_empty`
- Error: `AttributeError: 'SegmentArtworkTests' object has no attribute 'tmp_path'`
- Cause (confirmed by reading the file): the class is a Django `SimpleTestCase`
  whose `tmp_path` comes from `@pytest.fixture(autouse=True) def _tmp(...)`.
  Pytest injects it; the unittest runner never executes pytest fixtures, so
  every test touching `self.tmp_path` errors.
- Responsible commit: `f26a572` ("Components .ai: each motif element cut into
  its own movable object") — the file was born with the pytest-only idiom.
- Classification: **test-harness defect** (runner incompatibility). The
  application code (`services/artwork_segments.py`) is exercised and passes
  under pytest.
- Repair: replace the fixture with runner-neutral `setUp()` using
  `tempfile.TemporaryDirectory` (`pathlib.Path`), teardown via `addCleanup`.
  Mechanical, zero app-code risk.

### F-2 — `test_phase11.py` RevisionWorkflowTests · 3 FAILURES · order/state-dependent

- Tests: `test_rerun_images_skips_creative_and_prompt_stages`
  (`mock_gen.call_count 0 != 2`), `test_rerun_prompts_skips_creative_director_only`
  (`call_claude` called 0 times), `test_rerun_supersedes_old_images_and_default_
  payload_hides_them` (`superseded` False).
- All three say the same thing: **the rerun never executed** under the full
  unittest run, while the same tests pass in isolation (pytest 70/70).
- Supporting evidence from the full-run log: `WARNING Conflict:
  /dashboard/tasks/3/gate1-regeneration/confirm/` — a 409 guard fired during
  the run, i.e. some lock/idempotency/state guard persisted across tests.
- Likely responsible layer: a later-added rerun/regeneration guard (candidate
  commits to bisect: `d2433b6` "four first-production complaints",
  `b3fa487` B4b-1 secure reference core, and the 2A-6E/2B-3V regeneration
  guard series) interacting with **shared state that unittest ordering does
  not reset** (Django cache-based locks, module-level singletons, or on-disk
  `var/` ledger/lock artifacts).
- Classification: **test-harness/isolation defect (probable)** — but the
  repair session MUST verify the guard is not wrongly persisting state in
  production too (a real app defect would look exactly like this).

### F-3 — `test_gate1_reference_regeneration.py` · 1 ERROR + 1 FAILURE · order/state-dependent

- Tests: `test_full_regeneration_with_provenance`
  (`mock_edit.call_args` is None → the edit call never happened),
  `test_repetitive_prompts_fail_closed_before_image_spend`
  (`mock_pe.call_count != 2`).
- Same signature as F-2: flow refused before reaching the mocked provider
  layer under full-run state; passes in isolation.
- Likely responsible commit: `3019bf3` (2B-3V-CORR canonical visual-reference
  resolver + pre-spend + reject) or `1df7fb5` (2A-6E-CORR-5 job-scoped failure
  semantics) — both added refusal paths in exactly this flow.
- Classification: **test-harness/isolation defect (probable)**, same
  verification duty as F-2.

### F-4 — `test_container_confirmation_2c2e.py` · 2 ERRORS + 2 FAILURES · order/state-dependent

- Tests: `test_material_separation_and_concept_fidelity_measured`
  (`KeyError: 'container_material_objects/1.0'`),
  `test_review_board_presents_gate_2_stage`
  (`KeyError: 'Next required human action'`),
  `test_confirmation_reconstructs_and_stops_at_gate_2` and
  `test_rejection_survives_the_corrected_rerender`
  (both: `task.status != "awaiting_gate_2"`).
- Both spec key and label still exist in current code
  (`targets/container/__init__.py`) — these are NOT renamed-key staleness.
  The reconstruction evidently failed/refused earlier in the flow under
  full-run state, leaving spec/board/status incomplete.
- Likely responsible layer: post-2C-2E authority slices that added refusal
  semantics ahead of `awaiting_gate_2` (candidates: VQR-6 `96bdd19` artifact/
  status authority, VQR-2A `5512cdc` fail-closed visual-quality gate)
  combined with the same shared-state leak as F-2/F-3.
- Classification: **test-harness/isolation defect (probable)**, same
  verification duty.

## Proposed repair order (no work begun)

1. **R1 — F-1 mechanical fix** (runner-neutral tmp dir). Smallest, fully
   diagnosed, zero app risk. Turns 8 errors → 3.
2. **R2 — Deterministic reproduction of the order dependence** (diagnosis
   only): run `manage.py test` bisected by app/test-module subsets to find
   the minimal pair (contaminating test → failing test); inspect the 409
   Conflict guard's backing store (cache vs DB vs file).
3. **R3 — Isolation fix at the identified layer**: reset the specific shared
   state (cache/lock/ledger) in the guilty tests' setUp OR fix the app-side
   state holder if R2 shows production-relevant persistence (that finding
   would be re-classified as an application defect and reported before
   fixing).
4. **R4 — Runner policy decision (owner)**: declare pytest the canonical
   runner in docs + CI and keep `manage.py test` best-effort, or require
   dual-runner cleanliness. Recommendation: pytest canonical + R1-style
   neutrality where trivial.

Exit criteria: `manage.py test` full run 0F/0E (or an owner-accepted runner
policy that excludes it), full pytest suite green, no app behavior change
without its own review.

**Awaiting owner authorization before any of R1–R4 begins.**
