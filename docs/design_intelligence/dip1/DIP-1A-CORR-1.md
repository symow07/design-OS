# DIP-1A-CORR-1 — authorization snapshot contract correction

Status: corrected; pending review. Code correction commit: `3046333`.

This correction temporarily reopened DIP-1A for one verified correctness defect. It did not
add or change any intelligence persistence, asset approval, operational permission,
retrieval, automatic-use, evidence, UI, or role-management capability.

## Defect proof and root cause

Before production code changed, an end-to-end regression created authorized persisted users
and assignments, then called the real `grant_reviewer_role`, `revoke_reviewer_role`,
`enable_reviewer_profile`, and `disable_reviewer_profile` services. The production
`verify_decision_chain` path inspected the resulting four-event chain and returned four
fatal `INVALID` findings: each signed snapshot disagreed with its signed event envelope.
No event was crafted or monkeypatched for this proof.

The role services emitted the older 1A-5A reduced mapping. It omitted the schema marker,
policy id, actor, identity observations, actor assignment ids, action, subject, and
evaluation timestamp, and named target-history ids as `prior_assignment_ids`. The 1A-5C
verifier correctly interpreted any `authz_snapshot` as the complete 1A-5B contract. The
role-service tests checked only selected payload fields and never ran full-chain
verification, so the producer/verifier mismatch escaped coverage.

## Selected contract

Option A was selected: every current protected DecisionEvent service uses the existing
complete `authz_snapshot/1.0` builder. Role services now call
`authorization.build_authorization_snapshot(actor, result, evaluation_timestamp)` with the
same timestamp used for their service-level authorization. Target-assignment history stays
in the role event's domain payload; `assignment_ids` inside the authorization snapshot
always identifies the acting user's authorizing assignments.

`authz_snapshot/1.0` has one exact vocabulary:

`snapshot_schema`, `policy_id`, `policy_version`, `actor_id`, `user_is_active`,
`reviewer_enabled`, `active_roles`, `authorizing_roles`, `role_used`, `assignment_ids`,
`reason_code`, `action`, `subject_type`, `subject_id`, `evaluation_timestamp`.

The verifier requires the explicit schema and exact field set; validates types, canonical
role/assignment lists, identity state, the signed envelope mapping, policy authorization,
deterministic role selection, timestamp ordering, and live assignment corroboration; and
never fills missing security fields from current database state. A schema change requires a
new signed `snapshot_schema` value and an explicit historical verifier branch.

Every snapshot field is nested in `DecisionEvent.payload`, which is part of the canonical
event document covered by the content hash and HMAC. The event, linkage hash, and signed
head therefore bind the snapshot cryptographically.

## Producer/verifier matrix

| event action | producer | before correction | snapshot after correction | verifier requirement | historical implication |
|---|---|---|---|---|---|
| `grant_reviewer_role` | `role_services.grant_reviewer_role` | local reduced, unversioned builder; target `prior_assignment_ids` | canonical `authz_snapshot/1.0`; actor `assignment_ids` | exact v1.0 contract plus envelope/policy/history checks | future events use v1.0; domain `prior_assignment_ids` remains separately signed |
| `revoke_reviewer_role` | `role_services.revoke_reviewer_role` | local reduced, unversioned builder; target assignment id | canonical `authz_snapshot/1.0`; actor `assignment_ids` | exact v1.0 contract plus envelope/policy/history checks | future events use v1.0; revoked target assignment remains a domain field |
| `enable_reviewer_profile` | `role_services.enable_reviewer_profile` | local reduced, unversioned builder | canonical `authz_snapshot/1.0` | exact v1.0 contract plus envelope/policy/history checks | future events use v1.0 |
| `disable_reviewer_profile` | `role_services.disable_reviewer_profile` | local reduced, unversioned builder | canonical `authz_snapshot/1.0` | exact v1.0 contract plus envelope/policy/history checks | future events use v1.0 |
| four `attest_*` actions | `attestation.record_attestation` | canonical `build_authorization_snapshot` | unchanged canonical v1.0 | exact v1.0 plus attestation semantics | existing v1.0 interpretation unchanged |
| attestation revoke/quarantine/re-review actions | `attestation.record_attestation_lifecycle` | canonical `build_authorization_snapshot` | unchanged canonical v1.0 | exact v1.0 plus lifecycle semantics | existing v1.0 interpretation unchanged |
| all above | `decision_chain.append_decision` | signs the service payload; does not invent or repair snapshots | unchanged | content hash, HMAC, linkage, algorithm, actor/action/role, signed head | lower-level writer remains a single signing primitive, not a second snapshot vocabulary |
| all above | `chain_verification._verify_snapshot` | assumed complete fields but did not enforce schema/field vocabulary | validates declared v1.0 exactly | missing, extra, wrong-version, or inconsistent signed fields are fatal `INVALID` | no silent reinterpretation and no current-state inference |

## Historical database status

The configured local PostgreSQL server was reachable during this correction, but the
configured `bbrose_db` does not contain the `accounts_decisionevent` table: the DIP accounts
migrations have not been applied there. Consequently it contains no installed DIP ledger
from which a DecisionEvent count, action distribution, snapshot distribution, or chain
result can be produced. Fresh-database migration tests still establish a genesis head and
zero seeded DecisionEvents.

No signed event was rewritten or re-signed. No compatibility branch for the reduced mapping
was added because no real reduced-schema event was found in the available database and the
mapping had no schema marker by which it could be safely interpreted. If such an event is
found in another deployment, verification will fail explicitly instead of guessing; that
deployment must be reported and reviewed before any compatibility schema is introduced.
The production change therefore affects future role lifecycle event production only.

No database schema migration was required.

## Legacy authority characterization (read-only)

These paths were inventoried only. Nothing below was removed, redirected, or granted DIP
authority by this correction.

| value/path | consumer and effect | classification |
|---|---|---|
| `DesignReference.active` | Admin/imported rows are eligible only when active; `reference_index.select_reference_records` filters, scores, and resolves their image paths | `LEGACY_RETRIEVAL` |
| selected `DesignReference` rows and disk fallback | `brand_context.get_design_references` returns selected paths or newest files under `MEDIA_ROOT/references` | `LEGACY_RETRIEVAL` |
| selected reference images/anatomy | `CreativeDirectorAgent.run` attaches images and anatomy to the Claude request; `ARIAAgent._top_reference_anatomy` feeds the closest anatomy into prompt construction | `LEGACY_AUTOMATIC_INPUT` |
| selected reference paths | `ImageProducerAgent._reference_inputs` passes them directly to `openai.images.edit` | `LEGACY_AUTOMATIC_INPUT` |
| reference tag/anatomy mutations | import/tagging commands write machine tags and anatomy used by selection; admin can edit the same fields | `UNKNOWN_REQUIRES_REVIEW` |
| Gate 1 endpoints, including batch approval | Legacy `IsReviewer` permission, status transition, and `GateDecision` control whether the pipeline resumes | `LEGACY_WORKFLOW_CONTROL` |
| `GeneratedImage.is_approved` and `gate_1_approved` | `ARIAAgent.resume_after_gate_1` makes the selected image the automatic input to target generation; retry logic reuses the approved image | `LEGACY_AUTOMATIC_INPUT` |
| dimension gate and its `GateDecision` | Reviewer-confirmed dimensions and panel information drive dieline, editable AI, production PDF, and spec generation | `LEGACY_PRODUCTION_AUTHORITY` |
| Gate 2 endpoint/status | `resume_after_gate_2` sets `PackagingOutput.is_final_approved`, completes the task, and advances composite projects | `LEGACY_PRODUCTION_AUTHORITY` |
| `PackagingOutput.is_final_approved` | Library list/detail/reuse, spec download, and batch ZIP export expose or reuse only final-approved outputs | `LEGACY_PRODUCTION_AUTHORITY` |
| gate/status/history serializers, review board, admin, dashboard/live status | Displays legacy approval state without independently advancing or exporting it | `LEGACY_DISPLAY_ONLY` |
| seeded `ColorSystem.status="canonical"` | `build_brand_context` injects palettes and image-generation context into model prompts; `get_brand_hexes` drives deterministic QA and revision decisions | `LEGACY_AUTOMATIC_INPUT` |
| seeded `AestheticLanguage.status="canonical"` | `build_brand_context` injects its description and product prompt seed into generation | `LEGACY_AUTOMATIC_INPUT` |
| seeded `MaterialSystem.status="approved"` | `build_brand_context` injects its prompt descriptors into generation | `LEGACY_AUTOMATIC_INPUT` |
| canonical color status | Dashboard palette panel and `verify_launch` count/display canonical rows | `LEGACY_DISPLAY_ONLY` |
| `Product.color_system` / `Product.material` | Product context names the assigned color system regardless of status; the Pacdora path copies palette/material into deliverable specifications | `LEGACY_PRODUCTION_AUTHORITY` |
| all known `ColorSystem` names/ids | Creative Director validation treats them as recognized palette vocabulary, regardless of signed DIP decisions | `LEGACY_WORKFLOW_CONTROL` |
| `BRAND_LOGO_PATH` in Creative Director | Existing file is described as official and attached to the Claude vision request | `LEGACY_AUTOMATIC_INPUT` |
| `BRAND_LOGO_PATH` in Image Producer and flat-artwork extraction | Existing file is passed to OpenAI image-edit calls and instructed to be reproduced as the official mark | `LEGACY_AUTOMATIC_INPUT` |
| `BRAND_LOGO_PATH` in container and dieline exporters | Existing file is placed into container graphs and components-mode editable AI/design previews | `LEGACY_PRODUCTION_AUTHORITY` |
| task-uploaded logo/container/label/inspiration/color files | Uploaded files can override the house logo or join model grounding and container composition without DIP permission projection | `LEGACY_AUTOMATIC_INPUT` |

The seeded `canonical`/`approved` strings, `active` flags, legacy group permissions, and gate
booleans are legacy workflow facts, not signed DIP decisions. They must not be imported as
approved DIP truth.

The DIP/accounts decision-security boundary introduces no asset approval, operational
permission, retrieval, or automatic-use capability. Legacy pipeline selection, approval,
seed-status, and automatic-input paths remain outside this boundary and must be contained by
the DIP-1B default-deny compatibility gateway.

## Verification and scope boundary

The correction regression covers valid grant, revoke, profile-enable, and profile-disable;
payload/HMAC, content-hash, linkage and signed-head verification; strict snapshot fields and
version; actor/role/action mismatch; assignment-history corroboration; and a mixed role plus
attestation chain. The full command is invoked against the generated four-role-event chain.

No intelligence model, migration, import, projection, UI, evidence feature, retrieval path,
automatic-use path, approval type, asset permission, or new role-management capability was
implemented.
