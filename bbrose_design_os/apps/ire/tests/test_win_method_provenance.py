"""§AA3 / WI-N — which STAGE supplied a container's print method.

The defect is not a wrong number. It is that a machine's default argument and
a hand-written test fixture produced the SAME provenance string, so a proposal
read as a confirmation and every floor downstream inherited the confusion.
`TestTheTwoRecordsWereIndistinguishable` is that defect, measured.

Two things in here are pinned rather than fixed, and each says so where it
sits: the stages live output never reaches (`TestConstraintsLiveOutputNever
Reaches`), and the fact that the typography axis blocks this surface today
only by coincidence (`TestTheBlockIsCoincidental`). §AA made "a constraint the
pipeline never reaches is a constraint nobody has tested" a standing rule and
required the zero-effect sentence to sit next to the fix, not in a footnote.
These are that sentence, in a form that fails when someone changes it.
"""
import pytest

from apps.ire import back_panel as bp
from apps.ire import container_method_provenance as cmp_
from apps.ire import container_production_method as cpm
from apps.ire import container_text_floor as ctf
from apps.ire import container_typography_metrics as ctm
from apps.ire.compose_container import HERO_SURFACE, TRUE_SCALE_SURFACE_PREFIX
from apps.ire.graph import Color, Document, Group, TextRun
from apps.pipeline.services import container_contract as cc

BLACK = Color.from_hex("#000000")
PROFILE = {"archetype": "bottle", "variant": "cylindrical"}

#: the hand-written record `tests/test_back_panel.py` measures against, copied
#: here in full. It is a FIXTURE and is named one every time its 6.0 is quoted
#: (§AA's rule from WI-K). Nothing in it has been through the builder, which is
#: exactly what makes it useful: it is what an unattributed record looks like.
FIXTURE_METHODS = {"methods": [
    {"method_id": "m_front", "method_type": "ADHESIVE_LABEL",
     "minimum_text_size_pt": 4.0, "target_surfaces": [HERO_SURFACE]},
    {"method_id": "m_back", "method_type": "HOT_STAMP",
     "minimum_text_size_pt": 6.0, "target_surfaces": [bp.SURFACE]}]}


def _live_methods():
    """The record the production path actually builds for this bottle.

    Profile → `propose_zones` → `build_production_methods`, the real chain from
    `apps/pipeline/targets/container/__init__.py`. No argument is passed that
    the pipeline does not pass, because the point of every test below is what
    the pipeline produces when nobody intervenes.
    """
    profile = cc.build_inferred_profile("bottle", "cylindrical")
    return cpm.build_production_methods(cc.propose_zones(profile), profile)


def _method(**over):
    base = {"method_id": "m", "method_type": "SCREEN_PRINT",
            "minimum_text_size_pt": 5.0, "target_surfaces": [bp.SURFACE],
            "authority_state": cpm.INFERRED_NONAUTHORITATIVE,
            "confirmed_by": ""}
    base.update(over)
    return base


def _run(name="product-name-hero", size_pt=8.0, text="BBROSE SERUM"):
    return TextRun(name=name, text=text, x=10.0, y=40.0, font="bold",
                   size_pt=size_pt, color=BLACK)


def _doc(children):
    return Document(page_w=100.0, page_h=120.0, metadata={},
                    root=Group(name="Root", role="artwork", children=children))


class TestTheTwoRecordsWereIndistinguishable:
    """The defect §AA3(a) names, reproduced before it is claimed fixed."""

    def test_a_machine_default_and_a_fixture_gave_the_identical_source(self):
        """The 5.0 traces to a DEFAULT ARGUMENT VALUE in `make_zone`'s
        signature; the 6.0 traces to four keys typed into a test file. The
        floors differ, the method types differ, and the `source` string — the
        only provenance the record carried — is byte-identical."""
        _, live = bp.size_for_surface(_live_methods())
        _, fixture = bp.size_for_surface(FIXTURE_METHODS)

        assert live["source"] == fixture["source"] == bp.SIZE_TABLE
        assert (live["surface_floor_pt"], fixture["surface_floor_pt"]) == (
            5.0, 6.0)
        assert live["method_types"] != fixture["method_types"]

    def test_the_stage_is_what_now_tells_them_apart(self):
        _, live = bp.size_for_surface(_live_methods())
        _, fixture = bp.size_for_surface(FIXTURE_METHODS)

        assert live["method_stages"] == [cmp_.STAGE_MACHINE_PROPOSED]
        assert fixture["method_stages"] == [cmp_.STAGE_UNATTRIBUTED]
        assert live["method_stages"] != fixture["method_stages"]

    def test_neither_of_them_is_confirmed_and_both_say_so(self):
        """Telling them apart is not the same as accepting either. §AA3(a)
        says an owner-confirmed method is NEITHER of these two."""
        for record in (_live_methods(), FIXTURE_METHODS):
            _, source = bp.size_for_surface(record)
            assert source["method_confirmed"] is False
            assert source["size_is_an_assumption"] is True
            assert source["assumption_reason"] == cmp_.ASSUMPTION

    def test_the_defect_was_dropped_information_not_missing_information(self):
        """`build_production_methods` recorded the authority all along;
        `surface_floors` copied four keys and discarded it, at exactly the
        boundary where the floor is decided. The fix is to stop dropping it."""
        live = _live_methods()
        assert all("authority_state" in m for m in live["methods"])
        floors = ctf.surface_floors(live)
        assert floors[bp.SURFACE]["method_stages"] == [
            cmp_.STAGE_MACHINE_PROPOSED]


class TestTheStages:
    """§AA3(a)'s three-way, plus the two states the records can actually be
    in that it does not name."""

    def test_the_builders_own_state_is_a_proposal(self):
        assert cmp_.method_stage(_method()) == cmp_.STAGE_MACHINE_PROPOSED

    def test_a_record_with_no_authority_state_is_unattributed(self):
        """Not `FIXTURE`. What is detectable is the ABSENCE of the builder's
        signature, which is a weaker claim than "a test wrote this" — and the
        weaker claim is the one that stays true if a second producer appears."""
        assert cmp_.method_stage(
            {"method_id": "m", "method_type": "HOT_STAMP"}
        ) == cmp_.STAGE_UNATTRIBUTED

    def test_verified_manufacturer_capability_is_the_confirmation(self):
        stage = cmp_.method_stage(
            _method(authority_state=cpm.VERIFIED_MANUFACTURER_CAPABILITY))
        assert stage == cmp_.STAGE_OWNER_CONFIRMED
        assert cmp_.is_confirmed(stage) is True

    def test_design_intent_is_its_own_stage_not_rounded_to_the_nearest(self):
        """An owner asking for hot foil is not `propose_zones` guessing and is
        not a fixture. Whether it CONFIRMS the method is an owner ruling; it
        gets its own name so the ruling has something to attach to."""
        stage = cmp_.method_stage(
            _method(authority_state=cpm.USER_REQUESTED_UNVERIFIED))
        assert stage == cmp_.STAGE_USER_REQUESTED
        assert cmp_.is_confirmed(stage) is False

    def test_a_named_confirmer_is_not_masked_by_the_authority_it_travels_with(
            self):
        """`confirmed_by` is checked BEFORE the unverified states. A human who
        put their name to a method must not be overridden by the field the
        builder left behind."""
        assert cmp_.method_stage(_method(confirmed_by="BBrose")) == (
            cmp_.STAGE_OWNER_CONFIRMED)
        assert cmp_.method_stage(
            _method(authority_state=cpm.USER_REQUESTED_UNVERIFIED,
                    confirmed_by="BBrose")) == cmp_.STAGE_OWNER_CONFIRMED

    def test_whitespace_is_not_a_confirmation(self):
        assert cmp_.method_stage(_method(confirmed_by="   ")) == (
            cmp_.STAGE_MACHINE_PROPOSED)

    def test_an_unrecognised_authority_state_is_unattributed_not_proposed(self):
        """A stage nobody recognises is unattributed. Folding it into
        MACHINE_PROPOSED would be inventing an attribution for a record that
        does not have one."""
        assert cmp_.method_stage(_method(authority_state="SOMETHING_NEW")) == (
            cmp_.STAGE_UNATTRIBUTED)

    @pytest.mark.parametrize("junk", [None, "SCREEN_PRINT", 5.0, []])
    def test_a_non_record_is_unattributed(self, junk):
        assert cmp_.method_stage(junk) == cmp_.STAGE_UNATTRIBUTED

    def test_exactly_one_stage_is_a_confirmation(self):
        assert cmp_.CONFIRMED_STAGES == {cmp_.STAGE_OWNER_CONFIRMED}
        for stage in (cmp_.STAGE_USER_REQUESTED, cmp_.STAGE_MACHINE_PROPOSED,
                      cmp_.STAGE_UNATTRIBUTED, cmp_.STAGE_UNSUPPORTED):
            assert cmp_.is_confirmed(stage) is False


class TestConstraintsLiveOutputNeverReaches:
    """§AA's WI-K precedent, applied to WI-N's own work: where a branch's
    effect on production output is zero, that is stated NEXT TO the branch.

    Both of these are pinned as facts about the repo as it stands, not as
    approval of them. If a confirmation flow is ever built, these fail and the
    failure is the notification that the world changed.
    """

    def test_no_production_path_marks_a_zone_as_an_explicit_user_fact(self):
        """So `USER_REQUESTED` exists, is tested above, and has never run on a
        real container."""
        zones = cc.propose_zones(cc.build_inferred_profile("bottle",
                                                           "cylindrical"))
        assert zones
        assert {z.get("source") for z in zones} == {cc.SRC_INFERRED}
        assert cc.SRC_INFERRED != "EXPLICIT_USER_FACT"

    def test_the_builder_leaves_the_confirmer_blank_by_construction(self):
        live = _live_methods()
        assert live["methods"]
        assert {m.get("confirmed_by") for m in live["methods"]} == {""}
        assert cpm.VERIFIED_MANUFACTURER_CAPABILITY not in {
            m.get("authority_state") for m in live["methods"]}

    def test_every_method_on_a_live_container_is_machine_proposed(self):
        """The headline. This module's answer for live output is known in
        advance — which is why it is recorded, so the next reader does not have
        to rediscover it."""
        record = cmp_.measure_method_provenance(_live_methods())
        assert record["all_confirmed"] is False
        assert record["any_unconfirmed"] is True
        assert record["codes"] == [cmp_.METHOD_UNCONFIRMED]
        stages = {s for e in record["by_surface"].values() for s in e["stages"]}
        assert stages == {cmp_.STAGE_MACHINE_PROPOSED}

    def test_the_back_face_technique_is_a_default_argument_value(self):
        """Named exactly, because §AA3(e) forbids fixing it here and a reader
        who cannot find WHERE the guess came from will fix it anyway."""
        zones = cc.propose_zones(cc.build_inferred_profile("bottle",
                                                           "cylindrical"))
        back = [z for z in zones if cc.zone_surface(z) == bp.SURFACE]
        assert back, "the bottle proposal no longer has a BODY_BACK zone"
        assert all(z["permitted_techniques"] == ["screen_printing"]
                   or tuple(z["permitted_techniques"]) == ("screen_printing",)
                   for z in back)
        assert cpm.method_type_for(back[0]) == "SCREEN_PRINT"


class TestTheSurfaceIsOnlyAsConfirmedAsItsLeastConfirmedMethod:

    def test_one_unconfirmed_method_makes_the_surface_unconfirmed(self):
        record = {"methods": [
            _method(method_id="a", minimum_text_size_pt=6.0,
                    authority_state=cpm.VERIFIED_MANUFACTURER_CAPABILITY),
            _method(method_id="b", minimum_text_size_pt=6.0)]}
        prov = cmp_.surface_provenance(record)
        assert prov[bp.SURFACE]["confirmed"] is False
        assert prov[bp.SURFACE]["stages"] == [cmp_.STAGE_MACHINE_PROPOSED,
                                              cmp_.STAGE_OWNER_CONFIRMED]
        assert cmp_.unconfirmed_surfaces(prov) == [bp.SURFACE]

    def test_a_surface_whose_methods_are_all_confirmed_is_confirmed(self):
        record = {"methods": [_method(
            authority_state=cpm.VERIFIED_MANUFACTURER_CAPABILITY)]}
        prov = cmp_.surface_provenance(record)
        assert prov[bp.SURFACE]["confirmed"] is True
        assert cmp_.unconfirmed_surfaces(prov) == []

    def test_a_surface_with_no_recorded_method_does_not_appear(self):
        """Not an oversight. §W2(b) already ruled that case and the record
        already says the word FALLBACK; a second disclosure saying the fallback
        is unconfirmed adds a word without adding a fact."""
        assert cmp_.surface_provenance({"methods": []}) == {}
        assert cmp_.measure_method_provenance(None)["surfaces_examined"] == []

    def test_nothing_recorded_is_not_reported_as_all_confirmed(self):
        empty = cmp_.measure_method_provenance({"methods": []})
        assert empty["all_confirmed"] is False
        assert empty["any_unconfirmed"] is False


class TestTheDisclosureTravelsWithTheNumber:
    """§AA3(c). A reader looking at one run must not have to go elsewhere to
    learn that its floor is an assumption."""

    def test_every_run_carries_its_own_stage(self):
        doc = _doc([_run()])
        record = ctf.measure_text_floor(
            doc, cpm.build_production_methods(
                [{"zone_id": "Z", "parent_surface": HERO_SURFACE,
                  "x_mm": 4.0, "y_mm": 20.0, "width_mm": 30.0,
                  "height_mm": 45.0,
                  "permitted_techniques": ["screen_printing"]}], PROFILE))
        assert [r["method_confirmed"] for r in record["runs"]] == [False]
        assert [r["method_stages"] for r in record["runs"]] == [
            [cmp_.STAGE_MACHINE_PROPOSED]]
        assert record["unconfirmed_method_surfaces"] == [HERO_SURFACE]

    def test_a_fallback_run_says_none_not_false(self):
        """There is no method on that surface to be unconfirmed. False would
        assert one exists and nobody confirmed it — a claim about a method that
        is not there. `floor_source` already says FALLBACK."""
        record = ctf.measure_text_floor(_doc([_run()]), None)
        assert [r["method_confirmed"] for r in record["runs"]] == [None]
        assert [r["method_stages"] for r in record["runs"]] == [[]]
        assert record["unconfirmed_method_surfaces"] == []
        assert record["any_floor_is_a_fallback"] is True

    def test_the_axis_reports_the_surfaces_it_is_judging_on_an_assumption(self):
        doc = _doc([_run()])
        record = ctm.measure_typography_metrics(doc, _live_methods())
        assert record["size_floor_unconfirmed_method_surfaces"] == [
            HERO_SURFACE]
        assert record["method_provenance_by_surface"][HERO_SURFACE] == {
            "confirmed": False, "stages": [cmp_.STAGE_MACHINE_PROPOSED]}

    def test_an_explicit_caller_size_is_not_dressed_up_as_a_method(self):
        """A caller that names a size has already decided. There is no method
        behind that number, so there is nothing to be unconfirmed and nothing
        to call an assumption."""
        _, source = bp.size_for_surface(_live_methods(), size_pt=7.0)
        assert source["source"] == bp.SIZE_CALLER
        assert source["method_confirmed"] is None
        assert source["size_is_an_assumption"] is False
        assert source["assumption_reason"] is None


class TestTheBlockIsCoincidental:
    """WI-N's finding, pinned so it is an artefact rather than a paragraph.

    §AA3(b) says the axis stays blocking. It does — and NOT because of the
    unconfirmed method. It blocks because runs sit below their floors:
    `below_floor` returns True by its first branch, and when that branch stops
    firing the verdict is False and the axis PASSES on a technique that
    entered the system as a default argument value.

    `test_on_the_real_sheet_the_block_is_mostly_sheet_furniture` measures WHICH
    runs those are, because the answer is not the one this class first
    assumed — see `below_floor`'s docstring for the full count.

    The obvious remedy — a None branch for an unconfirmed method — was built,
    measured, and reverted: `OWNER_CONFIRMED` is unreachable by construction,
    so it makes FALSE unreachable for EVERY container forever, repealing §W2's
    PASS branch including the 2.0 pt bottom inkjet code §W2 names as a FALSE
    FAIL. That is an owner ruling. These tests pin today's behaviour so the
    day it is ruled on, they fail and say what changed.
    """

    def _record(self, size_pt):
        return ctf.measure_text_floor(
            _doc([_run(size_pt=size_pt)]),
            cpm.build_production_methods(
                [{"zone_id": "Z", "parent_surface": HERO_SURFACE,
                  "x_mm": 4.0, "y_mm": 20.0, "width_mm": 30.0,
                  "height_mm": 45.0,
                  "permitted_techniques": ["screen_printing"]}], PROFILE))

    def test_it_blocks_today_because_a_run_is_under_its_floor(self):
        record = self._record(3.0)
        assert record["unconfirmed_method_surfaces"] == [HERO_SURFACE]
        assert ctf.below_floor(record) is True
        assert [r["node_name"] for r in record["below_floor"]] == [
            "product-name-hero"]

    def test_the_day_the_copy_clears_it_passes_on_an_unconfirmed_method(self):
        """The finding itself. Same unconfirmed surface, one number changed,
        and the verdict is a universal claim of legibility."""
        record = self._record(9.0)
        assert record["unconfirmed_method_surfaces"] == [HERO_SURFACE]
        assert record["below_floor"] == []
        assert ctf.below_floor(record) is False

    def test_the_axis_emits_the_flag_rather_than_going_unmeasured(self):
        """Stated at the gate's own boundary, not just the floor module's:
        `below_size_floor` is PRESENT and False, so the axis measures."""
        doc = _doc([_run(size_pt=9.0)])
        record = ctm.measure_typography_metrics(doc, _live_methods())
        assert record["below_size_floor"] is False
        assert record["size_floor_unconfirmed_method_surfaces"] == [
            HERO_SURFACE]

    def test_the_two_pt_bottom_code_is_why_the_none_branch_was_reverted(self):
        """§W2's headline FALSE FAIL, re-asserted from WI-N's side. A bottom
        inkjet code at 2.0 pt is standard practice and passes — on a method no
        stage confirmed, because there is no other kind."""
        zone = {"zone_id": "CODE", "parent_surface": HERO_SURFACE,
                "zone_type": "BOTTOM_CODE_ZONE", "x_mm": 4.0, "y_mm": 20.0,
                "width_mm": 30.0, "height_mm": 45.0,
                "permitted_techniques": ["screen_printing"]}
        record = ctf.measure_text_floor(
            _doc([_run(name="code-batch", size_pt=2.0, text="L2408A")]),
            cpm.build_production_methods([zone], PROFILE))
        assert [r["floor_pt"] for r in record["runs"]] == [2.0]
        assert record["unconfirmed_method_surfaces"] == [HERO_SURFACE]
        assert ctf.below_floor(record) is False

    def test_on_the_real_sheet_the_block_is_mostly_sheet_furniture(self):
        """The correction to this class's own first claim.

        I wrote that WI-O clearing `front-support`/`front-net-content` would
        flip the verdict. Measured on the emitted sheet it would not: 9 of the
        13 failing runs are the sheet's own annotations, measured as printed
        type because `NON_ARTWORK_TEXT_PREFIXES` does not cover `panel-label-`,
        `confirmed-dims` or `census-line`. Recorded, not fixed — widening that
        tuple changes which runs the gate sees, and §AA4 forbids chained fixes.
        """
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.container_motif_fidelity import NON_ARTWORK_TEXT_PREFIXES
        from apps.ire.tests.test_back_panel import (_BACK_ZONE, _FRONT_ZONE,
                                                    _GEOMETRY, _LIVE)

        live = _live_methods()
        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name="Rose Damascena", sku="X",
            back_sections=_LIVE, revision_status="TEST", methods_record=live)
        record = ctf.measure_text_floor(doc, live)

        # §BH50(f)(1): the owner ruled the nine annotations out of §W2's
        # scope. They leave the judged set and are LISTED with their sizes;
        # no printed run is below its floor; and the verdict is None — not
        # False — because the bottom code is drawn only in the bottom diagram
        # and BOTTOM is named not measured. This test asserted `is True` on
        # nine annotations until the ruling: the block was sheet furniture.
        assert ctf.below_floor(record) is None
        assert record["below_floor"] == []
        listed = [a["node_name"] for a in record["out_of_scope_annotations"]]
        furniture = [n for n in listed
                     if n.startswith(("panel-label-", "confirmed-dims",
                                      "census-line"))]
        # eleven, not the nine that failed the floor at HEAD: the same nine,
        # every one under 5.0 pt, plus the two captions the strip and the
        # bottom diagram carry — HEAD dropped those two silently with the
        # strip (§W1(c)); the scope declaration lists them as what they are.
        # Measured HEAD-versus-tree on this composition before the re-pin.
        assert len(furniture) == 11
        # §BH54(g): the caption DRAWS the composition's own back zone — "(22×42.3)" here, no longer the literal
        # "(22×36)" — and the node's name is the panel's identity, without a size
        drawn = {str(n.name): n.text for n, _ in doc.walk() if str(getattr(n, "name", "")).startswith("panel-label-9a")}
        assert drawn == {"panel-label-9a · BACK PRINT": "9a · BACK PRINT (22×42.3)"}
        assert {"panel-label-9a · BACK PRINT",
                "panel-label-9b · BOTTOM CODE (14×5)"} <= set(furniture)
        assert all(a["size_pt"] < 5.0
                   for a in record["out_of_scope_annotations"]
                   if a["node_name"] in furniture)
        assert not any(r["node_name"] in furniture for r in record["runs"])
        assert [s["surface"] for s in record["surfaces_not_measured"]] == ["BOTTOM"]
        assert record["scope_undeclared_runs"] == []
        # the prefix set still does not cover them; it no longer has to
        assert not any(n.startswith(NON_ARTWORK_TEXT_PREFIXES)
                       for n in furniture)

    def test_the_note_does_not_claim_a_block_it_does_not_cause(self):
        """A constant asserting a block that does not happen is the same
        defect as a fallback presenting as a measurement."""
        # §BH50(f)(1): the note used to say the axis "does block today, but on
        # runs found below their floors" — false once the annotations left
        # scope; it now names what the verdict rests on
        assert "does not rest on this" in cmp_.UNCONFIRMED_NOTE
        assert "§BH50(f)(1)" in cmp_.UNCONFIRMED_NOTE
        assert "owner ruling" in cmp_.UNCONFIRMED_NOTE


class TestTheReasonStringReportsBothOrIsNotEmitted:
    """The two clauses of `unresolved_reason`, and the reason it takes two
    SURFACES to see both.

    An ambiguous surface's runs are skipped, never measured, so that surface
    can never appear in `unconfirmed_method_surfaces` — the two clauses are
    structurally about different surfaces and cannot both describe one. That is
    not a defect in the reason string; it is why the string needs both clauses
    at all, and why they are joined by ALSO rather than by "and".
    """

    def _record(self):
        """HERO ambiguous, BODY_BACK unconfirmed, both carrying a run.

        The back run is wrapped in a `TrueScaleSurface-*` group, which is how
        §W1's full-scale panel reaches the per-surface floor: it is the printed
        surface, so it is container view and carries its own surface name
        instead of falling through to the hero.
        """
        back = Group(name=TRUE_SCALE_SURFACE_PREFIX + bp.SURFACE,
                     role="artwork",
                     children=[_run(name="back-panel-body", size_pt=8.0)])
        doc = _doc([_run(), back])
        return ctf.measure_text_floor(doc, {"methods": [
            _method(method_id="a", method_type="SCREEN_PRINT",
                    minimum_text_size_pt=5.0, target_surfaces=[HERO_SURFACE]),
            _method(method_id="b", method_type="HOT_STAMP",
                    minimum_text_size_pt=6.0, target_surfaces=[HERO_SURFACE]),
            _method(method_id="c", method_type="SCREEN_PRINT",
                    minimum_text_size_pt=5.0, target_surfaces=[bp.SURFACE])]})

    def test_the_two_clauses_describe_two_different_surfaces(self):
        record = self._record()
        assert record["ambiguous_surfaces"] == [HERO_SURFACE]
        assert record["unconfirmed_method_surfaces"] == [bp.SURFACE]
        assert ctf.below_floor(record) is None

    def test_ambiguity_is_the_cause_and_the_stage_rides_along_after_it(self):
        reason = ctf.unresolved_reason(self._record())
        assert reason.startswith(ctf._AMBIGUOUS_REASON)
        assert "  ALSO: " in reason
        assert cmp_.UNCONFIRMED_NOTE in reason
        assert cmp_.STAGE_MACHINE_PROPOSED in reason

    def test_the_two_never_read_as_one_finding(self):
        cause, _, disclosure = ctf.unresolved_reason(self._record()).partition(
            "  ALSO: ")
        assert HERO_SURFACE in cause and bp.SURFACE not in cause
        assert disclosure.startswith(cmp_.UNCONFIRMED_NOTE)
        assert bp.SURFACE in disclosure

    def test_the_cause_is_never_displaced_by_the_disclosure(self):
        """A reason string that led with the disclosure would answer a question
        the reader did not ask and bury the one they did."""
        reason = ctf.unresolved_reason(self._record())
        assert reason.index(ctf._AMBIGUOUS_REASON) < reason.index(
            cmp_.UNCONFIRMED_NOTE)
