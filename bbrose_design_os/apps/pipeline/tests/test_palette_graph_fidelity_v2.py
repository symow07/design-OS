"""PALT-M4C §4/§7 — the completed Design Graph and the eleven metrics."""
from django.test import SimpleTestCase

from apps.pipeline.services import palette_design_fidelity as fid
from apps.pipeline.services import palette_design_graph as dg
from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_rect_pan as rect_pan
from apps.pipeline.services import palette_rect_tray_geometry as rt


def _tray():
    return rt.build_rect_recessed_tray()


class DesignGraphTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intent = OC.confirmed_intent()
        cls.tray = _tray()
        cls.graph = dg.build_palette_design_graph(
            cls.intent, cls.tray, pan=rect_pan.build_rect_pan("pan"))
        cls.meta = cls.graph["document"].metadata

    def test_it_carries_every_component_the_design_has(self):
        ids = {c["id"] for c in self.graph["components"]}
        self.assertEqual(ids, {"case", "lid", "base", "tray", "hinge",
                               "clasp"})

    def test_unbuilt_components_say_so_rather_than_claiming_geometry(self):
        """A node claiming built geometry it does not have would be worse
        than a missing node."""
        self.assertEqual(set(self.graph["unbuilt_components"]),
                         {"case", "lid", "base", "hinge", "clasp"})
        for c in self.graph["components"]:
            if c["geometry_state"] == dg.NOT_BUILT:
                self.assertIsNone(c["mesh_identity"])
                self.assertEqual(c["built_by"], "PALT-M4B-B")
            else:
                self.assertEqual(c["mesh_identity"],
                                 self.tray["mesh_identity"])

    def test_it_holds_twelve_rectangular_pans(self):
        struct = self.graph["document"].find_role("structure")[0]
        self.assertEqual(len(struct.children), 12)
        self.assertEqual(self.tray["pocket_shape"], "RECTANGULAR")

    def test_row_and_column_relationships_exist(self):
        rels = self.meta["relationships"]
        rows = [r for r in rels if r["kind"] == "ROW_GROUP"]
        cols = [r for r in rels if r["kind"] == "COLUMN_GROUP"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(cols), 4)
        self.assertEqual(sum(len(r["members"]) for r in rows), 12)
        self.assertEqual(sum(len(c["members"]) for c in cols), 12)

    def test_spacing_margin_alignment_and_size_constraints_exist(self):
        kinds = {r["kind"] for r in self.meta["relationships"]}
        for kind in ("SPACING", "MARGIN", "ALIGNMENT", "RELATIVE_SIZE",
                     "PARENT_CHILD"):
            self.assertIn(kind, kinds)

    def test_open_and_closed_states_are_declared(self):
        states = self.meta["states"]
        self.assertIn(dg.OPEN, states)
        self.assertIn(dg.CLOSED, states)
        for s in states.values():
            self.assertEqual(s["geometry_state"], dg.NOT_BUILT)

    def test_pantone_tokens_are_nodes_and_are_not_converted(self):
        self.assertEqual(self.meta["named_colour_references"],
                         ["PANTONE 621 C", "PANTONE 627 C"])
        a = self.meta["spot_colour_authority"]
        self.assertEqual(a["state"], "UNRESOLVED_SPOT_COLOUR")
        self.assertEqual(a["governs"],
                         "THE_NAMED_SPOT_COLOUR_NOT_THE_PLACEHOLDER")

    def test_shade_label_zones_exist_one_per_pan(self):
        labels = [n for n, _ in self.graph["document"].walk()
                  if getattr(n, "name", "").startswith("shade_label_r")]
        self.assertEqual(len(labels), 12)

    def test_a_decorative_preference_cannot_become_structure(self):
        orn = self.intent.get("ornament")
        self.assertEqual(orn.constraint_level, di.DECORATIVE)
        with self.assertRaises(dg.PaletteGraphError) as ctx:
            dg._provenance(orn, "structure")
        self.assertIn("cannot drive a 'structure' node", str(ctx.exception))

    def test_the_display_box_is_linked_not_merged(self):
        link = self.graph["packaging_link"]
        self.assertFalse(link["merged_into_palette"])
        self.assertEqual(link["linked_target"], "packaging")
        names = {getattr(n, "name", "") for n, _ in
                 self.graph["document"].walk()}
        self.assertFalse(any("box" in n or "carton" in n for n in names))

    def test_it_refuses_to_invent_a_missing_field(self):
        bare = di.PaletteDesignIntent(concept_reference="empty")
        with self.assertRaises(dg.PaletteGraphError) as ctx:
            dg.build_palette_design_graph(bare, self.tray)
        self.assertIn("will not invent", str(ctx.exception))

    # --- serialization / versioning / editing / reconstruction ---------

    def test_it_serializes_and_reconstructs_to_the_same_identity(self):
        blob = dg.serialize(self.graph)
        back = dg.deserialize(blob)
        self.assertEqual(back["graph_identity"], self.graph["graph_identity"])
        self.assertEqual(back["node_count"], self.graph["node_count"])
        self.assertEqual(back["relationship_count"],
                         self.graph["relationship_count"])

    def test_serialization_is_deterministic(self):
        self.assertEqual(dg.serialize(self.graph), dg.serialize(self.graph))

    def test_editing_produces_a_new_version_and_leaves_the_original(self):
        edited = dg.edit_text(self.graph, "wordmark_outer_glow",
                              "OUTER GLOW DELUXE")
        self.assertEqual(edited["graph_version"],
                         self.graph["graph_version"] + 1)
        self.assertNotEqual(edited["graph_identity"],
                            self.graph["graph_identity"])
        original = [n.text for n, _ in self.graph["document"].walk()
                    if getattr(n, "type", "") == "text"]
        self.assertIn("OUTER GLOW", original)
        self.assertNotIn("OUTER GLOW DELUXE", original)

    def test_editing_an_unknown_node_is_refused(self):
        with self.assertRaises(dg.PaletteGraphError):
            dg.edit_text(self.graph, "wordmark_nope", "x")

    def test_a_foreign_schema_is_refused(self):
        with self.assertRaises(dg.PaletteGraphError):
            dg.deserialize('{"schema": "something_else/1.0"}')

    def test_it_is_not_emission_ready(self):
        self.assertFalse(self.graph["emission_ready"])
        self.assertFalse(self.graph["owner_approved"])
        self.assertEqual(self.graph["manufacturing_authority"],
                         "NOT_ESTABLISHED")


class ElevenMetricFidelityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intent = OC.confirmed_intent()
        cls.tray = _tray()
        cls.graph = dg.build_palette_design_graph(cls.intent, cls.tray)
        cls.report = fid.score_palette_fidelity(cls.intent, cls.tray,
                                                graph=cls.graph)

    def test_the_eleven_named_metrics_are_all_present(self):
        want = {"PAN_SHAPE_FIDELITY", "PAN_COUNT_FIDELITY", "GRID_FIDELITY",
                "RELATIVE_PAN_PROPORTION_FIDELITY",
                "INTER_PAN_SPACING_FIDELITY", "OUTER_MARGIN_FIDELITY",
                "CASE_PROPORTION_FIDELITY",
                "LID_BASE_RELATIONSHIP_FIDELITY", "ARTWORK_ZONE_FIDELITY",
                "TYPOGRAPHY_HIERARCHY_FIDELITY", "COLOUR_ZONE_FIDELITY"}
        self.assertEqual({m[0] for m in fid.METRICS}, want)
        self.assertEqual(len(self.report["metrics"]), 11)

    def test_the_report_leads_with_the_five_required_breakdowns(self):
        for key in ("discriminating_metrics_passed",
                    "discriminating_metrics_failed",
                    "metrics_excluded_from_the_score",
                    "metrics_with_excessive_tolerance_headroom",
                    "metrics_guaranteed_by_construction"):
            self.assertIn(key, self.report)

    def test_no_perfect_aggregate_is_presented_without_the_caveat(self):
        self.assertIn("Read the discriminating split",
                      self.report["weighted_score_caveat"])
        self.assertIn("discriminating metrics pass", self.report["headline"])

    def test_a_metric_that_cannot_fail_is_excluded_from_discriminating(self):
        self.assertIn("OUTER_MARGIN_FIDELITY",
                      self.report["passes_by_construction"])
        self.assertNotIn("OUTER_MARGIN_FIDELITY",
                         self.report["discriminating_metrics_passed"])

    def test_unbuilt_geometry_is_unmeasurable_not_a_pass(self):
        row = next(r for r in self.report["metrics"]
                   if r["metric"] == "LID_BASE_RELATIONSHIP_FIDELITY")
        self.assertEqual(row["verdict"], fid.UNMEASURABLE)
        self.assertIn("PALT-M4B-B", row["why"])
        self.assertIn("LID_BASE_RELATIONSHIP_FIDELITY",
                      self.report["metrics_excluded_from_the_score"])

    def test_the_confirmed_design_is_realised_by_the_built_geometry(self):
        self.assertEqual(self.report["discriminating_metrics_failed"], [])

    def test_a_wrong_grid_fails_the_discriminating_metrics(self):
        wrong = rt.build_rect_recessed_tray(
            {"cells_x": 3, "cells_y": 3, "tray_width_mm": 90.0,
             "tray_depth_mm": 70.0})
        report = fid.score_palette_fidelity(self.intent, wrong,
                                            graph=self.graph)
        self.assertIn("PAN_COUNT_FIDELITY",
                      report["discriminating_metrics_failed"])
        self.assertIn("GRID_FIDELITY",
                      report["discriminating_metrics_failed"])
        self.assertFalse(report["all_discriminating_metrics_passed"])

    def test_dropping_a_colour_reference_fails_colour_zone_fidelity(self):
        thin = dg.build_palette_design_graph(self.intent, self.tray)
        thin["document"].metadata["named_colour_references"] = \
            ["PANTONE 621 C"]
        report = fid.score_palette_fidelity(self.intent, self.tray,
                                            graph=thin)
        self.assertIn("COLOUR_ZONE_FIDELITY",
                      report["discriminating_metrics_failed"])

    def test_no_calibrated_photographic_accuracy_is_claimed(self):
        self.assertFalse(self.report["pixel_overlay_computed"])
        self.assertFalse(
            self.report["calibrated_photographic_accuracy_claimed"])
        self.assertIn("visual similarity to the source image",
                      self.report["does_not_measure"])
