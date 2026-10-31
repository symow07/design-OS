"""Container concept-sheet composer → editable .ai (Phase B2, 2026-07-08).

Verifies the flagged-exceptions standard with a real PDF parser: the
container STRUCTURE (silhouette, colour zones, product name, SKU, swatches)
is native editable vector, and the ONLY rasters are the explicitly-supplied,
grouped exceptions (reference photo / label / logo). With none supplied the
sheet is fully vector.
"""
from __future__ import annotations

import pytest

from apps.ire.compose_container import compose_container_graph
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import Group, Image
from apps.ire.rasterize import pdf_to_png
from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone

fitz = pytest.importorskip("fitz")


def _png(tmp_path, name, color=(210, 180, 190)):
    from PIL import Image as PILImage
    p = tmp_path / name
    PILImage.new("RGB", (200, 200), color).save(p)
    return str(p)


def _backbone(archetype="bottle"):
    return build_backbone(ContainerProfile(archetype=archetype,
                                           height_mm=110, width_mm=40))


def test_structure_is_native_vector_with_no_rasters_when_no_assets(tmp_path):
    doc = compose_container_graph(
        _backbone(), product_name="Rose Nectar", sku="LG-6410-E",
        colors={"body": "#EAD7D2", "cap": "#C9A24B"})
    out = emit_pdf_ai(doc, str(tmp_path / "c.ai"))
    page = fitz.open(out)[0]
    text = page.get_text()
    assert "ROSE NECTAR" in text                 # title (live text)
    assert "SKU: LG-6410-E" in text              # native spec text
    assert "BODY #EAD7D2" in text and "CAP #C9A24B" in text  # swatch labels
    assert len(page.get_drawings()) > 3          # silhouette + cap + swatches
    assert page.get_images() == []               # fully vector, zero rasters


def test_supplied_assets_are_the_only_rasters(tmp_path):
    # distinct content so reportlab embeds three separate XObjects (identical
    # bytes would dedupe to one — correct, but not what this test asserts)
    ref = _png(tmp_path, "ref.png", (200, 100, 100))
    label = _png(tmp_path, "label.png", (100, 200, 100))
    logo = _png(tmp_path, "logo.png", (100, 100, 200))
    doc = compose_container_graph(
        _backbone(), reference_path=ref, label_path=label, logo_path=logo,
        product_name="Rose Nectar", sku="LG-6410-E")
    out = emit_pdf_ai(doc, str(tmp_path / "c.ai"))
    page = fitz.open(out)[0]
    # exactly the three flagged exceptions — nothing else raster
    assert len(page.get_images()) == 3
    # the reference is isolated + labelled, not presented as final artwork
    assert "REFERENCE — not final artwork" in page.get_text()


def test_reference_lives_in_its_own_labelled_group():
    doc = compose_container_graph(_backbone(), reference_path="/nope.png",
                                  product_name="X")
    ref_groups = [n for n, _ in doc.walk()
                  if isinstance(n, Group) and n.name == "Reference"]
    assert len(ref_groups) == 1
    # container structure lives in its own group, separate from the reference
    assert doc.find_role("product")


def test_missing_reference_degrades_to_a_placeholder_not_a_crash(tmp_path):
    doc = compose_container_graph(_backbone(), reference_path="/does/not/exist.png",
                                  product_name="X", sku="S1")
    out = emit_pdf_ai(doc, str(tmp_path / "c.ai"))
    page = fitz.open(out)[0]
    assert page.get_images() == []               # no ghost raster
    assert "REFERENCE" in page.get_text()


def _zones(archetype="bottle"):
    from apps.pipeline.services import container_contract as cc
    prof = cc.build_inferred_profile(archetype)
    return cc.propose_zones(prof)


def test_native_mode_places_no_raster_label(tmp_path):
    # 2B-2: native mode consumes zones and emits NATIVE decoration — the label
    # raster must never appear even when a label_path is supplied
    label = _png(tmp_path, "label.png", (100, 200, 100))
    doc = compose_container_graph(
        _backbone(), label_path=label, product_name="Rose Nectar",
        name_lines=["Rose Nectar"], zones=_zones(), native=True)
    # the decoration group is native vector, no Image inside it
    deco = [n for n, _ in doc.walk()
            if isinstance(n, Group) and n.role == "decoration"]
    assert deco, "a native decoration group must be emitted"
    assert not any(isinstance(c, Image) for c in deco[0].children)
    out = emit_pdf_ai(doc, str(tmp_path / "c.ai"))
    page = fitz.open(out)[0]
    assert "Rose Nectar" in page.get_text()          # native live name
    assert page.get_images() == []                   # zero rasters (no logo here)


def test_container_design_graph_record_counts_zero_decorative_rasters(tmp_path):
    from apps.ire.compose_container import container_design_graph_record
    ref = _png(tmp_path, "ref.png", (200, 100, 100))
    logo = _png(tmp_path, "logo.png", (100, 100, 200))
    zones = _zones()
    doc = compose_container_graph(
        _backbone(), reference_path=ref, logo_path=logo,
        product_name="Rose Nectar", name_lines=["Rose Nectar"],
        zones=zones, native=True)
    rec = container_design_graph_record(
        doc, zones_consumed=[z["zone_id"] for z in zones], mode="native")
    assert rec["mode"] == "native"
    assert rec["decorative_raster_count"] == 0        # §5 invariant
    assert rec["primitives"]["reference_rasters"] == 1
    assert rec["primitives"]["logo_rasters"] == 1
    assert rec["primitives"]["live_text"] >= 1
    assert rec["zones_consumed"]


@pytest.mark.parametrize("archetype", ["bottle", "jar", "tube"])
def test_all_three_archetypes_compose_and_emit(archetype, tmp_path):
    doc = compose_container_graph(_backbone(archetype), product_name="P", sku="S")
    out = emit_pdf_ai(doc, str(tmp_path / f"{archetype}.ai"))
    assert fitz.open(out).page_count == 1
    assert pdf_to_png(out, str(tmp_path / f"{archetype}.png"))   # PNG preview


# --- THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
# switch the mark to it so gold foil can print." The composer handed an approved vector master — a SYNTHETIC fixture
# (apps/ire/tests/brand_mark_fixtures.py); the owner's trace is never placed by a test. ---------------------------------

def _marked(tmp_path, master=None):
    from apps.ire import brand_mark as B
    from apps.ire.tests import brand_mark_fixtures as FX
    master = master or B.read_master(FX.POTRACE_STYLE)
    logo = _png(tmp_path, "logo.png", (100, 100, 200))                     # a raster on file too: the master wins
    doc = compose_container_graph(_backbone(), logo_path=logo, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=_zones(), native=True, logo_master=master)
    raster = compose_container_graph(_backbone(), logo_path=logo, product_name="Rose Nectar",
                                     name_lines=["Rose Nectar"], zones=_zones(), native=True)
    return doc, raster, master


def test_bh69_the_mark_is_placed_at_its_masters_ink_aspect_and_never_its_padded_viewbox(tmp_path):
    """TRAP: potrace's viewBox is the traced PNG's whole canvas, padded round the ink. The placed box takes the
    MASTER'S INK aspect (20/70 on the fixture), never the viewBox's (40/100) — the instrument that measures
    distortion agrees — and it keeps the width the raster gets: only the height is the master's."""
    from apps.ire import container_logo_metrics as clm
    from apps.ire.tests import brand_mark_fixtures as FX
    doc, raster, master = _marked(tmp_path)
    mark = next(n for n, _ in doc.walk() if n.name == "logo")
    png = next(n for n, _ in raster.walk() if n.name == "logo")
    assert (mark.type, png.type) == ("asset_ref", "image")
    assert abs(master.aspect - FX.POTRACE_INK_ASPECT) < 1e-12
    assert abs(mark.h / mark.w - FX.POTRACE_INK_ASPECT) < 1e-12
    assert abs(mark.h / mark.w - FX.POTRACE_VIEWBOX_ASPECT) > 0.1
    assert (mark.x, mark.w) == (png.x, png.w)
    record = clm.measure_logo_metrics(doc)
    assert record["materially_distorted"] is False
    assert record["placements"][0]["intrinsic_aspect"] == round(FX.POTRACE_INK_ASPECT, 6)


def test_bh69_the_front_keeps_out_of_the_masters_own_clear_space(tmp_path):
    """The keep-out is the mark's bottom edge plus 1.0 x ITS cap height — the master's band, measured on the master
    rasterised by the same instrument, never the PNG's 0.856667."""
    from apps.ire import brand_mark as B
    from apps.ire.compose_container import _front_keepout_y
    _doc, _raster, master = _marked(tmp_path)
    box = (10.0, 20.0, 30.0, 30.0 * master.aspect)
    band = B.cap_band(master)
    assert band is not None and band["canvas_px"][1] == B.CAP_BAND_RASTER_PX
    assert _front_keepout_y(box, "/no/such/logo.png", logo_master=master) == box[1] + box[3] + box[3] * band[
        "cap_ratio"]


def test_bh69_the_census_names_the_vector_mark_and_only_when_one_is_drawn(tmp_path):
    from apps.ire import brand_mark as B
    from apps.ire.compose_container import container_design_graph_record
    doc, raster, _master = _marked(tmp_path)
    rec = container_design_graph_record(doc, zones_consumed=[], mode="native")
    assert rec["primitives"]["logo_rasters"] == 0 and rec["primitives"]["logo_vector_marks"] == 1
    assert rec["logo_zone_used"] == B.ZONE_USED == doc.metadata["logo_zone_used"]
    assert rec["decorative_raster_count"] == 0
    plain = container_design_graph_record(raster, zones_consumed=[], mode="native")
    assert "logo_vector_marks" not in plain["primitives"]
    assert plain["logo_zone_used"] == "front-controlled-fallback"


_CHROME = ("sheet-title", "reference-label", "sku", "swatch-")


def _chrome_extents(doc):
    """Every one of the sheet's own words and swatches, as (name, x0, x1) in mm — by the composer's own estimate, read
    at the capitals' advance as the composer reads it."""
    from apps.ire.compose_container import name_width_estimate_mm
    out = []
    for node, _ in doc.walk():
        name = str(getattr(node, "name", "") or "")
        if not name.startswith(_CHROME):
            continue
        if getattr(node, "type", "") == "text":
            w = name_width_estimate_mm(node.text, node.size_pt, upper=True)
            x0 = node.x - (w / 2 if node.align == "center" else 0.0)
            out.append((name, x0, x0 + w))
        elif hasattr(node, "w"):
            out.append((name, node.x, node.x + node.w))
    return out


@pytest.mark.parametrize("archetype,height_mm,width_mm", [("pencil", 150.0, 7.0), ("pencil", 150.0, 8.0),
                                                           ("mascara", 120.0, 12.0), ("mascara", 125.0, 16.0),
                                                           ("tube", 200.0, 20.0)])
def test_bh70_the_sheets_own_words_stay_on_its_page(archetype, height_mm, width_mm):
    """§BH70(1): the sheet is 2.45 x the product's width while its title, reference label, SKU and swatches took their
    size from its height, so a slim tall product printed words off its own page — MEASURED at 7693828: a pencil lost its
    title's ends, its reference label's ends and its cap swatch; a mascara and a 20 x 200 tube (a form that was already
    here) their reference label's start and their cap swatch. Every one of them now stays on the page."""
    from apps.pipeline.targets.container import archetypes as A
    bb = build_backbone(ContainerProfile(archetype=archetype, variant=A.variants_of(archetype)[0][0],
                                         cap_style=A.closures_of(archetype)[0][0],
                                         height_mm=height_mm, width_mm=width_mm))
    doc = compose_container_graph(bb, colors={"body": "#D8BEB8", "cap": "#B76E79"}, product_name="Rose Glow",
                                  sku="BBR-1")
    extents = _chrome_extents(doc)
    assert {e[0] for e in extents} >= {"sheet-title", "reference-label", "sku", "swatch-body", "swatch-cap"}
    off = [(n, round(a, 2), round(b, 2)) for n, a, b in extents if a < 0.0 or b > doc.page_w]
    assert off == [], (archetype, width_mm, doc.page_w, off)


def test_bh70_a_sheet_that_fitted_is_drawn_exactly_as_before():
    """§BH70(1): a word keeps the size and the place the sheet has always given it wherever it fits — a 40 x 110 bottle's
    title, reference label, SKU and swatches are the formulas they were, to the number."""
    from apps.ire.compose_container import _sheet_layout
    bb = _backbone("bottle")
    doc = compose_container_graph(bb, colors={"body": "#D8BEB8", "cap": "#B76E79"}, product_name="Rose Glow",
                                  sku="BBR-1")
    layout = _sheet_layout(bb)
    k, (rx, _ry, rw, _rh) = layout["k"], layout["ref_box"]
    nodes = {str(n.name): n for n, _ in doc.walk() if str(getattr(n, "name", "") or "").startswith(_CHROME)}
    assert nodes["sheet-title"].size_pt == max(7.0, 20 * k)
    assert (nodes["reference-label"].x, nodes["reference-label"].size_pt) == (rx + rw / 2, max(3.0, 6 * k))
    assert nodes["sku"].size_pt == max(4.0, 8 * k)
    assert (nodes["swatch-cap"].x, nodes["swatch-cap"].w) == (rx + 46 * k, 16 * k)
    assert nodes["swatch-label-cap"].size_pt == max(2.5, 4.5 * k)


def _front_case(archetype, height_mm, width_mm):
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets.container import archetypes as A
    variant, closure = A.variants_of(archetype)[0][0], A.closures_of(archetype)[0][0]
    bb = build_backbone(ContainerProfile(archetype=archetype, variant=variant, cap_style=closure,
                                         height_mm=height_mm, width_mm=width_mm))
    record = cc.merge_user_profile(cc.build_inferred_profile(archetype, variant), {
        "archetype": archetype, "variant": variant, "cap_type": closure,
        "body_height_mm": height_mm, "body_width_mm": width_mm, "body_depth_mm": width_mm})
    return bb, cc.propose_zones(record)


@pytest.mark.parametrize("archetype,height_mm,width_mm", [("tin", 42.0, 42.0), ("sachet", 180.0, 125.0),
                                                           ("oval_stick", 124.0, 54.0), ("aerosol", 190.0, 45.0),
                                                           ("ampoule", 75.0, 11.0)])
def test_bh71_each_new_form_composes_into_its_own_zones_and_emits(archetype, height_mm, width_mm, tmp_path):
    """§BH71 PART 3: \"Add each as a shape the system can draw.\" Each new form, at its own starting size, composed
    natively into the zones its proposal offers, its name set, emitted to a one-page .ai and rasterised — and its
    drawn outline is its own builder's, never a bottle's."""
    bb, zones = _front_case(archetype, height_mm, width_mm)
    assert bb.archetype == archetype
    doc = compose_container_graph(bb, colors={"body": "#EAD7D2", "cap": "#C9A24B"}, product_name="Rose",
                                  sku="X", zones=zones, native=True)
    out = emit_pdf_ai(doc, str(tmp_path / ("%s.ai" % archetype)))
    assert fitz.open(out).page_count == 1
    assert pdf_to_png(out, str(tmp_path / ("%s.png" % archetype)))


@pytest.mark.parametrize("archetype,height_mm,width_mm,name", [("bottle", 60.0, 20.0, "Rosewaterglow"),
                                                                ("pencil", 150.0, 7.0, "Rose Glow")])
def test_bh70_a_name_its_front_would_cut_is_refused_never_drawn_cut(archetype, height_mm, width_mm, name):
    """§BH70(1) and his §BD(b), "A clipped brand name never ships": both fronts wrap the name inside the front zone and
    clip to it, so a word wider than the zone was drawn with both ends cut off — MEASURED at a9daa5d on a 20 mm bottle
    named "Rosewaterglow" and a 7 mm pencil named "Rose Glow". On the ruled front production draws, and on the
    decoration front, the composer now refuses by name and draws nothing."""
    from apps.ire.compose_container import NAME_WIDER_THAN_FRONT, NameWiderThanFront
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    bb, zones = _front_case(archetype, height_mm, width_mm)
    for hierarchy in (ruled_front_hierarchy(name, descriptor=None), None):
        with pytest.raises(NameWiderThanFront) as refused:
            compose_container_graph(bb, product_name=name, name_lines=[name], sku="X", zones=zones, native=True,
                                    hierarchy_lines=hierarchy)
        assert str(refused.value).startswith(NAME_WIDER_THAN_FRONT)
        assert refused.value.line_mm > refused.value.front_mm


def test_bh70_a_name_that_fits_its_front_is_drawn_whole():
    """§BH70(1): the refusal is only for a name the front would cut — a 20 mm bottle named "Rose Nectar" and a 12 mm
    pencil named "Rose Glow" are drawn with every word of the name, on the ruled front production draws."""
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    for archetype, height_mm, width_mm, name in (("bottle", 60.0, 20.0, "Rose Nectar"),
                                                  ("pencil", 150.0, 12.0, "Rose Glow")):
        bb, zones = _front_case(archetype, height_mm, width_mm)
        doc = compose_container_graph(bb, product_name=name, name_lines=[name], sku="X", zones=zones, native=True,
                                      hierarchy_lines=ruled_front_hierarchy(name, descriptor=None))
        drawn = " ".join(n.text for n, _ in doc.walk() if str(getattr(n, "name", "")).startswith("product-name-hero"))
        assert drawn.split() == name.split(), (archetype, drawn)


def test_bh70_a_name_whose_even_split_would_be_cut_is_set_in_lines_that_fit():
    """§BH70(1) and §BD(b): "Focus Pressed Powder" in spaced capitals splits evenly as "Focus Pressed / Powder", and at
    9 pt its first line is wider than a 28.8 mm front — the front's clip cut it (found by this commit's refusal, in the
    fixtures of test_vqr3_logo_metrics). The container front now fills its lines as far as each fits, at most three,
    every word kept; the shared `wrap_name`, which the lid's steps and the dropper also read, is unchanged."""
    from apps.ire.compose_container import fitting_name_lines, name_width_estimate_mm, wrap_name
    name, size_pt, room_mm, style = "Focus Pressed Powder", 9.0, 28.8 * 0.94, {"tracking_em": 0.15, "upper": True}
    balanced = wrap_name(name, size_pt, room_mm, **style)
    assert balanced == ["Focus Pressed", "Powder"]
    assert name_width_estimate_mm(balanced[0], size_pt, **style) > room_mm           # the defect, measured
    fitted = fitting_name_lines(name, size_pt, room_mm, **style)
    assert " ".join(fitted).split() == name.split() and len(fitted) <= 3
    assert all(name_width_estimate_mm(line, size_pt, **style) <= room_mm for line in fitted), fitted


def test_bh70_a_compacts_base_is_its_information_panel():
    """§BH70(1), item 7 of the list he was sent: the information panel was the surface NAMED BODY_BACK, so a compact's
    base — where its back print zone and its ingredients go — was drawn as a motif continuation. It is the surface the
    back print zone is on; a bottle's back stays its panel."""
    bb, zones = _front_case("compact", 95.0, 110.0)
    doc = compose_container_graph(bb, product_name="Rose", sku="X", zones=zones, native=True)
    assert doc.metadata["surface_inventory"]["BASE_BOTTOM"] == "readable_info"
    bb, zones = _front_case("bottle", 110.0, 40.0)
    doc = compose_container_graph(bb, product_name="Rose", sku="X", zones=zones, native=True)
    assert doc.metadata["surface_inventory"]["BODY_BACK"] == "readable_info"


def test_bh70_the_generic_front_copy_is_measured_across_against_the_confirmed_zone():
    """§BH70(1), item 5 of the list the owner was sent: every form but the dropper carried one front-copy code, "no fit
    instrument on this path". A line's width is its own at true size whatever rectangle it was laid into — the sheet
    draws the product at s = 1 — so the ruled front a bottle, a tube or a lipstick is drawn with is measured across by
    the dropper's own instrument against its confirmed zone's safe area: a descriptor too wide for it is caught, one
    that fits holds, and the height says why it is not measured. A jar's proposed label wraps it and has no front."""
    from apps.ire.compose_container import _fit, _sheet_layout
    from apps.ire.compose_dropper import FRONT_COPY_EXCEEDS_SAFE_AREA, FRONT_COPY_FIT_UNMEASURED
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container import GENERIC_FRONT_HEIGHT_UNMEASURED, generic_front_copy_fit
    height_code = f"{FRONT_COPY_FIT_UNMEASURED}: vertical ({GENERIC_FRONT_HEIGHT_UNMEASURED['ruled']})"
    for archetype, height_mm, width_mm in (("bottle", 110.0, 40.0), ("tube", 130.0, 35.0), ("lipstick", 80.0, 20.0)):
        bb, zones = _front_case(archetype, height_mm, width_mm)
        assert _fit(bb.width_mm, bb.height_mm, _sheet_layout(bb)["con_box"])[0] == 1.0   # true size: a width is its own
        front = next(z for z in zones if z["zone_type"] == "FRONT_PRINT_ZONE")
        safe_mm = float(front["width"]) - 2 * float(front["safe_margin_mm"])
        for descriptor, over in (("Serum", False), ("Intensive Overnight Restorative Treatment Concentrate", True)):
            doc = compose_container_graph(bb, product_name="Rose", sku="X", zones=zones, native=True,
                                          hierarchy_lines=ruled_front_hierarchy("Rose", descriptor=descriptor))
            fit = generic_front_copy_fit(doc, zones, archetype)
            [row] = [r for r in fit["runs"] if r["name"] == "front-descriptor"]
            [name] = fit["name_runs"]
            assert fit["safe_area_mm"] == pytest.approx(safe_mm) and name["state"] == "HELD", (archetype, name)
            assert (row["state"] == "EXCEEDS_SAFE_AREA") is over, (archetype, descriptor, row)
            assert any(c.startswith(f"{FRONT_COPY_EXCEEDS_SAFE_AREA}: front-descriptor +") for c in fit["codes"]) is over
            assert fit["codes"][-1] == height_code and fit["not_read"] == [], fit["codes"]
    _bb, zones = _front_case("jar", 50.0, 60.0)
    assert [z["zone_type"] for z in zones] == ["WRAP_LABEL_ZONE"]
    assert generic_front_copy_fit(None, zones, "jar") is None


def test_bh70_a_lids_colour_is_named_for_its_lid_on_the_drawn_file():
    """§BH70(1), item 21 of the list the owner was sent: the drawn file labelled every form's closure colour CAP — a
    compact's and a jar's is its LID; a bottle's stays CAP."""
    for archetype, height_mm, width_mm, word in (("compact", 95.0, 110.0, "LID"), ("jar", 50.0, 60.0, "LID"),
                                                  ("bottle", 110.0, 40.0, "CAP")):
        bb, zones = _front_case(archetype, height_mm, width_mm)
        doc = compose_container_graph(bb, colors={"body": "#EAD7D2", "cap": "#C9A24B"}, product_name="Rose", sku="X",
                                      zones=zones, native=True)
        shown = [str(n.text) for n, _ in doc.walk() if n.type == "text" and "#C9A24B" in str(n.text)]
        assert shown == [f"{word} #C9A24B"], (archetype, shown)


def test_bh70_a_transparent_form_that_is_not_a_bottle_names_its_swatches_for_what_they_paint():
    """§BH70(1), item 11 of the list the owner was sent: every transparent form's sheet carried the registry ruled for
    the transparent serum bottle (2B-3V-CORR-3 §6) — a peach-rose fill, dewdrops, the serum's print colours — whatever it
    held. A compact's names its wall, the product seen through it and its lid; a bottle keeps the ruled registry."""
    blue = {"state": "TRANSPARENT", "product_color": "#9FC5E8"}
    bb, zones = _front_case("compact", 95.0, 110.0)
    doc = compose_container_graph(bb, colors={"body": "#EAD7D2", "cap": "#C9A24B"}, product_name="Rose", sku="X",
                                  zones=zones, native=True, transparency=blue)
    words = [str(n.text) for n, _ in doc.walk() if n.type == "text" and str(n.text).split(" ")[-1].startswith("#")]
    assert words == ["CONTAINER_TRANSPARENT_BODY #FDF7F2", "PRODUCT_SEEN_THROUGH #9FC5E8", "LID #C9A24B"], words
    bb, zones = _front_case("bottle", 110.0, 40.0)
    doc = compose_container_graph(bb, colors={"body": "#EAD7D2", "cap": "#C9A24B"}, product_name="Rose", sku="X",
                                  zones=zones, native=True, transparency=blue)
    words = [str(n.text) for n, _ in doc.walk() if n.type == "text"]
    assert "PRODUCT_PEACH_ROSE_FILL #9FC5E8" in words and "SPOT_UV_DEWDROPS #E8E8E8" in words, words


def test_bh71_the_hero_is_drawn_at_its_measured_poses_in_colours_a_record_names():
    """§BH71 PART 1, ROUTE A: each measured unit drawn with the design language's own petal at its pose — pointed at
    its measured point, its axis turned as measured, its length and width the window's shares — named ``petal-<i>``,
    and filled with the named colour nearest the one measured; with no sourced palette, the unsourced stand-in the
    printed-colour audit refuses by name — never the measured colour."""
    from apps.ire import compose_container as C
    from apps.ire.graph import Color
    hero = {"units": [{"name": "petal-0", "anchor": [0.5, 0.8], "theta_deg": -90.0, "length": 0.4,
                        "width": 0.15, "hex": "#C48C84", "metal": False},
                       {"name": "petal-1", "anchor": [0.4, 0.8], "theta_deg": -120.0, "length": 0.4,
                        "width": 0.15, "hex": "#9C6A51", "metal": True}]}

    class _Swatch:
        def __init__(self, hex_):
            self.hex = hex_

    class _Swatches:
        def all(self):
            return [_Swatch("#C9A24B"), _Swatch("#D4A0A0"), _Swatch("#6E2B3A")]
    g = C._hero_units(hero, (10.0, 20.0, 40.0, 50.0), _Swatches())
    assert [p.name for p in g.children] == ["petal-0", "petal-1"]
    first = g.children[0].segments
    assert (round(first[0].x, 6), round(first[0].y, 6)) == (30.0, 60.0)          # pointed at its measured point
    tip = first[2]                                                             # the round end, along its axis
    assert abs(tip.x - 30.0) < 1e-6 and abs(tip.y - (60.0 - 0.4 * 40.0)) < 1e-6, (tip.x, tip.y)
    from apps.ire.container_brand_usage import _delta_e_hex
    named = ["#C9A24B", "#D4A0A0", "#6E2B3A"]
    for unit, petal in zip(hero["units"], g.children):                  # a named colour, and none nearer
        chosen = next(h for h in named if Color.from_hex(h) == petal.fill.color)
        assert all(_delta_e_hex(unit["hex"], chosen) <= _delta_e_hex(unit["hex"], h) + 1e-9 for h in named)
    bare = C._hero_units(hero, (10.0, 20.0, 40.0, 50.0), None)
    assert all(p.fill.color == Color.from_hex(C._UNSOURCED_LIGHT) for p in bare.children)


def test_bh71_a_window_draws_its_measured_hero_in_place_of_the_procedural_motif():
    """§BH71 PART 1: a concept's window whose hero was measured on its picture draws those units, cut to the window,
    where the procedural motif was drawn — named motif-window, as the finish reader and the fidelity check read it."""
    from apps.ire import compose_container as C
    from apps.ire.graph import Color
    hero = {"units": [{"name": "petal-0", "anchor": [0.5, 0.8], "theta_deg": -90.0, "length": 0.4,
                        "width": 0.15, "hex": "#C48C84", "metal": False},
                       {"name": "petal-1", "anchor": [0.4, 0.8], "theta_deg": -120.0, "length": 0.4,
                        "width": 0.15, "hex": "#9C6A51", "metal": True}], "metal_units": ["petal-1"]}
    nodes, _boxes, drawn = C.draw_concept_elements(
        {"layout": "window", "window_shape": "oval", "hero": hero}, (10.0, 20.0, 60.0, 80.0), None,
        Color.from_hex("#5A2A36"), fit_width=False, swatches=C._motif_swatches({"motif": ["#D4A0A0", "#C9A24B"]}))
    assert drawn[:2] == ["window-interior", "motif-window"], drawn
    motif = next(n for n in nodes if getattr(n, "name", "") == "motif-window")
    assert [p.name for p in motif.children] == ["petal-0", "petal-1"] and motif.clip is not None


def _round_set(size_pt, *, top_mm=20.0, circle=(50.0, 50.0, 40.0)):
    """One step of a lid's layout, as ``_concept_face`` hands it to the step search: the name one line, centred at
    ``top_mm``, on a round lid's safe circle."""
    from apps.ire import concept_face as CF
    em = size_pt * CF.MM_PER_PT
    lay = {"placed": {CF.NAME: {"x": 50.0, "align": "center", "ink_top": top_mm,
                                 "ink_bottom": top_mm + (CF.INK_ABOVE_EM + CF.INK_BELOW_EM) * em,
                                 "baseline": top_mm + CF.INK_ABOVE_EM * em}},
           "regions": {"text": [0.0, 0.0, 100.0, 100.0], "mark": [0.0, 0.0, 100.0, 100.0]},
           "not_placed": [], "collisions": []}
    return {"size_pt": size_pt, "text_w": 100.0, "lines": ["ROSE VEIL"], "ar_size_pt": size_pt, "lay": lay,
            "follow": {"moves": [], "followed": []}, "round_lid": circle}


def test_bh71_a_round_lid_is_measured_against_its_circle_not_its_box():
    """§BH71 PART 1: a line inside a round lid's box can leave its circle at its corners — measured by the line's own
    ink box against the lid's safe circle; the same line at the lid's middle keeps inside."""
    from apps.ire import compose_container as C
    near_the_rim = C._outside_the_round_lid(_round_set(36.0, top_mm=12.0), (50.0, 50.0, 40.0), style={},
                                            ar_text=None)
    assert [e for e, _mm in near_the_rim] == ["name"] and near_the_rim[0][1] > 0.0, near_the_rim
    assert C._outside_the_round_lid(_round_set(36.0, top_mm=44.0), (50.0, 50.0, 40.0), style={}, ar_text=None) == []


def test_bh71_a_learned_oval_lid_is_measured_against_its_ellipse():
    """§BH71 PART 3: on a learned oval lid a line near its flat top leaves the ellipse while a circle of its width
    would hold it; at its middle it keeps inside; and on a circle the ellipse's measure is the round lid's own."""
    from apps.ire import compose_container as C
    flat = (50.0, 50.0, 40.0, 20.0)
    near_the_top = C._outside_the_oval_lid(_round_set(36.0, top_mm=33.0), flat, style={}, ar_text=None)
    assert [e for e, _mm in near_the_top] == ["name"] and near_the_top[0][1] > 0.0, near_the_top
    assert C._outside_the_round_lid(_round_set(36.0, top_mm=33.0), (50.0, 50.0, 40.0), style={}, ar_text=None) == []
    assert C._outside_the_oval_lid(_round_set(12.0, top_mm=47.0), flat, style={}, ar_text=None) == []
    rim = _round_set(36.0, top_mm=12.0)
    a = C._outside_the_oval_lid(rim, (50.0, 50.0, 40.0, 40.0), style={}, ar_text=None)
    b = C._outside_the_round_lid(rim, (50.0, 50.0, 40.0), style={}, ar_text=None)
    assert [e for e, _ in a] == [e for e, _ in b] and all(abs(x - y) < 1e-9 for (_, x), (_, y) in zip(a, b)), (a, b)


def test_bh71_a_round_lid_takes_the_largest_step_whose_lines_keep_inside_it():
    """§BH71 PART 1: the name's step on a round lid is the largest of the scale whose lines keep inside the lid's
    circle — every larger step refused by name for leaving it, as a step that leaves its region is (§BH68(b))."""
    from apps.ire import compose_container as C
    set_, record = C._lid_name_step(_round_set, style={}, ar_text=None)
    circle = (50.0, 50.0, 40.0)
    assert C._outside_the_round_lid(set_, circle, style={}, ar_text=None) == []
    assert record["larger_steps_refused"], record                  # the scale's top leaves the lid here
    for refused in record["larger_steps_refused"]:
        assert any("leaves the round lid" in why for why in refused["why"]), refused
        assert C._outside_the_round_lid(_round_set(refused["step_pt"]), circle, style={}, ar_text=None)


def _with_shade(top_mm, *, text_w=100.0):
    """A step of a round lid's layout with the record's shade laid at ``top_mm`` below the name at the lid's middle."""
    from apps.ire import compose_container as C
    from apps.ire import concept_face as CF
    set_ = _round_set(12.0, top_mm=44.0)
    shade = C._shade_set({"en": "Natural", "ar": "طبيعي"}, None, 48.0)
    em = shade["size_pt"] * CF.MM_PER_PT
    set_["lay"]["placed"][CF.SHADE] = {"x": 50.0, "align": CF.CENTRE, "ink_top": top_mm,
                                       "ink_bottom": top_mm + (CF.INK_ABOVE_EM + CF.AR_INK_BELOW_EM) * em,
                                       "baseline": top_mm + CF.INK_ABOVE_EM * em}
    set_["shade"], set_["text_w"] = shade, text_w
    return set_


def test_bh71_the_shade_line_is_the_records_measured_whole_against_the_round_lid():
    """His answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks for". The
    shade line — the record's English and Arabic side by side, one em of its size between them — is measured against a
    round lid's circle by its whole ink box, as every other line is: near the rim it leaves the circle, at the lid's
    middle it keeps inside; a line wider than the text width refuses the step, by name."""
    from apps.ire import compose_container as C
    circle = (50.0, 50.0, 40.0)
    near = C._outside_the_round_lid(_with_shade(87.0), circle, style={}, ar_text=None)
    assert [e for e, _mm in near] == ["shade"] and near[0][1] > 0.0, near
    assert C._outside_the_round_lid(_with_shade(58.0), circle, style={}, ar_text=None) == []
    refusals = C._lid_step_refusals(_with_shade(58.0, text_w=5.0), style={}, ar_text=None)
    assert any((r["kind"], r["key"]) == ("width", "shade") for r in refusals), refusals
    runs = C._shade_runs(_with_shade(58.0)["shade"], 50.0, "centre")
    assert [(name, text) for name, text, _x, _w in runs] == [("product-shade", "Natural"), ("product-shade-ar", "طبيعي")]
    left, right = runs[0][2], runs[-1][2] + runs[-1][3]
    assert abs((left + right) / 2.0 - 50.0) < 1e-9 and runs[1][2] > runs[0][2] + runs[0][3], runs   # centred, apart


def test_bh71_the_shade_line_takes_the_concepts_own_line_height_never_above_half_the_name():
    """His answer of 2026-09-29, (4): the shade line is set at the step of the scale whose ink is as tall as the
    concept's own shade line (91's "03 Medium Beige" is 4.33 mm tall on its 110 mm lid: 12 pt), never above half the
    name, never under the scale's smallest step; with no line of the concept's own it takes a quarter of the name; a
    record with no shade, or an empty one, gives none."""
    from apps.ire import compose_container as C
    seen = C._shade_set({"en": "Natural", "ar": ""}, (30.0, 90.0, 24.6, 4.33), 48.0)
    assert (seen["size_pt"], seen["place"]) == (12.0, "the concept's own shade line"), seen
    assert C._shade_set({"en": "Natural"}, (30.0, 90.0, 24.6, 40.0), 16.0)["size_pt"] == 8.0      # half the name
    assert C._shade_set({"en": "Natural"}, None, 48.0)["size_pt"] == 12.0                         # a quarter of 48
    assert C._shade_set({"en": "Natural"}, None, 8.0)["size_pt"] == 6.0                           # the scale's floor
    assert C._shade_set(None, None, 48.0) is None and C._shade_set({"en": "", "ar": ""}, None, 48.0) is None


def test_w11_a_jars_wrap_label_is_read_on_its_front_as_the_front_view_draws_it():
    """[The clean-up's wiring check, 2026-10-05, its finding W11] A jar's proposed label is 0.85 of its wrap, measured
    round the unrolled wrap; the front view draws the half facing it. Read as the front's own, its centre stood 34 mm
    past a 60 mm jar, and a mark moved clear of the picture's parts was drawn off the sheet — Gate 2 refused it (logo
    clipped, an element outside the artboard). Now: the label's front is the body's whole width; a narrower label its
    projected chord, centred; a label wholly on the back, and every other zone, unchanged; and the mark moved clear of a
    part stays centred on the body."""
    import math
    from apps.ire import compose_container as C
    bb, zones = _front_case("jar", 70.0, 60.0)
    wrap = C._front_zone(zones)
    assert (wrap["zone_id"], wrap["width"]) == ("z_wrap", 160.2), wrap          # 0.85 of 60π, round the wrap
    front = C._front_view_zone(wrap, bb)
    assert (front["x"], front["width"], front["y"], front["height"]) == (0.0, 60.0, wrap["y"], wrap["height"]), front
    circ = math.pi * 60.0
    narrow = dict(wrap, x=circ / 2.0 - circ / 8.0, width=circ / 4.0)                # a quarter of the wrap, centred
    seen = C._front_view_zone(narrow, bb)
    assert seen["width"] == pytest.approx(60.0 * math.sin(math.pi / 4.0), abs=1e-3), seen   # its chord: D·sin(π/4)
    assert seen["x"] + seen["width"] / 2.0 == pytest.approx(30.0, abs=1e-3), seen           # centred on the body
    back = dict(wrap, x=0.0, width=circ / 5.0)                                       # behind the jar, by its seam
    assert C._front_view_zone(back, bb) is back
    bottle, bottle_zones = _front_case("bottle", 110.0, 40.0)
    flat = C._front_zone(bottle_zones)
    assert C._front_view_zone(flat, bottle) is flat and C._front_view_zone(None, bb) is None
    # the mark, moved clear of a part printed over its place, stays on the body: centred across it, never past it
    s, ox, oy = 1.0, 75.0, 10.0
    mark = (ox + 30.0 - 14.04, oy + 30.0, 28.08, 8.42)
    moved, where = C._mark_clear_of(mark, {"band": (0.0, 0.40, 1.0, 0.60)}, front, bb, s, ox, oy)
    assert where is not None and moved[0] + moved[2] / 2.0 == pytest.approx(ox + 30.0), (moved, where)
    unmoved, _w = C._mark_clear_of(mark, {"band": (0.0, 0.40, 1.0, 0.60)}, wrap, bb, s, ox, oy)
    assert unmoved[0] + unmoved[2] / 2.0 > ox + 60.0, unmoved        # the negative control: the wrap read as the front


def test_w10_a_jars_back_copy_prints_on_the_back_of_its_wrap_label_and_never_nowhere():
    """[His answer of 2026-10-05, W10: "a jar's back copy goes on the back of its wrap label; with no wrap, on the base
    label. Never nowhere."] A 60 mm jar proposes one zone, its wrap label (0.85 of its circumference, centred on its
    front): its back is the label's two ends behind the body, and the brief's back copy is drawn there at print size,
    flowing from the first end to the second at a section's end, on the wrap's own surface. A design with no back zone,
    no wrap and no base label draws no panel and is refused by name; the quality check's composition axis names it."""
    from apps.ire import back_panel as bp
    from apps.ire import compose_container as C
    from apps.pipeline.services import visual_quality_gate as vq
    bb, zones = _front_case("jar", 70.0, 60.0)
    where, places = C.information_zones(zones, bb.width_mm)
    assert where == bp.WHERE_WRAP_BACK and len(places) == 2, (where, places)
    assert all(z["parent_surface"] == "BODY_WRAP" and z["width"] >= bp.WRAP_END_MIN_MM for z in places), places
    sections = [{"heading": "How to use", "text": "Apply to clean skin, morning and night, with clean fingertips; "
                                                  "massage gently until absorbed. Follow with sunscreen by day."},
                {"heading": "Ingredients", "text": "Aqua, Glycerin, Rosa Damascena Flower Water, Squalane, Caprylic/"
                                                   "Capric Triglyceride, Butyrospermum Parkii Butter, Cetearyl "
                                                   "Alcohol, Glyceryl Stearate, Tocopherol, Sodium Hyaluronate, "
                                                   "Phenoxyethanol, Ethylhexylglycerin, Parfum."},
                # [his goal of 2026-10-06, item 8] three allergens fewer: measured in the faces the wrap is drawn in,
                # the list with them runs past the second end's foot (it was measured in Noto Sans, and fitted)
                {"heading": "Warnings", "text": "For external use only. Avoid contact with the eyes. Stop use if "
                                                "irritation occurs. Keep out of reach of children."},
                {"heading": "", "text": "Made in UAE."}]
    groups, fit = C.compose_information_panels(sections, zones, bb.width_mm, 10.0, 10.0)
    assert fit["where"] == bp.WHERE_WRAP_BACK and fit["emitted"] and len(groups) == len(fit["panels"]) == 2, fit
    assert all(str(g.name) == "TrueScaleSurface-BODY_WRAP" for g in groups)
    drawn = [e for e in fit["lines"] if e["fits"]]
    assert {e["section"] for e in drawn} == {0, 1, 2, 3} and fit["fits"], fit["codes"]     # every section, whole
    first = {int(str(n.name).split("-")[2]) for n in groups[0].children if str(n.name).count("-") >= 4}
    second = {int(str(n.name).split("-")[2]) for n in groups[1].children if str(n.name).count("-") >= 4}
    assert first and second and max(first) < min(second), (first, second)                     # flowed, in order
    doc = C.compose_container_graph(bb, product_name="Rose Velvet", native=True, zones=zones,
                                    back_sections=sections, back_panel={"methods_record": None})
    assert doc.metadata[bp.SCHEMA]["where"] == bp.WHERE_WRAP_BACK
    texts = " ".join(str(n.text) for n, _ in doc.walk() if getattr(n, "type", "") == "text")
    assert "Rosa Damascena" in texts and "Made in UAE." in texts
    short = [{"heading": "", "text": "Made in UAE."}]
    one, fit_one = C.compose_information_panels(short, zones, bb.width_mm, 10.0, 10.0)
    assert len(one) == 1 and "panels" not in fit_one, fit_one              # whole on one end: no empty second panel
    nowhere, rec = C.compose_information_panels(sections, [], bb.width_mm, 10.0, 10.0)
    assert nowhere == [] and bp.NO_SURFACE in rec["codes"] and rec["where"] is None, rec
    spec = {"container_composition_metrics/1.0": {"overlap_count": 0, "outside_zone_count": 0,
                                                  "below_floor_count": 0, "front_hierarchy_nonempty": True},
            bp.SCHEMA: rec}
    assert vq._back_copy_has_no_surface(spec) and not vq._back_copy_has_no_surface({bp.SCHEMA: fit})


# ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 2: "The title says "— compact lid". A palette design
# ---- must include the whole palette: the lid AND the open tray with its 18 pans in 3 rows of 6, each shade name from my
# ---- brief printed under its pan. Tell me if today it only designs the lid, and build the tray if so."]

BRIEF_124 = """Enchanted Rose Palette (test)

Type: eyeshadow palette, a rectangular case with a magnetic lid, 18
square pans in 3 rows of 6, each shade name printed under its pan;
plus its outer box (a slim sleeve or tuck box).

Lid front copy: BBROSE logo, "Enchanted Rose", "18 shades", 27 g ℮ 0.95 oz.
Shade names (row by row, left to right):
Row 1: Petal Frost, Moonlit Rose, Fairy Dust, Rosewater, Wild Rose,
Velvet Bloom.
Row 2: Lilac Mist, Gilded Petal, Spellbound, Enchanted, Twilight,
Briar.
Row 3: Dusk Garden, Mystic, Thorn, Nightshade, Eternal, Midnight Bloom.
Back copy: Description: An 18-shade eyeshadow palette.
"""


def test_goal_1010_item2_the_tray_is_read_from_his_briefs_own_words():
    """His grid and his shade names, row by row, left to right — a name that runs onto the next line kept whole, the
    back copy after them never read as a name; a brief naming no pans draws no tray; a count alone is laid out near a
    square, named from the product record's shades."""
    from apps.ire.palette_tray import read_tray
    tray = read_tray(BRIEF_124)
    assert (tray["rows"], tray["cols"], tray["shape"], tray["named"], tray["source"]) == (3, 6, "square", 18,
                                                                                           "his brief")
    assert tray["names"][0] == ["Petal Frost", "Moonlit Rose", "Fairy Dust", "Rosewater", "Wild Rose", "Velvet Bloom"]
    assert tray["names"][1][-1] == "Briar" and tray["names"][2][-1] == "Midnight Bloom"
    assert read_tray("A pressed face powder for BBROSE.") is None
    counted = read_tray("Capacity: 6 pans", shades=[{"en": "Rose"}, {"en": "Plum"}])
    assert counted["rows"] * counted["cols"] >= 6 and counted["names"][0][:2] == ["Rose", "Plum"]
    assert counted["source"] == "the product record"


def test_goal_1010_item2_a_palette_draws_its_lid_and_its_open_tray_every_pan_named(tmp_path):
    """124's palette at its 190 x 120 mm: the lid as before, and below it the open tray at print size — 18 pans, one
    size, in 3 rows of 6, each shade's name in capitals centred under its own pan and no wider than it, the frame round
    the pans inside the insert — on the sheet, in the drawing's record and in the emitted file."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from apps.dielines.exporters.counter_display_files import _resolve_fonts
    from apps.ire.palette_tray import read_tray
    bb, zones = _front_case("compact", 120.0, 190.0)
    doc = compose_container_graph(bb, zones=zones, product_name="Enchanted Rose", open_tray={
        "tray": read_tray(BRIEF_124), "ground_hex": "#F6DCE6", "ink_hex": "#6B3A5A",
        "edge_hexes": ["#F4B8CF", "#C9B6E4", "#9ED9E0"]})
    record = doc.metadata["open_tray"]
    assert (record["rows"], record["cols"], record["named"], record["insert_mm"]) == (3, 6, 18, [184.0, 114.0])
    found = {n.name: n for n, _parent in doc.walk() if n.name}
    assert "OPEN TRAY" in found and "sheet-open-tray-label" in found
    wells = sorted(n for n in found if n.startswith("pan-well-"))
    names = sorted(n for n in found if n.startswith("shade-name-"))
    assert len(wells) == 18 and len(names) == 18
    assert (found["shade-name-1-1"].text, found["shade-name-3-6"].text) == ("PETAL FROST", "MIDNIGHT BLOOM")
    face = _resolve_fonts()[0]
    for name in names:
        r, c = name.split("-")[-2:]
        well = found["pan-well-%s-%s" % (r, c)].segments
        xs = [s.x for s in well if hasattr(s, "x")]
        ys = [s.y for s in well if hasattr(s, "y")]
        run = found[name]
        assert abs(run.x - (min(xs) + max(xs)) / 2.0) < 0.01                       # centred under its own pan
        assert run.y > max(ys)                                                      # under it
        assert stringWidth(run.text, face, run.size_pt) * 25.4 / 72.0 <= max(xs) - min(xs)   # no wider than it
    sides = {round(max(s.x for s in found[w].segments if hasattr(s, "x"))
                   - min(s.x for s in found[w].segments if hasattr(s, "x")), 3) for w in wells}
    assert len(sides) == 1                                                          # every pan one size
    edge = [s for s in found["tray-pan-field-edge"].segments if hasattr(s, "x")]
    ground = found["tray-insert-ground"]
    assert min(s.x for s in edge) >= ground.x and max(s.x for s in edge) <= ground.x + ground.w
    assert min(s.y for s in edge) >= ground.y and max(s.y for s in edge) <= ground.y + ground.h
    assert doc.page_h >= ground.y + ground.h
    out = emit_pdf_ai(doc, str(tmp_path / "palette.ai"))
    with fitz.open(out) as pdf:
        text = " ".join(page.get_text() for page in pdf)
    assert "MIDNIGHT BLOOM" in text and "PETAL FROST" in text and "OPEN TRAY AT PRINT SIZE" in text


BRIEF_SMALL_TRAY = """An eyeshadow palette for Rose Velvet, a rectangular case with 12 square pans in 2 rows of 6, each shade name
printed under its pan.
Shade names (row by row, left to right):
Row 1: Petal Frost, Moonlit Rose, Fairy Dust, Rosewater, Wild Rose, Velvet Bloom.
Row 2: Lilac Mist, Gilded Petal, Spellbound, Enchanted, Twilight, Briar.
"""


def _small_tray_doc():
    from apps.ire.palette_tray import read_tray
    bb, zones = _front_case("compact", 95.0, 110.0)
    return compose_container_graph(bb, zones=zones, product_name="Rose Velvet", open_tray={
        "tray": read_tray(BRIEF_SMALL_TRAY), "ground_hex": "#F6DCE6", "ink_hex": "#6B3A5A",
        "edge_hexes": ["#F4B8CF", "#C9B6E4"]})


def test_goal_1010_item2_a_small_trays_names_never_go_under_the_print_floor_a_long_one_breaks_onto_two_lines():
    """[His goal of 2026-10-10, item 2: "each shade name from my brief printed under its pan"] A 110 x 95 mm compact's 12
    pans are 14 mm: "VELVET BLOOM" on one line fits only at 4.25 pt, under the 5 pt floor its printed run is judged at
    (no print method is recorded for the tray's insert — the disclosed fallback). So every name is set at the floor or
    above, and a name too long for its pan there breaks at its space onto two lines in the band under it — never
    shrunk under the floor, never wider than its pan; each run declared printed on the tray's insert, the sheet's label
    over the tray an annotation."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from apps.dielines.exporters.counter_display_files import _resolve_fonts
    from apps.ire.compose_container import TRAY_INSERT_SURFACE
    from apps.ire.container_text_floor import FALLBACK_FLOOR_PT, SOURCE_FALLBACK, measure_text_floor
    from apps.ire.palette_tray import NAME_MIN_PT
    doc = _small_tray_doc()
    record = doc.metadata["open_tray"]
    assert NAME_MIN_PT == FALLBACK_FLOOR_PT and record["name_pt"] >= NAME_MIN_PT
    assert "Velvet Bloom" in record["names_on_two_lines"] and record["wider_than_pan"] == []
    found = {n.name: n for n, _parent in doc.walk() if n.name}
    first, second = found["shade-name-1-6"], found["shade-name-1-6-2"]
    assert (first.text, second.text) == ("VELVET", "BLOOM") and second.y > first.y
    assert found["shade-name-2-6"].text == "BRIAR" and "shade-name-2-6-2" not in found      # a short name: one line
    face = _resolve_fonts()[0]
    well = [s for s in found["pan-well-1-6"].segments if hasattr(s, "x")]
    below = [s for s in found["pan-well-2-6"].segments if hasattr(s, "x")]
    for run in (first, second):
        assert stringWidth(run.text, face, run.size_pt) * 25.4 / 72.0 <= max(s.x for s in well) - min(s.x for s in well)
        assert max(s.y for s in well) < run.y < min(s.y for s in below)                    # in the band under its pan
    floor = measure_text_floor(doc)
    names = [r for r in floor["runs"] if r["node_name"].startswith("shade-name-")]
    assert len(names) == len([n for n in found if n.startswith("shade-name-")]) > 12
    assert {(r["surface"], r["scope_source"], r["floor_pt"], r["floor_source"], r["below"]) for r in names} == {
        (TRAY_INSERT_SURFACE, "DECLARED", FALLBACK_FLOOR_PT, SOURCE_FALLBACK, False)}
    assert "sheet-open-tray-label" in {a["node_name"] for a in floor["out_of_scope_annotations"]}


def test_goal_1010_item2_the_open_tray_on_the_sheet_is_product_never_canvas(tmp_path):
    """[His goal of 2026-10-10, item 2] Gate 2's artboard axis allows a sheet 3 x the product it draws. A palette drawn
    lid and open tray measured 763.94 x 948.19 pt for a 110 x 95 mm compact, the tray taking 98 mm of it at print
    size: read as the lid alone it is refused as presentation canvas (the refusal his tray first met at Gate 2); read
    with the tray's height from the drawing's own record it passes; and a sheet taller than the lid's allowance and its
    tray together is still refused — the factor unchanged."""
    import fitz

    from apps.pipeline.services.visual_quality_gate import VQ_ARTBOARD_UNRELATED_TO_PRODUCT, _artboard_axis
    record = _small_tray_doc().metadata["open_tray"]
    assert record["sheet_grown_mm"] > record["insert_mm"][1]                     # the tray, its label and its margins

    def output(w_pt, h_pt):
        path = tmp_path / ("sheet-%d.ai" % int(h_pt))
        pdf = fitz.open()
        pdf.new_page(width=w_pt, height=h_pt)
        pdf.save(str(path))

        class _File:
            def open(self, mode):
                return open(path, "rb")

        class _Out:
            design_preview_ai = _File()
        return _Out()
    profile = {"archetype": "compact", "width_mm": 110.0, "height_mm": 95.0}
    sheet = output(763.94, 948.19)
    lid_alone = _artboard_axis(sheet, profile)
    assert (lid_alone["state"], lid_alone["code"]) == ("FAIL", VQ_ARTBOARD_UNRELATED_TO_PRODUCT), lid_alone
    with_tray = _artboard_axis(sheet, profile, {"open_tray_sheet_mm": 98.0})
    assert with_tray["state"] == "PASS" and with_tray["measured"]["open_tray_sheet_pt"] == 277.8, with_tray
    taller = _artboard_axis(output(763.94, 95.0 * 72 / 25.4 * 3 + 277.8 + 20.0), profile, {"open_tray_sheet_mm": 98.0})
    assert (taller["state"], taller["code"]) == ("FAIL", VQ_ARTBOARD_UNRELATED_TO_PRODUCT), taller


def test_goal_1011_tray_every_pan_is_drawn_its_shades_colour_and_finish_never_grey(tmp_path):
    """[His test blocker on design 124, 2026-10-11, (5): "Every pan gets a real shade colour and finish (matte / shimmer /
    glitter) ... No grey pans."] 124's tray drawn with its pans' shades: each pan in its own colour — MATTE flat, SHIMMER a
    sheen across it (a gradient from its colour lit towards white), GLITTER its colour strewn with fine specks — none
    the grey the tray was drawn in before; the list on the drawing's record, each pan its name, colour, finish and
    source."""
    from apps.ire.graph import GradientFill, SolidFill
    from apps.ire.palette_tray import PAN_SHOWN, read_tray
    tray = read_tray(BRIEF_124)
    finishes = ["matte", "shimmer", "glitter"]
    pans = [[{"name": name, "hex": "#%02X%02X%02X" % (120 + 6 * c, 60 + 20 * r, 150), "finish": finishes[(r + c) % 3],
              "source": "the tray picture"} for c, name in enumerate(row)] for r, row in enumerate(tray["names"])]
    bb, zones = _front_case("compact", 120.0, 190.0)
    doc = compose_container_graph(bb, zones=zones, product_name="Enchanted Rose", open_tray={
        "tray": tray, "ground_hex": "#F6DCE6", "ink_hex": "#6B3A5A", "edge_hexes": ["#F4B8CF", "#C9B6E4"],
        "pans": pans})
    found = {n.name: n for n, _parent in doc.walk() if n.name}
    for r in range(3):
        for c in range(6):
            pan, node = pans[r][c], found["pan-%d-%d" % (r + 1, c + 1)]
            if pan["finish"] == "shimmer":
                assert isinstance(node.fill, GradientFill) and node.fill.stops[-1].color.to_hex() == pan["hex"]
            else:
                assert isinstance(node.fill, SolidFill) and node.fill.color.to_hex() == pan["hex"]
            specks = [n for n in found if n.startswith("pan-%d-%d-speck-" % (r + 1, c + 1))]
            assert bool(specks) == (pan["finish"] == "glitter"), (r, c, len(specks))
            assert node.fill.stops[-1].color.to_hex() != PAN_SHOWN if isinstance(node.fill, GradientFill) else \
                node.fill.color.to_hex() != PAN_SHOWN
    listed = doc.metadata["open_tray"]["pans"]
    assert listed[2][5] == {"name": "Midnight Bloom", "hex": pans[2][5]["hex"], "finish": pans[2][5]["finish"],
                            "source": "the tray picture"}
    out = emit_pdf_ai(doc, str(tmp_path / "pans.ai"))
    with fitz.open(out) as pdf:
        assert pdf[0].get_images() == []


def test_goal_1011_one_engine_a_compacts_lid_is_drawn_from_its_map_and_its_art_never_its_forms_layout(tmp_path):
    """[His test blocker on design 124, 2026-10-11, (2) and (3)] A palette whose face is drawn from its concept's map: its
    art — the illustration traced in colour over its sky's gradients — laid on the lid's own face and clipped to its
    outline, and nothing of the form's own layout: no procedural petals, no hero units, no ruled name block; the lid
    still its own hero, drawn once; the art's record on the drawing."""
    from apps.ire.graph import Group, Image as _Image
    from apps.pipeline.targets.container import archetypes as A
    from apps.pipeline.targets.container import lid_art as LA
    import importlib
    tt = importlib.import_module("apps.pipeline.tests.test_targets")
    art_png, _img = tt._lid_art_png()
    trace = LA.trace_art(art_png, False)
    bb, zones = _front_case("compact", 120.0, 190.0)
    surface = A.primary_surface_of("compact")["surface"]
    doc = compose_container_graph(bb, zones=zones, product_name="Enchanted Rose",
                                  concept_front={"face": {"state": "MAP", "surface": surface}},
                                  map_front={"shapes": {"state": "TRACED"}, "lid_art": trace})
    found = {n.name: n for n, _parent in doc.walk() if n.name}
    art = found["LID ART"]
    assert isinstance(art, Group) and art.clip                                   # clipped to the lid's own outline
    assert len([n for n in found if n.startswith("lid-art-")]) == len(trace["regions"])
    # [his goal of 2026-10-13, (9): "Gradients are smooth, never flat bands"] the sky one smooth mesh over the lid — it
    # was one band a row of its field
    assert found["lid-sky"].fill.type == "mesh" and not [n for n in found if n.startswith("lid-sky-")]
    assert not [n for n in found if "petal" in n or n.startswith("hero-") or n.startswith("concept-")], sorted(found)[:40]
    record = doc.metadata["map_front"]["lid_art"]
    assert record["regions"] == len(trace["regions"]) and record["drawn_on_mm"][2] > 100
    out = emit_pdf_ai(doc, str(tmp_path / "lid.ai"))
    with fitz.open(out) as pdf:
        assert pdf[0].get_images() == []                                        # vector, never a raster
    assert not [n for n, _p in doc.walk() if isinstance(n, _Image) and "lid" in (n.name or "")]


def test_goal_1011_one_engine_a_lids_mark_stands_where_its_picture_prints_it(tmp_path):
    """[His test blocker on design 124, 2026-10-11, (2)] a lid drawn from its map with no master of the mark on hand: the
    house mark laid where the picture prints its mark — at the picture's ink height, in the mark's own proportion, in
    the lid's top left where the map reads it — never left at the form's ruled place over the lid's name."""
    from PIL import Image as _PIL

    from apps.pipeline.targets.container import archetypes as A
    from apps.pipeline.targets.container import lid_art as LA
    import importlib
    tt = importlib.import_module("apps.pipeline.tests.test_targets")
    art_png, _img = tt._lid_art_png()
    trace = LA.trace_art(art_png, False)
    logo = tmp_path / "logo.png"
    _PIL.new("RGBA", (400, 120), (20, 20, 20, 255)).save(logo)
    bb, zones = _front_case("compact", 120.0, 190.0)
    surface = A.primary_surface_of("compact")["surface"]
    doc = compose_container_graph(bb, zones=zones, product_name="Enchanted Rose", logo_path=str(logo),
                                  concept_front={"face": {"state": "MAP", "surface": surface}},
                                  map_front={"shapes": {"state": "TRACED", "marks": [
                                      {"part": "BBROSE logo", "box": [0.05, 0.06, 0.26, 0.11], "ink": "#CAAFC8"}]},
                                      "lid_art": trace})
    record = doc.metadata["map_front"]
    assert record["mark"]["placed"] == "where the picture prints its mark" and record["mark"]["why"]
    x0, y0, x1, y1 = record["boxes"]["BBROSE logo"]
    assert abs(x0 - 0.05) < 0.01 and abs(y0 - 0.06) < 1e-6 and abs(y1 - 0.11) < 1e-6
    assert abs((x1 - x0) * 190.0 / ((y1 - y0) * 114.0) - 400 / 120.0) < 0.05          # its own proportion


# ---- [His goal after the pitch page, 2026-10-15, A (2): "METALS: gold and chrome are drawn as metallic (highlights and
# ---- shadows as the concept shows), never flat tan or grey; gold goes on the foil plate."]

def _node(doc, name):
    return next(n for n, _p in doc.walk() if getattr(n, "name", None) == name)


def test_pitch_a2_a_metal_closure_is_drawn_with_its_concepts_light_never_flat(tmp_path):
    from apps.ire.graph import GradientFill, SolidFill
    look = {"metal": "gold", "lightness": [[0.0, 30.0], [0.4, 88.0], [1.0, 45.0]]}
    doc = compose_container_graph(_backbone(), product_name="X", colors={"body": "#FFFFFF", "cap": "#CCAA79"},
                                  closure_looks={"cap": look})
    cap = _node(doc, "cap")
    assert isinstance(cap.fill, GradientFill) and cap.fill.kind == "linear" and len(cap.fill.stops) == 3
    light = [sum((st.color.r, st.color.g, st.color.b)) for st in cap.fill.stops]
    assert light[1] > light[0] and light[1] > light[2]                # its shine where the concept shows it
    assert all(st.color.r >= st.color.b for st in cap.fill.stops)     # gold at every stop, never grey
    xs = [s.x for s in cap.segments if hasattr(s, "x")]
    assert abs(cap.fill.x1 - min(xs)) < 1e-6 and abs(cap.fill.x2 - max(xs)) < 1e-6
    flat = compose_container_graph(_backbone(), product_name="X", colors={"body": "#FFFFFF", "cap": "#CCAA79"})
    assert isinstance(_node(flat, "cap").fill, SolidFill)             # no look: drawn as it always was
    out = emit_pdf_ai(doc, str(tmp_path / "metal.ai"))                # the emitter draws the gradient as a shading
    assert fitz.open(out)[0].get_drawings()


def test_pitch_a2_a_gold_closure_joins_the_foil_plate_and_a_chrome_one_does_not():
    from apps.ire.compose_container import _with_gold_closure
    record = {"gold_nodes": ["logo"]}
    assert _with_gold_closure(record, {"cap": {"metal": "gold"}})["gold_nodes"] == ["logo", "cap"]
    assert _with_gold_closure(record, {"cap": {"metal": "chrome"}, "bulb": {"metal": "gold"}})["gold_nodes"] == [
        "logo", "closure-bulb"]
    assert _with_gold_closure(record, None) is record


def test_pitch_a2_a_foiled_metal_part_is_drawn_as_drawn_on_page_one():
    from apps.ire.emitters.native_ai import _ink_twin
    from apps.ire.graph import Color, Finish, GradientFill, GradientStop, MoveTo, LineTo, ClosePath, Path
    node = Path(name="cap", segments=[MoveTo(x=0, y=0), LineTo(x=5, y=0), LineTo(x=5, y=5), ClosePath()],
                fill=GradientFill(stops=[GradientStop(offset=0.0, color=Color.from_hex("#8A6A3A")),
                                         GradientStop(offset=1.0, color=Color.from_hex("#F2DCA0"))], x2=5.0),
                finishes=[Finish(kind="foil", plate="FOIL_GOLD")])
    twin = _ink_twin(node, node.finishes[0])
    assert twin is not None and isinstance(twin.fill, GradientFill) and twin.finishes == []


def test_pitch_a3_a_droppers_bulb_takes_its_own_colour_never_a_stock_plum():
    from apps.pipeline.tests.test_container_silhouettes import _profile
    prof = _profile([(0.0, 0.03, 0.05, 0.20), (0.03, 0.15, 0.20, 0.20), (0.15, 0.17, 0.20, 0.50),
                     (0.17, 0.30, 0.50, 0.50), (0.30, 0.36, 0.50, 1.0), (0.36, 1.0, 1.0, 1.0)])
    bb = build_backbone(ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="dropper", width_mm=40.0,
                                         height_mm=100.0, outline={"kind": "profile", "profile": prof,
                                                                   "closure_share": 0.30, "height_to_width": 2.5}))
    doc = compose_container_graph(bb, product_name="X", colors={"body": "#9BD4DE", "cap": "#D1D1D1", "bulb": "#D4D4D4"})
    assert _node(doc, "closure-bulb").fill.color.to_hex() == "#D4D4D4"
    plain = compose_container_graph(bb, product_name="X", colors={"body": "#9BD4DE", "cap": "#D1D1D1"})
    assert _node(plain, "closure-bulb").fill.color.to_hex() == "#D1D1D1"   # no reading of its own: the closure's


def test_pitch_a2_a_gold_closure_reaches_the_foil_plate():
    from apps.ire import container_finishes as CF
    doc = compose_container_graph(_backbone(), product_name="X", colors={"body": "#FFFFFF", "cap": "#CCAA79"},
                                  closure_looks={"cap": {"metal": "gold", "lightness": [[0.0, 30.0], [1.0, 85.0]]}})
    out = CF.apply(doc, None, brand_metallic_hex="#C9A24B", depict_as_drawn=True, gold_as_drawn=("cap",))
    cap = _node(doc, "cap")
    assert any(f.plate.endswith("GOLD") for f in cap.finishes), out


# [His review of 127, 130, 131 and 132, 2026-10-15, C (3), C (8), D (11); the lead's looks at 134 and 135]

def _texts(doc):
    return {str(getattr(n, "text", "")) for n, _ in doc.walk() if getattr(n, "type", "") == "text"}


def test_his_review_c8_no_panel_is_drawn_that_holds_only_a_placeholder():
    """131's base bottom: a grey block holding only "INFO · INCI · CODE". A surface is drawn as a panel only where it
    holds what prints there; one with no copy, no code window, no motif is not drawn — its surface still listed."""
    doc = compose_container_graph(_backbone(), product_name="Rose Nectar", name_lines=["Rose Nectar"],
                                  zones=_zones(), native=True)
    texts = _texts(doc)
    assert "INFO · INCI · CODE" not in texts and "BATCH —" not in texts and "MFG — · EXP —" not in texts
    fields = [n.name for n, _ in doc.walk() if str(getattr(n, "name", "")).endswith("-field")
              and str(n.name).startswith("panel-")]
    assert fields == [], fields
    assert len(doc.metadata["surface_inventory"]) > 1                  # the surfaces themselves stay known
    with_copy = compose_container_graph(_backbone(), product_name="Rose Nectar", name_lines=["Rose Nectar"],
                                        zones=_zones(), native=True,
                                        back_sections=[{"heading": "How to use", "text": "Apply daily."}])
    assert "How to use" in _texts(with_copy)                           # a back that holds its copy is drawn


def test_his_review_c3_a_faces_art_begins_at_its_drawn_closures_foot():
    from apps.ire.compose_container import closure_foot_share
    from apps.pipeline.targets.container.silhouettes import _stood_on_closure
    bb = _backbone()
    foot = closure_foot_share(bb)
    assert foot is not None and abs(foot - max(s.y for s in bb.cap_region if hasattr(s, "y")) / 110.0) < 1e-9
    tube = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=150,
                                           width_mm=40))
    stood = _stood_on_closure(tube, ContainerProfile(archetype="tube", height_mm=150, width_mm=40))
    assert closure_foot_share(stood) is None                           # a closure at its foot: no face top from it


def test_his_review_d11_a_collar_and_a_seam_are_drawn_as_the_concept_shows_them():
    from dataclasses import replace
    from apps.ire.graph import MoveTo, LineTo, ClosePath
    bb = _backbone()
    collar = [MoveTo(x=14.0, y=20.0), LineTo(x=26.0, y=20.0), LineTo(x=26.0, y=26.0), LineTo(x=14.0, y=26.0),
              ClosePath()]
    bb = replace(bb, collar_region=collar)
    doc = compose_container_graph(bb, product_name="P", colors={"body": "#2D222A", "cap": "#47373F",
                                                                 "collar": "#B8A77F"},
                                  closure_seams=[{"at": 0.05, "hex": "#CF850F", "width_share": 0.002}])
    nodes = {n.name: n for n, _ in doc.walk() if getattr(n, "name", None)}
    assert nodes["closure-collar"].fill.color.to_hex().upper() == "#B8A77F"
    assert nodes["closure-seam-0"].stroke.color.to_hex().upper() == "#CF850F"
    assert "swatch-collar" in nodes
    plain = compose_container_graph(_backbone(), product_name="P", colors={"body": "#2D222A", "cap": "#47373F"})
    assert not any(str(getattr(n, "name", "")).startswith(("closure-collar", "closure-seam")) for n, _ in plain.walk())


def test_s2_127_a_cap_meets_its_body_at_a_parting_line_in_its_own_deeper_shade():
    """[His last goal before the pitch, 2026-10-16, Step 2: "the hero is never lost: caps and closures"] 127's brown cap
    on its brown drip band read as one shape, its cap gone. Where a cap on top meets its body, a fine parting line is
    drawn across the body at the cap's foot, in a deeper shade of the cap's own colour; a tube stood on its cap has none."""
    from apps.ire.compose_container import JOIN_SHADE, JOIN_WIDTH_MM, closure_foot_share
    from apps.ire.graph import Color
    bb = _backbone()
    doc = compose_container_graph(bb, product_name="P", colors={"body": "#4B3022", "cap": "#4B3022"})
    nodes = {n.name: n for n, _ in doc.walk() if getattr(n, "name", None)}
    line = nodes["closure-join-line"]
    cap = Color.from_hex("#4B3022")
    assert abs(line.stroke.color.r - cap.r * JOIN_SHADE) < 1e-6 and line.stroke.width_mm == JOIN_WIDTH_MM
    assert line.segments[0].y == line.segments[1].y and closure_foot_share(bb) is not None      # level, at the foot
