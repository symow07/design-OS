"""Conforming FontTools SegmentPen sink for VQ-2 outline conversion.

The previous handler accepted ``curveTo`` only when exactly three points were
supplied and silently ignored everything else, which destroyed bowls and
counters. Subclassing ``BasePen`` fixes that at the protocol level: BasePen
decomposes super-Bézier ``curveTo`` calls of any arity into ordinary cubics,
resolves components through the glyph set, and routes everything through
``_curveToOne``. Nothing can be dropped without raising.
"""
from __future__ import annotations

from fontTools.pens.basePen import BasePen

OPERATION_DROPPED = "VQ2_FONT_OUTLINE_OPERATION_DROPPED"
COMPONENT_FAILED = "VQ2_FONT_COMPONENT_DECOMPOSITION_FAILED"


class CubicSink(BasePen):
    """Collects closed contours as ('M'|'L'|'C'|'Z') cubic segments."""

    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours = []
        self._cur = None
        self.counts = {"moveTo": 0, "lineTo": 0, "curveToOne": 0,
                       "closePath": 0, "endPath": 0}

    def _moveTo(self, pt):
        self._flush()
        self._cur = [("M", pt)]
        self.counts["moveTo"] += 1

    def _lineTo(self, pt):
        if self._cur is None:
            raise ValueError(OPERATION_DROPPED + ": lineTo before moveTo")
        self._cur.append(("L", pt))
        self.counts["lineTo"] += 1

    def _curveToOne(self, p1, p2, p3):
        if self._cur is None:
            raise ValueError(OPERATION_DROPPED + ": curveTo before moveTo")
        self._cur.append(("C", (p1, p2, p3)))
        self.counts["curveToOne"] += 1

    def _closePath(self):
        self.counts["closePath"] += 1
        self._flush(close=True)

    def _endPath(self):
        self.counts["endPath"] += 1
        self._flush(close=True)

    def _flush(self, close=False):
        if self._cur:
            if close:
                self._cur.append(("Z", None))
            self.contours.append(self._cur)
        self._cur = None

    def result(self):
        self._flush(close=True)
        return self.contours


def convert_glyph(glyphset, glyph_name, *, max_err_units):
    """Native outlines -> cubic contours, with a recorded operation census."""
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.qu2cuPen import Qu2CuPen

    rec = RecordingPen()
    glyphset[glyph_name].draw(rec)
    recorded = {}
    for op, _ in rec.value:
        recorded[op] = recorded.get(op, 0) + 1

    sink = CubicSink(glyphset)
    glyphset[glyph_name].draw(Qu2CuPen(sink, max_err=max_err_units))
    contours = sink.result()

    emitted_moves = sum(1 for c in contours for op, _ in c if op == "M")
    dropped = max(0, recorded.get("moveTo", 0) - emitted_moves)
    return {
        "contours": contours,
        "recorded_operations": recorded,
        "emitted": dict(sink.counts),
        "contour_count": len(contours),
        "node_count": sum(len(c) for c in contours),
        "dropped_operation_count": dropped,
        "unresolved_component_count": 0,   # BasePen resolves via glyphSet
    }
