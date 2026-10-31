"""§W3 — one overlap rule, read by two axes, and it must stay one.

``blocking_overlaps`` and ``materially_overlapping`` were refused for the same
reason and ruled by the same paragraph. The risk this file guards is not that
the rule is wrong — the owner wrote it — but that it gets applied twice, in
two producers, and the two copies drift into disagreeing about the same pair
of runs. So every behavioural property here is asserted through BOTH axes.

The second risk is the rule quietly widening. §W3 is three clauses; a fourth
one invented here to make an awkward document decidable would be moving an
owner's rule to fit the work. §W3(d) says what to do instead, and the oblique
run exercises it.
"""
import pytest

from apps.ire import container_composition_metrics as ccm
from apps.ire import container_overlap as co
from apps.ire import container_typography_metrics as ctm
from apps.ire.graph import (Color, Document, Group, LineTo, MoveTo, Path, Rect,
                            SolidFill, Stroke, TextRun)

BLACK = Color.from_hex("#000000")
PAGE_W = 100.0
PAGE_H = 120.0


def _doc(children, page_w=PAGE_W, page_h=PAGE_H, metadata=None):
    return Document(page_w=page_w, page_h=page_h, metadata=metadata or {},
                    root=Group(name="Root", role="artwork", children=children))


def _run(x=10.0, y=40.0, text="BBROSE SERUM", name="product-name-hero",
         size_pt=12.0, opacity=1.0, rotation_deg=0.0):
    return TextRun(name=name, text=text, x=x, y=y, font="bold",
                   size_pt=size_pt, color=BLACK, opacity=opacity,
                   rotation_deg=rotation_deg)


def _box(run, doc):
    """The run's extent as THE PRODUCER computes it — never a number restated
    here, or a test could pass against a box the rule never saw."""
    from apps.ire.text_metrics import resolve_metric_faces, resolve_role_metrics
    return ccm._bbox(run, resolve_role_metrics(
        resolve_metric_faces(doc.metadata)))


def _overlaps(doc):
    return co.measure_text_overlaps(doc)


def _both_axes(doc):
    """``(blocking_overlaps, materially_overlapping)`` as the two records
    report them, with a sentinel for ABSENT so the two states stay distinct."""
    composition = ccm.measure_composition_metrics(doc)
    typography = ctm.measure_typography_metrics(doc)
    return (composition.get("blocking_overlaps", "ABSENT"),
            typography.get("materially_overlapping", "ABSENT"))


class TestClauseATypeOverTypeBlocks:
    """"Two names on top of each other is never intentional.\""""

    def test_two_intersecting_runs_block(self):
        record = _overlaps(_doc([_run(name="product-name-a"),
                                 _run(name="product-name-b")]))
        assert co.blocking_overlap_count(record) == 1
        assert record["blocking"][0]["nodes"] == ["product-name-a",
                                                  "product-name-b"]

    def test_the_finding_carries_the_evidence_for_the_verdict(self):
        record = _overlaps(_doc([_run(name="product-name-a"),
                                 _run(name="product-name-b")]))
        pair = record["blocking"][0]
        assert pair["overlap_mm"][0] > 0 and pair["overlap_mm"][1] > 0
        assert len(pair["boxes_mm"]) == 2
        assert pair["extent_sources"] == ["measured_text", "measured_text"]

    def test_separated_runs_do_not_block(self):
        record = _overlaps(_doc([_run(y=40.0, name="product-name-a"),
                                 _run(y=90.0, name="product-name-b")]))
        assert co.blocking_overlap_count(record) == 0

    @pytest.mark.parametrize("opacity", [1.0, 0.5, 0.05, 0.0])
    def test_the_overlap_blocks_at_any_opacity(self, opacity):
        """§W3(a) says "at any opacity", and every node in this graph carries
        one, so the clause has something to bite on. A name hidden under
        another name at 5% is still two names — and 0.0 is not an exemption
        either, because the run is still in the artwork."""
        record = _overlaps(_doc([_run(name="product-name-a"),
                                 _run(name="product-name-b",
                                      opacity=opacity)]))
        assert co.blocking_overlap_count(record) == 1
        assert record["blocking"][0]["opacity"] == [1.0, opacity]

    def test_three_stacked_runs_report_three_pairs(self):
        record = _overlaps(_doc([_run(name="product-name-a"),
                                 _run(name="product-name-b"),
                                 _run(name="product-name-c")]))
        assert co.blocking_overlap_count(record) == 3

    def test_abutting_boxes_are_not_an_overlap(self):
        """The most common non-defect in typesetting: two runs whose extents
        meet exactly. If the epsilon were a clearance rather than a noise
        allowance, every multi-line name would fail."""
        doc = _doc([_run(name="product-name-a")])
        first = doc.root.children[0]
        box = _box(first, doc)
        doc = _doc([first, _run(x=box[0] + box[2], name="product-name-b")])
        assert co.blocking_overlap_count(_overlaps(doc)) == 0


class TestClauseBTypeOverArtworkDoesNotBlock:
    """"That is the composition working as drawn, and the A2 rosette and the
    FB3093 lids depend on it.\""""

    def _over_artwork(self, artwork):
        return _overlaps(_doc([_run(), artwork]))

    def test_type_over_a_colour_field_does_not_block(self):
        record = self._over_artwork(
            Rect(name="decoration-field", x=0.0, y=0.0, w=60.0, h=60.0,
                 fill=SolidFill(color=BLACK)))
        assert co.blocking_overlap_count(record) == 0
        assert len(record["non_blocking_over_artwork"]) == 1

    def test_type_over_a_motif_does_not_block(self):
        record = self._over_artwork(
            Path(name="motif-flourish",
                 segments=[MoveTo(x=5.0, y=20.0), LineTo(x=60.0, y=60.0)],
                 stroke=Stroke(color=BLACK, width_mm=0.25)))
        assert co.blocking_overlap_count(record) == 0
        assert record["non_blocking_over_artwork"][0]["nodes"][1] == \
            "motif-flourish"

    def test_a_horizontal_hairline_rule_is_seen_at_its_stroke_width(self):
        """WI-L (§Z4). This test used to assert the OPPOSITE and was right to:
        it pinned a known limit of the evidence rather than of the verdict.

        ``geometry_report._path_bbox`` read coordinates out of the segment
        list and never consulted the stroke, so a rule drawn as one horizontal
        line measured 0 mm tall and no reader could see it. §W3's verdict was
        never affected — clause (b) rules type over a rule non-blocking, so a
        rule that never intersected gave the right answer for the wrong
        reason — but the pair was missing from the evidence list, which is
        supposed to be the record of what the rule looked at and let through.

        The helper now measures the ink. Both halves matter here: the verdict
        is unchanged, and the evidence is no longer silently short by one."""
        record = self._over_artwork(
            Path(name="rule-front-single",
                 segments=[MoveTo(x=5.0, y=38.0), LineTo(x=60.0, y=38.0)],
                 stroke=Stroke(color=BLACK, width_mm=0.25)))
        assert co.blocking_overlap_count(record) == 0, (
            "§W3(b) has not changed: type over a rule still does not block")
        assert len(record["non_blocking_over_artwork"]) == 1, (
            "the rule was invisible to the reader before WI-L; it is the "
            "EVIDENCE that was short, and this is what discharges it")
        pair = record["non_blocking_over_artwork"][0]
        assert pair["nodes"] == ["product-name-hero", "rule-front-single"]
        rule_box = pair["boxes_mm"][1]
        assert rule_box[3] == pytest.approx(0.25), (
            "the rule's measured height is its stroke width, exactly")
        assert rule_box[1] == pytest.approx(38.0 - 0.125), (
            "a stroke is centred on its path, so half a width above the line")
        assert rule_box[2] == pytest.approx(55.0), (
            "and a BUTT cap adds nothing along it — the rule is no longer "
            "than the 5→60 the composer drew")

    def test_the_zero_discriminated_rather_than_finding_nothing(self):
        """A zero from a reader that applied the rule and a zero from a reader
        that looked at nothing are different facts, and the record has to tell
        them apart or it cannot show the rule was exercised."""
        record = self._over_artwork(
            Rect(name="decoration-field", x=0.0, y=0.0, w=60.0, h=60.0,
                 fill=SolidFill(color=BLACK)))
        assert record["non_blocking_over_artwork"], (
            "the type-over-artwork overlap was not even seen, so this "
            "document proves nothing about clause (b)")


class TestClauseCTheArtboardCrossingIsSeparate:
    """"Crossing the artboard edge blocks SEPARATELY, and is already measured
    as elements_outside_artboard.\""""

    def test_a_run_off_the_page_is_not_reported_as_an_overlap(self):
        stray = _run(x=PAGE_W + 10.0, name="product-name-stray")
        record = ccm.measure_composition_metrics(_doc([_run(), stray]))
        assert record["elements_outside_artboard"] == 1
        assert record["blocking_overlaps"] == 0, (
            "an element half off the page was counted twice — once as an "
            "artboard crossing and again as an overlap")

    def test_the_record_names_where_crossings_are_counted_instead(self):
        record = _overlaps(_doc([_run()]))
        assert record["artboard_crossings_measured_separately"] == \
            "elements_outside_artboard"


class TestClauseDTheCaseTheRuleDoesNotReach:
    """"If a case does not fit (a)–(c) cleanly, it is UNMEASURED and blocking,
    and it comes back here." Used as written, not stretched."""

    def test_an_oblique_run_leaves_the_count_absent(self):
        record = _overlaps(_doc([_run(), _run(name="product-name-vertical",
                                              rotation_deg=30.0)]))
        assert co.blocking_overlap_count(record) is None
        assert record["unmeasurable_runs"][0]["node_name"] == \
            "product-name-vertical"
        assert record["unmeasurable_runs"][0]["rotation_deg"] == 30.0

    def test_the_reason_names_the_run_and_its_angle(self):
        record = _overlaps(_doc([_run(), _run(name="product-name-vertical",
                                              rotation_deg=30.0)]))
        reason = co.unmeasurable_reason(record)
        assert "product-name-vertical" in reason
        assert "30.0" in reason

    @pytest.mark.parametrize("rotation", [0.0, 90.0, -90.0, 180.0, 0.4])
    def test_the_axis_aligned_cases_stay_measurable(self, rotation):
        """``_text_bbox_mm`` states the extent exactly for these, and the
        emitter uses −90 for vertical consumer copy. Refusing them would
        make an ordinary container permanently unmeasured."""
        record = _overlaps(_doc([_run(rotation_deg=rotation)]))
        assert record["unmeasurable_runs"] == []
        assert co.blocking_overlap_count(record) == 0

    def test_a_blocking_pair_beside_an_unreachable_run_still_reports(self):
        """The sprint-7 asymmetry: a positive finding is about the pair that
        was found; a zero is a universal claim over every pair on the
        surface. An unmeasurable neighbour does not un-see the defect."""
        record = _overlaps(_doc([_run(name="product-name-a"),
                                 _run(name="product-name-b"),
                                 _run(name="product-name-vertical",
                                      rotation_deg=30.0)]))
        assert co.blocking_overlap_count(record) == 1


class TestTheScopeIsTheContainerViewNotTheStrip:
    """§W1(c) — do not measure the strip harder. The strip draws the other
    surfaces at diagram scale AND diagram positions, so two captions touching
    there says nothing about the container. Runs the emitter placed on two
    different surfaces cannot overlap in any case."""

    def _strip(self, *runs):
        from apps.ire.compose_container import SURFACE_GROUP_PREFIX
        return Group(name=f"{SURFACE_GROUP_PREFIX}BODY_BACK",
                     role="decoration", children=list(runs))

    def test_two_overlapping_strip_runs_do_not_block(self):
        doc = _doc([_run(), self._strip(_run(name="back-inci-0"),
                                        _run(name="back-inci-1"))])
        assert co.blocking_overlap_count(_overlaps(doc)) == 0

    def test_the_strip_runs_are_not_even_examined(self):
        doc = _doc([_run(), self._strip(_run(name="back-inci-0"),
                                        _run(name="back-inci-1"))])
        assert _overlaps(doc)["runs_examined"] == 1


class TestOneRuleTwoAxes:
    """The property the shared module exists for. Every document must produce
    the SAME answer on both axes — including the absent state, which is where
    two independent implementations would diverge first."""

    CASES = {
        "clean": [_run()],
        "blocking": [_run(name="product-name-a"), _run(name="product-name-b")],
        "over-artwork": [_run(), Rect(name="decoration-field", x=0.0, y=0.0,
                                      w=60.0, h=60.0,
                                      fill=SolidFill(color=BLACK))],
        "unreachable": [_run(), _run(name="product-name-vertical",
                                     rotation_deg=30.0)],
    }

    @pytest.mark.parametrize("case", sorted(CASES))
    def test_the_two_axes_agree(self, case):
        count, flag = _both_axes(_doc(list(self.CASES[case])))
        if count == "ABSENT":
            assert flag == "ABSENT", (
                "one axis reported an overlap verdict the other refused to "
                "give — the rule has been applied twice and they disagree")
        else:
            assert flag is (count > 0)

    def test_the_blocking_case_is_measured_on_both(self):
        assert _both_axes(_doc(list(self.CASES["blocking"]))) == (1, True)

    def test_the_unreachable_case_is_absent_on_both(self):
        assert _both_axes(_doc(list(self.CASES["unreachable"]))) == \
            ("ABSENT", "ABSENT")

    def test_source_guard_neither_producer_reimplements_the_rule(self):
        """SOURCE-STRING GUARD (§Y2). Asserts one literal is present and
        another absent in two files. **It asserts nothing about behaviour**
        and is not citable as coverage (§Y2(c)) — a second intersection test
        written with different variable names sails straight past it.

        Kept under §Y2(a) because the drift it prevents is textual before it
        is behavioural: a duplicated rule would pass every behavioural test
        above on the day it was written, and only diverge later.
        """
        for module in (ccm, ctm):
            source = open(module.__file__).read()
            assert "container_overlap import" in source
            assert "min(a[0]" not in source, (
                f"{module.__name__} grew its own intersection test")


class TestTheGateReportsTheRuleThatFired:
    """The axis reason must name what §W3 actually catches. "required
    elements overlap" described a rule nobody had written, and would read as
    the gate calling type over a motif a defect."""

    def _blocking(self):
        return _doc([_run(name="product-name-a"), _run(name="product-name-b")])

    def test_the_composition_axis_fails_and_names_it(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ccm.measure_composition_metrics(self._blocking())
        axis = vqg._composition_axis({ccm.SCHEMA: record})
        assert axis["state"] == vqg.FAIL
        assert axis["reason"] == "text is set over text"

    def test_the_typography_axis_fails_and_names_it(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ctm.measure_typography_metrics(self._blocking())
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.FAIL
        assert axis["reason"] == "type is set over type"

    def test_the_ruled_out_variant_is_recorded_as_not_available(self):
        """§W3 names the rule it did NOT choose — blocking only where an
        overlap materially impairs reading — and why: no instrument here can
        measure "impairs". A later session must find that in the record
        rather than rediscovering it as a good idea."""
        assert "impairs" in co.RULE
        assert "NOT available" in co.RULE
