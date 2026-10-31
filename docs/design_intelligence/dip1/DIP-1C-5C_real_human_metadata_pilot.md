# DIP-1C-5C — First Real Human Semantic Metadata Pilot

**Status: PHASE 1 CLOSED — MVP COMPLETE, HUMAN SEMANTIC ENRICHMENT DEFERRED.**

Outcome in the accepted vocabulary: **`INSUFFICIENT_REAL_REVIEW`** — not a defect finding.
The workflow was built, hardened through four corrections (CORR-1…CORR-4), and provisioned;
the substantive human review was deferred by the user in favour of Phase 2A (Design
Reasoning Engine MVP). No descriptor may be invented to stand in for it.

### Item 1 — accepted quarantined pilot condition

Item 1 (BL-2050 STAND) carries **two active human semantic metadata events** (sequences 2
and 3 — the second appended by a stale application process, documented below). The verified
history resolver reports `REVIEW_REQUIRED · MULTIPLE_ACTIVE_METADATA_EVENTS`, and this is
the accepted parked state:

* the DecisionEvent chain remains **VALID** (3 events);
* the disputed metadata is **not published** — HumanAssertionProjection was deliberately not
  rebuilt, so no bundle for item 1 is effective anywhere;
* the dedicated conflict-resolution workflow (`7e783f8`) is committed, tested, and ready for
  a future resumption — the resolution form is the only mutation the page offers;
* no governance decision, no operational permission, no retrieval or automatic-use authority
  exists;
* the signed events are immutable and will not be edited, deleted, or rewritten.

**Semantic search remains experimental and inactive.** Lexical reviewer search is the active
search capability. Generation `e88b1468` (schema 1.2) is preserved and unused by any
operational surface.

### Historical note — authority state at the FIRST deferral (before stage 2 resumed)

| Authority state at the first deferral (superseded — see closure above) | |
|---|---|
| DecisionEvents | **1** — the single-operator bootstrap ceremony only |
| Human semantic metadata events | **0** |
| HumanAssertionProjection rows | **0** (generation `2ea4c605`, CURRENT) |
| GovernanceDecisionProjection rows | **0** (generation `d5c339fb`, CURRENT) |
| ALLOWED OperationalPermissionProjection rows | **0** |
| BootstrapState | `closed = true`, anchored to `3b00b610…`, `break_glass_count = 0` |
| Reviewer | `admin`, `DESIGN_REVIEWER`, expires **2026-08-01T08:08:41Z** |
| Bootstrap flags | both `false` |
| External requests | none |

Everything below records what was built and provisioned. The pilot scopes, forms,
evidence-label correction, documentation and tests are preserved for later use.

### If the pilot resumes after 2026-08-01

The `DESIGN_REVIEWER` assignment expires on its own — that is the design, not a fault.
**Do not reopen bootstrap and do not bypass role controls to get around an expired grant.**
The single-operator ceremony is permanently closed and its break-glass path is deliberately
refused (`SINGLE_OPERATOR_BOOTSTRAP_REOPEN_REQUIRES_SEPARATE_REVIEW`).

Resuming requires a fresh authority review that first identifies a legitimate renewal path.
The honest options, in order of preference: a protected `grant_reviewer_role` performed by a
second real authenticated human holding `BUSINESS_OWNER`/`BRAND_ADMIN`; or, if the
environment is still genuinely single-operator, a separately reviewed renewal design — which
does not exist yet and must not be improvised from the bootstrap ceremony.

### Historical note (stage 1, before provisioning)

At the time stage 1 was written, no signing key was configured, no reviewer was provisioned,
no role was granted, and `DecisionEvent` count was **0**. The single-operator ceremony
(DIP-1A-BOOTSTRAP-CORR-2) was performed later under explicit authorization.

## Part I — focused review of DIP-1C-5B (511c99a, 5790d74)

Verified empirically against the running system. **No defect found.**

| Check | Result |
|---|---|
| Schema/vocabularies frozen and bounded | `human_semantic_metadata/1.0`, `human_semantic_vocabulary/1.0`; 9 frozen vocabularies |
| Notes cannot enter embedding text | `bundle_embedding_terms` excludes `reviewer_notes`; asserted |
| Authority-claim terms rejected | all 7 `FORBIDDEN_BRAND_CLAIMS` refused with `FORBIDDEN_AUTHORITY_CLAIM` |
| Evidence mandatory in service **and** projection | service refuses an empty list; `_metadata_event` refuses one |
| Projector re-validation idempotent | `build_metadata_bundle(build_metadata_bundle(x)) == x` |
| Record/correct form one bounded supersession family | exactly two cross-action pairs exist chain-wide: classification, metadata |
| Unrelated cross-action supersession impossible | confirmed by enumerating every action pair |
| Deferred clarification action absent | not in `ACTIONS`, not in `POLICY`, no attribute |
| Schema 1.3 not in the executable build registry | in `DEFINED_NOT_BUILDABLE_SCHEMAS`; requesting it fails closed |
| No migration | `makemigrations --check` → no changes detected |
| Lexical remains default | search views reference the lexical/hybrid path only |
| Ranker 1.2 / gate 1.1 inactive | `rescue_ranker` is referenced by no view or search service |
| Generation `e88b1468` preserved | `PUBLISHED`, schema 1.2, 176 embeddings; `f88bd738` `SUPERSEDED` |
| Authority counts zero | events 0 · assertion projections 0 · governance 0 · permissions 0 |

### `authz/1.3` and BUSINESS_OWNER — intentional, and strictly descriptive

`BUSINESS_OWNER` was granted `record_/correct_human_semantic_metadata` deliberately: a
business owner describing what a design looks like is ordinary product judgement, and the
action confers nothing else. Verified that 1.3 did not widen the role's authority surface:

* `finalize_canonical_brand_asset` and `finalize_primary_brand_palette` remain `BRAND_ADMIN`
  only — `BUSINESS_OWNER` is **not** in either.
* the role's `revoke_*` rights are unchanged from 1.2 (they pre-date this slice).
* every action mapping in `POLICY_V1_2` is byte-identical in `POLICY`; 1.3 only **adds**.
* no ownership, canonical, licence, permission or governance-finalization capability is
  reachable through a metadata action.

A test (`test_business_owner_may_describe_but_gains_no_authority_from_authz_1_3`) now proves
a `BUSINESS_OWNER` can record a bounded descriptor, that every prohibited authority claim is
still refused for that role, that the 1.2 mapping is frozen, and that describing creates no
governance or permission state.

## Pilot scope — `dip1c_semantic_metadata_pilot/1.0`

**Hash:** `71166c7f88cef3b86e058bd6a03651083dd83f14ad2908c05f80d33868efe277`
**Parent review scope:** `dip1c_semantic_metadata_review_scope/1.0`, hash
`8911b32131ee0f1121df7ca6a2b523ee124a7d6df28dbc4821a08251f5dcac78` (unchanged).

The pilot is a strict subset of the accepted 55-item scope. Selection is deterministic
(`external_key` order) and adds two hard criteria, because an item that fails either cannot
be reviewed at all:

1. **evidence integrity must not block evidence-dependent claims** — the projector refuses
   such an item, so handing it to a reviewer wastes the review;
2. **a `ReviewCandidate` must exist** — metadata is submitted from the review-detail page, so
   an item without one has no route a human can use.

Building the scope writes nothing: no `CorpusItem`, no `ReviewCandidate`, no `DecisionEvent`,
no permission.

### Selected items — 10 of the requested 12

| Segment | Target | Selected | External key | Evidence | Candidate |
|---|---|---|---|---|---|
| historical | 4 | 4 | `historical:dip0b-history:00:BL-2050 STAND` | 12 | yes |
| | | | `historical:dip0b-history:01:EP416-E` | 9 | yes |
| | | | `historical:dip0b-history:02:ES3083吸塑 展盒刀线` | 9 | yes |
| | | | `historical:dip0b-history:03:FB-2060 白卡` | 13 | yes |
| c2_assets | 2 | 2 | `asset:dip0c2_asset_candidate_pilot/1.0:027f836…` | 1 | yes |
| | | | `asset:dip0c2_asset_candidate_pilot/1.0:069efd5…` | 1 | yes |
| curated_assets | 2 | 2 | `asset:dip1b_curated_asset_expansion/1.0:dip1b-…` ×2 | 1 each | yes |
| fonts | 2 | 2 | `font:fam-023e33d897408ed9`, `font:fam-100546fe66abb998` | 1 each | yes |
| **brand_palette** | **2** | **0** | — | — | — |

All 10 selected items are `VERIFIED` on evidence integrity and ready for descriptive review.

### The brand/palette shortfall — a real blocker, reported not padded

**21 of 22 brand candidates** in the corpus are blocked by an unresolved evidence source
version in `dip0c3_brand_candidates/1.0` (`STALE_GENERATED_OUTPUT`, reason codes
`DECLARED_HASH_MISMATCH`, `KNOWN_NON_AUTHORITATIVE_GENERATED_VERSION`,
`PATH_IDENTITY_NON_AUTHORITATIVE`). All 5 brand items inside the accepted 55-item scope are
among them. The single unblocked brand/palette identity —
`palette:dip0c3-palette:pantone-3519-c` — sorts after the `brand:` keys and is therefore
outside the accepted scope's `brand_palette` segment.

So the segment yields zero reviewable items, and the document records
`unfilled_segments: {"brand_palette": 2}` rather than padding from another segment. This
matters beyond arithmetic: brand/palette is precisely the segment the pilot most wanted to
test, because it is where descriptive review is most likely to drift into ownership language.

**This is a decision for you**, and the reason stage 1 stops here rather than proceeding:

* **(a) run the pilot at 10 items** — accept that the authority-drift boundary is exercised
  only by the doctrine and the vocabulary, not by a real brand item;
* **(b) amend the DIP-1C-5B review scope** so its `brand_palette` segment prefers reviewable
  identities (would admit the Pantone palette item). This **changes the accepted scope hash
  `8911b321…`**, so it needs your explicit approval;
* **(c) resolve the `dip0c3_brand_candidates/1.0` integrity finding first**, then re-run the
  pilot selection with brand candidates included.

I recommend **(a)** now and **(c)** as separate work: option (b) edits an accepted contract
to route around an integrity finding, which is the kind of convenience that later reads as a
precedent.

## Operational preflight — `dip1c_semantic_metadata_preflight/1.0`

Read-only. It reports the *shape* of the signing configuration and never a key value: tests
assert that neither the key nor even the active key id appears anywhere in the report.

| Field | Current value |
|---|---|
| Signing keys configured | **no** (`DECISION_EVENT_HMAC_KEYS_NOT_CONFIGURED`) |
| Active key id configured | no |
| Registry resolves | no |
| Active users | 3 — `admin`, `pwtest`, `runtest` |
| `ReviewerProfile` rows | **0** |
| Active role assignments | **0** |
| Reviewers eligible for metadata | **0** |
| DecisionEvent chain | head present, terminal sequence 0, **verified**, 0 events |
| Pilot items ready | 10 of 10 selected |
| Authority counts | events 0 · assertion projections 0 · governance 0 · permissions 0 |

**Blocking conditions:** `NO_USABLE_DECISION_EVENT_SIGNING_KEY`,
`NO_REVIEWER_AUTHORIZED_FOR_SEMANTIC_METADATA`.

Neither can be resolved by me. Both require a human action on secrets and authority state.

## Manual setup procedure (to run only after explicit authorization)

### 1. Configure the decision-event signing key

A dedicated secret — never `SECRET_KEY`, never stored in the database, never committed.

```
# generate locally; do not paste the value into chat, a log, or a commit
python -c "import secrets; print(secrets.token_hex(32))"
```

Add to the environment (e.g. `.env`, which is git-ignored):

```
DECISION_EVENT_HMAC_KEYS={"dip1c-key-1":"<the generated value>"}
DECISION_EVENT_ACTIVE_KEY_ID=dip1c-key-1
```

Confirm with the preflight — it will report `registry_resolves: true` and still print no key
material. **Once events are signed with this key, it must not be lost or rotated away
without a documented rotation**: the chain is verified against it.

### 2. Provision exactly one reviewer

**Superseded by DIP-1A-BOOTSTRAP-CORR-2.** The two-person protected grant cannot be
completed honestly here: `grant_reviewer_role` requires `BUSINESS_OWNER`/`BRAND_ADMIN` and
forbids self-elevation, so it needs two distinct real humans, and only one exists. The
legacy direct `DESIGN_REVIEWER` bootstrap is now closed because it left `BootstrapState`
open forever.

Use the single-operator ceremony instead — see
[DIP-1A-BOOTSTRAP-CORR-2](DIP-1A-BOOTSTRAP-CORR-2_single_operator_ceremony.md):

```
# check readiness first; never prompts, writes nothing
manage.py bootstrap_single_operator_reviewer --username <you> --expires-days 14 \
    --reason "DIP-1C-5C bounded human semantic metadata pilot" --dry-run
```

It requires `BOOTSTRAP_ENABLED` **and** `BOOTSTRAP_SINGLE_OPERATOR_ENABLED`, a classified
`LOCAL_DEVELOPMENT` environment, and an interactive password challenge. It grants a
time-bounded `DESIGN_REVIEWER` and closes bootstrap **permanently** in the same transaction.
The signed event records `single_operator: true` — it is not dual control and does not
pretend to be.

The ceremony appends a signed event, so `DecisionEvent` will no longer be 0, and that is
correct. **Do not reset the chain afterwards.**

### 3. Confirm the environment before reviewing

Re-run the preflight. Proceed only when `blocking_conditions` is empty.

## Real review procedure (the reviewer performs this; I do not)

For each of the 10 pilot items, at `/intelligence/reviews/<candidate_id>/`:

1. **Read the review packet and open the evidence.** The descriptors must come from the
   artwork, not from the filename, the machine labels, or a plausible guess.
2. **Select only what you can see**, from the domains listed for that item's segment:
   * historical — product family, design style, motif, visual mood, colour, layout/format,
     evidence-supported synonyms;
   * design assets — style, motif, mood, colour, layout/format, asset category, synonyms;
   * fonts — font style, script suitability, bounded intended use, synonyms;
   * brand/palette — **observational descriptions only** (if any such item is later added).
3. **Leave a domain empty rather than choosing `UNKNOWN` for completeness.** `UNKNOWN` is
   dropped from embedding text; an empty domain and an `UNKNOWN` say the same thing, and the
   empty one is honest about effort.
4. **Cite the evidence you actually looked at.** At least one reference is required.
5. **Never assert authority.** No ownership, official-brand identity, canonical master,
   licence validity, rights clearance, approval or operational permission. If an item looks
   like an official brand master, record `BBROSE_LABEL_OBSERVED_UNCONFIRMED` and raise it
   through governance. The form cannot express ownership; do not work around that.
6. **Submit** through the protected POST/CSRF form. Actor and role are derived server-side.
7. **Verify** the signed event appears, then rebuild the projection
   (`rebuild_assertion_projections --apply`) and confirm the bundle shows as CURRENT in the
   browser.
8. **Correct only where a correction is genuinely warranted.** If none is, the correction
   workflow is verified in the test environment instead — a fabricated correction in the real
   chain would be a permanent lie in an immutable record.

After each submission, stage 2 will verify: signature and chain linkage, actor/role
derivation, authorization snapshot, evidence ownership, metadata schema, controlled
vocabulary, source hashes, supersession state, projection publication, and that no
operational permission, governance state or retrieval activation appeared. **A failed
projection or chain verification stops the pilot** — no further events on an invalid chain.

## Pilot usability findings (stage 2, before the first submission)

### 1. Evidence labels were not discriminative — corrected (DIP-1C-5C-CORR-1)

The review forms labelled every evidence checkbox `evidence_kind · SourceArtifact.sha256`.
That hash belongs to the whole source file, so all 11 `FILE_PAGE_UNIT` references extracted
from `BL-2050 STAND.ai` rendered **identical** labels.

The underlying records were never ambiguous: item 1's 12 references have 12 distinct
`evidence_hash` values, and each locator already carried `page` and `unit_key`. Only the
presentation collapsed them — and a reviewer who cannot tell two checkboxes apart cannot
honestly claim to have inspected one of them.

The correction renders bounded locator identity through one shared helper used by every
review form:

```
FILE_PAGE_UNIT · page 0 · BL-2050 STAND-p0-u01
SOURCE_FILE · complete source · SHA-256 e57211a5e858…
```

Presentation only: evidence identity, stored hashes, locators, source artifacts, signed
schemas and validation semantics are unchanged, and the submitted checkbox value is still
the canonical `EvidenceReference` id. Paths are never rendered in a label — `source_file`,
`json_path`, `jsonl_record` and `archive_member` locators all carry real repository or
`materials/` paths, so those fail closed to the reference's own id and hash prefix rather
than to the shared source hash.

**This does not solve visual evidence inspection.** It makes selection *honest*; it does not
let a reviewer see the artwork.

### 2. NEEDS_EVIDENCE_IMPROVEMENT — no in-browser visual preview (PARTIALLY RESOLVED)

**Resolved for 47 of 49 pilot evidence references by DIP-1C-6A**, which renders bounded,
authenticated, read-only PNG previews directly on the review page: all 43 historical
references, both C2 assets, and both fonts (as glyph specimens). See
[DIP-1C-6A](DIP-1C-6A_safe_artwork_preview.md).

**Still open for the 2 curated-expansion EPS assets.** They embed palette TIFF previews with
an extra sample, which Pillow cannot decode, and Ghostscript — which would render them — is
deliberately not installed. Those cards report `NOT_RENDERABLE` with the reason rather than
showing a broken image. The finding below records the original state.

### 2. NEEDS_EVIDENCE_IMPROVEMENT — no in-browser visual preview

The review page shows technical facts, machine classifications and hashes, but no rendering
of the actual artwork. Descriptors must come from the artwork, so review requires opening
the source file in Illustrator outside the system. That is workable for a 10-item pilot and
it does not scale — and it means the system cannot show *what* a reviewer actually looked at.

Separately noted: the DIP-1B-5B review packet renders a root-relative
`repository:materials/…` source location by design, so the reviewer knows which file to
open. That is deliberate and outside the label correction; no absolute filesystem path is
exposed.

## Explicit exclusions (stage 1 and stage 2)

No schema-1.3 embedding build. No OpenAI transfer of any kind. No benchmark query embedding.
No ranker 1.2 or gate 1.1 activation. No threshold tuning. No schema-1.2 generation rebuild.
No retrieval-quality claim — this slice measures whether humans can record grounded
descriptors, not whether search improves. No migration: the pilot adds no table, and nothing
persists beyond the existing `DecisionEvent` and `HumanAssertionProjection`.

## Verification (stage 1)

* `pytest -m "not pacdora"` — **1294 passed, 1 skipped** (10 new: 9 pilot/preflight, 1
  BUSINESS_OWNER authority separation).
* ruff clean; `makemigrations --check` → no changes detected.
* Generation `e88b1468` preserved; campaign hash `cf178a33…` and partition 20/14/24/10/22
  unchanged; `materials/` untouched.
* Authority counts 0/0/0/0 before and after — confirmed by test and by direct query.

## Operational incident — stale application process (DIP-1C-5C-CORR-4)

During stage 2 a second independent metadata record event was appended for item 1, leaving
two active bundles and `REVIEW_REQUIRED · MULTIPLE_ACTIVE_METADATA_EVENTS`.

**This was a deployment-version mismatch, not a code defect and not reviewer error.** The
development server had been started with `--noreload` and predated two committed
corrections — `178bc06` (separated evidence rows) and `4de64b2` (correction from verified
history, including the guard that refuses a second record). The repository and its tests were
correct; the running process had not loaded them, so the browser executed old mutation
behaviour and the guard that would have refused the submission was never in memory.

Mitigations, in order of reliability:

1. **Never run the review server with `--noreload`** during active development.
2. **Restart and re-verify after every code update**, before asking a human to review.
3. The review page now displays the **revision the process actually loaded** (DEBUG only,
   resolved once at import — never per request, never by shelling out in a view). If that
   stamp is behind your working tree, restart before reviewing.

The two duplicate events remain immutable in the chain and were reduced to one effective
bundle by a signed conflict resolution rather than edited or deleted.
