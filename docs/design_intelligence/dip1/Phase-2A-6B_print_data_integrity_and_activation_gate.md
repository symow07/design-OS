# Phase 2A-6B — Printed-Data Integrity Recovery and Local Activation Gate

Proves that verified panel information survives regeneration, scopes the
database transport workaround, and builds the recovery path for the task-#47
incident. `STANDARD_VECTOR_PACKAGING_PIPELINE` stays **False**.

Commits: `6438f6e` snapshot contract + regeneration integrity · `0b86193`
database transport policy · `4605178` entry/review screen + recovery report ·
this document.

## Activation gate outcome: NEEDS_PRINT_DATA_RECOVERY

Every engineering precondition is met. The one outstanding item is **your
data**: task #47's printed information must be re-entered before the replay
can be compared before/after, and that comparison is the gate's core
requirement.

| gate condition | state |
|---|---|
| print-data recovery complete | **NO — awaiting your data** |
| before/after snapshot identical | not yet exercisable |
| clean prefork worker boot verified | yes |
| no external calls | yes — `ApiCallRecord` 164 throughout |
| production-eligible templates green | yes |
| task #47 generalized replay succeeds | yes (structurally) |
| no regulatory data loss | yes — guarded and tested |
| no Phase-1 authority changes | yes |
| real ICC profile configured | **NO — not supplied** |

## Snapshot contract — `packaging_print_data_snapshot/1.0`

Task ID · schema version · normalized field values · per-field verification
state · translation identities · legal-role mapping · timestamp · source
identity · content hash. The hash covers canonical bytes that **exclude** the
timestamp, so two snapshots of the same data match whenever they were taken.
Translations are carried as per-language, per-field SHA-256 + length —
identities, not copies. Credentials, worker state, agent rationale and the
internal brief are structurally absent.

## Regeneration integrity

A run binds to the snapshot it consumed, re-snapshots its output, and
compares. Codes: `PRINT_DATA_FIELD_DROPPED`, `PRINT_DATA_FIELD_CHANGED`,
`PRINT_DATA_DEFAULT_SUBSTITUTED` (changed *into* a Product/Brand default —
the incident's exact signature), `TRANSLATION_DATA_LOST`,
`LEGAL_ROLE_MAPPING_CHANGED`, `VERIFIED_PRINT_DATA_WOULD_BE_LOST`,
`PRINT_DATA_SNAPSHOT_MISMATCH`. Formatting-only normalization (NFC, newline
and space collapsing) passes and is listed explicitly. **No partial success**:
one failure halts the run at the structure gate with the comparison attached.

## Precedence contract

1. stored task-specific printed-information record;
2. explicit verified task override;
3. Product/Brand defaults **only** for fields truly absent and never
   previously verified;
4. no generated fallback for a required production field.

A stored VERIFIED value can never be replaced by a default, and a task with
no `Product` row keeps its own record — both asserted.

## Database transport policy

`DB_GSSENCMODE` now defaults to **empty**. `LOCAL_DEVELOPMENT` opts into
`disable` automatically (the documented macOS prefork fork-safety
workaround); every other environment must state its policy or fail
`TRANSPORT_POLICY_AMBIGUOUS`, and an inherited local workaround fails
`TRANSPORT_GSS_WORKAROUND_LEAKED`. TLS is configured **independently** via
`DB_SSLMODE` and reported separately — disabling GSS encryption says nothing
about transport encryption. Checks read policy values only; a test asserts no
database user or password can reach check output.

## Prefork verification

Clean boot on `4605178`: **0 SIGSEGV**, worker responds to ping, the task set
includes `resume_aria_structure`, a real DB-touching replay completed in the
worker, Redis and PostgreSQL stable, **0 external provider calls**.
Connection: `postgresql`, database `bbrose_db`, host `localhost`, options
`{'gssencmode': 'disable'}` — no credentials recorded anywhere.

## ICC output intent

`MISSING_OUTPUT_INTENT` remains a hard Gate-2 blocker and nothing is bundled.
`manage.py check_icc_profile <path>` validates a candidate and prints exactly
what the readiness record will carry: runtime path, SHA-256, description,
colour space, components, device class, version, validation result. Verified
against real profiles — Generic CMYK passes (v2.2, output printer, 4
components), sRGB is refused `NOT_CMYK`. **Generic CMYK is a test fixture
only and must not become the BBROSE production profile.** The real profile
must come from the print shop and match the printing condition, board stock,
coating, press standard and ink limit; keep it outside source control, since
licence and redistribution rights are the shop's.

## Task #47 recovery state

`awaiting_gate_2`, unapproved, restored to the accepted DIE-5 deliverables,
incident recorded as `PRINT-DATA-47-2026-07-20` listing eleven lost fields.
The entry screen reports **nine outstanding required fields**:
`brand_display_name`, `product_name`, `product_type`, `ingredients`,
`how_to_use`, `warnings`, `net_weight`, `manufacturer`, `country_of_origin`.
Recovery result: `AWAITING_USER_ENTRY`.

Nothing was transcribed from the rendered artifacts, no OCR was used, no line
breaks or translations were inferred, no placeholder INCI or example
identifiers were restored, and no other product's record was copied.

**When you supply the exact approved data** the sequence is: enter values →
assign verification states → save → produce snapshot/hash → review the
normalized record → confirm → replay through the standard path → compare
before/after → regenerate back/side panels → re-run production readiness.
Gate 2 is not approved automatically, and `MISSING_OUTPUT_INTENT` will remain
until the real ICC profile is configured.

## Operational note

During the §7 worker probe I ran the replay against task #47 itself, which
regenerated its files; I restored the accepted DIE-5 deliverables again. A
scratch task should be used for worker probes — the incident task is not a
test fixture.
