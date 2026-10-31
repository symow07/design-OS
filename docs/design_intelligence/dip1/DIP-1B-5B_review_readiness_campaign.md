# DIP-1B-5B — Curated corpus review readiness and the first human review wave

**Status:** implemented, tested, held for review before DIP-1B-6.

DIP-1B-5B makes the existing 90-item curated review queue practical, measurable and ready
for real authenticated human reviewers. It adds **no migration** and **no new authority**.

> **Review readiness is coordination metadata.** It says which candidates a human can
> usefully pick up next and what blocks them. It is **not** human truth, approval,
> ownership, licence validity, canonical/official status, governance selection, or any
> operational permission — and it can never upgrade any of those.

Nothing in this slice writes a decision, provisions a reviewer, or grants a permission.
Every module here is read-only.

---

## 1. Campaign scope — `dip1b_curated_review_scope/1.0`

`apps/intelligence/review_campaign.py`.

**Authoritative scope hash (frozen):**

```
cf178a337ec0350d8facf093bae8155aa1d2a039c46358102a93a011920150bf
```

The scope document is **hash-stable by construction**: it carries no `generated_at` and no
wall-clock field, so the same corpus state always yields the same hash. If an
implementation change moves this hash, that is a scope change and must be explained — not
silently re-documented.

### Wave partition (frozen, 90 tasks)

| Wave | Count | Subject |
|---|---:|---|
| `WAVE_1_HISTORICAL_DESIGN_MEMORY` | 20 | historical design reference memory |
| `WAVE_2A_ORIGINAL_C2_DESIGN_ASSETS` | 14 | original C2 pilot assets |
| `WAVE_2B_CURATED_DESIGN_ASSETS` | 24 | curated acquisition expansion |
| `WAVE_3_FONT_CANDIDATES` | 10 | font candidates |
| `WAVE_4_BRAND_AND_PALETTE_TRIAGE` | 22 | 21 brand-lineage + 1 palette |
| **Total** | **90** | |

`verify_campaign_partition()` enforces this contract separately from
`build_campaign_scope()`, which stays a pure function of whatever candidates exist (so it
remains unit-testable on fixtures).

### The campaign is deliberately bounded

It covers **38 of 100** design assets and **10 of 34** fonts. This is a choice, not a gap
to be closed by widening the campaign. The remaining items stay imported and unreviewed.

### Lineage is authoritative; a machine label is not

Wave assignment follows **dataset lineage** (`external_key` prefix / `dataset_identifier`)
and `review_type` only. `candidate_kind` is a machine label and **must never** redefine
identity, campaign membership, or governance subject. A brand-lineage candidate the machine
labelled `PALETTE` stays in `WAVE_4` as `BRAND_IDENTITY` — lineage wins. This is tested.

---

## 2. Review readiness — `review_readiness/1.0`

`apps/intelligence/review_readiness.py`. Calculation version
`bbrose.intelligence.review_readiness/1.0`.

Computed **on demand** — no migration, no persisted readiness table. The same inputs and
calculation version always produce the same result, so persistence would only duplicate
what the inputs already determine.

Readiness reuses the existing authority gates rather than re-deriving them
(`EvidenceIntegrityResolver` for integrity; `evidence_readiness` for the brand
rights/identity dimensions).

**Five independent axes, never combined into one score:**
`technical_evidence` · `provenance_evidence` · `identity_evidence` · `rights_evidence` ·
`integrity`.

Every `ReviewReadiness` states, rather than assumes:
`implies_approval=False`, `implies_rights_clearance=False`,
`operational_permission_granted=False`.

### Hard blocks (structural, not inferred)

* **Rights are never inferred.** A curated acquisition is `RIGHTS_UNREVIEWED` by lineage,
  full stop. Matching SHA-256s, a nearby licence file, a sibling asset's conclusion, a
  machine label, and technical quality can **none** of them clear rights. *Exact bytes do
  not prove identical rights — rights attach to provenance and acquisition, not content.*
  A `TECHNICALLY_READY` curated asset is still rights-unreviewed. Tested.
* **The 21 brand-lineage candidates stay identity-blocked**, and the palette stays blocked
  from primary-palette governance. Technical evidence is not brand identity.
* **Historical memory is `RIGHTS_NOT_APPLICABLE`** — reference memory, not a reuse claim.
  Not-applicable is not cleared.
* **An unresolved evidence-integrity finding blocks only the candidates it affects.**

Blocker codes are emitted in a normalised order so output is deterministic:
`EVIDENCE_INTEGRITY_UNRESOLVED`, `IDENTITY_UNCONFIRMED`, `RIGHTS_UNREVIEWED`,
`TECHNICAL_EVIDENCE_INCOMPLETE`, `PROVENANCE_INCOMPLETE`.

### Integrity is reported as the resolver found it

Each resolver status maps to exactly one readiness state. In particular **`REVIEW_REQUIRED`
is not reported as `HASH_MISMATCH`**: the resolver is saying *a human must look*, not *the
hashes disagree*. `DECLARED_HASH_MISMATCH` may appear as one reason code among several, but
a reason code is not the finding. Reason codes are carried verbatim in
`integrity_reason_codes`. The preserved codes are `DECLARED_HASH_MISMATCH`,
`KNOWN_NON_AUTHORITATIVE_GENERATED_VERSION`, `PATH_IDENTITY_NON_AUTHORITATIVE`.

**Live corpus state:** 21 candidates `REVIEW_REQUIRED` (the brand lineage), 69 `VERIFIED`.
The evidence-integrity gate is open and correctly failing closed — it has not been papered
over.

---

## 3. Review packets — `review_packet/1.0`

`apps/intelligence/review_packet.py`.

A packet is everything a human needs to judge one campaign candidate and nothing more:
**deterministic, read-only, bounded**.

* Never serves source binaries.
* **Never emits an unrestricted absolute filesystem path.** No `location_kind` promises an
  absolute path (`REPOSITORY_RELATIVE`, `CONFIGURED_ROOT_RELATIVE`, `ARCHIVE_MEMBER`,
  `LOGICAL`), so redaction to `REDACTED_UNRESTRICTED_PATH` is defence in depth against an
  importer writing an absolute path under a kind that claims relative.
* Machine classifications are labelled `"authoritative": false` and kept visibly apart from
  human assertions.
* Governance is **read-only** (`read_only: true`); 5B never creates or rebuilds a
  governance selection.
* Operational permissions are evaluated and reported — all denied.
* States, never assumes: `implies_approval`, `implies_rights_clearance`,
  `implies_governance_selection`, `grants_operational_permission` — all `false`.

A candidate outside the frozen campaign has **no packet**; absence is reported, never faked.

### Question sets — questions only, never answers

The packet asks; it never answers. The system supplies no substantive human answer — that
is the reviewer's job, and it arrives as a **signed decision event**, not a packet field.

| Review type | Questions |
|---|---|
| `HISTORICAL_MEMORY` | product_family · design_role · layout_patterns · typography_hierarchy · color_relationships · reference_memory_suitability · copying_risk · obsolete_brand_risk |
| `DESIGN_ASSET` | asset_category · extraction_quality · vector_raster_suitability · collection_relationship · provenance_completeness · rights_review_requirement · reference_only_versus_technically_reusable |
| `FONT_TECHNICAL` | family_identity · style_category · script_coverage · weight_and_width_suitability · bbrose_suitability · licence_evidence_state · system_demo_trial_suspicion |
| `BRAND_IDENTITY` | visible_brand_identity · bbrose_third_party_or_unknown · master_composition_lockup_or_unrelated_graphic · vector_master_suitability · missing_evidence |
| `PALETTE_OBSERVATION` | observed_colors · parse_completeness · authoritative_bbrose_evidence · candidate_only_suitability · blockers_before_governance_review |

### Prohibited-inference warnings

Universal: `REVIEW_READINESS_IS_NOT_APPROVAL_OR_OPERATIONAL_PERMISSION` ·
`MACHINE_CLASSIFICATION_IS_NOT_HUMAN_TRUTH` · `TECHNICAL_QUALITY_IS_NOT_RIGHTS_CLEARANCE` ·
`MATCHING_HASH_DOES_NOT_TRANSFER_RIGHTS` ·
`FILE_LOCATION_DOES_NOT_ESTABLISH_OWNERSHIP_OR_IDENTITY`.

Per type, additionally: brand — `TECHNICAL_EVIDENCE_IS_NOT_BRAND_IDENTITY`,
`A_BBROSE_LABEL_IS_NOT_CONFIRMED_BBROSE_OWNERSHIP`, `CANDIDATE_IS_NOT_CANONICAL`; palette —
`TECHNICAL_PARSE_IS_NOT_PALETTE_AUTHORITY`, `CANDIDATE_IS_NOT_THE_PRIMARY_PALETTE`; asset —
`NEARBY_LICENCE_EVIDENCE_DOES_NOT_CLEAR_RIGHTS`,
`A_SIBLING_ACQUISITION_CONCLUSION_DOES_NOT_TRANSFER`; historical —
`REFERENCE_MEMORY_IS_NOT_A_REUSE_LICENCE`; font — `POSSESSION_IS_NOT_A_LICENCE`.

---

## 4. Browser surface

`apps/intelligence/views.py`, `templates/intelligence/review_queue.html`,
`templates/intelligence/review_detail.html`.

Both pages carry the banner:
**`REVIEW READINESS IS NOT APPROVAL OR OPERATIONAL PERMISSION.`**

**Filters** (queue): assignment · status · review type · **campaign wave** · **readiness
state** · **blocker** · **evidence integrity** · **machine candidate kind** · **assigned
reviewer**. Every filter validates against a bounded vocabulary and **refuses an unknown
value with 400** rather than silently ignoring it — a silently-dropped filter would show a
reviewer a wider set than they believe they are looking at.

**Machine candidate kind is a display filter only.** It spans two profile tables
(`DesignAssetProfile.candidate_asset_kind`: MOTIF/BACKGROUND/ILLUSTRATION/LOGO_CANDIDATE/
PATTERN/PHOTO/UNKNOWN; `BrandCandidateProfile.candidate_kind`: LOGO/WORDMARK/BRAND_GRAPHIC/
PALETTE/LOCKUP/UNKNOWN_BRAND_ASSET) and its vocabulary is derived from the models so it
cannot drift. It **never** feeds wave assignment, readiness, identity, or governance
subject — lineage decides those. The live corpus makes the point: two brand rows are
machine-labelled `PALETTE`, but only one is palette lineage. The filter may hide a
candidate; it may never reclassify one. Tested.

**Progress** is deterministic and reported as review tasks completed / remaining / total
plus a readiness breakdown. It is computed over the **whole queue and is unaffected by
filters** — a stable denominator, by intent: filters change which cards you see, never how
much work exists. There is a **next recommended candidate** — a suggestion only; it claims
nothing and assigns nothing, and the reviewer must still claim the review.

A candidate whose lineage cannot be resolved is **withheld and counted as unreadable**
rather than given an invented wave or allowed to 500 the queue.

**Detail** renders the packet panel with sections `TECHNICAL EVIDENCE` · `PROVENANCE` ·
`MACHINE OUTPUT` · `HUMAN ASSERTIONS` · `REVIEW READINESS` · `GOVERNANCE STATUS` ·
`OPERATIONAL PERMISSION`, plus the question set and prohibited inferences.

No governance or permission-granting control is offered by this surface. **GET writes
nothing**; POST endpoints keep CSRF and their existing authorization. Campaign membership
**fails closed**: if the frozen scope cannot be built, membership is withheld rather than
guessed, and the queue says so.

`review_readiness` (campaign coordination) and `evidence_readiness` (brand rights/identity
dimensions) are different things and are kept as distinct context keys.

---

## 5. Campaign report — `dip1b_curated_review_report/1.0`

`apps/intelligence/campaign_report.py`. Read-only; writes nothing, grants nothing.

**Corpus and campaign counts are never blended** — they are separate keys with distinct key
names, because the campaign is a deliberately bounded subset and mixing the two would
misrepresent both.

```
corpus  : historical_designs 20 · design_assets 100 (c2 47 · curated 53)
          · fonts 34 · brand_lineage_candidates 21 · palette_lineage_candidates 1
campaign: total 90 · curated_assets_in_campaign 24 · c2_assets_in_campaign 14
          · brand_lineage_in_campaign 21 · palette_lineage_in_campaign 1
```

**There is no combined approval percentage.** `combined_approval_percentage` is
permanently `None` by design. Progress is reported along separate, non-substitutable axes:
`imported_corpus_items` · `in_active_campaign` · `review_tasks_completed` ·
`human_classified` · `evidence_assessed` · `governance_selected` ·
`operationally_permitted`. Collapsing them into one number would imply that technical
progress is approval progress. It is not.

`imported_corpus_items` counts the corpus itself (**176**), not a sum of profile tables —
summing historical + assets + fonts would silently omit every brand and palette item.

**Corpus-wide hard block:** 53 curated assets are `RIGHTS_UNREVIEWED` — 24 inside the
campaign and 29 outside it. Being outside the campaign does not make an item clear.

**Authority counts must stay zero until real humans decide:** `signed_decision_events`,
`human_assertion_projections`, `governance_selections`, `allowed_operational_permissions`
(counted for the `ALLOWED` state specifically — an unfiltered count would over-report a
number whose whole purpose is to stay zero).

---

## 6. Coverage gap — `dip1b_coverage_gap:HAIR_CARE/1.0`

A deterministic, visible record that the corpus has no hair-care historical memory. The
live product-family labels are `makeup-compact`, `complexion`, `lip-colour`,
`primer-skincare`, `eye-colour`, `concealer` — all cosmetics.

**Deliberately non-blocking** (`blocking: false`, `blocks_other_waves: false`): it must not
stall unrelated review waves, and it must not tempt anyone into importing a weak or
unverified design merely to make a number move. An unverified reference would corrupt the
memory it is meant to serve. Closing it is an **acquisition decision, not a review action**.

`human_verified_coverage` is the literal `0`. `HistoricalDesignProfile` carries only
`product_family_machine_label` — a machine guess — and `audit_status` tops out at
`MACHINE_AUDITED`. **No field records human product-family verification**, so verified
coverage is 0 by construction. Counting the machine label here would launder a guess into a
verification claim.

---

## 7. Manual procedure for the first human review wave

This procedure is **not automated on purpose**. Each step is a human act.

1. **Configure a signing key.** `DECISION_EVENT_HMAC_KEYS` / `DECISION_EVENT_ACTIVE_KEY_ID`
   are unset in the local environment, so no decision can be signed and the system fails
   closed. This must be done deliberately by an operator — never automatically, and never
   by weakening the fail-closed configuration. See `DIP-1A_key_rotation_runbook.md`.
2. **Provision reviewers.** Create the user, `ReviewerProfile` (`reviewer_enabled`), and a
   `ReviewerRoleAssignment` with a real granter, grant source and reason. Never provisioned
   automatically.
3. **Start with `WAVE_1`** (historical memory, 20 tasks): rights are not applicable, so it
   is the cleanest wave to calibrate reviewers on.
4. **Then `WAVE_2A`** (14 original C2 assets) — no curated-rights hard block.
5. **`WAVE_4` (22) is triage only.** Brand identity and palette authority stay unconfirmed;
   classify what the evidence shows and stop there. All 21 brand candidates are currently
   integrity `REVIEW_REQUIRED` — triage technical and identity evidence only.
6. **`WAVE_2B` (24 curated) may be classified technically but never rights-cleared** by
   this wave. Rights review is a separate human act on separate evidence.
7. **`WAVE_3`** (10 fonts): possession is not a licence.
8. Claim → review the packet → answer the question set → submit a **signed** classification.
   An unclaimed task is never auto-assigned.

**A machine may not:** configure a signing key, provision a reviewer, fabricate a signed
assertion, reset the chain, weaken fail-closed configuration, or answer a question set.

---

## 8. Exclusions

Not in 5B: no migration; no new persisted table; no expansion of the campaign to all 100
assets or all 34 fonts; no governance selection or rebuild; no permission grant; no
retrieval, automatic use, embedding or production use (all remain `false` until a human
approves); no reviewer provisioning; no key configuration; no regeneration of historical
milestone records under newer schemas; no loosening of thresholds to produce non-zero
output.

---

## 9. Verification

* `apps/intelligence/test_review_campaign.py` — 17 tests (waves/lineage, determinism,
  fail-closed identity, frozen partition, readiness hard blocks).
* `apps/intelligence/test_review_packet.py` — 21 tests (packet bounds, path redaction,
  machine non-authoritative, governance read-only, report separation, integrity honesty,
  corpus axis, hair-care gap).
* `apps/intelligence/test_review_browser.py` — 21 tests (authorization denial, bounded
  filters, determinism, GET writes nothing, packet sections, no permission control,
  candidate-kind never moves a wave, orphan withheld not guessed, progress denominator
  stable under filtering, absolute-path redaction actually runs).

Live corpus checks: scope hash `cf178a3…50bf` preserved; partition 20/14/24/10/22 = 90;
corpus/campaign key overlap empty; all authority counts zero.
