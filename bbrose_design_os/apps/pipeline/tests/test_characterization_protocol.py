"""M5 — the characterization protocol, its pass laws and its records."""
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.pipeline.services import palette_characterization_protocol as PR
from apps.pipeline.services import palette_m5_closeout as CO
from apps.pipeline.services import palette_material_swatch as SW
from apps.pipeline.services import palette_moulded_validators as mv

REPO = Path(__file__).resolve().parents[3]
M5DIR = REPO / "docs" / "roadmap" / "palt_m5"


class PassLawTests(SimpleTestCase):
    AXES = {
        "A": {"kind": "relative", "bar": 0.25, "independent": True},
        "B": {"kind": "absolute", "bar": 0.25, "independent": True},
        "C": {"kind": "relative", "bar": 0.25, "independent": False},
    }

    def test_two_independent_axes_pass(self):
        rep = PR.apply_pass_law({"A": 1.0, "B": 0.0, "C": 1.0},
                                {"A": 2.0, "B": 0.5, "C": 1.0},
                                self.AXES, 2, "x", "y")
        self.assertEqual(rep["verdict"], "PASS")
        self.assertEqual(sorted(rep["independent_axes_clearing"]),
                         ["A", "B"])

    def test_a_supporting_axis_never_counts_as_independent(self):
        """GRAZING shares its formula with the contrast axis; a clearing
        supporting axis must not become the second independent one."""
        rep = PR.apply_pass_law({"A": 1.0, "B": 0.0, "C": 1.0},
                                {"A": 2.0, "B": 0.1, "C": 9.0},
                                self.AXES, 2, "x", "y")
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertEqual(rep["independent_axes_clearing"], ["A"])
        self.assertEqual(rep["supporting_axes_clearing"], ["C"])

    def test_identical_axes_fail(self):
        same = {"A": 1.0, "B": 0.5, "C": 1.0}
        rep = PR.apply_pass_law(same, dict(same), self.AXES, 2, "x", "y")
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertEqual(rep["independent_axes_clearing"], [])

    def test_absolute_and_relative_kinds_differ(self):
        """A correlation near zero must not explode a relative bar."""
        rep = PR.apply_pass_law({"A": 1.0, "B": 0.01, "C": 0.0},
                                {"A": 1.0, "B": 0.02, "C": 0.0},
                                self.AXES, 1, "x", "y")
        self.assertFalse(rep["axes"]["B"]["clears"])

    def test_the_declared_reflective_law_matches_the_directive(self):
        self.assertEqual(PR.REFLECTIVE_REQUIRED_AXES, 2)
        supporting = [a for a, s in PR.REFLECTIVE_AXES.items()
                      if not s["independent"]]
        self.assertEqual(supporting, ["GRAZING_REFLECTION_RESPONSE"])
        dependent = [a for a, s in PR.TRANSMISSION_AXES.items()
                     if not s["independent"]]
        self.assertEqual(dependent, ["SCATTERING_OR_BLUR"])


class GridMetricTests(SimpleTestCase):
    def _bars(self, scale=1.0):
        return [[(0.8 if (c // 4) % 2 == 0 else 0.1) * scale
                 for c in range(32)] for _r in range(32)]

    def test_pattern_contrast_is_exposure_invariant(self):
        """§7 — a brighter render must not read as a different material."""
        a = PR.grid_pattern_contrast(self._bars())
        b = PR.grid_pattern_contrast(self._bars(scale=1.7))
        self.assertAlmostEqual(a, b, places=6)
        self.assertGreater(a, 0.5)

    def test_correlation_of_a_pattern_with_itself_is_one(self):
        self.assertAlmostEqual(
            PR.grid_correlation(self._bars(), self._bars(scale=2.0)), 1.0,
            places=6)

    def test_a_flat_grid_has_no_contrast(self):
        flat = [[0.4] * 32 for _ in range(32)]
        self.assertAlmostEqual(PR.grid_pattern_contrast(flat), 0.0,
                               places=6)

    def test_coherence_separates_bands_from_speckle(self):
        bands = self._bars()
        import random
        rnd = random.Random(7)
        speckle = [[rnd.random() for _ in range(32)] for _ in range(32)]
        self.assertGreater(PR.grid_coherence(bands),
                           PR.grid_coherence(speckle))


class FixtureTests(SimpleTestCase):
    def test_the_transmission_plates_are_watertight(self):
        """An open sheet bends a transmitted ray permanently; the plate
        fixture must be a genuine solid."""
        for name, mesh in SW.build_transmission_plates().items():
            d = mv.validate_mesh(name, mesh,
                                 check_self_intersection=False)
            with self.subTest(plate=name):
                self.assertTrue(d["valid"], d["findings"])
                self.assertEqual(d["diagnostics"]["euler_characteristic"],
                                 2)

    def test_one_plate_fixture_for_every_transmission_material(self):
        self.assertIn("CLOSED_PLATES", PR.TRANSMISSION_RIG["fixture"])

    def test_the_swatch_identity_is_preserved(self):
        self.assertEqual(SW.build_swatch()["swatch_geometry_identity"],
                         "720d17daee36e487")

    def test_protocol_identity_is_deterministic(self):
        self.assertEqual(PR.protocol_identity(), PR.protocol_identity())


class ProtocolRecordTests(SimpleTestCase):
    """The committed reports must say what the checkpoint claims."""

    def _load(self, name):
        path = M5DIR / name
        self.assertTrue(path.exists(), f"{name} is missing")
        return json.loads(path.read_text())

    def test_the_reflective_report_passes_with_behaving_controls(self):
        r = self._load("reflective_metric_report.json")
        self.assertEqual(r["REFLECTIVE_MATERIAL_RIG"], "PASS")
        self.assertEqual(r["controls_misbehaved"], [])
        self.assertEqual(r["robustness_unstable"], [])
        self.assertEqual(r["glossy_vs_metallic"]["verdict"], "PASS")
        self.assertGreaterEqual(
            len(r["glossy_vs_metallic"]["independent_axes_clearing"]), 2)

    def test_the_transmission_report_passes_all_pairs(self):
        r = self._load("transmission_metric_report.json")
        self.assertEqual(r["TRANSMISSION_RIG"], "PASS")
        self.assertEqual(r["failed_pairs"], [])
        self.assertTrue(r["exposure_control"]["behaved"])

    def test_the_manifest_records_the_commissioning_defects(self):
        m = self._load("characterization_protocol_manifest.json")
        self.assertEqual(m["M5_CHARACTERIZATION_PROTOCOL"], "PASS")
        self.assertGreaterEqual(
            len(m["commissioning_defects_caught_by_the_rigs_own_gates"]),
            4)


class WorkflowTraceTests(TestCase):
    """§10 — the production chain, driven and re-verified in a test DB."""

    def test_the_trace_runs_and_verifies_end_to_end(self):
        from apps.pipeline.services import palette_m5_workflow as WF
        WF.run_trace()
        v = WF.verify_trace()
        self.assertEqual(v["M5_REAL_WORKFLOW_CONNECTION"], "PASS", v)
        self.assertEqual(len(v["variants"]), 6)
        for row in v["variants"]:
            self.assertEqual(row["verdict"], "PASS", row)
        self.assertIsNotNone(v["gate_decision_id"])

    def test_a_missing_artifact_fails_the_trace(self):
        from apps.pipeline.models import PaletteMaterialArtifact
        from apps.pipeline.services import palette_m5_workflow as WF
        WF.run_trace()
        PaletteMaterialArtifact.objects.filter(
            variant_name="METALLIC_ACCENT").delete()
        v = WF.verify_trace()
        self.assertEqual(v["M5_REAL_WORKFLOW_CONNECTION"], "FAIL")
        self.assertTrue(any("METALLIC_ACCENT" in s
                            for s in v["stages_failed"]))

    def test_a_tampered_evidence_hash_fails_the_trace(self):
        from apps.pipeline.models import PaletteMaterialArtifact
        from apps.pipeline.services import palette_m5_workflow as WF
        WF.run_trace()
        a = PaletteMaterialArtifact.objects.get(
            variant_name="NEUTRAL_ABS_MATTE")
        a.evidence_sha256 = "0" * 64
        a.save()
        v = WF.verify_trace()
        self.assertEqual(v["M5_REAL_WORKFLOW_CONNECTION"], "FAIL")


class PowderProtocolDeclarationTests(SimpleTestCase):
    """M6 §14 — the declaration must be complete, honest and pinned
    BEFORE any realization exists."""

    def test_the_declaration_is_pinned_and_honest(self):
        from apps.pipeline.services import palette_powder_protocol as PP
        status = PP.protocol_status()
        # owner-amended twice 2026-08-08 (M6_INDEPENDENCE_AMENDMENT_PROMPT.md,
        # then M6_DRIVER_COMPLETENESS_PROMPT.md (1e/1f/1g), then
        # M6_MEASUREMENT_ADEQUACY_PROMPT.md (1i), then
        # M6_ESTABLISHMENT_CLOSURE_PROMPT.md (1j), then
        # M6_SEQUENCING_AND_SUBSTITUTION_RULING.md (1k/1l/1m) —
        # conservation 1f, degenerate-statistic guard 1g) — bars
        # diff-proven unchanged both times.
        # 2026-08-14: identity moved by the A391 manifest rebind for the
        # products-node records (M6-PRODUCTS-OBSERVABILITY-TRACE-BOARDS)
        # — records, regenerate, rebind, compute, PIN. Bars untouched.
        # Re-pinned again same day for the exit-gate close (F1/F2 +
        # products re-run records bound; A391 chain each time).
        # REALIZED flipped True the same day: the status's own
        # not_yet_implemented list emptied; realization is not
        # completion (exit gate unrun, owner approval not granted).
        # Re-pinned 2026-08-17 for the §R4/§S1 fallback-class registration,
        # which writes two records under the declared root (gate_baseline
        # gains its registrations block; fallback_class_defects is new).
        # A375/A391 again: records, regenerate, rebind, compute, PIN. No
        # law text edited, no bar moved — the historical identity
        # 52bffe4a622e3dc0 stays untouched in the close records that
        # recorded it as the state of THAT run.
        # Re-pinned 2026-08-20 at WI-3G/§AJ, and this one was not a node
        # writing records — it was a REPAIR. suite_records/INDEX.json had
        # been RECORD_UNDECLARED since d4f93e0 and the halt on the
        # unclassified `.gz` was raised BEFORE check() ever ran, so the
        # undeclared row was invisible for as long as the halt stood: one
        # fail-closed guard masking a second finding behind it. A375/A391
        # once more — records, regenerate, rebind, compute, PIN. No law
        # text edited, no bar moved; 1a087f9911cead97 stays true of the
        # runs that recorded it.
        # Re-pinned 2026-08-20 at WI-3I/§AQ, for the close of the §R4/§S1
        # fallback-class register: gate_baseline.json gained the last two
        # justification-bearing registrations and fallback_class_defects
        # .json settled its final six entries, so both records moved and
        # the manifest moved with them — +0 -0 ~3, the two registers and
        # the ledger, nothing added and nothing removed.
        # RECORDED HONESTLY, because this is the second half of a chain I
        # left half-done. I ran records, regenerate, rebind — and stopped,
        # because the gate went green and record_integrity reported OK and
        # it LOOKED finished. The missing compute+PIN is exactly what made
        # this test fail in the full suite. The A391 order has five steps
        # precisely because stopping after three is invisible from every
        # signal available at step three.
        # Diff-proven scope: the only edit to palette_powder_protocol.py
        # is one line of EXTENT_DIGESTS. No law text edited, no bar moved;
        # 5fe9b7098cb01228 stays true of the runs that recorded it.
        # Re-pinned 2026-08-20 at WI-3J/§AR, for the extent repair. BOTH
        # EXTENT_DIGESTS entries moved this time: suite_file_manifest,
        # because the manifest declared 318 files against 362 collected
        # and had done since 2026-08-12; and record_digest_manifest,
        # because that regeneration is itself a record. `+0 -0 ~3` —
        # suite_file_manifest.json, suite_manifest_diffs.json and the
        # ledger. Nothing added, nothing removed.
        # THE CHAIN RAN TO FIVE THIS TIME, and §AR4(4) is the reason it is
        # worth saying: I wrote that clause hours ago, in the same session,
        # precisely because the note above admits I stopped at three. A
        # lesson recorded and then not applied on the very next occasion is
        # a lesson nobody learned. Steps, in order: records moved
        # (suite_file_manifest.json, suite_manifest_diffs.json) ->
        # record_integrity.py --regenerate -> both digests rebound ->
        # protocol_status() computed -> this line.
        # Scope: no law text edited, no bar RAISED against past work. Two
        # floors were raised — tier1 28 -> 66, total 5,970 -> 7,360 — and
        # those are bars on FUTURE runs only; 2768210120a5be21 stays true
        # of the runs that recorded it.
        # Re-pinned 2026-08-21 at §AV5. ONE EXTENT_DIGESTS entry moved:
        # record_digest_manifest, 6aebd0932c703c2a -> 3606f3f55c49753c.
        # suite_file_manifest did NOT move, so this is the narrower case of
        # the §AR entry above, not a repeat of it.
        # THE CHAIN RAN TO TWO AND STOPPED, one tranche after the note above
        # said "a lesson recorded and then not applied on the very next
        # occasion is a lesson nobody learned". §AV3 did records ->
        # regenerate and committed there: no rebind, no compute, no pin.
        # That is worse than the three-step stop this comment was written to
        # correct, and it happened with the correction in the file. What the
        # earlier note got wrong is the diagnosis, not the count: it says
        # stopping early "is invisible from every signal available at step
        # three". It is not invisible — A387 raises UnsyncedManifest by
        # name, and two tests went red immediately. §AV3 had the signal, in
        # the failure list it collected, and read past it because it was
        # holding a green `RECORD_INTEGRITY=OK` from a tool that does not
        # measure this. The gap is not detection. It is that an OK from any
        # instrument was allowed to stand for an OK from the right one.
        # Scope, proven by diff rather than asserted: the only non-comment
        # edit to palette_powder_protocol.py in this amendment is the single
        # EXTENT_DIGESTS line quoted above — `git diff -U0` on that file
        # yields exactly one `-`/`+` pair. No law text edited, no floor
        # moved, no bar raised against past work; 49441eabb019734e stays
        # true of the runs that recorded it.
        # Re-pinned 2026-08-21 at §AV6. TWO EXTENT_DIGESTS entries moved:
        # suite_file_manifest f9d225bd0855d513 -> 054cc280b1d2d414, and
        # record_digest_manifest 3606f3f55c49753c -> b924d02e99f6eb2f. So
        # this is the WIDER case of the §AR entry above, not the narrower
        # §AV5 one.
        # WHY IT MOVED AT ALL, WHICH IS THE PART WORTH READING: I added one
        # test file — test_av5_artefact_withheld.py, the 11 tests that watch
        # the three artefact closures fire — and did not declare it. A327(a)
        # caught it in the FULL suite, not in the four files I had been
        # running, and it was one of exactly three failures this tranche
        # caused. I found that out by building a worktree at HEAD and running
        # the six failures there: three reproduced (pre-existing) and three
        # did not (mine). Attributing them by assumption instead would have
        # repeated 9c270fd's audited defect exactly — that commit blamed AV3
        # for failures already eight commits old.
        # THE CHAIN RAN TO FIVE. Records moved (suite_file_manifest.json,
        # suite_manifest_diffs.json, the ledger) -> record_integrity.py
        # --regenerate, `+0 -0 ~3` -> both digests rebound above ->
        # protocol_status() COMPUTED, not predicted -> this line. §AV3
        # stopped at two with the correction already in this file; the only
        # thing that makes writing it down worth anything is doing it the
        # next time, and this is the next time.
        # Scope: no law text edited. ONE floor rose — total_floor 7,408 ->
        # 7,422 — and a floor is a bar on FUTURE runs only; 930cecbd1472ac8a
        # stays true of the runs that recorded it. tier1_floors did not move.
        # The +14 is NOT all mine and I first wrote that it was. The added
        # file collects ELEVEN, measured. The floor is
        # `max(old, sum(collected))` and is RE-MEASURED every regeneration
        # per AR3(d), so the other 3 were already being collected and were
        # simply sitting above a stale floor. 7,422 is the whole suite's
        # collected total and reconciles exactly: 7,413 passed + 3 skipped
        # + 6 failed. Writing "14 tests of the added file" would have been a
        # number I inferred from a subtraction rather than counted, which is
        # the precise habit 9c270fd's audit refuted with `210 passed`.
        # Re-pinned 2026-08-21 at §AX. ONE EXTENT_DIGESTS entry moved:
        # suite_file_manifest 054cc280b1d2d414 -> 3b2de42e9be3ef05.
        # record_digest_manifest did NOT move — it was already synced, checked
        # by hashing the file on disk against the corpus BEFORE computing
        # anything, which is A387's assertion done by hand rather than waited
        # for. So this is the narrower §AV5 case, not the wider §AV6 one.
        # WHY IT MOVED, AND THE PART WORTH READING: three test files were
        # undeclared, and only two of them were mine. test_aw_emitter_closure.py
        # is §AW's — that tranche committed its RULING and left its eight tests
        # untracked, and nothing noticed for a day. I did not go looking for it;
        # A327(a) put it in the same failure message as my two. An extent gate
        # justifies itself on the file nobody was thinking about, and this is
        # that file.
        # THE CHAIN RAN TO FIVE, and the check at step one is the reason it can
        # be said rather than hoped: records verified in sync (b924d02e99f6eb2f
        # on disk == corpus) -> regenerate, `+3 -0` under §AR4(1) checked BEFORE
        # applying -> the single digest above rebound -> protocol_identity()
        # COMPUTED, not predicted -> this line. §AV3 stopped at two and §AV6
        # noted that doing it next time is the only thing that makes writing it
        # down worth anything; this is the next time after that one.
        # Scope: no law text edited. ONE floor rose — total_floor 7,422 ->
        # 7,475 — and a floor is a bar on FUTURE runs only; 7d58c897f1f89d74
        # stays true of the runs that recorded it. tier1_floors did not move.
        # The +53 RECONCILES rather than being inferred from the subtraction:
        # 51 collected from the three added files (19 + 24 + 8, counted with
        # --collect-only) plus 2 added to test_container_line_weight.py, which
        # was already declared and whose floor was therefore re-measured under
        # AR3(d). Nothing is left over, which is the check §AV6 had to write an
        # apology for skipping.
        #
        # RE-PINNED A SECOND TIME, SAME DAY, AND THE SENTENCES ABOUT
        # record_digest_manifest ARE WRONG. They are left standing because the
        # way they were wrong is the finding. "record_digest_manifest did NOT
        # move — it was already synced, checked by hashing the file on disk
        # against the corpus" was true when written. It then moved, to
        # a32b4daa5bb67bfd, because `record_integrity.py` was refusing on a
        # RECORD_DIGEST_MISMATCH and clearing that refusal rewrites the very
        # file the corpus pins. So "THE CHAIN RAN TO FIVE" was false too: it
        # ran STEPS TWO THROUGH FIVE, twice.
        # THE ERROR IS §AV5's, INVERTED. §AV5 read `RECORD_INTEGRITY=OK` and
        # concluded the pin was current — borrowing the record tool's verdict
        # for the pin question. I hashed the manifest against the corpus, found
        # it equal, and concluded the RECORDS step was done — borrowing the pin
        # check's verdict for the record question. "Is the pin current?" and
        # "does the record set validate?" are different questions and neither
        # instrument answers the other. Two tranches running, one register,
        # opposite directions, same mistake.
        # WHAT IT COST, honestly: nothing, one re-run. A387 raised UnsyncedManifest
        # naming the order in its own message, before any commit. §AV5's silent
        # version cost a tranche. That gap is the guard's whole value and it is
        # the first time this repo has been able to price it.
        # The chain, second pass: records cleared (`+0 -0 ~3`) -> corpus rebound
        # -> protocol_identity() COMPUTED -> this line.
        #
        # RE-PINNED AGAIN AT §AY1, and this time the recipe was followed to the
        # letter and STILL refused. One test file was added —
        # test_ay1_outbound_guard.py, the 14 tests that watch the outbound-call
        # guard refuse a real connection — and A327(a) caught it outside the
        # declared extent, as it has now caught every added test file in four
        # consecutive tranches.
        # A391 step 1 ran FIRST this time, exactly as the two paragraphs above
        # demanded, and returned `RECORD_INTEGRITY=OK records=1734 failing=0`.
        # Step 2 then regenerated the suite manifest — AND STEP 2 IS ITSELF A
        # RECORD WRITE. It moved three declared records, so step 1's OK was
        # invalidated by the next step of the recipe that ordered it. Running
        # record_integrity.py again before the rebind returned
        # RECORD_DIGEST_MISMATCH on suite_file_manifest.json, 3b2de42e… ->
        # 8faa48a1…. The finding is not "I ran it out of order" — it is that a
        # LINEAR five-step recipe cannot describe a chain whose second step
        # dirties its first, and no permutation of five distinct steps fixes
        # that. The records step has to run TWICE. EXTENT_DIGESTS["recipe"] now
        # says so; it did not before, and every prior entry on this pin read the
        # failure as an ordering mistake because the recipe only offered
        # ordering as an explanation.
        # Scope: no law text edited. ONE floor rose — total_floor 7,475 ->
        # 7,489 — and a floor bars FUTURE runs only. tier1_floors did not move.
        # The +14 RECONCILES exactly: 14 collected from the one added file,
        # counted with --collect-only, nothing left over.
        # The chain, this pass: records OK -> regenerate (`+1 -0`, additive,
        # checked under §AR4(1) BEFORE applying) -> records AGAIN (`+0 -0 ~3`)
        # -> BOTH corpus digests rebound in one amendment
        # (8faa48a16268ffdf, 6300c0500768f446) -> protocol_identity() COMPUTED,
        # not predicted -> this line.
        #
        # RE-PINNED A THIRD TIME IN THE SAME TRANCHE, 39d203679d1c8482 ->
        # c7c9d902e2a138a1, AND THIS TIME THE CAUSE WAS ME, NOT THE RECIPE.
        # After the §AS2(2) node move I ran `tier2_gate.py
        # --regenerate-manifest` defensively, on a manifest that was already
        # correct. It reported `added (0) / removed (0)` — and still changed
        # the file, because the manifest stamps `generated` with the wall
        # clock. 04:35:34.199453Z -> 08:16:36.851849Z was the whole diff, and
        # it was enough to move the digest 8faa48a1… -> 52e0f544…, refuse the
        # records gate, and cost a rebind, this recompute and this re-pin.
        # THE GENERATOR IS NOT IDEMPOTENT: for this record `--regenerate` is a
        # WRITE, not a query, so "run it again to be sure" is not free and is
        # not safe. EXTENT_DIGESTS["recipe"] now says to run it only when a
        # test file actually moved. The stale timestamp was NOT edited back to
        # manufacture idempotence — the append-only diff entry and the REFUSED
        # ledger line stand as written, because an append-only record that is
        # tidied after the fact is not a record.
        # The chain, third pass: (node move) -> [my needless regenerate] ->
        # records `+0 -0 ~3` -> BOTH digests rebound in one amendment
        # (52e0f544d91be347, 53a6806e4aa96814) -> protocol_identity()
        # COMPUTED, not predicted -> this line.
        #
        # RE-PINNED 2026-08-22, c7c9d902e2a138a1 -> 6fce38955702c00b, and this
        # time the regeneration was EARNED: a test file actually moved, which
        # is the precondition the entry above had to learn the hard way.
        # test_two_roots_collision_guard.py adds 10 tests pinning the
        # git-root/Django-root collision. A327(a) caught it outside the
        # declared extent, as it has for five consecutive tranches.
        # WHAT THE RECOUNT FOUND THAT NOBODY WAS LOOKING FOR: the TIER_1 floor
        # for test_palette_statistics.py read 49 in BOTH copies against a
        # collected 50. dab25db added the 50th test and raised neither copy.
        # ExtentFloorsAreMonotonic compares the two copies TO EACH OTHER, so a
        # pair stale by the same amount passes it — the §AR2 guard cannot see
        # the §AR2 defect when both halves drift together. Only a recount from
        # disk could find it, and only a legitimately-triggered regeneration
        # causes a recount. It sat wrong for two commits.
        # A387 also earned its keep rather than merely existing: all three
        # identity tests refused with UnsyncedManifest BEFORE hashing anything,
        # naming both digests and the A391 order in the message.
        # The chain, this pass: records -> regenerate (`+1 -0`, additive,
        # checked under §AR4(1) against a byte backup BEFORE applying) ->
        # records AGAIN (`+0 -0 ~3`) -> BOTH corpus digests rebound in one
        # amendment (307ce4c380fa0f02, 4afa98f85203874d) -> protocol_identity()
        # COMPUTED, not predicted -> this line.
        #
        # RE-PINNED 2026-08-27 at §BC(h)/C10, 6fce38955702c00b ->
        # 4ab5331b49fbd923, and the regeneration was EARNED for the second
        # tranche running: apps/ire/tests/test_c10_mark_width.py adds 15 tests
        # that measure the owner-ruled 0.55 mark share as an emitted millimetre
        # width. A327(a) caught it outside the declared extent — six
        # consecutive tranches now, every added test file, none missed.
        # WHAT DID NOT HAPPEN THIS TIME IS THE ENTRY. Six of the eight notes
        # above are confessions: a chain stopped at two, at three, run out of
        # order, run defensively on a clean manifest. This pass ran records ->
        # regenerate (`+1 -0`, additive, checked against a byte backup BEFORE
        # applying) -> records AGAIN (`+0 -0 ~3`) -> BOTH digests rebound in
        # one amendment (65aef9fb1a3660cd, 413e1e2cb99d664c) ->
        # protocol_identity() COMPUTED, not predicted -> this line. Nothing
        # refused. The recipe absorbed the §AY1 two-pass rule and the §AZ0(l)
        # earned-trigger rule and the chain became uneventful, which is the
        # only evidence that either rule was worth writing down.
        # THE RECOUNT CLOSED A WRITTEN PREDICTION rather than exposing a new
        # defect, and that is the difference from the entry above. tier1
        # test_palette_statistics.py 50 -> 51 in the manifest: `4cda10f`
        # raised the guarded_commit.sh copy when it added the test and left a
        # comment saying the manifest copy "will [say 50] until the next
        # regeneration". This is the next regeneration. Both copies read 51.
        # Scope: no law text edited, no bar RAISED against past work. One
        # floor rose — total_floor 7,567 -> 7,643 — and a floor bars FUTURE
        # runs only; 6fce38955702c00b stays true of the runs that recorded it.
        # The +76 is NOT this tranche's 15 and is not reported as though it
        # were: the floor is `max(old, sum(collected))` re-measured under
        # AR3(d), so it caught up with everything collected since 2026-08-22.
        #
        # RE-PINNED 2026-08-28 at §BH2, 4ab5331b49fbd923 -> 4fe211b5837c1645,
        # AND THE CHAIN STOPPED AT TWO — §AV3's error exactly, with §AV5's
        # correction sitting in this file where I had already read it.
        # WHAT MOVED THE DIGEST IS NEW, and it is why this entry is worth more
        # than the confession. No test file was added; no node wrote records.
        # The owner ruled a one-line STATUS correction to
        # declared_spreads/spreads_campaign_declaration.json — execution_status,
        # thirteen days stale. That single field propagates four levels:
        # declaration bytes -> its digest in record_digest_manifest.json ->
        # EXTENT_DIGESTS["record_digest_manifest"] -> this identity. At every
        # level the hash covers the WHOLE artifact below it, so an honest
        # status correction and a silent re-scoping of the campaign are
        # indistinguishable to all four. That is the §BH2 finding at full size,
        # and this pin is where it becomes visible.
        # HOW IT WAS MISSED, precisely: records -> regenerate, then I stopped,
        # holding RECORD_INTEGRITY=OK records=1734 failing=0. That is worse
        # than §AV5's borrowed OK, because I had DEMONSTRATED it — check() run
        # in-process before and after the regeneration, exactly 2 refusals then
        # 0 — and then nominated that leg as the commit's sharp one in the
        # message. A green you earn by firing the instrument yourself is still
        # that instrument's green, and record_integrity.py does not measure
        # this pin. §AV5's sentence — "an OK from any instrument was allowed to
        # stand for an OK from the right one" — takes a second confirmation and
        # needs no amendment.
        # WHAT IT COST: one refused gate run and no commit. A387 raised
        # UnsyncedManifest in all three identity tests, naming both digests and
        # the order, before anything landed.
        # ATTRIBUTION PROVEN, NOT ASSUMED, per §AV6: a detached worktree at
        # ae3e4d9 ran the three failures and all passed there, so they are
        # mine. The manifest hashes 413e1e2cb99d664c at HEAD and
        # dfa03eea8235bb33 in the tree — the same fact from the other side.
        # NARROW CASE, the §AV5/§AX shape and not §AV6's: suite_file_manifest
        # hashed 65aef9fb1a3660cd on disk, equal to the corpus, so the suite
        # manifest generator was NOT RUN — §AZ0(l)'s earned-trigger rule, which
        # exists because running it defensively once cost an entire chain.
        # The chain, this pass: records verified in sync (check() in-process,
        # `[]`, no ledger write) -> regenerate NOT REPEATED, because for this
        # record --regenerate is a WRITE that appends a diff entry -> the one
        # digest above rebound -> protocol_identity() COMPUTED, not predicted
        # -> this line.
        # Scope: no law text edited, no bar moved, PROVEN rather than asserted.
        # The identity payload MINUS extent_digests hashes 675cdbda… at 83,893
        # bytes both at HEAD and after this edit — over exactly the fields
        # protocol_identity() reads — and `git diff -U0` on
        # palette_powder_protocol.py is a single `-`/`+` pair. 4ab5331b49fbd923
        # stays true of the runs that recorded it: commit L's scored prediction
        # in the register at :12651 and the tracker's measurement at
        # progress_tracker.json:214 are both left untouched.
        #
        # RE-PINNED 2026-08-29 at §BH4(b), commit P, 4fe211b5837c1645 ->
        # b9272465dbe49f31. Mover: docs/roadmap/palt_m6/spreads_ceiling_breach
        # .json, the owner-ordered ceiling-breach finding, plus the ledger line
        # from commit O's gate. `+0 -0 ~2`; manifest b269f918c546fc55 ->
        # 7bf32c2efcec96ec. Full chain, in order, no step assumed.
        # WHAT IS NEW HERE IS THAT THE CHAIN CAUGHT A FALSE STATEMENT OF FACT,
        # not a missed step. The COMPUTE leg reads protocol_identity()'s
        # payload. `defect_class_register` is one of its nine keys. Reading it
        # is what revealed DEFECT_CLASS_REGISTER — 23 entries, APPEND ONLY,
        # palette_powder_protocol.py:1445 — AFTER the breach record already on
        # disk asserted in the owner's own record that "THERE IS NO MASTER
        # REGISTER OF THE NUMBERED CLASSES". It had been searched for four
        # times. Every grep was correctly run and every one looked for class
        # NUMBERS; the register is keyed by NAME.
        # THE CLASS IS TWO_ROOTS_MEASUREMENT AND THE COSTUME IS THIRD. A wrong
        # PATH errors. A narrow ROOT was §AY1's. A wrong KEY returns exit 0 and
        # silence, which reads as proof of absence and is not. "I found
        # nothing" is not a finding until the shape of the search is stated
        # beside it. Two class attributions were wrong from memory in the same
        # draft and were fixed the same way — by reading the definitions.
        # Scope: no law text edited, no bar moved, no class minted. The record
        # cites classes BY NAME only and refers UNIT_MISMATCH to the owner
        # rather than appending to an APPEND-ONLY register inside a record
        # commit. 4fe211b5837c1645 stays true of the runs that recorded it.
        # AND THEN THE CHAIN RAN A FOURTH TIME, 5dd20cae6d87df7a ->
        # b9272465dbe49f31, WITH THE GATE ALREADY RUNNING GREEN ON THE THIRD.
        # Reading ahead to the next commit turned up a second false claim in
        # the same record: it listed TWO_ROOTS_MEASUREMENT among the classes it
        # had "checked against the real register", and that class has no entry
        # in DEFECT_CLASS_REGISTER — it lives in prose in four files, one of
        # them the register's own host file. So the corrected record's claim
        # was itself defective, in the same direction, one draft later.
        # THE LESSON IS NOT "CHECK TWICE". It is that both errors were claims
        # about a data structure, made from recollection, in a file that can
        # import it. The record now MEASURES them: the writer asserts all seven
        # cited names are in the register and that TWO_ROOTS_MEASUREMENT is
        # not, so the prose cannot drift from the register again without the
        # write failing.
        # RE-PINNED 2026-08-29 at §BH4(c), commit Q, b9272465dbe49f31 ->
        # 78c09eeb76cac775. Mover: spreads_campaign_declaration.json, ten
        # inserted lines closing campaign spend. ONE chain pass this time, not
        # four. b9272465dbe49f31 stays true of the runs that recorded it.
        # THE SAME DEFECT PRESENTED A THIRD TIME AND WAS CAUGHT BEFORE THE
        # WRITE INSTEAD OF AFTER IT. Commit Q's writer had been drafted with
        # the sentence "c1434e1efdb98a62 at 21 sites across 9 files". From the
        # git root it is 23 across 10. The file the narrow reading drops is
        # OWNER_BLOCKER_CLEARANCE.md — the document carrying the ruling being
        # executed — because it is tracked at the git root only and this repo
        # has two. Both greps exit 0 and neither says which root it answered
        # for. The measurement fix commit P built for register claims did not
        # cover this, because it was scoped to the register rather than to the
        # habit; the writer now runs the pin census itself from a PINNED root
        # and refuses to emit the record if either count moves.
        # RE-PINNED 2026-08-29 at §BH5(a), commit S, 78c09eeb76cac775 ->
        # dfc98caf984055e3. Mover: DEFECT_CLASS_REGISTER, 23 -> 25 entries,
        # minting UNIT_MISMATCH and TWO_ROOTS_MEASUREMENT on the owner's
        # ruling. The register is bound into protocol_identity()'s payload,
        # so a mint moves this value by construction and cannot be undone by
        # deletion — only by a further appended correction.
        # NO SUITE-MANIFEST REGENERATION AND NO REBIND: EXTENT_DIGESTS's own
        # recipe says regenerate ONLY when a test file was added or removed,
        # because it is a WRITE that stamps `generated` with the wall clock
        # and mints a new digest even on added(0)/removed(0). This commit adds
        # no test file. Measured, not assumed: 0 of the 1735 records in
        # record_digest_manifest.json is a .py file, so editing the protocol
        # source moves no record digest, RECORD_INTEGRITY is untouched, and
        # the "run the records step TWICE" clause does not apply — its cause
        # is manifest regeneration, which is not performed here.
        # 63 records EMBED a protocol_identity and none carried the previous
        # value either; they are historical stamps of the bytes their runs ran
        # against, not a live index, so a mint does not drag them.
        # RE-PINNED 2026-08-29 at §BH7, commit U, dfc98caf984055e3 ->
        # ead892658e3323a8. Mover: NOT the defect-class register this time.
        # P1's first act (§BH3, ruled to reading A by §BH7(a)) writes three
        # new bound records under docs/roadmap/palt_m6, so the A391 RECORDS
        # step was owed and run: `+3 -0 ~1`. That moved
        # record_digest_manifest.json, which is bound into EXTENT_DIGESTS,
        # which is bound into this identity — rebound in the SAME amendment
        # per the recipe, 1e4e82003c328302 -> ff18cb2d74866a94, never
        # separately.
        # THE RECORDS STEP RAN ONCE, NOT TWICE, AND THAT IS MEASURED: the
        # "run it TWICE" clause exists because regenerating the SUITE
        # manifest is itself a write to three declared records (§AY1). This
        # commit adds and removes no test file, so the suite manifest is not
        # regenerated, the clause's cause is absent, and the second pass is
        # not owed. Independently: record_digest_manifest.json does not track
        # ITSELF, so regenerating it cannot invalidate itself.
        # The declaration identity did NOT move and was never going to.
        # sha256(spreads_campaign_declaration.json) is 87893c1264fd232f
        # before and after every step above. protocol_identity and
        # declaration_identity are different registers over different bytes;
        # both are 16-hex sha256 prefixes and NEITHER CARRIES ITS NAMESPACE
        # IN ITS OWN TEXT, which is exactly how a correct declaration
        # identity came to be reported as a mislabelled protocol identity
        # (§BH7(b), the fifth self-caught defect).
        # Day6: six new test files and individually justified helper keys;
        # suite/record bindings recomputed, no historical law or safety bar changed.
        # Day8: four new test files (day8_jury, day8_concepts, day8_library, ire day8_fonts) and the gate's
        # individually judged registrations; A391 in order (records, regenerate, records again, rebind both digests,
        # compute, pin) — no historical law or safety bar changed.
        # Day9: seven new test files (day9_palette, day9_builds, the five ornament generators' day9_orn_a2, _b1, _b2,
        # _c1, _c2); A391 in order (records, regenerate, records again, rebind both digests, compute, pin) — no
        # historical law or safety bar changed.
        # Day10: one new test file (day10_master); A391 in order (records, regenerate, records again, rebind both
        # digests, compute, pin) — no historical law or safety bar changed.
        # Day11: six new test files (day11_carton, day11_golden_hour, day11_lipstick, day11_pages, day11_zilal,
        # day11_zilal_pack); A391 in order (records, regenerate, records again, rebind both digests, compute, pin) —
        # no historical law or safety bar changed.
        # Day12: seven new test files (counter_tray_header, day12_balm, day12_board, day12_display, day12_lipstick,
        # day12_pages, day12_reader); A391 in order (records, regenerate, records again, rebind both digests, compute,
        # pin) — no historical law or safety bar changed.
        # Day13: seven new test files (day13_carton_copy, day13_creativity, day13_creativity_page, day13_demo,
        # day13_display_faces, day13_lipstick_carton, day13_print_pack); A391 in order (records, regenerate, records
        # again, rebind both digests, compute, pin) — no historical law or safety bar changed.
        # Day14: four new files (faces, file_door, wrap, print_pack), collected by pytest; records,
        # regenerate, records again, both digests rebound, identity computed, then pinned.
        # Every old floor is retained or raised; no law or behavioral threshold changed.
        # Round 1: one new test file and twelve individually reviewed helper keys;
        # A391 records, additive suite manifest, records again, both digests, then identity.
        # All prior files and floors retained; no law or judgment threshold changed.
        # Round 1C: seven missing HAYAT test files plus close/leaflet tests;
        # forty-four individually judged helper keys. Records, additive
        # manifest, records again, both digests, computed identity, this pin.
        # Prior files and monotonic floors retained; no law or threshold changed.
        # Round 2: four new fixture test files, 32 individually reviewed helper keys.
        # Records, additive manifest (+4/-0; all floors monotonic), records again,
        # both digests rebound, identity computed, then pinned; no threshold changed.
        # Round 2 recovery: two individually reviewed new keys; every prior entry
        # unchanged. No test files added/removed, so suite manifest unchanged.
        # Records regenerated, record digest rebound, identity computed, then pinned.
        # Round 2 Break 3: four individually reviewed keys; old entries retained.
        # No test files added/removed. Records regenerated, digest rebound,
        # identity computed and pinned; suite manifest and floors unchanged.
        # Round 2 Breaks 5/6: one individually reviewed optional-opacity key.
        # No test files added/removed; all prior keys and floors retained.
        # Records regenerated (+0/-0/~1), digest rebound, identity computed then pinned.
        # Ideas jury completion: three optional-job occurrences individually reviewed;
        # historical keys and suite floors unchanged. Records regenerated, bound, then pinned.
        # Execution half: four new fixture files; forty individually reviewed fallback keys.
        # Records regenerated, both extent digests rebound, identity computed, then pinned.
        # Owner-authorized additional files repair: seven individually reviewed keys.
        # No test files added/removed; records regenerated, rebound, then identity pinned.
        # Pictured-width amendment: seven individually reviewed keys; no test-file
        # changes. Records regenerated, digest rebound, identity computed and pinned.
        # Owed module-move re-pin (owner, 2026-10-28): the fallback register's
        # four round_files_art keys re-keyed to round_files_reading (moved
        # unchanged) and the retired files' 25 removed; the suite manifest
        # +2/-2 (test_counter_display, test_round_files_faces in; the archived
        # test_round_files_art, test_round_files_job out). Manifest, records,
        # both digests rebound, identity computed, then pinned; no threshold changed.
        # The four checks re-pinned (owner, 2026-10-29, "Re-pin the four checks per PLAN.md"): the fallback register's
        # 257 keys of archived files moved to an archive record and 89 occurrences registered one by one; the 1q
        # allowlist's two reviewed dispositions; the declared list −42 (the consolidation's and the retirement's archived
        # test files, his third approved removal). Manifest, records, both digests rebound, identity computed equal to
        # its zero-write preview, then pinned; no threshold changed, no floor lowered.
        # 2026-10-29, §3 faces at 300 PPI: three fallback keys registered; records, rebind, identity (preview-equal).
        # the owner's goal of 2026-10-29 (faces built in layers): four layer-fitting occurrences registered under §R4 in gate_baseline.json; records regenerated, rebound, the identity pinned
        # the owner's ruling of 2026-10-29 (CURRENT_DECISIONS.md, "Owner: execution — match the pick"): the minimum test count lowered 10,949 → 9,890, the collected count — the archived tests left with their engines; the manifest digest rebound, records regenerated, the identity pinned
        # the owner's goal of 2026-10-29 (§5: the restart's check on the chain): chain_preflight's check registered under §R4; records regenerated, rebound, the identity pinned
        self.assertEqual(status["protocol_identity"], '9169003d5a11ab69')
        self.assertTrue(status["DECLARED"])
        self.assertTrue(status["REALIZED"])
        self.assertEqual(status["not_yet_implemented"], [])
        self.assertEqual(len(PP.POWDER_FAMILIES), 9)
        # every family names a sub-rig that exists and lists it back
        for fam, spec in PP.FAMILY_STRUCTURE.items():
            rig = spec["sub_rig"]
            self.assertIn(rig, PP.SUB_RIGS)
            self.assertIn(fam, PP.SUB_RIGS[rig]["families"])
        # every required distinction uses declared families and rigs
        for a, b, rig in PP.REQUIRED_DISTINCTIONS:
            self.assertIn(a, PP.POWDER_FAMILIES)
            self.assertIn(b, PP.POWDER_FAMILIES)
            self.assertIn(rig, PP.SUB_RIGS)
        self.assertEqual(status["colour_authority"]["FB3090"],
                         "UNSOURCED")
        self.assertEqual(PP.PASS_LAW["required_independent_axes"], 2)


class CloseoutBarTests(SimpleTestCase):
    def test_the_product_bar_is_predeclared(self):
        self.assertEqual(CO.PRODUCT_DIFF_MIN_FRACTION, 0.04)
        self.assertEqual(CO.PRODUCT_DIFF_LEVEL, 10)

    def test_the_exit_gate_reads_records_not_return_values(self):
        gate = CO.exit_gate()
        self.assertEqual(len(gate["checks"]), 19)
        pytest_check = next(c for c in gate["checks"] if c["n"] == 19)
        self.assertIn("cannot verify itself", pytest_check["detail"])

    def test_the_specular_condition_source_is_computed_not_tuned(self):
        """Option (a): the placement follows from mirror geometry and
        the apparatus is the characterization rig's own, verbatim."""
        from apps.pipeline.services import palette_characterization_rig
        import math
        src = palette_characterization_rig.RIG["specular_source"]
        point = (0.0, 0.0, 4.5)
        rim2 = CO.specular_condition_rim2(point)
        # apparatus transplanted verbatim — no new numbers
        self.assertEqual(rim2["size"], [src["size"], src["size"]])
        self.assertEqual(rim2["energy"], src["energy"])
        self.assertAlmostEqual(
            math.hypot(*(rim2["loc"][i] - point[i] for i in range(3))),
            src["distance"])
        # mirror geometry: reflected view direction about +Z, emission
        # axis aimed back at the surface point
        az = math.radians(CO.THREE_QUARTER_AZ_DEG)
        el = math.radians(CO.THREE_QUARTER_EL_DEG)
        self.assertAlmostEqual(
            rim2["loc"][0], -src["distance"] * math.cos(el) * math.sin(az))
        self.assertGreater(rim2["loc"][2], point[2])
        self.assertEqual(rim2["rot_deg"],
                         [90.0 - CO.THREE_QUARTER_EL_DEG, 0.0,
                          CO.THREE_QUARTER_AZ_DEG - 180.0])

    def test_an_occluded_specular_view_is_refused_not_scored(self):
        """The deck attempt scored 0.000 because the open lid stood in
        the optical path — indistinguishable from a material tie. The
        commissioning check must name a blocker on the camera ray and
        must ignore boxes behind the surface and the surface's owner."""
        import numpy as np

        def box(lo, hi):
            return {"vertices": np.array([lo, hi], dtype=float)}

        point = (0.0, 0.0, 4.5)
        # a slab straddling the ray between surface and camera
        state = {"subject": box((-5, -5, 4), (5, 5, 4.5)),
                 "lid": box((-60, -60, 5), (60, -30, 72))}
        self.assertEqual(
            CO.view_ray_blockers(state, point, "subject"), ["lid"])
        # the same slab BEHIND the surface (opposite the camera) is clear
        state = {"subject": box((-5, -5, 4), (5, 5, 4.5)),
                 "wall": box((-60, 30, -20), (-30, 60, 0))}
        self.assertEqual(
            CO.view_ray_blockers(state, point, "subject"), [])

    def test_the_closed_lid_specular_view_has_a_clear_path(self):
        """The corrected view must actually be measurable: on the real
        CLOSED assembly no component blocks the ray from the lid top to
        the three-quarter camera."""
        from apps.pipeline.services import palette_moulded_rect as MR
        from apps.pipeline.services import (
            palette_es3083_owner_confirmation as OC)
        comps, dims = MR.build_rect_components(OC.confirmed_intent())
        closed = MR.compose_rect_state(comps, dims, "CLOSED")
        lid = closed["lid_outer_shell"]["vertices"]
        centre = (0.0, float(lid[:, 1].mean()), float(lid[:, 2].max()))
        self.assertEqual(
            CO.view_ray_blockers(closed, centre, "lid_outer_shell"), [])

    def test_the_specular_row_is_calibrated_and_unclipped(self):
        """§9 record: the pair verdict may only rest on an unclipped,
        calibration-recorded measurement — a clipped 1.000 must never
        be what PASS points at."""
        rec = CO._load("m5_product_observability.json")
        row = next(r for r in rec["comparisons"]
                   if r["view"] == "specular_condition_closed_lid")
        self.assertTrue(row["unclipped"])
        self.assertLessEqual(max(row["p99_8bit"].values()),
                             CO.SPECULAR_MAX_P99_8BIT)
        calib = row["calibration"]
        self.assertEqual(calib["target_linear"],
                         CO.SPECULAR_TARGET_LINEAR)
        self.assertAlmostEqual(
            calib["calibrated_energy"],
            calib["reference_energy"] * calib["target_linear"]
            / calib["measured_peak_linear"])
        # both invalid attempts stay on the record with their lessons
        self.assertEqual(
            rec["invalid_views"]["specular_condition_deck"]["verdict"],
            "INVALID_VIEW_OCCLUDED_OPTICAL_PATH")
        self.assertEqual(
            rec["invalid_views"][
                "specular_condition_closed_lid_uncalibrated"]["verdict"],
            "INVALID_CLIPPED_MEASUREMENT")

    def test_the_mirrored_camera_angles_match_the_production_script(self):
        """The closeout mirrors az/el from palette_csg_views.py; if the
        script's three-quarter camera moves, this must fail."""
        from apps.pipeline.services import palt_p1_m4b_evidence as EV
        script = Path(EV.SCRIPT).read_text()
        expected = (f"az, el = math.radians("
                    f"{CO.THREE_QUARTER_AZ_DEG:g}), math.radians("
                    f"{CO.THREE_QUARTER_EL_DEG:g})")
        self.assertIn(expected, script)

    def test_condition_19_reads_the_external_suite_record(self):
        # The record is written by the checkpoint process after the
        # suite exits; a tampered or failing record must FAIL the gate.
        record = CO._load("m5_canonical_suite_record.json")
        self.assertIsNotNone(record)
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["failed"], 0)
        gate = CO.exit_gate()
        pytest_check = next(c for c in gate["checks"] if c["n"] == 19)
        self.assertEqual(pytest_check["verdict"], "PASS")


class AbsentDefectStandingControls(SimpleTestCase):
    """A362/3p — an absent defect is not a guarded defect.

    Both rows below were DEFECT_STRUCTURALLY_ABSENT in the hostile
    suite: the attempt ran, the condition obtained, and the instrument
    did nothing because there was nothing to do. That absence is a
    property of the current implementation and is loseable by any later
    edit with nothing to observe the loss. These are the retained
    reintroduction mutations, turned into standing controls.
    """

    def _gate(self):
        import importlib.util
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "t2_control", root / "tools" / "tier2_gate.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_extent_of_comparison_remains_absent(self):
        """Reintroduction mutation: drop the ^ anchor from failed_ids.
        Observed to reintroduce over-collection, so this asserts the
        anchor still holds. immunity_kind: STRUCTURAL."""
        gate = self._gate()
        embedded = "captured stdout: FAILED apps/fake.py::test_x\n1 passed\n"
        self.assertEqual(gate.failed_ids(embedded), [],
                         "failed_ids over-collected a FAILED token that was "
                         "not at line start — the ^ anchor was lost")
        self.assertEqual(
            gate.failed_ids("FAILED apps/fake.py::test_x\n"),
            ["apps/fake.py::test_x"],
            "the anchored form must still be collected, or this control "
            "would pass by matching nothing at all")

    def test_observation_window_remains_full(self):
        """Reintroduction mutation: slice proc.stdout before parsing.
        Observed to lose one of two ids, so this asserts both survive.
        immunity_kind: STRUCTURAL."""
        gate = self._gate()
        wide = ("FAILED apps/a.py::t1\n" + "x" * 400
                + "\nFAILED apps/b.py::t2\n")
        self.assertEqual(gate.failed_ids(wide),
                         ["apps/a.py::t1", "apps/b.py::t2"],
                         "an id was lost — the parse window is narrower "
                         "than the event")

    def test_node_id_normalization_refuses_rather_than_falling_through(self):
        """A366 — the fall-through is the dangerous half: an
        unnormalizable key must not present as UNREGISTERED."""
        gate = self._gate()
        self.assertEqual(
            gate.normalize_node_id("_a/test_x.py::test_y"),
            "_a/test_x.py::test_y")
        with self.assertRaises(gate.UnnormalizableNodeId):
            gate.normalize_node_id("no-double-colon-here.py")

    def test_instrument_prose_asserts_no_absolutes(self):
        """A365 — the prohibition is the enforceable form of 'inspect
        claims', which is not buildable."""
        import importlib.util
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "claim_scan", root / "tools" / "claim_scan.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import os
        cwd = os.getcwd()
        os.chdir(root)
        try:
            self.assertEqual(mod.scan(), [])
        finally:
            os.chdir(cwd)


class ExtentManifestDeclaresEveryTestFile(SimpleTestCase):
    """§AR / WI-3J — A327(a) is blind to every file it does not declare.

    The clause enumerates the file SET rather than a total because "a
    total alone cannot detect a file's disappearance". That is true of
    DECLARED files and says nothing about undeclared ones, and the
    consequence runs backwards: an undeclared file's disappearance
    REDUCES the refusal count, because the file simply stops appearing in
    `actual_files - declared`. Measured by mutation at §AR: deleting
    undeclared `test_back_panel.py` (41 tests) took refusals 44 -> 43,
    while deleting a declared file took them 44 -> 45 and named it. The
    instrument reported improvement when coverage was lost, across 44
    files and 1,310 tests — 17.8% of the suite.

    These tests use the FILESYSTEM rather than a nested `--collect-only`,
    deliberately. A second pytest process inside the suite would share
    the test database with the run hosting it, and the point of a
    standing guard is that it is cheap enough to always be on.
    """

    def _manifest(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        return root, json.loads(
            (root / "docs/roadmap/palt_m6/suite_file_manifest.json")
            .read_text())

    def _disk_test_files(self, root):
        import os
        found = set()
        for base, dirs, files in os.walk(root / "apps"):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    found.add(os.path.relpath(os.path.join(base, f), root))
        return found

    def test_every_test_file_on_disk_is_declared(self):
        """The standing guard. Measured 2026-08-20: 361 test_*.py files
        under apps/, all declared, plus apps/core/tests.py which is
        declared and collected under Django's older naming.

        An hour before this test existed the same predicate produced 44
        violations, which is why it is a test and not a comment."""
        root, m = self._manifest()
        undeclared = sorted(self._disk_test_files(root) - set(m["files"]))
        self.assertEqual(
            undeclared, [],
            "%d test files exist on disk and are outside the declared "
            "extent. Every one of them could vanish and A327(a) would "
            "complain LESS, not more. Regenerate via "
            "tools/tier2_gate.py --regenerate-manifest, and read §AR4(1) "
            "first: the diff must be purely additive."
            % len(undeclared))

    def test_the_committed_diff_log_shows_what_this_closed(self):
        """The historical negative control, and it is a RECORD rather
        than a synthetic one.

        A guard that has only ever been true proves nothing about its own
        sensitivity (§AA). This one was false — for 44 files, for eight
        days — and `suite_manifest_diffs.json` is the committed evidence,
        written by the tool at the moment of the repair rather than by me
        afterwards.

        THE ANCHOR IS THE CONTENT, NOT THE POSITION. My first draft read
        `diffs[-1]` and meant "the entry that closed the gap"; running the
        regenerator a second time appended an empty entry and the test
        failed with `0 not greater than or equal to 44`. It was asserting
        about a POSITION while claiming to assert about an event, and the
        position moves every time anyone runs the tool. So the claim is
        made over the whole log instead, which is also the stronger claim:
        the log is the append-only history of the declared set, every file
        it has ever recorded as added must still be declared, and no entry
        may have absorbed a removal."""
        root, m = self._manifest()
        log = json.loads(
            (root / "docs/roadmap/palt_m6/suite_manifest_diffs.json")
            .read_text())
        # THE ONE REMOVAL HE APPROVED. His answer by option of 2026-09-26 ("Yes, accept this one"), on the register
        # after his answer to the §BH69 (1) list (1eff269) ordered the supplier-outreach code removed and the declared
        # list shrunk for its three test files: the tool recorded that shrink at exactly this entry. Anchored to the
        # entry's content — its time and its removed list, both whole — and asserted present once, so the exception
        # can neither widen nor go vacuous; every other removal still fails below.
        approved = {"utc": "2026-09-26T19:26:39.815045Z",
                    "removed": ["apps/pipeline/tests/test_supplier_dispatch.py",
                                "apps/pipeline/tests/test_supplier_eml.py",
                                "apps/pipeline/tests/test_supplier_sent_validation.py"]}
        self.assertEqual(
            [e["removed"] for e in log["diffs"] if e["utc"] == approved["utc"]],
            [approved["removed"]],
            "the approved removal's entry is not in the log exactly once, "
            "as he approved it")
        # THE SECOND, THE MODULE MOVES. His "STOP AND REUSE — THE FILES BUILD" (2026-10-27, CURRENT_DECISIONS.md)
        # retired the picture-tracing modules and their tests to archive/round_files_v1/; his message of 2026-10-28
        # ("Re-pin the two repo checks owed from the module moves (the test-file list and the fallback register)")
        # ordered the declared list to follow. Anchored the same way: its time and its removed list, whole, once.
        moved = {"utc": "2026-10-28T06:36:49.506375Z",
                 "removed": ["apps/pipeline/tests/test_round_files_art.py",
                             "apps/pipeline/tests/test_round_files_job.py"]}
        self.assertEqual(
            [e["removed"] for e in log["diffs"] if e["utc"] == moved["utc"]],
            [moved["removed"]],
            "the module moves' removal is not in the log exactly once, as he ordered it")
        # THE THIRD, THE CONSOLIDATION AND THE RETIREMENT. His "ENGINE CONSOLIDATION" (2026-10-28) archived the engines
        # nothing in the chain needs, tests with them; his "QUALITY, NOT COUNT" (2026-10-29, CURRENT_DECISIONS.md) retired
        # the history pages and ordered "Re-pin the four checks per PLAN.md" — the declared list among them. Anchored the
        # same way: its time and its removed list (42 test files, each moved to archive/ by git mv), whole, once.
        retired = {"utc": "2026-10-28T20:47:11.922378Z",
                   "removed": [
                               "apps/dielines/tests/test_counter_tray_header.py",
                               "apps/pipeline/tests/test_balm_leaflet.py",
                               "apps/pipeline/tests/test_day11_carton.py",
                               "apps/pipeline/tests/test_day11_golden_hour.py",
                               "apps/pipeline/tests/test_day11_lipstick.py",
                               "apps/pipeline/tests/test_day11_zilal.py",
                               "apps/pipeline/tests/test_day11_zilal_pack.py",
                               "apps/pipeline/tests/test_day12_balm.py",
                               "apps/pipeline/tests/test_day12_board.py",
                               "apps/pipeline/tests/test_day12_display.py",
                               "apps/pipeline/tests/test_day12_lipstick.py",
                               "apps/pipeline/tests/test_day12_reader.py",
                               "apps/pipeline/tests/test_day13_carton_copy.py",
                               "apps/pipeline/tests/test_day13_creativity.py",
                               "apps/pipeline/tests/test_day13_creativity_page.py",
                               "apps/pipeline/tests/test_day13_demo.py",
                               "apps/pipeline/tests/test_day13_display_faces.py",
                               "apps/pipeline/tests/test_day13_lipstick_carton.py",
                               "apps/pipeline/tests/test_day13_print_pack.py",
                               "apps/pipeline/tests/test_day14_wrap.py",
                               "apps/pipeline/tests/test_day8_jury.py",
                               "apps/pipeline/tests/test_day9_orn_b1.py",
                               "apps/pipeline/tests/test_day9_orn_b2.py",
                               "apps/pipeline/tests/test_day9_orn_c1.py",
                               "apps/pipeline/tests/test_hayat_cap_cleanup.py",
                               "apps/pipeline/tests/test_hayat_derivative_diff.py",
                               "apps/pipeline/tests/test_hayat_master_artifacts.py",
                               "apps/pipeline/tests/test_hayat_master_page.py",
                               "apps/pipeline/tests/test_hayat_review_contract.py",
                               "apps/pipeline/tests/test_hayat_side_repair.py",
                               "apps/pipeline/tests/test_rescue_day2_browser.py",
                               "apps/pipeline/tests/test_rescue_day3_browser.py",
                               "apps/pipeline/tests/test_rescue_day4_browser.py",
                               "apps/pipeline/tests/test_rescue_day5_browser.py",
                               "apps/pipeline/tests/test_rescue_day6.py",
                               "apps/pipeline/tests/test_rescue_day6_bottle.py",
                               "apps/pipeline/tests/test_rescue_day6_browser.py",
                               "apps/pipeline/tests/test_rescue_day6_cut_layout.py",
                               "apps/pipeline/tests/test_rescue_day6_native.py",
                               "apps/pipeline/tests/test_rescue_day6_render.py",
                               "apps/pipeline/tests/test_rescue_day6_surface_fidelity.py",
                               "apps/pipeline/tests/test_round_balm_preservation.py"]}
        self.assertEqual(
            [e["removed"] for e in log["diffs"] if e["utc"] == retired["utc"]],
            [retired["removed"]],
            "the retirement's removal is not in the log exactly once, as he ordered it")
        for entry in log["diffs"]:
            if entry["utc"] in (approved["utc"], moved["utc"], retired["utc"]):
                continue
            self.assertEqual(
                entry["removed"], [],
                "§AR4(1)/§AR3(b): a regeneration absorbed a removal at "
                "%s. Removals are FINDINGS — a regeneration that swallows "
                "one converts A327(a) into a rubber stamp." % entry["utc"])
        self.assertTrue(
            any(len(e["added"]) >= 44 for e in log["diffs"]),
            "no entry records the 44 additions that closed the §AR gap; "
            "the history this control depends on is gone")
        declared = set(m["files"])
        ever_added = {f for e in log["diffs"] for f in e["added"]}
        lost = sorted(f for f in ever_added
                      if f not in declared and f not in approved["removed"] + moved["removed"] + retired["removed"])
        self.assertEqual(lost, [], "declared once, no longer declared: %s"
                         % lost)


class ExtentFloorsAreMonotonic(SimpleTestCase):
    """§AR3(d)/§AR4(3) — floors are re-measured and never lowered.

    Until WI-3J `regenerate_manifest` carried floors forward verbatim, so
    a floor moved only when someone hand-edited a file whose digest sits
    in EXTENT_DIGESTS — a full A391 re-pin to change one integer. What
    that cost bought is measurable rather than predictable: between
    2026-08-12 and 2026-08-20 nobody paid it, and the manifest said 28
    for test_characterization_protocol.py against a measured 59 — inside
    the gate that exists because THIS FILE once went to zero bytes. It
    would have tolerated losing 31 of its 59 tests in silence.

    A365 fired on the first draft of this paragraph, which said the
    floors were "guaranteed to rot". They were not guaranteed to do
    anything; they rotted, which is a measurement, and §AM is the rule
    that a description of the present is not a law about the future.

    §AJ, at WI-3G, diagnosed exactly this staleness and repaired one of
    the two copies of the number. A repair applied to one of two copies
    is a measurement of one of two copies.
    """

    def _gate(self):
        import importlib.util
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "t2_floors", root / "tools" / "tier2_gate.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_stale_floor_is_raised_to_the_measurement(self):
        """The §AR case, in its own numbers."""
        gate = self._gate()
        raised = gate.raised_floors(
            {"apps/pipeline/tests/test_characterization_protocol.py": 28},
            {"apps/pipeline/tests/test_characterization_protocol.py": 59})
        self.assertEqual(
            raised["apps/pipeline/tests/test_characterization_protocol.py"],
            59)

    def test_a_floor_is_never_lowered_by_a_regeneration(self):
        """THE FENCE, and the reason `max` is in the code rather than a
        plain assignment.

        Re-measuring on regeneration is only safe if the tool cannot
        profit from a smaller measurement. Without this, running the
        regenerator on a suite that had just lost half its tests would
        write the smaller number down and call it the standard — the
        §AL4 move, in a different file. Lowering a floor must cost a
        deliberate hand-edit and a diff someone can read."""
        gate = self._gate()
        raised = gate.raised_floors({"a.py": 59, "b.py": 49},
                                    {"a.py": 12, "b.py": 50})
        self.assertEqual(raised["a.py"], 59,
                         "a regeneration lowered a floor to a smaller "
                         "measurement — the gate can now buy relief by "
                         "being run at the wrong moment")
        self.assertEqual(raised["b.py"], 50,
                         "and the raise must still happen, or this "
                         "control passes by freezing everything")

    def test_a_tier1_file_that_stopped_collecting_keeps_its_floor(self):
        """The zero-bytes case, which is the whole reason TIER_1 floors
        exist. A file absent from `counts` reports 0; `max` holds the
        floor rather than collapsing it to zero. Its absence is
        A327(a)'s to refuse on — one clause failing open into another is
        how the zero-bytes defect happened the first time."""
        gate = self._gate()
        self.assertEqual(gate.raised_floors({"gone.py": 59}, {})["gone.py"],
                         59)

    def test_the_manifest_on_disk_carries_no_stale_floor(self):
        """The state assertion, against the committed manifest. This is
        the one that fails if a future regeneration reverts to carrying
        floors forward: the file grows, the floor does not, and nobody
        notices for another eight days."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        m = json.loads(
            (root / "docs/roadmap/palt_m6/suite_file_manifest.json")
            .read_text())
        self.assertGreaterEqual(
            m["tier1_floors"]
            ["apps/pipeline/tests/test_characterization_protocol.py"], 59,
            "the manifest floor is back below the measured extent")
        self.assertGreaterEqual(
            m["total_floor"], 7353,
            "total_floor retreated. §AR3(d): a backstop trailing the "
            "suite by 19%% is not a backstop.")

    def test_the_two_copies_of_the_tier1_floors_agree(self):
        """§AR2 — the finding was not "a number was stale", it was "there
        are two copies of the number and I repaired one".

        The duplication is deliberate and stays: TIER_1 runs before
        tier2_gate's digest check, so a TIER_1 that read the manifest
        directly would trust an unverified file and an edited manifest
        could lower this floor. Two copies with an enforced agreement is
        the smaller risk. This is the enforcement.

        The assertion is one-directional — the shell copy may not be
        BELOW the manifest copy — because that is the direction that
        loses coverage silently. A shell copy that is higher refuses
        earlier, which is noisy rather than blind.

        THE MAINTENANCE COST IS THE POINT AND IS NOT A BUG. Growing a
        TIER_1 file raises the manifest floor on the next regeneration
        and this test then demands the shell array be updated by hand.
        That is one integer in one file, for the two TIER_1 files only,
        and it fired within a minute of being written — the third
        regeneration took the manifest to 66 while the shell still said
        65. A guard that costs nothing and has never fired is the thing
        §AA warns about. Do not resolve a failure here by deleting this
        test or by loosening it to a tolerance; update the number.
        """
        import pathlib
        import re
        root = pathlib.Path(__file__).resolve().parents[3]
        script = (root / "tools" / "guarded_commit.sh").read_text()
        block = re.search(r"EXPECTED_TARGETS=\((.*?)\)", script, re.S)
        self.assertIsNotNone(
            block, "EXPECTED_TARGETS is no longer an array literal in "
                   "guarded_commit.sh — this check reads it by shape and "
                   "has just stopped being able to see it (AD0(b)). Do "
                   "not delete this assertion; re-point the parse.")
        shell = {m.group(1): int(m.group(2)) for m in
                 re.finditer(r'"([^":]+):(\d+)"', block.group(1))}
        self.assertEqual(
            len(shell), 2,
            "parsed %d TIER_1 targets from the shell array, expected 2. "
            "A vacuous parse would let this control pass by matching "
            "nothing at all." % len(shell))
        m = json.loads(
            (root / "docs/roadmap/palt_m6/suite_file_manifest.json")
            .read_text())
        for path, floor in m["tier1_floors"].items():
            self.assertIn(path, shell,
                          "%s is a TIER_1 floor in the manifest and is "
                          "absent from guarded_commit.sh" % path)
            self.assertGreaterEqual(
                shell[path], floor,
                "guarded_commit.sh declares %d for %s while the manifest "
                "declares %d. This is §AR2 recurring: two copies, one "
                "number, and the lower one wins wherever it is read."
                % (shell[path], path, floor))


class DecisionSurfaceStandingControl(SimpleTestCase):
    """3t / class seventeen — DECISION_WITHOUT_A_REVIEW_SURFACE.

    Retained per 3p: an absence proven once is loseable by any later
    edit with nothing to observe the loss. The reintroduction mutation
    is removing shade_names from the panel again; it was OBSERVED to
    reintroduce the defect, so this asserts the row still holds.
    """

    def _panel_and_record(self):
        from apps.pipeline.services import palette_intent_confirmation as pc
        from apps.pipeline.services.palette_es3083_intent import (
            build_es3083_intent)
        from apps.pipeline.services import (
            palette_es3083_owner_confirmation as oc)
        rows = pc.panel(build_es3083_intent())["rows"]
        return pc, rows, oc.confirmation_record().actions

    def test_no_decision_lacks_a_review_surface(self):
        pc, rows, actions = self._panel_and_record()
        result = pc.reconcile_decision_surface(actions, rows)
        self.assertEqual(
            result["UNSURFACED"], [],
            "a decision is attributed to the owner that no panel row "
            "could have shown them")

    def test_the_check_fires_when_a_row_is_removed(self):
        """The mutation, retained. A check that cannot fail is worse
        than absent because it reports coverage."""
        pc, rows, actions = self._panel_and_record()
        mutated = [r for r in rows if r["field"] != "shade_names"]
        self.assertEqual(
            pc.reconcile_decision_surface(actions, mutated)["UNSURFACED"],
            ["shade_names"],
            "removing the row must reintroduce the defect, or this "
            "control is not load-bearing")


class SurfacePartitionStandingControl(SimpleTestCase):
    """3u / class eighteen — FIELD_NEITHER_SURFACED_NOR_DECLARED_WITHHELD.

    Class seventeen compares RECORD to PANEL and is blind to this by
    construction: a field in neither population cannot appear in a
    difference of the two. Demonstrated, not assumed.
    """

    def _parts(self):
        from apps.pipeline.services import palette_intent_confirmation as pc
        from apps.pipeline.services import palette_design_intent as di
        from apps.pipeline.services.palette_es3083_intent import (
            build_es3083_intent)
        intent = build_es3083_intent()
        return pc, di, intent, pc.panel(intent)["rows"]

    def _smuggle(self, di, intent, name="symmetry"):
        tmpl = intent.get("silhouette")
        return di.IntentField(
            name=name, value="BILATERAL",
            source_reference=tmpl.source_reference, source_region="n/a",
            confidence=0.9, extraction_method=tmpl.extraction_method,
            confirmation_state="PENDING_OWNER_CONFIRMATION",
            constraint_level="HARD_VISIBLE_CONSTRAINT",
            geometry_relevance=True, material_relevance=False,
            artwork_relevance=False)

    def test_every_intent_field_is_surfaced_or_declared_withheld(self):
        pc, _di, intent, rows = self._parts()
        self.assertTrue(pc.assert_surface_partition(intent, rows))

    def test_the_check_fires_on_an_undeclared_field(self):
        """The retained mutation. A check that cannot fail is worse than
        absent because it reports coverage."""
        pc, di, intent, rows = self._parts()
        intent.fields.append(self._smuggle(di, intent))
        try:
            with self.assertRaises(pc.UndeclaredField):
                pc.assert_surface_partition(intent, rows)
        finally:
            intent.fields.pop()

    def test_class_seventeen_is_blind_to_it(self):
        """Proves the two classes are distinct rather than duplicates."""
        pc, di, intent, rows = self._parts()
        from apps.pipeline.services import (
            palette_es3083_owner_confirmation as oc)
        intent.fields.append(self._smuggle(di, intent))
        try:
            result = pc.reconcile_decision_surface(
                oc.confirmation_record().actions, rows)
            self.assertEqual(result["UNSURFACED"], [])
        finally:
            intent.fields.pop()

    def test_withheld_reasons_come_from_the_closed_vocabulary(self):
        pc, _di, _intent, _rows = self._parts()
        for field, (reason, _why) in pc.NOT_SURFACED.items():
            self.assertIn(reason, pc.WITHHELD_REASONS, field)


class ResolutionOrderStandingControl(SimpleTestCase):
    """3v / class ten EXHIBITED — which act governs, asserted.

    apply_confirmations resolves accumulated acts by iteration order and
    nothing said so. Reversing the loop changes the confirmed intent
    while every pre-existing test still passes. These assertions fail if
    the resolution order changes.
    """

    def _mod(self):
        from apps.pipeline.services import palette_intent_confirmation as pc
        return pc

    def _apply(self, pc, *acts):
        from apps.pipeline.services.palette_es3083_intent import (
            build_es3083_intent)
        intent = build_es3083_intent()
        record = pc.ConfirmationRecord(
            concept_reference=intent.concept_reference,
            draft_identity=intent.identity())
        for a in acts:
            record.apply(a)
        out = pc.apply_confirmations(intent, record)
        return out.get("pan_count") or next(
            (f for f in out.fields if f.name == "pan_count"), None)

    def test_the_rule_is_named(self):
        pc = self._mod()
        self.assertEqual(
            pc.RESOLUTION_RULE,
            "LAST_WRITE_PER_ATTRIBUTE_WINS_EXCEPT_DELETE_WHICH_DOMINATES")

    def test_last_write_wins_on_the_same_attribute(self):
        pc = self._mod()
        A = pc.ConfirmationAction
        self.assertEqual(
            self._apply(pc, A("pan_count", pc.CORRECT, new_value=7, route="PANEL_ACTION"),
                        A("pan_count", pc.CORRECT, new_value=8, route="PANEL_ACTION")).value, 8)
        self.assertEqual(
            self._apply(pc, A("pan_count", pc.CORRECT, new_value=8, route="PANEL_ACTION"),
                        A("pan_count", pc.CORRECT, new_value=7, route="PANEL_ACTION")).value, 7)

    def test_state_depends_on_order_and_this_is_the_exhibit(self):
        """CORRECT then CONFIRM and CONFIRM then CORRECT are the same two
        acts with different outcomes, decided by loop order alone."""
        pc = self._mod()
        A = pc.ConfirmationAction
        first = self._apply(pc, A("pan_count", pc.CORRECT, new_value=99, route="PANEL_ACTION"),
                            A("pan_count", pc.CONFIRM, route="PANEL_ACTION"))
        second = self._apply(pc, A("pan_count", pc.CONFIRM, route="PANEL_ACTION"),
                             A("pan_count", pc.CORRECT, new_value=99, route="PANEL_ACTION"))
        self.assertNotEqual(first.confirmation_state,
                            second.confirmation_state)

    def test_different_attributes_compose_rather_than_supersede(self):
        pc = self._mod()
        A = pc.ConfirmationAction
        f = self._apply(pc, A("pan_count", pc.CORRECT, new_value=12, route="PANEL_ACTION"),
                        A("pan_count", pc.RECLASSIFY,
                          new_level="HARD_VISIBLE_CONSTRAINT",
                          route="PANEL_ACTION"))
        self.assertEqual(f.value, 12)
        self.assertEqual(f.constraint_level, "HARD_VISIBLE_CONSTRAINT")

    def test_delete_dominates_regardless_of_position(self):
        pc = self._mod()
        A = pc.ConfirmationAction
        for pair in ((A("pan_count", pc.DELETE, route="PANEL_ACTION"), A("pan_count", pc.CONFIRM, route="PANEL_ACTION")),
                     (A("pan_count", pc.CONFIRM, route="PANEL_ACTION"), A("pan_count", pc.DELETE, route="PANEL_ACTION"))):
            self.assertEqual(self._apply(pc, *pair).confirmation_state,
                             "OWNER_REMOVED")


class MultiplicityStandingControl(SimpleTestCase):
    """3v / class nineteen — MULTIPLICITY_ERASED_BY_A_SET_COMPARISON."""

    def test_set_difference_reads_clean_while_doubled_names_it(self):
        from apps.pipeline.services import palette_intent_confirmation as pc
        from apps.pipeline.services.palette_es3083_intent import (
            build_es3083_intent)
        rows = pc.panel(build_es3083_intent())["rows"]
        tripled = [{"field_name": "margins", "action": "CONFIRM",
                    "route": "PANEL_ACTION"}] * 3
        result = pc.reconcile_decision_surface(tripled, rows)
        # the set comparison is blind to it
        self.assertEqual(result["UNSURFACED"], [])
        # DOUBLED is not
        self.assertEqual(result["DOUBLED"],
                         {"margins": ["CONFIRM", "CONFIRM", "CONFIRM"]})


class RouteStandingControl(SimpleTestCase):
    """3w — an act carries its route, and a count that mixes routes
    measures the process rather than the subject."""

    def _pc(self):
        from apps.pipeline.services import palette_intent_confirmation as pc
        return pc

    def _rows(self, pc):
        from apps.pipeline.services.palette_es3083_intent import (
            build_es3083_intent)
        return pc.panel(build_es3083_intent())["rows"]

    def test_an_act_without_a_route_is_refused_at_construction(self):
        pc = self._pc()
        with self.assertRaises(pc.MissingRoute):
            pc.ConfirmationAction(field_name="margins", action="CONFIRM")

    def test_an_undeclared_route_is_refused(self):
        pc = self._pc()
        with self.assertRaises(pc.MissingRoute):
            pc.ConfirmationAction(field_name="margins", action="CONFIRM",
                                  route="SOMEWHERE")

    def test_forged_same_route_same_attribute_is_flagged(self):
        pc = self._pc()
        A = pc.ConfirmationAction
        forged = [A(field_name="margins", action=pc.CORRECT, new_value="a",
                    route="PANEL_ACTION"),
                  A(field_name="margins", action=pc.CORRECT, new_value="b",
                    route="PANEL_ACTION")]
        r = pc.reconcile_decision_surface(forged, self._rows(pc))
        self.assertEqual(r["FLAGGED_SAME_ROUTE_SAME_ATTRIBUTE"],
                         {"margins|PANEL_ACTION|value": 2})

    def test_legitimate_cross_attribute_multiplicity_is_not_flagged(self):
        pc = self._pc()
        A = pc.ConfirmationAction
        legit = [A(field_name="pan_count", action=pc.CORRECT, new_value=12,
                   route="BASELINE_REPLAY"),
                 A(field_name="pan_count", action=pc.RECLASSIFY,
                   new_level="HARD_VISIBLE_CONSTRAINT",
                   route="BASELINE_REPLAY")]
        r = pc.reconcile_decision_surface(legit, self._rows(pc))
        self.assertEqual(r["FLAGGED_SAME_ROUTE_SAME_ATTRIBUTE"], {})
        # and the undecomposed measure cannot tell the two cases apart
        self.assertEqual(list(r["DOUBLED"].values()),
                         [["CORRECT", "RECLASSIFY"]])


class A597RecordGateHarvestTests(SimpleTestCase):
    """A539/A554 — the free harvest, and the proof it is not silent.

    The record gate computed its verdict and its failing set on every
    run and threw both away on the green path: a pass printed three
    words and recorded neither its extent nor the set it passed over.
    That is the shape 3m closed for TIER_2 at the suite level, still
    open at the record level. Deferred four nodes; landed here.

    Every test below redirects the ledger to a temporary file. The
    committed ledger is an APPEND_ONLY record and the suite may not
    write to it — a test that mutates the artifact it checks is the
    defect, not the check.
    """

    def _mod(self):
        import importlib.util
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "ri_harvest", root / "tools" / "record_integrity.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_the_ledger_is_declared_APPEND_ONLY(self):
        """Overwriting a fixed path each run is class twenty-two,
        CAPTURE_WITHOUT_RETENTION — the defect .tier2_gate_output
        already exhibits. The harvest must not repeat it."""
        mod = self._mod()
        self.assertIn("record_gate_ledger.jsonl", mod.APPEND_ONLY_NAMES)
        self.assertEqual(mod.classify("/x/record_gate_ledger.jsonl"),
                         "APPEND_ONLY")

    def test_a_green_run_records_its_extent_not_just_its_verdict(self):
        import json
        import tempfile
        mod = self._mod()
        rows = {"a.json": {"classification": "REVISABLE"},
                "b.jsonl": {"classification": "APPEND_ONLY"}}
        with tempfile.TemporaryDirectory() as td:
            mod.LEDGER = f"{td}/ledger.jsonl"
            line = mod.emit_ledger("OK", [], rows)
            written = [json.loads(x) for x in
                       open(mod.LEDGER).read().splitlines()]
        self.assertEqual(line["verdict"], "OK")
        self.assertEqual(line["records_checked"], 2)
        self.assertEqual(line["append_only"], 1)
        self.assertEqual(line["revisable"], 1)
        self.assertEqual(written, [line])

    def test_the_failing_set_is_emitted_ENTIRE_not_counted(self):
        """2p — a count without an enumeration is not a declaration.
        The stderr path truncates at 20; the ledger must not."""
        import tempfile
        mod = self._mod()
        refusals = [f"RECORD_UNDECLARED: docs/r/f{i}.json" for i in range(25)]
        with tempfile.TemporaryDirectory() as td:
            mod.LEDGER = f"{td}/ledger.jsonl"
            line = mod.emit_ledger("REFUSED", refusals, {})
        self.assertEqual(line["refusal_count"], 25)
        self.assertEqual(line["failing_set"], refusals)

    def test_the_ledger_appends_and_never_rewrites(self):
        import tempfile
        mod = self._mod()
        with tempfile.TemporaryDirectory() as td:
            mod.LEDGER = f"{td}/ledger.jsonl"
            mod.emit_ledger("OK", [], {})
            first = open(mod.LEDGER).read()
            mod.emit_ledger("REFUSED", ["RECORD_MISSING: x"], {})
            second = open(mod.LEDGER).read()
        self.assertTrue(second.startswith(first),
                        "history was rewritten, not appended")
        self.assertEqual(len(second.splitlines()), 2)

    def test_check_accepts_a_prepared_survey_so_the_harvest_is_free(self):
        """Zero marginal cost is the whole claim: the survey is taken
        once and shared, not taken twice so the ledger can be written."""
        import inspect
        mod = self._mod()
        self.assertIn("now", inspect.signature(mod.check).parameters)
        src = inspect.getsource(mod.main)
        self.assertIn("rows = survey()", src)
        self.assertIn("check(rows)", src)


class AJ3CompressedRecordTests(SimpleTestCase):
    """§AJ3/A403 — a record does not stop being a record by being
    compressed.

    WI-3G. `record_integrity.py` halted on `.gz` because the kind had no
    stored disposition, and the kind had no stored disposition because I
    put the only `.gz` in the tree myself at 5d06ae6 without classifying
    it. Dispositioning `.gz` NOT_A_RECORD closes the halt and opens
    something worse: `os.path.splitext` reduces `findings.json.gz` to
    `.gz`, so a compressed findings record would classify as a capture
    and be waved into a 4,139-file complement — the exact disappearance
    this instrument was built to prevent, and its own docstring names
    the shape.

    So a wrapped file is classified by WHAT IT WRAPS. Every test below
    builds its own tree and passes it as `root`; before WI-3G this guard
    could only be fired by writing into the real record directory, which
    is why it had never been fired.
    """

    def _mod(self):
        import importlib.util
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "ri_gz", root / "tools" / "record_integrity.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _tree(self, td, *names):
        import os
        for n in names:
            p = os.path.join(td, n)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(b"x")
        return td

    def test_a_record_does_not_escape_the_gate_by_being_compressed(self):
        """THE ONE THAT MATTERS. A gzipped findings record is a findings
        record sitting outside the binding pattern, and the gate must
        say so."""
        import tempfile
        mod = self._mod()
        with tempfile.TemporaryDirectory() as td:
            self._tree(td, "sub/findings.json.gz")
            _kinds, refusals = mod.classify_complement(root=td)
        self.assertTrue(
            any("RECORD_KIND_OUTSIDE_PATTERN" in r for r in refusals),
            f"a compressed record passed the gate unnoticed: {refusals}")

    def test_a_compressed_capture_is_still_not_a_record(self):
        """The other direction, or the rule is just 'refuse everything
        gzipped'. `.log.gz` is a `.log`, and `.log` is unbound by
        design."""
        import tempfile
        mod = self._mod()
        with tempfile.TemporaryDirectory() as td:
            self._tree(td, "suite_records/vqr3_fullsuite.log.gz")
            _kinds, refusals = mod.classify_complement(root=td)
        self.assertEqual(refusals, [])

    def test_wrapping_is_not_an_escape_hatch_for_the_halt(self):
        """An unclassifiable inner extension must still stop the
        selection. If compression laundered unknown kinds into a known
        one, A403 would be repealed by a suffix."""
        import tempfile
        mod = self._mod()
        with tempfile.TemporaryDirectory() as td:
            self._tree(td, "sub/mystery.wat.gz")
            with self.assertRaises(mod.UnclassifiedKind):
                mod.classify_complement(root=td)

    def test_the_bare_wrapper_with_nothing_inside_is_still_classified(self):
        """`archive.gz` has no inner extension. It must not crash and
        must not be silently dropped — it falls back to the wrapper's own
        disposition."""
        import tempfile
        mod = self._mod()
        with tempfile.TemporaryDirectory() as td:
            self._tree(td, "sub/archive.gz")
            kinds, refusals = mod.classify_complement(root=td)
        self.assertEqual(refusals, [])
        self.assertEqual(sum(kinds.values()), 1)

    def test_the_real_gz_in_the_committed_tree_classifies_clean(self):
        """Not a synthetic case: the file that caused the halt is in the
        repository and this is what the gate now says about it."""
        import os
        mod = self._mod()
        real = os.path.join(
            mod.ROOT, "docs/roadmap/palt_m6/suite_records/"
                      "vqr3_fullsuite.log.gz")
        self.assertTrue(os.path.exists(real), "the subject moved")
        _kinds, refusals = mod.classify_complement()
        self.assertEqual(
            [r for r in refusals if "RECORD_KIND_OUTSIDE_PATTERN" in r], [])

    def test_the_walked_root_is_overridable_so_this_guard_can_be_fired(self):
        """§AA — a guard nobody has seen fire is not evidence of
        anything. The override exists so the five tests above can exist;
        without it they would have to write into the real record tree."""
        import inspect
        mod = self._mod()
        self.assertIn("root",
                      inspect.signature(mod.classify_complement).parameters)
