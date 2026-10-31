"""VQ-2 converter fixture suite — SegmentPen protocol conformance (§5)."""
import json
import math
import os

import pytest
from django.conf import settings
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen

from apps.ire.vq2_glyph_pen import CubicSink, OPERATION_DROPPED, convert_glyph
from apps.ire.vq2_polyline_distance import (correspond, point_segment_distance,
                                            symmetric)

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
D = os.path.join(DOCS, "vq2")


class LegacySink(BasePen):
    """The broken handler: only accepts curveTo of exactly three points.

    Kept solely so the regression fixtures can prove it fails where the
    repaired sink passes.
    """

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours = []
        self._cur = None

    def _moveTo(self, pt):
        self._cur = [("M", pt)]

    def _lineTo(self, pt):
        if self._cur is not None:
            self._cur.append(("L", pt))

    def _closePath(self):
        if self._cur:
            self.contours.append(self._cur)
        self._cur = None

    def _endPath(self):
        self._closePath()

    def curveTo(self, *points):          # the defect: silent arity filter
        if len(points) == 3 and self._cur is not None:
            self._cur.append(("C", points))

    def qCurveTo(self, *points):         # silently ignored
        return


def sink_for(seq):
    s = CubicSink({})
    for op, args in seq:
        getattr(s, op)(*args)
    return s


class TestPenOperations:
    def test_ordinary_three_point_curveto(self):
        s = CubicSink({})
        s.moveTo((0, 0))
        s.curveTo((1, 1), (2, 1), (3, 0))
        s.closePath()
        c = s.result()
        assert len(c) == 1
        assert sum(1 for op, _ in c[0] if op == "C") == 1

    def test_arbitrary_arity_curveto_is_decomposed(self):
        """Super-Bézier: BasePen must split it, never drop it."""
        s = CubicSink({})
        s.moveTo((0, 0))
        s.curveTo((1, 2), (2, 2), (3, 2), (4, 2), (5, 0))
        s.closePath()
        c = s.result()
        n = sum(1 for op, _ in c[0] if op == "C")
        assert n >= 2, "super-Bezier must decompose into multiple cubics"
        assert s.counts["curveToOne"] == n

    def test_legacy_handler_drops_super_bezier(self):
        legacy = LegacySink({})
        legacy.moveTo((0, 0))
        legacy.curveTo((1, 2), (2, 2), (3, 2), (4, 2), (5, 0))
        legacy.closePath()
        emitted = sum(1 for c in legacy.contours for op, _ in c if op == "C")
        assert emitted == 0, "the legacy defect must still reproduce"

    def test_multiple_connected_cubic_segments(self):
        s = CubicSink({})
        s.moveTo((0, 0))
        s.curveTo((1, 1), (2, 1), (3, 0))
        s.curveTo((4, -1), (5, -1), (6, 0))
        s.closePath()
        assert sum(1 for op, _ in s.result()[0] if op == "C") == 2

    def test_qcurveto_multiple_offcurve_points(self):
        s = CubicSink({})
        s.moveTo((0, 0))
        s.qCurveTo((1, 2), (2, 2), (3, 0))
        s.closePath()
        assert sum(1 for op, _ in s.result()[0] if op == "C") >= 2

    def test_qcurveto_implied_oncurve_points(self):
        """All-off-curve quadratic contour (trailing None)."""
        s = CubicSink({})
        s.qCurveTo((0, 0), (2, 3), (4, 0), None)
        c = s.result()
        assert c and sum(1 for op, _ in c[0] if op == "C") >= 2

    def test_legacy_handler_drops_qcurveto(self):
        legacy = LegacySink({})
        legacy.moveTo((0, 0))
        legacy.qCurveTo((1, 2), (2, 2), (3, 0))
        legacy.closePath()
        assert sum(1 for c in legacy.contours for op, _ in c if op == "C") == 0

    def test_closed_bowl_single_contour(self):
        s = CubicSink({})
        s.moveTo((0, 0))
        for p in (((1, 1), (2, 1), (3, 0)), ((2, -1), (1, -1), (0, 0))):
            s.curveTo(*p)
        s.closePath()
        assert len(s.result()) == 1

    def test_nested_counters_two_contours(self):
        s = CubicSink({})
        for r in (10, 5):
            s.moveTo((-r, 0))
            s.lineTo((r, 0))
            s.lineTo((r, r))
            s.lineTo((-r, r))
            s.closePath()
        assert len(s.result()) == 2

    def test_disconnected_ink_contours(self):
        s = CubicSink({})
        for ox in (0, 100, 200):
            s.moveTo((ox, 0))
            s.lineTo((ox+10, 0))
            s.lineTo((ox+10, 10))
            s.closePath()
        assert len(s.result()) == 3

    def test_endpath_flushes(self):
        s = CubicSink({})
        s.moveTo((0, 0))
        s.lineTo((1, 0))
        s.lineTo((1, 1))
        s.endPath()
        assert len(s.result()) == 1
        assert s.counts["endPath"] == 1

    def test_unsupported_operation_fails_loudly(self):
        s = CubicSink({})
        with pytest.raises(ValueError) as e:
            s._lineTo((1, 1))          # no moveTo first
        assert OPERATION_DROPPED in str(e.value)
        s2 = CubicSink({})
        with pytest.raises(ValueError):
            s2._curveToOne((1, 1), (2, 2), (3, 3))


class TestComponents:
    def _font(self):
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
        p = os.path.join(settings.BASE_DIR, "vendor", "fonts", "imbue",
                         "Imbue[opsz,wght].ttf")
        if not os.path.exists(p):
            pytest.skip("Imbue not present in this environment")
        return instancer.instantiateVariableFont(
            TTFont(p), {"wght": 400, "opsz": 100}, inplace=False)

    def test_real_glyphs_drop_nothing(self):
        f = self._font()
        gs = f.getGlyphSet()
        cmap = f.getBestCmap()
        for ch in "RoseDamscn":
            r = convert_glyph(gs, cmap[ord(ch)], max_err_units=1.0)
            assert r["dropped_operation_count"] == 0, ch
            assert r["unresolved_component_count"] == 0, ch
            assert r["contour_count"] >= 1
            assert r["node_count"] > 3, f"{ch} looks like the old shard output"
        f.close()

    def test_counters_survive(self):
        f = self._font()
        gs = f.getGlyphSet()
        cmap = f.getBestCmap()
        for ch in "RoDa":
            r = convert_glyph(gs, cmap[ord(ch)], max_err_units=1.0)
            assert r["contour_count"] >= 2, f"{ch} lost its counter"
        f.close()

    def test_components_are_decomposed_by_glyphset(self):
        f = self._font()
        gs = f.getGlyphSet()
        composites = []
        for name in list(gs.keys())[:400]:
            rec = RecordingPen()
            try:
                gs[name].draw(rec)
            except Exception:
                continue
            if any(op == "addComponent" for op, _ in rec.value):
                composites.append(name)
        for name in composites[:5]:
            r = convert_glyph(gs, name, max_err_units=1.0)
            assert r["unresolved_component_count"] == 0
            assert r["contour_count"] >= 1, f"{name} decomposed to nothing"
        f.close()


class TestDistanceMetric:
    def test_midpoint_of_long_segment_is_zero(self):
        assert point_segment_distance((5, 0), (0, 0), (10, 0))[0] == 0.0

    def test_parallel_separation_exact(self):
        assert point_segment_distance((5, 3), (0, 0), (10, 0))[0] == 3.0

    def test_zero_length_segment_safe(self):
        assert point_segment_distance((3, 4), (0, 0), (0, 0))[0] == 5.0

    def test_different_sampling_same_line_is_zero(self):
        a = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
        b = [[(0, 0), (5, 0), (10, 0), (10, 5), (10, 10), (5, 10), (0, 10),
              (0, 5)]]
        assert symmetric(a, b)["symmetric_max"] == 0.0

    def test_reversed_direction_unchanged(self):
        c = [(math.cos(2*math.pi*i/64)*100, math.sin(2*math.pi*i/64)*100)
             for i in range(64)]
        assert symmetric([c], [list(reversed(c))])["symmetric_max"] == 0.0

    def test_translation_measured_exactly(self):
        c = [(math.cos(2*math.pi*i/256)*100, math.sin(2*math.pi*i/256)*100)
             for i in range(256)]
        d = symmetric([c], [[(x+2, y) for x, y in c]])["symmetric_max"]
        assert abs(d - 2.0) < 1e-6

    def test_correspondence_is_geometric_not_positional(self):
        outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
        inner = [(40, 40), (60, 40), (60, 60), (40, 60)]
        pairs, amb = correspond([outer, inner], [inner, outer])
        assert amb is None
        assert dict((i, j) for i, j, _ in pairs) == {0: 1, 1: 0}

    def test_mismatched_contour_counts_are_ambiguous(self):
        sq = [(0, 0), (1, 0), (1, 1)]
        pairs, amb = correspond([sq], [sq, sq])
        assert pairs is None and amb


class TestCertificationIntact:
    def test_deterministic_certification_record_stands(self):
        c = json.load(open(os.path.join(
            D, "vq2_lf1_r1_deterministic_certification.json")))
        assert c["state"] == "VQ2_LF1_R1_DETERMINISTICALLY_CERTIFIED"
        assert c["vector_result"]["passing"] == 13
        assert c["raster_result"]["passing"] == 13
        assert c["geometry_changed_during_certification"] is False
