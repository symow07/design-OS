# DIP-0C3b1 — Completion Report

**Slice:** the rights model — ownership states, licence states, business assertions,
confirmation states, permission defaults, transition rules, machine guards.
**Status:** complete, held for review before DIP-0C3b2.

**Scope guard:** this slice ships a **model**, not a workflow. No evidence
ingestion, no ledger, no canonical-master workflow, no permission granting, no
expiry processing, no queues, no reports on assets. Those are C3b2–C3b4.

Reproduce: `python -m tools.dip0c.run_c3b1` (reads no materials).
DIP-0C3a commit: **`2c00dda6e0595f85d78c189941cb5682bd0b9f57`**.

---

## Four layers, disjoint by construction

| # | Layer | Answers | Who may write it |
|---|---|---|---|
| 1 | `business_assertion` | "what the business **believes**" | a human |
| 2 | `machine_inference` | "what the evidence **suggests**" | machine, uncertain only |
| 3 | `human_confirmation` | "what a reviewer **decided**" | **HUMAN ONLY** |
| 4 | `permissions` | "what the system **may do**" | **HUMAN ONLY, per flag** |

`layers_are_disjoint: true` — their key sets do not intersect, so a layer *cannot*
write into another. "Human review does not mutate machine inference" is therefore a
structural property, not a discipline someone must remember.

## The core invariant

> **Machine code may only ever REDUCE certainty or permission — never increase it.**

Enforced centrally in `validate_transition()` and `machine_permission_update()`.
Made **checkable** by a certainty rank: a machine transition may only move to a rank
`<=` the current one. The validator enumerates *every* (from, to) pair on both axes
for both actors and confirms no machine transition increases rank.

## Ownership states (10)

- **Machine-permitted (5, all uncertain):** `OWNERSHIP_UNKNOWN` ·
  `BBROSE_OWNED_UNCONFIRMED` · `THIRD_PARTY_UNCONFIRMED` · `OWNERSHIP_DISPUTED` ·
  `QUARANTINED_PENDING_REVIEW`
- **HUMAN-ONLY (4):** `BBROSE_OWNED_CONFIRMED` · `THIRD_PARTY_CONFIRMED` ·
  `LICENSED_FOR_LIMITED_USE` · `JOINT_OR_CONTRACTED_USE`
- **Business assertion (1, its own layer):** `BUSINESS_ASSERTED_BBROSE` — ranked
  **equal to an unconfirmed guess**, because a belief is not evidence.

## Licence states (11) — a separate axis

- **Machine-permitted (5):** `LICENSE_UNVERIFIED` · `NO_LICENSE_EVIDENCE` ·
  `COMMERCIAL_USE_UNKNOWN` · `QUARANTINED` · `EXPIRED_OR_REVIEW_REQUIRED`
- **HUMAN-ONLY (6):** `LICENSE_APPROVED` · `INTERNAL_USE_ONLY` ·
  `ATTRIBUTION_REQUIRED` · `MODIFICATION_RESTRICTED` · `EMBEDDING_RESTRICTED` ·
  `REDISTRIBUTION_RESTRICTED`

Ownership confirmation never grants a licence; licence approval never proves
ownership.

## Transition matrix

| Axis | Actor | Legal | Refused |
|---|---|---|---|
| ownership | machine | **37** | **53** |
| ownership | human | 81 | 9 |
| licence | machine | **44** | **66** |
| licence | human | 110 | 0 |

**119 machine transitions refused**, by reason: `HumanOnlyStateViolation` **105** ·
`MachineMayNotIncrease` **14**. The full matrix — every pair, every verdict, every
reason — is committed in
[`c3b1_transition_matrix.json`](c3b1_transition_matrix.json).

## Permission defaults

13 fields, all denied: 9 boolean flags all `false`, `approved_products` `[]`,
`approved_markets` `[]`, `attribution_required` `null`, `review_expiry` `null`.

**A fully-owned, fully-confirmed asset still has every permission `false`.** Nothing
is derived from ownership. Machine may only narrow a list, may only flip a flag
`true → false`, and may not relax an attribution requirement.

## Machine guards verified (all true)

`machine_cannot_emit_human_only_ownership` ·
`machine_cannot_emit_human_only_license` ·
`machine_cannot_invent_a_business_assertion` ·
`machine_cannot_select_canonical_master` · **`machine_never_increases_certainty`** ·
**`machine_cannot_grant_any_permission`** (all 9 flags) · `machine_may_revoke`.

## Business-assertion behaviour

Recording *"this is our logo"*:

- changes **nothing else** (`assertion_changed_nothing_else: true`);
- grants **no permission**;
- is **not** a confirmation (`is_confirmation: false`);
- leaves the effective ownership at `OWNERSHIP_UNKNOWN`;
- **cannot on its own reach a confirmed state** — `can_confirm()` refuses with
  *"the business assertion is a BELIEF, not evidence"*.

And when the machine later **disputes** ownership, the assertion **survives
unerased**. `LOGO6.ai` is the case that matters: the business may sincerely believe
it owns that logo, and the file's own live text reads *"global logistics services"*.
Both remain visible to the reviewer.

## Tests / lint / integrity

- `pytest tools/dip0c/tests/test_c3b1.py` — **39 passed**.
- DIP-0C3a — **23 passed** (the guards were tightened; C3a is unaffected).
- `ruff check tools/dip0c` — clean.
- **Materials snapshot unchanged** — this slice reads no materials, and proves it.

## Findings requiring adjustment before C3b2

1. **A confirmation cannot yet be recorded anywhere.** `can_confirm()` says *whether*
   a reviewer may confirm; the append-only ledger that would *store* the decision is
   C3b2. Until it exists, the model can refuse but not remember.
2. **Reviewer authorisation is not modelled.** The model says "human only"; it does
   not check *which* human, nor that they are entitled to confirm ownership or
   approve a licence. That belongs with the ledger.
3. **`machine_revoke()` is implemented and tested but nothing calls it.** Expiry
   processing is C3b3; the mechanism is ready and unscheduled.
4. **Scope is flat.** `approved_markets` / `approved_products` are plain lists with
   no hierarchy. If approval needs to be inherited ("all EU markets"), that structure
   belongs in DIP-1, not here.

**HOLD** for review before starting DIP-0C3b2.
