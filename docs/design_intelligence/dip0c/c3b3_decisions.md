# DIP-0C3b3 — decisions

## D0. A canonical master is under DUAL CONTROL — two attestations, two people
Applied at review, on the business's instruction. The 15-item checklist is **split**
into a `TECHNICAL_AND_BRAND` attestation (DESIGN_REVIEWER *or* BRAND_ADMIN) and a
`RIGHTS_AND_OWNERSHIP` attestation (LEGAL_REVIEWER **only**). Final activation is
BRAND_ADMIN's, and is reachable only once both attestations exist.

The split is what makes the rule enforceable rather than aspirational: **neither
attester is authorised to answer the other's half**, so the checklist cannot be
completed by one person even in principle.

Separation is by **actor identity**, not by role — `technical_reviewer_id !=
legal_reviewer_id`. A single person holding both roles is still a single person, and
that is precisely what dual control exists to prevent. An attester may also only sign
for items they **personally confirmed**.

Enforced **twice, deliberately**: in `check_canonical_approval()` and again in
`ledger.event()` at the point of recording, so no code path can write the event by
skipping the check. It applies to `CANONICAL_MASTER_APPROVED` and
`CANONICAL_MASTER_REPLACED` only — not to nomination, variants, deprecation,
assertions, evidence or quarantine.

Two people signing still grants **no operational permission** (D2 is unaffected).

## D1. An unanswered checklist item blocks approval; it is not a pass
`blank_checklist()` uses `None`, not `False`. "We looked and it failed" and "nobody
looked" are different facts, and a boolean cannot hold both. Approval requires all 13
items answered **and** answered true.

## D2. Canonical approval and permission granting are separate acts
A `CANONICAL_MASTER_APPROVED` event grants **nothing**. Permissions stay `false`
until each one is granted individually. This is the tested scenario
`test_canonical_master_does_not_equal_usable`, and it is the whole reason the two
modules do not import each other's decisions.

## D3. Prerequisites are per-permission, not a single "has rights" bar
Retrieval needs no licence (reading a file we own internally is not a licensing
question); production use requires `LICENSE_APPROVED`; redistribution, public export
and use for other brands additionally require `LEGAL_REVIEWER`. One generic gate
would have made "we may look at it" imply "we may publish it".

## D4. Expiry fails closed, evaluated, not stored
The grant event is immutable and untouched by expiry. The **evaluation** denies the
moment the date passes, with no dependence on an audit event having been generated.
The `PERMISSION_EXPIRED` event is for the record; the denial does not wait for it.
Tested with `now` injected, and with no expiry event present.

## D5. Reading never writes
`effective_permissions()` and `detect_expired()` are pure functions. A test snapshots
the ledger directory before and after calling them and asserts it is unchanged.
Otherwise a read-only report could mutate the audit trail as a side effect.

## D6. An empty scope list means ALL, and therefore collides with everything
`scopes_overlap()` treats `products: []` / `markets: []` as unrestricted. A naive
set-intersection would compute `[] ∩ ["EU"] = ∅` → "no conflict", and admit a second
canonical master for a scope already covered. The empty list is the *broadest* claim,
not the narrowest.

## D7. A conflict is refused, never resolved
When a requested canonical scope overlaps an active master, approval is **blocked**
and the incumbent is named. The machine may raise `POSSIBLE_CONFLICT` and enumerate
the permitted resolutions; it never silently replaces the first master. Rewriting
which file is the brand, without a human, is precisely the failure this milestone
exists to prevent.

## D8. `SYSTEM_ADMIN` may only ever reduce
It can quarantine, revoke, expire and demand re-review. It may **not** confirm
ownership, approve a licence, grant any permission, or select the canonical master.
Administrative power is not legal authority, and this is asserted **at import time**
in `authz.py` over all 10 forbidden actions — not left to convention.

## D9. Approving the canonical master and releasing it publicly are disjoint roles
`APPROVE_CANONICAL_MASTER` = (BRAND_ADMIN); `GRANT_LEGAL_PERMISSION` =
(LEGAL_REVIEWER). No role holds both. Deciding a file *is* the brand and deciding the
world may *have* it are never the same person's call.

## D10. The pilot is synthetic; the real ledger stays empty
No real asset receives a canonical approval or a permission grant. The four
scenarios run against `TEST_ONLY_*` assets and land in
`decisions/examples_TEST_ONLY/`. `LOGO6.ai`'s approval path is *evaluated* (refused,
then allowed once the contradiction is acknowledged) but **no approval is recorded** —
a fabricated approval in the ledger would be indistinguishable from one a human made.
The runner exits non-zero if the real ledger is non-empty.

## Correction made during this slice

I initially read the comment in `authz.py` ("ownership is a LEGAL determination — a
designer or an admin cannot decide it") as excluding `BRAND_ADMIN`, and wrote a test
asserting no single role can answer the whole checklist. It failed: `BRAND_ADMIN`
can. I was about to tighten `CONFIRM_OWNERSHIP` to legal-only — i.e. reverse a
committed C3b2 policy to satisfy a test I had just written.

That reading was wrong. The `authz.py` docstring names the two excluded roles
explicitly: `SYSTEM_ADMIN` ("an admin") and `DESIGN_REVIEWER` ("a designer").
`BRAND_ADMIN` is the broad brand-authority role and its breadth is deliberate and
documented. The over-claim was in **my** comment, so I corrected the comment and the
test, and raised the underlying question — *should a canonical approval require two
people?* — as an open item for the business rather than deciding it silently in code.

**The business answered it: yes.** That is D0. Note what did *not* change:
`CONFIRM_OWNERSHIP` still admits `BRAND_ADMIN` (the general ownership policy was not
touched to satisfy the canonical rule), and no other decision gained a second-reviewer
requirement. Dual control was added exactly where it was asked for, and nowhere else.
