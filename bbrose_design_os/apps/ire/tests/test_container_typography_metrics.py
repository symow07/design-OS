"""VQR-4 — the typography axis PASSED on fields nobody measured.

This is the worst of the four gate-read contracts, and not because it had no
producer. ``_typography_axis`` read its three defect flags with ``.get()``,
so an ABSENT flag arrived as False. A record carrying nothing but
``min_text_pt: 8.0`` therefore reached PASS, the axis asserting "not
clipped, not overlapping, no placeholder" about three things no one had
looked at. The same defaulting failed the other way too: a record with the
flags but no ``min_text_pt`` read 0 and FAILED on an invented number.

Both halves are fixed here — the gate now requires PRESENCE, and this
producer supplied the two fields that are facts about the emitted document
while OMITTING the two that were design policy:

* ``materially_overlapping`` — the same shape as ``blocking_overlaps``, and
  §W3 confirmed it was literally the same question, ruling both at once.
* ``placeholder_text_present`` — two committed definitions in this repo
  disagree ("N/A" is placeholder to one and copy to the other), and both
  were written for spec field values, not for type drawn on a container.

BOTH have since been ruled — §W5 and §W3 — and both are now measured. The
tests that pinned them absent were right when written and are now wrong, and
the reason they moved is an owner ruling through OWNER_BLOCKER_CLEARANCE.md,
never a session that wanted a green axis. What they guarded survives: each
field still goes absent, and the axis still blocks, on the case its ruling
does not reach.

These tests exist mostly to stop a future session "finishing" the record.
"""
from apps.ire import container_typography_metrics as ctm
from apps.ire.graph import Color, Document, Group, TextRun

BLACK = Color.from_hex("#000000")
PAGE_W = 100.0
PAGE_H = 120.0


def _doc(children, page_w=PAGE_W, page_h=PAGE_H, metadata=None):
    return Document(page_w=page_w, page_h=page_h, metadata=metadata or {},
                    root=Group(name="Root", role="artwork", children=children))


def _name_run(x=10.0, y=40.0, text="BBROSE SERUM", size_pt=12.0,
              name="product-name-hero"):
    return TextRun(name=name, text=text, x=x, y=y, font="bold",
                   size_pt=size_pt, color=BLACK)


def _oblique_run(x=10.0, y=80.0, text="POLVO HORNEADO"):
    """A run set at an angle §W3(d) leaves UNMEASURED — ``_text_bbox_mm``
    returns the UNROTATED box off-axis, so its geometry is not available and
    neither an intersection nor its absence can be read off it."""
    return TextRun(name="product-name-vertical", text=text, x=x, y=y,
                   font="bold", size_pt=9.0, color=BLACK, rotation_deg=30.0)


class TestTheUnmeasurableFieldsAreAbsentNotFalse:
    """The single most important property in this module.

    BOTH fields left this class in sprint 8, and the reason matters: §W5 and
    §W3 supplied the rulings they were waiting on. Neither became measurable
    because a later session got tired of an UNMEASURED axis.

    The property survives the rulings rather than being retired by them, so
    the class keeps its name: a field whose ruling does not reach the document
    in hand is still ABSENT, not False.
    """

    def test_the_ruled_fields_are_now_in_the_record(self):
        record = ctm.measure_typography_metrics(_doc([_name_run()]))
        assert record is not None
        assert record["materially_overlapping"] is False
        # §BH50(f)(2): placeholder copy is its own blocker; the typography
        # record publishes no placeholder field at all
        assert "placeholder_text_present" not in record
        assert not any(k.startswith("placeholder_") for k in record)
        assert record["unmeasured"] == []

    def test_a_field_the_ruling_cannot_reach_is_still_absent(self):
        """§W3(d). The rule asks whether the geometry intersects; for an
        obliquely rotated run this repo has no geometry to ask about."""
        record = ctm.measure_typography_metrics(
            _doc([_name_run(), _oblique_run()]))
        assert "materially_overlapping" not in record, (
            "a flag was supplied for a run whose extent is not available")
        assert record["unmeasured"] == ["materially_overlapping"]
        for field in record["unmeasured"]:
            assert record["unmeasured_reasons"][field]

    def test_the_gate_axis_stays_unmeasured_on_that_document(self):
        """A document the rule cannot fully read must NOT reach PASS. If it
        does, the producer has answered a question it was not asked."""
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ctm.measure_typography_metrics(
            _doc([_name_run(), _oblique_run()]))
        assert record["clipped"] is False
        # §W2 moved the size verdict to the producer, so this pins that the
        # UNMEASURED below is the absent overlap field and not the size.
        assert record["below_size_floor"] is False
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.UNMEASURED
        assert axis["code"] == vqg.VQ_TYPOGRAPHY_METRICS_UNMEASURED

    def test_a_record_that_did_supply_the_field_would_pass(self):
        """The guard above is only meaningful if the axis COULD pass — this
        pins that the record is one field away, so the test above is
        detecting the absent field and not some unrelated refusal."""
        from apps.pipeline.services import visual_quality_gate as vqg
        record = dict(ctm.measure_typography_metrics(
            _doc([_name_run(), _oblique_run()])))
        record["materially_overlapping"] = False
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.PASS


class TestTheGateNoLongerPassesOnAbsentFlags:
    """The defect this work item exists for, pinned directly on the axis so
    it cannot come back through a different producer."""

    def _axis(self, metrics):
        from apps.pipeline.services import visual_quality_gate as vqg
        return vqg._typography_axis(
            {"container_typography_metrics/1.0": metrics},
            {"primitives": {"live_text": 3}})

    def test_a_size_only_record_no_longer_passes(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"min_text_pt": 8.0})
        assert axis["state"] == vqg.UNMEASURED
        assert axis["code"] == vqg.VQ_TYPOGRAPHY_METRICS_UNMEASURED

    def test_an_absent_size_no_longer_fails_on_an_invented_zero(self):
        """The mirror defect. ``min_text_pt`` defaulted to 0, which is below
        every legibility floor, so a record that never measured size FAILED
        as though it had measured 0 pt type."""
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"clipped": False, "materially_overlapping": False,
                           "placeholder_text_present": False})
        assert axis["state"] == vqg.UNMEASURED
        assert "min_text_pt" not in axis["measured"]

    def test_the_incomplete_axis_says_which_fields_were_missing(self):
        axis = self._axis({"min_text_pt": 8.0, "clipped": False})
        for field in ("materially_overlapping", "below_size_floor"):
            assert field in axis["reason"]
        assert "placeholder_text_present" not in axis["reason"]   # §BH50(f)(2)

    def test_the_incomplete_axis_still_reports_what_it_was_given(self):
        """An UNMEASURED axis that drops the fields it DID receive is a
        diagnostic reporting less than it found."""
        axis = self._axis({"min_text_pt": 8.0, "clipped": False,
                           "unmeasured": ["materially_overlapping"]})
        assert axis["measured"]["min_text_pt"] == 8.0
        assert axis["measured"]["clipped"] is False
        assert axis["measured"]["live_text_runs"] == 3
        assert axis["measured"]["unmeasured"] == ["materially_overlapping"]

    def test_a_measured_defect_still_fails_on_an_incomplete_record(self):
        """FAIL and UNMEASURED both block, but they say different things. A
        defect that WAS measured stays a finding — an unmeasured neighbour
        does not un-see it."""
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"below_size_floor": True, "clipped": False})
        assert axis["state"] == vqg.FAIL
        assert axis["code"] == vqg.VQ_TYPOGRAPHY_DEFECTIVE
        axis = self._axis({"clipped": True})
        assert axis["state"] == vqg.FAIL

    def test_a_small_number_is_no_longer_a_defect_by_itself(self):
        """§W2. This assertion used to read FAIL: 3.0 pt was below the gate's
        flat floor. The gate no longer owns that number, so a size with no
        print method behind it is an incomplete record, not a finding — the
        2.0 pt bottom code the old rule condemned is why."""
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"min_text_pt": 3.0, "clipped": False})
        assert axis["state"] == vqg.UNMEASURED
        assert "below_size_floor" in axis["reason"]

    def test_an_explicit_null_is_not_a_measurement(self):
        """A record may carry the key with no value. That is the field not
        measured, not the field measured False."""
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"min_text_pt": 8.0, "clipped": None,
                           "materially_overlapping": False,
                           "placeholder_text_present": False})
        assert axis["state"] == vqg.UNMEASURED
        assert "clipped" in axis["reason"]

    def test_a_complete_record_still_passes(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"min_text_pt": 8.0, "clipped": False,
                           "materially_overlapping": False,
                           "below_size_floor": False,
                           "placeholder_text_present": False})
        assert axis["state"] == vqg.PASS


class TestTheSmallestTypeIsMeasuredNotAssumed:

    def test_the_minimum_is_the_smallest_artwork_run(self):
        record = ctm.measure_typography_metrics(_doc([
            _name_run(size_pt=12.0),
            _name_run(y=60.0, size_pt=6.5, name="claim-line"),
            _name_run(y=70.0, size_pt=9.0, name="subhead")]))
        assert record["min_text_pt"] == 6.5
        assert record["container_view_text_runs"] == 3
        assert [e["node_name"] for e in record["smallest_runs"]] == \
            ["claim-line"]

    def test_no_legibility_floor_is_applied_here(self):
        """Three different minimum-size constants live in this codebase. The
        producer reports the number and the gate adjudicates it; choosing
        between the constants here would be a policy wearing a
        measurement's name."""
        record = ctm.measure_typography_metrics(
            _doc([_name_run(size_pt=2.0)]))
        assert record["min_text_pt"] == 2.0
        assert "pass" not in record and "legible" not in record

    def test_sheet_furniture_is_not_container_copy(self):
        """A 4 pt swatch caption is type on the presentation sheet. Failing
        the container's legibility on it would be a finding about the wrong
        artifact — and the exclusion set is the one the hierarchy validator
        already uses, not a second list."""
        record = ctm.measure_typography_metrics(_doc([
            _name_run(size_pt=12.0),
            TextRun(name="sku", text="ES3083", x=5.0, y=115.0,
                    font="regular", size_pt=4.0, color=BLACK)]))
        assert record["min_text_pt"] == 12.0
        assert record["container_view_text_runs"] == 1

    def test_a_document_of_only_sheet_furniture_yields_no_record(self):
        """Mirrors the logo and composition producers: nothing to measure
        means no record, never a record of confident zeros."""
        sku = TextRun(name="sku", text="ES3083", x=5.0, y=115.0,
                      font="regular", size_pt=6.0, color=BLACK)
        assert ctm.measure_typography_metrics(_doc([sku])) is None
        assert ctm.measure_typography_metrics(_doc([])) is None


class TestClippingIsPageBoundsAndSaysSo:

    def test_a_run_inside_the_page_is_not_clipped(self):
        record = ctm.measure_typography_metrics(_doc([_name_run()]))
        assert record["clipped"] is False
        assert record["clipped_runs"] == []

    def test_a_run_off_the_page_is_clipped_and_named(self):
        record = ctm.measure_typography_metrics(
            _doc([_name_run(x=PAGE_W - 2.0)]))
        assert record["clipped"] is True
        entry = record["clipped_runs"][0]
        assert entry["node_name"] == "product-name-hero"
        assert entry["box_mm"][0] == PAGE_W - 2.0

    def test_a_negative_coordinate_is_clipped_too(self):
        record = ctm.measure_typography_metrics(_doc([_name_run(x=-1.0)]))
        assert record["clipped"] is True

    def test_clipping_is_judged_by_the_measured_extent(self):
        """Derived, not asserted: the run is anchored so the char-count guess
        and the real advance width disagree about whether it leaves the page.
        A producer that fell back to the guess fails here."""
        from apps.dielines.exporters.counter_display_files import _resolve_fonts
        from apps.ire import text_metrics as tm
        _, bold = _resolve_fonts()
        text, size_pt = "BBROSE SERUM", 12.0
        size_mm = size_pt / 2.835
        measured = tm.text_width_mm_measured(text, size_mm, bold)
        guess = len(text) * size_mm * tm._FALLBACK_ADVANCE_EM
        assert measured is not None
        assert abs(measured - guess) > 0.5, (
            "this face's advance and the guess agree too closely for the "
            "placement below to distinguish them")
        x = PAGE_W - (measured + guess) / 2.0
        record = ctm.measure_typography_metrics(
            _doc([_name_run(x=x, text=text, size_pt=size_pt)]))
        assert record["clipped"] is (x + measured > PAGE_W)

    def test_a_run_cut_by_an_ancestor_clip_path_is_clipped(self):
        """The correction the real emitted document forced. A TextRun has no
        ``clip`` of its own, and the first version of this module concluded
        from that that page bounds was the whole test — but ``Group`` DOES
        carry one, and the emitter puts a real clip on ``BACK_DIRECT_PRINT``.
        A page-bounds-only producer calls this run unclipped."""
        from apps.ire.nodes import rect_clip
        run = _name_run(x=10.0, y=40.0, name="claim-line")
        boxed = Group(name="BACK_DIRECT_PRINT", role="decoration",
                      children=[run], clip=rect_clip(10.0, 40.0, 4.0, 4.0))
        record = ctm.measure_typography_metrics(_doc([boxed]))
        assert record["clipped"] is True
        assert record["clipped_runs"][0]["clip_findings"] == \
            ["clip_path:BACK_DIRECT_PRINT"]

    def test_a_clip_path_that_contains_the_run_does_not_clip_it(self):
        """A clip is not a defect — a clip that CUTS is. Without this the
        test above would pass on any clip at all."""
        from apps.ire.nodes import rect_clip
        run = _name_run(x=10.0, y=40.0, name="claim-line")
        boxed = Group(name="BACK_DIRECT_PRINT", role="decoration",
                      children=[run], clip=rect_clip(0.0, 0.0, 90.0, 90.0))
        record = ctm.measure_typography_metrics(_doc([boxed]))
        assert record["clipped"] is False

    def test_a_clip_two_groups_up_is_still_found(self):
        from apps.ire.nodes import rect_clip
        run = _name_run(x=10.0, y=40.0, name="claim-line")
        inner = Group(name="BACK_DIRECT_PRINT", role="decoration",
                      children=[run])
        outer = Group(name="Panel", role="decoration", children=[inner],
                      clip=rect_clip(10.0, 40.0, 4.0, 4.0))
        record = ctm.measure_typography_metrics(_doc([outer]))
        assert record["clipped_runs"][0]["clip_findings"] == \
            ["clip_path:Panel"]

    def test_the_record_states_what_clipping_means_here(self):
        record = ctm.measure_typography_metrics(_doc([_name_run()]))
        assert "page bounds" in record["clip_definition"]
        assert "ancestor clip path" in record["clip_definition"]
        assert not hasattr(_name_run(), "clip"), (
            "a TextRun gained its own clip — the ancestor walk is no longer "
            "the whole of the clip test")

    def test_every_reported_run_states_how_its_extent_was_obtained(self):
        record = ctm.measure_typography_metrics(
            _doc([_name_run(x=PAGE_W - 2.0)]))
        for entry in record["clipped_runs"] + record["smallest_runs"]:
            assert entry["extent_source"] in ("measured_text",
                                              "estimated_text")


class TestTheSurfaceStripIsADiagramNotTheContainer:
    """The correction the real emitted document forced, and the reason this
    class exists at all. The first version of this module measured every
    surface, reasoning that legibility is not a front-only property. On the
    real document that read ``min_text_pt: 1.5`` off
    ``panel-BODY_BACK-label`` — a run whose TEXT IS THE SURFACE'S OWN NAME,
    drawn in the schematic strip at diagram scale. Failing a container's
    print legibility on the caption of its own thumbnail is the same error
    as the false PASS this work item removed, pointing the other way.
    """

    def _strip_panel(self, size_pt=1.5, name="panel-BODY_BACK-label"):
        from apps.ire.compose_container import SURFACE_GROUP_PREFIX
        return Group(
            name=f"{SURFACE_GROUP_PREFIX}BODY_BACK", role="decoration",
            children=[Group(name="BACK_DIRECT_PRINT", role="decoration",
                            children=[_name_run(size_pt=size_pt, name=name)])])

    def test_strip_type_does_not_set_the_container_minimum(self):
        record = ctm.measure_typography_metrics(
            _doc([_name_run(size_pt=12.0), self._strip_panel()]))
        assert record["min_text_pt"] == 12.0
        assert record["container_view_text_runs"] == 1

    def test_the_excluded_strip_runs_are_counted_not_hidden(self):
        """The back panel's copy is emitted ONLY in the strip, so this
        record does not measure back-panel legibility. That limit has to be
        visible in the record, not inferable from its absence."""
        record = ctm.measure_typography_metrics(
            _doc([_name_run(size_pt=12.0), self._strip_panel()]))
        assert record["surface_strip_runs_excluded"] == 1
        # §BH50(f)(1): the sentence used to say back-panel legibility was not
        # measured by this record — false since the true-scale panel; it now
        # says where the panel is measured and what a depicted-only surface is
        assert "§BH50(f)(1)" in record["surface_strip_exclusion_reason"]
        assert "NOT MEASURED" in record["surface_strip_exclusion_reason"]

    def test_a_document_of_only_strip_type_yields_no_record(self):
        assert ctm.measure_typography_metrics(
            _doc([self._strip_panel()])) is None

    def test_source_guard_the_hero_skip_literal_is_in_surface_panels(self):
        """SOURCE-STRING GUARD (§Y2). Asserts a literal appears in a function's
        source. **It asserts nothing about behaviour** — the comparison being
        written there does not prove the hero survives the strip, and it is
        not citable as coverage (§Y2(c)). The behavioural cover is
        ``test_container_text_floor.test_only_the_hero_surface_is_reachable_
        from_the_container_view``, which measures which surfaces come back.

        Kept under §Y2(a): the exclusion rests on ``_surface_panels`` skipping
        the hero, so if the emitter ever wrapped the hero too, the exclusion
        would silently drop the front. This catches that line disappearing.

        §BH66(a) moved the literal and not the line: the skip now reads the
        RUN's hero surface, because a FACE is its own hero (a compact's
        LID_TOP) and must not be drawn a second time as a strip panel. The
        parameter defaults to ``HERO_SURFACE``, so every front run skips
        exactly what it skipped before — that default is asserted by a
        behavioural test (``test_au3_divider_gates``, the §BH66(a) class),
        never by this guard.
        """
        import inspect
        from apps.ire import compose_container as cc
        src = inspect.getsource(cc._surface_panels)
        assert "surf != hero_surface" in src


class TestTheRecordSaysWhereItsTextExtentsCameFrom:
    """WI-F made text extents measurable and made them SAY whether they were
    measured. A clipping verdict resting on an estimated extent is an
    estimated verdict."""

    def test_the_record_carries_the_per_role_provenance(self):
        record = ctm.measure_typography_metrics(_doc([_name_run()]))
        prov = record["text_metrics_provenance"]
        assert set(prov["faces_by_role"]) == {"regular", "bold", "arabic"}
        assert prov["all_roles_measured"] is False
        assert prov["roles_estimated"] == ["arabic"]

    def test_the_record_names_its_producer_and_artboard(self):
        record = ctm.measure_typography_metrics(_doc([_name_run()]))
        assert record["schema_version"] == ctm.SCHEMA
        assert record["artboard_mm"] == [PAGE_W, PAGE_H]
        assert record["measured_by"].endswith("measure_typography_metrics")


# --- WI-A / §W5: placeholder text on a container ---------------------------

def _copy_run(text, name="product-name-hero", size_pt=12.0):
    return TextRun(name=name, text=text, x=10.0, y=40.0, font="bold",
                   size_pt=size_pt, color=BLACK)


def _in_strip(*runs, surface="BODY_BACK"):
    from apps.ire.compose_container import SURFACE_GROUP_PREFIX
    return Group(name=f"{SURFACE_GROUP_PREFIX}{surface}", role="decoration",
                 children=[Group(name="BACK_DIRECT_PRINT", role="decoration",
                                 children=list(runs))])


class TestPlaceholderTextIsRuledNotGuessed:
    """§W5 turned the one field this producer refused into a measurable one.

    It stayed absent through sprint 7 for a good reason: a boolean failing on
    ANY placeholder would have contradicted §B1/§B2, which rule the
    back-label EAN and the distributor identity legitimate. The ruling is an
    ALLOW-LIST of those two, not a cleverer regex.
    """

    # §BH50(f)(2): these five tests read the typography RECORD's placeholder
    # fields until the ruling. The detector is unchanged and is now the
    # placeholder record's instrument, so they read it directly; the last test
    # of the class pins that the typography record and the gate's field set
    # carry no placeholder field.

    def test_a_clean_container_now_reports_false_rather_than_absent(self):
        rep = ctm.measure_placeholder_text(_doc([_copy_run("BBROSE")]))
        assert rep["present"] is False
        record = ctm.measure_typography_metrics(_doc([_copy_run("BBROSE")]))
        assert "placeholder_text_present" not in record["unmeasured"]

    def test_an_unruled_placeholder_is_a_finding(self):
        rep = ctm.measure_placeholder_text(
            _doc([_copy_run("TBD", name="product-name-hero")]))
        assert rep["present"] is True

    def test_the_finding_names_the_run_and_the_text(self):
        """§W5(b) requires both. A finding that says only "a placeholder was
        found" sends the owner looking for it."""
        rep = ctm.measure_placeholder_text(
            _doc([_copy_run("LOREM IPSUM DOLOR", name="product-name-hero")]))
        finding = rep["findings"][0]
        assert finding["node_name"] == "product-name-hero"
        assert finding["text"] == "LOREM IPSUM DOLOR"
        assert finding["marker"] == "lorem ipsum"

    def test_the_permitted_ean_placeholder_does_not_fail(self):
        rep = ctm.measure_placeholder_text(_doc([
            _copy_run("BBROSE"),
            _copy_run("EAN — PLACEHOLDER", name="back-label-ean")]))
        assert rep["present"] is False
        assert rep["permitted"][0]["node_name"] == "back-label-ean"

    def test_the_permitted_distributor_placeholder_does_not_fail(self):
        rep = ctm.measure_placeholder_text(_doc([
            _copy_run("BBROSE"),
            _copy_run("DISTRIBUTOR — PLACEHOLDER",
                      name="distributor-identity")]))
        assert rep["present"] is False

    def test_the_typography_record_and_the_gate_carry_no_placeholder_field(self):
        """§BH50(f)(2): the same six pieces were a typography failure and a
        readiness code at once. The typography record publishes no placeholder
        field, the gate's typography axis reads none, and the placeholder
        record carries the finding with its own code."""
        from apps.ire import container_placeholder_copy as cpc
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ctm.measure_typography_metrics(
            _doc([_copy_run("TBD", name="product-name-hero")]))
        assert not any(k.startswith("placeholder_") for k in record)
        assert "placeholder_text_present" not in vqg._TYPOGRAPHY_FIELDS
        assert "placeholder_text_present" not in vqg._TYPOGRAPHY_FLAG_FINDINGS
        rec = cpc.build(_doc([_copy_run("TBD", name="product-name-hero")]),
                        sections=[], content_codes=[], composed=False)
        assert rec["codes"] == [
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:unslotted:product-name-hero"]
        assert rec["unslotted"][0]["text"] == "TBD"
        assert rec["back_copy_composed_on_this_path"] is False
        assert rec["blocks"].startswith("ACCEPTANCE")

    def test_the_allow_list_is_exactly_the_two_ruled_placeholders(self):
        """§W5(d): an executor may not extend it. This test is the tripwire —
        it fails on any addition, so a fifth entry has to be argued for
        against a ruling rather than slipped in."""
        assert set(ctm.PERMITTED_PLACEHOLDER_RUNS) == {
            "back-label-ean", "distributor-identity"}
        for citation in ctm.PERMITTED_PLACEHOLDER_RUNS.values():
            assert "OWNER_BLOCKER_CLEARANCE.md" in citation

    def test_a_permitted_run_does_not_license_the_rest_of_the_container(self):
        rep = ctm.measure_placeholder_text(_doc([
            _copy_run("EAN — PLACEHOLDER", name="back-label-ean"),
            _copy_run("TODO", name="product-name-hero")]))
        assert rep["present"] is True
        assert [f["node_name"] for f in rep["findings"]] == ["product-name-hero"]


class TestThePlaceholderCheckFollowsTheCopy:
    """Different scope from the SIZE measurement, deliberately.

    The size floor is a PRINT floor, so measuring the strip's diagram scale
    against it fails the container for a property of its own thumbnail — the
    sprint-7 1.5 pt finding. A placeholder is not a scale property: "TBD" is
    TBD at any size, and the back panel's copy is real product copy that
    today is drawn ONLY in the strip.
    """

    def test_back_panel_copy_in_the_strip_is_still_container_copy(self):
        # §BH50(f)(2): read from the detector, which the placeholder record
        # uses; the strip's depiction of product copy stays in its scope
        rep = ctm.measure_placeholder_text(_doc([
            _copy_run("BBROSE"),
            _in_strip(_copy_run("TBD", name="back-section-0-copy",
                                size_pt=1.2))]))
        assert rep["present"] is True
        assert rep["findings"][0]["node_name"] == "back-section-0-copy"

    def test_the_strip_still_does_not_set_the_size_floor(self):
        """The scope widening must not leak into min_text_pt — that would
        re-introduce the exact defect sprint 7 removed."""
        record = ctm.measure_typography_metrics(_doc([
            _copy_run("BBROSE", size_pt=12.0),
            _in_strip(_copy_run("INGREDIENTS", name="back-section-0-copy",
                                size_pt=1.2))]))
        assert record["min_text_pt"] == 12.0
        assert record["container_view_text_runs"] == 1

    def test_the_strips_own_furniture_is_not_container_copy(self):
        """``panel-{surface}-label`` is the emitter captioning its own
        diagram. Its words are not drawn on the container."""
        rep = ctm.measure_placeholder_text(_doc([
            _copy_run("BBROSE"),
            _in_strip(_copy_run("PLACEHOLDER",
                                name="panel-BODY_BACK-label", size_pt=1.5))]))
        assert rep["present"] is False

    def test_sheet_furniture_is_not_container_copy(self):
        rep = ctm.measure_placeholder_text(_doc([
            _copy_run("BBROSE"),
            _copy_run("TBD", name="spec-note")]))
        assert rep["present"] is False


class TestTheContestedTokenIsNotAdjudicated:
    """§W5(c) names the disagreement: ``print_data._PLACEHOLDER_RE`` matches
    "N/A" and ``production_readiness._PLACEHOLDER_RE`` does not. §W5 rules
    which placeholders are PERMITTED; it does not rule that one. Choosing
    between two committed definitions by coin-flip is not a measurement.
    """

    # §BH50(f)(2): the contested token is the placeholder record's finding
    # now — it blocks there, by its own code, and the typography record
    # carries no placeholder field at all

    def test_the_contested_token_leaves_the_field_absent(self):
        record = ctm.measure_typography_metrics(
            _doc([_copy_run("N/A", name="product-name-hero")]))
        assert "placeholder_text_present" not in record
        assert "placeholder_text_present" not in record["unmeasured"]
        rep = ctm.measure_placeholder_text(
            _doc([_copy_run("N/A", name="product-name-hero")]))
        assert rep["present"] is None

    def test_the_contested_run_is_named(self):
        from apps.ire import container_placeholder_copy as cpc
        rep = ctm.measure_placeholder_text(
            _doc([_copy_run("N/A", name="product-name-hero")]))
        assert rep["contested"][0]["node_name"] == "product-name-hero"
        rec = cpc.build(_doc([_copy_run("N/A", name="product-name-hero")]),
                        sections=[], content_codes=[], composed=False)
        assert rec["codes"] == [
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:contested:product-name-hero"]

    def test_a_contested_token_does_not_hide_a_real_finding(self):
        """Absence of one measurement does not un-see a defect found beside
        it — the asymmetry both axes were fixed to carry in sprint 7."""
        from apps.ire import container_placeholder_copy as cpc
        doc = _doc([_copy_run("N/A", name="product-name-0"),
                    _copy_run("TBD", name="product-name-1")])
        rep = ctm.measure_placeholder_text(doc)
        assert rep["present"] is True
        assert rep["contested"]
        rec = cpc.build(doc, sections=[], content_codes=[], composed=False)
        assert rec["codes"] == [
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:unslotted:product-name-1",
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:contested:product-name-0"]

    def test_the_block_moved_to_its_own_code_and_did_not_vanish(self):
        """This test asserted that the gate's typography axis blocked on a
        contested token (UNMEASURED) and on a found one (FAIL) until
        §BH50(f)(2). The block is the placeholder record's own code now, at
        acceptance, in both cases; the typography axis names no placeholder."""
        from apps.ire import container_placeholder_copy as cpc
        from apps.pipeline.services import visual_quality_gate as vqg
        for text in ("N/A", "TBD"):
            doc = _doc([_copy_run(text, name="product-name-hero")])
            rec = cpc.build(doc, sections=[], content_codes=[], composed=False)
            assert rec["codes"] and all(
                c.startswith(cpc.CONTENT_VERIFICATION_REQUIRED) for c in rec["codes"])
            axis = vqg._typography_axis(
                {ctm.SCHEMA: ctm.measure_typography_metrics(doc)}, {})
            assert "placeholder" not in axis["reason"].lower()


class TestTheContainerRuleIsItsOwn:
    """§W5(c): do not reuse either existing regex. Both were written for spec
    FIELD VALUES, where "" and "—" ARE placeholders. On a container an empty
    run is not drawn at all and a dash is a RULE, so importing either would
    fail every container that draws a divider."""

    def test_source_guard_neither_spec_field_regex_is_imported(self):
        """SOURCE-STRING GUARD (§Y2). Asserts three import literals are absent
        from a module's source. **It asserts nothing about behaviour** and is
        not citable as coverage (§Y2(c)) — an import written any other way, or
        the same regex pasted in rather than imported, leaves it green. The
        behavioural cover is ``test_a_drawn_dash_is_not_a_placeholder`` below,
        which measures what the container rule actually does with a dash.
        """
        import inspect
        src = inspect.getsource(ctm)
        assert "import _PLACEHOLDER_RE" not in src
        assert "print_data import" not in src
        assert "production_readiness import" not in src

    def test_a_drawn_dash_is_not_a_placeholder(self):
        """``print_data._PLACEHOLDER_RE`` matches a lone dash. A container
        draws those as rules and separators."""
        rep = ctm.measure_placeholder_text(
            _doc([_copy_run("—", name="product-name-hero")]))
        assert rep["present"] is False


class TestTheAxisReasonNamesWhatFired:
    """The WI-M treatment, applied to the sibling axis. Reciting all four
    defects in one sentence asserted about fields nobody measured — and §W5
    made that live rather than latent, because a placeholder finding on a
    record with no overlap measurement would have announced an overlap."""

    def test_a_placeholder_finding_does_not_announce_an_overlap(self):
        """§BH50(f)(2): the placeholder is no longer a typography finding,
        so the axis on this record is UNMEASURED for the oblique run's overlap
        and says nothing about placeholders; the placeholder record carries
        the finding under its own code. This test asserted FAIL with the
        reason "placeholder text is drawn on the container" until then."""
        from apps.ire import container_placeholder_copy as cpc
        from apps.pipeline.services import visual_quality_gate as vqg
        doc = _doc([_copy_run("TBD", name="product-name-hero"), _oblique_run()])
        record = ctm.measure_typography_metrics(doc)
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.UNMEASURED
        assert "placeholder" not in axis["reason"].lower()
        assert "materially_overlapping" not in record
        assert cpc.build(doc, sections=[], content_codes=[],
                         composed=False)["codes"] == [
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:unslotted:product-name-hero"]

    def test_the_floor_finding_still_fires_and_is_named(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ctm.measure_typography_metrics(
            _doc([_copy_run("BBROSE", size_pt=2.0)]))
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.FAIL
        # §W2 renamed the finding as well as relocating it: no print method
        # is recorded here, so 2.0 pt is measured against the 5.0 fallback.
        assert axis["reason"] == \
            "type is below its print method's minimum size"

    def test_two_findings_are_both_named(self):
        """§BH50(f)(2): a placeholder below the floor is two findings in two
        records — the size here, the unwritten copy in the placeholder
        record — and each names its own. This test asserted one reason
        carrying both until then."""
        from apps.ire import container_placeholder_copy as cpc
        from apps.pipeline.services import visual_quality_gate as vqg
        doc = _doc([_copy_run("TBD", name="product-name-hero", size_pt=2.0)])
        record = ctm.measure_typography_metrics(doc)
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["reason"] == "type is below its print method's minimum size"
        assert cpc.build(doc, sections=[], content_codes=[],
                         composed=False)["codes"] == [
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:unslotted:product-name-hero"]
