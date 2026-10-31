# BBROSE Design OS — open defect inventory

Recorded 2026-08-07 at `67151ef356de1207e3ee86894ecbb11c6b10f19a`.

This is a register, not a plan and not a status report. Everything in it was
established by reading the repository at that SHA; nothing is carried over from
a prior document, because the prior documents are part of what is wrong. Each
entry names the evidence it rests on so it can be argued with.

The repository's own rule is that exactly one milestone is primary at a time.
This register does not overturn that. It exists so the queue behind the active
milestone is written down rather than rediscovered, and so that defects sharing
a root cause are fixed once rather than seven times.

---

## The organising observation

Six of the eight highest-severity items in this register are the same defect.
Not the same symptom — the same defect:

> A property is **declared** of some artifact, the artifact does not have it,
> and nothing in the system is capable of noticing.

The Bump node whose amplitude went into `Strength` while `Distance` was never
set. The grain scales sitting below the anti-aliasing limit while the record
said the grain was there. The frame written as `_16bit.png` that is 8-bit RGBA.
The negative control that reports `behaved: true` because the instrument it was
controlling is dead. The `progress_tracker.json` that says `NOT_STARTED` for
five milestones that have shipped. The `README.md` describing a system a third
the size of the one on disk.

The project already has the correct response to this written down — *a defect
class that returns a third time gets a structural guard, not more care*. This
class has now returned at least four times. The response therefore is not to
fix six bugs. It is to make the class unrepresentable, in the one place where
it does the most damage first: the measurement chain that M6 is currently
asking to adjudicate powder families.

---

## A — Blocking the active milestone (M6)

These are documented in full, with measured numbers, in
`axis_instrument_defect_findings.json` (findings F1–F8) and answered by the
declared repair `palette_instrument_repair_protocol.py`, identity
`1e198aed8d86ed9c`. Summarised here only so the register is complete.

**A1 — the measurement frame is not what the instrument thinks it is.**
`swatch_*_16bit.png` is 8-bit RGBA. The texture axes average all four channels,
so the quantity every one of them is computed from is `(R+G+B+255)/4`. The only
reading under which `GRAZING_BAND_CONTRAST` passes its own positive fixture is
the contaminated one: 0.2683 with alpha, 0.1078 on RGB, 0.1252 on the
scene-linear EXR, against a bar of 0.25. A verdict that depends on how many
channels the reader happened to average is not a verdict.

**A2 — `SURFACE_AUTOCORRELATION_MM` returns 0.140000 mm on every frame ever
measured**, including both members of its own positive fixture where grain
scale doubles. 0.14 mm is exactly 2 px. It correlates a field that a 3×3 box
high-pass has just whitened, so it reports its own kernel support. It is not
insensitive; it is measuring the instrument.

**A3 — `EDGE_HIGHLIGHT_RESPONSE` cleared the 25% pass bar on a seed-only
negative control** (0.27991, two `POWDER_MATTE` specs differing only in random
seed). `MATTE_vs_SATIN` was ruled PASS on exactly two clearing axes, one of
which was `EDGE` at 0.3604 — 1.29× its own measured noise floor. That PASS is
not supported by its own evidence. `PRESSED_vs_MATTE` cleared on three axes and
survives the removal.

**A4 — "independent axes" is asserted, never measured.** Four of the six lobe
axes read the identical scalar `highlight_fwhm_fraction`, differing only by
region. The §6 correction already caught this once and changed *which* scalar
was shared rather than removing the sharing. `PASS_LAW` requires two
*independent* axes; independence is currently a word in a docstring.

**A5 — no stimulus-realization control exists anywhere.** Renders are
deterministic and fixture pairs share a seed, so an unrealized parameter yields
bit-identical frames and every axis reports exactly 0.0 — which the study
records as "the axis is blind". That is the false conclusion drawn at `927ab8a`
and withdrawn at `05d481c`. `texture_axes_validation.json` still carries its
fingerprint: `low == high` to six decimal places on all three axes.

**A6 — silent zero fallbacks.** `lag_mm` stays 0.0 when variance is below the
numerical floor; `contrast` returns 0.0 when the region median is zero. A
reader cannot distinguish "measured zero" from "declined to measure".

**A7 — the GLITTER rig's PASS is in question, not overturned.** The 87-event
census at `27ded17` reads the same `png16`, and the comment justifying that read
says in terms that 8 bits would crush event contrast into quantisation noise.
Re-measure from the EXR; confirm or withdraw.

**A8 — cleared, recorded so it is not raised again.** `surface_roughness` *is*
plumbed to the Principled BSDF (`powder_materials.py:204-207`). Its near-zero
effect on `POWDER_MATTE` is correct physics — the micro-normal field dominates
the lobe, exactly as the family docstring claims. The `ROUGHNESS_ONLY` fixture
behaved as designed.

---

## B — The progress record contradicts the repository

**B1 — `docs/roadmap/progress_tracker.json` is wrong about the active
programme.** It records `PALT-M2` through `PALT-M7` as `NOT_STARTED` and titles
`PALT-M6` "artwork + shade system + .AI export". On disk: M1–M3 are
owner-accepted, M4 was owner-rejected and repaired through M4B/M4C, M5 closed
19/19, and M6 is the powder engine, mid-flight. The file was last written
2026-08-05 and five commits have contradicted it since.

This matters more than a stale document normally would, because of B2.

**B2 — the only legitimate source of a progress number reads the wrong file.**
The methodology states, correctly, that `manage.py roadmap_status` is the sole
authority for a progress percentage. It computes that percentage from
`progress_tracker.json`. So the one number the project permits itself to quote
is derived from a record the repository can already prove wrong. A reconciliation
is owed, and it is not in `next_executable_node`.

The deeper fix is structural and belongs with the class in A: the tracker
should not be able to say `NOT_STARTED` about a milestone that has a closure
record on disk. That is a checkable invariant, not a discipline problem.

**B3 — five top-level documents describe a substantially smaller system.**
`README.md`, `PROJECT_DOCUMENTATION.md`, `EXECUTION_STATUS.md`,
`AUDIT_REPORT.md`, `BBROSE_DesignOS_Milestones*.md` — all July 2026. Two
specific claims in them are affirmatively false rather than merely stale: that
the IRE M3 backbone "sits unused" (it is wired live into `reconstruct_container`
via `m3_backbone.build_container_backbone`, commit `d92c370`), and the M6
numbering described in B1. Anyone onboarding reads these first.

---

## C — Structural drift traps

**C1 — the dieline template lists disagree.** `TemplateType` in
`apps/dielines/models.py` declares four choices; `_REGISTRY` in
`apps/dielines/registry.py` registers six `template_id`s —
`ecma_a20_20_01_01_ste_carton` and `reference_opposed_tuck_carton` exist in the
registry with no enum member. A template registered but not enumerable is
reachable by some code paths and not others.

**C2 — adding a Design Target breaks three separate target lists.** Known and
documented; not yet guarded. The same shape as C1: one fact, three places, no
assertion tying them together. Both are the declared-versus-realized class
again, wearing different clothes.

**C3 — Git LFS is not installed and the migration was never performed.**
`git lfs` is not a command in this working copy, and the repository is
accumulating EXR and PNG render evidence in ordinary object storage — 121
modified files in the working tree right now, most of them frames. This is not
urgent and it is not free; it gets worse monotonically.

**C4 — the sanctioned commit path could not commit its own gate verdict. FIXED
2026-08-24.** `tools/record_integrity.py` appends a verdict line to the tracked
`record_gate_ledger.jsonl` on every run of `tools/guarded_commit.sh`. Staging is
the CALLER's act and happens before the script is invoked; the append happens
inside it. So the line describing a commit's gate run was never in that commit —
it was swept into the NEXT one. The committed history therefore never held the
verdict for the commit it judged, and a clean working tree was unreachable
through the sanctioned path by construction. Measured at `9456e7d`, which
carries the `2026-08-22T11:24:55Z` line while its own `2026-08-24T01:28:50Z`
line was still unstaged after it returned. **The shape is C1 and C2 inverted:**
not one fact written in three places with nothing tying them together, but one
act split across two agents — the caller who stages and the script that appends
— with nothing sequencing them. Fixed by staging the ledger inside the script,
between the `--dry-run` exit and `git commit`. **How often it actually bit,
population stated (§A564):** over the 50 consecutive ledger-commit pairs in
history, **10 commits omitted a ledger line that was already on disk when they
were made**, the worst by 926 minutes. The other 40 committed a complete ledger
because they did not go through this script and so had no line of their own to
leave behind. The structural claim is the universal one and needs no count —
staging precedes the append, so a commit *through this path* cannot contain its
own line; the count only says how often that path was taken. Two earlier drafts
of this measurement were wrong in opposite directions, one unable to distinguish
the fixed case from the broken one at all and the next defeated by dry-run lines
landing between commits. **The limit:** the fix does not realign what already
exists. Those 10 stay misaligned; nothing was lost and nothing is retro-attached.

**C5 — the §Y2 source-guard census could only see one assertion dialect. FIXED
2026-08-24.** `apps/pipeline/tests/test_wig_source_string_guards.py` enforces
§Y2 by walking `apps/` with `ast` and classifying every test that asserts only
on source text. Its scanner implemented `visit_Assert`, which fires on
`ast.Assert` and nothing else, so **every `self.assertX` in the repository was
invisible to it** — the entire `unittest` half of the suite. Two further blind
spots compounded it: `.sh` was not a source suffix, though `guarded_commit.sh`
is the commit path itself, and a guard that binds `i = src.index(a)` before
comparing scored zero where the inline `src.index(a) < src.index(b)` scored
one, penalising the clearer form. **This is neither the C1/C2 shape nor C4's:**
it is an instrument whose answer was correct about a smaller population than
the one it named. The census reported 64 guards and 14 visible declared ones,
and both numbers were true of pytest-styled tests only. Nothing in the numbers
could reveal that, which is the property worth carrying — a blind spot does not
present as a wrong figure, it presents as a right figure with an unstated
denominator. **Measured, all eight subsets of the three fixes:** no fix moves
the visible-declared count alone; two pairs move it to 15; only all three reach
16. The position fix is necessary for every movement and sufficient for none.
**Cost, measured rather than estimated:** 2 previously-uncounted guards in 2
files, both genuine, added to `REGISTERED_UNDECLARED` (50 → 52). The commit
that fixed C4 declined this repair on a written estimate of "tests across 58
files" — **an overstatement of 29x, and the sole §AC justification given for
deferring.** 58 was the count of files where the blind spot *could* apply, not
where it did. **The limit:** a fourth blind spot remains, is known, and is not
fixed — a guard that scans source through `git grep` in a subprocess opens no
path and binds no name, so the census cannot see it. Population re-measured
after this repair, not assumed: exactly one file in `apps/` does that, and it
is `apps/ire/tests/test_wio_on_pack_copy.py`, which documents its own case.

**C6 — §AE0(a) is the one rule allowed to hold absolutely, and no instrument
enforced it. ENFORCEMENT FIXED 2026-08-24; THE RECORD IT PRESUMES IS STILL
OWED — filed A19.** The rule says `owner_acceptance` is
**untouchable** and that **no status containing `OWNER_ACCEPTED` / `ACCEPTED` /
`APPROVED` / `SIGNED_OFF` is written by the executor for any node, ever** —
§Q's *no self-approval at any gate*, narrowed to the one place it must hold
absolutely so it can be relaxed everywhere else. It is enforced by prose alone.

**Measured, in-process against the real tracker, caches refreshed each time as
any editor of the file would refresh them.** Population one: the 56 nodes whose
`owner_acceptance_percent` is 0 and whose status is not already barred from
carrying acceptance — every node an executor could raise today. Raise one to
100 and **0 of 56** are caught by `test_roadmap_tracker.py`, all 39 tests. A
first pass without refreshing the caches appears to catch 45, but every one of
those findings is *cached rollup drifted*, never *acceptance*, and all 45
vanish on recompute — the cache guard reads as an acceptance guard and is not
one.

Population two: all 95 nodes not already `OWNER_ACCEPTED`. Flip the status
outright and 63 are caught — but **58 of the 63 are
`test_tracker_is_fully_valid` and
`test_every_critical_path_item_has_a_valid_ordered_node` objecting that the
node's IMPLEMENTATION is incomplete**, which is an accident of where the node
sits, not a refusal of self-approval. The four acceptance-shaped tests fire on
exactly one node each: the ones they pin by name. **32 of 95 escape in silence,
and one is `cp.pilot_evidence`, whose status is `REJECTED`** — a record of a
failed pilot, flippable to `OWNER_ACCEPTED` with nothing objecting.

**The evidence asymmetry is the root of it.** `EVIDENCE_REQUIRED` does include
`OWNER_ACCEPTED`, but it is discharged by `evidence_commits or evidence_tests`,
both of which the executor writes. Population: every key in
`progress_tracker.json`. The acceptance-adjacent keys are `evidence_commits`
(106), `evidence_tests` (106), `evidence_screenshots` (106) and
`owner_decision_required` (106) — **there is no field anywhere that records an
owner's act**, and `evidence_screenshots`, the closest thing to owner-facing
evidence, is not even accepted as sufficient. So the only evidence that can
discharge an owner acceptance is evidence the executor produced. Of the nine
nodes born at 100 in `7bc9293`, exactly one cites a commit whose subject
records an owner act (`ire.m3_backbone` → `32cedf9`). That is not evidence the
other eight were unaccepted; it is that the tracker has nowhere to say so.

**No violation exists to date and this is not a live breach.** All three
acceptance writes in the tracker's 37-commit history are dated 2026-08-03;
§AE0(a) entered at `c69787d`, 2026-08-20. Nine tracker commits have landed
since and none touched acceptance. **The limit, stated:** git authorship cannot
distinguish executor from owner in this repository — two authors exist
repo-wide, every recent commit is the same one — so a mechanical guard cannot
be built from provenance. What settled the audit was two subject lines naming
an owner decision. Any fix has to invent the record the rule presumes, and that
is an owner question, not an executor one, which is why this is filed rather
than repaired.

> **REPAIRED THE SAME DAY, and the sentence above is left standing because it
> is half right.** *"Any fix has to invent the record the rule presumes … which
> is why this is filed rather than repaired"* conflated two jobs that separate
> cleanly. **Building the place the record goes is an executor job. Filling it
> is not.** The first is done; the second is A19 in `OWNER_INPUT_MANIFEST.md`.
>
> `owner_acceptance_evidence` is now a required field on any node claiming an
> owner acceptance — by `owner_acceptance_percent > 0` **or** by status, which
> covers both halves of §AE0(a), the dimension clause and the write clause that
> binds at node CREATION where no delta exists. It takes one of three kinds:
> `OWNER_RULING_COMMIT` (locator + quote + date, all three required non-empty),
> `OWNER_MANIFEST_SECTION`, or `UNRECORDED_PREDATES_FIELD`, which is available
> only to a **frozen set of eight node ids written in code**. Present without a
> claim is also a finding, so the evidence cannot be staged before the
> acceptance it justifies.
>
> **Both counterfactuals re-measured by the same method that produced the
> numbers above, caches refreshed each time.** Population one: **0 of 56 → 56
> of 56.** Population two: **63 of 95 (32 escaping, including the `REJECTED`
> `cp.pilot_evidence`) → 95 of 95, none escaping.** The 58 findings that were
> really *implementation incomplete* are still there; they are no longer doing
> the work alone.
>
> `verify_acceptance_evidence` runs `git log -1 --format=%B` on each named
> commit and requires the quoted words to appear in it. All three real entries
> resolve today: `ire.m3_backbone` → `32cedf9` (`VQ1_OWNER_ACCEPTED`),
> `pc.vqr1_m3_integration` → `99415f5`, `quality.fail_closed_gate` →
> `acbbcf7`. A fabricated sha and a real commit quoted with words it never said
> are both caught, and both cases are tested.
>
> **THE RESIDUE, STATED RATHER THAN IMPLIED: this buys FALSIFIABILITY, NOT
> UNFORGEABILITY.** The check proves the commit exists and that the sentence is
> in it. It cannot prove the sentence was about *this node* — an executor can
> still aim a genuine owner ruling at the wrong one. Closing that needs an
> owner-written record git cannot supply here, since authorship does not
> distinguish the two actors in this repository. **And the eight
> `UNRECORDED_PREDATES_FIELD` entries are not a finding of innocence or of
> guilt.** They are the statement that the repository cannot show those nodes
> were accepted. Owner confirmation replaces them; nothing else may. The
> grandfather set may only ever SHRINK, and a test refuses any addition to it.
> Two of the eight are flagged in place as ones the executor would not sign:
> `pkg.archetypes` (recorded authority is `TECHNICALLY_QUALIFIED_DOMAIN` only,
> so `100` claims more than the record supports) and `ire.gate_a_roundtrip` (a
> technical gate passing is not an owner accepting).

---

## D — Standing blockers (external or owner, not fixable by code)

These are recorded in `palette_roadmap_continuation_state.json` and are
unchanged. They are listed so that no plan silently assumes them away.

**D1 — `SUPPLIER_DATA`.** No approved outbound channel; 0 of 5 supplier
requests sent. `MANUFACTURING_AUTHORITY` is `NOT_ESTABLISHED` and cannot be
established from inside the repository.

**D2 — `MATERIALS_LIBRARY_ABSENT`.** Native `.ai` sources are not in this
working copy.

**D3 — `ES3083_DIMENSIONS_UNREADABLE`.** No readable millimetre value exists;
every P1B dimension is a `PROVISIONAL_DESIGN_DEFAULT`. Every downstream
geometric claim inherits that provisionality.

**D4 — `VQ1_HUMAN_STRUCTURAL_REVIEW`. CLOSED 2026-08-13.** The original text —
"the M4C-4 confirmation panel was served but never confirmed by the owner in a
browser; no amount of engineering closes this one" — was **true when written and
false from 2026-08-12**, and it stood false for a day because nothing compared
it to the session record that disproved it.

*Both surfaces are satisfied, and the entry named two.* Its title named the
**VQ-1 human structural review** (container/dropper geometry); its body named the
**M4C-4 intent panel** (design-intent classification). Two different owner
judgment surfaces in one entry, which is why checking either one never resolved
it. VQ-1 was **owner accepted 2026-07-28** (`vq1_owner_acceptance.json`, commit
`6fb8262`, candidate M3, loop `PERMANENTLY_CLOSED`). The M4C-4 panel was
**confirmed 2026-08-12** — task 9, three versions, gate decisions 57 and 58,
scope `VISIBLE_COMPOSITION_ONLY`, now landed in `docs/` at
`palt_m4c/m4c4_panel_confirmation.json`.

*Closing this grants no authority, and both surfaces said so themselves.* The
VQ-1 acceptance carries `acceptance_is_production_authority: false`,
`is_manufacturable: false`, `is_tooling_ready: false`,
`is_production_geometry: false`, certifying only
`CONCEPT_VISUAL_STRUCTURAL_GEOMETRY`; the M4C-4 confirmation left all four
programme flags unchanged. What closed is the **owner judgment**.
`PALT_P1_FINAL_DIMENSIONS NOT_APPROVED`,
`PALT_P1_MANUFACTURING_AUTHORITY NOT_ESTABLISHED`,
`PALT_P1_OWNER_APPROVAL NOT_GRANTED` and `GATE_2 BLOCKED` are untouched and
remain the gate.

**D5 — colour authority: DOWNGRADED 2026-08-13, NOT CLOSED.** It no longer
reads "colour authority does not exist" — for ES3083's pan shades it now does.
It does not close, because one of the two things a close would assert is not
yet true. Both residuals are named below rather than folded into the headline.

*What resolved.* `pan_shades` are resolved to `OWNER_CHOSEN_DESIGN_INTENT` —
twelve owner-decided shades, stamped **per shade** so any one can be upgraded
without touching the other eleven. The record is
`docs/roadmap/palt_m6/es3083_shade_authority.json` at
`es3083_shade_authority/1.3`, sha256
`7c98a2637b4a20049a40aa2d79abc6d6169c19da06a893deb4d2c2e68f520ed7`
(1.1 corrected the Residual-2 direction and the deferral justification; 1.2
records that the transform is now applied and that the twelve have been
rendered — no colour moved in either), deciding
document `SHADE_AUTHORITY_PROPOSAL.md` sha256
`612dd0aa608a48f02e9ce972d5523c6c1e4550b87eecdae70c5a36facb9bf7c6`.

*What is untouched.* PANTONE **621 C / 627 C are CASE colours, not pan
shades**; they remain governed by `SPOT_COLOUR_AUTHORITY` in
`palette_design_graph.py`, still `UNRESOLVED_SPOT_COLOUR`, and this record does
not touch them. **FB3090 remains `UNSOURCED`** — this record is ES3083 only.

*Residual 1 — chosen, not measured.* Nothing here matches a physical chip, a
Pantone number or a spectrophotometer reading. This is the weakest admitted
tier. It is **sufficient to make artwork and to put a deliverable in front of a
client**, and it is **NOT manufacturing colour authority**.

*Residual 2 — REPAIRED IN CODE at beb1fe5, and now awaiting the only judgement
that can close it.* **As originally found:** the shades are stored sRGB and
`PowderMaterialSpec.realize()` passed them **untransformed** as `display_rgb`
into a **scene-linear** consumer (`blender_scripts/powder_materials.py:168`,
Principled BSDF `Base Color` `default_value`), with no sRGB-to-linear transfer
anywhere on the path — extent: `srgb|to_linear|linear_to|gamma|1.055|
0.0031308` over every `.py` in `blender_scripts/` plus
`palette_powder_engine.py`; the only hits were display-side
`view_settings.gamma = 1.0`.

**That is fixed.** `realize()` now resolves the space through
`COLOUR_SPACE_BY_AUTHORITY` and emits `shader_input_rgb` in `SCENE_LINEAR` for
owner shades, leaving provisional shades untouched. Midnight Bloom reaches the
shader at 0.068480 / 0.027323 / 0.043745, verified before rendering. The twelve
have been rendered on the commissioned rig and composed for review:
`docs/roadmap/palt_m6/owner_swatches/es3083_owner_twelve_grid.png` and
`…/es3083_owner_twelve_chip_vs_render.png`.

**D5 still does not close**, and the reason is no longer a code defect: it
closes when the owner looks at those images and accepts them. That is a
judgement, not a measurement, and it is not the executor's to make.

**Direction, corrected 2026-08-13.** An earlier revision of this entry said
these render "materially darker than chosen." **That was inverted.**
`srgb_to_linear` is strictly *below* the identity on the open interval (0, 1),
so handing an sRGB-encoded value to a linear socket sets an albedo that is too
**high**, and every pan arrives **LIGHTER and less saturated** — never darker.
Proven, not asserted: `TransferDirectionTests` in `test_powder_engine.py`
samples 20,001 points across (0, 1) in each direction, fixes the endpoints as
equalities, and pins the segment knee at 0.04045 / 0.0031308.

**The error is not uniform, and that is the real finding.** It is negligible
at the light end and severe at the deep end: Petal Veil's lightest channel
gains 0.0282, Midnight Bloom's green gains 0.2814 — an order of magnitude
apart. So the palette's own structure degrades, not merely its brightness. The
depth run **Damascena → Blush Hour → Old Rose → Thorn** retains only **68.3%**
of its intended spread (0.4288 → 0.2930), because its pale members arrive
nearly correct while its deep members do not. A uniform shift could be dialled
out downstream; a compressed depth run cannot, and it is the thing the palette
was designed around.

**Worked example, computed.** Midnight Bloom, intended `#4A2E3B` = sRGB
0.2902/0.1804/0.2314. Its correct scene-linear albedo is
0.068480/0.027323/0.043745; it is fed 0.2902/0.1804/0.2314 instead. Under
neutral unit illumination the albedo round-trip arrives at
0.5751/0.4618/0.5183 — **`#937684`**, a pale dusty mauve where a deep plum was
chosen. (Arrival is the albedo round-trip, not a render prediction: lighting,
BSDF and roughness all intervene in a real frame. The *direction* is
unconditional because the albedo is unconditionally too high; the *magnitude*
is the flat-lit figure.)

The record carries a derived `rgb_linear` per shade under
`IEC_61966_2_1_sRGB_EOTF`. Since beb1fe5 the engine also applies the transfer
itself in `realize()`, so a renderer reading `shader_input_rgb` — or
`display_rgb`, which is now a frozen-contract alias of it — gets scene-linear
values without doing the conversion twice.

**Why the fix was deferred — justification corrected 2026-08-13.** The earlier
revision said fixing the shader "moves every `material_identity` in the
programme." **That was wrong.** `material_identity()`
(`palette_powder_engine.py:510-516`) digests schema, version, family, seed,
`shade.to_dict()` and params; `powder_materials.py` is not among its inputs, so
editing the builder would move **no** material identity at all. The real
constraint is that `powder_materials.py` is the **frozen instrument**: every M6
measurement was taken through it, and its repair is
**`M6-CONTRACT-INTEGRITY-REPAIR`'s named jurisdiction**, recorded at
`independence_amendment_phase4.json` (`builder:specular_ior_level` and the
other builder drivers, "varying it means editing the frozen instrument, which
is M6-CONTRACT-INTEGRITY-REPAIR's jurisdiction and may not start inside this
node"). The refusal stands; only its justification changes.

*Also inconsistent, deliberately not repaired here.* The hashed
`COLOUR_AUTHORITY` block in `palette_powder_protocol.py` still reads
`pan_shades: NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY`. That is now
stale. It sits inside `protocol_identity()`, so correcting it is an
amendment-scale act requiring owner authorization, and it was not performed as
a side effect of landing a shade record.

**D7 — no mechanical control compares a computed material identity to a
recorded one. OPEN, and deliberately NOT scheduled.**

*The finding.* The record gate binds record **bytes**; nothing binds identity
**agreement**. An engine change that moves `material_identity()` rewrites no
committed record, so `record_integrity` stays green, `protocol_identity` does
not move, and the suite passes — while every identity recorded in the M6
corpus silently stops being reproducible from the code that claims to produce
it.

*Extent (A564), reproduced from the survey that found it.* 671 distinct
material identity values across 1,433 files, 1,497 occurrences — predicate:
leaf keys `material_identity` / `POWDER_MATERIAL_IDENTITY` matching
`^[0-9a-f]{16}$`, population: every `.json` under `docs/**` parsed and walked
to leaves. **1,067 of those occurrences sit inside measurement frame and rig
directories** (`independence_sweeps/frames` 809, `realization_audit` 108,
`texture_axes` 84, `combined_manifest/frames` 63) and are load-bearing: they
identify the material each M6 frame was rendered from. Comparison sites —
predicate: every line mentioning a material identity alongside `assert`, `==`,
`!=`, `mismatch` or `compare`; population: every `.py` under `apps/ tools/
docs/ scripts/` — **5 sites, all in one test file, all relational between two
freshly computed values. Zero compare against a stored one.** `tools/
record_integrity.py` and `tools/tier2_gate.py` contain **zero** references;
`protocol_identity()`'s payload contains **zero**.

*The consequence.* An accidental engine change invalidates the M6 measured
corpus with every test and every gate still green. The failure mode is silent
by construction, and it is undetectable after the fact.

*What this is NOT.* Not a colour bug. Not part of D5 — D5 is ES3083 shade
authority and this is corpus reproducibility. **Not caused by this arc**: it
predates all of it, and it was found by a survey run for another reason (the
blast-radius measurement for the colour-space fix, 5cb30f3). Nothing in the
colour-space work moved a material identity; the survey that proved that is
what exposed the absence of any check that would have noticed if it had.

*Status: OPEN, NOT SCHEDULED.* M6 is parked. A verifier for a corpus nobody is
extending is work at the wrong time, and building it now would be motion
rather than progress. It is recorded so that whoever resumes M6 finds it
before they trust an identity.

*Closing it would require* a control that recomputes each recorded material
identity from its recorded spec and refuses on disagreement — which presumes
the specs were recorded alongside the identities.

**That presumption was checked on 2026-08-13, and it is FALSE. D7 is therefore
not a verifier somebody owes; it is a permanent loss.**

*What was checked, and how.* Extent: all 1,677 `.json` files under
`docs/roadmap/palt_m6/**`, each parsed and walked to every leaf. **1,377 carry
a material identity. ZERO of them carry the four fields needed to recompute it**
(`family`, `seed`, `shade`, `params`) — 1,373 carry none of the four, two carry
`family`+`seed`, one carries `family`, one carries `seed`. `material_identity()`
digests all four plus schema and version, so a partial record recomputes
nothing.

*Then the harder question: is the spec reconstructible from committed code?*
Brute force over **45,990 candidate specs** — all 9 families × all 35 shades
constructed anywhere in committed code (11 named rig shades plus both
twelve-shade sets) × 146 seeds covering every literal and ensemble range in the
tree — against the **671 distinct recorded identities**.

> **Hit rate: 74 of 671 — 11.0%. 597 identities are unrecoverable.**

*Why, and it is structural.* The recovered 74 are default-parameter renders.
The unrecoverable 597 are **parameter-sweep frames** — 303 in
`independence_sweeps/frames`, 107 in `realization_audit`, 29 in
`flake_rig/sweep`, and so on — where each frame was rendered with per-level
`overrides` that entered `params`, moved the identity, and **were never written
down anywhere**. No search of code can recover them because the value was
generated by a loop and discarded.

*What this means.* The M6 measured corpus **cannot be re-derived**. Not by a
verifier, not by anyone, because the inputs are gone rather than merely
unchecked. M7 would inherit family rulings that can never be checked against
the materials that produced them. The 1,067 load-bearing identities are
**permanently unverifiable evidence**: they are still records of what was
measured, and they can no longer be shown to be records of what the code
produces.

*Status is unchanged: OPEN, NOT SCHEDULED, and no verifier is to be built* —
building one would now be worse than useless, since it could only ever confirm
the 11% that were never the problem. What is owed is a **decision** about
whether the M6 corpus is cited as evidence going forward, and that decision is
the owner's.

**D8 — the rig's validated measurement window does not cover the depth range of
the shipping palette. OPEN, NOT scheduled.**

*The finding — REWRITTEN 2026-08-13, because the original wording was wrong and
the alarm was overstated.* What I first wrote was: "the affected shades are
refused rather than measured badly, which is the instrument behaving correctly."
**That is false. Those shades are not refused, because they have never been on
a path that reads the guard.** The twelve owner swatches were rendered through
`characterize_powder`, which carries **no window guard at all**; `:661` lives in
`_measure_pair_per_member`, on the texture-axis path, which the palette has
never entered. That is also why `POWDER_METALLIC` renders at 0.1767 in
`swatches/` without being refused — the same observation that first suggested
the guard might be dead.

*The guard is not dead, and here is where it can fire.* Extent:
`_measure_pair_per_member` — the function containing `:661` — has exactly **two**
callers, both inside `palette_powder_texture_axes.py`. (1) `:629` from
`characterize_texture_pair`, the **calibrated** path: it iterates energy toward
`CAL_TARGET` 0.88 and breaks only on a peak inside the window with zero
clipping, raising elsewhere if four iterations fail — so `:661` is nearly
redundant there, but **not** dead, because calibration renders at
`max(24, samples//2)` and `_measure_pair_per_member` re-renders at full
samples, so a marginal peak can drift below 0.35 between them. (2) `:690` from
`measured_pair_at`, the **uncalibrated reuse** path — no calibration happens at
all. Its callers are `palette_axis_eligibility.py:101` (ensemble members 3–6
reusing the first member's energy) and `palette_powder_texture_axes.py:859`
(the §7 controls). **On that path the guard fires whenever a subject reuses an
energy solved for a lighter one** — which is exactly what measuring a palette
of this depth range at one energy would do.

*So the corrected finding is narrower and different from my original claim.*
It is not "the palette is being refused". It is: **the palette has never been
measured on the guarded path, and if it were, its depth range could not be
measured at a single reused energy** — each deep shade would need its own
calibration, and the shades below the floor after calibration would then be
refused. The coverage question is real; the refusal I described has not
happened to anything.

*The count, with the peak definition stated — because two definitions give two
answers.* **(A)** The quantity the guard actually reads is the *rendered*
`regions.PLANAR.scene_linear_peak`. Measured on the twelve committed swatches
(`owner_swatches/`, default rig energy): **eight of twelve below 0.35** — Blush
Hour 0.267, Attar 0.296, Copper Leaf 0.054, Sage Stem 0.219, Old Rose 0.111,
Thorn 0.060, Moss Garden 0.084, Midnight Bloom 0.014. **(B)** The *albedo* peak
channel, `max(srgb_to_linear(hex))`, gives **five** — Sage Stem 0.231, Old Rose
0.266, Thorn 0.109, Moss Garden 0.098, Midnight Bloom 0.068, with Copper Leaf
marginal at 0.392. **(A) is the count against the guard's own quantity; (B)
measures albedo, which the guard never reads.**

*Bound on both numbers, which neither answers.* Neither predicts what the
texture path would actually do, because `characterize_texture_pair` **calibrates
source energy per member toward `CAL_TARGET` 0.88 before** `:661` is reached,
and raises separately if that calibration fails to converge in four iterations.
Whether calibration can lift these shades into the window is untested here. The
counts above describe the committed swatches at default energy, not the
outcome of a texture-axis run.

*The causal note, which is the uncomfortable part.* These shades moved out of
the window **because of beb1fe5**, the colour-space fix. Measured, not
estimated: Moss Garden rendered on the default rig at its pre-transform albedo
(0.2824, 0.3451, 0.2471) peaks at **0.2866**; at its post-transform albedo
(0.0648, 0.0976, 0.0497) it peaks at **0.0835**. It was already under the floor
before the fix and the fix pushed it 3.4× further under. **Both facts are
recorded because both are true: the transform was correct, and the transform is
what put the palette this far outside the instrument's range.** The fix is not
in question; its consequence for measurability is.

*A related fact that widens the finding.* The floor is not only a
new-palette problem. Of the nine families in `docs/roadmap/palt_m6/swatches`,
`POWDER_METALLIC` renders at **0.1767** — one of the nine proven families is
itself below the window floor. The nine span 0.177–0.568, median 0.462; the
frequently-quoted "0.53" is `POWDER_MATTE` alone, not a group value.

*The compounding relationship to D7.* The M6 family proofs were established
inside a window that most of the shipping palette sits below, **and** per D7 the
corpus that established them cannot be re-derived — 597 of 671 recorded
identities are unrecoverable. Jointly these permit the M6 corpus to be cited
for exactly one thing: **that the instruments, as commissioned, distinguished
the families they were run on at the lightnesses they were run at.** They
forbid it being cited as evidence about how the shipping palette behaves, as a
reproducible measurement, or as support for any claim about a shade the window
would refuse. A verdict established on materials that cannot be reconstructed,
inside a range the product does not occupy, is a record of a past experiment
and not a property of the product.

*Status: OPEN, NOT scheduled.* M6 is parked and re-commissioning a rig is not
a thing to start while it is. `SUBJECT_WINDOW` is **not** widened here.

*Closing it would require* either a commissioned exposure path that brings
deep shades into a validated window without changing what the axes mean, or a
second validated window with its own floors and controls for the deep range —
either of which is a rig commissioning, not an edit. Nothing needs doing until
someone actually tries to measure the palette on the texture path.

**D9 — nothing compares a recorded blocker against evidence that disproves it.
OPEN.**

`MATERIALS_LIBRARY_ABSENT` sat in `palette_roadmap_continuation_state.json` as
an `EXTERNAL` blocker on M7, asserting the materials library was absent and the
`.ai` sources unopenable. Both halves were false: 7,695 files and 29.90 GB were
present, gitignored as a deliberate read-only source library, and the ES3083
`.ai` opened with a parser already in the venv and already used by
`tools/dip0/detect.py`. `ES3083_DIMENSION_FINDINGS.md`, at the repository root,
disproved it in its first paragraph. The two artefacts were never compared, and
nothing in the programme was capable of comparing them.

*What control would have caught it, and does one exist?* A control that treats
every recorded blocker as a falsifiable claim and requires each to name a
predicate a machine can evaluate — `path exists`, `parser opens it`, `record X
absent` — so that a blocker whose predicate now evaluates false is surfaced
rather than inherited. **No such control exists anywhere in the programme.**
Extent: every `.py` under `tools/` (11 files) and the suite's control tests —
none references `palette_roadmap_continuation_state.json` and none mentions
blockers at all. The nearest existing thing is `tools/claim_scan.py`, which is
explicitly and correctly scoped to *instrument prose only* and states in its own
docstring that reaching into law records or state records is a different
class it does not cover.

**EXTENDED 2026-08-13 — the hole is wider than blockers, and this is one hole,
not two.** Two more instances landed within days, both the same shape:

- **A milestone id and its title described different milestones for months.**
  `palettes.palt_m6_artwork_shades` carried the title "PALT-M6 — powder &
  eyeshadow material engine". The slug came from the founding plan
  (`palt_m1/palette_roadmap.md:44`, which assigned artwork to M6); the work
  moved to M7 and the title was updated, the id was not. Corrected 2026-08-13
  by renaming the id, with the drift recorded in the tracker's own `meta`.
- **Two prose constants outlived the repair they described.** `SUBJECT_WINDOW`
  aside, `palette_marbling_rig.py`'s module docstring and its
  `DERIVED_COEFFICIENTS` both stated the pre-repair scalar `×0.55 / ×1.35+0.05`
  after the C6 **chromatic** repair had replaced it with a per-channel form
  that `_derived_components` now *raises* on — that is the palette campaign's
  C6, named as `palette_marbling_rig.py` names it, **not this register's C6**,
  which was added above on 2026-08-24 and collides with it. Both were accurate
  when written. This
  is the **second stale-statement sweep in this arc**; the first (829c598)
  found the same shape in the colour-transform prose.

*Why these are one defect and not three.* In every case a recorded claim —
a blocker's premise, an id's meaning, a docstring's coefficients — described
an artifact that had since changed, and **nothing in the programme compares a
claim to the thing it describes.** That is the register's own organising
observation, arriving in a third place. `tools/claim_scan.py` checks that
instrument prose makes no *absolute* claims; it does not check that instrument
prose is *true*.

*Status: OPEN.* Recorded because B4's answer was that no such control exists;
not scheduled and not built here, and deliberately **not** split into separate
entries — two defects describing one hole is worse than one. **Closing it would
require** recorded claims — blockers, ids, coefficient constants — to carry a
machine-evaluable predicate and a control that re-evaluates them, which is a
change to how claims are written and not only a new script.

**D10 — a measurement can be reported against a measure the instrument does not
declare, and nothing checks it. OPEN.**

*Why this is NOT D9.* D9 is about a recorded claim going stale — a blocker's
premise, an id's meaning, a coefficient constant — where the stale text sits in
a file and a sweep can find it. **This one has no file to sweep.** The defect is
in an analyst's *choice of measure*, which was never written down anywhere
before the result was published. A file sweep could not have caught it, so
folding it into D9 would put a hole under a heading whose remedy does not reach
it.

*The evidence, and it is my own work twice.* `palette_characterization_rig.py`
declares six axes in `axes_from()`, and its `§6` note records that peak-over-
median was **retired** from five of the six for not discriminating: "those are
transformations of one quantity, not five independent axes… what separates a
matte from a satin is how WIDE it is." At `7d985bb` and again at `61ddd75` I
judged seven families using **PLANAR p99/median** — that retired scalar, on the
one flat region — and concluded BAKED and PRESSED_POWDER were indistinguishable
from their control. On the declared axes both read clearly: BAKED clears at
`GRAZING_RESPONSE` 0.271 at Moss Garden's depth and on three axes at Attar's
own value; PRESSED_POWDER clears at `EDGE_HIGHLIGHT_RESPONSE` 0.357 and
`SHEEN_REGION_RESPONSE` 0.264. The measure could not see what it was judging.

*How far it spread — the sweep says: no further.* Extent: all **1,858** `.json`
under `docs/roadmap/**` carrying a verdict token, searched for peak-over-median
and for a PLANAR-only reading. Four hits, **none of them a verdict resting on
either**: `axis_instrument_defect_findings.json` is the record that *diagnosed*
the peak/median problem and is marked `FINDINGS_ONLY_NO_REPAIR_APPLIED`;
`glitter_particle_rig_report.json` counts discrete particles on PLANAR, which is
the correct region for a particle census; `flake_rig/parameter_plumbing_audit`
and `instrument_repair_phase0` carry no verdict. **No committed verdict rests on
a retired or region-blind measure.** The two instances are both mine, both in
this arc, and both were labelled "look-at-it aid, not certification" rather than
committed as verdicts — which limited the damage but did not prevent the wrong
conclusion being reported to the owner twice.

*Status: OPEN, not scheduled.* **Closing it would require** a reported
measurement to name the axis set it used and a control that refuses an axis the
instrument has retired — which means measures need declared identities, not
only instruments.

**D11 — a record's identifier and its body can describe different things, and
nothing compares them. OPEN.**

*Three instances, all found by hand, none found by a control.*

| record | the identifier said | the body said |
|---|---|---|
| `palettes.palt_m6_artwork_shades` | artwork + shades (the founding plan) | "powder & eyeshadow material engine" (the work) |
| `MATERIALS_LIBRARY_ABSENT` | a library is absent | the library is present; a **typeface** was the residue |
| `VQ1_HUMAN_STRUCTURAL_REVIEW` | the VQ-1 container structural review | the **M4C-4 intent panel**, a different surface |

*Why this is its own entry and not D9's or D10's.* **D9** is a claim going stale
against the world — detecting it requires an external referent, and its remedy
is a predicate that re-evaluates against that referent. **D10** is an analyst's
choice of measure that was never written down — no artifact exists to check.
**This needs neither.** Both halves are *inside the record*; the contradiction
is self-contained, and detecting it requires only reading the record against
itself. That makes it the cheapest of the three to check and the one with a
genuinely different remedy, which is why folding it into either would bury it
under a fix that does not reach it.

*What it costs when it survives.* `VQ1_HUMAN_STRUCTURAL_REVIEW` stayed open
after **both** of the things it named were satisfied — VQ-1 accepted 2026-07-28,
the M4C-4 panel confirmed 2026-08-12 — because whoever checked one half found
the other half still worded as unmet. A blocker that cannot be discharged by
satisfying it is worse than a blocker that is merely wrong.

*Is there any control that reads a record's id and its body and asks whether
they describe the same thing?* **No.** `record_integrity` compares bytes to
digests, `tier2_gate` compares collected files to a manifest, `claim_scan` reads
instrument prose for absolute claims and is scoped to instruments by its own
docstring, and `roadmap_status` validates the tracker's internal consistency —
duplicate ids, illegal statuses, weight sums, percentage bounds, milestone
pointers, rollup staleness — none of which is a semantic comparison of an id
against its title.

*Status: OPEN, not scheduled.* **Closing it would require** ids to be either
opaque (and never read as descriptions) or checkable against their bodies, which
is a decision about what an identifier is for and not only a script.

**D12 — a rule fitted on one population can be applied to a subject outside it,
and nothing declares the extrapolation. OPEN.**

*The instance.* `axis_independence_matrix_n6.json` records six
`census_families` — CREAM, POWDER_MATTE, POWDER_METALLIC, POWDER_SATIN,
PRESSED_POWDER, SHIMMER — and every correlation in it is a Spearman **across
those six**. At `b92521f` I applied its R5 ceiling to **MARBLED, GLITTER and
BAKED**, all three absent from that population, and published three FAIL
verdicts. Corrected to NEITHER in `d5i_adjudication_correction.json`. The
numbers were right; the verdict was not the instrument's to give.

*Why it is not D9, D10 or D11.* **D9** is a claim going stale — the matrix is
neither stale nor wrong, it is bounded. **D11** is a record whose halves
disagree — this record's halves agree perfectly; `census_families` and
`abs_spearman` are exactly consistent. **D10** is the near miss and the one
worth arguing: it is an undeclared choice of measure, and its remedy is "name
the axis set you used, and refuse a retired axis." **That remedy does not reach
this** — I *did* name the axis set, and not one of the six was retired. What
went undeclared was not which measure I used but that the **rule** I applied to
it was fitted on a population my subjects were not in.

*The sweep says this is the only instance, and that is the whole result.*
Extent: all **1,860** `.json` under `docs/roadmap/**`; 150 cite the eligibility
/ R5 / noise-floor / 0.25 apparatus; 51 cite R5, the n6 matrix or its 0.80
ceiling specifically. Of those, every record adjudicating MARBLED, GLITTER or
BAKED does so on **that family's own rig and floors** — `establishment_table`
uses "chroma span" for MARBLED, "event count" for GLITTER and "worst-case mm"
for BAKED, none of them a lobe axis. And where the census actually grew,
`a2_firing_result.json` **recomputed** at N=8 ("N=8 recompute of GRANULARITY ×
SHEEN and GRANULARITY × FWHM") rather than carrying the n6 numbers over. The
programme's own precedent is to recompute; `b92521f` is the one place that
extrapolated instead.

*The bound is now recorded where it cannot be missed* — a
`POPULATION_BOUND_2026_08_13` block at the **top** of the matrix, above the
correlations, stating that applying R5 outside `census_families` is an
extrapolation that must be declared at the point of use.

*Status: OPEN, not scheduled.* **Closing it would require** fitted rules to
carry their population as a first-class field and use-sites to assert
membership before applying them — which is a change to how rules are written,
not only a check.

**D13 — an absence claim's population can exclude the place the thing lives,
and A564 does not check the population. OPEN.**

*The two instances — the sweep says two, not four.* Extent of the sweep: every
A564 extent statement recorded in this arc's acts (M4C-4 confirmation check,
back-label copy, stock, 24/12 allocation, the font census absences, the
M7-scope search, the R5 application sweep, the D7 spec search, the
typeface-mention search, the die probe), each audited for whether its stated
population plausibly contained the target.

1. **61ddd75** — searched `docs/` and `apps/` for an M4C-4 confirmation;
   `OWNER_BLOCKER_SESSION.md` at the repository **root** recorded it and would
   have matched. The answer changed when the root was read.
2. **37f9d54** — searched three `palt_*` directories for ingredients copy;
   `ES3083_DIMENSION_FINDINGS.md` at the repository **root** — a file the same
   record cites for geometry — carries an ingredients lead at line 77 that the
   predicate `INCI|ingredient` matches. The answer changed when the root was
   read.

A near-instance, examined and not counted: the 7d985bb M7-scope search also
excluded the root, but the root file matches neither the predicate
(`PALT-M7`, not bare `M7`) nor answers the scope question, so inclusion would
not have changed the answer. The other seven claims' populations were sound.
**Two.**

*Why this is its own entry.* A564 mandates *stating* the extent, and both
instances stated it correctly — the failure is upstream, in *choosing* it. It
is not D10 (an undeclared choice of measure — these choices were declared),
not D12 (a rule applied outside its fitted population — no rule is involved),
and not D9 or D11. The common mechanical signature is exact: **repository-root
markdown excluded by directory-scoped greps**, twice, both times excluding the
very file that held the answer.

*The cheapest control that would have caught both.* Default the population of
any absence claim over project records to include the repository root's
markdown files — there are about fifteen, so the cost is near zero — and
require a stated reason when they are excluded. That single default catches
both instances. Stated honestly: a fully mechanical checker cannot parse
arbitrary extent prose, so this is a *discipline with a cheap default*, not a
gate; what CAN be made mechanical later is small (flag any recorded extent
whose population enumerates only `docs/` or `apps/` subtrees), and nothing is
built here.

*Status: OPEN, not scheduled.* **Closing it would require** the default above
being adopted into how A564 extents are written, and the small flag if anyone
wants it mechanical.

**D6 — 41 diagnostic renders were not produced** and the fail-closed manifest
is holding the gate shut. `PALT_VISUAL_EVIDENCE: 41_IMAGES_NOT_PRODUCED_GATE_ENFORCED`.
The gate is behaving correctly; the images are still missing.

---

## Sequencing

The active milestone does not change. M6 stays primary, and inside M6 the
instrument repair comes before any further family measurement — measuring
families with an instrument known to be broken is how M6 produced two verdicts
it later had to withdraw.

Within that constraint the order is:

The instrument repair (A1–A7) is realized against its declaration
`1e198aed8d86ed9c`, with every negative control recorded as having failed
correctly. Then the sensitivity study and the three diffuse pairs are re-run on
frozen families, and `MATTE_vs_SATIN` is re-adjudicated in place. Then the
GLITTER census is re-measured from the EXR. Only then does the M6 chain resume
at the flake-reflection rig.

B1 and B2 are small, are independent of M6, and remove the project's ability to
quote a wrong number about itself — they can be done in parallel by anyone,
and the tracker invariant that prevents recurrence is the part that matters.
B3 is documentation and should wait until M6 closes, so it is written once and
correctly rather than twice.

C1 and C2 are guards, not features. They belong with the structural work in A,
because they are the same defect class and the assertion that catches one is the
same shape as the assertion that catches the others.

D is not sequenced. D1 and D4 need the owner. D2 and D3 need files that do not
exist here. Nothing in A, B or C is blocked on them, and no plan should pretend
otherwise.

---

*No bar, window, pass law or family definition was moved in producing this
register. Protocol identity `087c7f64317910fb` is unchanged. Nothing here
constitutes owner acceptance, and `manufacturing_authority` remains
`NOT_ESTABLISHED`.*
