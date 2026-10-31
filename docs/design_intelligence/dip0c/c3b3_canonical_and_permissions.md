# DIP-0C3b3 — the canonical-master workflow and the permission model

Two questions that look like one and are not:

| Question | Answered by | Module |
|---|---|---|
| **Which file IS the brand?** | canonical status | `canonical_master.py` |
| **What may the system DO with it?** | permissions | `permissions.py` |

**A file can be the canonical BBROSE master and still have every permission
`false`.** That is not a gap in the model, it is the model. It has a test:
`test_canonical_master_does_not_equal_usable`.

---

## 1. Canonical states

Machine code may emit exactly four values, and all four are questions, not answers:

| Machine-allowed | Means |
|---|---|
| `BRAND_MASTER_CANDIDATE` | this file looks like it could be a master — a nomination |
| `POSSIBLE_VARIANT` | this file looks related to a master |
| `POSSIBLE_CONFLICT` | two files both claim the same scope |
| `REQUIRES_HUMAN` | the machine will not guess |

The seven states that actually decide something are unreachable from machine code —
`machine_brand_master()` raises `HumanOnlyStateViolation` on every one of them:

`CANONICAL_BRAND_MASTER` · `ALTERNATE_LOCKUP` · `MONOCHROME_VARIANT` ·
`COLOR_VARIANT` · `PRODUCT_SPECIFIC_VARIANT` · `DEPRECATED_VERSION` ·
`REJECTED_CANDIDATE`

A nomination confers nothing. `logo.pdf` is nominated in the pilot and it is neither
canonical nor usable.

## 2. The approval checklist — 15 items, an unanswered item is not a pass

`blank_checklist()` sets every item to `None`, and `None` **blocks approval**. The
distinction between "we checked and it's fine" and "nobody looked" is the entire
point; a schema that defaults to `False` would quietly erase it.

Each item records `result` / `confirmed_by` / `confirmed_at` / `notes`, and the whole
checklist is persisted **inside the approval event** — so the approval can never be
read without the reasoning that produced it.

`check_canonical_approval()` gates on eight things: **dual control** (below), an
authorised actor, a complete and passing checklist, confirmed ownership or explicitly
permitted use, at least one `REVIEWED_ACCEPTED` piece of evidence, an explicit reason,
acknowledged contradictions, and no scope conflict.

## 3. DUAL CONTROL — a canonical master takes two people

The checklist is **split into the two attestations**, and the split is what makes
"one person cannot do this alone" enforceable rather than aspirational: neither
attester is authorised to answer the other's half.

| `TECHNICAL_AND_BRAND` — DESIGN_REVIEWER *or* BRAND_ADMIN | `RIGHTS_AND_OWNERSHIP` — LEGAL_REVIEWER **only** |
|---|---|
| `brand_identity_confirmed` | `ownership_or_permitted_use_confirmed` |
| `technical_readiness_appropriate` | `reviewed_accepted_evidence_present` |
| `editable_vector_confirmed` | `license_status_confirmed` |
| `official_proportions_confirmed` | `restrictions_and_attribution_recorded` |
| `symbol_wordmark_relationship_confirmed` | `approved_product_scope` |
| `approved_lockup_type` | `approved_market_scope` |
| `approved_color_variants` | `review_expiry_or_no_expiry_reason` |
| `version_or_date_recorded` | |

**Final activation** is `BRAND_ADMIN`'s alone, and is reachable only once both
attestations exist. The activator may also be the technical attester — but **never**
the legal one.

**Separation is by actor identity, not by role.** `technical_reviewer_id !=
legal_reviewer_id`. One person holding both `BRAND_ADMIN` and `LEGAL_REVIEWER` is
still one person, and one person is exactly what dual control exists to prevent. An
attester may also only sign for items **they personally confirmed** — signing off on
someone else's ticks is not an attestation.

Enforced in **two** places, deliberately: in `check_canonical_approval()`, and again
in `ledger.event()` at the point of recording — so no code path can write the event
by skipping the check.

Dual control applies to `CANONICAL_MASTER_APPROVED` and `CANONICAL_MASTER_REPLACED`
(becoming the master, by either route). It does **not** apply to machine nomination,
variant classification, deprecation, business assertions, evidence submission, or
quarantine. Alternate lockups and variants may get their own policy later — but they
must never become the canonical master through that path.

Two people signing still grants **no operational permission**. Dual control decides
*which file is authoritative*; it switches nothing on.

## 4. Conflicts — the existing master is never silently replaced

Only one canonical master may be active per **brand + lockup + product + market +
period**. When a second one is requested for an overlapping scope, approval is
**refused** with a `CANONICAL CONFLICT` problem naming the incumbent.

The subtlety is in `scopes_overlap()`: an **empty** product/market list means *all
of them*, so it collides with everything. A naive set-intersection returns "no
overlap" for `[] ∩ ["EU"]` and would let a second master through — exactly backwards.

A machine may only ever raise the flag (`POSSIBLE_CONFLICT`) and list the permitted
resolutions — deprecate the former master, narrow one scope, reclassify one as a
variant, or reject the request. It resolves nothing.

## 5. Permissions — nine flags, each granted on its own

No implicit bundles. `PERMISSION_GRANTED` without a named flag is refused by the
ledger. Prerequisites are **action-specific**, because "may we retrieve this
internally" and "may we redistribute this publicly" are not the same question and
must not share a bar:

| Flag | Ownership | Licence | Legal only |
|---|---|---|---|
| `retrieval_allowed` | confirmed / licensed / joint / third-party | *none required* | |
| `automatic_use_allowed` | confirmed / licensed / joint | approved or internal | |
| `production_use_allowed` | confirmed / licensed / joint | **approved** | |
| `modification_allowed` | confirmed / licensed | approved or internal | |
| `embedding_allowed` | confirmed / licensed | approved | |
| `approved_for_bbrose` | confirmed / licensed / joint | *none required* | |
| `redistribution_allowed` | **confirmed** | **approved** | ✔ |
| `public_export_allowed` | **confirmed** | **approved** | ✔ |
| `approved_for_other_brands` | **confirmed** | **approved** | ✔ |

Anything that exposes the asset **outside the company** is `LEGAL_REVIEWER`'s alone
(`GRANT_LEGAL_PERMISSION`). A `BRAND_ADMIN` may switch on internal retrieval; it may
not publish.

`APPROVE_CANONICAL_MASTER` (BRAND_ADMIN) and `GRANT_LEGAL_PERMISSION`
(LEGAL_REVIEWER) are **disjoint** — no single role can both declare a file
authoritative and let it out of the building. Tested.

## 6. Expiry fails closed, and reading never writes

Two things are kept apart:

- the **grant event** — immutable, historical, never edited;
- the **effective value** — evaluated on demand, never stored.

An expired permission is not rewritten. `effective_permissions()` returns
`value=False`, `status=RE_REVIEW_REQUIRED` the instant the review date passes —
**without waiting for anyone to generate the audit event**. A system that only denies
once a nightly job has run is a system that grants access it should not, for as long
as that job is broken.

`effective_permissions()` and `detect_expired()` are **pure**: `now` is injected, and
a test asserts that calling them adds no file to the ledger. Merely *asking* what the
permissions are must never *change* what the permissions are.

Re-review restores nothing by itself. Only a new, authorised, human grant does.

## 7. What a machine may do to a permission

Turn it **off**. That is all. `machine_may_revoke_only()` raises
`MachineMayNotIncrease` on any `false → true`. Quarantine, revocation, scope
reduction and expiry all reduce; every one of them is available to automation.
Granting is not.
