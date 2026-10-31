"""Container silhouette backbone (Phase B1, 2026-07-08).

The container's structural backbone — its answer to the dieline. Pins that
each archetype builds a well-formed frame: a closed outline, a cap region,
a label zone inside the box, and the logo/product-name anchors the composer
needs. Geometry is structural (not manufacturing-accurate), so tests check
validity and bounds, not exact coordinates.
"""
from __future__ import annotations

import pytest

from apps.ire.graph import ClosePath, MoveTo, Path, SolidFill, Color
from apps.pipeline.targets.container.silhouettes import (
    SUPPORTED_ARCHETYPES,
    ContainerProfile,
    build_backbone,
)


def _closed(segments) -> bool:
    return bool(segments) and isinstance(segments[0], MoveTo) and \
        isinstance(segments[-1], ClosePath)


def _within(rect, w, h) -> bool:
    x, y, rw, rh = rect
    return x >= -0.01 and y >= -0.01 and x + rw <= w + 0.01 and y + rh <= h + 0.01


@pytest.mark.parametrize("archetype", SUPPORTED_ARCHETYPES)
def test_each_archetype_builds_a_valid_backbone(archetype):
    b = build_backbone(ContainerProfile(archetype=archetype,
                                        height_mm=110, width_mm=40))
    assert b.archetype == archetype
    assert _closed(b.silhouette)                 # closed outline
    assert _closed(b.cap_region)                 # closed cap zone
    assert _within(b.label_zone, b.width_mm, b.height_mm)
    assert {"logo", "product_name"} <= set(b.anchors)
    # anchors sit inside the box
    for ax, ay in b.anchors.values():
        assert 0 <= ax <= b.width_mm and 0 <= ay <= b.height_mm


def test_the_supported_set_is_exactly_the_forms_that_can_be_drawn():
    """§BH55(a): compact joins, for the owner's Phase 1 palette. RENAMED — the old name said "three".

    The set is asserted exactly, so a form added without a builder, or a builder added without the editor
    entry that lets a person confirm it, fails here.
    """
    # §BH70(1), 2026-09-27: lipstick, mascara and pencil join, each with its own builder and its own editor card.
    # Was: == {"bottle", "jar", "tube", "compact"}.
    # [§BH71 PART 3, the owner's goal of 2026-09-28: "Add each as a shape the system can draw." — the tin, the
    # sachet, the oval stick, the aerosol can and the ampoule join, each with its own builder and its own card]
    assert set(SUPPORTED_ARCHETYPES) == {"bottle", "jar", "tube", "compact", "lipstick", "mascara", "pencil",
                                         "tin", "sachet", "oval_stick", "aerosol", "ampoule"}


def test_bh71_every_catalogue_shape_is_a_shape_the_system_draws_at_its_own_size():
    """§BH71 PART 3, the owner's goal of 2026-09-28: \"Use the web search to build the list of cosmetic product types
    and their real packaging, with typical sizes ... Add each as a shape the system can draw.\" Every shape of the
    catalogue (targets/container/shapes.py, 39, each with its pages) is a declared form with one of that form's own
    variants and closures, the shape step accepts its size at both ends of the pages' ranges, and it is drawn at
    its typical size — closed, inside its box, its label inside — with its zones and one code place valid."""
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets import ui
    from apps.pipeline.targets.container import archetypes as A
    from apps.pipeline.targets.container import shapes
    assert len(shapes.SHAPES) == 39 and len({s["id"] for s in shapes.SHAPES}) == 39
    for s in shapes.SHAPES:
        form, variant, closure = s["form"], s["variant"], s["closure"]
        assert variant in dict(A.variants_of(form)) and closure in dict(A.closures_of(form)), s["id"]
        assert s["sources"] and all(u.startswith("https://") for u in s["sources"]), s["id"]
        for end in (0, 1):
            size = {"%s_mm" % k: v[end] for k, v in s["size_mm"].items()}
            payload = dict(size, archetype=form, variant=variant, cap_style=closure)
            assert ui.validate_container_profile_payload(payload) == [], (s["id"], end, payload,
                                                                         ui.validate_container_profile_payload(payload))
        size = shapes.typical_size(s)
        if form != "bottle" or closure != "dropper":             # the dropper draws the M3 assembly
            bb = build_backbone(ContainerProfile(archetype=form, variant=variant, cap_style=closure,
                                                 width_mm=size["width_mm"], height_mm=size["height_mm"]))
            assert bb.archetype == form and type(bb.silhouette[-1]).__name__ == "ClosePath", s["id"]
            lx, ly, lw, lh = bb.label_zone
            assert 0 <= lx and lx + lw <= bb.width_mm + 1e-6 and 0 <= ly and ly + lh <= bb.height_mm + 1e-6, s["id"]
        record = cc.merge_user_profile(cc.build_inferred_profile(form, variant), {
            "archetype": form, "variant": variant, "cap_type": closure, "body_height_mm": size["height_mm"],
            "body_width_mm": size["width_mm"], "body_depth_mm": size["depth_mm"]})
        zones = cc.augment_code_zones(record, cc.propose_zones(record))
        assert cc.validate_zone_set(zones, record) == [], (s["id"], cc.validate_zone_set(zones, record))
        assert len([z for z in zones if z["zone_type"] == "BOTTOM_CODE_ZONE"]) == 1, s["id"]


def test_bh71_the_catalogues_closures_and_variants_are_each_their_own_drawing():
    """§BH71 PART 3: \"It never squeezes a product into the wrong shape.\" A nail polish's brush cap is taller than a
    screw cap, a perfume's crimped spray wider, an airless pump's overcap as wide as its body; an airless bottle has no
    neck, a roll-on is a vial; a cushion compact is round; a paperboard palette's corners are a book's; a sifter jar's
    lid is deep and an airless jar carries its button; a liner pen's cap is a third of it and a click pen has none."""
    def cap_box(**kw):
        bb = build_backbone(ContainerProfile(**kw))
        xs = [s.x for s in bb.cap_region if hasattr(s, "x")]
        ys = [s.y for s in bb.cap_region if hasattr(s, "y")]
        return max(xs) - min(xs), max(ys) - min(ys)
    base = dict(archetype="bottle", variant="cylindrical", width_mm=40.0, height_mm=100.0)
    screw = cap_box(**base, cap_style="screw")
    assert cap_box(**base, cap_style="brush_cap")[1] > 2 * screw[1]
    assert cap_box(**base, cap_style="crimp_spray")[0] > 1.5 * screw[0]
    assert abs(cap_box(**dict(base, variant="airless"), cap_style="airless_pump")[0] - 0.98 * 40.0) < 1e-6
    drawn = {v: build_backbone(ContainerProfile(**dict(base, variant=v), cap_style="screw")).silhouette
             for v in ("cylindrical", "airless", "flacon", "roller")}
    assert len({tuple((round(s.x, 3), round(s.y, 3)) for s in path if hasattr(s, "x")) for path in drawn.values()}) == 4
    cushion = build_backbone(ContainerProfile(archetype="compact", variant="cushion", width_mm=80.0, height_mm=80.0))
    assert [type(s).__name__ for s in cushion.silhouette].count("CubicTo") == 4           # a circle
    book = build_backbone(ContainerProfile(archetype="compact", variant="paperboard", width_mm=120.0, height_mm=80.0))
    assert book.silhouette[0].x < 3.0                                            # its corners a book's, 2 %
    jar = dict(archetype="jar", width_mm=60.0, height_mm=50.0, cap_style="screw")
    assert cap_box(**jar, variant="sifter")[1] > 1.2 * cap_box(**jar, variant="standard")[1]    # 40 % of it, not 32
    assert min(s.y for s in build_backbone(ContainerProfile(**jar, variant="airless")).silhouette
               if hasattr(s, "y")) == 0.0 and cap_box(**jar, variant="airless")[1] > cap_box(**jar, variant="standard")[1]
    pen = dict(archetype="pencil", width_mm=10.0, height_mm=120.0)
    assert cap_box(**pen, variant="pen", cap_style="cap")[1] > cap_box(**pen, variant="sharpened", cap_style="cap")[1]
    assert cap_box(**pen, variant="pen", cap_style="click")[1] < 0.1 * 120.0


def test_bh71_each_new_form_is_drawn_by_a_builder_of_its_own():
    """§BH71 PART 3: every variant of the five new forms is drawn closed inside its own box, its closure and its label
    inside the outline's box, each variant its own drawing — a round tin a circle, a slide tin its rectangle, a sachet
    notched at its tear seal, an ampoule's glass bulb, plastic tab and vial stopper three outlines."""
    from apps.pipeline.targets.container import archetypes as A
    for form in ("tin", "sachet", "oval_stick", "aerosol", "ampoule"):
        nominal, caps = A.nominal_of(form), [k for k, _ in A.closures_of(form)]
        drawn = set()
        for variant, _label in A.variants_of(form):
            bb = build_backbone(ContainerProfile(archetype=form, variant=variant, cap_style=caps[0],
                                                 width_mm=float(nominal["width_mm"]),
                                                 height_mm=float(nominal["height_mm"])))
            assert bb.archetype == form and type(bb.silhouette[-1]).__name__ == "ClosePath", (form, variant)
            for path in (bb.silhouette, bb.cap_region):
                pts = [(s.x, s.y) for s in path if hasattr(s, "x")]
                assert all(-1e-6 <= x <= bb.width_mm + 1e-6 and -1e-6 <= y <= bb.height_mm + 1e-6
                           for x, y in pts), (form, variant)
            lx, ly, lw, lh = bb.label_zone
            assert 0 <= lx and lx + lw <= bb.width_mm and 0 <= ly and ly + lh <= bb.height_mm, (form, variant)
            drawn.add((tuple((round(s.x, 3), round(s.y, 3)) for s in bb.silhouette if hasattr(s, "x")),
                       tuple(round(v, 3) for v in bb.label_zone)))
        assert len(drawn) == len(A.variants_of(form)), form            # each variant a drawing of its own
    tin = build_backbone(ContainerProfile(archetype="tin", variant="round", cap_style="screw", width_mm=42.0,
                                          height_mm=42.0))
    assert [type(s).__name__ for s in tin.silhouette].count("CubicTo") == 4               # a circle
    sachet = build_backbone(ContainerProfile(archetype="sachet", variant="three_side", cap_style="tear_notch",
                                             width_mm=125.0, height_mm=180.0))
    assert min(s.x for s in sachet.silhouette if hasattr(s, "x") and 0 < s.y < 20) < 125.0   # the notch


def test_the_slim_forms_are_drawn_closed_with_the_print_on_the_body_below_the_cap():
    """§BH70(1): a lipstick and a mascara were drawn as the TUBE — a squeeze tube with a crimped end — and a pencil
    could not be drawn at all. Each is now its own outline, closed and standing: its cap at the top, the label zone on
    the body BELOW the cap and inside the product's own width, and its outline not the tube's at the same size."""
    from apps.pipeline.targets.container import archetypes as A
    for form, (h, w) in {"lipstick": (80.0, 20.0), "mascara": (125.0, 16.0), "pencil": (150.0, 8.0)}.items():
        profile = ContainerProfile(archetype=form, variant=A.variants_of(form)[0][0],
                                   cap_style=A.closures_of(form)[0][0], height_mm=h, width_mm=w)
        bb = build_backbone(profile)
        assert bb.archetype == form
        lx, ly, lw, lh = bb.label_zone
        cap_bottom = max(seg.y for seg in bb.cap_region if hasattr(seg, "y"))
        assert ly >= cap_bottom, (form, ly, cap_bottom)                  # printed on the body, not the cap
        assert 0 <= lx and lx + lw <= w and ly + lh <= h, (form, bb.label_zone)
        tube = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="screw",
                                               height_mm=h, width_mm=w))
        assert bb.silhouette != tube.silhouette, form


def test_an_unknown_archetype_is_refused_by_name_and_never_drawn_as_a_bottle():
    """§BH65(e) INVERTED THIS TEST, and its old name is the reason: `test_unknown_archetype_falls_back_to_bottle`
    pinned `build_backbone`'s `.get(archetype, _bottle)` — the §BH61(a) defect in its last hiding place, a
    `.get()` default whose default is a FUNCTION, which §BH64(c)'s guard for archetype LITERALS could not see.
    "If removing a fallback makes something refuse that used to proceed, that is the rule working" (§BH61(a))."""
    import pytest
    from apps.pipeline.targets.container import archetypes as A
    with pytest.raises(A.ArchetypeUnresolved) as ctx:
        build_backbone(ContainerProfile(archetype="teapot"))
    assert "'teapot'" in str(ctx.value) and "build_backbone" in str(ctx.value)


def test_bh65e_a_field_nobody_set_is_recorded_as_none_not_as_a_bottles_value():
    """The dataclass is also the RECORD (`asdict` -> `container_profile`). A compact built without a variant, a
    closure or a size recorded "cylindrical", "screw", 110 x 40 and a 0.42 neck — a bottle's words on a hinged
    case. None is "not known"."""
    p = ContainerProfile(archetype="compact")
    assert (p.variant, p.cap_style, p.height_mm, p.width_mm, p.neck_ratio) == (None, None, None, None, None)


def test_bh65e_a_form_is_drawn_at_its_own_declared_size_and_the_record_is_left_alone():
    from apps.pipeline.targets.container import archetypes as A
    for form in A.ARCHETYPES:
        p = ContainerProfile(archetype=form)
        b = build_backbone(p)
        n = A.nominal_of(form)
        # [his answer after test day finding 3, 2026-09-30, (4): a round-width form is drawn as wide as its flat end]
        from apps.pipeline.targets.container.silhouettes import drawn_width_mm
        assert (b.width_mm, b.height_mm) == (drawn_width_mm(form, float(n["width_mm"])), float(n["height_mm"])), form
        assert p.width_mm is None and p.height_mm is None, form          # the record still says "not known"


def test_bh65e_no_bottle_draws_differently():
    """A bottle's declared nominal IS the 110 / 40 / 0.42 its defaults always were, so an unsized bottle draws
    exactly as it did — asserted on the emitted silhouette, not on the numbers that feed it."""
    unsized = build_backbone(ContainerProfile(archetype="bottle"))
    sized = build_backbone(ContainerProfile(archetype="bottle", height_mm=110.0, width_mm=40.0,
                                            neck_ratio=0.42))
    assert unsized.silhouette == sized.silhouette and unsized.cap_region == sized.cap_region


def test_bh71_a_form_drawn_in_elevation_is_drawn_from_its_traced_outline():
    """§BH71 PART 1: a bottle whose profile carries its concept's traced outline is drawn from it — its widest the
    confirmed width, its height the confirmed height, its closure above the line the picture shows, its label inside
    the body below it — and without one, by its template exactly as before."""
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.tests.test_vqr2b_concept_analysis import _bottle_png
    t = co.trace_elevation(_bottle_png())
    outline, source = co.outline_for(t, archetype="bottle", variant="cylindrical", image_sha256=t["source_sha256"])
    assert source["source"] == co.TRACED_FROM_CONCEPT and outline["kind"] == co.PROFILE, source
    kw = dict(archetype="bottle", variant="cylindrical", width_mm=40.0, height_mm=144.0, cap_style="screw")
    traced, template = build_backbone(ContainerProfile(**kw, outline=outline)), build_backbone(ContainerProfile(**kw))
    assert template == build_backbone(ContainerProfile(**kw))
    pts = [(s.x, s.y) for s in traced.silhouette if hasattr(s, "x")]
    ctl = [(v.x1, v.y1) for v in traced.silhouette if hasattr(v, "x1")] + \
        [(v.x2, v.y2) for v in traced.silhouette if hasattr(v, "x2")]
    assert traced.silhouette != template.silhouette
    assert all(-1e-6 <= x <= 40.0 + 1e-6 and -1e-6 <= y <= 144.0 + 1e-6 for x, y in pts + ctl)
    assert abs(max(x for x, _y in pts) - min(x for x, _y in pts) - 40.0) < 0.5
    assert abs(max(y for _x, y in pts) - min(y for _x, y in pts) - 144.0) < 1e-6
    cap_foot = max(s.y for s in traced.cap_region if hasattr(s, "y"))
    assert abs(cap_foot - outline["closure_share"] * 144.0) < 1e-6
    lx, ly, lw, lh = traced.label_zone
    assert ly > cap_foot and 0.0 < lx and lx + lw < 40.0 and ly + lh < 144.0
    assert all(type(s).__name__ in ("MoveTo", "LineTo", "CubicTo", "ClosePath") for s in traced.silhouette)


def test_bh71_no_drawn_curve_leaves_the_two_points_it_joins():
    """§BH71 PART 1, the owner's goal of 2026-09-28: \"read and traced to a clean vector\". A long side beside a short
    shoulder threw the shoulder's curve past its own points — a horn 6.45 mm tall at each shoulder of task 53's
    traced bottle, 3.6 mm on the synthetic bottle traced here, 7.4 mm under an aerosol's overcap. Every cubic drawn
    through kept points — a traced outline's, and every form's the same primitive draws — stays inside the span of
    the two points it joins; the traced outline is still smooth, not a polygon."""
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.targets.container import archetypes as A
    from apps.pipeline.targets.container.silhouettes import _curve_through
    from apps.pipeline.tests.test_vqr2b_concept_analysis import _bottle_png

    def leaves(path):
        worst, last = 0.0, None
        for s in path:
            if type(s).__name__ == "CubicTo":
                x0, y0 = last
                for k in range(1, 32):
                    t = k / 32.0
                    m = 1.0 - t
                    x = m ** 3 * x0 + 3 * m * m * t * s.x1 + 3 * m * t * t * s.x2 + t ** 3 * s.x
                    y = m ** 3 * y0 + 3 * m * m * t * s.y1 + 3 * m * t * t * s.y2 + t ** 3 * s.y
                    worst = max(worst, min(y0, s.y) - y, y - max(y0, s.y), min(x0, s.x) - x, x - max(x0, s.x))
            if hasattr(s, "x"):
                last = (s.x, s.y)
        return worst
    drawn = []
    for tilt in (0.0, 6.0):
        t = co.trace_elevation(_bottle_png(tilt=tilt))
        outline, _source = co.outline_for(t, archetype="bottle", variant="cylindrical",
                                          image_sha256=t["source_sha256"])
        drawn.append(("traced bottle, tilted %g" % tilt, build_backbone(ContainerProfile(
            archetype="bottle", variant="cylindrical", width_mm=40.0, height_mm=144.0, cap_style="screw",
            outline=outline))))
    for form in ("tin", "sachet", "oval_stick", "aerosol", "ampoule"):
        nominal, caps = A.nominal_of(form), [k for k, _ in A.closures_of(form)]
        for variant, _label in A.variants_of(form):
            drawn.append(("%s %s" % (form, variant), build_backbone(ContainerProfile(
                archetype=form, variant=variant, cap_style=caps[0], width_mm=float(nominal["width_mm"]),
                height_mm=float(nominal["height_mm"])))))
    for name, bb in drawn:
        assert leaves(bb.silhouette) < 1e-9 and leaves(bb.cap_region) < 1e-9, (
            name, leaves(bb.silhouette), leaves(bb.cap_region))
    # the side and its shoulder as task 53's trace kept them (its right half, mm): the curve joins the two and never
    # rises past the shoulder's top
    side = [(35.0, 140.28), (35.0, 24.35), (33.48, 21.32), (31.45, 19.79), (24.09, 18.27)]
    assert leaves([MoveTo(x=35.0, y=140.28)] + _curve_through(side, 35.0, 145.1)) < 1e-9
    last, handles = None, 0
    for s in drawn[0][1].silhouette:                                 # still curves, not a polygon
        if type(s).__name__ == "CubicTo" and ((s.x1, s.y1) != last or (s.x2, s.y2) != (s.x, s.y)):
            handles += 1
        if hasattr(s, "x"):
            last = (s.x, s.y)
    assert handles >= 4, handles


def test_bh71_a_learned_oval_lid_is_drawn_an_ellipse_in_its_own_plan():
    """§BH71 PART 3: a compact's or a tin's learned oval lid (variant "learned_oval") is drawn as the ellipse in the
    plan's own width and length — four cubics, its extents the plan's, its face the whole ellipse, its label inside;
    the round lid is drawn as it was."""
    from apps.pipeline.targets.container.silhouettes import OVAL_LID, compact_lid_face
    for form in ("compact", "tin"):
        bb = build_backbone(ContainerProfile(archetype=form, variant=OVAL_LID, width_mm=90.0, height_mm=60.0))
        for path in (bb.silhouette, bb.cap_region):
            assert [type(s).__name__ for s in path].count("CubicTo") == 4, (form, path)
            assert not any(type(s).__name__ == "LineTo" for s in path), form
            xs = [v for s in path if hasattr(s, "x") for v in (s.x,)]
            ys = [v for s in path if hasattr(s, "y") for v in (s.y,)]
            assert (min(xs), max(xs), min(ys), max(ys)) == (0.0, 90.0, 0.0, 60.0), (form, xs, ys)
        lx, ly, lw, lh = bb.label_zone
        for px in (lx, lx + lw):
            for py in (ly, ly + lh):
                assert ((px - 45.0) / 45.0) ** 2 + ((py - 30.0) / 30.0) ** 2 <= 1.0 + 1e-9, (form, bb.label_zone)
    assert compact_lid_face(90.0, 60.0, variant=OVAL_LID) == {
        "x_mm": 0.0, "y_mm": 0.0, "width_mm": 90.0, "height_mm": 60.0, "shape": "oval", "corner_mm": 30.0}
    round_ = build_backbone(ContainerProfile(archetype="compact", variant="round", width_mm=90.0, height_mm=90.0))
    assert [type(s).__name__ for s in round_.silhouette].count("CubicTo") == 4


def test_bh71_a_round_compact_is_drawn_round_and_a_square_one_square():
    """§BH71 PART 1, measured in his goal: \"the compact template ignores 'Round' and always draws a rounded
    rectangle.\" A round compact's plan and lid are circles across the plan's narrower side, its face the whole
    circle and saying so; a square one's corner is its traced share where the drawing carries one; the rounded
    rectangle is drawn as it always was."""
    from apps.pipeline.targets.container.silhouettes import compact_lid_face
    b = build_backbone(ContainerProfile(archetype="compact", variant="round", width_mm=110.0, height_mm=110.0))
    for path in (b.silhouette, b.cap_region):
        cubics = [s for s in path if s.op == "C"]
        xs = [p for s in cubics for p in (s.x, s.x1, s.x2)]
        assert len(cubics) == 4 and abs(max(xs) - min(xs) - 110.0) < 1e-9
    assert compact_lid_face(110.0, 110.0, variant="round") == {
        "x_mm": 0.0, "y_mm": 0.0, "width_mm": 110.0, "height_mm": 110.0, "shape": "round", "corner_mm": 55.0}
    lx, ly, lw, lh = b.label_zone
    assert (lx - 55.0) ** 2 + (ly - 55.0) ** 2 < 55.0 ** 2                  # the artwork zone inside the circle
    rect = build_backbone(ContainerProfile(archetype="compact", variant="rounded_rect", width_mm=110.0,
                                           height_mm=95.0))
    assert [s.op for s in rect.cap_region].count("C") == 4 and [s.op for s in rect.cap_region].count("L") == 4
    sq = build_backbone(ContainerProfile(archetype="compact", variant="square", width_mm=90.0, height_mm=90.0,
                                         outline={"kind": "square", "corner_share": 0.2}))
    assert abs(sq.silhouette[0].x - 18.0) < 1e-9                              # its corner the traced 20 %


def test_finding3_a_squeeze_tube_is_drawn_a_tube_not_a_bottle():
    """His test day finding 3 (2026-09-30, design 117): "it gave me a bottle of shampoo" — the tube template drew a
    straight body, a rounded shoulder and a screw cap's narrow cap on top. A squeeze tube is drawn cap up, its flip-top
    as wide as its round end (2/π of the crimp's width, all but its edge), its body widening in straight sides to a flat
    crimp band as wide as the drawing, the label on its body; a lip tube's slim nozzle form is left as it was."""
    import math

    from apps.pipeline.targets.container.silhouettes import TUBE_CAP_H, TUBE_CRIMP_H
    H = 180.0
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip",
                                         height_mm=H, width_mm=50.0))
    W = bb.width_mm       # [his answer after finding 3, (4): the drawing as wide as its flat end, π/2 of the round 50]
    def xs(segs, y):
        return sorted(round(s.x, 3) for s in segs if hasattr(s, "y") and abs(s.y - y) < 1e-6)
    cap_w = max(s.x for s in bb.cap_region if hasattr(s, "x")) - min(s.x for s in bb.cap_region if hasattr(s, "x"))
    assert abs(cap_w - 0.96 * 2 / math.pi * W) < 0.01, cap_w                  # the flip-top, as wide as its round end
    crimp = [0.0, round(W, 3)]
    assert xs(bb.silhouette, H) == crimp and xs(bb.silhouette, H - TUBE_CRIMP_H * H) == crimp       # the crimp
    top_w = xs(bb.silhouette, 0.0)
    assert top_w[1] - top_w[0] < 0.65 * W                                      # a tube's cap, not a bottle's body
    lx, ly, lw, lh = bb.label_zone
    assert ly > TUBE_CAP_H * H and 0 < lx and lx + lw < W and ly + lh < H - TUBE_CRIMP_H * H
    screw = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="screw",
                                            height_mm=H, width_mm=W))
    assert screw.silhouette != bb.silhouette                                    # its closure its own width
    lip = build_backbone(ContainerProfile(archetype="tube", variant="slim", cap_style="nozzle", height_mm=100.0,
                                          width_mm=25.0))
    assert xs(lip.silhouette, 26.0) == [0.0, round(lip.width_mm, 3)]        # its straight body, at its flat width


def test_finding3_a_tube_its_concept_stands_on_its_cap_is_drawn_on_its_cap():
    """His test day finding 3 (2026-09-30, design 117): his concept stands its squeeze tube on its flip-top, the trace
    read it so ("stood narrow end up"), and the drawing stood it on its crimp. The trace's reading reaches the outline
    and its words; a tube so traced is drawn on its cap — its cap at its foot, its crimp the widest at its top, its label
    clear of the cap with the logo above the name; unturned when the trace read it closure up; a bottle never turned;
    and a transparent tube's product fill is the body above its cap, never a sliver below it."""
    from dataclasses import replace

    from apps.ire.compose_container import compose_container_graph
    from apps.pipeline.services import concept_outline as co
    prof = [[i / 20.0, 0.62 if i < 3 else 0.68 + 0.32 * (i - 3) / 17.0] for i in range(21)]   # narrow end up
    trace = {"state": co.TRACED_FROM_CONCEPT, "view": "ELEVATION", "kind": co.PROFILE, "profile": prof,
             "closure_share": 0.15, "height_to_width": 2.3, "source_sha256": "ab" * 32, "stood_narrow_end_up": True}
    outline, source = co.outline_for(trace, archetype="tube", variant="standard", image_sha256="ab" * 32)
    assert outline["stands_on_closure"] is True and source["stands_on_closure"] is True
    assert co.words(source).endswith("standing on its closure as the concept stands it")
    W, H = 50.0, 180.0
    tube = ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=H, width_mm=W,
                            outline=outline)
    bb = build_backbone(tube)
    cap_ys = [s.y for s in bb.cap_region if hasattr(s, "y")]
    assert min(cap_ys) > 0.8 * H and max(cap_ys) <= H + 1e-6                          # its cap at its foot
    top = sorted(s.x for s in bb.silhouette if hasattr(s, "y") and abs(s.y) < 1e-6)
    assert top and top[-1] - top[0] > 0.95 * W                                        # its crimp, widest, at its top
    lx, ly, lw, lh = bb.label_zone
    assert ly + lh <= min(cap_ys) and bb.anchors["logo"][1] < bb.anchors["product_name"][1]
    upright = build_backbone(replace(tube, outline=dict(outline, stands_on_closure=False)))
    assert max(s.y for s in upright.cap_region if hasattr(s, "y")) <= 0.16 * H         # as the trace stood it
    bottle = build_backbone(ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="screw",
                                             height_mm=110.0, width_mm=40.0, outline=outline))
    assert max(s.y for s in bottle.cap_region if hasattr(s, "y")) <= 0.16 * 110.0       # a bottle: never turned
    doc = compose_container_graph(bb, product_name="Rose", sku="X", transparency={"product_color": "#F2C4CE"})
    nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
    fill, cap = nodes["product-peach-rose-fill"], nodes["cap"]
    cap_top = min(s.y for s in cap.segments if hasattr(s, "y"))
    assert fill.h > 0.5 * (cap_top - fill.y) > 1.0 and fill.y + fill.h <= cap_top + 1e-6    # the body above its cap


def test_his_answer_a_round_50_mm_tube_is_drawn_78_5_mm_at_its_flat_end_and_50_at_its_round():
    """His answer after test day finding 3 (2026-09-30), (4) "round": his 50 mm is the tube's round diameter. The tube
    is drawn as wide as its flat end, π/2 × 50 = 78.54 mm, its round end — where its flip-top sits — 50 mm; its front
    and back print surfaces are that flat face, its wrap the circumference; a bottle is drawn and surfaced as before."""
    import math

    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets.container.silhouettes import TUBE_ROUND_END, drawn_width_mm
    bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                         width_mm=50.0))
    assert abs(bb.width_mm - 50.0 * math.pi / 2.0) < 1e-6 and abs(TUBE_ROUND_END * bb.width_mm - 50.0) < 1e-6
    assert drawn_width_mm("bottle", 40.0) == 40.0
    tube = cc.build_inferred_profile("tube", "standard", {"body_width_mm": 50.0, "body_height_mm": 180.0,
                                                           "body_depth_mm": 50.0})
    faces = cc.surface_geometry(tube)
    assert faces["BODY_FRONT"]["w"] == faces["BODY_BACK"]["w"] == round(50.0 * math.pi / 2.0, 2)
    assert faces["BODY_WRAP"]["w"] == round(math.pi * 50.0, 2)
    bottle = cc.surface_geometry(cc.build_inferred_profile("bottle", "cylindrical", {"body_width_mm": 40.0,
                                                                                     "body_height_mm": 110.0}))
    assert bottle["BODY_FRONT"]["w"] == 40.0
    assert build_backbone(ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="screw",
                                           height_mm=110.0, width_mm=40.0)).width_mm == 40.0


def test_label_zone_override_is_respected():
    zone = (5.0, 40.0, 20.0, 30.0)
    b = build_backbone(ContainerProfile(archetype="bottle", label_zone=zone))
    assert b.label_zone == zone


def test_cap_style_changes_cap_proportions():
    screw = build_backbone(ContainerProfile(archetype="bottle", cap_style="screw"))
    pump = build_backbone(ContainerProfile(archetype="bottle", cap_style="pump"))
    # pump caps are taller than screw caps — the cap region reaches lower
    screw_bottom = max(getattr(s, "y", 0) for s in screw.cap_region)
    pump_bottom = max(getattr(s, "y", 0) for s in pump.cap_region)
    assert pump_bottom > screw_bottom


def test_backbone_segments_drop_into_a_graph_path():
    # the outline is graph Segments → wraps directly in a Path node, proving
    # the backbone speaks the shared Design Graph vocabulary (no conversion).
    b = build_backbone(ContainerProfile(archetype="jar"))
    node = Path(name="silhouette", segments=b.silhouette,
                fill=SolidFill(color=Color.from_hex("#EAD7D2")))
    assert node.segments[0].op == "M"


# ---- [His goal after the pitch page, 2026-10-15, A (3): "SHAPES AND PROPORTIONS come from the concept: caps, droppers,
# ---- lids, collars and the product's outline and aspect ratio (not crude templates: 128's grey-block dropper, 130's
# ---- shield lid, 131 drawn landscape when the concept is portrait with a cream border)". Each read on a profile no
# ---- design has drawn: the fault is the engine's, never one design's.]

def _pts(segments):
    return [(s.x, s.y) for s in segments if hasattr(s, "x")]


def _profile(rows):
    """A traced profile from ``(height share, half-width share)`` bands — each band sampled every 0.01."""
    out = []
    for (t0, t1, s0, s1) in rows:
        n = max(1, int(round((t1 - t0) / 0.01)))
        for k in range(n):
            f = k / n
            out.append([round(t0 + (t1 - t0) * f, 4), round(s0 + (s1 - s0) * f, 4)])
    out.append([1.0, rows[-1][3]])
    return out


def test_pitch_a3_a_dropper_is_split_into_its_bulb_and_its_collar():
    """A dropper whose bulb is narrower than its collar (128's chrome pair) is drawn as two parts — its bulb down to
    where the collar's own width begins, its collar its own region below — never a sliver of bulb on a block."""
    prof = _profile([(0.0, 0.03, 0.05, 0.20), (0.03, 0.15, 0.20, 0.20), (0.15, 0.17, 0.20, 0.50),
                     (0.17, 0.30, 0.50, 0.50), (0.30, 0.36, 0.50, 1.0), (0.36, 1.0, 1.0, 1.0)])
    outline = {"kind": "profile", "profile": prof, "closure_share": 0.30, "height_to_width": 2.5}
    bb = build_backbone(ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="dropper", width_mm=40.0,
                                         height_mm=100.0, outline=outline))
    assert bb.bulb_region is not None and bb.collar_region is not None
    bulb_foot = max(y for _x, y in _pts(bb.bulb_region))
    collar_ys = [y for _x, y in _pts(bb.collar_region)]
    assert 14.0 <= bulb_foot <= 16.5, bulb_foot                       # the bulb ends where the collar begins
    assert abs(min(collar_ys) - bulb_foot) < 1e-6 and abs(max(collar_ys) - 30.0) < 1e-6
    bulb_w = max(x for x, _y in _pts(bb.bulb_region)) - min(x for x, _y in _pts(bb.bulb_region))
    collar_w = max(x for x, _y in _pts(bb.collar_region)) - min(x for x, _y in _pts(bb.collar_region))
    assert bulb_w < 0.5 * collar_w


def test_pitch_a3_a_round_bulb_on_a_neck_is_split_at_its_neck():
    from apps.pipeline.targets.container.silhouettes import closure_split
    prof = _profile([(0.0, 0.06, 0.10, 0.30), (0.06, 0.12, 0.30, 0.14), (0.12, 0.14, 0.14, 0.50),
                     (0.14, 0.28, 0.50, 0.50), (0.28, 1.0, 1.0, 1.0)])
    split = closure_split(prof, 0.28)
    assert split is not None and 0.11 <= split <= 0.135, split


def test_pitch_a3_a_lid_keeps_its_straight_sides_and_its_flat_top():
    """A lid as wide as its body (130's gold lid) seen a little from above: its top face is the photo's ellipse and the
    body's shoulder flares out under it. Drawn, its top is flat across its full width and it ends where its own straight
    side ends — never a shield narrowing to its top and flaring into the shoulder."""
    prof = _profile([(0.0, 0.04, 0.25, 0.83), (0.04, 0.17, 0.85, 0.85), (0.17, 0.23, 0.86, 0.97),
                     (0.23, 0.95, 1.0, 1.0), (0.95, 1.0, 1.0, 0.6)])
    outline = {"kind": "profile", "profile": prof, "closure_share": 0.235, "height_to_width": 1.2}
    bb = build_backbone(ContainerProfile(archetype="jar", variant="standard", cap_style="lid", width_mm=60.0,
                                         height_mm=72.0, outline=outline))
    cap = _pts(bb.cap_region)
    foot = max(y for _x, y in cap)
    assert foot <= 0.18 * 72.0, foot                                  # not 0.235 down: the shoulder is the body's
    top_row = [x for x, y in cap if y < 1e-6]
    assert max(top_row) - min(top_row) > 0.84 * 60.0                  # its top as wide as its side
    side_xs = [x for x, y in cap if 0.0 <= y <= foot]
    assert max(side_xs) - min(side_xs) <= 0.86 * 60.0 + 1e-6           # no flare


def test_pitch_a3_a_cap_on_a_neck_is_read_as_traced():
    from apps.pipeline.targets.container.silhouettes import closure_shaped
    prof = _profile([(0.0, 0.1, 0.2, 0.3), (0.1, 0.2, 0.3, 0.3), (0.2, 0.3, 0.3, 0.6), (0.3, 1.0, 1.0, 1.0)])
    shaped, c, said = closure_shaped(prof, 0.25, "screw")
    assert c == 0.25 and said == [] and [list(r) for r in shaped] == prof


def test_pitch_a3_a_traced_lid_is_drawn_whole_with_its_concepts_rim():
    """A compact whose lid was traced from its concept is the lid its concept shows: no hinge band in the body's colour
    across its back (131's grey strip), its square corner kept square, and the rim its concept shows round the art
    drawn as a rim at its measured widths."""
    border = {"top": 0.01, "right": 0.02, "bottom": 0.03, "left": 0.02, "hex": "#E6D5C5"}
    bb = build_backbone(ContainerProfile(archetype="compact", variant="rounded_rect", width_mm=110.0, height_mm=124.0,
                                         outline={"kind": "rounded_rect", "corner_share": 0.0, "border": border}))
    cap = _pts(bb.cap_region)
    assert min(y for _x, y in cap) == 0.0 and max(y for _x, y in cap) == 124.0
    assert (0.0, 0.0) in cap                                          # a traced 0.0 corner is square
    assert bb.border_region is not None
    inner = _pts(bb.border_region)[len(_pts(bb.cap_region)):]
    assert abs(min(x for x, _y in inner) - 2.2) < 1e-6 and abs(min(y for _x, y in inner) - 1.24) < 1e-6
    assert abs(max(y for _x, y in inner) - (124.0 - 3.72)) < 1e-6
    plain = build_backbone(ContainerProfile(archetype="compact", variant="rounded_rect", width_mm=110.0,
                                            height_mm=124.0, outline={"kind": "rounded_rect", "corner_share": 0.1}))
    assert plain.border_region is None                                # no rim in the concept: none drawn
    template = build_backbone(ContainerProfile(archetype="compact", variant="rounded_rect", width_mm=110.0,
                                               height_mm=124.0))
    assert min(y for _x, y in _pts(template.cap_region)) > 0.0         # the template keeps its hinge band


def _lid_with_rim(rim_px, w=300, h=340):
    import cv2
    import numpy as np
    img = np.zeros((h, w, 3), np.uint8)
    for y in range(h):
        img[y, :] = (200 - y // 3, 120 + y // 4, 60 + y // 2)          # an art's sky, graded down the lid
    if rim_px:
        img[:rim_px, :] = img[-rim_px:, :] = img[:, :rim_px] = img[:, -rim_px:] = (197, 213, 230)
    return cv2.imencode(".png", img)[1].tobytes()


def test_pitch_a3_a_lids_rim_is_read_round_its_art():
    from apps.pipeline.services import concept_outline as co
    rim = co.lid_border(_lid_with_rim(6))
    assert rim is not None and rim["hex"].upper() in ("#E6D5C5", "#E6D5C4", "#E5D5C5", "#E6D6C5")
    assert abs(rim["top"] - 6 / 340) < 1e-4 and abs(rim["left"] - 6 / 300) < 1e-4
    assert co.lid_border(_lid_with_rim(0)) is None                    # its art runs to its edge: no rim


def test_pitch_a3_an_oval_lid_keeps_its_concepts_aspect():
    from apps.pipeline.services import concept_outline as co
    trace = {"state": co.TRACED_FROM_CONCEPT, "view": "PLAN", "kind": co.OVAL, "aspect": 0.8,
             "rim": {"long_axis_angle_deg": 90.0}}
    assert co.proposal(trace, "compact", width_mm=80.0, traced_variants={co.OVAL: "learned_oval"}) == {
        "variant": "learned_oval", "height_mm": 100.0}                # portrait: its long axis down the frame
    wide = dict(trace, rim={"long_axis_angle_deg": 0.0})
    assert co.proposal(wide, "compact", width_mm=80.0, traced_variants={co.OVAL: "learned_oval"})["height_mm"] == 64.0


def test_pitch_a3_a_domed_cap_as_wide_as_its_case_keeps_its_dome():
    """Only a lid's top is squared (its form names its closure a lid): a lipstick's cap as wide as its case may be truly
    domed, and its traced dome stands."""
    from apps.pipeline.targets.container.silhouettes import closure_shaped
    prof = _profile([(0.0, 0.05, 0.4, 0.95), (0.05, 0.5, 1.0, 1.0), (0.5, 1.0, 1.0, 1.0)])
    shaped, _c, said = closure_shaped(prof, 0.5, None, "lipstick")
    assert [list(r) for r in shaped] == prof and said == []
    lid, _c2, said2 = closure_shaped(prof, 0.5, None, "jar")
    assert lid[0][1] == 1.0 and said2                                  # the same outline on a jar: its lid's flat top


# [His review of 127, 130, 131 and 132, 2026-10-15, C (3): "parts meet as the concept shows ... the product outline
# matches the concept (130's jar is a shield shape)"; D (11): the dropper bulb as the concept shows; the executor's own
# look at 128: its bulb a castle, its collar with its shoulder, its foot bevelled]

def _bottom_pts(segs, H, within):
    return [(x, y) for x, y in _pts(segs) if y >= H - within]


def test_his_review_c3_a_base_seen_from_above_is_drawn_flat_with_its_corners_rounded():
    """The photo shows a jar's foot (130's) as the ellipse a base makes seen a little from above: its rows narrow to a
    point over a shallow depth. Drawn, its foot is flat across most of its width, its corners rounded — never the V of
    the photo's ellipse (the "shield")."""
    prof = _profile([(0.0, 0.03, 0.3, 0.85), (0.03, 0.2, 0.85, 0.85), (0.2, 0.25, 0.85, 1.0), (0.25, 0.92, 1.0, 1.0),
                     (0.92, 1.0, 1.0, 0.06)])
    outline = {"kind": "profile", "profile": prof, "closure_share": 0.2, "height_to_width": 1.2}
    bb = build_backbone(ContainerProfile(archetype="jar", variant="standard", cap_style="lid", width_mm=60.0,
                                         height_mm=72.0, outline=outline))
    foot = [x for x, y in _pts(bb.silhouette) if y >= 72.0 - 1e-6]
    assert foot and max(foot) - min(foot) > 0.6 * 60.0, foot            # flat across, not a point
    near = [x for x, y in _pts(bb.silhouette) if 72.0 - 4.0 <= y < 72.0 - 1e-6 and x > 30.0]
    assert near and max(near) < 60.0 - 0.3                               # its corner rounded, never square


def test_his_review_d11_a_dome_stays_a_dome_and_its_steps_are_smoothed():
    """A bulb's dome (128's): 96 rows read its round as steps (0.03, 0.12, 0.128, 0.208, 0.224, 0.232). Drawn, it is one
    smooth quarter round each side — every arc point kept, rising steadily, its apex on the axis — never a castle."""
    from apps.pipeline.targets.container.silhouettes import rounded_ends
    steps = [(0.0, 0.032), (0.009, 0.12), (0.02, 0.128), (0.03, 0.208), (0.041, 0.224), (0.051, 0.232),
             (0.062, 0.232), (0.072, 0.232), (0.083, 0.232), (0.1, 0.232), (0.2, 0.232), (0.3, 1.0), (1.0, 1.0)]
    prof, keep = rounded_ends(steps, 2.648)
    arc = [(t, s) for t, s in prof if t in keep and t <= 0.06]
    assert len(arc) >= 8 and arc[0][1] < 0.02                           # its apex on the axis: a dome
    widths = [s for _t, s in arc]
    assert widths == sorted(widths)                                     # widening steadily: no step back, no castle
    lid, keep2 = rounded_ends([(0.0, 0.85), (0.05, 0.85), (0.5, 1.0), (1.0, 1.0)], 1.2)
    assert lid[0] == (0.0, 0.85) and not [t for t in keep2 if t < 0.1]  # a flat top already square is kept


def test_his_review_d11_a_droppers_collar_ends_where_its_shoulder_begins():
    """128's closure line fell into its shoulder: the closure's lowest rows widen 0.512 → 0.66, so its collar was read
    0.66 wide, no bulb could be split from it, and a two-row tip was drawn as its bulb. The collar ends where its own
    side stops widening; the bulb is its whole narrow part above the collar."""
    rows = ([(round(0.01 * k, 4), 0.03 + 0.04 * k) for k in range(5)] + [(round(0.05 + 0.01 * k, 4), 0.23)
                                                                          for k in range(11)]
            + [(0.16, 0.40)] + [(round(0.17 + 0.01 * k, 4), 0.512) for k in range(14)]
            + [(0.31, 0.528), (0.32, 0.544), (0.33, 0.664), (0.34, 0.784), (0.35, 0.90), (0.36, 0.98)]
            + [(round(0.37 + 0.01 * k, 4), 1.0) for k in range(63)] + [(1.0, 1.0)])
    outline = {"kind": "profile", "profile": rows, "closure_share": 0.3459, "height_to_width": 2.648}
    bb = build_backbone(ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="dropper", width_mm=40.0,
                                         height_mm=105.9, outline=outline))
    assert bb.bulb_region is not None and bb.collar_region is not None
    bulb_foot = max(y for _x, y in _pts(bb.bulb_region)) / 105.9
    collar = _pts(bb.collar_region)
    assert 0.14 <= bulb_foot <= 0.17, bulb_foot                          # the whole stem is the bulb's, not two rows
    assert max(y for _x, y in collar) / 105.9 < 0.32                     # the collar ends above the shoulder
    assert max(x for x, _y in collar) - min(x for x, _y in collar) < 0.56 * 40.0   # its own width, no skirt


def test_his_review_d11_a_cap_on_its_collar_is_drawn_as_both():
    """A closure its concept's map reads as a cap on its collar (the lead's look at 134's flacon: its gold collar drawn in
    its plum cap's colour): the cap its region down to the collar, the collar its own region below it."""
    prof = _profile([(0.0, 0.15, 0.5, 0.5), (0.15, 0.26, 0.35, 0.35), (0.26, 0.3, 0.35, 1.0), (0.3, 1.0, 1.0, 1.0)])
    outline = {"kind": "profile", "profile": prof, "closure_share": 0.26, "height_to_width": 2.0, "collar_split": 0.15}
    bb = build_backbone(ContainerProfile(archetype="bottle", variant="flacon", cap_style="crimp_spray", width_mm=40.0,
                                         height_mm=110.0, outline=outline))
    assert bb.collar_region is not None and bb.bulb_region is None
    assert abs(max(y for _x, y in _pts(bb.cap_region)) - 0.15 * 110.0) < 1e-6
    assert abs(min(y for _x, y in _pts(bb.collar_region)) - 0.15 * 110.0) < 1e-6
    plain = build_backbone(ContainerProfile(archetype="bottle", variant="flacon", cap_style="crimp_spray", width_mm=40.0,
                                            height_mm=110.0, outline=dict(outline, collar_split=None)))
    assert plain.collar_region is None                                  # no collar read: one closure, as before


def _shadowed_flacon(shadow: bool):
    import cv2
    import numpy as np
    img = np.full((768, 512, 3), (243, 246, 248), np.uint8)           # a light studio ground
    if shadow:
        img[150:720, 330:436] = (205, 209, 212)                        # its shadow, cast to the right
    img[100:200, 196:316] = (70, 55, 60)                               # a plum cap
    img[200:260, 216:296] = (60, 120, 170)                             # a gold collar
    img[260:700, 136:376] = (70, 55, 60)                               # its body
    return cv2.imencode(".png", img)[1].tobytes()


def test_his_review_d11_a_shadow_cast_on_a_light_ground_is_never_the_product():
    """134's shadow ran beside its body and moved its axis: every half-width was read about the wrong middle — its cap a
    third too narrow and stepped. Traced, a product casting a shadow on a light ground reads as the same product with
    none: its sides agree and its cap is as wide as its own pixels."""
    from apps.pipeline.services import concept_outline as co
    clean, shaded = co.trace_elevation(_shadowed_flacon(False)), co.trace_elevation(_shadowed_flacon(True))
    assert clean["state"] == shaded["state"] == co.TRACED_FROM_CONCEPT, (clean.get("detail"), shaded.get("detail"))
    assert shaded["sides_disagree"] <= 0.05
    cap = lambda tr: max(s for t, s in tr["profile"] if 0.05 <= t <= 0.15)
    assert abs(cap(shaded) - cap(clean)) < 0.05 and abs(cap(clean) - 0.5) < 0.05, (cap(clean), cap(shaded))


def test_b10_a_tubes_proposed_height_is_its_concepts_proportion_of_the_width_it_is_drawn_at():
    """[His goal after the pitch page, B (10)] the lotion tube, 139: proposed 35 x 63.4 mm — 35 x the picture's 1.81 —
    and drawn at its flat end, 55 mm wide: squat, where its concept is tall. Its height is the proportion of the width
    it is drawn at; a form drawn at its confirmed width is as before."""
    import math
    from apps.pipeline.services import concept_outline as co
    trace = {"state": co.TRACED_FROM_CONCEPT, "view": "ELEVATION", "kind": co.PROFILE, "height_to_width": 1.8106}
    assert co.proposal(trace, "tube", width_mm=35.0) == {"height_mm": round(35.0 * math.pi / 2.0 * 1.8106, 1)}
    assert co.proposal(trace, "bottle", width_mm=35.0) == {"height_mm": 63.4}
    # a tall concept's tube never proposed past the sizes its shape step accepts (40-200 mm)
    assert co.proposal(dict(trace, height_to_width=4.0), "tube", width_mm=35.0) == {"height_mm": 200.0}


def test_s2_138_an_end_that_reaches_its_side_in_one_row_is_square():
    """[His last goal before the pitch, 2026-10-16, Step 2] 138's square black cap — its top row 0.34 wide, the next
    0.586, its side — was drawn with a flared, rounded top: the photo's thin top ellipse read as a round. An end that
    reaches its side in one row is kept square; one that takes several rows is still rounded."""
    from apps.pipeline.targets.container.silhouettes import rounded_ends
    square = [(0.0, 0.34)] + [(round(0.009 + 0.0105 * k, 4), 0.586) for k in range(20)] + [(0.4, 1.0), (1.0, 1.0)]
    prof, keep = rounded_ends(square, 1.963)
    assert prof[:2] == [(0.0, 0.586), (0.009, 0.586)] and [t for t in keep if t < 0.1] == [0.0]   # flat, square
