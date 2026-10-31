"""WI-L (§Z4) — a stroke is ink, so a hairline is not zero mm tall.

``geometry_report._path_bbox`` read the segment list's coordinates and stopped
there. A rule drawn as one horizontal line therefore measured zero height, and
every reader of that box — the §W3 non-blocking evidence list, the artboard
containment check — was blind to it. §Y4 recorded it; §Z4 ordered it fixed,
and ordered a FIX rather than a wider tolerance.

The distinction matters and this file is organised around it. Widening
``_EPS_MM`` would have made the symptom go away by making the reader less
sure of everything, including the things it was right about. Consulting the
stroke makes the reader MORE sure: an unstroked path's box does not move by
one float, and a stroked one's box is what the producer inks.

WHERE the ink goes is read off the producer, not assumed — the discipline
sprint 11 opened with, after WI-I ruled on a units disagreement without
reading the emitter and got it backwards. ``pdf_ai`` calls ``setLineWidth``
and never ``setLineCap`` or ``setLineJoin``, so ReportLab's canvas defaults
stand: cap 0 (BUTT), join 0 (miter). That premise is not asserted in prose
here; ``TestThePremiseIsTheProducersOwnState`` asserts the default against a
real ReportLab canvas — behaviour — and guards the override textually. Read
those two declared guards as §Y2(c) requires: they catch a literal entering
or leaving ``pdf_ai``, which is not the same as proving no cap is ever set.
"""
import inspect

import pytest

from apps.ire import container_composition_metrics as ccm
from apps.ire import geometry_report as gr
from apps.ire.graph import (ClosePath, Color, CubicTo, Document, Group, LineTo,
                            MoveTo, Path, Rect, SolidFill, Stroke, TextRun)

BLACK = Color.from_hex("#000000")


def _stroke(width_mm):
    return Stroke(color=BLACK, width_mm=width_mm)


def _geometry_only_bbox(path):
    """The PRE-WI-L helper, reimplemented from its coordinates-only rule.

    Deliberately a second implementation rather than an import of the thing
    under test: a negative control that called the fixed helper to describe
    the unfixed one would be comparing a number with itself.
    """
    xs, ys = [], []
    for seg in path.segments:
        for attr in ("x", "x1", "x2"):
            value = getattr(seg, attr, None)
            if value is not None:
                xs.append(float(value))
        for attr in ("y", "y1", "y2"):
            value = getattr(seg, attr, None)
            if value is not None:
                ys.append(float(value))
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _rule(y=10.0, x0=5.0, x1=45.0, width_mm=0.25):
    return Path(name="rule-front-single",
                segments=[MoveTo(x=x0, y=y), LineTo(x=x1, y=y)],
                stroke=_stroke(width_mm))


class TestThePremiseIsTheProducersOwnState:
    """WI-I's lesson, applied before the measurement rather than after it.

    The pad's PLACEMENT is a claim about what the emitter does. If the claim
    is wrong the measurement is wrong, so the claim is a test.
    """

    def test_reportlab_starts_with_a_butt_cap_and_a_miter_join(self):
        import io

        from reportlab.pdfgen import canvas

        c = canvas.Canvas(io.BytesIO())
        assert c._lineCap == 0, (
            "a round or square cap would extend a rule half a width past "
            "each end and _path_bbox would then be under-reporting length")
        assert c._lineJoin == 0

    def test_source_guard_the_emitter_never_changes_the_cap_or_the_join(self):
        """SOURCE-STRING GUARD (§Y2). Asserts two literals are ABSENT from a
        source file. **It asserts nothing about behaviour** and is not citable
        as coverage (§Y2(c)): a cap set through `canvas.setLineCap`'s alias,
        through a graphics-state push, or by a caller that hands `pdf_ai` a
        pre-configured canvas sails straight past it.

        The behavioural half of this premise is the test above, which reads
        the cap off a real ReportLab canvas. What this guard adds is the
        other conjunct — that nothing between that default and the page
        overrides it — and under §Y2(a) that drift is textual before it is
        behavioural, because `setLineCap(1)` would keep every test in this
        file passing on the day it was written while making `_path_bbox`
        under-report the length of all 18 hairlines on the sheet.
        """
        from apps.ire.emitters import pdf_ai

        source = inspect.getsource(pdf_ai)
        assert "setLineCap" not in source
        assert "setLineJoin" not in source

    def test_source_guard_the_emitter_converts_the_width_from_mm(self):
        """SOURCE-STRING GUARD (§Y2). Asserts one literal is PRESENT in one
        function. **It asserts nothing about behaviour** and is not citable
        as coverage (§Y2(c)) — the same conversion written as
        `w = stroke.width_mm * mm` on the line before would fail this and
        change nothing about the PDF.

        Kept under §Y2(a) because it pins §Z1's law at the one call site the
        law is about: `width_mm` is millimetres and the emitter converts.
        That is the whole basis of `_stroke_pad_mm` returning `width_mm / 2`
        in millimetres, so if this literal ever goes the padding is being
        computed against an emitter that no longer does what it says.
        """
        from apps.ire.emitters import pdf_ai

        source = inspect.getsource(pdf_ai._set_stroke)
        assert "setLineWidth(stroke.width_mm * mm)" in source, (
            "§Z1 — width_mm is millimetres and the emitter converts. A "
            "stroke is centred on its path, so the ink reaches half of it "
            "on each side, which is the whole basis of _stroke_pad_mm")


class TestTheDefect:
    """A horizontal hairline, which is the finding §Y4 recorded."""

    def test_before_the_fix_the_rule_measured_zero_height(self):
        assert _geometry_only_bbox(_rule())[3] == 0.0, (
            "if this ever stops being true the defect was never what §Y4 "
            "said it was, and the rest of this file is measuring nothing")

    def test_the_rule_now_measures_its_stroke_width_exactly(self):
        x, y, w, h = gr._path_bbox(_rule(y=10.0, width_mm=0.25))
        assert h == pytest.approx(0.25)
        assert y == pytest.approx(10.0 - 0.125), "centred on the path"

    @pytest.mark.parametrize("width_mm", [0.08, 0.12, 0.2, 0.22, 0.32, 2.0])
    def test_the_height_is_the_width_at_every_weight_on_the_sheet(self,
                                                                  width_mm):
        assert gr._path_bbox(_rule(width_mm=width_mm))[3] == pytest.approx(
            width_mm)

    def test_a_vertical_rule_gains_width_not_height(self):
        path = Path(name="tick", segments=[MoveTo(x=8.0, y=2.0),
                                           LineTo(x=8.0, y=40.0)],
                    stroke=_stroke(0.4))
        x, y, w, h = gr._path_bbox(path)
        assert w == pytest.approx(0.4)
        assert h == pytest.approx(38.0), "the length is untouched"
        assert x == pytest.approx(8.0 - 0.2)


class TestItIsAFixAndNotAWiderTolerance:
    """§Z4's actual instruction. A tolerance makes a reader less sure of
    everything; this makes it more sure of one thing and changes nothing
    else."""

    def test_an_unstroked_path_does_not_move_by_one_float(self):
        path = Path(name="silhouette",
                    segments=[MoveTo(x=1.0, y=2.0), LineTo(x=30.0, y=2.0),
                              LineTo(x=30.0, y=44.0), ClosePath()],
                    fill=SolidFill(color=BLACK))
        assert gr._path_bbox(path) == _geometry_only_bbox(path)

    def test_nor_does_a_curve_with_no_stroke(self):
        path = Path(name="bulb", segments=[
            MoveTo(x=0.0, y=0.0),
            CubicTo(x1=3.0, y1=1.0, x2=9.0, y2=7.0, x=12.0, y=6.0)],
            fill=SolidFill(color=BLACK))
        assert gr._path_bbox(path) == _geometry_only_bbox(path)

    def test_the_epsilon_that_decides_containment_is_untouched(self):
        assert ccm._EPS_MM == 1e-6, (
            "§Z4 asked for a fix, not a wider tolerance — this constant "
            "moving is the failure mode the instruction names")


class TestAButtCapAddsNothingAlongTheLine:
    """The reason the pad is perpendicular rather than uniform. Padding all
    four sides is one line of code shorter and invents ink."""

    def test_a_rule_does_not_get_longer(self):
        assert gr._path_bbox(_rule(x0=5.0, x1=45.0, width_mm=0.25))[2] == \
            pytest.approx(40.0)

    def test_a_diagonal_takes_the_perpendicular_projection(self):
        # 3-4-5: direction (30, 40), length 50, so a 1.0 mm stroke reaches
        # 0.5 * 40/50 = 0.4 in x and 0.5 * 30/50 = 0.3 in y
        path = Path(name="motif-flourish",
                    segments=[MoveTo(x=0.0, y=0.0), LineTo(x=30.0, y=40.0)],
                    stroke=_stroke(1.0))
        x, y, w, h = gr._path_bbox(path)
        assert x == pytest.approx(-0.4)
        assert y == pytest.approx(-0.3)
        assert w == pytest.approx(30.8)
        assert h == pytest.approx(40.6)

    def test_a_cross_does_not_grow_at_all(self):
        """``M L M L`` — a horizontal arm and a vertical arm, which is how
        the powder constellation draws its `cross` particle.

        Each arm's pad falls INSIDE the span the other arm already covers, so
        the honest answer is that the node's extent is unchanged. A uniform
        pad would have grown every cross in the field by a full stroke width
        in both axes. This is the case that tells the two apart.
        """
        path = Path(name="particle-core-5-cross", segments=[
            MoveTo(x=-4.0, y=0.0), LineTo(x=4.0, y=0.0),
            MoveTo(x=0.0, y=-4.0), LineTo(x=0.0, y=4.0)],
            stroke=_stroke(0.5))
        assert gr._path_bbox(path) == pytest.approx(
            _geometry_only_bbox(path))

    def test_but_a_closed_path_does_grow_on_every_side(self):
        """A miter join on a right angle reaches exactly half a width in each
        axis, and every vertex of a closed subpath is a join."""
        path = Path(name="cu0-silhouette-outline", segments=[
            MoveTo(x=10.0, y=10.0), LineTo(x=30.0, y=10.0),
            LineTo(x=30.0, y=50.0), LineTo(x=10.0, y=50.0), ClosePath()],
            stroke=_stroke(0.22))
        assert gr._path_bbox(path) == pytest.approx(
            (10.0 - 0.11, 10.0 - 0.11, 20.0 + 0.22, 40.0 + 0.22))

    def test_and_so_does_a_curve_whose_extremum_turns(self):
        """At the leftmost point of a curve the tangent is vertical, so the
        ink does reach half a width further left."""
        path = Path(name="bottom-base-circle", segments=[
            MoveTo(x=0.0, y=0.0),
            CubicTo(x1=6.0, y1=0.0, x2=12.0, y2=6.0, x=12.0, y=12.0)],
            stroke=_stroke(0.2))
        assert gr._path_bbox(path) == pytest.approx(
            (-0.1, -0.1, 12.2, 12.2))


class TestSubpathsAreNotOneRun:
    """``M L M L`` is two disjoint strokes with four butt caps between them,
    not a four-point run. Treating it as one would join two lines the emitter
    never joined and pad an interior that is not there."""

    def test_two_parallel_verticals_pad_in_x_only(self):
        # GLASS_INNER_WALL's shape: two vertical lines, drawn in one node
        path = Path(name="GLASS_INNER_WALL", segments=[
            MoveTo(x=0.0, y=0.0), LineTo(x=0.0, y=40.0),
            MoveTo(x=20.0, y=0.0), LineTo(x=20.0, y=40.0)],
            stroke=_stroke(0.32))
        x, y, w, h = gr._path_bbox(path)
        assert h == pytest.approx(40.0), (
            "no cap extends a vertical line's length, in either subpath")
        assert w == pytest.approx(20.32)
        assert x == pytest.approx(-0.16)

    def test_a_lone_moveto_inks_nothing(self):
        path = Path(name="stray", segments=[MoveTo(x=3.0, y=4.0)],
                    stroke=_stroke(0.5))
        assert gr._path_bbox(path) == (3.0, 4.0, 0.0, 0.0)

    def test_a_zero_length_segment_does_not_divide_by_zero(self):
        path = Path(name="degenerate", segments=[MoveTo(x=3.0, y=4.0),
                                                 LineTo(x=3.0, y=4.0)],
                    stroke=_stroke(0.5))
        box = gr._path_bbox(path)
        assert box is not None and box[2] == pytest.approx(0.5)


class TestWhatItCostElsewhere:
    """§Z4 says the defect is shared with ``elements_outside_artboard``,
    "where it could change an answer". Whether it did is measured, not
    assumed, and the answer is stated either way."""

    @staticmethod
    def _doc(*children, page_w=100.0, page_h=120.0):
        return Document(page_w=page_w, page_h=page_h,
                        root=Group(name="root", children=list(children)))

    def test_a_rule_flush_to_the_trim_is_now_correctly_outside(self):
        """The answer that COULD change, constructed so it does. A rule drawn
        exactly on the trim edge inks half its width past it; before WI-L the
        box was zero-height and sat exactly on the boundary, so containment
        said inside. It is not inside — that ink is off the sheet.
        """
        doc = self._doc(
            TextRun(name="product-name-hero", text="ROSE", x=10.0, y=40.0,
                    size_pt=12.0, color=BLACK),
            Path(name="rule-at-trim",
                 segments=[MoveTo(x=5.0, y=120.0), LineTo(x=60.0, y=120.0)],
                 stroke=_stroke(0.4)))
        record = ccm.measure_composition_metrics(doc)
        assert record["elements_outside_artboard"] == 1
        assert [o["node_name"] for o in record["outside_elements"]] == [
            "rule-at-trim"]
        assert record["outside_elements"][0]["box_mm"][1] == pytest.approx(
            119.8)

    def test_and_a_rule_a_clear_millimetre_inside_stays_inside(self):
        """The other half of the same claim. A fix that reported everything
        outside would also have made the first test pass."""
        doc = self._doc(
            TextRun(name="product-name-hero", text="ROSE", x=10.0, y=40.0,
                    size_pt=12.0, color=BLACK),
            Path(name="rule-inside",
                 segments=[MoveTo(x=5.0, y=119.0), LineTo(x=60.0, y=119.0)],
                 stroke=_stroke(0.4)))
        record = ccm.measure_composition_metrics(doc)
        assert record["elements_outside_artboard"] == 0

    def test_the_composed_sheets_count_did_not_move_and_here_is_why(self):
        """MEASURED on the committed dropper fixture, not asserted from the
        shape of the change: the count is 4 before WI-L and 4 after.

        Not because the fix is inert — ``cu2-silhouette-outline`` went from
        1.805 mm past the bottom trim to 1.915 mm, so its box did move. It
        moved DEEPER outside. The four elements over the edge were already
        over it by 0.51 to 1.805 mm, which is five to sixteen times the
        0.11 mm a 0.22 mm stroke adds, and nothing else on the sheet sits
        inside that margin of the trim. A count that had moved would have
        been the more interesting result and it is not what happened.
        """
        from apps.ire.compose_dropper import compose_dropper_sheet
        # [his correction of 2026-10-07] the hot stamp CONFIRMED: only a confirmed method holds a label at its 6 pt
        from apps.ire.tests.test_back_panel import _BACK_ZONE, _FRONT_RECORD, _FRONT_ZONE, _GEOMETRY, _LIVE
        from apps.ire.tests.test_back_panel import _CONFIRMED_METHODS as _METHODS

        # §BH67(c)2: the front's two record lines handed in, as the count below was taken with them drawn
        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name="Rose Damascena", sku="X",
            back_sections=_LIVE, revision_status="TEST",
            methods_record=_METHODS, drawing_source="PARAMETRIC", **_FRONT_RECORD)   # §BH49(a): this evidence measures the PARAMETRIC composition (the typed numbers); the product path draws M3 by construction
        record = ccm.measure_composition_metrics(doc)
        assert record["elements_outside_artboard"] == 4
        assert record["element_count"] == 187

        paths = [n for n, _ in doc.walk() if getattr(n, "type", "") == "path"]
        stroked = [p for p in paths if p.stroke is not None]
        unstroked = [p for p in paths if p.stroke is None]
        assert len(unstroked) == 76 and not [
            p for p in unstroked
            if gr._path_bbox(p) != _geometry_only_bbox(p)], (
            "76 fill-only paths, and the fix moved none of them")

        flat = [p for p in stroked if _geometry_only_bbox(p)[3] == 0.0]
        assert len(flat) == 18, (
            "18 hairlines on this sheet measured zero height before WI-L")
        assert all(gr._path_bbox(p)[3] == pytest.approx(p.stroke.width_mm)
                   for p in flat), "and every one of them now measures its ink"
        assert all(gr._path_bbox(p)[2] == _geometry_only_bbox(p)[2]
                   for p in flat), "with not one of them any longer"


class TestTheDuplicateIsRecordedNotFixed:
    """``container_motif_fidelity`` carries a byte-identical copy of the
    pre-WI-L helper, and §Z4 does not name it. It is left alone, which is a
    decision and therefore gets a test rather than a silence.

    Fixing it would move ``dewdrop_census``'s size_min/size_max — read by a
    ``size_max < size_min * 1.8`` threshold that decides
    MOTIF_SCALE_DISTRIBUTION_FAILED — and ``container_quant_fidelity``'s ink
    coverage ratio. Those are gate axes §Z4 did not rule about, and §Y4's
    recorded reason for deferring this whole fix was that widening a shared
    geometry helper moves numbers on axes the ruling did not cover. So it is
    a finding for the owner sheet, not a second fix in this commit.
    """

    def test_the_duplicate_still_exists_and_still_ignores_the_stroke(self):
        from apps.ire import container_motif_fidelity as cmf

        rule = _rule(width_mm=0.25)
        assert cmf._path_bbox(rule)[3] == 0.0
        assert cmf._path_bbox(rule) == _geometry_only_bbox(rule)

    def test_so_the_two_helpers_now_disagree_and_that_is_the_finding(self):
        from apps.ire import container_motif_fidelity as cmf

        tick = Path(name="particle-core-1-tick", segments=[
            MoveTo(x=0.0, y=0.0),
            CubicTo(x1=1.0, y1=2.0, x2=4.0, y2=3.0, x=6.0, y=4.0)],
            stroke=_stroke(0.56))
        assert cmf._path_bbox(tick) != gr._path_bbox(tick), (
            "recorded, not fixed — sprint 12's material, and the owner "
            "sheet says so with the numbers")

    def test_a_stroked_rect_has_the_same_blind_spot(self):
        """The second recorded finding. ``_bbox`` reads a Rect's own x/y/w/h
        and never its stroke, so the defect §Z4 named for paths is one branch
        away, unfixed."""
        doc = TestWhatItCostElsewhere._doc(
            TextRun(name="product-name-hero", text="ROSE", x=10.0, y=40.0,
                    size_pt=12.0, color=BLACK),
            Rect(name="panel-frame-1", x=5.0, y=119.9, w=50.0, h=0.1,
                 stroke=_stroke(0.4)))
        record = ccm.measure_composition_metrics(doc)
        assert record["elements_outside_artboard"] == 0, (
            "it inks 0.2 mm past the 120 mm trim and is reported inside — "
            "recorded, not fixed")

    def test_and_no_rect_on_the_composed_sheet_is_near_enough_to_care(self):
        """Why leaving it costs nothing TODAY, measured rather than assumed.

        The first draft of this finding claimed no rect on the sheet carries a
        stroke at all. 18 of 22 do. The claim was written from the shape of the
        change instead of from the document — sprint 11's own lesson, landing
        on sprint 11 — and the honest version is a clearance measurement.
        """
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_back_panel import (_BACK_ZONE, _FRONT_ZONE,
                                                    _GEOMETRY, _LIVE, _METHODS)

        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name="Rose Damascena", sku="X",
            back_sections=_LIVE, revision_status="TEST",
            methods_record=_METHODS)
        rects = [n for n, _ in doc.walk() if getattr(n, "type", "") == "rect"]
        stroked = [n for n in rects if n.stroke is not None]
        assert len(stroked) == 18, (
            "18 of the sheet's rects DO carry a stroke — panel frames, "
            "swatches, the back-panel boundary, the bottom-code window")
        clearances = [min(n.x, n.y, doc.page_w - (n.x + n.w),
                          doc.page_h - (n.y + n.h)) for n in stroked]
        pads = [n.stroke.width_mm / 2.0 for n in stroked]
        assert min(clearances) == pytest.approx(12.0)
        assert max(pads) == pytest.approx(0.1)
        assert not [n for n, c, p in zip(stroked, clearances, pads) if c < p], (
            "zero of 18 would cross the artboard once the stroke counts, so "
            "the unfixed branch changes no number on this sheet")
