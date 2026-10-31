# §BH22 — THE ONE REPORT, DELIVERED AT THE GOAL'S OWN HARD STOP

**Written 2026-09-01, at HEAD a06ccf6 (unmoved). The §BH22(a) re-pin commit's
gate REFUSED on FOUR tests beyond the two known movers. §BH22's sentence:
"if the re-pin commit's gate refuses on ANYTHING beyond the two known movers,
stop and report." This is the stop and this is the report. NOTHING LANDED —
no commit A, no transcription, no pass 2, no queue record. Every measurement
below is hand-captured; raw evidence in ~/bh21_work/ (a_gate.log, a_exit.txt,
bh22_measurement.json) and the gate's own capture
`bbrose_design_os/.tier2_captures/20260901T014718Z_a06ccf6.txt`.**

---

## §1 — THE STOP, MEASURED

* Gate line: `TIER_2=REFUSE collected=8490 failures=4 apps=7684 dip0c=671 dip0=135`
  → `GUARDED_COMMIT_REFUSED: TIER_2=REFUSE (A326/3m)`.
* Exit **1**, hand-captured (`a_exit.txt`). HEAD **a06ccf6, unmoved** — the
  two landing confirmations correctly NOT met; "landed" is not claimed.
* Suite detail: `4 failed, 7677 passed, 3 skipped, 41596 subtests passed in
  722.52s`.
* **Both known movers are ANSWERED and GREEN**: dip1b's fail-closed branch
  (test_manifest_import.py) and test_c4b's 130 are NOT in the failure list —
  the worktree edits did exactly what they were ruled to do. The refusal is
  entirely NEW territory, which is what makes it the hard stop.

The four, all in `apps/intelligence/test_evidence_integrity.py`:

1. `test_stale_output_classification_is_deterministic` —
   `{'UNRESOLVED'} == {'STALE_IGNORED_OUTPUT'}` fails (:169).
2. `test_full_hash_mismatch_is_stale_ignored_output_and_path_does_not_override_identity`
   — same classification assert.
3. `test_general_resolver_does_not_let_verified_physical_evidence_cure_data_mismatch`
   — `result.classification == STALE_IGNORED_OUTPUT` fails (:374); status is
   still REVIEW_REQUIRED (that leg passed).
4. `test_browser_surfaces_review_required_hash_warning_for_affected_candidate`
   — `b"STALE_IGNORED_OUTPUT" in response.content` fails (:296) on both the
   corpus-detail and review-detail pages.

## §2 — ONE MECHANISM, FULLY MEASURED: A SECOND EVIDENCE CONTRACT PINS THE FIRST ONE'S BYTES

The chain, every link hand-measured:

* `docs/design_intelligence/dip1/dip1b_evidence_integrity_registry_1_0.json:18`
  — a frozen, tracked evidence document — declares
  `"current_frozen_manifest_sha256": "7dbb2281…86186aa"`: **the sha256 of the
  ENTIRE dip1b_mvp_manifest_1_0.json FILE**, as its root of trust.
* Measured: HEAD's manifest bytes hash to exactly `7dbb2281…86186aa`; my
  amended worktree manifest hashes to `88630af7…d2159a`. The §BH22(a)
  amendment is the FIRST byte change to that file since its 2026-07-16 seal —
  so this was the check's first firing, ever.
* `EvidenceIntegrityResolver` (`apps/intelligence/evidence_integrity.py:319-323`):
  `manifest_verified = self.manifest_sha256 == manifest_expected`; when False
  → EVERY source-version's status becomes `UNVERIFIED_SOURCE_VERSION` with
  reason `FROZEN_MANIFEST_VERSION_UNVERIFIED`.
* `_result` (:445-449): classification is `STALE_IGNORED_OUTPUT` only when
  ALL unresolved rows are `STALE_GENERATED_OUTPUT`; otherwise `UNRESOLVED`.
  With the manifest unverified, the brand row can no longer reach
  `STALE_GENERATED_OUTPUT` → classification falls to `UNRESOLVED` → all four
  asserts fail (two direct, one via `evaluate_evidence_integrity`, one via
  the browser surfacing the classification string).
* **This is the guard working as designed, not a defect**: the whitelist that
  classifies the 21's divergence as the KNOWN stale state
  (`recognized_non_authoritative_versions` carrying `b4a891de…` + byte_size)
  is only trusted while the manifest itself is byte-identical to seal. Amend
  the manifest → the recognized-version list is no longer provably the sealed
  one → everything fail-closes to UNRESOLVED / REVIEW_REQUIRED.

**Why every prior gate was blind to it:** the §BH21 refused gate (failures=2)
ran with the manifest UNEDITED — post-regen artifacts moved the manifest's
ENTRY targets, not the manifest's own bytes, and these four tests scope the
brand correction policy (`dip1b_data_corr_1_brand_candidate_source_hash/1.0`),
not face entries. fedfab7/a06ccf6 green gates: manifest unedited, brand
mismatch = the known stale state → STALE_IGNORED_OUTPUT held. The coupling is
to the manifest's OWN BYTES, and no event in the entire §BH17–§BH22 arc had
ever changed them until the ruled amendment did.

## §3 — THE ENUMERATION: WHAT PINS THE MANIFEST'S OWN BYTES

`grep 7dbb2281` across both roots — SEVEN sites:

| site | role |
|---|---|
| `docs/design_intelligence/dip1/dip1b_evidence_integrity_registry_1_0.json:18` | **the ONLY live check** — read by the resolver at every evaluation |
| `bbrose_design_os/apps/intelligence/brand_evidence.py:35` (`FROZEN_MVP_MANIFEST_SHA256`) | constant emitted into generated `frozen_lineage` metadata; its test file passed at this gate — not compared to the live file |
| `dip1b_brand_evidence_2_0.json` · `dip1b_brand_evidence_manifest_2_0.json` | frozen lineage records of the 2026-07-16 state |
| `DIP-1B-5A_deterministic_brand_evidence.md` · `DIP-1B-2_bounded_import_browser.md` · `DIP-1B-DATA-CORR-1_brand_candidate_source_hash.md` | historical docs recording the seal |

* **The chain terminates**: nothing anywhere pins the REGISTRY's bytes
  (`grep 09a0ca9f…` = zero hits) — an authorized one-field registry amendment
  cascades nowhere.
* The registry is NOT among the manifest's 100 entries — no circular pin.
* The registry IS an evidence contract. §BH22(a)'s single-use authorization
  was scoped to "EXACTLY the 34 face_manifest entries in
  dip1b_mvp_manifest_1_0.json" — it does not reach this file, and "absent an
  owner sentence like this one, they may not."

**The blind-spot, scored against myself:** bh22_measure.py audited all 100
things the manifest PINS (the ruling's count gate — 34+21, no 35th — held
perfectly) but never asked what pins the MANIFEST. Third instance of the
same lesson: the 13-pin sweep missed 2 sites; the entry audit missed this 1;
the gate is the correct enumerator every time. Pins form CHAINS
(artifact ← manifest ← registry ← code), which sharpens the queued
corpus-pin architecture item.

## §4 — OVERLAP WITH §BH22(b), RECORDED NOT INVESTIGATED

The refusal mechanism itself surfaced that the 21's divergence is GOVERNED:
a correction policy (`dip1b_data_corr_1_brand_candidate_source_hash/1.0`),
a recognized-stale whitelist (`b4a891de…` + byte_size), lineage flags
(`new_dataset_is_distinct_version: True, old_bytes_recovered: False`), and a
correction record (`DIP-1B-DATA-CORR-1_brand_candidate_source_hash.md`,
cited by filename, NOT read). Recorded here because reporting the refusal
required reading the resolver; nothing beyond the mechanism was pursued —
the CORR-1 record's content and the 21's origin story stay unread and
unmeasured per §BH22(b). Note for the owner's eventual ruling on the 21:
the drafted queue item's sentence "its ORIGIN is unmeasured" is now
qualified — the divergence is at least GOVERNED, with its own frozen policy
apparatus; whether that apparatus EXPLAINS entries 78-98's specific pin
values remains unmeasured.

## §5 — PRED_A, SCORED LEG BY LEG, NO BAR LOWERED

| leg | declared | measured | verdict |
|---|---|---|---|
| L1 write set | staged manifest only; unstaged ledger+3 tests | exactly that (porcelain, pre+post) | HELD |
| L2 diff shape | +34−34 manifest (staged half) | verified pre-gate | HELD (commit half N/A — no commit) |
| L3 no new file | none | none | HELD |
| L4 staged==declared | both halves | both halves exact | HELD |
| L5 commit contents | amendment only | NO COMMIT — refusal | N/A by refusal |
| **L6 suite** | `TIER_2=GREEN 8490/0` | **`TIER_2=REFUSE failures=4`** | **MISS — and the leg's own declared consequence ("refusal on ANYTHING = hard stop, stop and report") is exactly what executed** |
| L7 ledger | fold to 423 committed, clean | 423 disk / 421 committed — **TWO orphans** (§BH21's + this run's) | MISS (conditional on landing, which didn't occur) |
| L8 apps/ untouched | zero apps/ edits | zero (porcelain) | HELD |

Claims: C1-C4 HELD (fresh-measured value written; count gate PASS; the 21
byte-untouched — post-gate porcelain shows no brand-pin change; single-use
quoted in the unlanded message). C5 moot (no landing). C6 HELD in the honest
direction: exit 1 captured, HEAD unmoved, landing NOT claimed.

## §6 — REPO STATE AT THE STOP, EXACTLY

* HEAD `a06ccf6`. No commit was created.
* STAGED: `docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json`
  (+34−34; old pin 0 occurrences, new pin 34 — the §BH22(a) edit, verified,
  still carrying the fresh-measured value `302679…e35c`).
* UNSTAGED: ledger (423 disk / 421 committed, two orphan refusal lines) ·
  `test_c4b.py` (130) · `test_c4c.py` (3969/2834) · `test_c5.py` (3969) —
  the declared commit-B set, byte-intact.
* Untracked-ignored: 3 new gate capture files (`20260901T014718Z_a06ccf6*`).
* The 21 brand pins: byte-untouched. The registry: byte-untouched. No
  tracked file moved outside the declared set.
* Drafted, durable, unlanded: `bh22_block.md` (transcription, `__AXHASH__`
  ×3) · `bh22_queue_append.md` (both queue blocks, `__AXHASH__`/`__P2HASH__`)
  · `pred_a.txt` (scored above) — all in ~/bh21_work/.

## §7 — GOAL STATE, HONESTLY: NOT REACHED, BLOCKED ON ONE SENTENCE

| goal leg | state |
|---|---|
| gate GREEN at final HEAD | NOT REACHED — REFUSE at the first landing |
| worktree clean | NOT REACHED — declared edits ride, unlanded |
| every commit with prediction declared+scored | pred_a declared+scored; no commit exists |
| §BH20(c) join measurement in the queue | NOT LANDED — drafted, placeholder-blocked |

## §8 — THE ONE OPEN DECISION (OPTIONS, NOT A RESOLUTION)

The amendment §BH22(a) ordered cannot pass any gate while the registry's
root-of-trust field pins the PRE-amendment manifest bytes. The registry is an
evidence contract; machines do not edit evidence contracts absent an owner
sentence. Options as I see them — the owner's sentence governs:

* **(i) Extend the authorization by one field**: amend
  `dip1b_evidence_integrity_registry_1_0.json:18`
  `current_frozen_manifest_sha256` → the amended manifest's hash, measured
  fresh at write time (today it measures `88630af7…d2159a`). Chain terminates
  (measured — nothing pins the registry). Count gate: exactly ONE field, one
  file. The five lineage records + the apps constant record the ORIGINAL
  2026-07-16 seal under "original/frozen" semantics and passed green at this
  very gate — on my reading they are historical records, not live checks,
  and would stay untouched; if the owner reads them differently, the
  owner's sentence governs. Landing shape (whether the registry field joins
  commit A or is its own commit) is also the owner's call — both edits must
  ride the worktree together for ANY gate to green, same logic as before.
* **(ii) Withdraw the 34** (unstage + restore the manifest) — returns the
  repo to the §BH21 refused state (failures=2) and contradicts §BH22(a)'s
  own sentence; listed for completeness only.
* **(iii) Fold this into the queued corpus-pin architecture redesign** —
  leaves §BH22 unfinishable until that design exists.

Under (i), the remainder resumes exactly as ruled: A′ (re-pin + registry
field) → C (transcription) → B (pass 2) → D (queue record, final gate) —
predictions sealed before each gate, scored after, hard stops unchanged.

## §9 — WHAT IS NOT ASKED FOR HERE

Nothing beyond the one sentence in §8. The 21 stay untouched and queued;
the four owner-gated items stand (this refusal sharpens the corpus-pin
architecture item with the pin-CHAIN fact); C3 stays BLOCKING by
construction; the OFL reading stays the owner's alone (§BH12(a)). No test
was edited, no evidence contract touched beyond the still-staged §BH22(a)
amendment itself, no bar moved.
