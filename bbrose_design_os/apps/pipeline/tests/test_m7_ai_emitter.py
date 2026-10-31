"""M7 .AI emitter — the declared refusals and the structural claims."""
import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services import palette_m7_ai_emitter as AI


def _face():
    return AI.SetFace(AI.MATERIALS_FONT)


class VocabularyRefusalTests(SimpleTestCase):
    def _parse(self, body):
        with tempfile.NamedTemporaryFile("w", suffix=".svg",
                                         delete=False) as f:
            f.write(body)
            name = f.name
        self.addCleanup(os.remove, name)   # the test removes what it made (the clean-up of 2026-10-04)
        return AI.parse_svg(name)

    def test_unknown_element_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            self._parse('<svg xmlns="http://www.w3.org/2000/svg" '
                        'width="10mm" height="10mm" viewBox="0 0 10 10">'
                        '<circle r="1"/></svg>')

    def test_unknown_attribute_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            self._parse('<svg xmlns="http://www.w3.org/2000/svg" '
                        'width="10mm" height="10mm" viewBox="0 0 10 10">'
                        '<rect width="1" height="1" rx="0.5"/></svg>')

    def test_non_mm_viewbox_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            self._parse('<svg xmlns="http://www.w3.org/2000/svg" '
                        'width="10mm" height="10mm" viewBox="0 0 100 '
                        '100"></svg>')

    def test_unrecorded_colour_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            AI._rgb("hsl(10,10%,10%)")


class PathVocabularyTests(SimpleTestCase):
    """The §J extension: stroked single-subpath absolute M/L[/Z] only."""

    def test_curve_command_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            AI._path_ops("M 1 1 C 2 2 3 3 4 4")

    def test_relative_command_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            AI._path_ops("m 1 1 l 2 2")

    def test_second_subpath_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            AI._path_ops("M 1 1 L 2 2 M 3 3 L 4 4")

    def test_ml_z_parses(self):
        ops, closed = AI._path_ops("M 1 2 L 3 4 L 5 6 Z")
        self.assertEqual(ops, [("m", 1.0, 2.0), ("l", 3.0, 4.0),
                               ("l", 5.0, 6.0)])
        self.assertTrue(closed)

    def _emit_body(self, path_el):
        import tempfile
        body = ('<svg xmlns="http://www.w3.org/2000/svg" width="10mm" '
                'height="10mm" viewBox="0 0 10 10">%s</svg>' % path_el)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "p.svg"
            p.write_text(body)
            AI.emit(p, Path(tmp) / "p.ai", _face())
            return (Path(tmp) / "p.ai").read_bytes()

    def test_filled_path_with_stroke_attrs_refuses(self):
        # was test_filled_path_refuses before the §M plate grammar: a
        # filled path is now legal, but mixing fill with stroke attrs
        # still refuses (fills OR strokes, never both)
        with self.assertRaises(AI.AiEmitterError):
            self._emit_body('<path d="M 1 1 L 2 2 Z" '
                            'fill="rgb(20,22,20)" stroke="none" '
                            'stroke-width="0.2"/>')

    def test_filled_plate_emits_closed_fill_on_ground_stratum(self):
        # the §M dual-final plate grammar: closed single-subpath fill
        raw = self._emit_body('<path d="M 1 1 L 2 2 L 1 3 Z" '
                              'fill="rgb(207,224,216)"/>')
        self.assertIn(b"h f\n", raw)
        self.assertIn(b"/OC /oc0 BDC", raw)  # Ground stratum

    def test_filled_open_path_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            self._emit_body('<path d="M 1 1 L 2 2 L 1 3" '
                            'fill="rgb(207,224,216)"/>')

    def test_path_without_fill_attribute_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            self._emit_body('<path d="M 1 1 L 2 2 Z" '
                            'stroke="rgb(20,22,20)" '
                            'stroke-width="0.2"/>')

    def test_stroked_ring_emits_round_joined_closed_path(self):
        raw = self._emit_body('<path d="M 1 1 L 2 2 L 1 3 Z" fill="none" '
                              'stroke="rgb(20,22,20)" stroke-width="0.18" '
                              'stroke-linecap="round" '
                              'stroke-linejoin="round"/>')
        self.assertIn(b"1 J\n1 j\n", raw)
        self.assertIn(b"h S\n", raw)


class SetFaceTests(SimpleTestCase):
    def test_em_dash_encodes_to_winansi_97(self):
        self.assertEqual(_face().encode_winansi("—"), b"\x97")

    def test_middot_encodes_to_winansi_b7(self):
        self.assertEqual(_face().encode_winansi("·"), b"\xb7")

    def test_unmappable_character_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            _face().encode_winansi("桜")

    def test_missing_glyph_refuses(self):
        with self.assertRaises(AI.AiEmitterError):
            _face().advance_units("☃")

    def test_embedding_permission_is_checked(self):
        face = _face()
        self.assertGreater(face.upm, 0)
        self.assertGreater(len(face.bytes), 0)


class EmissionTests(SimpleTestCase):
    """Emit the LOCKED C3 lid into a temp dir and prove the declared
    structure — never touching the committed emission outputs."""

    def _emit_lid(self, tmp):
        svg = AI.M7 / "lid_artwork" / "es3083_lid_C3_final.svg"
        return AI.emit(svg, Path(tmp) / "lid.ai", _face())

    def test_lid_structure_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = self._emit_lid(tmp)
            self.assertEqual(rec["artboard_mm"], [65.0, 65.0])
            self.assertEqual(rec["outlined_text_blocks"], [])
            self.assertIn("BBROSE", rec["live_text_blocks"])
            self.assertEqual(rec["spot_separations"],
                             ["PANTONE 621 C", "PANTONE 627 C"])
            v = AI.validate(Path(tmp) / "lid.ai", (65.0, 65.0),
                            rec["live_text_blocks"],
                            rec["spot_separations"])
            self.assertEqual(v["verdict"], "PASS", v["findings"])

    def test_emission_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._emit_lid(tmp)
            b_dir = Path(tmp) / "again"
            svg = AI.M7 / "lid_artwork" / "es3083_lid_C3_final.svg"
            b = AI.emit(svg, b_dir / "lid.ai", _face())
            self.assertEqual(a["ai_sha256"], b["ai_sha256"])

    def test_anchor_convention_includes_trailing_letter_space(self):
        """The committed artwork anchors at centre - spacing/2; the
        emitter's width model (sum of advances + n*Tc) is what makes
        that anchor land ink-centred. One character at size s with
        spacing t must be centred on advance + t, not advance."""
        face = _face()
        adv_b = face.advance_units("B") / face.upm
        with tempfile.TemporaryDirectory() as tmp:
            body = ('<svg xmlns="http://www.w3.org/2000/svg" '
                    'width="10mm" height="10mm" viewBox="0 0 10 10">'
                    '<text x="5" y="5" font-family="Crimson Text" '
                    'font-size="2" letter-spacing="1" '
                    'text-anchor="middle" fill="rgb(20,22,20)">B'
                    '</text></svg>')
            p = Path(tmp) / "one.svg"
            p.write_text(body)
            AI.emit(p, Path(tmp) / "one.ai", face)
            raw = (Path(tmp) / "one.ai").read_bytes()
            k = AI.MM_TO_PT
            width_pt = adv_b * 2 * k + 1 * k
            tx = 5 * k - width_pt / 2.0
            self.assertIn(f"{AI._num(tx)} ".encode(), raw)


class CommittedEmissionRecordTests(SimpleTestCase):
    """Once the emission has run for real, the record must bind byte
    identities to sources; skipped-by-absence is not allowed — the
    launcher's own verdict is that an emitter never run is a FAIL."""

    #: the §I-accepted set — these three must always lead the record
    LOCKED_THREE = ("es3083_lid_C3.ai", "es3083_label_sheet_T1.ai",
                    "es3083_back_label_DRAFT.ai")

    def _record(self):
        import json
        rec_path = AI.OUT_DIR / "m7_ai_emission_record.json"
        self.assertTrue(rec_path.exists(),
                        "m7_ai_emission_record.json missing — the "
                        "emitter was never RUN, which the launcher "
                        "declares a FAIL")
        return json.loads(rec_path.read_text())

    def test_the_emission_record_exists_and_binds(self):
        import hashlib
        rec = self._record()
        self.assertGreaterEqual(len(rec["emissions"]), 3)
        self.assertEqual(
            tuple(e["ai"] for e in rec["emissions"][:3]),
            self.LOCKED_THREE,
            "the §I-accepted set no longer leads the record")
        for e in rec["emissions"]:
            ai = AI.OUT_DIR / e["ai"]
            self.assertTrue(ai.exists(), e["ai"])
            self.assertEqual(
                hashlib.sha256(ai.read_bytes()).hexdigest(),
                e["ai_sha256"], f"{e['ai']} drifted from its record")
            src = AI.REPO / e["source_svg"]
            incident = e.get("source_binding_incident")
            if incident and incident["status"].startswith("OPEN"):
                # a RECORDED open incident pins the canonical state
                # instead of the lost consumed source; an unrecorded
                # drift still fails below
                self.assertEqual(
                    hashlib.sha256(src.read_bytes()).hexdigest(),
                    incident["canonical_source_sha256"],
                    f"{e['source_svg']}: canonical source drifted "
                    "BEYOND the recorded incident")
                continue
            self.assertEqual(
                hashlib.sha256(src.read_bytes()).hexdigest(),
                e["source_sha256"],
                f"{e['source_svg']} drifted — the LOCKED artwork moved")

    def test_reemitting_locked_sources_reproduces_recorded_bytes(self):
        """The strongest guard on emitter evolution: converting each
        recorded source TODAY must reproduce the recorded .ai hash
        exactly. A change that moves shipped bytes is a visible FAIL,
        not a silent re-emission."""
        import hashlib
        import tempfile
        rec = self._record()
        face = _face()
        with tempfile.TemporaryDirectory() as tmp:
            for e in rec["emissions"]:
                out = Path(tmp) / e["ai"]
                r = AI.emit(AI.REPO / e["source_svg"], out, face)
                incident = e.get("source_binding_incident")
                if incident and incident["status"].startswith("OPEN"):
                    # the consumed source is recorded lost; the canonical
                    # source must still re-emit to the recorded canonical
                    # hash — the emitter's behaviour stays pinned
                    self.assertEqual(
                        r["ai_sha256"],
                        incident["canonical_reemission_sha256"],
                        f"{e['ai']}: canonical re-emission drifted "
                        "BEYOND the recorded incident")
                    continue
                self.assertEqual(
                    r["ai_sha256"], e["ai_sha256"],
                    f"{e['ai']}: the emitter no longer reproduces the "
                    "recorded bytes — behaviour drifted")
                self.assertEqual(
                    hashlib.sha256(out.read_bytes()).hexdigest(),
                    r["ai_sha256"])
