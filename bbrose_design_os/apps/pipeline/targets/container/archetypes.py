"""THE ONE DECLARATION of container archetypes and their vocabulary — §BH61(c).

The owner found the third per-archetype registry by using the product: he chose a palette and the shape step
offered him a Bottle, pre-selected. "Had I clicked through, my palette would have been rebuilt as a bottle and
nothing would have said so." §BH61(c): "Find every place that enumerates archetypes or anything keyed by
them … and make them read from one declaration. Then a test asserts that every archetype in that declaration
has every dependent vocabulary — so the next archetype fails at the gate with a list of what it lacks,
instead of in front of me."

This module is that declaration. Nothing here is new vocabulary: every value is lifted from the registry that
already held it (`silhouettes`, `container_contract`, `targets.ui`), which §BH61(e) requires — "no vocabulary
beyond what an archetype needs to be answerable".

WHAT A DEPENDENT VOCABULARY IS. For each archetype the rest of the system needs five things, and a form that
lacks any one of them cannot be answered by a person or drawn by the engine:

    variants     the shapes the form comes in            (the editor offers them)
    closures     how it closes                           (the editor offers them)
    surfaces     the faces artwork can be placed on      (container_contract)
    proportions  the measurements that APPLY to it       (§BH61(b): no neck on a hinged case)
    drawn        whether silhouettes can draw it

`test_archetype_conformance` asserts all five for every key below, so a sixth archetype fails at the gate with
a list of what it lacks.

NOTHING FALLS BACK TO BOTTLE — §BH61(a). `resolve()` raises `ArchetypeUnresolved` naming the value that was
missing and where it was looked for. There is no default in this module and no caller may supply one.
"""
from __future__ import annotations

#: §BH61(a): the refusal code a caller surfaces when no archetype could be resolved.
ARCHETYPE_UNRESOLVED = "CONTAINER_ARCHETYPE_UNRESOLVED"

#: §BH61(b)(c): a bottle-only path states its scope with this and refuses anything else BY NAME AT ENTRY.
ARCHETYPE_OUT_OF_SCOPE = "CONTAINER_ARCHETYPE_OUT_OF_SCOPE"


class ArchetypeUnresolved(ValueError):
    """No archetype could be resolved, and none is invented (§BH61(a)).

    The message names the value that was missing and every place it was looked for, because the owner's rule
    is that "the stop says which value was missing and where it was looked for".
    """

    def __init__(self, looked_in, *, value=None):
        self.looked_in = tuple(looked_in)
        self.value = value
        seen = "none" if value in (None, "") else repr(value)
        super().__init__(
            f"{ARCHETYPE_UNRESOLVED}: no container archetype could be resolved "
            f"(value seen: {seen}); looked in: {', '.join(self.looked_in) or 'nothing'}. "
            f"Known archetypes: {', '.join(ARCHETYPES)}. Nothing falls back to bottle (§BH61(a)).")


class ArchetypeOutOfScope(ValueError):
    """A path that serves ONE form was handed another, and refuses at the door (§BH61(b)(c)).

    The owner: "a bottle-only path may declare itself bottle-only — that is honest … What it may never do is
    accept a form it does not serve and rewrite it into one it does."
    """

    def __init__(self, where, *, given, serves):
        self.given, self.serves = given, tuple(serves)
        super().__init__(
            f"{ARCHETYPE_OUT_OF_SCOPE}: {where} serves {'/'.join(self.serves)} only and was handed "
            f"{given!r}. It refuses rather than rewriting the form it was given (§BH61(b)).")


#: The forms the engine can draw. `silhouettes._ARCHETYPES` is built from this.
#: §BH70(1), his words: "A 'Complete Product' is ANY cosmetic product, not a bottle: lipstick, eyeliner, mascara,
#: pencil, compact, palette, tube, jar, bottle, and anything else in cosmetics." Measured on the four forms that were
#: here: a lipstick and a mascara were read as a squeeze tube with a crimped end, and an eyeliner or a pencil had no
#: form at all and could not be entered at its size. The three that join are the three the four could not honestly
#: stand in for; an eyeliner is a pencil, or a mascara-shaped vial when it is liquid and carries a wand.
#: [§BH71 PART 3, the owner's goal of 2026-09-28: "Add each as a shape the system can draw." — five join, the
#: packagings the seven could not stand in for without squeezing a product into the wrong shape; see VOCABULARY]
ARCHETYPES = ("bottle", "jar", "tube", "compact", "lipstick", "mascara", "pencil",
              "tin", "sachet", "oval_stick", "aerosol", "ampoule")

#: Every proportion control the editor knows. Which ones APPLY is per archetype, below.
PROPORTION_KEYS = ("height_mm", "width_mm", "depth_mm", "neck_ratio")

#: §BH64(d): HOW A FORM IS SEEN. The owner: the preview "draws a jar while the record says compact …
#: I judge by the picture, and the picture is lying", and the compact's card is blank because
#: `static/img/containers/compact.png` does not exist. Both are the same gap — a form declared its
#: words and never declared its APPEARANCE, so the drawer's `else` (a bottle) and a missing PNG were
#: what a new archetype inherited.
#:
#:   drawn_as   ELEVATION (seen from the side) or PLAN (seen from above)
#:   nominal    the proportions the CARD ICON is drawn at, so an icon needs no profile to exist
#:
#: `nominal` is a drawing decision and NOT a claim about any product: it exists so five cards can be
#: drawn before a task is loaded. The bottle's four are `CONTAINER_EDITOR_PROPORTIONS`' own defaults,
#: lifted not invented; the other three are chosen to read as their own form at icon size.
#: [§BH70(1): it is also the size a form OPENS at in the shape step when nothing — no record, no product row, no
#: person — has given it one. The editor opened every form at the bottle's 110 x 40 x 40, "so a palette opens as 40
#: wide and 110 tall"; a starting size a person changes, never a measurement, exactly as the card icon's is.]
#:
#:   ranges     OPTIONAL — the size controls' own limits for a form the shared ones cannot reach, as
#:              {proportion: (min, max)} in millimetres. The shared rows (`targets.ui.CONTAINER_EDITOR_PROPORTIONS`)
#:              stop at 20 mm wide and 10 mm deep, so a 7 mm pencil or a 12 mm mascara could not be entered at its
#:              size (§BH70(1), item 14). A form that declares none keeps the shared rows exactly as they were.
ELEVATION, PLAN = "ELEVATION", "PLAN"

#: §BH66(a): WHICH SURFACE IS THE PRODUCT'S PRIMARY ONE, AND WHETHER IT IS A FRONT OR A FACE. The owner, ruling that
#: §AU1 had been governing a form it was never written for: "§AU1 governs bottle, jar and tube fronts as it always
#: has. It does NOT govern a compact lid, and it does not govern any future form whose primary surface is its face —
#: a palette, a case, a box lid. On such a surface the concept's own arrangement governs." That sentence needs one
#: fact per form, and it is declared here — never inferred from the form's name in a composer, which is the §BH61
#: lesson: a value nobody declared is the value some `else` supplies.
#:
#:   FRONT   a panel of a body the eye walks around — §AU1's ruled front (name, a rule below it, one line)
#:   FACE    the whole of the product as it is held and seen — the concept's own arrangement (§BH66(a))
#:
#: `surface` is one of the form's own `surfaces`, and the conformance test holds it there.
FRONT, FACE = "front", "face"

VOCABULARY: dict[str, dict] = {
    "bottle": {
        "label": "Bottle",
        "closure_part": "cap",          # §BH70(1), item 21: the word for the part its closure colour paints
        "description": "A vertical container with a defined body, shoulder, neck and closure.",
        "variants": (("cylindrical", "Cylindrical"), ("tapered", "Tapered"),
                     ("square", "Square"), ("slim", "Slim"),
                     # [§BH71 PART 3: an airless bottle, a perfume flacon, a roll-on — the catalogue's]
                     ("airless", "Airless"), ("flacon", "Flacon"), ("roller", "Roll-on")),
        "closures": (("screw", "Screw Cap"), ("pump", "Pump"),
                     ("flip", "Flip Top"), ("dropper", "Dropper"),
                     # [§BH71 PART 3: a nail polish's brush cap, a perfume's crimped spray, an airless pump's
                     # overcap, a fine mist's, a roll-on's ball under its cap]
                     ("brush_cap", "Brush Cap"), ("crimp_spray", "Crimped Spray"),
                     ("airless_pump", "Airless Pump"), ("mist", "Fine Mist"), ("roller_ball", "Roller Ball")),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_LEFT", "BODY_RIGHT",
                     "SHOULDER", "NECK", "CAP_FRONT", "CAP_TOP", "BOTTOM"),
        # a bottle is the only form in this system with a NECK, and neck_ratio is its proportion
        "proportions": ("height_mm", "width_mm", "depth_mm", "neck_ratio"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        "nominal": {"height_mm": 110, "width_mm": 40, "depth_mm": 40, "neck_ratio": 0.42},
        # [§BH71 PART 3: a roll-on is 15 mm across and a lotion pump bottle 250 tall — the catalogue's pages]
        "ranges": {"height_mm": (40, 260), "width_mm": (12, 120), "depth_mm": (10, 120)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "jar": {
        "label": "Jar",
        "closure_part": "lid",
        "description": "A wider container with a broad opening and removable lid.",
        # [§BH71 PART 3: a loose powder's sifter jar under its deep lid, an airless jar's pump button on its lid]
        "variants": (("standard", "Standard"), ("sifter", "Sifter"), ("airless", "Airless")),
        "closures": (("lid", "Lid"), ("screw", "Screw Cap")),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CAP_TOP", "CAP_WRAP", "BOTTOM"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        "nominal": {"height_mm": 70, "width_mm": 60, "depth_mm": 60},
        # [§BH71 PART 3: a sifter jar is 20 mm tall and a 5 g pot 18 — the catalogue's pages]
        "ranges": {"height_mm": (15, 200), "width_mm": (20, 120), "depth_mm": (10, 120)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "tube": {
        "label": "Tube",
        "closure_part": "cap",
        "description": "A flexible or rigid tubular container with a dispensing closure.",
        "variants": (("standard", "Standard"), ("slim", "Slim")),
        "closures": (("screw", "Screw Cap"), ("flip", "Flip Top"), ("crimp", "Crimp Seal"),
                     ("nozzle", "Applicator Nozzle")),              # [§BH71 PART 3: a lip tube's]
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CRIMP_ZONE", "CAP_FRONT", "CAP_TOP"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        # [his answer after test day finding 3, 2026-09-30, (4) round: a tube's width is its round diameter, and the
        # shape step says so where every other form reads "Body Width"]
        "size_labels": {"width_mm": "Diameter (round end)"},
        # [and its width row reaches a lip tube's round 13 mm; its height and depth the shared rows]
        "ranges": {"height_mm": (40, 200), "width_mm": (13, 120), "depth_mm": (10, 120)},
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        "nominal": {"height_mm": 130, "width_mm": 35, "depth_mm": 20},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "compact": {
        "label": "Compact / Palette",
        "closure_part": "lid",
        "description": ("A hinged case that opens flat — pans or a pressed cake in the base, usually a "
                        "mirror in the lid. Drawn from above: the width and height are the lid seen from "
                        "above, and the closed thickness is the depth."),
        "variants": (("rounded_rect", "Rounded Rectangle"), ("square", "Square"), ("round", "Round"),
                     # [§BH71 PART 3: a cushion compact, round and deep; a paperboard palette, a book's corners]
                     ("cushion", "Cushion"), ("paperboard", "Paperboard Book")),
        "closures": (("clasp", "Clasp"), ("magnet", "Magnetic"), ("friction", "Friction Fit")),
        "surfaces": ("LID_TOP", "LID_EDGE", "BASE_BOTTOM", "BASE_EDGE"),
        # §BH61(b), his words: "no neck proportion on a hinged case, no cap dimensions where there is no cap"
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": False,
        # §BH55(a) built the compact to be drawn IN PLAN and §BH64(d)2 found that nothing drew it that
        # way: "the lid from above, its closed thickness the depth". The description above already said
        # so in words; this is the same sentence in a form the drawer can read.
        "drawn_as": PLAN,
        "nominal": {"height_mm": 95, "width_mm": 110, "depth_mm": 18},
        # [§BH71 PART 3: a twelve-well palette is 197 mm wide and a paperboard one 8 mm thin — the catalogue's pages]
        "ranges": {"height_mm": (30, 200), "width_mm": (20, 200), "depth_mm": (6, 120)},
        # §BH71 PART 1/3: the variant a lid traced from its concept is, by the trace's kind (concept_outline)
        "traced_variants": {"round": "round", "square": "square", "rounded_rect": "rounded_rect"},
        # §BH66(a), his words: "A compact's lid is ninety by seventy-four millimetres and it is the whole face of the
        # product" — the lid, seen in PLAN, is what a person holds and looks at
        "primary_surface": {"surface": "LID_TOP", "kind": FACE},
    },
    # §BH70(1) — THE THREE THE FOUR COULD NOT STAND IN FOR. Each is a body the eye walks around, drawn from the side
    # with its closure on, so each is an ELEVATION with a FRONT: §AU1 governs it as it governs a bottle, jar or tube
    # front — the executor's reading of §BH66(a), which scoped §AU1 away only from a form whose primary surface is its
    # face (a compact lid, a palette, a case, a box lid); a lipstick's case, a mascara's vial and a pencil's barrel are
    # none of those. Its vocabulary is the trade's own: a lipstick's cap pulls off or holds by a magnet, a mascara's
    # cap IS its wand, a pencil is sharpened or twisted up. Their surfaces are named from the contract's existing
    # vocabulary (`container_contract.SURFACES`); nothing is new but the three forms.
    "lipstick": {
        "label": "Lipstick",
        "closure_part": "cap",
        "description": "A twist-up stick in a case with a pull-off cap — a lipstick, or a balm or cream stick.",
        "variants": (("round", "Round"), ("square", "Square"), ("slim", "Slim")),
        "closures": (("cap", "Pull-off Cap"), ("magnet", "Magnetic Cap")),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CAP_FRONT", "CAP_TOP", "BOTTOM"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        "nominal": {"height_mm": 80, "width_mm": 20, "depth_mm": 20},
        # a mini lipstick is some 50 mm closed and a slim one 15 mm across; a full square case some 30
        "ranges": {"height_mm": (40, 120), "width_mm": (10, 40), "depth_mm": (10, 40)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "mascara": {
        # [the owner's answer of 2026-09-27: a gloss is asked "wand vial or squeeze tube?" — the vial is this form, and
        # the shape step names it so; it read "Mascara" alone]
        "label": "Mascara / Wand vial",
        "closure_part": "cap",
        "description": ("A slim vial whose long cap carries the wand and its brush — a mascara, or a gloss or liquid "
                        "liner with a wand."),
        "variants": (("round", "Round"), ("square", "Square"), ("slim", "Slim")),
        # [§BH71 PART 3: a gloss's doe-foot and a liquid liner's brush — the vial closed looks the same, and says which]
        "closures": (("wand", "Wand Cap"), ("doe_foot", "Doe-foot Applicator"), ("brush", "Brush Applicator")),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CAP_FRONT", "CAP_TOP", "BOTTOM"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        "nominal": {"height_mm": 125, "width_mm": 16, "depth_mm": 16},
        # a slim mascara is some 10-12 mm across; a full one 20
        "ranges": {"height_mm": (60, 200), "width_mm": (8, 40), "depth_mm": (8, 40)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "pencil": {
        "label": "Pencil",
        "closure_part": "cap",
        "description": "A slim pencil with a cap — an eyeliner, brow or lip pencil, sharpened or twist-up.",
        # [§BH71 PART 3: a liner or brow pen, and a click pen's button]
        "variants": (("sharpened", "Sharpened"), ("twist", "Twist-up"), ("pen", "Pen")),
        "closures": (("cap", "Cap"), ("click", "Click Button")),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CAP_FRONT", "CAP_TOP"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        "nominal": {"height_mm": 150, "width_mm": 8, "depth_mm": 8},
        # a cosmetic pencil is 7-8 mm across and a jumbo one 12, from a short 100 mm to a long 180
        "ranges": {"height_mm": (60, 200), "width_mm": (5, 20), "depth_mm": (5, 20)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    # §BH71 PART 3, THE OWNER'S GOAL OF 2026-09-28: "Use the web search to build the list of cosmetic product types
    # and their real packaging, with typical sizes ... Add each as a shape the system can draw." FIVE THE SEVEN COULD
    # NOT STAND IN FOR without squeezing a product into the wrong shape (his "never"), each measured on the pages the
    # research leaf read (archive/work/bh71_trends_shapes_every_form/research/shapes/CATALOGUE.md names each one's sources): a tin is not a compact (no
    # hinge, no pans, no mirror) and not a jar (its artwork is its lid, seen from above); a sachet has no cap and is
    # flat; an oval stick is wider than a lipstick's 40 mm and its cap a snap-on fifth, not half; a can has no neck to
    # label; an ampoule has no cap on a shoulder and is some ten millimetres across. Their sizes are the pages' own.
    "tin": {
        "label": "Tin",
        "closure_part": "lid",
        "description": ("A shallow metal tin — round with a screw or slip lid, or a slide tin — for a lip balm, a salve "
                        "or a solid perfume. Drawn from above: the lid as it is held, the closed depth its thickness."),
        "variants": (("round", "Round"), ("slide", "Slide")),
        "closures": (("screw", "Screw Lid"), ("slip", "Slip Lid"), ("slide", "Slide Lid")),
        "surfaces": ("LID_TOP", "LID_EDGE", "BASE_BOTTOM", "BASE_EDGE"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": False,
        "drawn_as": PLAN,
        # a 15 ml tin is 42 mm across and 18 deep; a lip balm tin 30, a solid perfume's up to 75
        "nominal": {"height_mm": 42, "width_mm": 42, "depth_mm": 18},
        # a four-cornered lid traced from a tin's concept is a slide tin's
        "traced_variants": {"round": "round", "square": "slide", "rounded_rect": "slide"},
        "ranges": {"height_mm": (25, 80), "width_mm": (25, 80), "depth_mm": (5, 30)},
        "primary_surface": {"surface": "LID_TOP", "kind": FACE},
    },
    "sachet": {
        "label": "Sachet / Flat pouch",
        "closure_part": "seal",
        "description": ("A flat pouch sealed along its edges, torn open at a notch — a sheet mask or a sample sachet. "
                        "Drawn flat, its front as it lies."),
        "variants": (("three_side", "Three-side Seal"), ("four_side", "Four-side Seal")),
        "closures": (("tear_notch", "Heat Seal, Tear Notch"),),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "CRIMP_ZONE"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": False,
        "drawn_as": PLAN,
        # a sheet mask's pouch is some 180 x 125 mm; a sample sachet 50 x 40, a few millimetres thick
        "nominal": {"height_mm": 180, "width_mm": 125, "depth_mm": 3},
        "ranges": {"height_mm": (40, 240), "width_mm": (30, 160), "depth_mm": (1, 10)},
        # its front is printed as a label is, the name and its line ruled (§AU1) — its closure is its seal, not a face
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "oval_stick": {
        "label": "Oval stick",
        "closure_part": "cap",
        "description": "A twist-up stick in an oval case under a snap-on cap — a deodorant or a body stick.",
        "variants": (("oval", "Oval"), ("round", "Round")),
        "closures": (("snap_cap", "Snap-on Cap"),),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_LEFT", "BODY_RIGHT", "CAP_FRONT", "CAP_TOP", "BOTTOM"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        # the stick the research read: 124 x 54 x 32 mm; body sticks from 60 mm tall, up to 80 across
        "nominal": {"height_mm": 124, "width_mm": 54, "depth_mm": 32},
        "ranges": {"height_mm": (60, 160), "width_mm": (25, 80), "depth_mm": (15, 50)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "aerosol": {
        "label": "Aerosol can",
        "closure_part": "cap",
        "description": ("A can printed all round, its valve under a cap — a dry shampoo, a hair spray, a body spray or an "
                        "aerosol setting spray."),
        "variants": (("straight", "Straight"), ("necked", "Necked")),
        "closures": (("overcap", "Overcap"), ("actuator", "Spray-through Cap")),
        "surfaces": ("BODY_WRAP", "BODY_FRONT", "BODY_BACK", "SHOULDER", "CAP_TOP", "CAP_WRAP", "BOTTOM"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": True,
        "drawn_as": ELEVATION,
        # a 45 mm can, 150 tall with its cap to 190; travel cans from 60, the largest 260
        "nominal": {"height_mm": 190, "width_mm": 45, "depth_mm": 45},
        "ranges": {"height_mm": (60, 260), "width_mm": (20, 70), "depth_mm": (20, 70)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
    "ampoule": {
        "label": "Ampoule / Vial",
        "closure_part": "tip",
        "description": ("A single dose in a slim ampoule with a snap-off or twist-off tip, or a sample vial under a "
                        "stopper."),
        "variants": (("glass", "Glass Snap"), ("plastic", "Plastic Twist-off"), ("vial", "Sample Vial")),
        "closures": (("snap_tip", "Snap-off Tip"), ("twist_tab", "Twist-off Tab"), ("stopper", "Stopper")),
        "surfaces": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "NECK", "BOTTOM"),
        "proportions": ("height_mm", "width_mm", "depth_mm"),
        "has_cap_dimensions": False,
        "drawn_as": ELEVATION,
        # the 2 ml ampoule the research read: 75 x 11 mm; a hair ampoule to 170 tall, 30 across
        "nominal": {"height_mm": 75, "width_mm": 11, "depth_mm": 11},
        "ranges": {"height_mm": (40, 170), "width_mm": (6, 30), "depth_mm": (6, 30)},
        "primary_surface": {"surface": "BODY_FRONT", "kind": FRONT},
    },
}

#: NOT a drawable form. It exists so a person can say "none of these" honestly instead of being coerced into
#: bottle — the §BH61(a) rule in the one place it is allowed to be visible. It is NOT in `ARCHETYPES` and the
#: conformance test excludes it by name, because it has no vocabulary to conform to.
NON_DRAWABLE = {
    "other": {
        "label": "Other",
        # §BH70(1): it named the four forms there were, so it went stale the moment a fifth card stood beside it
        "description": "A form none of the other cards describes.",
        "pending_code": "OTHER_CUSTOM_PROFILE_RECONSTRUCTION_PENDING",
    },
}


def is_known(value) -> bool:
    return isinstance(value, str) and value.strip().lower() in VOCABULARY


def resolve(*candidates, looked_in=()) -> str:
    """The first candidate that names a known archetype, or a refusal that says what was missing.

    §BH61(a): never defaulted, never inferred, never assumed. A caller passes the places it looked, in order,
    so the stop can say where it looked — the owner's rule, not decoration.
    """
    for value in candidates:
        if is_known(value):
            return value.strip().lower()
    seen = next((v for v in candidates if v not in (None, "")), None)
    raise ArchetypeUnresolved(looked_in or [f"{len(candidates)} candidate(s)"], value=seen)


def require_scope(where, given, serves=("bottle",)) -> str:
    """A path that serves only some forms declares it here and refuses anything else AT ENTRY (§BH61(b)(c))."""
    if not is_known(given):
        raise ArchetypeUnresolved([where], value=given)
    got = given.strip().lower()
    if got not in serves:
        raise ArchetypeOutOfScope(where, given=got, serves=serves)
    return got


def vocabulary_of(archetype: str) -> dict:
    if not is_known(archetype):
        raise ArchetypeUnresolved(["vocabulary_of()"], value=archetype)
    return VOCABULARY[archetype.strip().lower()]


def variants_of(archetype):
    return vocabulary_of(archetype)["variants"]


def closures_of(archetype):
    return vocabulary_of(archetype)["closures"]


def surfaces_of(archetype):
    return vocabulary_of(archetype)["surfaces"]


def proportions_of(archetype):
    return vocabulary_of(archetype)["proportions"]


def drawn_as_of(archetype):
    """ELEVATION or PLAN — the view the preview and the card icon are drawn in (§BH64(d))."""
    return vocabulary_of(archetype)["drawn_as"]


def size_labels_of(archetype) -> dict:
    """``{proportion: the words the shape step labels it with}`` where the form names its own (a tube's width is its
    diameter at its round end); ``{}`` where the shared words hold."""
    return dict(VOCABULARY[archetype].get("size_labels") or {}) if archetype in VOCABULARY else {}


#: [his last goal before the pitch, 2026-10-16, Step 2: "real-world sizes (a blush compact is ~60–70 mm, not 110)"] a
#: form's starting size by what its brief names it holds: a compact of one pan (a blush, a powder, a highlighter, a
#: bronzer, a cushion) starts round at 65 mm; one its brief calls a palette keeps the form's own (a palette's)
NOMINAL_BY_CONTENT = {"compact": (r"\b(blush|powder|highlighter|bronzer|cushion|single pan|pressed)\b", r"\bpalette\b",
                                  {"height_mm": 65, "width_mm": 65, "depth_mm": 14})}


def nominal_for(archetype, brief) -> dict:
    """The form's starting size for the product its brief names (``NOMINAL_BY_CONTENT``), else its own (``nominal_of``)."""
    import re
    rule = NOMINAL_BY_CONTENT.get(archetype)
    text = str(brief) if brief else ""
    if rule is not None and re.search(rule[0], text, re.I) and not re.search(rule[1], text, re.I):
        return dict(rule[2])
    return nominal_of(archetype)


def nominal_of(archetype):
    """The proportions a CARD ICON is drawn at, before any task is loaded (§BH64(d))."""
    return dict(vocabulary_of(archetype)["nominal"])


def ranges_of(archetype) -> dict:
    """``{proportion: (min, max)}`` — the size limits this form declares of its own; empty when it keeps the shared
    rows (§BH70(1), item 14). Read by the editor's rows, its config and the server's validation alike, through
    `targets.ui.form_ranges`, so the slider and the server can never disagree about what a form may measure."""
    return {k: tuple(v) for k, v in (vocabulary_of(archetype).get("ranges") or {}).items()}


def traced_variants_of(archetype) -> dict:
    """§BH71 PART 1/3: ``{traced kind: variant}`` — which of this form's own variants a lid traced from its concept
    is; empty for a form with no lid to trace (a form drawn in elevation, a sachet)."""
    return dict(vocabulary_of(archetype).get("traced_variants") or {})


def primary_surface_of(archetype) -> dict:
    """``{"surface": ..., "kind": FRONT | FACE}`` — the form's primary surface and which ruling arranges it (§BH66(a))."""
    return dict(vocabulary_of(archetype)["primary_surface"])


def is_face(archetype) -> bool:
    """True when the form's primary surface is its FACE: the concept's own arrangement governs it, not §AU1."""
    return primary_surface_of(archetype)["kind"] == FACE


def closure_part_of(archetype) -> str:
    """The part a closure colour paints, in the form's own word — a bottle's or a lipstick's ``cap``, a jar's or a
    compact's ``lid`` (§BH70(1), item 21): the review board and the drawn file said "cap" of every form."""
    return vocabulary_of(archetype)["closure_part"]


#: the things every archetype must have, named so the conformance test can report what is MISSING.
#: §BH64(d): `drawn_as` and `nominal` JOIN THE LIST — the owner's "so the next archetype gets one by
#: construction". A form that declares no appearance now fails the gate with that word in its list,
#: instead of reaching him drawn as a bottle with a blank card.
#: §BH70(1), item 21 of the list the owner was sent: `closure_part` joins — the word the review board and the drawn
#: file use for the part a closure colour paints, so the next form names its own instead of inheriting "cap".
DEPENDENT_VOCABULARY = ("variants", "closures", "surfaces", "proportions", "has_cap_dimensions",
                        "drawn_as", "nominal", "primary_surface", "closure_part")


def missing_vocabulary(archetype: str) -> list[str]:
    """What this archetype LACKS — the list the owner asked the gate to print (§BH61(c))."""
    entry = VOCABULARY.get((archetype or "").strip().lower())
    if entry is None:
        return list(DEPENDENT_VOCABULARY) + ["(not declared)"]
    missing = []
    for key in DEPENDENT_VOCABULARY:
        if key not in entry:
            missing.append(key)
        elif key != "has_cap_dimensions" and not entry[key]:
            missing.append(key)
    return missing


__all__ = [
    "ARCHETYPES", "VOCABULARY", "NON_DRAWABLE", "PROPORTION_KEYS",
    "DEPENDENT_VOCABULARY", "ARCHETYPE_UNRESOLVED", "ARCHETYPE_OUT_OF_SCOPE",
    "ArchetypeUnresolved", "ArchetypeOutOfScope",
    "is_known", "resolve", "require_scope", "vocabulary_of",
    "variants_of", "closures_of", "surfaces_of", "proportions_of", "ranges_of",
    "missing_vocabulary", "FRONT", "FACE", "primary_surface_of", "is_face", "closure_part_of",
]
