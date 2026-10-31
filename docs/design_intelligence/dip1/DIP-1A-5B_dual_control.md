# DIP-1A-5B — authenticated dual control and historical authorization

Records and validates attestations. **It activates nothing.** A valid dual-control pair
proves that two authorized, authenticated reviewers attested to the same proposed decision;
it does not confirm ownership, approve a licence, select a canonical master, or activate a
palette.

## Attestations are DecisionEvents

An attestation is a protected signed DecisionEvent (`apps/accounts/attestation.py`). It
reuses the **existing** per-category `ATTEST_*` policy actions — no new policy action — so
`SYSTEM_ADMIN` is forbidden from substantive attestation by construction:

| category | action | authorizing roles |
|---|---|---|
| `TECHNICAL_AND_BRAND` | `attest_canonical_technical` | DESIGN_REVIEWER, BRAND_ADMIN |
| `RIGHTS_AND_OWNERSHIP` | `attest_canonical_legal` | LEGAL_REVIEWER |
| `COLOR_AND_BRAND` | `attest_palette_color` | BRAND_ADMIN, DESIGN_REVIEWER |
| `RIGHTS_AND_USE` | `attest_palette_rights` | LEGAL_REVIEWER |

The signed `action` (envelope) and signed `attestation_category` (payload) are cross-checked
**both ways**, at record time and in the validator.

## Reserved-field rejection (caller supplies facts, never security fields)

The caller supplies decision facts only. The service **rejects** (does not silently ignore)
any `payload_extras` carrying a reserved/managed field: `actor_id`, `role_used`,
`active_roles`, `authorizing_roles`, `authorization_snapshot`/`authz_snapshot`, `created_at`,
`sequence_number`, `previous_event_hash`, `signing_key_id`, `signature_algorithm`,
`content_hash`, `hmac_signature`, `policy_id`/`policy_version`, `decision_scope_hash`,
`attestation_status`, or any managed schema key.

## Authorization snapshot (internal, signed)

`authorization.build_authorization_snapshot(user, result, at)` is generated **internally**
and signed in the payload — a caller can never construct or modify it. It records:
`policy_id`, `policy_version`, `actor_id`, **observed** `user_is_active` and
`reviewer_enabled` (at append time), `active_roles`, `authorizing_roles`, `role_used`,
`assignment_ids`, `reason_code`, `action`, subject mapping, and `evaluation_timestamp`.

## Decision/scope binding

`decision_scope_hash` is **service-computed** — SHA-256 over canonical bytes of
(subject_type, subject_id, decision_type, decision_version, normalized_scope, sorted
evidence_refs, contradiction_present, binding-schema version). A caller-supplied
`decision_scope_hash` is rejected. **Two attestations combine only when their binding hashes
are identical** — never on human-readable names.

## `validate_dual_control(a, b, at=None)` — pure, read-only

A valid pair requires: two **verified** (chain-valid, via `verify_event`) attestations; two
**distinct authenticated user PKs** (one user with several roles is still one actor);
**complementary** categories (a substance half + a rights half); identical subject / decision
type / decision version / **binding hash**; compatible policy version; both currently
**effective**; and historical role validity for each. It **writes nothing** (tested: zero
DecisionEvents created across a full validate/read cycle).

## Effective state — fail closed, computed

`effective_attestation_state(event, at)` (read-only) fails closed on: a non-verifying event
(`CHAIN_INVALID`), **computed expiry** (`at >= review_expiry`, no event needed), or any
verifiable **lifecycle** event referencing it.

Lifecycle events (`ATTESTATION_REVOKED` / `_SUPERSEDED` / `_QUARANTINED` / `_RE_REVIEW_REQUIRED`)
reference the original via a **signed-payload `invalidates_event_id`**, *not* the
`supersedes_event` FK — this deliberately avoids the 1A-4 same-action supersession rule and
reuses the existing reduce-only actions (`REVOKE_DECISION`, `QUARANTINE_ASSET`,
`REQUIRE_RE_REVIEW`). Nothing is edited or deleted. `ATTESTATION_EXPIRED` needs **no** event.

## Historical role validity

`historical_role_validity(event)` evaluates authority **at the event's signed timestamp**
using the snapshot's `assignment_ids` and the assignment rows: `granted_at <= created_at <
expires_at`, and `revoked_at` null or `> created_at`, belonging to the actor, matching the
role, and the role authorized the action under the **pinned** policy version. **A later
revocation does not retro-invalidate a then-valid event.**

- **Policy versioning:** if the event's recorded policy version is unknown to this build,
  it returns `POLICY_REVIEW_REQUIRED` — it never silently reinterprets under the current
  policy, and never auto-invalidates a previously valid event.
- **Identity-state limitation:** `User.is_active` / `ReviewerProfile.reviewer_enabled` are
  mutable current-state fields, so their **append-time observed** values are preserved in
  the signed snapshot and used for historical checks. Every historical result carries the
  `IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY` warning (a review signal, not a silent pass). Full
  account/profile history persistence is deferred to DIP-1B or a later security extension.

## Verified-event interface

`decision_chain.verify_event(event)` verifies a single event's signed envelope (recomputed
content hash, pinned HMAC via the recorded key, algorithm, known role/action). Every
higher-level reader uses it rather than trusting a row because it exists.

## NOT in 1A-5B (→ 1A-5C)

The `verify_decision_chain` command, full-chain historical-authorization reporting
(JSON/human), the runbook set, migration reconciliation, and the final DIP-1A production
gate. No approval / permission / retrieval / automatic-use path is introduced.
