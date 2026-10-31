"""Design Graph schema — the central pipeline contract (Phase 0, 2026-07-08).

Pins the two properties every downstream stage relies on: the graph
round-trips losslessly through JSON (so it can be persisted, versioned, and
handed between VUE / resolver / IRE / emitters), and its discriminated
unions parse back to the right concrete node types.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.ire.graph import (
    AssetRef,
    Barcode,
    Color,
    CubicTo,
    Document,
    GradientFill,
    GradientStop,
    Group,
    Image,
    LineTo,
    MoveTo,
    Path,
    Rect,
    SolidFill,
    Stroke,
    TextRun,
)


def _doc() -> Document:
    rose = Color.from_hex("#C97B2E")
    cream = Color.from_hex("#EFE9E4")
    return Document(
        page_w=140.0, page_h=175.0, title="unit",
        root=Group(name="Artwork", role="artwork", children=[
            Group(name="Background", role="background", children=[
                Rect(name="ground", x=0, y=0, w=140, h=175,
                     fill=GradientFill(kind="radial", cx=70, cy=87, r=90, stops=[
                         GradientStop(offset=0.0, color=cream),
                         GradientStop(offset=1.0, color=rose),
                     ])),
            ]),
            Group(name="Label", role="label", children=[
                Path(name="frame", segments=[
                    MoveTo(x=10, y=10), LineTo(x=130, y=10),
                    CubicTo(x1=132, y1=12, x2=132, y2=14, x=130, y=16),
                    LineTo(x=10, y=16), LineTo(x=10, y=10),
                ], stroke=Stroke(color=rose, width_mm=0.5),
                    fill=SolidFill(color=cream)),
                TextRun(name="title", text="ROSÉ NECTAR", x=70, y=90,
                        size_pt=24, color=rose, align="center"),
                TextRun(name="ar", text="غلوس الشفاه", x=130, y=110,
                        size_pt=8, color=rose, align="right", rtl=True),
                Barcode(name="ean", symbology="ean13",
                        value="5061030634110", x=12, y=150, w=40, h=18),
            ]),
            Group(name="Decoration", role="decoration", children=[
                AssetRef(name="rose-motif", query="engraved rose",
                         x=20, y=20, w=30, h=30, recolor=rose),
                Image(name="interim-motif", src="/tmp/motif.png",
                      x=0, y=0, w=140, h=175),
            ]),
        ]),
    )


def test_round_trips_through_json_losslessly():
    doc = _doc()
    dumped = doc.model_dump_json()
    restored = Document.model_validate_json(dumped)
    assert restored.model_dump() == doc.model_dump()


def test_discriminated_unions_parse_to_concrete_types():
    doc = Document.model_validate_json(_doc().model_dump_json())
    label = doc.find_role("label")[0]
    kinds = {c.type for c in label.children}
    assert {"path", "text", "barcode"} <= kinds
    ean = next(c for c in label.children if c.type == "barcode")
    assert isinstance(ean, Barcode) and ean.symbology == "ean13"
    ref = next(c for c in doc.find_role("decoration")[0].children
               if c.type == "asset_ref")
    assert isinstance(ref, AssetRef) and ref.query == "engraved rose"


def test_walk_visits_every_node_with_parent():
    doc = _doc()
    nodes = list(doc.walk())
    assert nodes[0][1] is None                       # root has no parent
    title = next(n for n, _ in nodes if getattr(n, "name", "") == "title")
    parent = next(p for n, p in nodes if n is title)
    assert parent is not None and parent.role == "label"


def test_color_hex_helpers():
    assert Color.from_hex("#EFE9E4").to_hex() == "#EFE9E4"
    with pytest.raises(ValueError):
        Color.from_hex("#fff")


def test_gradient_requires_two_stops():
    with pytest.raises(ValidationError):
        GradientFill(stops=[GradientStop(offset=0.0, color=Color.from_hex("#000000"))])


def test_document_root_must_be_group():
    doc = Document(page_w=10, page_h=10, root=Group(name="r", role="artwork"))
    assert doc.root.type == "group"


# ---- §BH32(d)(i): RTL is detected by script on every text run at composition.

def _run(text, **kw):
    from apps.ire.graph import TextRun, Color
    return TextRun(name="t", text=text, x=0, y=0, size_pt=8,
                   color=Color(r=0, g=0, b=0), **kw)


def test_an_arabic_run_is_rtl_without_the_producer_setting_anything():
    assert _run("رحيق الورد").rtl is True


def test_a_latin_run_is_not_rtl_and_digits_decide_nothing():
    assert _run("ROSE NECTAR").rtl is False
    assert _run("2026-09-04").rtl is False          # no strong character
    assert _run("").rtl is False


def test_the_first_strong_character_decides_a_mixed_run():
    assert _run("رحيق الورد — ROSE NECTAR").rtl is True
    assert _run("ROSE NECTAR — رحيق الورد").rtl is False
    assert _run("12 رحيق").rtl is True               # leading digits are neutral


def test_an_explicit_flag_from_a_producer_is_kept_as_its_declaration():
    assert _run("ROSE", rtl=True).rtl is True
    assert _run("رحيق", rtl=False).rtl is False


def test_a_run_validated_from_a_dict_without_the_flag_is_detected_too():
    from apps.ire.graph import TextRun
    d = _run("رحيق").model_dump()
    d.pop("rtl")
    assert TextRun.model_validate(d).rtl is True
    assert _run("رحيق").model_dump()["rtl"] is True   # always a bool after validation


def test_composition_yields_rtl_runs_for_an_arabic_product_name():
    import apps.pipeline.tests.test_container_font_authority as T
    ns = vars(T)
    bb = ns["build_backbone"](ns["ContainerProfile"](archetype="bottle", height_mm=110, width_mm=40))
    zones = ns["cc"].propose_zones(ns["cc"].build_inferred_profile("bottle"))
    doc = ns["compose_container_graph"](bb, product_name="رحيق الورد",
                                        name_lines=["رحيق الورد", "ROSE NECTAR"], zones=zones, native=True)
    runs = [(n.text, n.rtl) for n, _ in doc.walk() if n.type == "text"]
    assert any(text == "رحيق الورد" and rtl is True for text, rtl in runs)
    assert any(text == "ROSE NECTAR" and rtl is False for text, rtl in runs)
    assert all(isinstance(rtl, bool) for _, rtl in runs)   # no producer left it unset


def test_split_script_runs_keeps_neutral_characters_with_their_neighbours():
    from apps.ire.text_script import split_script_runs, scripts_in
    assert split_script_runs("رحيق 12 ROSE") == [("arabic", "رحيق 12 "), ("latin", "ROSE")]
    assert split_script_runs("12 رحيق") == [("arabic", "12 رحيق")]
    assert split_script_runs("2026") == [("neutral", "2026")]
    assert scripts_in("رحيق ROSE") == {"arabic", "latin"}



def test_a_document_that_carries_no_finish_dumps_without_the_key():
    """§BH65(c)2: the new vocabulary is omitted from every dump when unset, so no design-graph hash and no serialised
    graph identity moves for a document that does not use it."""
    dumped = _doc().model_dump_json()
    assert '"finishes"' not in dumped
    assert Document.model_validate_json(dumped).model_dump_json() == dumped


def test_a_finish_round_trips_through_the_dump():
    from apps.ire.graph import Finish
    doc = _doc()
    doc.root.children[0].finishes = [Finish(kind="foil", plate="FOIL_ROSE_GOLD", appearance=Color.from_hex("#C9A24B")),
                                     Finish(kind="emboss", plate="EMBOSS")]
    back = Document.model_validate_json(doc.model_dump_json())
    assert back.root.children[0].finishes == doc.root.children[0].finishes
    assert back.model_dump_json() == doc.model_dump_json()



def test_a_pattern_fill_round_trips_and_a_solid_one_dumps_as_before():
    from apps.ire.graph import PatternFill
    doc = _doc()
    filled = next(n for n, _ in doc.walk() if hasattr(n, "fill"))
    filled.fill = PatternFill(kind="lines", color=Color.from_hex("#8B2E3C"), spacing_mm=0.8, angle_deg=32.0)
    back = Document.model_validate_json(doc.model_dump_json())
    assert next(n for n, _ in back.walk() if n.name == filled.name).fill == filled.fill
    assert '"pattern"' not in _doc().model_dump_json()



def test_a_blend_mode_round_trips_and_is_absent_from_a_dump_that_does_not_use_it():
    doc = _doc()
    assert '"blend_mode"' not in doc.model_dump_json()
    doc.root.blend_mode = "multiply"
    back = Document.model_validate_json(doc.model_dump_json())
    assert back.root.blend_mode == "multiply"



def test_an_opacity_mask_round_trips_and_is_absent_when_unused():
    from apps.ire.graph import OpacityMask
    doc = _doc()
    assert '"opacity_mask"' not in doc.model_dump_json()
    doc.root.opacity_mask = OpacityMask(kind="radial", cx=10, cy=10, r=5, start_opacity=1.0, end_opacity=0.2)
    back = Document.model_validate_json(doc.model_dump_json())
    assert back.root.opacity_mask == doc.root.opacity_mask



def test_a_shadow_round_trips_and_is_absent_when_unused():
    from apps.ire.graph import Shadow
    doc = _doc()
    assert '"shadow"' not in doc.model_dump_json()
    doc.root.shadow = Shadow(color=Color.from_hex("#5A2C3A"), blur_mm=1.0)
    assert Document.model_validate_json(doc.model_dump_json()).root.shadow == doc.root.shadow



def test_tracking_and_case_round_trip_and_are_absent_when_unused():
    doc = _doc()
    dumped = doc.model_dump_json()
    assert '"tracking_em"' not in dumped and '"text_case"' not in dumped
    run = next(n for n, _ in doc.walk() if n.type == "text")
    run.tracking_em, run.text_case = 0.12, "upper"
    back = next(n for n, _ in Document.model_validate_json(doc.model_dump_json()).walk() if n.type == "text")
    assert (back.tracking_em, back.text_case, back.text) == (0.12, "upper", run.text)



def test_a_fill_rule_round_trips_and_is_absent_from_a_dump_that_does_not_use_it():
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." The mark drawn from its approved vector master prints by the
    nonzero rule, and the Path says so; every other path says nothing, so no existing graph's dump — and no hash of
    it — moves."""
    doc = _doc()
    dumped = doc.model_dump_json()
    assert '"fill_rule"' not in dumped
    path = next(n for n, _ in doc.walk() if n.type == "path")
    assert path.fill_rule is None
    path.fill_rule = "nonzero"
    back = Document.model_validate_json(doc.model_dump_json())
    assert next(n for n, _ in back.walk() if n.type == "path").fill_rule == "nonzero"
    with pytest.raises(ValidationError):
        Path(segments=[MoveTo(x=0, y=0)], fill_rule="winding")
