"""Phase 2A-8 native Illustrator handoff tests (§16).

Serialization determinism, safe escaping, layer taxonomy, semantic-group
survival, swatch/spot contracts, live typography, artwork census, script
safety and the task-50 golden handoff regression.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase

from apps.ire.compose_vector_art import VectorArtStyle, compose_vector_art_graph
from apps.ire.handoff.graph_schema import (
    ROOT_LAYERS,
    canonical_hash,
    serialize_handoff_graph,
)
from apps.ire.handoff.jsx_emitter import emit_design_handoff_jsx
from apps.ire.handoff.package import (
    _painted_swatch_names,
    build_handoff_package,
    validate_handoff,
)

from apps.pipeline.tests.test_selected_concept_fidelity import (
    SELECTED_VARIATION,
    _spec,
)

BARLOW = {"name": "BarlowCondensed-Bold",
          "path": "/Users/symow/Desktop/bbrose-systemOS/materials/Fonts/"
                  "3333/BarlowCondensed-Bold.ttf"}


def _golden_doc():
    from apps.dielines.geometry.engine import calculate_dieline
    from apps.dielines.validators.schema import DielineInputJSON
    params = DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.35,
                      "thickness_compensation": True},
        metadata={"product_name": "Baked Powder",
                  "product_type": "face powder"})
    coords = calculate_dieline(params)
    spec = {**_spec(), "confirmed_font": dict(BARLOW)}
    return compose_vector_art_graph(
        coords, style=VectorArtStyle.for_variation(SELECTED_VARIATION,
                                                   seed=50),
        product_name="Baked Powder", subtitle="face powder",
        concept_spec=spec)


class SerializationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = _golden_doc()
        cls.graph = serialize_handoff_graph(cls.doc, task_id=50)

    def test_deterministic_graph_and_jsx(self):
        again = serialize_handoff_graph(self.doc, task_id=50)
        assert canonical_hash(again) == canonical_hash(self.graph)
        assert emit_design_handoff_jsx(again) == \
            emit_design_handoff_jsx(self.graph)

    def test_no_volatile_or_forbidden_content(self):
        payload = json.dumps(self.graph)
        for forbidden in ("materials/", "prompt", "anthropic", "openai",
                          "api_key", "raw_response"):
            assert forbidden not in payload.lower(), forbidden

    def test_safe_escaping_of_text(self):
        from apps.ire.graph import Color, TextRun
        run = TextRun(name='evil"; alert(1); //', text='"\\</script> ',
                      x=1, y=1, size_pt=10,
                      color=Color(r=0, g=0, b=0))
        self.doc.root.children[-1].children.append(run)
        try:
            graph = serialize_handoff_graph(self.doc, task_id=50)
            jsx = emit_design_handoff_jsx(graph)
            assert " " not in jsx          # ensure_ascii escapes it
            assert 'alert(1); //"' not in jsx.split("var HANDOFF")[0]
        finally:
            self.doc.root.children[-1].children.pop()

    def test_script_safety_contract(self):
        jsx = emit_design_handoff_jsx(self.graph)
        for forbidden in ("eval(", "Socket", "system(", "app.system",
                          "File.execute", "XMLHttpRequest"):
            assert forbidden not in jsx, forbidden
        # asset lookup is bounded to ./assets next to the script
        assert 'parent.fsName + "/assets/"' in jsx


class LayerTaxonomyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = serialize_handoff_graph(_golden_doc(), task_id=50)

    def test_all_root_layers_declared_in_order(self):
        assert tuple(self.graph["root_layers"]) == ROOT_LAYERS

    def test_semantic_groups_survive_with_no_anonymous_collapse(self):
        tree = self.graph["layer_tree"]
        front_groups = {key for key in tree["05_PANEL_ARTWORK"]
                        if key.startswith("front-artwork/")
                        or key.startswith("FRONT/")}
        assert {"front-artwork/constellation-core",
                "front-artwork/constellation-drift"} <= front_groups
        assert "FRONT/logo-frame" in tree["05_PANEL_ARTWORK"]
        assert "side_right-artwork/panel-continuation" in \
            tree["05_PANEL_ARTWORK"]
        assert all("unnamed-group" not in key
                   for layer in tree.values() for key in layer)
        # §4: each panel's artwork wrapper carries ONE registered clip
        clip_prefixes = {tuple(c["group_path"])
                         for c in self.graph["panel_clips"]}
        assert ("front-artwork",) in clip_prefixes

    def test_technical_separation(self):
        tree = self.graph["layer_tree"]
        assert tree["01_DIELINE_CUT"] == {"cut": 1}
        assert sum(tree["02_DIELINE_FOLD"].values()) >= 4
        assert sum(tree["00_REFERENCE_NONPRINTING"].values()) >= 5
        assert sum(tree["03_BLEED_SAFE_GUIDES"].values()) == 1
        for obj in self.graph["objects"]:
            if obj["layer"] in ("00_REFERENCE_NONPRINTING",
                                "03_BLEED_SAFE_GUIDES",
                                "14_TECHNICAL_NOTES"):
                assert obj["printable"] is False

    def test_finish_layers_carry_spot_tags_not_process_decoration(self):
        finish_objects = [obj for obj in self.graph["objects"]
                          if obj["layer"].startswith(("10_", "11_", "12_",
                                                      "13_"))]
        assert finish_objects
        for obj in finish_objects:
            assert obj["finish"] in ("SPOT_UV", "EMBOSS", "DEBOSS",
                                     "ROSE_GOLD_FOIL")
            assert obj["fill"] is None      # outline mask, never painted


class SwatchContractTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = serialize_handoff_graph(_golden_doc(), task_id=50)

    def test_named_process_swatches_exist_without_duplicates(self):
        names = [s["name"] for s in self.graph["process_swatches"]]
        assert len(names) == len(set(names))
        assert {"WARM_IVORY_BASE", "BLUSH_PINK", "DUSTY_PINK_TYPE",
                "ROSE_GOLD_PLACEHOLDER", "SOFT_PEACH_PARTICLES",
                "SOFT_MINT_WASH", "WARM_GREY_SUPPORTING_TEXT",
                "WHITE_TYPE_HIGHLIGHT"} <= set(names)
        assert not any(name.endswith(("-1", "copy", "2")) for name in names)

    def test_finish_and_technical_spots_exist(self):
        spots = {s["name"] for s in self.graph["spot_swatches"]}
        assert spots == {"CUT", "CREASE", "SPOT_UV", "EMBOSS", "DEBOSS",
                         "ROSE_GOLD_FOIL"}

    def test_gradients_reference_named_swatches(self):
        for obj in self.graph["objects"]:
            fill = obj.get("fill")
            if fill and fill["type"] == "gradient":
                for stop in fill["stops"]:
                    assert stop["swatch"]


class TypographyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = serialize_handoff_graph(_golden_doc(), task_id=50)
        cls.texts = {o["name"]: o for o in cls.graph["objects"]
                     if o["type"] == "text"}

    def test_barlow_requested_explicitly_and_text_live(self):
        assert self.texts["product-name-line-1"]["font_postscript"] == \
            "BarlowCondensed-Bold"
        assert self.texts["product-name-line-2"]["font_postscript"] == \
            "BarlowCondensed-Bold"
        assert all(o["live"] for o in self.texts.values())

    def test_rotated_spanish_copy_preserved(self):
        vertical = self.texts["vertical-copy"]
        assert vertical["text"] == "POLVO HORNEADO"
        assert vertical["rotation_deg"] == -90.0

    def test_missing_font_aborts_atomically_before_any_document(self):
        """§1: every face resolves BEFORE documents.add; a missing face
        returns HANDOFF_FONT_UNAVAILABLE with no partial document."""
        jsx = emit_design_handoff_jsx(self.graph)
        assert "HANDOFF_FONT_UNAVAILABLE" in jsx
        preflight = jsx.index("HANDOFF_FONT_UNAVAILABLE")
        create = jsx.index("app.documents.add")
        assert preflight < create
        # the abort path never reaches document creation (guarded else)
        assert "} else {" in jsx[preflight:create]
        # never outline, never substitute
        assert "createOutline" not in jsx


class PackageAndValidatorTests(TestCase):
    def test_package_and_validator_roundtrip(self):
        doc = _golden_doc()
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        package = build_handoff_package(
            doc, out, task_id=50,
            production_blockers=("MISSING_OUTPUT_INTENT",))
        for name in ("design_handoff.jsx", "design_graph.json",
                     "handoff_manifest.json"):
            assert (Path(out) / name).exists()
        manifest = package["manifest"]
        assert manifest["production_blockers"] == ["MISSING_OUTPUT_INTENT"]
        assert manifest["fonts"] == ["BarlowCondensed-Bold",
                                     "NotoSans-Regular"]
        # This comment used to read: "without a real Illustrator run the
        # ONLY code is the required-verification marker". That was true
        # until H020 added the orphan-plate direction, and it is now false:
        # the golden package also ships a DEBOSS spot swatch that no
        # printable object paints with. Kept as an exact-equality assertion
        # (not `in`) so a THIRD code cannot appear unnoticed.
        codes = validate_handoff(doc, package["graph"])
        assert codes == ["HANDOFF_ORPHAN_SPOT_SWATCH: DEBOSS",
                         "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"]

    def test_real_summary_clears_or_names_specific_codes(self):
        doc = _golden_doc()
        graph = serialize_handoff_graph(doc, task_id=50)
        good = {"executed": True, "status": "OK",
                "layers": len(graph["root_layers"]),
                "textFrames": graph["object_census"].get("text", 0),
                "errors": [], "missingFonts": []}
        # A clean Illustrator run used to clear this to []. It no longer
        # does, and the residue is a FINDING about the golden artwork, not
        # about the validator: task-50 defines a DEBOSS plate and paints
        # nothing with it. Recorded here rather than silenced, because the
        # honest fix is upstream in the artwork (drop the plate or use it),
        # and task-50's package is a pinned regression artefact.
        assert validate_handoff(doc, graph,
                                illustrator_summary=good) == [
            "HANDOFF_ORPHAN_SPOT_SWATCH: DEBOSS"]
        missing_font = {**good, "status": "ILLUSTRATOR_FONT_MISSING",
                        "missingFonts": ["BarlowCondensed-Bold"]}
        codes = validate_handoff(doc, graph,
                                 illustrator_summary=missing_font)
        assert any(code.startswith("HANDOFF_FONT_MISSING")
                   for code in codes)

    def test_golden_layer_tree_hash_is_stable(self):
        doc = _golden_doc()
        dir_a = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dir_a, True)
        dir_b = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dir_b, True)
        out_a = build_handoff_package(doc, dir_a, task_id=50)
        out_b = build_handoff_package(doc, dir_b, task_id=50)
        assert out_a["hashes"] == out_b["hashes"]


class OrphanSpotSwatchTests(TestCase):
    """H020 — the ORPHAN direction of the spot-swatch contract.

    A spot swatch that is DEFINED (and therefore created in Illustrator by
    the emitter) but that nothing prints with is an empty separation plate.
    The pre-existing check only covered the MISSING direction.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = _golden_doc()
        cls.graph = serialize_handoff_graph(cls.doc, task_id=50)

    def _orphan_codes(self, graph):
        return [c for c in validate_handoff(self.doc, graph)
                if c.startswith("HANDOFF_ORPHAN_SPOT_SWATCH")]

    def test_golden_artwork_defines_a_plate_it_never_paints(self):
        """The finding, asserted directly: DEBOSS is defined and unused.

        Not a synthetic case — this is the real task-50 handoff package.
        """
        assert self._orphan_codes(self.graph) == [
            "HANDOFF_ORPHAN_SPOT_SWATCH: DEBOSS"]
        # and it is genuinely DEFINED, i.e. the emitter will create it
        assert "DEBOSS" in {s["name"] for s in self.graph["spot_swatches"]}

    def test_no_orphan_reported_once_the_plate_is_painted(self):
        """The check must not fire on a document that uses every plate."""
        painted = dict(self.graph, objects=list(self.graph["objects"]) + [
            {"id": "path-9001", "name": "deboss-mask", "type": "path",
             "layer": "12_FINISH_DEBOSS", "panel": "FRONT",
             "group_path": ["DEBOSS"], "printable": True, "visible": True,
             "locked": False, "finish": "DEBOSS", "opacity": 1.0}])
        assert self._orphan_codes(painted) == []

    def test_non_printable_reference_object_does_not_count_as_painted(self):
        """A non-printing halo referencing a plate leaves it empty.

        This is the branch that separates "referenced anywhere" from
        "actually prints" — the golden fixture does not discriminate the
        two, so it is pinned here instead.
        """
        ghost = dict(self.graph, objects=list(self.graph["objects"]) + [
            {"id": "path-9002", "name": "deboss-halo", "type": "path",
             "layer": "00_REFERENCE_NONPRINTING", "panel": "",
             "group_path": ["readability-halos"], "printable": False,
             "visible": True, "locked": False, "finish": "DEBOSS",
             "opacity": 1.0}])
        assert self._orphan_codes(ghost) == [
            "HANDOFF_ORPHAN_SPOT_SWATCH: DEBOSS"]

    def test_a_spot_used_only_as_a_fill_is_not_an_orphan(self):
        """Fill-carried spots must not be reported as unused.

        No spot swatch is fill-carried in the golden artwork, so this
        breadth is deliberate rather than measured — and therefore tested.
        """
        filled = dict(self.graph, objects=list(self.graph["objects"]) + [
            {"id": "rect-9003", "name": "deboss-panel", "type": "rect",
             "layer": "12_FINISH_DEBOSS", "panel": "FRONT",
             "group_path": ["DEBOSS"], "printable": True, "visible": True,
             "locked": False, "finish": "", "opacity": 1.0,
             "fill": {"type": "solid", "swatch": "DEBOSS", "opacity": 1.0}}])
        assert self._orphan_codes(filled) == []
        # ... and via a gradient stop, the other fill shape
        gradient = dict(self.graph, objects=list(self.graph["objects"]) + [
            {"id": "rect-9004", "name": "deboss-fade", "type": "rect",
             "layer": "12_FINISH_DEBOSS", "panel": "FRONT",
             "group_path": ["DEBOSS"], "printable": True, "visible": True,
             "locked": False, "finish": "", "opacity": 1.0,
             "fill": {"type": "gradient", "kind": "linear", "stops": [
                 {"offset": 0.0, "swatch": "DEBOSS", "opacity": 1.0}]}}])
        assert self._orphan_codes(gradient) == []

    def test_live_text_carries_its_swatch_flat_and_still_counts(self):
        """The route the first version of the helper missed.

        Text is the only object type whose colour is NOT nested under
        fill/stroke — the serializer sets `swatch` directly on the record.
        An earlier version of this test asserted these objects contributed
        NOTHING, which pinned the bug as intended behaviour; a spot ink used
        only for type would have been reported as an unused plate.
        """
        keyless = [o for o in self.graph["objects"]
                   if "stroke" not in o and "fill" not in o]
        assert len(keyless) == 4
        assert all(o["type"] == "text" for o in keyless)
        # every one carries a flat swatch, and the helper now reads it
        assert all(o.get("swatch") for o in keyless)
        assert _painted_swatch_names({"objects": keyless}) == {
            o["swatch"] for o in keyless}

    def test_a_spot_used_only_by_live_text_is_not_an_orphan(self):
        """End-to-end guard against the false orphan D1 would have caused."""
        typed = dict(self.graph, objects=list(self.graph["objects"]) + [
            {"id": "text-9005", "name": "deboss-wordmark", "type": "text",
             "layer": "07_LIVE_TYPOGRAPHY", "panel": "FRONT",
             "group_path": ["product-name"], "printable": True,
             "visible": True, "locked": False, "finish": "", "opacity": 1.0,
             "text": "BBROSE", "live": True, "swatch": "DEBOSS"}])
        assert self._orphan_codes(typed) == []

    def test_helper_is_safe_on_absent_and_null_shapes(self):
        """`stroke`/`fill` may be absent OR explicitly serialized None."""
        assert _painted_swatch_names(
            {"objects": [{"printable": True, "stroke": None, "fill": None}]}
        ) == set()
        assert _painted_swatch_names({"objects": [{"printable": True}]}) \
            == set()
        assert _painted_swatch_names({}) == set()
