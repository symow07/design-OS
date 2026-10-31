# DIP-0C3b1 — The rights state model

## Four layers, never collapsed

They live in four blocks whose key sets are **disjoint**, so no layer can silently
write into another (verified: `layers_are_disjoint`).

| # | Layer | Answers | Who may write it |
|---|---|---|---|
| 1 | `business_assertion` | "what the business **believes**" | a human, recorded verbatim |
| 2 | `machine_inference` | "what the evidence **suggests**" | machine — uncertain states only |
| 3 | `human_confirmation` | "what a reviewer **decided**" | **HUMAN ONLY** |
| 4 | `permissions` | "what the system **may do**" | **HUMAN ONLY, per flag** |

A user asserting *"this is our logo"* writes layer 1 and **nothing else**.

## The core invariant

> **Machine code may only ever REDUCE certainty or permission — never increase it.**

Enforced centrally in `rights_model.validate_transition()` and
`machine_permission_update()`, not re-implemented at call sites.

Machine **may**: mark disputed · quarantine · revoke · expire · reduce confidence ·
demand review.
Machine **may never**: confirm ownership · approve a licence · grant a permission ·
approve a canonical master · restore an expired permission · activate retrieval or
automatic use.

"Reduce" is made checkable by a **certainty rank**; a machine transition may only
move to a rank `<=` the current rank.

## Ownership states

**Machine-permitted (all uncertain):** `OWNERSHIP_UNKNOWN` (1) ·
`BBROSE_OWNED_UNCONFIRMED` (2) · `THIRD_PARTY_UNCONFIRMED` (2) ·
`OWNERSHIP_DISPUTED` (0) · `QUARANTINED_PENDING_REVIEW` (0)

**HUMAN-ONLY (rank 3):** `BBROSE_OWNED_CONFIRMED` · `THIRD_PARTY_CONFIRMED` ·
`LICENSED_FOR_LIMITED_USE` · `JOINT_OR_CONTRACTED_USE`

**Business assertion (rank 2, its own layer):** `BUSINESS_ASSERTED_BBROSE` — *a
belief is not more certain than a guess.* It is not a confirmation and no actor may
set it as a confirmed state.

## Licence states — a separate axis

**Machine-permitted:** `LICENSE_UNVERIFIED` (1) · `NO_LICENSE_EVIDENCE` (1) ·
`COMMERCIAL_USE_UNKNOWN` (1) · `QUARANTINED` (0) · `EXPIRED_OR_REVIEW_REQUIRED` (0)

**HUMAN-ONLY:** `LICENSE_APPROVED` (3) · `INTERNAL_USE_ONLY` (2) ·
`ATTRIBUTION_REQUIRED` (2) · `MODIFICATION_RESTRICTED` (2) ·
`EMBEDDING_RESTRICTED` (2) · `REDISTRIBUTION_RESTRICTED` (2)

**Ownership confirmation never grants a licence. Licence approval never proves
ownership.**

## Permissions

13 fields, every one independent, every one denied by default: 9 boolean flags
(`retrieval_allowed`, `automatic_use_allowed`, `production_use_allowed`,
`modification_allowed`, `embedding_allowed`, `redistribution_allowed`,
`public_export_allowed`, `approved_for_bbrose`, `approved_for_other_brands`) plus
`approved_products` `[]`, `approved_markets` `[]`, `attribution_required` `null`,
`review_expiry` `null`.

**Nothing is derived from ownership.** A fully-owned, fully-confirmed asset still
has every permission `false` until a human grants each one individually — pinned by
`test_ownership_confirmation_grants_no_permission`.

Machine may only *narrow* a list and only flip a flag `true -> false`; it may not
widen a list, grant a flag, or relax an attribution requirement.

## Confirmation requires evidence AND a decision

`can_confirm()` returns false unless **at least one REVIEWED evidence item** exists.
A business assertion is a belief, not evidence, and can never on its own reach a
confirmed state.
