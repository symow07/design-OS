# DIP-0C3b3 — completion report

**Canonical-brand-master workflow, independent permission grants, scopes, expiry.**

Builds on C3b2 (`bcac12f`). The invariant is unchanged and now covers two more axes:
**machine code may only ever reduce certainty or permission, never increase it.**

---

## 1. What shipped

| Module | New in C3b3 |
|---|---|
| `config.py` | 7 human-only canonical states, 4 machine-allowed nominations, 7 `EFF_*` effective statuses; `machine_brand_master()` raises on every human-only value |
| `authz.py` | 13 new actions (23 total) incl. the two attestations; `APPROVE_CANONICAL_MASTER` narrowed to BRAND_ADMIN; `LEGAL_PERMISSIONS`; **import-time assertion** that `SYSTEM_ADMIN` appears in none of the 12 forbidden actions |
| `canonical_master.py` (new) | **dual control** (`attestation()`, `check_attestations()`), 15-item checklist split into two attestations, `scope()`, `scopes_overlap()`, `check_canonical_approval()` (8 gates), `detect_conflict()` |
| `permissions.py` (new) | per-flag `PREREQUISITES`, `check_grant()` (7 gates), `effective_permissions()` (pure, time-injected, fail-closed), `detect_expired()`, `machine_may_revoke_only()` |
| `ledger.py` | 10 new event types (23 total), `permission_block()`, `canonical_block()` (carries the attestations), `DUAL_CONTROL_EVENTS`; refuses an unnamed permission grant, a canonical event with no canonical block, a corrective event with no `supersedes_event_id`, and a **single-actor canonical approval** |
| `run_c3b3.py` | synthetic pilot + reconciliation |

Design rationale: [c3b3_canonical_and_permissions.md](c3b3_canonical_and_permissions.md).
Decisions: [c3b3_decisions.md](c3b3_decisions.md).
Limitations: [c3b3_known_limitations.md](c3b3_known_limitations.md).

## 2. Dual control (applied at review)

A canonical master now requires **two attestations from two distinct people**. The
15-item checklist is split so that neither attester is authorised to answer the
other's half — that split is what makes the rule enforceable rather than merely
stated.

| `TECHNICAL_AND_BRAND` (8 items) | `RIGHTS_AND_OWNERSHIP` (7 items) |
|---|---|
| DESIGN_REVIEWER *or* BRAND_ADMIN | **LEGAL_REVIEWER only** |
| brand identity, technical readiness, editable vector, proportions, symbol/wordmark, lockup, colour variants, version/date | ownership or permitted use, accepted evidence, licence status, restrictions & attribution, product scope, market scope, review expiry |

Final activation is **BRAND_ADMIN only** (`APPROVE_CANONICAL_MASTER` is now `(BRAND_ADMIN,)`),
reachable only once both attestations exist. The activator may be the technical
attester; **never** the legal one.

Separation is by **actor identity**: `technical_reviewer_id != legal_reviewer_id`.
One person holding both roles is still one person. An attester may only sign for items
they **personally confirmed**.

Enforced **twice**, deliberately — in `check_canonical_approval()` and again in
`ledger.event()` at the point of recording, so no code path can write the event by
skipping the check. Applies to `CANONICAL_MASTER_APPROVED` and
`CANONICAL_MASTER_REPLACED` only; **not** to nomination, variants, deprecation,
assertions, evidence or quarantine. Two people signing still grants **no permission**.

What deliberately did **not** change: `CONFIRM_OWNERSHIP` still admits `BRAND_ADMIN`
(the general ownership policy was not touched to satisfy the canonical rule), and no
other decision gained a second-reviewer requirement.

## 3. The four required properties

**Canonical status ≠ usable.** A `CANONICAL_MASTER_APPROVED` event grants nothing.
Every one of the 9 permissions stays `false`, status `DENIED_NO_GRANT`. Tested
(`test_canonical_master_does_not_equal_usable`) and demonstrated in the pilot.

**No implicit bundles.** One flag per grant event; the ledger refuses a
`PERMISSION_GRANTED` that names no flag. Granting retrieval grants retrieval and
nothing else. Prerequisites differ per flag — retrieval needs no licence, production
use needs `LICENSE_APPROVED`, and anything that exposes the asset outside the company
is `LEGAL_REVIEWER`'s alone.

**Expiry fails closed.** `effective_permissions()` returns `False` /
`RE_REVIEW_REQUIRED` the instant the review date passes — **with no
`PERMISSION_EXPIRED` event present**. The denial does not wait for a batch job. The
grant event itself is never edited; only the evaluation changes.

**Reading never writes.** `effective_permissions()` and `detect_expired()` are pure.
A test snapshots the ledger directory around both calls and asserts nothing was
created.

## 4. Pilot — synthetic, and the real ledger is still empty

| Scenario | Result |
|---|---|
| `logo.pdf` | nominated `BRAND_MASTER_CANDIDATE`; **no** canonical approval, no permissions |
| `LOGO6.ai` | canonical approval **refused** — a contradiction (its live text reads *"global logistics services"*) is unacknowledged. Allowed only once a human acknowledges it *with a reason*. **No approval was recorded either way.** |
| incomplete checklist | approval **blocked** — one unanswered item is not a pass |
| **dual control** | one BRAND_ADMIN attesting both halves → **refused** · technical attestation only → **refused** · legal attestation only → **refused** · two distinct authorised actors → **allowed** |
| `JOJIA LOGO.ai` | third-party ownership **confirmed** → **still every permission false**, and it can never be BBROSE's canonical master. Note the trap: `retrieval_allowed`'s prerequisites *do* admit `THIRD_PARTY_CONFIRMED`. Settling *whose* a logo is answers a question; it hands out no permission. |
| synthetic BBROSE master | passes the checklist → TEST_ONLY canonical event → **all 9 permissions still false** → one explicit TEST_ONLY retrieval grant → effective `True` in scope → **expires** → effective `False`, `RE_REVIEW_REQUIRED` |
| out-of-scope market | grant scoped to `EU`; evaluated for `US` → `DENIED_SCOPE_MISMATCH` |
| second canonical, same scope | **refused**, incumbent named, `POSSIBLE_CONFLICT` flagged, not replaced |

**6 illegal attempts refused:** `SYSTEM_ADMIN` selecting the canonical master ·
`SYSTEM_ADMIN` granting a permission · `BRAND_ADMIN` granting redistribution ·
**the ledger recording a canonical approval attested by one person** · machine
declaring `CANONICAL_BRAND_MASTER` · machine turning a permission `false → true`.

**Real ledger: 0 events.** No real asset has a canonical approval or a permission
grant. The runner exits non-zero if that ever stops being true. Synthetic records
live in `decisions/examples_TEST_ONLY/`.

## 5. A correction worth recording

A test I wrote asserted "no single role can answer the whole checklist". It failed:
`BRAND_ADMIN` can. I was one edit away from tightening `CONFIRM_OWNERSHIP` to
legal-only — **reversing a committed C3b2 policy to make a test I had just written go
green.**

The test was wrong, not the policy. `authz.py`'s docstring names the two excluded
roles explicitly — `SYSTEM_ADMIN` ("an admin") and `DESIGN_REVIEWER` ("a designer") —
and `BRAND_ADMIN`'s breadth is deliberate. I corrected my over-claiming comment and
re-pointed the test at a separation the policy *does* enforce: `APPROVE_CANONICAL_MASTER`
and `GRANT_LEGAL_PERMISSION` are disjoint, so no role can both declare a file
authoritative and release it publicly.

**I raised the underlying question — should a canonical approval require two people? —
rather than deciding it silently in code. The business answered: yes.** That is §2,
and it is why the checklist is now split and the rule enforced in two places. The
right outcome, and it arrived by surfacing the question rather than by my quietly
reversing a policy to make a test pass.

## 6. Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c/tests/test_c3b3.py` | **55 passed** (16 of them dual control) |
| `pytest tools/dip0c` (full slice) | **298 passed** |
| DIP-0A + DIP-0B | **343 passed** |
| Django | **537 passed**, 1 skipped |
| `ruff check tools/dip0c` | clean |
| `materials/` integrity | **unchanged** (pre/post snapshot) |
| real ledger | **0 events**, `validate()` clean |
| runtime | 0.16 s |

Machine-readable: [c3b3_reconciliation.json](c3b3_reconciliation.json).

## 7. Not in this slice

Review queues and the consolidated C3b report (**C3b4**). Purpose-scoped evaluation,
expiry warning windows, a market taxonomy with containment, and the guided
conflict-resolution workflow — all recorded in the limitations. Real authentication
and DB-backed roles remain DIP-1.

**HOLD for review before C3b4.**
