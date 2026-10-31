"""Phase 2B-2 slice 4 — three-state selected-concept fidelity.

Measures the emitted Document against the visual graph: a known target that is
satisfied PASSES, a known target that is violated (or a motif the native field
cannot reproduce) FAILS, and a MISSING target is UNMEASURED — never an
auto-pass. A MEASURED_FAIL is a reconstruction blocker.
"""
from __future__ import annotations

import pytest

from apps.ire import container_fidelity as cf
from apps.ire.compose_container import (
    compose_container_graph,
    container_design_graph_record,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_visual_graph as cvg
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

fitz = pytest.importorskip("fitz")


def _doc(name_lines=("Rose Nectar",), product_name="Rose Nectar"):
    bb = build_backbone(ContainerProfile(archetype="bottle", height_mm=110,
                                         width_mm=40))
    zones = cc.propose_zones(cc.build_inferred_profile("bottle"))
    return compose_container_graph(
        bb, product_name=product_name, name_lines=list(name_lines),
        zones=zones, native=True), zones


def _vg(**field_overrides):
    fields = {
        "logo_zone": {"value": None, "verification": cc.MISSING},
        "product_name_zone": {"value": None, "verification": cc.MISSING},
        "motif_family": {"value": None, "verification": cc.MISSING},
    }
    fields.update(field_overrides)
    return {"schema_version": cvg.SCHEMA, "fields": fields}


def test_first_pass_name_present_everything_else_unmeasured():
    doc, _ = _doc()
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"])
    assert rep["axes"]["product_name_presence"]["state"] == cf.MEASURED_PASS
    # no record → logo / name-zone / motif are UNMEASURED, never auto-pass
    assert rep["axes"]["logo"]["state"] == cf.UNMEASURED
    assert rep["axes"]["motif_family"]["state"] == cf.UNMEASURED
    # VQR-2A §6 fail-closed: a pass + unmeasured required axes can no
    # longer produce MEASURED_PASS — absence of evidence is never success
    assert rep["overall"] == cf.UNMEASURED_BLOCKING
    assert rep["blocking_unmeasured"]
    assert rep["failures"] == []


def test_missing_name_run_is_measured_fail():
    doc, _ = _doc(name_lines=(), product_name="")     # no name emitted at all
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"])
    # name was required but not emitted
    assert rep["axes"]["product_name_presence"]["state"] == cf.MEASURED_FAIL
    assert cf.PRODUCT_NAME_TOO_SMALL in rep["failures"]


def test_motif_family_is_deferred_to_the_motif_engine():
    # 2B-2A: the base fidelity engine no longer judges motif family — the
    # dedicated container_motif_fidelity engine measures the emitted motif
    # GEOMETRY. Here the motif axis is UNMEASURED (not double-counted).
    doc, _ = _doc()
    vg = _vg(motif_family={"value": "powder_constellation",
                           "verification": cc.VERIFIED})
    rep = cf.measure_fidelity(doc, vg, name_lines=["Rose Nectar"])
    assert rep["axes"]["motif_family"]["state"] == cf.UNMEASURED
    assert cf.MOTIF_FAMILY_MISMATCH not in rep["failures"]


def test_logo_axis_is_unmeasured_not_passed_when_a_logo_is_emitted_against_a_zone():
    """§BH50(f)(5): this test asserted MEASURED_PASS on presence alone until
    the ruling — an upper-left target, a centred logo, and a pass. A logo is
    emitted; its zone is not compared here, so the axis is UNMEASURED naming
    the target, blocking at acceptance, and the quant axis compares it."""
    doc, _ = _doc()
    doc.metadata["logo_zone_used"] = "front-controlled-fallback"
    vg = _vg(logo_zone={"value": "upper left", "verification": cc.VERIFIED})
    rep = cf.measure_fidelity(doc, vg, name_lines=["Rose Nectar"],
                              census={"logo_rasters": 1})
    assert rep["axes"]["logo"]["state"] == cf.UNMEASURED
    assert "upper left" in rep["axes"]["logo"]["detail"]
    assert "not compared" in rep["axes"]["logo"]["detail"]
    assert "logo" in rep["blocking_unmeasured"]


def test_the_name_zone_passes_only_when_compared_and_equal():
    """§BH50(f)(5): a centred target against centred runs is a compared PASS;
    a right-hand target against centred runs is UNMEASURED naming the token
    (no NEW rule-4 failure: rule-4 failures block the reconstruction); the
    left-against-centred failure stays; a left target with NO name run no
    longer passes on an empty list."""
    doc, _ = _doc()
    centred = _vg(product_name_zone={"value": "centered column",
                                     "verification": cc.VERIFIED})
    rep = cf.measure_fidelity(doc, centred, name_lines=["Rose Nectar"])
    assert rep["axes"]["product_name_zone"]["state"] == cf.MEASURED_PASS
    assert "equal" in rep["axes"]["product_name_zone"]["detail"]
    right = _vg(product_name_zone={"value": "right column",
                                   "verification": cc.VERIFIED})
    rep = cf.measure_fidelity(doc, right, name_lines=["Rose Nectar"])
    assert rep["axes"]["product_name_zone"]["state"] == cf.UNMEASURED
    assert "right column" in rep["axes"]["product_name_zone"]["detail"]
    assert cf.PRODUCT_NAME_ZONE_MISMATCH not in rep["failures"]
    left = _vg(product_name_zone={"value": "left column",
                                  "verification": cc.VERIFIED})
    rep = cf.measure_fidelity(doc, left, name_lines=["Rose Nectar"])
    assert rep["axes"]["product_name_zone"]["state"] == cf.MEASURED_FAIL
    assert cf.PRODUCT_NAME_ZONE_MISMATCH in rep["failures"]
    empty, _ = _doc(name_lines=(), product_name="")
    rep = cf.measure_fidelity(empty, left, name_lines=["Rose Nectar"])
    assert rep["axes"]["product_name_zone"]["state"] == cf.UNMEASURED


def test_logo_axis_fails_when_target_present_but_none_emitted():
    doc, _ = _doc()
    doc.metadata["logo_zone_used"] = ""
    vg = _vg(logo_zone={"value": "upper left", "verification": cc.VERIFIED})
    rep = cf.measure_fidelity(doc, vg, name_lines=["Rose Nectar"],
                              census={"logo_rasters": 0})
    assert rep["axes"]["logo"]["state"] == cf.MEASURED_FAIL
    assert cf.LOGO_ZONE_MISMATCH in rep["failures"]


def test_the_wrap_axis_is_not_applicable_on_a_product_with_no_wrapped_surface():
    """§BH50(f)(6)/(5): given the zone record, the wrap axis takes the seam
    check's applicability — NOT_APPLICABLE with its reason on a bottle, counted
    apart and never blocking; UNMEASURED and blocking on a jar's BODY_WRAP;
    UNMEASURED as before when no zone record is given. The report states what
    its unmeasured axes block."""
    doc, zones = _doc()
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"], zones=zones)
    wrap = rep["axes"]["wrap_alignment"]
    assert wrap["state"] == cf.NOT_APPLICABLE and "BODY_FRONT" in wrap["detail"]
    assert wrap["required"] is True
    assert "wrap_alignment" not in rep["blocking_unmeasured"]
    assert rep["counts"]["not_applicable"] == 1
    assert rep["overall"] == cf.UNMEASURED_BLOCKING      # the other axes
    assert rep["blocking_scope"] == "ACCEPTANCE"
    jar = cc.propose_zones(cc.build_inferred_profile("jar"))
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"], zones=jar)
    assert rep["axes"]["wrap_alignment"]["state"] == cf.UNMEASURED
    assert "wrap_alignment" in rep["blocking_unmeasured"]
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"])
    assert rep["axes"]["wrap_alignment"]["state"] == cf.UNMEASURED
    assert rep["counts"]["not_applicable"] == 0
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"], zones=[])
    assert rep["axes"]["wrap_alignment"]["state"] == cf.UNMEASURED
    assert "no zone record" in rep["axes"]["wrap_alignment"]["detail"]


def test_unmeasured_never_counts_as_failure():
    doc, _ = _doc()
    rep = cf.measure_fidelity(doc, _vg(), name_lines=["Rose Nectar"])
    assert rep["counts"]["unmeasured"] >= 3
    assert rep["counts"]["measured_fail"] == 0
    assert rep["fidelity_code"] == ""


def test_front_back_roles_distinct_on_normal_emission():
    doc, _ = _doc()                        # front name, no back motif
    fb = cf.measure_front_back(doc)
    assert fb["roles_distinct"] is True and fb["front_is_hero"] is True


def test_front_back_collapse_when_back_carries_hero_motif():
    # a hero motif emitted on the back surface is a real role collapse (§6)
    from apps.ire.graph import Document, Group, TextRun
    from apps.ire.graph import Color as _C
    ink = _C.from_hex("#000000")
    doc = Document(page_w=210, page_h=297, root=Group(
        name="Artwork", role="artwork", children=[
            TextRun(name="product-name-0", text="X", x=1, y=1, size_pt=12, color=ink),
            Group(name="motif-BODY_BACK", role="decoration", children=[])]))
    fb = cf.measure_front_back(doc)
    assert fb["roles_distinct"] is False and fb["back_has_hero_motif"] is True



# [His test blocker on design 122 at reconstruction, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md): "the concept sets "Rose
# Blossom" small inside its oval window. The picture's layout wins (my rule): draw the name at the size the concept shows,
# as long as it's readable and above the print floor. Tell me which old rule refused it and retire it for fronts drawn
# from their concept." ... "FRONT/BACK RELATIONSHIP: find what this check wants ... Make the check and the new back area
# agree, for every form."] MEASURED: 122's 149 drew "Rose Blossom" at 14.27 pt as a plain line (the name was only ever
# the whole "Rose Blossom Hand Cream"), so this check found no name and the front no hero.

def _drawn(*kids, from_its_concept=True):
    from apps.ire.graph import Document, Group
    doc = Document(page_w=210, page_h=297, root=Group(name="Artwork", role="artwork", children=list(kids)))
    if from_its_concept:
        doc.metadata["map_front"] = {"drawn": [], "name_traced": None}
    return doc


def _run(name, size_pt):
    from apps.ire.graph import Color, TextRun
    return TextRun(name=name, text="Rose Blossom", x=1, y=1, size_pt=size_pt, color=Color.from_hex("#B3122E"))


def test_his_122_a_front_drawn_from_its_concept_takes_its_name_at_the_concepts_size_above_the_print_floor():
    """The 8 pt the ruled block's hierarchy set (VQR-2A) is retired for a front drawn from its concept: its name passes
    at the size the concept shows it down to the print floor every line of it is set on, and is refused below it; a
    front the drawing lays out itself keeps its 8 pt."""
    from apps.ire.compose_container import MAP_TYPE_FLOOR_PT
    assert cf.name_floor_pt(_drawn()) == MAP_TYPE_FLOOR_PT < 8.0
    assert cf.name_floor_pt(_drawn(from_its_concept=False)) == 8.0
    for size_pt, state in ((MAP_TYPE_FLOOR_PT + 0.5, cf.MEASURED_PASS), (MAP_TYPE_FLOOR_PT - 0.5, cf.MEASURED_FAIL)):
        rep = cf.measure_fidelity(_drawn(_run("product-name-hero-0", size_pt)), _vg(), name_lines=["Rose Blossom"])
        assert rep["axes"]["product_name_presence"]["state"] == state, (size_pt, rep["axes"]["product_name_presence"])
    rep = cf.measure_fidelity(_drawn(_run("product-name-hero-0", MAP_TYPE_FLOOR_PT + 0.5), from_its_concept=False),
                              _vg(), name_lines=["Rose Blossom"])
    assert rep["axes"]["product_name_presence"]["state"] == cf.MEASURED_FAIL


def test_his_122_the_front_back_check_wants_the_hero_on_the_front_and_never_its_motif_on_the_back():
    """What the check wants: the hero on the front — its name, or its motif — and never the hero motif on the back. A
    front drawn from its concept carries its motif under the map's own names (122's "lineart-map-0 …"), and that is the
    hero as "motif-front" is; the back grown to the front's area carries no motif of its own, so the two agree."""
    from apps.ire.graph import Group
    motif = Group(name="motif-map-front", role="decoration", children=[
        Group(name="lineart-map-0 red hairline rose and leaf engraving all-over", role="decoration", children=[])])
    assert cf.measure_front_back(_drawn(motif))["roles_distinct"] is True
    assert cf.measure_front_back(_drawn(_run("front-descriptor-0-0", 14.27)))["front_is_hero"] is False
    assert cf.measure_front_back(_drawn(_run("product-name-hero-0", 14.27)))["roles_distinct"] is True
    back = Group(name="motif-BODY_BACK", role="decoration", children=[])
    assert cf.measure_front_back(_drawn(motif, back))["roles_distinct"] is False


def test_goal_1011_script_a_traced_name_spelling_the_start_of_the_records_name_is_the_name():
    """[His test blocker on design 124, 2026-10-11, with his rule on 122 at reconstruction: "draw the name at the size
    the concept shows"] 124's lid sets "Enchanted Rose" of the record's "Enchanted Rose Palette", traced at 35 pt in
    Great Vibes: the hierarchy check reads it as the name — it asked for the whole name, measured the sheet's 12.6 pt
    title instead and refused the drawing. One word that is not the whole name is never the name; nor another's."""
    from apps.ire.container_fidelity import spells_the_name
    from apps.ire.container_motif_fidelity import PRODUCT_NAME_TOO_SMALL, validate_typography_hierarchy
    from apps.ire.graph import ClosePath, Color, Document, Group, LineTo, MoveTo, Path, SolidFill, TextRun
    assert spells_the_name("Enchanted Rose", "Enchanted Rose Palette")
    assert spells_the_name("Enchanted Rose Palette", "Enchanted Rose Palette")
    assert not spells_the_name("Enchanted", "Enchanted Rose Palette")
    assert not spells_the_name("Rose Palette", "Enchanted Rose Palette")
    assert not spells_the_name("", "Enchanted Rose Palette")

    def drawn(words, size):
        ink = Color.from_hex("#D2A475")
        name = Path(name="product-name-traced", fill=SolidFill(color=ink),
                    segments=[MoveTo(x=10, y=10), LineTo(x=60, y=10), LineTo(x=60, y=20), ClosePath()])
        runs = [TextRun(name="front-line-1", text="Eyeshadow Palette", x=10, y=30, size_pt=17.55, color=ink),
                TextRun(name="sheet-title", text="ENCHANTED ROSE PALETTE", x=10, y=2, size_pt=12.63, color=ink)]
        doc = Document(page_w=200.0, page_h=130.0, title="lid", root=Group(name="Artwork", children=[name] + runs))
        doc.metadata["map_front"] = {"name_traced": {"words": words, "size_pt": size}}
        return doc
    assert validate_typography_hierarchy(drawn("Enchanted Rose", 35.02), "Enchanted Rose Palette")["failures"] == []
    small = validate_typography_hierarchy(drawn("Enchanted Rose", 15.0), "Enchanted Rose Palette")
    assert small["axes"]["product_name"]["code"] == PRODUCT_NAME_TOO_SMALL                   # still measured: too small
    other = validate_typography_hierarchy(drawn("Rose", 35.02), "Enchanted Rose Palette")
    assert other["failures"]                                                              # one word: never the name
