"""Phase 2B-4 — Product Container native Illustrator handoff.

Golden fixtures per archetype + the task-#51-shaped human-rejection fixture.
No provider call anywhere; everything deterministic."""
from __future__ import annotations

import json

from apps.ire import container_motif as cm
from apps.ire.compose_container import compose_container_graph
from apps.ire.handoff.container_adapter import (
    CONTAINER_HANDOFF_SCHEMA,
    CONTAINER_ROOT_LAYER_ORDER,
    HUMAN_REJECTION_LABEL,
    build_container_handoff_package,
    canonical_container_hash,
    serialize_container_handoff_graph,
    validate_container_handoff,
)
from apps.ire.handoff.jsx_emitter import emit_design_handoff_jsx
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

_STRUCT = {
    "verified": True, "variation_id": "C_DEWDROP_CONSTELLATION",
    "title": "Dewdrop Constellation",
    "motif_signature": "dewdrop constellation, droplets in three size classes",
    "composition_signature": "asymmetric vertical",
}


def _spec(archetype="bottle", variant="slim", w=35.0, d=25.0, h=95.0,
          rejected=False, separations=True):
    rec = cc.merge_user_profile(
        cc.build_inferred_profile(archetype, variant),
        {"body_width_mm": w, "body_depth_mm": d, "body_height_mm": h})
    zones = cc.propose_zones(rec)
    spec = {
        "backend": "container", "product_name": "Rosé Nectar",
        "sku": "BBR-CO-410",
        "container_profile/1.0": rec,
        "container_decoration_zones/1.0": {
            "zones": zones, "zone_set_hash": cc.zone_set_hash(zones)},
        "container_confirmation": {"combined_hash": "abc123"},
        "container_reconstruction": {"status": "RECONSTRUCTED",
                                     "blockers": []},
        "container_selected_variation/1.0": {
            "variation_id": "C_DEWDROP_CONSTELLATION"},
    }
    if separations:
        spec["container_production_separations/1.0"] = {
            "separation_set_hash": "sep123",
            "separations": [
                {"name": "PROCESS_ARTWORK", "method_type": "SCREEN_PRINT",
                 "classification": "PROCESS", "printable": True},
                {"name": "SCREEN_INK_1", "method_type": "SCREEN_PRINT",
                 "classification": "SPOT", "printable": True,
                 "zones": ["z_front"]},
                {"name": "BOTTOM_CODE", "method_type": "BOTTOM_INKJET_CODE",
                 "classification": "TECHNICAL", "printable": True,
                 "zones": ["z_bottom_code"]}],
            "swatches": [
                {"name": "SCREEN_INK_1", "classification": "SPOT",
                 "hex": "#AA5566", "value": "TECHNICAL_PLACEHOLDER"},
                {"name": "BOTTOM_CODE", "classification": "TECHNICAL"}]}
    if rejected:
        spec["container_2b3v_final_status/1.0"] = {
            "gate2_human_acceptance": "REJECTED",
            "blocking_codes": ["HUMAN_GATE2_VISUAL_REJECTION"]}
        spec["container_reconstruction_rejected/2"] = {"label": "REJECTED"}
    return spec, rec, zones


def _doc(spec, rec, zones, transparency=True):
    fields = rec["fields"]
    bb = build_backbone(ContainerProfile(
        archetype=rec["archetype"], variant=rec.get("variant") or "",
        width_mm=fields["body_width_mm"]["value"],
        height_mm=fields["body_height_mm"]["value"]))
    ms = cm.build_motif_spec(_STRUCT, {"fields": {}}, zones, rec)
    return compose_container_graph(
        bb, product_name="Rosé Nectar", name_lines=["Rosé Nectar"],
        zones=zones, native=True, motif_spec=ms,
        colors={"cap": "#F2C4CE", "product": "#F7DDE3"},
        transparency={"state": "TRANSPARENT", "product_color": "#F7DDE3"}
        if transparency else None)


def _graph(archetype="bottle", variant="slim", **kw):
    spec, rec, zones = _spec(archetype, variant, **kw)
    doc = _doc(spec, rec, zones)
    return spec, doc, serialize_container_handoff_graph(doc, spec, task_id=1)


# --- golden layer trees per archetype -----------------------------------------

def test_bottle_golden_layers_surfaces_and_census():
    spec, doc, g = _graph("bottle", "slim")
    assert g["schema_version"] == CONTAINER_HANDOFF_SCHEMA
    # deterministic order, only applicable layers (§3)
    assert g["root_layers"] == [x for x in CONTAINER_ROOT_LAYER_ORDER
                                if x in g["root_layers"]]
    assert "08_CAP_ARTWORK" not in g["root_layers"]     # no cap zone proposed
    assert "01_CONTAINER_PROFILE" in g["root_layers"]
    assert g["panel_sublayer_map"]["05_FRONT_ARTWORK"] == ["BODY_FRONT"]
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (8): "No empty grey blocks in the files"] a back with no copy
    # handed over draws no placeholder panel, so its artwork layer holds nothing and is not listed
    assert "06_BACK_ARTWORK" not in g["panel_sublayer_map"]
    assert not any(o["layer"] == "06_BACK_ARTWORK" for o in g["objects"])
    # the BOTTOM_CODE separation note keeps the plate layer present even
    # though the generic bottle proposal has no bottom zone
    assert "20_BOTTOM_CODE" in g["root_layers"]
    # transparent wall + product fill live on separate layers (§7)
    walls = [o for o in g["objects"] if o["layer"] == "03_BASE_CONTAINER"
             and "container-wall" in o["group_path"]]
    fills = [o for o in g["objects"] if o["layer"] == "04_PRODUCT_FILL"]
    assert walls and fills
    assert validate_container_handoff(doc, g, spec) == []
    # dewdrop motif groups preserved (§13)
    motif = [o for o in g["objects"] if any(
        p.startswith("dewdrop-") for p in o["group_path"])]
    assert motif
    assert g["object_census"].get("image", 0) == 0      # no logo asset in test


def test_jar_and_tube_golden_surfaces():
    spec, doc, g = _graph("jar", "standard", w=70, d=70, h=60)
    assert "07_SIDE_WRAP_ARTWORK" in g["root_layers"] \
        or "06_BACK_ARTWORK" not in g["root_layers"]
    spec, doc, g = _graph("tube", "slim", w=35, d=35, h=140)
    # crimp code zone genuinely applies to squeeze tubes
    assert "20_BOTTOM_CODE" in g["root_layers"]
    assert validate_container_handoff(doc, g, spec) == []


def test_determinism_same_inputs_same_hashes():
    _, doc1, g1 = _graph("bottle", "slim")
    _, doc2, g2 = _graph("bottle", "slim")
    assert canonical_container_hash(g1) == canonical_container_hash(g2)
    assert emit_design_handoff_jsx(g1) == emit_design_handoff_jsx(g2)


# --- opening state + separations ----------------------------------------------

def test_opening_state_hides_plates_and_technical_layers():
    _, _, g = _graph("bottle", "slim")
    hidden = set(g["default_hidden_layers"])
    for name in ("01_CONTAINER_PROFILE", "02_DECORATION_ZONES",
                 "14_SCREEN_INKS", "20_BOTTOM_CODE", "22_TECHNICAL_NOTES"):
        if name in g["root_layers"]:
            assert name in hidden, name
    for name in ("03_BASE_CONTAINER", "04_PRODUCT_FILL", "05_FRONT_ARTWORK",
                 "09_LIVE_TYPOGRAPHY"):
        assert name not in hidden, name


def test_separations_deduped_and_process_artwork_excluded():
    _, _, g = _graph("bottle", "slim")
    seps = g["separations_included"]
    assert "PROCESS_ARTWORK" not in seps
    assert len(seps) == len(set(seps))
    assert "SCREEN_INK_1" in seps and "BOTTOM_CODE" in seps


# --- §16 human rejection authority ---------------------------------------------

def test_rejected_output_manifest_carries_human_rejection_label(tmp_path):
    spec, rec, zones = _spec(rejected=True)
    doc = _doc(spec, rec, zones)
    from apps.ire.container_production_readiness import human_design_acceptance
    human = human_design_acceptance(spec)
    pkg = build_container_handoff_package(
        doc, spec, str(tmp_path), task_id=51, human_acceptance=human,
        readiness_codes=["HUMAN_VISUAL_ACCEPTANCE_REQUIRED"])
    m = pkg["manifest"]
    assert m["handoff_label"] == HUMAN_REJECTION_LABEL
    assert m["human_visual_acceptance_state"] == "REJECTED / REVISION_REQUIRED"
    assert m["production_ready"] is False
    assert "HUMAN_VISUAL_ACCEPTANCE_REQUIRED" in m["production_blockers"] \
        or "HUMAN_VISUAL_ACCEPTANCE_REQUIRED" in m["production_readiness_codes"]
    # package files written
    for f in ("design_handoff.jsx", "design_graph.json",
              "handoff_manifest.json", "concept_sheet_preview.pdf",
              "production_separations_manifest.json"):
        assert (tmp_path / f).exists(), f
    # no font binaries, no concept-reference sources
    names = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert not any(n.lower().endswith((".ttf", ".otf")) for n in names)


def test_execution_success_never_clears_human_rejection(tmp_path):
    spec, rec, zones = _spec(rejected=True)
    doc = _doc(spec, rec, zones)
    from apps.ire.container_production_readiness import (
        build_readiness, human_design_acceptance)
    human = human_design_acceptance(spec)
    build_container_handoff_package(
        doc, spec, str(tmp_path), task_id=51, human_acceptance=human,
        readiness_codes=[])
    # even a hypothetical EXECUTED_OK state cannot change the readiness verdict
    report = build_readiness(spec)
    assert report["ready"] is False
    assert report["blocking_codes"][0] == "HUMAN_VISUAL_ACCEPTANCE_REQUIRED"


# --- validator + security ------------------------------------------------------

def test_crimp_on_rigid_bottle_flagged():
    spec, doc, g = _graph("bottle", "slim")
    g2 = dict(g, panel_sublayers=list(g["panel_sublayers"]) + ["CRIMP_ZONE"])
    codes = validate_container_handoff(doc, g2, spec)
    assert "HANDOFF_CRIMP_ON_RIGID_CONTAINER" in codes


def test_missing_live_text_flagged():
    spec, doc, g = _graph("bottle", "slim")
    g2 = dict(g, objects=[o for o in g["objects"]
                          if o["layer"] != "09_LIVE_TYPOGRAPHY"])
    codes = validate_container_handoff(doc, g2, spec)
    assert "HANDOFF_LIVE_TEXT_MISSING" in codes


def test_jsx_is_bounded_and_data_driven():
    _, _, g = _graph("bottle", "slim")
    jsx = emit_design_handoff_jsx(g)
    for forbidden in ("eval(", "system(", "app.system", "XMLHttpRequest",
                      "Socket(", "execute("):
        assert forbidden not in jsx, forbidden
    assert "var HANDOFF = " in jsx
    # user text cannot escape into executable JSX: the payload is one JSON
    # literal line
    payload = [line for line in jsx.splitlines()
               if line.startswith("var HANDOFF = ")][0]
    json.loads(payload[len("var HANDOFF = "):].rstrip(";"))


# --- 2B-4-CORR-1: spot inventory + manifest census integrity -------------------

def test_spot_separation_produces_spot_inventory(tmp_path):
    spec, rec, zones = _spec()
    doc = _doc(spec, rec, zones)
    from apps.ire.container_production_readiness import human_design_acceptance
    pkg = build_container_handoff_package(
        doc, spec, str(tmp_path), task_id=1,
        human_acceptance=human_design_acceptance(spec), readiness_codes=[])
    m = pkg["manifest"]
    # counts equal inventory lengths (census invariant, §2)
    assert m["spot_swatch_count"] == len(m["spot_swatches"]) == 1
    assert m["technical_swatch_count"] == len(m["technical_swatches"]) == 1
    assert m["process_swatch_count"] == len(m["process_swatches"])
    assert m["separation_count"] == len(m["separation_inventory"]) == 2
    assert m["printable_separation_count"] == 2
    assert m["spot_swatches"] == ["SCREEN_INK_1"]
    assert m["technical_swatches"] == ["BOTTOM_CODE"]
    # spot never zero when SPOT separations exist
    assert m["spot_swatch_count"] > 0


def test_missing_spot_swatch_fails():
    spec, doc, g = _graph()
    g2 = dict(g, spot_swatches=[])
    codes = validate_container_handoff(doc, g2, spec)
    assert any(c.startswith("HANDOFF_SPOT_COLOR_MISSING") for c in codes)
    assert any(c.startswith("HANDOFF_MANIFEST_CENSUS_INACCURATE")
               for c in codes)


def test_orphan_and_duplicate_spots_fail():
    spec, doc, g = _graph()
    extra = dict(g["spot_swatches"][0], name="UNUSED_SPOT")
    g2 = dict(g, spot_swatches=g["spot_swatches"] + [extra])
    codes = validate_container_handoff(doc, g2, spec)
    assert any(c.startswith("HANDOFF_ORPHAN_SPOT_SWATCH") for c in codes)
    g3 = dict(g, spot_swatches=g["spot_swatches"] * 2)
    codes = validate_container_handoff(doc, g3, spec)
    assert "HANDOFF_DUPLICATE_SPOT_SWATCH" in codes


def test_process_colours_not_conflated_with_spots():
    spec, doc, g = _graph()
    assert all(s["classification"] == "SPOT" for s in g["spot_swatches"])
    process_names = {s["name"] for s in g["process_swatches"]}
    assert not process_names & {s["name"] for s in g["spot_swatches"]}


# --- THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
# switch the mark to it so gold foil can print." — the mark drawn from an approved vector master, handed off. Every
# master here is a SYNTHETIC fixture (apps/ire/tests/brand_mark_fixtures.py); the owner's trace is never placed. -----

def _marked_graph():
    from apps.ire import brand_mark as B
    from apps.ire.tests import brand_mark_fixtures as FX
    spec, rec, zones = _spec("bottle", "slim")
    fields = rec["fields"]
    bb = build_backbone(ContainerProfile(
        archetype=rec["archetype"], variant=rec.get("variant") or "",
        width_mm=fields["body_width_mm"]["value"], height_mm=fields["body_height_mm"]["value"]))
    master = B.read_master(FX.POTRACE_STYLE)
    doc = compose_container_graph(
        bb, product_name="Rosé Nectar", name_lines=["Rosé Nectar"], zones=zones, native=True,
        motif_spec=cm.build_motif_spec(_STRUCT, {"fields": {}}, zones, rec),
        colors={"cap": "#F2C4CE", "product": "#F7DDE3"}, logo_master=master)
    return spec, doc, master, serialize_container_handoff_graph(doc, spec, task_id=1)


def test_bh69_the_mark_is_handed_off_on_the_brand_layer_as_one_path_carrying_its_fill_rule():
    spec, doc, master, g = _marked_graph()
    marks = [o for o in g["objects"] if o["name"] == "logo"]
    assert len(marks) == 1
    mark = marks[0]
    assert (mark["type"], mark["layer"], mark["group_path"], mark["fill_rule"]) == (
        "path", "10_BRAND", ["logo"], "nonzero")
    assert sum(1 for s in mark["segments"] if s[0] == "M") == master.census["subpaths"] == 5
    assert g["object_census"].get("image", 0) == 0
    assert all("fill_rule" not in o for o in g["objects"] if o["name"] != "logo")
    assert validate_container_handoff(doc, g, spec) == []


def test_bh69_only_a_graph_carrying_a_fill_rule_gets_the_compound_path_runtime():
    """TRAP: the runtime draws every subpath of a path as its own item, so the mark's counters would fill black. The
    compound-path branch is injected into THAT script only; a script whose graph carries no fill rule is the runtime
    exactly as it was — and so is its jsx_hash."""
    from apps.ire.handoff import jsx_emitter as J
    _, _, plain = _graph("bottle", "slim")
    plain_jsx = emit_design_handoff_jsx(plain)
    assert plain_jsx.endswith(J._RUNTIME.replace("/*__VERIFICATION_BLOCK__*/", ""))
    assert "buildCompound" not in plain_jsx
    _, _, _, marked = _marked_graph()
    jsx = emit_design_handoff_jsx(marked)
    assert jsx.count("container.compoundPathItems.add()") == 1
    assert 'if (obj.type === "path" && obj.fill_rule) {' in jsx
    assert "applyCompound(buildCompound(container, obj), obj);" in jsx


_ILLUSTRATOR_MOCK = r"""
// the smallest Illustrator DOM the handoff runtime touches — every collection's add() makes a recorded item
function Coll(kind) { this.kind = kind; this.items = []; this.length = 0; }
Coll.prototype.add = function () { var it = makeItem(this.kind); this.items.push(it); this[this.length] = it;
    this.length = this.items.length; return it; };
Coll.prototype.getByName = function (n) { for (var i = 0; i < this.items.length; i++) {
    if (this.items[i].name === n) { return this.items[i]; } } throw new Error("no " + n); };
Coll.prototype.rectangle = function () { return this.add(); };
Coll.prototype.pointText = function () { var t = this.add(); t.textRange = {characterAttributes: {},
    paragraphAttributes: {}}; t.geometricBounds = [0, 0, 1, 1]; t.rotate = function () {};
    t.translate = function () {}; return t; };
function makeItem(kind) {
    var it = {kind: kind, name: "", layers: new Coll("layer"), groupItems: new Coll("group"),
              pathItems: new Coll("path"), compoundPathItems: new Coll("compound"),
              textFrames: new Coll("text"), placedItems: new Coll("placed"), pathPoints: new Coll("point"),
              gradientStops: new Coll("stop"), pageItems: {length: 0}};
    it.setEntirePath = function (pts) { this.pathPoints = new Coll("point");
        for (var i = 0; i < pts.length; i++) { this.pathPoints.add(); } };
    it.remove = function () {}; it.rotate = function () {};
    return it;
}
var DOC = makeItem("document");
DOC.swatches = new Coll("swatch"); DOC.spots = new Coll("spot"); DOC.gradients = new Coll("gradient");
var app = {documents: {add: function () { return DOC; }}, textFonts: {getByName: function (n) { return {name: n}; }},
           userInteractionLevel: 0};
var UserInteractionLevel = {DONTDISPLAYALERTS: 1}, DocumentColorSpace = {CMYK: 1},
    CoordinateSystem = {ARTBOARDCOORDINATESYSTEM: 1}, ColorModel = {SPOT: 1}, PointType = {SMOOTH: 1, CORNER: 2},
    Justification = {CENTER: 1, RIGHT: 2}, GradientType = {RADIAL: 1, LINEAR: 2}, Transformation = {CENTER: 1};
function CMYKColor() {} function SpotColor() {} function GradientColor() {}
var $ = {fileName: "/nowhere/design_handoff.jsx"};
function File(p) { this.exists = false; this.parent = {fsName: "/nowhere"}; }
"""

_ILLUSTRATOR_DUMP = r"""
function dump(it) {
    var out = {kind: it.kind, name: it.name, filled: it.filled, evenodd: it.evenodd, opacity: it.opacity,
               points: it.pathPoints ? it.pathPoints.length : 0, children: []};
    var colls = [it.layers, it.groupItems, it.compoundPathItems, it.pathItems, it.textFrames, it.placedItems];
    for (var c = 0; c < colls.length; c++) { for (var i = 0; i < colls[c].items.length; i++) {
        out.children.push(dump(colls[c].items[i])); } }
    return out;
}
console.log(JSON.stringify({report: report, doc: dump(DOC)}));
"""


def _run_in_node(tmp_path, jsx):
    import shutil
    import subprocess
    import pytest
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the runtime is only read, not run")
    harness = tmp_path / "harness.js"
    harness.write_text(_ILLUSTRATOR_MOCK + jsx + _ILLUSTRATOR_DUMP)
    run = subprocess.run([node, str(harness)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


def _find(tree, pred, out=None):
    out = [] if out is None else out
    if pred(tree):
        out.append(tree)
    for child in tree["children"]:
        _find(child, pred, out)
    return out


def test_bh69_the_runtime_run_draws_the_mark_as_one_compound_path_whose_counters_are_its_members(tmp_path):
    """The script, RUN (in node, against the smallest mocked Illustrator DOM the runtime touches — Illustrator itself
    is not on this machine, so ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED stands): the mark arrives as ONE compound
    path whose members are its five outlines — the block, its two counters, the ring and its hole — each filled by
    the nonzero rule; no member of it is drawn as a path of its own. The control, the same graph with the fill rule
    taken off, draws five separate filled paths: the counters black."""
    _, _, master, g = _marked_graph()
    result = _run_in_node(tmp_path, emit_design_handoff_jsx(g))
    assert result["report"]["errors"] == []
    compounds = _find(result["doc"], lambda n: n["kind"] == "compound")
    assert [(c["name"], len(c["children"])) for c in compounds] == [("logo", master.census["subpaths"])]
    assert all(m["kind"] == "path" and m["filled"] is True and m["evenodd"] is False
               for m in compounds[0]["children"])
    assert compounds[0]["opacity"] == 100
    loose = _find(result["doc"], lambda n: n["kind"] == "path" and n["name"] == "logo")
    assert len(loose) == master.census["subpaths"]                  # every one of them inside the compound
    control = json.loads(json.dumps(g))
    for obj in control["objects"]:
        obj.pop("fill_rule", None)
    (tmp_path / "control").mkdir()
    result = _run_in_node(tmp_path / "control", emit_design_handoff_jsx(control))
    assert _find(result["doc"], lambda n: n["kind"] == "compound") == []
    assert len(_find(result["doc"], lambda n: n["kind"] == "path" and n["name"] == "logo"
                     and n["filled"] is True)) == master.census["subpaths"]
