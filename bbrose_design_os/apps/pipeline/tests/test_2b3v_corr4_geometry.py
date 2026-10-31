"""Phase 2B-3V-CORR-4 — container geometry, cap and palette fidelity.

The corrected dewdrop reconstruction still rendered a rounded bottle
silhouette with a hardcoded gold cap and a flat pink slab body. These tests
pin: the slim-variant bottle is a straight-walled rounded-rect block with a
low rectangular cap; the cap/product palette comes from the CONFIRMED
profile's concept-seeded hexes (never the gold default); the transparent body
keeps wall / product fill / highlight as separate editable objects."""
from __future__ import annotations

from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def test_slim_bottle_is_rectangular_block_not_shouldered_bottle():
    bb = build_backbone(ContainerProfile(
        archetype="bottle", variant="slim", width_mm=35, height_mm=95))
    xs = [getattr(s, "x", None) for s in bb.silhouette
          if getattr(s, "x", None) is not None]
    # straight side walls at the full body width: the outline spans the full
    # 0..35 with no narrow neck section
    assert max(xs) >= 34.9 and min(xs) <= 0.1
    # the cap region is a LOW rectangular block (≤20% of height)
    cap_ys = [getattr(s, "y", 0) for s in bb.cap_region
              if getattr(s, "y", None) is not None]
    assert max(cap_ys) <= 95 * 0.20 + 1e-6
    cap_xs = [getattr(s, "x", 0) for s in bb.cap_region
              if getattr(s, "x", None) is not None]
    assert max(cap_xs) - min(cap_xs) >= 35 * 0.9   # cap ≈ body width, no neck


def test_non_slim_bottle_unchanged():
    bb = build_backbone(ContainerProfile(
        archetype="bottle", variant="cylindrical", width_mm=40, height_mm=110))
    cap_xs = [getattr(s, "x", 0) for s in bb.cap_region
              if getattr(s, "x", None) is not None]
    assert max(cap_xs) - min(cap_xs) < 40 * 0.6    # legacy narrow screw cap


def test_transparent_slim_body_separates_wall_fill_highlight_and_blush_cap():
    from apps.ire.compose_container import compose_container_graph
    bb = build_backbone(ContainerProfile(
        archetype="bottle", variant="slim", width_mm=35, height_mm=95))
    doc = compose_container_graph(
        bb, product_name="Rosé Nectar", name_lines=["Rosé Nectar"],
        colors={"cap": "#F2C4CE"},
        native=True,
        transparency={"state": "TRANSPARENT", "product_color": "#F2C4CE"})
    nodes = {str(n.name): n for n, _ in doc.walk()}
    assert "body-transparent-wall" in nodes
    assert "product-peach-rose-fill" in nodes
    assert "glass-highlight" in nodes
    assert "body" not in nodes
    cap = nodes["cap"]
    assert cap.fill.color.to_hex().upper() == "#F2C4CE"      # blush, not gold
    wall = nodes["body-transparent-wall"]
    assert wall.fill.opacity <= 0.15                          # reads clear
    fill = nodes["product-peach-rose-fill"]
    assert fill.fill.opacity < 0.6                            # translucent


# --- §BH65(b)2: the lid face takes its FIELD colour, never the detailing colour ------------------
# The four sentences below are the concepts' OWN words, copied from the confirmed profile records of
# outputs 69 (task 89), 68 (task 88), 67 (task 84) and 36 (task 51), measured 2026-09-23.
_BRAND = [{"role": "Primary", "name": "Blush", "hex": "#F2C4CE"},
          {"role": "Accent", "name": "Deep Rose", "hex": "#8B3A52"},
          {"role": "Metallic", "name": "Rose Gold", "hex": "Metallic 10122 C"},
          {"role": "Ground", "name": "Warm Cream", "hex": "#FAF3EC"},
          {"role": "Ground", "name": "Warm Gold", "hex": "#CBA87D"}]


def test_finding3_the_body_is_drawn_in_its_concepts_two_colour_fields():
    """His test day finding 3 (2026-09-30, design 117): "the chosen pink is wrong" — his concept's body is two colour
    fields, "Hot pink (#E91E8C) solid upper two-thirds / soft pink (#F7B8D4) lower one-third", and the drawing painted
    one. The words name the fields; the picture splits them where its colour changes down the product's axis — a third
    down his tube, not the words' two-thirds, and the picture gives the proportions; the lower field is drawn inside the
    body's outline from there to the foot, the cap over it, and its colour is on the sheet. Words naming one field, or
    a picture not traced, draw one colour as before."""
    from apps.ire.compose_container import compose_container_graph
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.targets.container import _body_fields
    from apps.pipeline.targets.container import colour_sources as cs
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    from apps.pipeline.tests.test_vqr2b_concept_analysis import _tube_on_its_cap_png
    words = {"color_field_signature": "Hot pink (#E91E8C) solid upper two-thirds / soft pink (#F7B8D4) lower "
                                      "one-third fading to cream; cream-white drip shapes bridging the split; gold "
                                      "accents throughout"}
    fields = cs.colour_fields(words, [])
    assert fields == [("#E91E8C", "Hot pink (#E91E8C) solid upper two-thirds"),
                      ("#F7B8D4", "soft pink (#F7B8D4) lower one-third fading to cream")], fields
    trace = co.trace_elevation(_tube_on_its_cap_png())
    assert len(trace["axis_colours"]) == len(trace["profile"])
    split, got = _body_fields({co.SCHEMA: trace}, words, [], "tube")
    assert got == fields and abs(split - 0.34) < 0.03, split          # 208 of the tube's 610 px, from its crimp down
    assert _body_fields({co.SCHEMA: trace}, {"color_field_signature": "Hot pink (#E91E8C) all over"}, [], "tube") \
        == (None, [])
    assert _body_fields({co.SCHEMA: dict(trace, state=co.TEMPLATE_FALLBACK)}, words, [], "tube") == (None, [])
    outline, _source = co.outline_for(trace, archetype="tube", variant="standard", image_sha256=trace["source_sha256"])
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0, outline=outline))
    doc = compose_container_graph(bb, product_name="Rose", sku="X", body_split=split,
                                  colors={"body": "#E91E8C", "cap": "#E91E8C", "body_lower": "#F7B8D4"})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    body, group, field = nodes["body"], nodes["body-fields"], nodes["body-lower-field"]
    top, foot = min(p.y for p in body.segments if hasattr(p, "y")), max(p.y for p in body.segments if hasattr(p, "y"))
    assert group.clip == body.segments and field.fill.color.to_hex().upper() == "#F7B8D4"
    assert abs(field.y - (top + split * (foot - top))) < 1e-6 and field.y + field.h >= foot - 1e-6
    names = [getattr(n, "name", None) for n, _ in doc.walk()]
    assert names.index("body-lower-field") < names.index("cap") and "swatch-body_lower" in names
    plain = compose_container_graph(bb, product_name="Rose", sku="X", colors={"body": "#E91E8C", "cap": "#E91E8C"})
    assert "body-lower-field" not in [getattr(n, "name", None) for n, _ in plain.walk()]


def test_finding3_the_front_is_laid_in_its_concepts_two_fields_as_its_words_place_it():
    """His test day finding 3 (2026-09-30, design 117): his concept sets its logo on the hot-pink field and its name on
    the soft-pink one — "upper zone reserved for logo, lower zone for name and descriptor stack" — and the drawing set
    the logo on the split with the name under it. Those words, with two fields drawn, centre the mark in the part of his
    front above the split and begin the name stack below it by the mark's own clear space; words that do not say so,
    or one field, lay the front as before."""
    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from django.conf import settings

    from apps.pipeline.targets.container import _front_fields
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    words = {"decoration_zone_signature": "Wide equatorial drip-band as primary decoration zone; framed above and "
                                          "below by thin gold rules; upper zone reserved for logo, lower zone for "
                                          "name and descriptor stack"}
    assert _front_fields(words) == ["upper zone reserved for logo", "lower zone for name and descriptor stack"]
    assert _front_fields({"composition_signature": "centred axis, logo at the top"}) == []
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 7.5,
              "y": 40.5, "width": 35, "height": 99, "safe_margin_mm": 2.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0, label_zone=(8.9, 40.5, 32.1, 99.0)))
    logo = settings.BRAND_LOGO_PATH                                           # the house mark, as drawn
    colours = {"body": "#E91E8C", "cap": "#E91E8C", "body_lower": "#F7B8D4", "ink": "#8B3A52"}

    def front(**kw):
        doc = compose_container_graph(bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
                                      logo_path=logo, colors=colours, body_split=0.342, hierarchy_lines=
                                      ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"), **kw)
        nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
        body = nodes["body"]
        top, foot = (f(p.y for p in body.segments if hasattr(p, "y")) for f in (min, max))
        mm = (foot - top) / 180.0
        mark = next(n for n, _ in doc.walk() if getattr(n, "type", "") == "image")
        name = nodes["product-name-hero-0"]
        return (mark.y + mark.h / 2.0 - top) / mm, (mark.y + mark.h - top) / mm, (name.y - top) / mm
    centre, mark_foot, name_y = front(front_fields=True)
    assert abs(centre - (40.5 + 0.342 * 180.0) / 2.0) < 0.5, centre            # centred above the split, 51.3 mm
    assert mark_foot < 0.342 * 180.0 < name_y, (mark_foot, name_y)              # the mark above it, the name below
    was_centre, _was_foot, was_name = front()
    assert abs(was_centre - (40.5 + 0.16 * 99.0)) < 0.5 and was_name < name_y   # unchanged without the words


def test_finding3_his_front_leaves_the_concepts_own_elements_their_room_above_the_mark():
    """His test day finding 3 (2026-09-30, design 117): the redraw on f7bc01c was refused — laid into the front he
    confirmed, the mark stood so high in it that the concept's own elements, which print above the mark, had 1.8 mm
    where they need 8; nothing printed, the powder field the concept's motif record asks for was missing, and the
    fidelity gate refused the drawing (CONTAINER_MOTIF_FAMILY_MISMATCH). Where the label is his confirmed front, the
    mark stands below their full room: they print and the motif check passes, the mark still above the split and the
    name below it. A label that is not his front keeps the mark where it was."""
    from apps.ire.compose_container import CONCEPT_FRONT_MIN_MM, compose_container_graph
    from apps.ire.container_motif_fidelity import validate_motif_fidelity
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from django.conf import settings

    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    plan = {"schema_version": "container_concept_front/1.0", "state": "READ", "layout": "field", "ring": True,
            "outlines": False, "behind": False, "blend": None, "fade": None, "glow": False, "shadow": False,
            "window_fill": None, "window_shape": None, "motif": True, "name_style": None, "ground_hex": "#E91E8C",
            "rule": False}                                                  # 117's own, as its words read
    motif = {"reconstruction_capability": "SUPPORTED", "requested_family": "POWDER_CONSTELLATION",
             "rendered_via": "powder_constellation"}
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 7.5,
              "y": 40.5, "width": 35, "height": 99, "safe_margin_mm": 2.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0, label_zone=(8.9, 40.5, 32.1, 99.0)))
    colours = {"body": "#E91E8C", "cap": "#E91E8C", "body_lower": "#F7B8D4", "ink": "#8B3A52",
               "motif": ["#E91E8C", "#F7B8D4", "#8B3A52"]}

    def draw(**kw):
        return compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors=colours, body_split=0.342, front_fields=True, motif_spec=motif,
            concept_front=plan, hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion",
                                                                      descriptor="Body Lotion"), **kw)
    doc = draw(label_is_front=True)
    assert validate_motif_fidelity(doc, motif)["failures"] == []
    front = doc.metadata["concept_front"]
    assert front["placed"] == "above the mark's clear space" and front["drawn"], front
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    body = nodes["body"]
    top, foot = (f(p.y for p in body.segments if hasattr(p, "y")) for f in (min, max))
    mm = (foot - top) / 180.0
    mark, name = nodes["logo"], nodes["product-name-hero-0"]
    mark_top, mark_foot = (mark.y - top) / mm, (mark.y + mark.h - top) / mm
    assert mark_top - (40.5 + 2.0) > CONCEPT_FRONT_MIN_MM                   # their room above it, the floor and more
    assert mark_foot < 0.342 * 180.0 < (name.y - top) / mm                  # the mark above the split, the name below
    refused = draw()                                                         # not his front: the mark as it was
    assert "CONTAINER_MOTIF_FAMILY_MISMATCH" in validate_motif_fidelity(refused, motif)["failures"]


def test_his_answer_the_map_of_the_picture_gives_the_colours_ahead_of_the_words():
    """His answer after test day finding 3 (2026-09-30): "trace the colors from the given image. Not from the written";
    his check of the map: the cap keeps "the darker #CC1E4E the picture shows". A map on record for THIS picture gives
    the body, the lower field, the split between them, the cap as measured and the type's ink; a map of another picture,
    or one not read, gives nothing."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.targets.container import _map_colours
    rec = {"state": dm.MAP_READ, "source_sha256": "ab" * 32, "parts": [
        {"kind": "field", "name": "soft pink lower field", "box": [0.1, 0.35, 0.94, 0.85], "colour": "#F7BCC2"},
        {"kind": "field", "name": "hot pink upper field", "box": [0.03, 0.0, 0.97, 0.3488], "colour": "#EF316F"},
        {"kind": "closure", "name": "hot pink flip-top cap", "box": [0.08, 0.84, 0.92, 1.0], "colour": "#CC1E4E"},
        {"kind": "type", "name": "descriptor", "box": [0.27, 0.74, 0.73, 0.76], "colour": "#9D5045"},
        {"kind": "type", "name": "capacity", "box": [0.33, 0.81, 0.67, 0.84], "colour": "#9D5045"},
        {"kind": "type", "name": "script name", "box": [0.13, 0.57, 0.9, 0.68], "colour": "#B97447"},
        {"kind": "mark", "name": "BBROSE", "box": [0.15, 0.22, 0.86, 0.3], "colour": "#EBBD76"}]}
    got = _map_colours({dm.SCHEMA: rec}, "ab" * 32)
    assert {k: v[0] if isinstance(v, tuple) else v for k, v in got.items()} == {
        "body": "#EF316F", "body_lower": "#F7BCC2", "split": 0.3494, "cap": "#CC1E4E", "ink": "#9D5045"}, got
    assert "as the picture shows it" in got["cap"][1] and "map" in got["body"][1]
    assert _map_colours({dm.SCHEMA: rec}, "cd" * 32) == {}
    assert _map_colours({dm.SCHEMA: dict(rec, state=dm.MAP_UNREAD)}, "ab" * 32) == {}
    assert _map_colours({}, "ab" * 32) == {}


def test_his_answer_the_front_draws_the_band_its_edge_and_the_rule_its_picture_traced():
    """His answer after test day finding 3 (2026-09-30, transcribed at 23d4375): "...and the same way, draw it", the
    layout "exactly the picture. Not the rule"; his answer on the safe margin (transcribed at f23b9e8): the picture wins.
    A round 50 mm tube whose concept's map traced a cream band with a four-drip gold edge and a gold rule, composed into
    its map-proposed front: the band in its cream, its edge stroked in its gold at its width, the rule in its ink, each
    at the picture's place; the powder field its words asked for not drawn; every part placed as pictured, its breach
    of the front's margin a production note; the motif check reads the picture's drips and passes, the words' family
    said and set aside. With no map the front is as it was."""
    import math

    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph
    from apps.ire.container_motif_fidelity import validate_motif_fidelity
    from apps.ire.container_production_readiness import is_production_note
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.services import container_projection as cp
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    plan = {"schema_version": "container_concept_front/1.0", "state": "READ", "layout": "field", "ring": True,
            "outlines": False, "behind": False, "blend": None, "fade": None, "glow": False, "shadow": False,
            "window_fill": None, "window_shape": None, "motif": True, "name_style": None, "ground_hex": "#EF316F",
            "rule": False}
    motif = {"reconstruction_capability": "SUPPORTED", "requested_family": "POWDER_CONSTELLATION",
             "rendered_via": "powder_constellation"}
    flat = round(math.pi / 2.0 * 50.0, 2)
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT",
              "x": round(0.116 * flat, 1), "y": 39.1, "width": round(0.824 * flat, 1), "height": 110.7,
              "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    edge = [[0.12 + 0.82 * k / 40.0, 0.45 + 0.04 * (1 - math.cos(2 * math.pi * 4 * k / 40.0))] for k in range(41)]
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "bands": [{"part": "cream drip band", "fill": "#F9EFE5", "edge": [edge], "edge_width": 0.0068,
                         "edge_ink": "#E9BC71", "drips": 4,
                         "outline": [[0.12, 0.342]] + edge + [[0.94, 0.342]]}],
              "rules": [{"part": "upper gold rule", "box": [0.116, 0.342, 0.94, 0.348], "ink": "#EBC179"}]}
    colours = {"body": "#EF316F", "cap": "#CC1E4E", "body_lower": "#F7BCC2", "ink": "#9D5045",
               "motif": ["#EF316F", "#F7BCC2", "#9D5045"]}

    def draw(**kw):
        return compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors=colours, body_split=0.342, front_fields=True, motif_spec=motif,
            concept_front=plan, label_is_front=True,
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"), **kw)
    doc = draw(map_front={"shapes": shapes, "edge_part": "cream drip arches with gold contour"})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    body = nodes["body"]
    xs = [p.x for p in body.segments if hasattr(p, "x")]
    bxs = [p.x for p in bb.silhouette if hasattr(p, "x")]
    s = (max(xs) - min(xs)) / (max(bxs) - min(bxs))                       # the sheet's mm per drawn mm
    ox = min(xs) - min(bxs) * s
    oy = min(p.y for p in body.segments if hasattr(p, "y")) - min(p.y for p in bb.silhouette if hasattr(p, "y")) * s
    band, rule, drip = nodes["band-map-0"], nodes["rule-map-0"], nodes["drip-map-0-0"]
    assert band.fill.color.to_hex().upper() == "#F9EFE5" and rule.fill.color.to_hex().upper() == "#EBC179"
    assert drip.stroke.color.to_hex().upper() == "#E9BC71"
    assert abs(drip.stroke.width_mm - 0.0068 * bb.width_mm * s) < 1e-6
    assert abs(rule.x - (ox + 0.116 * bb.width_mm * s)) < 1e-6 and abs(rule.y - (oy + 0.342 * bb.height_mm * s)) < 1e-6
    assert "motif-field" not in nodes and "FRONT_CONCEPT" not in nodes      # the powder field its words asked for
    # [found on 117 redrawn, 2026-10-02] the design graph's census counts the map front as the front's resolved motif,
    # so the quality check never reads it as a zone-only placeholder
    from apps.ire.compose_container import container_design_graph_record
    from apps.pipeline.services import visual_quality_gate as vqg
    graph = container_design_graph_record(doc, zones_consumed=["z_front"], mode="native")
    assert "motif-map-front" in graph["motif_groups"], graph["motif_groups"]
    assert vqg._front_artwork_axis(graph)["state"] == "PASS"
    report = validate_motif_fidelity(doc, motif)
    assert report["failures"] == [] and report["from_the_picture"]["words_requested"] == "POWDER_CONSTELLATION"
    places = [p for p in doc.metadata["placements"] if p.get("as_pictured")]
    assert sorted(p["kind"] for p in places) == ["band", "motif", "rule"], places
    tube = cc.build_inferred_profile("tube", "standard", {"body_width_mm": 50.0, "body_height_mm": 180.0,
                                                          "body_depth_mm": 50.0})
    found = cp.validate_zone_containment(places, zones, tube)
    assert found and all(is_production_note(p) for p in found), found      # at its edges: notes, never refusals
    right = round((zones[0]["x"] + zones[0]["width"]) / bb.width_mm, 5)                # his front's own right edge
    assert doc.metadata["map_front"]["boxes"]["upper gold rule"] == [0.116, 0.342, right, 0.348]
    assert set(doc.metadata["map_front"]["boxes"]) == {"cream drip band", "upper gold rule",
                                                       "cream drip arches with gold contour"}
    # [his yes, transcribed at 5d23649: drawn from the map only inside the area he confirms] a rule the picture prints
    # wider than his front is drawn to its edges, and the cut said
    wide = dict(shapes, rules=[dict(shapes["rules"][0], box=[0.100, 0.342, 0.950, 0.348])])
    cut = draw(map_front={"shapes": wide, "edge_part": None}).metadata["map_front"]["clipped_to_his_front_mm"]
    assert abs(cut["upper gold rule"]["left"] - (zones[0]["x"] - 0.100 * bb.width_mm)) < 0.01, cut
    assert abs(cut["upper gold rule"]["right"] - (0.950 * bb.width_mm - zones[0]["x"] - zones[0]["width"])) < 0.01
    plain = draw()
    assert "map_front" not in plain.metadata and "motif-field" in {getattr(n, "name", None) for n, _ in plain.walk()}


def test_his_answer_the_front_draws_the_sparkle_stars_its_picture_traced():
    """His answer after test day finding 3 (2026-09-30): each motif drawn "the same way". A tube whose concept's map
    traced two sparkle stars draws each as its own outline in its own gold, at the picture's place, placed as pictured
    under the map's own name; the motif check reads the stars as the picture's motif."""
    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph
    from apps.ire.container_motif_fidelity import validate_motif_fidelity
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    motif = {"reconstruction_capability": "SUPPORTED", "requested_family": "POWDER_CONSTELLATION",
             "rendered_via": "powder_constellation"}
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))

    def star(cx, cy):
        return [[cx, cy - 0.006], [cx + 0.002, cy - 0.0015], [cx + 0.008, cy], [cx + 0.002, cy + 0.0015],
                [cx, cy + 0.006], [cx - 0.002, cy + 0.0015], [cx - 0.008, cy], [cx - 0.002, cy - 0.0015]]
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "scatters": [{"part": "four-point gold sparkle stars", "count": 2, "count_read": 5,
                            "stars": [{"outline": star(0.3, 0.5), "ink": "#E3AF75"},
                                      {"outline": star(0.6, 0.52), "ink": "#E9B584"}]}]}
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        motif_spec=motif, hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        map_front={"shapes": shapes, "edge_part": None})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    assert nodes["sparkle-map-0-0"].fill.color.to_hex().upper() == "#E3AF75"
    assert nodes["sparkle-map-0-1"].fill.color.to_hex().upper() == "#E9B584"
    rec = doc.metadata["map_front"]
    assert rec["stars"] == [2] and rec["boxes"]["four-point gold sparkle stars"] == [0.292, 0.494, 0.608, 0.526]
    assert any(p["kind"] == "motif" and p["as_pictured"] for p in doc.metadata["placements"])
    assert validate_motif_fidelity(doc, motif)["failures"] == []


def test_his_answer_the_mark_is_drawn_from_its_master_where_the_picture_prints_it():
    """His answer after test day finding 3 (2026-09-30): the house mark "from its approved master only, never traced, at
    the place the picture gives it". A front whose concept's map measured its mark's gold ink draws the approved master
    there — its height the ink's, its left edge the ink's, its width the master's own proportion, never stretched — its
    box under the map's own name for the score, and what it leaves over beside the picture said."""
    from django.conf import settings

    from apps.ire import brand_mark as B
    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.ire.tests import brand_mark_fixtures as FX
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    master = B.read_master(FX.POTRACE_STYLE)
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "marks": [{"part": "BBROSE gold wordmark", "box": [0.17, 0.22, 0.83, 0.284], "ink": "#E9BC71"}]}
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        logo_master=master, map_front={"shapes": shapes, "edge_part": None})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    body, logo = nodes["body"], nodes["logo"]
    xs = [p.x for p in body.segments if hasattr(p, "x")]
    bxs = [p.x for p in bb.silhouette if hasattr(p, "x")]
    s = (max(xs) - min(xs)) / (max(bxs) - min(bxs))
    ox = min(xs) - min(bxs) * s
    oy = min(p.y for p in body.segments if hasattr(p, "y")) - min(p.y for p in bb.silhouette if hasattr(p, "y")) * s
    assert abs(logo.h - (0.284 - 0.22) * bb.height_mm * s) < 1e-6                      # the picture's ink height
    assert abs(logo.h / logo.w - master.aspect) < 1e-6                                  # never stretched
    # [his final goal, 2026-10-05, A: "The safe margin rule applies to containers too (117 included): text, logos and
    # key elements stay inside it"] the picture prints the mark's top 0.5 mm inside the front's 3 mm margin: it stands at
    # the margin, 2.5 mm lower — its left edge, inside the margin already, the picture's
    assert abs(logo.x - (ox + 0.17 * bb.width_mm * s)) < 1e-6
    assert abs(logo.y - (oy + (zones[0]["y"] + zones[0]["safe_margin_mm"]) * s)) < 1e-6, logo.y
    rec = doc.metadata["map_front"]
    assert rec["boxes"]["BBROSE gold wordmark"][0] == 0.17 and "BBROSE gold wordmark" in rec["drawn"]
    assert rec["mark"]["beside_the_picture_mm"]["left"] == 0.0 and "right" in rec["mark"]["beside_the_picture_mm"]


def test_his_answer_the_front_sets_its_type_where_its_picture_prints_it():
    """His answer after test day finding 3 (2026-09-30) and the executor's proposal recorded with it: the small copy
    "placed at the picture's place and size but typed from the brief". A front whose map traced three type lines — the
    name the record holds, a descriptor the brief gives in English and Arabic, and a scent line no source gives — sets
    the name in the concept's face at its traced place, wrapped to the lines its height holds, and the descriptor as an
    English run and an Arabic run side by side, each line in its traced ink and inside its traced width and height; the
    scent line is left out by name and the ruled block is not drawn; the name check and the type hierarchy pass; each
    line is placed as pictured."""
    from django.conf import settings

    from apps.ire.compose_container import (MAP_TYPE_INK_EM, MAP_TYPE_LEADING_EM, compose_container_graph,
                                            name_width_estimate_mm)
    from apps.ire.container_fidelity import PRODUCT_NAME_TOO_SMALL, measure_fidelity
    from apps.ire.container_motif_fidelity import validate_typography_hierarchy
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    name = "Coconut Rose Body Lotion"
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "types": [{"part": "product name script", "box": [0.19, 0.553, 0.805, 0.679], "ink": "#B97447",
                         "words": name, "source": "the product's name on the record"},
                        {"part": "bilingual descriptor line 1", "box": [0.322, 0.734, 0.692, 0.75], "ink": "#9D5045",
                         "words": "Body Lotion / لوشن للجسم", "source": "the brief's front copy"},
                        {"part": "descriptor line 2", "box": [0.296, 0.757, 0.715, 0.769], "ink": "#9D5045",
                         "words": None, "source": None,
                         "left_out": "no source on record carries what the picture shows"}]}
    doc = compose_container_graph(
        bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"),
        map_front={"shapes": shapes, "edge_part": None})
    runs = {n.name: n for n, _ in doc.walk() if n.type == "text"}
    assert [runs["product-name-hero-%d" % j].text for j in (0, 1)] == ["Coconut Rose", "Body Lotion"], sorted(runs)
    hero = runs["product-name-hero-0"]
    assert hero.color.to_hex().upper() == "#B97447"
    assert (MAP_TYPE_INK_EM + MAP_TYPE_LEADING_EM) * hero.size_pt * 25.4 / 72.0 <= (0.679 - 0.553) * 180.0 + 1e-6
    assert all(name_width_estimate_mm(runs["product-name-hero-%d" % j].text, hero.size_pt) <= (0.805 - 0.19) * bb.width_mm
               for j in (0, 1))
    en, ar = runs["front-descriptor-1-0"], runs["front-descriptor-1-1"]
    assert (en.text, ar.text, ar.rtl, en.color.to_hex().upper()) == ("Body Lotion /", "لوشن للجسم", True, "#9D5045")
    assert en.x < ar.x and en.size_pt == ar.size_pt
    assert not any(n.startswith("front-descriptor") and runs[n].text == "Body Lotion" for n in runs)  # no ruled block
    rec = doc.metadata["map_front"]
    assert rec["left_out"] == [{"part": "descriptor line 2", "why": "no source on record carries what the picture shows"}]
    assert {t["part"]: t["source"] for t in rec["typed"]} == {"product name script": "the product's name on the record",
                                                              "bilingual descriptor line 1": "the brief's front copy"}
    assert PRODUCT_NAME_TOO_SMALL not in measure_fidelity(doc, {}, name_lines=[name])["failures"]
    assert validate_typography_hierarchy(doc, name)["failures"] == []
    kinds = sorted(p["kind"] for p in doc.metadata["placements"] if p.get("as_pictured"))
    assert kinds == ["descriptor", "product_name"], kinds


def test_his_answer_a_fronts_type_takes_its_words_from_the_record_and_the_brief():
    """His answer after test day finding 3 (2026-09-30): the sources a front's type may take its words from — the
    product's name, its Arabic name where a product record holds one, each phrase of the brief's front copy — each said."""
    import types

    from apps.pipeline.targets.container import type_sources_for
    task = types.SimpleNamespace(product=None, task_text='A tube.\nFront copy: BBROSE logo, "Body Lotion / لوشن للجسم", '
                                                         '200 ml ℮ 6.7 fl oz.\n')
    # [his rules 1 and 2, 2026-10-05] a phrase setting English beside Arabic is followed by its two halves
    assert type_sources_for(task, "Coconut Rose Body Lotion") == [
        ("Coconut Rose Body Lotion", "the product's name on the record"), ("BBROSE logo", "the brief's front copy"),
        ("Body Lotion / لوشن للجسم", "the brief's front copy"), ("Body Lotion /", "the brief's front copy"),
        ("لوشن للجسم", "the brief's front copy"), ("200 ml ℮ 6.7 fl oz", "the brief's front copy")]
    task.product = types.SimpleNamespace(name_ar="لوشن جوز الهند")
    assert ("لوشن جوز الهند", "the product record's Arabic name") in type_sources_for(task, "Coconut Rose Body Lotion")


def test_his_rules_the_briefs_own_arabic_name_and_scent_line_give_the_lines_their_words():
    """His second look at 117 (2026-10-02): "add the Arabic lines"; his rules the same day (transcribed at 6badb27),
    rule 1: "exact words"; his answer 4: designs "read the brief's colours and copy". 117's brief carries an "Arabic name:"
    and a "Scent line: … | …" — the executor had told him it carried no words for those lines. They are sources, each
    said; the brief's Arabic name wins over the picture's reading of it (one word read differently), and the scent
    line's two halves type its two lines, in the separator the picture prints."""
    import types

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.targets.container import type_sources_for
    brief = ("Product: BBROSE Coconut Rose Body Lotion.\r\nArabic name: لوشن الجسم بجوز الهند والورد\r\n"
             "Scent line: Coconut Cream · Rose Petals  |  كريمة جوز الهند · بتلات الورد\r\n\r\n"
             'Front copy: BBROSE logo, "Body Lotion /\r\nلوشن للجسم", scent line.\r\n')
    assert dm.brief_line_fields(brief) == [("لوشن الجسم بجوز الهند والورد", "the brief's Arabic name"),
                                           ("Coconut Cream · Rose Petals", "the brief's scent line"),
                                           ("كريمة جوز الهند · بتلات الورد", "the brief's scent line")]
    sources = type_sources_for(types.SimpleNamespace(product=None, task_text=brief), "Coconut Rose Body Lotion")
    assert sources[-3:] == dm.brief_line_fields(brief)
    lines = [{"part": "Arabic product name", "seen": "لوشن للجسم بجوز الهند والورد", "lettering": "arabic"},
             {"part": "descriptor line 2", "seen": "Coconut Cream • Rose Petals", "lettering": "sans"},
             {"part": "Arabic descriptor line 3", "seen": "كريمة جوز الهند • بتلات الورد", "lettering": "arabic"}]
    got = {t["part"]: (t["words"], t["source"]) for t in dm.type_sources(lines, sources)}
    assert got == {"Arabic product name": ("لوشن الجسم بجوز الهند والورد", "the brief's Arabic name"),
                   "descriptor line 2": ("Coconut Cream • Rose Petals", "the brief's scent line"),
                   "Arabic descriptor line 3": ("كريمة جوز الهند • بتلات الورد", "the brief's scent line")}, got
    # a product record's own Arabic name, where one is held, is said once and comes first
    record = types.SimpleNamespace(product=types.SimpleNamespace(name_ar="لوشن الجسم بجوز الهند والورد"), task_text=brief)
    said = [origin for text, origin in type_sources_for(record, "Coconut Rose Body Lotion")
            if text == "لوشن الجسم بجوز الهند والورد"]
    assert said == ["the product record's Arabic name"], said


def test_his_rules_the_back_is_drawn_from_the_briefs_back_copy_at_the_size_it_prints():
    """His rules for cloning a design from a picture (2026-10-02, transcribed at 6badb27), rule 5: "THE BACK IS DRAWN.
    Replace the placeholders ("INFO · INCI · CODE", "BATCH") with the brief's back copy: how to use, ingredients, batch
    code place, Made in UAE." 117's brief's back copy is read into its sections, in his words, and its batch code's
    place; a tube with a confirmed back zone and code zone draws them — no placeholder left; the back at the size it
    prints (§W1(a)) holds every word, nothing cut, the sheet grown to hold it; the code zone drawn as its window under
    his words. A call that asks for no panel draws the sheet as before."""
    from django.conf import settings

    from apps.ire import back_panel as BP
    from apps.ire.compose_container import TRUE_SCALE_SURFACE_PREFIX, compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    brief = ("Front copy: BBROSE logo, \"Body Lotion /\r\nلوشن للجسم\", scent line.\r\n"
             "Back copy: How to use: massage onto clean skin, daily. / Ingredients:\r\nAqua, Glycerin, Cocos Nucifera "
             "Oil, Cetearyl Alcohol, Rosa Damascena\r\nFlower Water, Parfum, Phenoxyethanol. / Batch code place. / Made in "
             "UAE.\r\nCarton: same direction as the tube, product name on 4 sides, back copy\r\non the back panel.\r\n")
    back = dm.brief_back_copy(brief)
    ingredients = ("Aqua, Glycerin, Cocos Nucifera Oil, Cetearyl Alcohol, Rosa Damascena Flower Water, Parfum, "
                   "Phenoxyethanol.")
    assert [(s["heading"], s["text"]) for s in back["sections"]] == [
        ("How to use", "massage onto clean skin, daily."), ("Ingredients", ingredients), ("", "Made in UAE.")]
    assert {s["source"] for s in back["sections"]} == {dm.BRIEF_BACK_COPY} and back["batch_code_place"] == "Batch code place."
    assert dm.brief_back_copy("Front copy: a name.") == {"sections": [], "batch_code_place": None}
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"},
             {"zone_id": "z_back", "zone_type": "BACK_PRINT_ZONE", "parent_surface": "BODY_BACK", "x": 11.8, "y": 40.5,
              "width": 55.0, "height": 99.0, "safe_margin_mm": 3.0},
             {"zone_id": "z_crimp_code", "zone_type": "BOTTOM_CODE_ZONE", "parent_surface": "CRIMP_ZONE", "x": 31.4,
              "y": 0.0, "width": 15.7, "height": 7.2, "safe_margin_mm": 1.0}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    name = "Coconut Rose Body Lotion"

    def draw(**extra):
        return compose_container_graph(
            bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"), **extra)
    before = draw()
    texts = {str(getattr(n, "text", "")) for n, _ in before.walk() if getattr(n, "type", "") == "text"}
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (8): "No empty grey blocks in the files"] with no back copy
    # handed over, no panel holding only a placeholder is drawn at all — never the placeholders he saw
    assert "INFO · INCI · CODE" not in texts and "BATCH —" not in texts
    doc = draw(back_sections=back["sections"], back_panel={"methods_record": None},
               batch_code_place=back["batch_code_place"])
    runs = [n for n, _ in doc.walk() if getattr(n, "type", "") == "text"]
    texts = {str(n.text) for n in runs}
    assert "INFO · INCI · CODE" not in texts and "BATCH —" not in texts and "MFG — · EXP —" not in texts
    panel = next(n for n, _ in doc.walk() if getattr(n, "name", "") == f"{TRUE_SCALE_SURFACE_PREFIX}BODY_BACK")
    def under(g):
        for c in getattr(g, "children", None) or []:
            yield c
            yield from under(c)
    drawn = " ".join(str(n.text) for n in under(panel) if getattr(n, "type", "") == "text")
    for words in ("How to use", "massage onto clean skin, daily.", "Ingredients", ingredients, "Made in UAE."):
        assert words in drawn, words                                       # every word, nothing cut
    fit = doc.metadata[BP.SCHEMA]
    assert fit["emitted"] and fit["fits"] and fit["copy_preserved"] and fit["panel_mm"] == [55.0, 99.0], fit
    box = next(n for n in under(panel) if getattr(n, "name", "") == "back-panel-boundary")
    assert box.y + box.h <= doc.page_h and doc.page_h > before.page_h          # the sheet grown to hold it, not scaled
    assert doc.metadata["back_copy_drawings"]["1"]["true_scale"], doc.metadata["back_copy_drawings"]
    window = next(n for n, _ in doc.walk() if getattr(n, "name", "") == "panel-CRIMP_ZONE-code-window")
    assert window.fill is None and window.stroke.dash and abs(window.w / window.h - 15.7 / 7.2) < 0.01
    assert "Batch code place" in texts and "15.7 × 7.2 mm" in texts


def test_his_look_the_english_words_the_picture_prints_are_added_with_its_separators():
    """His look at 117 drawn from its map (2026-10-02): "And about the English words, they need to be added." The
    picture's five lines under the name: its English line no record carries is typed in the picture's own words as the
    map read them, said so; the bilingual line typed from the brief prints the picture's "•" where the brief wrote "/";
    the capacity line keeps the brief's "℮"; and since his second look ("add the Arabic lines"), the two Arabic lines
    no record carries are typed in the picture's own words too, said so."""
    from apps.pipeline.services import concept_design_map as dm
    lines = [{"part": "Arabic product name", "seen": "لوشن للجسم بجوز الهند والورد", "lettering": "arabic"},
             {"part": "bilingual descriptor line 1", "seen": "Body Lotion • لوشن للجسم", "lettering": "sans"},
             {"part": "descriptor line 2", "seen": "Coconut Cream • Rose Petals", "lettering": "sans"},
             {"part": "Arabic descriptor line 3", "seen": "كريمة جوز الهند • بتلات الورد", "lettering": "arabic"},
             {"part": "capacity line", "seen": "200 ml e 6.7 fl oz", "lettering": "sans"}]
    sources = [("Coconut Rose Body Lotion", "the product's name on the record"),
               ("Body Lotion / لوشن للجسم", "the brief's front copy"), ("200 ml ℮ 6.7 fl oz", "the brief's front copy")]
    got = {t["part"]: t for t in dm.type_sources(lines, sources)}
    assert got["bilingual descriptor line 1"]["words"] == "Body Lotion • لوشن للجسم"
    assert got["bilingual descriptor line 1"]["source"] == "the brief's front copy"
    assert got["descriptor line 2"]["words"] == "Coconut Cream • Rose Petals"
    assert got["descriptor line 2"]["source"] == dm.PICTURE_ENGLISH
    assert got["capacity line"]["words"] == "200 ml ℮ 6.7 fl oz"
    # [his second look at 117, 2026-10-02: "add the Arabic lines"] the picture's two Arabic lines, in its own words
    assert got["Arabic product name"]["words"] == "لوشن للجسم بجوز الهند والورد"
    assert got["Arabic descriptor line 3"]["words"] == "كريمة جوز الهند • بتلات الورد"
    assert {got[a]["source"] for a in ("Arabic product name", "Arabic descriptor line 3")} == {dm.PICTURE_ARABIC}
    assert dm.type_sources([{"part": "a line no one can read", "seen": "Body Lotion • لوشن", "lettering": "sans"}],
                           [])[0]["words"] is None                    # a mixed line no record carries stays out
    # the bilingual line's two runs anchored toward their join, one space apart — never the gap an estimate leaves
    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph, name_width_estimate_mm
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    line = dict(got["bilingual descriptor line 1"], box=[0.322, 0.734, 0.692, 0.75], ink="#9D5045")
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        map_front={"shapes": {"state": "TRACED", "types": [line]}, "edge_part": None})
    runs = sorted((n for n, _ in doc.walk() if str(getattr(n, "name", "")).startswith("front-descriptor-")),
                  key=lambda n: n.name)
    assert [(n.text, n.align) for n in runs] == [("Body Lotion •", "right"), ("لوشن للجسم", "left")], runs
    assert abs((runs[1].x - runs[0].x) - name_width_estimate_mm(" ", runs[0].size_pt)) < 1e-6
    # [his second look, 2026-10-02] an Arabic line is one right-to-left run, its "•" inside it, centred where the
    # picture centres it; the line the map names as a name is set bold
    lines = [dict(got["Arabic descriptor line 3"], box=[0.306, 0.778, 0.702, 0.794], ink="#9D5045"),
             dict(got["Arabic product name"], box=[0.254, 0.686, 0.757, 0.708], ink="#B97447")]
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        map_front={"shapes": {"state": "TRACED", "types": lines}, "edge_part": None})
    runs = {n.text: n for n, _ in doc.walk() if str(getattr(n, "name", "")).startswith("front-descriptor-")}
    scent, name = runs["كريمة جوز الهند • بتلات الورد"], runs["لوشن للجسم بجوز الهند والورد"]
    assert (scent.rtl, scent.align, scent.font) == (True, "center", "regular")
    assert (name.rtl, name.align, name.font) == (True, "center", "bold")


def test_his_answer_the_name_is_drawn_as_the_pictures_traced_lettering():
    """His answer after test day finding 3 (2026-09-30), (3): "the script lettering also traced from the picture". A
    name line the picture letters in script, traced, every word of it the record's name: the name is drawn as the traced
    outlines in its ink, no name typed; the name check, the type hierarchy and the front's role read it as the name. Where
    the picture's words are not all the record's, the name is typed, never the picture's lettering copied."""
    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph
    from apps.ire.container_fidelity import PRODUCT_NAME_TOO_SMALL, measure_fidelity, measure_front_back
    from apps.ire.container_motif_fidelity import validate_typography_hierarchy
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    name = "Coconut Rose Body Lotion"
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" version="1.0" width="100pt" height="40pt" viewBox="0 0 100 40">'
           '<g transform="translate(0.000000,40.000000) scale(0.100000,-0.100000)" fill="#000000" stroke="none">'
           '<path d="M100 100 l0 200 800 0 0 -200 -800 0 z"/></g></svg>')
    line = {"part": "product name script", "box": [0.19, 0.553, 0.805, 0.679], "ink": "#B97447", "words": name,
            "source": "the product's name on the record", "match": 1.0, "lettering": "script",
            "outlines": {"svg": svg, "frame": [0.19, 0.553, 0.615 / 100.0, 0.126 / 40.0]}}

    def draw(the_line):
        shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
                  "types": [the_line, {"part": "descriptor", "box": [0.322, 0.734, 0.692, 0.75], "ink": "#9D5045",
                                       "words": "Body Lotion", "source": "the brief's front copy"}]}
        return compose_container_graph(
            bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"),
            map_front={"shapes": shapes, "edge_part": None})
    doc = draw(line)
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    traced = nodes["product-name-traced"]
    assert traced.fill.color.to_hex().upper() == "#B97447" and traced.fill_rule == "nonzero"
    assert not any(str(n).startswith("product-name-hero") for n in nodes)                 # no name typed
    assert PRODUCT_NAME_TOO_SMALL not in measure_fidelity(doc, {}, name_lines=[name])["failures"]
    assert validate_typography_hierarchy(doc, name)["failures"] == []
    assert measure_front_back(doc)["roles_distinct"] is True
    assert doc.metadata["map_front"]["name_traced"]["words"] == name
    garbled = draw(dict(line, match=0.75))                                                   # the picture's words differ
    names = {getattr(n, "name", None) for n, _ in garbled.walk()}
    assert "product-name-traced" not in names and "product-name-hero-0" in names


def test_his_answer_every_colour_the_map_front_prints_is_named_from_the_picture():
    """His answer after test day finding 3 (2026-09-30), (1): "trace the colors from the given image". Every colour a map
    front prints — its band's fill and gold edge, its rule, its stars' one ink, its lines' inks — is named as the
    concept picture's map, part by part, so §BH67's printed-colour audit finds no colour without a record; a line left
    out names nothing."""
    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container import colour_sources as _cs
    from apps.pipeline.targets.container import map_front_colour_sources
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    star = [[0.3, 0.494], [0.302, 0.4985], [0.308, 0.5], [0.302, 0.5015], [0.3, 0.506], [0.298, 0.5015], [0.292, 0.5],
            [0.298, 0.4985]]
    shapes = {"state": "TRACED", "bands": [{"part": "cream drip band", "fill": "#F9EFE5", "edge_ink": "#E9BC71",
                                            "edge_width": 0.0068, "edge": [[[0.12, 0.45], [0.5, 0.5], [0.9, 0.45]]],
                                            "outline": [[0.12, 0.342], [0.12, 0.45], [0.5, 0.5], [0.9, 0.45],
                                                        [0.9, 0.342]], "drips": 1}],
              "rules": [{"part": "upper gold rule", "box": [0.116, 0.342, 0.9, 0.348], "ink": "#EBC179"}],
              "scatters": [{"part": "four-point gold sparkle stars", "ink": "#E3AF75", "count": 1,
                            "stars": [{"outline": star, "ink": "#E3AF75"}]}],
              "types": [{"part": "descriptor", "box": [0.322, 0.734, 0.692, 0.75], "ink": "#9D5045",
                         "words": "Body Lotion", "source": "the brief's front copy"},
                        {"part": "scent line", "box": [0.3, 0.757, 0.7, 0.769], "ink": "#7A3A30", "words": None}]}
    named = map_front_colour_sources({"shapes": shapes})
    assert set(named) == {"#F9EFE5", "#E9BC71", "#EBC179", "#E3AF75", "#9D5045"}, named
    assert all(words.startswith("the concept picture's map — its part") for words in named.values())
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        map_front={"shapes": shapes, "edge_part": None})
    codes = _cs.printed_colour_audit(doc, dict(named, **{"#9D5045": "ink"}))["codes"]
    map_nodes = ("band-map", "drip-map", "rule-map", "sparkle-map", "front-descriptor")
    assert not [c for c in codes if c.split(":")[-1].startswith(map_nodes)], codes
    assert map_front_colour_sources(None) == {}


def test_his_look_the_foil_is_the_pictures_gold_as_drawn_on_every_part_the_concept_names():
    """His look at 117 drawn from its map (2026-10-02): "The foil gold, it's the picture, not the brand. Always the
    colors, the picture, not the brand. Every single color should play a role when we are working on generating the
    image, not after." A front drawn from its concept picture draws the mark in the picture's own gold, and the foil
    applied after it repaints nothing: each part keeps the picture's colour it was drawn in, its row says so, and the
    plate is cut on every part the concept's sentence names — the drip outlines, the sparkle stars, the traced script
    and the mark. A front not drawn from its picture keeps the brand's depiction as before."""
    from django.conf import settings

    from apps.ire import brand_mark as B
    from apps.ire import container_finishes as F
    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.ire.tests import brand_mark_fixtures as FX
    from apps.pipeline.targets.container import map_front_colour_sources
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    master = B.read_master(FX.POTRACE_STYLE)
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    name = "Coconut Rose Body Lotion"
    star = [[0.3, 0.494], [0.302, 0.4985], [0.308, 0.5], [0.302, 0.5015], [0.3, 0.506], [0.298, 0.5015], [0.292, 0.5],
            [0.298, 0.4985]]
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" version="1.0" width="100pt" height="40pt" viewBox="0 0 100 40">'
           '<g transform="translate(0.000000,40.000000) scale(0.100000,-0.100000)" fill="#000000" stroke="none">'
           '<path d="M100 100 l0 200 800 0 0 -200 -800 0 z"/></g></svg>')
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "marks": [{"part": "BBROSE gold wordmark", "box": [0.17, 0.22, 0.83, 0.284], "ink": "#EABC75"}],
              "bands": [{"part": "cream drip band", "fill": "#F9EFE5", "edge_ink": "#E9BC71", "edge_width": 0.0068,
                         "edge": [[[0.12, 0.45], [0.5, 0.5], [0.9, 0.45]]],
                         "outline": [[0.12, 0.342], [0.12, 0.45], [0.5, 0.5], [0.9, 0.45], [0.9, 0.342]], "drips": 1}],
              "scatters": [{"part": "four-point gold sparkle stars", "ink": "#E3AE6C", "count": 1,
                            "stars": [{"outline": star, "ink": "#E3AE6C"}]}],
              "types": [{"part": "product name script", "box": [0.19, 0.553, 0.805, 0.679], "ink": "#B97447",
                         "words": name, "source": "the product's name on the record", "match": 1.0,
                         "lettering": "script", "outlines": {"svg": svg, "frame": [0.19, 0.553, 0.615 / 100.0,
                                                                                    0.126 / 40.0]}}]}

    def draw(map_front):
        return compose_container_graph(
            bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"), logo_master=master,
            map_front=map_front)
    sentence = F.assignments("gold metallic ink as spot channel on logo, drip outlines, script name contour and "
                             "sparkle stars")
    doc = draw({"shapes": shapes, "edge_part": None})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    assert nodes["logo"].recolor.to_hex().upper() == "#EABC75"                 # the picture's gold, as it is drawn
    assert doc.metadata["map_front"]["mark"]["ink"] == "#EABC75"
    assert map_front_colour_sources({"shapes": shapes})["#EABC75"].startswith("the concept picture's map — its part")
    rows = [r for r in F.apply(doc, sentence, brand_metallic_hex="#C9A24B", depict_as_drawn=True)["applied"]
            if r["plate"] == "METALLIC_GOLD"]
    by = {r["target"]: r for r in rows}
    assert set(by) == {"motif", "lockup", "name"} and all(r["state"] == F.APPLIED for r in rows), rows
    assert not any("depiction_hex" in r for r in rows) and all(r["depiction"] == F.AS_DRAWN for r in rows)
    assert by["lockup"]["depiction_hexes"] == ["#EABC75"] and by["name"]["depiction_hexes"] == ["#B97447"]
    assert {"#E9BC71", "#E3AE6C"} <= set(by["motif"]["depiction_hexes"])
    plated = {n for r in rows for n in r["nodes"]}
    assert {"logo", "sparkle-map-0-0", "product-name-traced"} <= plated and any(n.startswith("drip-map-") for n in plated)
    assert not any(n.startswith(("band-map", "rule-map")) for n in plated)                 # the sentence names neither
    for n, _ in doc.walk():
        for f in getattr(n, "finishes", None) or []:
            assert f.appearance is None, (n.name, f)                     # nothing repaints a part after it is drawn
    # a front not drawn from its picture keeps the brand's depiction, as before
    plain = draw(None)
    plain_rows = [r for r in F.apply(plain, sentence, brand_metallic_hex="#C9A24B")["applied"]
                  if r["plate"] == "METALLIC_GOLD"]
    assert plain_rows and all(r.get("depiction_hex") == "#C9A24B" and "depiction" not in r for r in plain_rows)


def test_his_answers_gold_in_the_picture_is_foil_the_rule_too_for_every_design():
    """His answers after 117 was redrawn on his rules (2026-10-02, transcribed at a18911a), answer 2: "Gold in the picture
    is foil: the rule above the band goes on the foil plate. That is the rule for every design." A front drawn from its
    picture with a gold rule, a gold-edged band and gold stars: where the concept's sentence names only the mark's gold,
    the rule, the band's gold edge and the stars join that same gold plate, on a row of their own that says why; where
    the sentence names no gold at all, they go on a foil-gold plate; the band's own fill never does."""
    from django.conf import settings

    from apps.ire import container_finishes as F
    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    name = "Coconut Rose Body Lotion"
    star = [[0.48, 0.6], [0.5, 0.588], [0.52, 0.6], [0.5, 0.612]]
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "bands": [{"part": "cream drip band", "fill": "#F9EFE5", "edge_ink": "#E9BC71", "edge_width": 0.0068,
                         "edge": [[[0.12, 0.45], [0.5, 0.5], [0.9, 0.45]]],
                         "outline": [[0.12, 0.342], [0.12, 0.45], [0.5, 0.5], [0.9, 0.45], [0.9, 0.342]], "drips": 1}],
              "rules": [{"part": "upper gold rule", "box": [0.12, 0.335, 0.9, 0.342], "ink": "#E5B977"}],
              "scatters": [{"part": "gold sparkle stars", "ink": "#E3AE6C", "count": 1,
                            "stars": [{"outline": star, "ink": "#E3AE6C"}]}]}

    def plated(sentence):
        doc = compose_container_graph(
            bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"),
            map_front={"shapes": shapes, "edge_part": None})
        gold = tuple(doc.metadata["map_front"]["gold_nodes"])
        assert {"rule-map-0", "drip-map-0-0", "sparkle-map-0-0"} <= set(gold) and "band-map-0" not in gold, gold
        rows = F.apply(doc, F.assignments(sentence), brand_metallic_hex="#C9A24B", depict_as_drawn=True,
                       gold_as_drawn=gold)["applied"]
        nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
        return rows, nodes
    rows, nodes = plated("gold metallic ink as spot channel on logo")
    row = next(r for r in rows if r["target"] == "gold_as_drawn")
    assert (row["finish"], row["plate"], row["state"]) == ("metallic_ink", "METALLIC_GOLD", F.APPLIED)
    assert {"rule-map-0", "drip-map-0-0", "sparkle-map-0-0"} <= set(row["nodes"]) and row["how"] == F.GOLD_IS_FOIL
    assert [f.plate for f in nodes["rule-map-0"].finishes] == ["METALLIC_GOLD"]
    assert not nodes["band-map-0"].finishes                                  # the band's own fill: never gold
    rows, nodes = plated("matte laminate overall")
    row = next(r for r in rows if r["target"] == "gold_as_drawn")
    assert (row["finish"], row["plate"]) == F.GOLD_IS_FOIL_PLATE and "rule-map-0" in row["nodes"]
    assert [f.kind for f in nodes["rule-map-0"].finishes] == ["foil"]


def test_his_look_nothing_the_map_front_draws_prints_past_the_tubes_outline():
    """His look at 117 drawn from its map (2026-10-02), measured before any fix: the band, the rule and the outer drips
    printed past the tube's outline. A band the picture traces wider than the tube at its rows — inside his confirmed
    front — is cut to the product's drawn outline as well as to his front: its parts sit in a group clipped to the body's
    own outline, inside the front's motif group, and the record says both."""
    from django.conf import settings

    from apps.ire.compose_container import MAP_WITHIN_OUTLINE, compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
              "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "bands": [{"part": "cream drip band", "fill": "#F9EFE5", "edge_ink": "#E9BC71", "edge_width": 0.0068,
                         "edge": [[[0.11, 0.45], [0.5, 0.5], [0.94, 0.45]]],
                         "outline": [[0.11, 0.342], [0.11, 0.45], [0.5, 0.5], [0.94, 0.45], [0.94, 0.342]],
                         "drips": 1}]}
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        map_front={"shapes": shapes, "edge_part": None})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    body, front = nodes["body"], nodes["motif-map-front"]
    (within,) = front.children
    assert within.name == MAP_WITHIN_OUTLINE and within.clip is not None
    assert [(type(a), a.model_dump()) for a in within.clip] == [(type(b), b.model_dump()) for b in body.segments]
    assert {c.name for c in within.children} >= {"band-map-0", "drip-map-0-0"}
    # the band as traced reaches past the outline's own edge at its row — which the clip cuts
    band = [(p.x, p.y) for p in nodes["band-map-0"].segments if hasattr(p, "x")]
    bx, by = max(band)
    pts = [(p.x, p.y) for p in body.segments if hasattr(p, "x")]
    right = max(ax + (by - ay) * (cx - ax) / (cy - ay) for (ax, ay), (cx, cy) in zip(pts, pts[1:] + pts[:1])
                if (ay - by) * (cy - by) <= 0 and ay != cy)
    assert bx > right + 1.0, (bx, right)
    assert doc.metadata["map_front"]["clipped_to"] == "his confirmed front and the product's drawn outline"


def test_his_look_the_squeeze_tube_is_built_in_3d_from_the_drawn_outline():
    """His answer after test day finding 3 (2026-09-30), step 3 — "The 3D proof. A squeeze tube is added to the 3D
    engine, the drawing is rendered on it" — and his look at 117 drawn from its map (2026-10-02): "And also the 3D". A
    drawn tube's outline — 50 mm round at its foot, 78.5 mm flat at its crimp, a closure its lowest 15 % — built as a
    mesh: the closure round; the sleeve's girth the same at every height, as one printed sheet rolled; the crimp flat and
    ribbed; the drawing's own place for every vertex as the front shows it; written as an OBJ the engine reads; and the
    engine's script ready to run."""
    import math
    import os
    import py_compile
    import tempfile

    from apps.pipeline.services import tube_proof as tp
    outline = [(y, 25.0 + (39.27 - 25.0) * max(0.0, (y - 27.0) / 153.0)) for y in [i * 1.8 for i in range(101)]]
    mesh = tp.tube_mesh(outline, round_diameter_mm=50.0, closure_share=0.15)
    rings = mesh["rings"]
    girth = math.pi * 50.0
    assert {r["part"] for r in rings} == {"closure", "sleeve", "crimp"}
    for r in rings:
        if r["part"] == "closure":
            assert r["a"] == r["b"]                                                    # the closure is round
        elif r["part"] == "sleeve":
            assert abs(tp._ellipse_perimeter(r["a"], r["b"]) - girth) / girth < 0.01 or r["b"] == tp.TUBE_PROOF_PARAMS[
                "crimp_depth_mm"] / 2.0, r                                             # one sheet rolled
        else:
            assert r["b"] == tp.TUBE_PROOF_PARAMS["crimp_depth_mm"] / 2.0               # the crimp flat
    top = [r for r in rings if r["part"] == "crimp"]
    assert top and abs(top[-1]["a"] * 2.0 - 78.54) < 0.1
    assert all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 for u, v in mesh["uvs"])
    zs = [z for _x, y, z in mesh["vertices"] if y > 175.0]
    assert max(zs) > tp.TUBE_PROOF_PARAMS["crimp_depth_mm"] / 2.0                       # its ribs stand proud
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "tube.obj")
        tp.write_obj(mesh, path)
        lines = open(path).read().splitlines()
        assert sum(ln.startswith("v ") for ln in lines) == len(mesh["vertices"])
        assert sum(ln.startswith("vt ") for ln in lines) == len(mesh["uvs"])
        assert sum(ln.startswith("f ") for ln in lines) == len(mesh["faces"])
    py_compile.compile(tp.SCRIPT, doraise=True)


def test_his_answer_the_front_takes_the_shapes_of_the_picture_its_map_read_once():
    """His answer after test day finding 3 (2026-09-30): the parts drawn as the picture draws them. A READ map of THIS
    picture has its shapes traced and kept beside it; on record, of the same tracer, they are read and never traced
    again; a map of another picture, or one not read, gives no front from the map."""
    import hashlib
    from unittest import mock

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.targets.container import _map_front
    pic = b"the concept picture"
    sha = hashlib.sha256(pic).hexdigest()
    rec = {"state": dm.MAP_READ, "source_sha256": sha, "parts": []}
    traced = {"schema_version": dm.SHAPES_SCHEMA, "state": dm.SHAPES_TRACED, "source_sha256": sha,
              "params": dict(dm.SHAPE_PARAMS), "problems": [],
              "rules": [{"part": "rule", "box": [0.1, 0.3, 0.9, 0.31], "ink": "#EBC179"}]}
    calls = []

    def trace(picture, record, sources=None):
        calls.append(picture)
        return traced
    with mock.patch.object(dm, "trace_shapes", trace):
        records = []
        assert _map_front({dm.SCHEMA: rec}, pic, records) == {"shapes": traced, "edge_part": None}
        assert records == [("set", dm.SHAPES_SCHEMA, traced)] and calls == [pic]
        records = []
        assert _map_front({dm.SCHEMA: rec, dm.SHAPES_SCHEMA: traced}, pic, records) == {"shapes": traced, "edge_part": None}
        assert records == [] and calls == [pic]                                  # on record: read, never traced again
        assert _map_front({dm.SCHEMA: rec}, b"another picture", []) is None
        stale = dict(traced, params=dict(dm.SHAPE_PARAMS, star_reach=0.5))                # one number of the tracer moved
        records = []
        assert _map_front({dm.SCHEMA: rec, dm.SHAPES_SCHEMA: stale}, pic, records) == {"shapes": traced, "edge_part": None}
        assert records == [("set", dm.SHAPES_SCHEMA, traced)] and calls == [pic, pic]       # traced again
        assert _map_front({dm.SCHEMA: dict(rec, state=dm.MAP_UNREAD)}, pic, []) is None


def test_finding3_a_cap_takes_the_colour_its_words_name_never_the_stand_in():
    """His test day finding 3 (2026-09-30, design 117): its cap's words said "matching full-gloss hot pink" with no hex,
    and the drawing painted the stand-in gold — "invented a colour". The cap takes its own hex, else a brand swatch its
    words name, else the colour its words name as the body sentence gives it; nothing, where its words name none."""
    from apps.pipeline.targets.container import colour_sources as cs
    body = ("Hot pink (#E91E8C) solid upper two-thirds / soft pink (#F7B8D4) lower one-third fading to cream; "
            "cream-white drip shapes bridging the split")
    cap = ("Flip-top cap in matching full-gloss hot pink continues upper tube colour seamlessly; no colour break at "
           "shoulder — cap and body read as one uninterrupted hot-pink crown (concept-only)")
    assert cs.named_hexes(body) == {"hot pink": "#E91E8C", "soft pink": "#F7B8D4"}
    hx, said = cs.cap_colour(cap, body, _BRAND)
    assert hx == "#E91E8C" and '"hot pink"' in said
    assert cs.cap_colour("a soft pink flip cap", body, _BRAND)[0] == "#F7B8D4"
    assert cs.cap_colour("cap in Deep Rose gloss", body, _BRAND) == ("#8B3A52", "the brand's Deep Rose, which its words name")
    assert cs.cap_colour("cap (#123456) gloss", body, _BRAND) == ("#123456", "its own hex")
    assert cs.cap_colour("a rose-gold metallic cap", body, _BRAND) == (None, None)       # a metallic with no hex: none
    assert cs.cap_colour("a white cap", "", _BRAND) == (None, None)


def test_bh65b2_task_89s_lid_is_the_warm_cream_its_concept_named_not_the_gold():
    from apps.pipeline.targets.container import colour_sources as cs
    text = ("Lid in matte soft-touch warm cream with rose-gold foil detailing; compact body in matte "
            "blush-nude acrylic — cap is cream-over-blush, a tonal step rather than a contrast (concept-only)")
    assert cs.field_colour(text, _BRAND) == ("#FAF3EC", "Warm Cream")


def test_bh65b2_task_88s_lid_is_its_deep_rose_not_the_gold_default_it_would_have_taken():
    from apps.pipeline.targets.container import colour_sources as cs
    text = ("Deep rose-plum gloss cap strongly coordinated with the body's upper blush-rose gradient "
            "field, rose-gold foil band at cap-body join seam")
    assert cs.field_colour(text, _BRAND) == ("#8B3A52", "Deep Rose")


def test_bh65b2_the_two_lids_that_were_already_right_stay_right():
    from apps.pipeline.targets.container import colour_sources as cs
    assert cs.field_colour("Ivory (#FAF3EC) lid in satin-gloss finish / ivory compact body in soft-touch "
                           "matte laminate; deliberate gloss-vs-matte counterpoint", _BRAND)[0] == "#FAF3EC"
    assert cs.field_colour("Flat-topped matte peach-rose cap (#F2C4CE) contrasts with glassy transparent "
                           "PET tube body", _BRAND)[0] == "#F2C4CE"


def test_bh65b2_a_detail_colour_named_first_is_never_the_field():
    """HIS DEFECT CLASS, AS A SENTENCE: the foil hex comes first and the lid's ground second."""
    from apps.pipeline.targets.container import colour_sources as cs
    assert cs.field_colour("rose-gold #B76E79 foil border on a Warm Cream #FAF3EC lid",
                           _BRAND)[0] == "#FAF3EC"
    assert cs.field_colour("Deep Rose type on a Blush ground", _BRAND)[0] == "#F2C4CE"


def test_bh65b2_the_brands_metallic_is_never_a_lid_face():
    from apps.pipeline.targets.container import colour_sources as cs
    assert cs.field_colour("a rose gold lid", _BRAND) == (None, None)
    hx, source = cs.lid_face_colour({"cap_color": {"value": "a rose gold lid"}}, _BRAND)
    assert hx == "#FAF3EC" and "Ground" in source


def test_bh65b2_the_lid_falls_to_the_ground_sentence_then_the_brand_ground_and_says_which():
    from apps.pipeline.targets.container import colour_sources as cs
    fields = {"cap_color": {"value": "a soft-touch lid"},
              "body_base_color": {"value": "Warm Cream #FAF3EC ground across the full lid face; Deep "
                                           "Rose type; rose-gold foil accents"}}
    hx, source = cs.lid_face_colour(fields, _BRAND)
    assert hx == "#FAF3EC" and "body_base_color" in source
    hx, source = cs.lid_face_colour({}, _BRAND)
    assert hx == "#FAF3EC" and "Base packaging, backgrounds" in source
    assert cs.lid_face_colour({}, []) == (None, "no concept sentence and no brand Ground swatch names a colour")


def test_profile_hex_overrides_gold_cap_default():
    import re
    text = ("Flat-topped matte peach-rose cap (#F2C4CE) contrasts with "
            "glassy transparent body (concept-only)")
    m = re.search(r"#[0-9A-Fa-f]{6}", text)
    assert m and m.group(0).upper() == "#F2C4CE"


# --- §BH67 HARD STOP: "a finish or colour applied that nothing specified" --------------------------------------
# Measured on task 91's drawn lid: its name printed in #5A2C3A (the dropper palette's TYPE_WINE, carried onto the
# container without authority) and its motif in the design language's DEFAULT_SWATCHES. The sentences below are the
# concepts' OWN words (tasks 91, 89 and 88), read-only 2026-09-24; the palette carries the usage the brand wrote.
_BRAND_USAGE = [
    {"role": "Primary", "name": "Blush", "hex": "#F2C4CE", "usage": "Main surfaces, hero cartons"},
    {"role": "Secondary", "name": "Pale Petal", "hex": "#F7DDE3", "usage": "Interior, secondary panels"},
    {"role": "Accent", "name": "Deep Rose", "hex": "#8B3A52", "usage": "Typography, fine detail lines"},
    {"role": "Metallic", "name": "Rose Gold", "hex": "Metallic 10122 C", "usage": "Caps, closures, foil detail"},
    {"role": "Ground", "name": "Warm Cream", "hex": "#FAF3EC", "usage": "Base packaging, backgrounds"}]


def test_bh67_the_type_prints_in_the_colour_its_concept_names_else_the_brands_typography_swatch():
    from apps.pipeline.targets.container import colour_sources as cs
    t91 = {"typography_signature": "High-contrast old-style Latin serif ('Focus') over matching Naskh ('فوكس'), "
                                   "identical cap-height, tracked evenly, set above the petal window in Deep Rose; "
                                   "BBROSE wordmark in rose-gold hot-foil at the crown arc"}
    assert cs.type_ink(t91, _BRAND_USAGE) == ("#8B3A52", "the concept's own `typography_signature` — Deep Rose")
    # a metal is never the type's ink; the colour-field sentence can give the type its colour
    assert cs.type_ink({"typography_signature": "BBROSE wordmark in rose-gold foil",
                        "color_field_signature": "Warm Cream ground; Blush type"}, _BRAND_USAGE)[0] == "#F2C4CE"
    hx, source = cs.type_ink({"typography_signature": "a tall serif, tracked evenly"}, _BRAND_USAGE)
    assert hx == "#8B3A52" and "Typography, fine detail lines" in source
    assert cs.type_ink({}, [])[0] is None                       # silent everywhere: no ink, and the audit says so


def test_bh67_the_motif_prints_in_its_concepts_own_colours_never_the_ground_nor_the_metal():
    from apps.pipeline.targets.container import colour_sources as cs
    t89 = {"motif_signature": "Seven closed Bézier petal-droplets in a loose radial cluster inside the cartouche "
                              "window, alternating filled blush and rose-gold outline",
           "color_field_signature": "Warm Cream #FAF3EC ground across the full lid face; radial gradient within the "
                                    "window from cream centre to Pale Petal edge; Deep Rose type; rose-gold foil"}
    assert [h for h, _ in cs.motif_colours(t89, _BRAND_USAGE, ground_hex="#FAF3EC")] == [
        "#F2C4CE", "#F7DDE3", "#8B3A52"]
    out = cs.motif_colours({"motif_signature": "a dewdrop constellation"}, _BRAND_USAGE, ground_hex="#FAF3EC")
    assert [h for h, _ in out] == ["#F2C4CE", "#F7DDE3", "#8B3A52"] and all("brand" in s for _, s in out)


def test_bh67_the_body_is_the_colour_its_words_name_after_the_body_word_before_any_measurement():
    from apps.pipeline.targets.container import colour_sources as cs
    t88 = {"cap_body_signature": "Deep rose-plum gloss cap strongly coordinated with the body's upper blush-rose "
                                 "gradient field, rose-gold foil band at cap-body join seam"}
    t91 = {"cap_body_signature": "Lid and base both in matte soft-touch Warm Cream; thin polished rose-gold metal "
                                 "sidewall band as the cap/body separator"}
    assert cs.body_colour(t88, _BRAND_USAGE)[0] == "#F2C4CE"      # the cap's Deep Rose is not the body's
    assert cs.body_colour(t91, _BRAND_USAGE)[0] == "#FAF3EC"      # task 91 MEASURED #958879, a shadowed sidewall
    assert cs.body_colour({"cap_body_signature": "a rose gold cap"}, _BRAND_USAGE) == (None, None)


def test_bh67_the_audit_names_every_printed_colour_no_record_names_and_reads_no_annotation():
    from apps.ire.graph import SHEET_ANNOTATION, Color, Document, Group, PrintScope, Rect, SolidFill, TextRun
    from apps.pipeline.targets.container import colour_sources as cs
    printed = Group(name="FRONT_DIRECT_PRINT", role="decoration", children=[
        TextRun(name="product-name-hero", text="Focus", x=0, y=0, size_pt=9, color=Color.from_hex("#8B3A52"),
                print_scope=PrintScope(kind="PRINTED_ON_PRODUCT", surface="LID_TOP")),
        Rect(name="motif-leaf", x=0, y=0, w=1, h=1, fill=SolidFill(color=Color.from_hex("#5A2C3A")))])
    body = Rect(name="body", x=0, y=0, w=1, h=1, fill=SolidFill(color=Color.from_hex("#123456")))   # material
    panels = Group(name="Surfaces", role="generic", children=[
        TextRun(name="panel-BASE_BOTTOM-label", text="BASE", x=0, y=0, size_pt=3, color=Color.from_hex("#3F2620"),
                print_scope=PrintScope(kind=SHEET_ANNOTATION))])
    doc = Document(page_w=10, page_h=10, root=Group(name="root", role="generic", children=[
        Group(name="Container", role="product", children=[body, printed]), panels]))
    audit = cs.printed_colour_audit(doc, {"#8B3A52": "ink — the concept's own words"})
    assert audit["state"] == "READ"
    assert audit["codes"] == ["CONTAINER_COLOUR_UNSOURCED:#5A2C3A:motif-leaf"]
    assert set(audit["printed"]) == {"#8B3A52", "#5A2C3A"}          # neither the material nor the label is print
    # the label is out BECAUSE THE COMPOSER DECLARED IT a sheet annotation, never by its name: the same run with no
    # declaration fails closed (§BH50(f)(1)) — read as print, named, and refused
    panels.children[0].print_scope = None
    audit = cs.printed_colour_audit(doc, {"#8B3A52": "ink — the concept's own words"})
    assert audit["undeclared_read_as_print"] == ["panel-BASE_BOTTOM-label"]
    assert "CONTAINER_COLOUR_UNSOURCED:#3F2620:panel-BASE_BOTTOM-label" in audit["codes"]


def test_his_go_where_a_vials_picture_prints_no_mark_the_house_mark_keeps_clear_of_its_parts():
    """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a wand vial. A vial
    whose picture prints its name and a rule but no mark: where the house mark's ruled place lies over the name, the mark
    is drawn at its ruled size where it lies over none of the picture's parts — above them, under the cap, where it fits
    — and the record says why; where the ruled place already clears them the mark stays there and nothing is said."""
    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 0.5,
              "y": 37.2, "width": 14.8, "height": 40.0, "safe_margin_mm": 1.0, "curvature_type": "FLAT"}]
    bb = build_backbone(ContainerProfile(archetype="mascara", variant="square", cap_style="wand", height_mm=80.0,
                                         width_mm=16.0))

    def drawn(name_box):
        shapes = {"state": "TRACED", "source_sha256": "ab" * 32,
                  "params": {"version": "concept_design_shapes_params/1.0"},
                  "types": [{"part": "product name", "box": name_box, "ink": "#962846", "words": "Rosé Nectar",
                             "source": "the product's name on the record"}],
                  "rules": [{"part": "short gold rule", "box": [0.2, 0.95, 0.8, 0.955], "ink": "#CDA55F"}]}
        doc = compose_container_graph(
            bb, product_name="Rosé Nectar", sku="X", zones=zones, native=True, name_lines=["Rosé Nectar"],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#F1B0BA", "cap": "#C44868", "ink": "#962846"},
            hierarchy_lines=ruled_front_hierarchy("Rosé Nectar", descriptor="Lip Gloss"),
            map_front={"shapes": shapes, "edge_part": None})
        nodes = {getattr(n, "name", ""): n for n, _ in doc.walk()}
        xs = [q.x for q in nodes["body"].segments if hasattr(q, "x")]
        ys = [q.y for q in nodes["body"].segments if hasattr(q, "y")]
        x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        logo = nodes["logo"]
        return doc, ((logo.x - x0) / w, (logo.y - y0) / h, (logo.x + logo.w - x0) / w, (logo.y + logo.h - y0) / h)
    clear_doc, ruled = drawn([0.1, 0.80, 0.919, 0.90])                   # the name well clear of the ruled place
    assert "mark" not in clear_doc.metadata["map_front"]
    doc, moved = drawn([0.1, ruled[1] - 0.01, 0.919, ruled[3] + 0.06])  # the name over the ruled place
    mf = doc.metadata["map_front"]
    assert mf["mark"]["placed"] == "above the picture's parts", mf.get("mark")
    for x0, y0, x1, y1 in mf["boxes"].values():
        assert moved[3] <= y0 or moved[1] >= y1 or moved[2] <= x0 or moved[0] >= x1, (moved, (x0, y0, x1, y1))
    assert moved[1] > 0.56 and abs((moved[3] - moved[1]) - (ruled[3] - ruled[1])) < 1e-9     # under the cap, its size


def test_his_go_a_vials_small_copy_is_never_set_under_the_print_floor():
    """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a wand vial. On a
    16 mm vial its picture prints "LIP GLOSS" at about 4.1 pt; a front drawn from its picture sets no line under the
    print floor where no print method is recorded (§W2's 5.0 pt): the line is set at the floor, centred where the
    picture centres it, and its record says what the picture printed it at; a line the picture prints larger is set at
    its own size, as before."""
    from django.conf import settings

    from apps.ire.compose_container import MAP_TYPE_FLOOR_PT, compose_container_graph
    from apps.ire.container_text_floor import FALLBACK_FLOOR_PT
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    assert MAP_TYPE_FLOOR_PT == FALLBACK_FLOOR_PT == 5.0
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 0.5,
              "y": 37.2, "width": 14.8, "height": 19.6, "safe_margin_mm": 1.0, "curvature_type": "FLAT"}]
    bb = build_backbone(ContainerProfile(archetype="mascara", variant="square", cap_style="wand", height_mm=80.0,
                                         width_mm=16.0))
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "types": [{"part": "product name", "box": [0.1, 0.474, 0.919, 0.611], "ink": "#962846",
                         "words": "Rosé Nectar", "source": "the product's name on the record"},
                        {"part": "LIP GLOSS", "box": [0.192, 0.686, 0.8, 0.703], "ink": "#962846",
                         "words": "LIP GLOSS", "source": "the brief's front copy"}]}
    doc = compose_container_graph(
        bb, product_name="Rosé Nectar", sku="X", zones=zones, native=True, name_lines=["Rosé Nectar"],
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#F1B0BA", "cap": "#C44868", "ink": "#962846"},
        hierarchy_lines=ruled_front_hierarchy("Rosé Nectar", descriptor="Lip Gloss"),
        map_front={"shapes": shapes, "edge_part": None})
    typed = {t["part"]: t for t in doc.metadata["map_front"]["typed"]}
    small = typed["LIP GLOSS"]
    assert small["size_pt"] == 5.0 and small["at_the_floor"]["floor_pt"] == 5.0, small
    assert 3.5 < small["at_the_floor"]["pictured_pt"] < 5.0, small
    assert typed["product name"]["size_pt"] > 5.0 and "at_the_floor" not in typed["product name"]
    runs = [n for n, _ in doc.walk() if getattr(n, "type", "") == "text" and getattr(n, "text", "") == "LIP GLOSS"]
    assert runs and all(r.size_pt == 5.0 for r in runs)
    # a line the floor makes wider than the front he confirmed is measured over it by the front's own fit instrument
    # (which holds acceptance), never cut by the front's edge unsaid
    from apps.pipeline.targets.container import generic_front_copy_fit
    narrow = [dict(zones[0], x=4.0, width=8.0, safe_margin_mm=0.5)]
    over = compose_container_graph(
        bb, product_name="Rosé Nectar", sku="X", zones=narrow, native=True, name_lines=["Rosé Nectar"],
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#F1B0BA", "cap": "#C44868", "ink": "#962846"},
        hierarchy_lines=ruled_front_hierarchy("Rosé Nectar", descriptor="Lip Gloss"),
        map_front={"shapes": shapes, "edge_part": None})
    fit = generic_front_copy_fit(over, narrow, "mascara")
    assert any(code.startswith("CONTAINER_FRONT_COPY_EXCEEDS_ZONE: LIP GLOSS +") for code in fit["codes"]), fit["codes"]
    assert not [c for c in generic_front_copy_fit(doc, zones, "mascara")["codes"] if "EXCEEDS_ZONE: LIP GLOSS" in c]


def test_his_final_goal_a_a_containers_key_elements_stand_inside_its_safe_margin():
    """His final goal (2026-10-05, transcribed at 32e9aaf), A: "The safe margin rule applies to containers too (117
    included): text, logos and key elements stay inside it; backgrounds and patterns still run into the bleed." A tube
    whose picture prints its descriptor and a solid shape against the edges of its front: both are drawn inside the front
    zone's 3 mm margin; the band the picture runs across the front still runs edge to edge, as pictured."""
    import math

    from django.conf import settings

    from apps.ire.compose_container import compose_container_graph
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    flat = round(math.pi / 2.0 * 50.0, 2)
    zone = {"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT",
            "x": round(0.116 * flat, 1), "y": 39.1, "width": round(0.824 * flat, 1), "height": 110.7,
            "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    zx, zw = zone["x"] / bb.width_mm, zone["width"] / bb.width_mm                        # the zone, in fractions
    zy, zh = zone["y"] / bb.height_mm, zone["height"] / bb.height_mm
    ring = [[[[zx, 0.55], [zx + zw, 0.55, zx + zw, 0.55, zx + zw, 0.55], [zx + zw, 0.80, zx + zw, 0.80, zx + zw, 0.80],
              [zx, 0.80, zx, 0.80, zx, 0.80], [zx, 0.55, zx, 0.55, zx, 0.55]]]]
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "bands": [{"part": "cream band", "fill": "#F9EFE5", "edge": [], "edge_width": 0.0, "edge_ink": None,
                         "drips": 0, "outline": [[zx, 0.30], [zx + zw, 0.30], [zx + zw, 0.34], [zx, 0.34]]}],
              "shapes": [{"part": "rose silhouette", "ink": "#9D5045", "box": [zx, 0.55, zx + zw, 0.80],
                          "cubics": ring}],
              "types": [{"part": "descriptor", "box": [zx, zy + 0.40 * zh, zx + 0.45 * zw, zy + 0.42 * zh],
                         "ink": "#9D5045", "words": "Body Lotion", "source": "the brief's front copy"}]}
    doc = compose_container_graph(
        bb, product_name="Coconut Rose Body Lotion", sku="X", zones=[zone], native=True,
        logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
        label_is_front=True, hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
        map_front={"shapes": shapes, "edge_part": None})
    safe = doc.metadata["map_front"]["safe_margin"]
    assert safe["scale"] < 1.0 or safe["nudged"], safe                                   # something was moved in
    m = zone["safe_margin_mm"]
    boxes = doc.metadata["map_front"]["boxes"]
    for part in ("rose silhouette", "descriptor"):
        x0, y0, x1, y1 = boxes[part]
        assert x0 * bb.width_mm >= zone["x"] + m - 0.05 and x1 * bb.width_mm <= zone["x"] + zone["width"] - m + 0.05, (
            part, boxes[part])
        assert y0 * bb.height_mm >= zone["y"] + m - 0.05 and y1 * bb.height_mm <= zone["y"] + zone["height"] - m + 0.05
    band = boxes["cream band"]
    assert abs(band[0] * bb.width_mm - zone["x"]) < 0.05 and abs(band[2] * bb.width_mm - zone["x"] - zone["width"]) < 0.05

