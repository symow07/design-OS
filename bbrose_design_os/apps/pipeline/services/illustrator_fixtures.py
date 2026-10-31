"""Minimal Illustrator-compatibility fixtures (GATE-A-CORR-2 §4).

R1 opened in Illustrator showing three structure objects and none of the 37
artwork objects. Two explanations fit that observation equally well and nothing
in this environment can separate them, because the three survivors are BOTH the
first three layers AND the only geometry outside the body's bounding box:

  H1  the body ends up stacked above the artwork, which is therefore present
      but hidden
  H2  Illustrator stopped after the third %AI5_BeginLayer block, so the
      artwork is not in the document at all

These fixtures exist to settle that in Illustrator rather than by argument, and
to prove the R2 serializer independently of the artwork. Fixture A is built to
DISCRIMINATE: its rectangles overlap in a staircase, so one glance says both how
many survived and which way they stack. Non-overlapping swatches would answer
only the first question and leave the confound alive.

Every fixture is emitted by the same R2 serializer that writes the real source,
so passing here is evidence about that serializer and not about a toy.
"""
from . import ai8_color as A

# deliberately unlike the accepted palette, so a fixture can never be mistaken
# for approved artwork
STAIRCASE = [
    ("01_STRUCTURE_BODY", (0xE6, 0x19, 0x4B)),
    ("02_STRUCTURE_COLLAR", (0xF5, 0x82, 0x31)),
    ("03_STRUCTURE_CLOSURE", (0xFF, 0xE1, 0x19)),
    ("04_APPROVED_BBROSE_LOGO", (0x3C, 0xB4, 0x4B)),
    ("05_DIVIDER", (0x43, 0x63, 0xD8)),
    ("06_ROSE_LETTERING", (0x91, 0x1E, 0xB4)),
    ("07_DAMASCENA_LETTERING", (0x46, 0xF0, 0xF0)),
    ("08_SUPPORTING_COPY", (0x00, 0x00, 0x00)),
]


def _doc(width, height, layers):
    doc = A.Doc()
    doc.bbox = [0.0, 0.0, float(width), float(height)]
    doc.hires_bbox = [0.0, 0.0, float(width), float(height)]
    doc.layers = layers
    doc.trailer = ["%%PageTrailer", "%%Trailer", "%%EOF"]
    return doc


def _rect(layer, name, x0, y0, x1, y1, rgb, paint="f"):
    o = A.Obj(layer, name, rgb=rgb)
    o.color_op, o.paint_op = "Xa", paint
    o.geometry = [f"{x0:.4f} {y0:.4f} m", f"{x1:.4f} {y0:.4f} L",
                  f"{x1:.4f} {y1:.4f} L", f"{x0:.4f} {y1:.4f} L", "h"]
    return o


def fixture_a_layer_sequence():
    """Eight overlapping rectangles in a known staircase.

    Painted 01 first, 08 last. Correct back-to-front order therefore puts
    08_SUPPORTING_COPY (black) fully on top and 01_STRUCTURE_BODY (red)
    furthest back — the same relationship the real artwork needs. If the order
    inverts, red covers the rest; if boundaries are dropped, later colours are
    missing entirely. The two failures look nothing alike.
    """
    layers, step, size = [], 24.0, 120.0
    for i, (name, rgb) in enumerate(STAIRCASE):
        x = 10.0 + i * step
        y = 10.0 + i * step
        layers.append((None, name,
                       [_rect(name, f"SWATCH_{name}", x, y,
                              x + size, y + size, rgb)]))
    return _doc(10 + 7 * step + size + 10, 10 + 7 * step + size + 10, layers)


def fixture_b_compound_path():
    """Outer contour with two counters, plus a registered-symbol-sized mark.

    The counters are what a wrong fill rule closes, and the small mark is where
    a rule that survives at 60 pt can still fail at 4 pt.
    """
    ink = A.FLAT_COLORS["ARTWORK"]
    o = A.Obj("B_COMPOUND", "OUTER_WITH_TWO_COUNTERS", rgb=ink)
    o.color_op, o.paint_op = "Xa", "f"
    o.geometry = [
        "20.0000 20.0000 m", "100.0000 20.0000 L",
        "100.0000 140.0000 L", "20.0000 140.0000 L", "h",
        "40.0000 40.0000 m", "80.0000 40.0000 L",
        "80.0000 70.0000 L", "40.0000 70.0000 L", "h",
        "40.0000 90.0000 m", "80.0000 90.0000 L",
        "80.0000 120.0000 L", "40.0000 120.0000 L", "h",
    ]
    small = A.Obj("B_COMPOUND", "REGISTERED_SYMBOL_SIZED", rgb=ink)
    small.color_op, small.paint_op = "Xa", "f"
    small.geometry = [
        "120.0000 20.0000 m", "124.4000 20.0000 L",
        "124.4000 24.4000 L", "120.0000 24.4000 L", "h",
        "121.2000 21.2000 m", "123.2000 21.2000 L",
        "123.2000 23.2000 L", "121.2000 23.2000 L", "h",
    ]
    return _doc(150, 160, [(None, "B_COMPOUND", [o, small])])


def fixture_c_artwork_paint(source_doc):
    """Real accepted artwork, lifted unchanged, painted on its own.

    A logo component, the stroked divider, a Didone glyph and a sans glyph. If
    R2 renders these four in Illustrator, the artwork paths themselves are not
    the problem.
    """
    want = [("04_APPROVED_BBROSE_LOGO", "APPROVED_BBROSE_006"),
            ("05_DIVIDER", "DIVIDER_RULE"),
            ("06_ROSE_LETTERING", "ROSE_00_R"),
            ("08_SUPPORTING_COPY", "SUPPORTING_06_R")]
    by_key = {(o.layer, o.name): o for o in source_doc.objects()}
    objs = []
    for key in want:
        src = by_key[key]
        o = A.Obj("C_ARTWORK", f"{key[0]}__{key[1]}",
                  rgb=A.FLAT_COLORS["ARTWORK"])
        o.color_op, o.paint_op = src.color_op, src.paint_op
        o.geometry = list(src.geometry)          # copied, never regenerated
        objs.append(o)
    w, h = source_doc.size
    return _doc(w, h, [(None, "C_ARTWORK", objs)])


def fixture_d_graphics_state():
    """Three objects that would visibly disagree if state leaked.

    Object 1 is stroked and wide; object 2 is filled; object 3 is stroked and
    thin. If line width leaked, object 3 would be fat. If colour leaked, the
    colours would repeat. If a clip survived, the later objects would be cut.
    """
    a = _rect("D_STATE", "WIDE_STROKE", 10, 10, 90, 90,
              (0xE6, 0x19, 0x4B), paint="S")
    a.width = 8.0
    b = _rect("D_STATE", "PLAIN_FILL", 50, 50, 130, 130, (0x3C, 0xB4, 0x4B))
    c = _rect("D_STATE", "THIN_STROKE", 100, 10, 180, 90,
              (0x43, 0x63, 0xD8), paint="S")
    c.width = 0.5
    return _doc(200, 150, [(None, "D_STATE", [a, b, c])])


FIXTURES = {
    "A_layer_sequence": fixture_a_layer_sequence,
    "B_compound_path": fixture_b_compound_path,
    "D_graphics_state": fixture_d_graphics_state,
}


def build_all(source_doc):
    """Every fixture as (name, doc). C needs the accepted source's geometry."""
    out = [(n, f()) for n, f in FIXTURES.items()]
    out.insert(2, ("C_artwork_paint", fixture_c_artwork_paint(source_doc)))
    return out


def evaluate(name, doc, text):
    """What the fixture proves, checked from its own emitted bytes."""
    audit = A.audit_graphics_state(text)
    back = A.parse_eps_r2(text)
    src_objs = list(doc.objects())
    back_objs = list(back.objects())
    executed = A.ps_resolve(text)
    rec = {
        "fixture": name,
        "objects_expected": len(src_objs),
        "objects_in_emitted_bytes": len(back_objs),
        "object_names": [o.name for o in back_objs],
        "groups": [n for _, n, _ in back.layers],
        "graphics_state": audit,
        "geometry_round_trips":
            all(a.geometry == b.geometry
                for a, b in zip(src_objs, back_objs)),
        "colors_round_trip":
            all(b.emitted_rgb == a.expected_rgb
                for a, b in zip(src_objs, back_objs)),
        "executed_paints": len(executed),
        "executed_colors_correct":
            all(c == o.expected_rgb
                for (c, _, _), o in zip(executed, src_objs)),
        "uses_ai_operator_vocabulary": False,
        "pending_human_illustrator_confirmation": True,
    }
    if name == "A_layer_sequence":
        rec["discriminates_stacking_direction"] = True
        rec["paint_order_first_to_last"] = [o.name for o in src_objs]
        rec["expected_topmost"] = src_objs[-1].name
        rec["expected_bottommost"] = src_objs[0].name
        rec["reads_as"] = {
            "all eight visible, black on top":
                "stacking correct - neither H1 nor H2",
            "all eight visible, red on top":
                "stacking inverted - H1",
            "fewer than eight visible":
                "later content dropped - H2",
        }
    rec["passed"] = bool(
        audit["passed"] and rec["geometry_round_trips"]
        and rec["colors_round_trip"] and rec["executed_colors_correct"]
        and len(back_objs) == len(src_objs))
    return rec
