"""H2 design-request validators — promotion regression + contract rules.

The decisive test: BOTH live run trees validate UNCHANGED under the
promoted module — the docs arcs are the ground truth the promotion must
not disturb. Everything else pins the contract's refusal semantics.
"""
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services import h2_design_request as H2

REPO = Path(__file__).resolve().parents[3]
PALT_H2 = REPO / "docs" / "roadmap" / "palt_h2"


class RunTreeRegressionTests(SimpleTestCase):
    """The two live arcs ARE the regression: every known request dir
    must validate PASS on all four stages, exactly as the docs-side
    validators ruled during the arcs."""

    def test_known_request_dirs_all_exist(self):
        for d in H2.KNOWN_REQUEST_DIRS:
            self.assertTrue((PALT_H2 / d).is_dir(), d)

    def test_es3083_lid_alt_01_validates_pass(self):
        out = H2.validate_request(PALT_H2 / "es3083_lid_alt_01")
        self.assertEqual(out["verdict"], "PASS", out)

    def test_fb3093_compact_01_validates_pass(self):
        out = H2.validate_request(PALT_H2 / "fb3093_compact_01")
        self.assertEqual(out["verdict"], "PASS", out)

    def test_fb3093_compact_02_validates_pass_via_mandate_waiver(self):
        out = H2.validate_request(PALT_H2 / "fb3093_compact_02")
        self.assertEqual(out["verdict"], "PASS", out)
        cands = json.loads((PALT_H2 / "fb3093_compact_02" / "candidates" /
                            "candidate_register.json").read_text())
        directions = {c["direction"] for c in cands["candidates"]}
        self.assertNotIn("quiet_minimal", directions,
                         "round 2 must NOT carry a quiet-minimal "
                         "candidate — §L; if one appears, the waiver "
                         "test below is no longer exercising the waiver")

    def test_committed_index_matches_regeneration(self):
        """The run-tree index is DERIVED state: the committed JSON must
        equal a fresh regeneration, or a session changed a run tree
        without refreshing the index (the derived-artifact lesson)."""
        committed = json.loads(
            (PALT_H2 / "design_request_index.json").read_text())
        fresh = H2.design_request_index(
            PALT_H2, REPO / "docs" / "roadmap" / "palt_m7" /
            "ai_emission" / "m7_ai_emission_record.json")
        # normalise paths that embed the absolute repo location
        self.assertEqual(json.dumps(committed, sort_keys=True),
                         json.dumps(fresh, sort_keys=True),
                         "design_request_index.json is stale — "
                         "regenerate via design_request_index()")

    def test_docs_shim_delegates_to_this_module(self):
        import importlib.util
        shim_path = PALT_H2 / "h2_pipeline.py"
        spec = importlib.util.spec_from_file_location("h2_shim", shim_path)
        shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shim)
        out = shim.validate_request(PALT_H2 / "es3083_lid_alt_01")
        self.assertEqual(out["verdict"], "PASS")
        self.assertEqual(shim.CANDIDATE_MIN, H2.CANDIDATE_MIN)


class ContractRuleTests(SimpleTestCase):
    """THE_RULE residue + fail-closed refusals, each by its code."""

    def _brief(self, **overrides):
        b = {
            "record_type": "h2_design_request_brief/1.0",
            "request_id": "t", "submitted_by": "t", "submitted_on": "t",
            "product_identity": {"name": "t"},
            "physical_measurements": [
                {"name": "w", "value": 10.0, "unit": "mm",
                 "tier": "MEASURED", "source": "calipers"}],
            "deliverables_wanted": ["x"],
            "brand_constraints": {},
        }
        b.update(overrides)
        return b

    def _write(self, tmp, name, obj):
        p = Path(tmp) / name
        p.write_text(json.dumps(obj))
        return p

    def _codes(self, result):
        return {f["code"] for f in result["findings"]}

    def test_valid_brief_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = H2.validate_brief(self._write(tmp, "b.json", self._brief()))
        self.assertEqual(r["verdict"], "PASS", r)

    def test_prior_measurement_without_url_refuses(self):
        b = self._brief(physical_measurements=[
            {"name": "w", "value": 10.0, "unit": "mm", "tier": "PRIOR",
             "source": "some listing, no link"}])
        with tempfile.TemporaryDirectory() as tmp:
            r = H2.validate_brief(self._write(tmp, "b.json", b))
        self.assertIn("PRIOR_WITHOUT_URL_PROVENANCE", self._codes(r))

    def test_measurement_tier_outside_vocabulary_refuses(self):
        b = self._brief(physical_measurements=[
            {"name": "w", "value": 10.0, "unit": "mm", "tier": "GUESSED",
             "source": "x"}])
        with tempfile.TemporaryDirectory() as tmp:
            r = H2.validate_brief(self._write(tmp, "b.json", b))
        self.assertIn("MEASUREMENT_TIER_INVALID", self._codes(r))

    def test_absent_ledger_is_a_visible_fail(self):
        r = H2.validate_ledger(Path("/nonexistent/ledger.json"))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("LEDGER_ABSENT", self._codes(r))

    def test_empty_ledger_fails_by_the_milestones_own_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, "l.json",
                            {"entries": [], "harvest_executor": "x"})
            r = H2.validate_ledger(p)
        self.assertIn("LEDGER_EMPTY", self._codes(r))

    def test_ledger_without_executor_provenance_refuses(self):
        entry = {"entry_id": "e01", "source_url": "https://x.example/a",
                 "source_kind": "k", "observed": "o",
                 "idea_contributed": "i", "originality_note": "n"}
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(tmp, "l.json", {"entries": [entry]})
            r = H2.validate_ledger(p)
        self.assertIn("HARVEST_EXECUTOR_UNRECORDED", self._codes(r))

    def _request_dir(self, tmp, n_cands=4, direction="quiet_minimal",
                     mandate=None, cite="e01"):
        req = Path(tmp)
        (req / "candidates").mkdir()
        ledger = {"entries": [
            {"entry_id": "e01", "source_url": "https://x.example/a",
             "source_kind": "k", "observed": "o",
             "idea_contributed": "i", "originality_note": "n"}],
            "harvest_executor": "test"}
        (req / "inspiration_ledger.json").write_text(json.dumps(ledger))
        cands = []
        for i in range(n_cands):
            cid = "T%d" % i
            for ext in ("svg", "png"):
                (req / "candidates" / f"{cid}.{ext}").write_text("x")
            cands.append({
                "candidate_id": cid, "title": "t",
                "svg": f"{cid}.svg", "png": f"{cid}.png",
                "inspired_by_ledger_entries": [cite],
                "direction": direction if i == 0 else "other",
                "originality_statement": "s"})
        (req / "candidates" / "candidate_register.json").write_text(
            json.dumps({"candidates": cands}))
        if mandate is not None:
            (req / "round_pointer.json").write_text(
                json.dumps({"mandate": mandate}))
        return req

    def test_candidate_count_bounds_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp, n_cands=3)
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("CANDIDATE_COUNT_OUT_OF_RANGE", self._codes(r))

    def test_candidate_citing_unknown_ledger_entry_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp, cite="e99")
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("CANDIDATE_CITES_UNKNOWN_ENTRY", self._codes(r))

    def test_missing_quiet_minimal_fails_without_mandate(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp, direction="ornate")
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("NO_QUIET_MINIMAL_CANDIDATE", self._codes(r))

    def test_signed_mandate_waives_quiet_minimal_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(
                tmp, direction="ornate",
                mandate="OWNER_BLOCKER_CLEARANCE.md §L verbatim: ...")
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertEqual(r["verdict"], "PASS", r)

    def test_unsigned_mandate_text_does_not_waive(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp, direction="ornate",
                                    mandate="we just felt like it")
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("NO_QUIET_MINIMAL_CANDIDATE", self._codes(r))

    def test_whole_request_gate_fails_on_missing_contact_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp)
            brief = {"record_type": "h2_design_request_brief/1.0",
                     "request_id": "t", "submitted_by": "t",
                     "submitted_on": "t", "product_identity": {},
                     "physical_measurements": [],
                     "deliverables_wanted": ["x"],
                     "brand_constraints": {}}
            (req / "brief.json").write_text(json.dumps(brief))
            out = H2.validate_request(req)
        self.assertEqual(out["verdict"], "FAIL")
        self.assertIn("CONTACT_SHEET_ABSENT",
                      {f["code"] for s in out["stages"]
                       for f in s["findings"]})


class TheArtifactCheckIsAboutFilesNotPaths(SimpleTestCase):
    """§AO. ``validate_candidates`` promises "SVG and PNG both on disk",
    and before this class existed a candidate naming NEITHER passed it.

    The mechanism was not a missing key — that case always fired, and it
    is what the earlier COMPETENT judgment traced. It was the EMPTY
    STRING. ``Path(req) / "candidates" / ""`` yields the candidates
    DIRECTORY, and that directory is guaranteed to be there because
    ``candidate_register.json`` was read out of it twelve lines earlier
    (the function returns FAIL if it was not). So ``.exists()`` had
    collapsed from "is this artwork on disk" into "did we get this far",
    and the answer to the second question is always yes. **The check's own
    precondition was what made it pass.** There is no unlucky input here;
    it was structural.

    Measured before the repair, end to end, on a copy of the real
    ``es3083_lid_alt_01`` register with exactly one field changed::

        BASELINE : PASS
        EMPTY png: PASS | findings: []

    A PASS with an EMPTY findings list, for a candidate with no artwork.

    **THIS DEFECT WAS NOT DISCOVERED HERE.** It is already recorded in
    ``docs/roadmap/palt_m6/enforcement_closure/fallback_class_defects
    .json``, dated 2026-08-17, under the key ``(h2_design_request.py,
    validate_candidates, regex)`` — with a *better* counterexample than
    the one above, because it traces the whole way out: ``request_summary``
    re-reports ``png`` with no existence test, ``validate_request`` ANDs
    the stage verdicts, and the entire request reports PASS. I rediscovered
    it by mutation, which is slower than reading the register would have
    been.

    What this class adds is therefore not the finding. It is that the
    finding is now EXECUTABLE, in the suite, and fails if the repair is
    undone. A defect described in a JSON file that no test reads is a
    defect that survives being known about — which is exactly what
    happened to this one for three days.
    """

    # Reused rather than copied: a second 26-line fixture builder would
    # drift from the first, and the drift would be invisible.
    _request_dir = ContractRuleTests._request_dir
    _codes = ContractRuleTests._codes

    #: Every value that makes the path join degenerate or escape. ``""``
    #: and ``"."`` both resolve to the parent; ``".."`` climbs out of it;
    #: a separator addresses a different directory entirely. Fixing only
    #: the empty string would have been fixing the example.
    NOT_PLAIN_FILENAMES = ("", ".", "..", "sub/x.png", "a\\b.png", "  ")

    def test_a_candidate_naming_no_artwork_is_refused(self):
        for bad in self.NOT_PLAIN_FILENAMES:
            with self.subTest(png=bad), tempfile.TemporaryDirectory() as tmp:
                req = self._request_dir(tmp)
                reg = req / "candidates" / "candidate_register.json"
                d = json.loads(reg.read_text())
                d["candidates"][0]["png"] = bad
                reg.write_text(json.dumps(d))
                r = H2.validate_candidates(
                    req, req / "inspiration_ledger.json")
                self.assertEqual(r["verdict"], "FAIL", r)
                self.assertIn("CANDIDATE_ARTIFACT_NAME_INVALID",
                              self._codes(r), r)

    def test_a_non_string_artwork_value_is_refused(self):
        """A register is JSON, so ``"png"`` can be a number, a list or
        null. ``None`` is the one that mattered: the key is PRESENT, so
        the ``k not in c`` loop is satisfied, and the old code handed
        ``None`` to a path join."""
        for bad in (None, 3, [], {}, True):
            with self.subTest(png=bad), tempfile.TemporaryDirectory() as tmp:
                req = self._request_dir(tmp)
                reg = req / "candidates" / "candidate_register.json"
                d = json.loads(reg.read_text())
                d["candidates"][0]["png"] = bad
                reg.write_text(json.dumps(d))
                r = H2.validate_candidates(
                    req, req / "inspiration_ledger.json")
                self.assertEqual(r["verdict"], "FAIL", r)
                self.assertIn("CANDIDATE_ARTIFACT_NAME_INVALID",
                              self._codes(r), r)

    def test_a_missing_file_is_a_different_finding_from_a_bad_name(self):
        """§AO3(b)'s negative control, and the reason there are two codes.

        A register that names a plausible file which was never rendered is
        a DIFFERENT defect from a register that names nothing — the first
        is a generation step that did not finish, the second is a
        malformed record. Collapsing them into one code is the mistake
        §AN was about, one file over. If this test ever reports
        ``_NAME_INVALID`` the two codes have merged and the distinction
        is gone."""
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp)
            reg = req / "candidates" / "candidate_register.json"
            d = json.loads(reg.read_text())
            d["candidates"][0]["png"] = "never_rendered.png"
            reg.write_text(json.dumps(d))
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertEqual(r["verdict"], "FAIL", r)
        self.assertIn("CANDIDATE_ARTIFACT_ABSENT", self._codes(r), r)
        self.assertNotIn("CANDIDATE_ARTIFACT_NAME_INVALID",
                         self._codes(r), r)

    def test_a_directory_is_not_artwork(self):
        """``is_file()`` rather than ``exists()``, stated as behaviour: a
        candidate pointing at a real directory that really exists must
        still be refused, because a directory is not a drawing."""
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp)
            (req / "candidates" / "T0.png").unlink()
            (req / "candidates" / "T0.png").mkdir()
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertEqual(r["verdict"], "FAIL", r)
        self.assertIn("CANDIDATE_ARTIFACT_ABSENT", self._codes(r), r)

    def test_the_real_committed_registers_are_unaffected(self):
        """§AO4 check 2, kept as a test rather than a one-off probe.

        A repair whose purpose is to reject empty strings must not begin
        rejecting real committed artwork. Measured at the moment of
        writing: 30 svg/png values across the three registers, 0
        violations."""
        for name in H2.KNOWN_REQUEST_DIRS:
            with self.subTest(request=name):
                self.assertEqual(
                    H2.validate_request(PALT_H2 / name)["verdict"],
                    "PASS")

    def test_a_malformed_register_is_named_as_such(self):
        """§AO3(c) line 137. ``register.get("candidates", [])`` failed
        closed with ``0 not in [4,6]`` — the same finding a register that
        genuinely lists zero candidates produces. Right verdict, wrong
        cause, indistinguishable to any reader."""
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp)
            reg = req / "candidates" / "candidate_register.json"
            reg.write_text(json.dumps({"note": "no candidates key"}))
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("CANDIDATE_REGISTER_MALFORMED", self._codes(r), r)

    def test_a_malformed_ledger_does_not_blame_the_candidates(self):
        """§AO3(c) line 143. An ``entries``-less ledger emptied
        ``valid_ids``, so every citation became
        ``CANDIDATE_CITES_UNKNOWN_ENTRY`` — the finding accused the
        CANDIDATES of citing badly when the LEDGER was the broken
        record."""
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp)
            (req / "inspiration_ledger.json").write_text(
                json.dumps({"harvest_executor": "test"}))
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("LEDGER_MALFORMED", self._codes(r), r)

    def test_two_unnamed_candidates_are_told_apart(self):
        """§AO3(c) lines 150/155/160/164. ``"?"`` was the same label for
        every candidate without an id, so two of them produced two
        identical findings and no way to know which was which."""
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp)
            reg = req / "candidates" / "candidate_register.json"
            d = json.loads(reg.read_text())
            for c in d["candidates"][:2]:
                del c["candidate_id"]
            reg.write_text(json.dumps(d))
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        details = [f["detail"] for f in r["findings"]
                   if f["code"] == "CANDIDATE_FIELD_ABSENT"]
        self.assertEqual(
            sorted(details),
            ["register index 0 (no candidate_id) missing candidate_id",
             "register index 1 (no candidate_id) missing candidate_id"],
            details)
        self.assertEqual(len(set(details)), len(details),
                         "two candidates produced identical findings — "
                         "the label is not distinguishing them: %s"
                         % details)


class TheIndexIsWrittenOneWay(SimpleTestCase):
    """§AO. There was no writer for ``design_request_index.json``.

    Every session that regenerated it hand-rolled the ``json.dumps``
    arguments, and this session's first attempt produced a 29-insertion
    diff that was entirely ``—`` turning into ``\\u2014``. Content drift
    and formatting drift are different events, and a reviewer should not
    have to separate them by eye — especially in a file whose whole
    purpose is to show owner decisions.
    """

    def test_the_committed_index_is_byte_identical_to_the_writer(self):
        """Stronger than the ``sort_keys`` comparison next door, which
        compares PARSED structures and so cannot see formatting at all.
        This compares the bytes."""
        expected = json.dumps(
            H2.design_request_index(
                PALT_H2, REPO / "docs" / "roadmap" / "palt_m7" /
                "ai_emission" / "m7_ai_emission_record.json"),
            **H2.INDEX_SERIALISATION) + "\n"
        actual = (PALT_H2 / "design_request_index.json").read_text(
            encoding="utf-8")
        self.assertEqual(actual, expected,
                         "regenerate with "
                         "h2_design_request.write_design_request_index")

    def test_the_committed_index_carries_literal_utf8(self):
        """The named failure, asserted directly: if a future session
        regenerates with the default ``ensure_ascii=True`` this fires,
        and the message says which flag to set."""
        raw = (PALT_H2 / "design_request_index.json").read_text(
            encoding="utf-8")
        self.assertIn("—", raw, "em-dashes have been escaped")
        self.assertNotIn("\\u2014", raw, "ensure_ascii=False")


class TheEmissionRecordHasThreeStatesNotTwo(SimpleTestCase):
    """§AO. ``str(e.get("h2_request") or "").endswith(name)`` — which I
    wrote earlier in THIS sprint while removing fallbacks — collapsed
    "this emission is not H2-sourced" into "this emission is not mine".

    Those look identical from inside the filter and are not the same
    claim. Measured: 3 of the 6 committed emissions carry no
    ``h2_request`` key at all, because they are M7 work with no H2
    lineage. That absence is MEANINGFUL, which is why it is tested for
    by name rather than defaulted to ``""``.

    The same edit also swapped two ``lookup_default`` detector hits for
    one ``or_default`` hit. That is a change in which shape the detector
    sees, not a change in whether the code is honest, and it is the
    second time this sprint I have done it.
    """

    def test_no_record_means_no_emissions_considered(self):
        self.assertEqual(H2._emissions_for(None, "anything"), [])

    def test_an_entry_without_the_key_is_not_h2_sourced(self):
        record = {"emissions": [
            {"ai": "m7_only.ai"},
            {"ai": "mine.ai", "h2_request": "docs/roadmap/palt_h2/req_a"}]}
        got = H2._emissions_for(record, "req_a")
        self.assertEqual([e["ai"] for e in got], ["mine.ai"])

    def test_an_entry_claiming_lineage_without_naming_it_is_refused(self):
        """Present-but-empty is the §AN shape again: the key is there, so
        every presence test is satisfied, and the value says nothing."""
        for bad in ("", "   ", None, 7):
            with self.subTest(h2_request=bad):
                record = {"emissions": [{"ai": "x.ai", "h2_request": bad}]}
                with self.assertRaises(ValueError):
                    H2._emissions_for(record, "req_a")

    def test_a_record_without_an_emissions_list_is_refused(self):
        for bad in ({}, {"emissions": None}, {"emissions": "six"}):
            with self.subTest(record=bad):
                with self.assertRaises(ValueError):
                    H2._emissions_for(bad, "req_a")

    def test_the_real_record_still_partitions_the_same_way(self):
        record = json.loads((REPO / "docs" / "roadmap" / "palt_m7" /
                             "ai_emission" /
                             "m7_ai_emission_record.json").read_text())
        self.assertEqual(len(record["emissions"]), 6)
        self.assertEqual(
            len([e for e in record["emissions"] if "h2_request" not in e]), 3,
            "the 3 non-H2 emissions this class's docstring names")
        self.assertEqual(
            [e["ai"] for e in H2._emissions_for(record, "es3083_lid_alt_01")],
            ["es3083_lid_A2.ai"])

    def test_a_missing_emission_record_path_is_refused_not_emptied(self):
        """A typo in a path would otherwise silently move every accepted
        request back to ``picked_awaiting_finalisation`` — the outcome of
        the whole arc rewritten by a wrong filename."""
        with self.assertRaises(FileNotFoundError):
            H2.design_request_index(PALT_H2, PALT_H2 / "no_such_record.json")


class TheMandateMustBeSignedTextNotAnythingStringifiable(SimpleTestCase):
    """§AP4(2) — and a REVERSAL of §AO3(c).

    §AO3(c) tabled `validate_candidates` line 175 (now 229) as REGISTERED
    COMPETENT, and the reason was written into the source: "a mandate that
    is not text is not a signed citation either", offered as the
    justification for wrapping the lookup in `str()`.

    Running a fresh §AL3(b) refuter against that line one commit later
    refutes it. `str()` does not harden the check, it OPENS it. A mandate
    that is a LIST or a DICT mentioning the clearance file stringifies to
    a representation that CONTAINS the token, so `waived` becomes True and
    the owner requirement is waived by a value that is not a signed
    citation at all. Measured:

        ['OWNER_BLOCKER_CLEARANCE §L complexity'] -> waived=True
        {'cite': 'OWNER_BLOCKER_CLEARANCE'}       -> waived=True

    That is a fail-open ON OWNER AUTHORITY — the one direction the comment
    at the site declares it is not allowed to fail. The registration was
    mine, it was signed, and it was wrong; §AE3(d) says a ruling is
    re-derived and never grandfathered, so it is reversed rather than
    defended. The line is repaired, not registered.
    """

    _request_dir = ContractRuleTests._request_dir
    _codes = ContractRuleTests._codes

    NOT_SIGNED_CITATIONS = (
        ["OWNER_BLOCKER_CLEARANCE.md §L verbatim: ..."],
        {"cite": "OWNER_BLOCKER_CLEARANCE.md §L"},
        {"OWNER_BLOCKER_CLEARANCE": True},
        [["OWNER_BLOCKER_CLEARANCE"]],
        123,
        True,
        None,
    )

    def test_no_non_string_mandate_waives_the_owner_requirement(self):
        for mandate in self.NOT_SIGNED_CITATIONS:
            with self.subTest(mandate=mandate):
                with tempfile.TemporaryDirectory() as tmp:
                    req = self._request_dir(tmp, direction="ornate",
                                            mandate=mandate)
                    r = H2.validate_candidates(
                        req, req / "inspiration_ledger.json")
                self.assertIn("NO_QUIET_MINIMAL_CANDIDATE", self._codes(r),
                              "a %s mandate waived a recorded owner "
                              "requirement" % type(mandate).__name__)

    def test_a_signed_string_mandate_still_waives(self):
        """The repair must not close the door it exists to open."""
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(
                tmp, direction="ornate",
                mandate="OWNER_BLOCKER_CLEARANCE.md §L verbatim: ...")
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertEqual(r["verdict"], "PASS", r)

    def test_an_absent_round_pointer_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = self._request_dir(tmp, direction="ornate")
            self.assertFalse((req / "round_pointer.json").exists())
            r = H2.validate_candidates(req, req / "inspiration_ledger.json")
        self.assertIn("NO_QUIET_MINIMAL_CANDIDATE", self._codes(r))
