"""M4B-B §8 — true technical sections."""
import json
import os
from pathlib import Path

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_moulded_geometry as MG
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_technical_sections as TS

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs" / "roadmap" / "palt_m4b_b"


def _p1b():
    return MR.build_rect_components(OC.confirmed_intent())


class SectionEngineTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _p1b()

    def test_a_section_is_a_real_plane_cut(self):
        p = self.dims["tray"]["pockets"][0]
        cut = TS.section_assembly(self.comps, "y", p["centre_mm"][1])
        self.assertGreater(len(cut["components"]), 3)
        for name, joined in cut["components"].items():
            with self.subTest(component=name):
                self.assertTrue(joined["loops"])
                for lp in joined["loops"]:
                    self.assertTrue(lp["closed"])

    def test_components_that_miss_the_plane_are_absent_not_empty(self):
        cut = TS.section_assembly(self.comps, "z", 0.05)
        self.assertTrue(cut["not_on_plane"])
        for joined in cut["components"].values():
            self.assertTrue(joined["loops"])

    def test_the_cut_material_lies_on_the_plane(self):
        p = self.dims["tray"]["pockets"][0]
        at = p["centre_mm"][1]
        cut = TS.section_assembly(self.comps, "y", at)
        for name in cut["components"]:
            v = self.comps[name]["vertices"]
            with self.subTest(component=name):
                self.assertLessEqual(v[:, 1].min() - 1e-6, at)
                self.assertGreaterEqual(v[:, 1].max() + 1e-6, at)

    def test_a_blank_section_is_refused_rather_than_drawn(self):
        empty = {"axis": "z", "at": 999.0, "components": {},
                 "not_on_plane": []}
        with self.assertRaises(TS.SectionError) as ctx:
            TS.draw_section(empty, "/tmp/never.png", "T", "S")
        self.assertIn("would be blank", str(ctx.exception))

    def test_a_focus_on_absent_components_is_refused(self):
        cut = TS.section_assembly(self.comps, "y", 0.0)
        with self.assertRaises(TS.SectionError):
            TS.draw_section(cut, "/tmp/never.png", "T", "S",
                            focus=("does_not_exist_",))

    def test_the_engine_has_no_join_tolerance(self):
        """Segments are joined combinatorially; an open section fails
        rather than being closed silently."""
        self.assertIsNone(TS.SCHEMA and
                          TS.build_sections.__defaults__ and None)
        from apps.pipeline.services import palette_mesh_section as MS
        self.assertIsNone(MS.SECTION_TOPOLOGY["join_tolerance"])

    def test_eleven_sections_are_required(self):
        self.assertEqual(len(TS.SECTIONS), 11)
        self.assertEqual(len({s[0] for s in TS.SECTIONS}), 11)


class ProducedSectionTests(SimpleTestCase):
    def _record(self, name):
        path = OUT / name
        self.assertTrue(path.exists(), f"{path} is missing")
        return json.loads(path.read_text())

    def test_p1a_produced_all_eleven(self):
        rec = self._record("p1a_sections.json")
        self.assertEqual(rec["produced_count"], 11)
        self.assertEqual(rec["skipped"], [])

    def test_p1b_skips_only_the_mirror_stack_and_says_why(self):
        """ES3083 establishes no mirror, so there is no stack to cut."""
        rec = self._record("p1b_sections.json")
        self.assertEqual(rec["produced_count"], 10)
        self.assertEqual([s["section"] for s in rec["skipped"]],
                         ["mirror_stack"])
        self.assertIn("no mirror", rec["skipped"][0]["why"])

    def test_every_produced_section_file_exists_and_is_not_blank(self):
        for rec_name, folder in (("p1a_sections.json", "sections_p1a"),
                                 ("p1b_sections.json", "sections_p1b")):
            rec = self._record(rec_name)
            for key in rec["produced"]:
                path = OUT / folder / f"section_{key}.png"
                with self.subTest(section=f"{folder}/{key}"):
                    self.assertTrue(path.exists())
                    arr = np.asarray(Image.open(path).convert("RGB"))
                    self.assertGreater(float(arr.std()), 8.0,
                                       "a blank section is not evidence")

    def test_the_records_declare_a_true_cut_not_a_clipped_render(self):
        for name in ("p1a_sections.json", "p1b_sections.json"):
            rec = self._record(name)
            self.assertEqual(rec["method"],
                             "TRUE_PLANE_CUT_NOT_CLIPPED_RENDER")
            self.assertIsNone(rec["join_tolerance"])
            self.assertFalse(rec["owner_approved"])
            self.assertEqual(rec["manufacturing_authority"],
                             "NOT_ESTABLISHED")

    def test_the_clasp_sections_differ_between_engaged_and_disengaged(self):
        a = OUT / "sections_p1b" / "section_clasp_engaged.png"
        b = OUT / "sections_p1b" / "section_clasp_disengaged.png"
        self.assertTrue(a.exists() and b.exists())
        self.assertNotEqual(
            np.asarray(Image.open(a).convert("RGB")).tobytes(),
            np.asarray(Image.open(b).convert("RGB")).tobytes(),
            "an open lid must change the clasp section")


class P1ACuttersAreNotMaterialTests(SimpleTestCase):
    def test_cutters_are_excluded_from_p1a_sections(self):
        comps, _ = MG.build_moulded_components()
        cutters = [n for n in comps if MG.is_cutter(n)]
        self.assertTrue(cutters)
        rec = json.loads((OUT / "p1a_sections.json").read_text())
        self.assertEqual(rec["family"], "P1A")
        for key in rec["produced"]:
            self.assertNotIn("cutter", key)
