"""The design-target selector, as data (B4a).

The chips were hardcoded in the template, which is how the list drifted: only
four of the six future targets were listed, three carried abbreviated labels,
and none carried the description that tells a user what the target actually
does. One list here, rendered by the template and asserted by the tests, so a
target cannot be present in one place and missing in another.

``active`` is what the create form will submit. It is deliberately narrower
than the pipeline's capability: Complete Product remains registered and fully
functional, and is disabled HERE only because the owner has scoped the current
milestone to the two single-stage targets. Disabling a card never removes a
capability — see ``COMPLETE_PRODUCT_NOTE``.

[§BH55 PHASE 1, OWNER STANDING ORDER 2026-09-19 — "COMPLETE PRODUCT … The target ships: container and packaging as
one multi-stage project." The paragraph above is what stood. Complete Product is ACTIVE in the selector now; the
five targets after it still read "Coming soon" until Phase 2 builds them.]
[§BH55 PHASE 2, 2026-09-19: Marketing Material ships — the first artwork target (targets/artwork.py); four targets
still read "Coming soon".]
[§BH55 PHASE 2, 2026-09-19: Social Media ships on the same SDK; three targets still read "Coming soon".]
[§BH55 PHASE 2, 2026-09-19: Exhibition Booth ships — the stand's graphics; two targets still read "Coming soon".]
[§BH55 PHASE 2, 2026-09-19: Display Stand ships — a counter display sized from the product; one target still reads
"Coming soon".]
[§BH55 PHASE 2, 2026-09-19: Gift Set ships on the packaging target; no target reads "Coming soon".]
[§BH55 PHASE 2, 2026-09-19: Palette read "Active" and failed after its paid concepts; it is NAMED with what it
needs, its chip disabled, and the create door refuses it before any spend.]
[§BH55 PHASE 3, 2026-09-20: every other card read "Active" — a stranger could not tell the four targets whose
design is finished at its review from the four whose design cannot be finished without the owner or at all yet.
Each card now says how its design is finished, as measured (the Phase 2 dry runs, Gate 2's own refusals).]
"""
import re

from .base import DesignTarget
from apps.pipeline.targets.container import archetypes as _declared

COMPLETE_PRODUCT_NOTE = (
    "Complete Product is implemented and its pipeline is registered and "
    "working — the 2C live pilot exercised it end to end. It is shown as "
    "coming soon in this selector because the owner scoped the current "
    "milestone to the single-stage targets, not because the capability was "
    "removed or regressed. [§BH55 Phase 1, 2026-09-19: the owner has ordered it "
    "shipped, and it is ACTIVE in this selector.]"
)

#: §BH55 Phase 3: how a design of each target is finished — measured, never assumed: Packaging, Marketing Material,
#: Exhibition Booth and Social Media reach "Finished" when a reviewer approves them at Gate 2 (their no-spend dry
#: runs: 200 → completed); a bottle's Gate 2 waits on the owner's recorded acceptance (HUMAN_VISUAL_ACCEPTANCE_REQUIRED,
#: only his door writes it); a gift set and a display stand are held at Gate 2 (DIMENSION_COMBINATION_UNSUPPORTED,
#: PHYSICAL_SAMPLE_VALIDATION_REQUIRED). They read "Active".
#: [§BH70(3): "A physical sample is never required to finish a design … Remove that condition from Display Stand." A
#: display stand is finished at its review since — a clean one is approved at Gate 2, 200, no spend, measured in
#: test_create_design_target; the gift set is still held, by its die's own domain.]
#: [§BH70(4) (§BH70 LIVE), his words: "The bottom line of every card says one plain thing I can understand, the same
#: wording for the same meaning. No engine status." Two meanings stand, so two lines: finished when a reviewer approves
#: it at the review, or not finishable yet — its card's description says why. "Finished at its review" named a gate;
#: "Finished when the owner accepts it" and "… accepts its bottle" promised a container's finish that no container
#: reaches today — §BH70(1) item 1, MEASURED: his four containers waiting at their review (tasks 110, 91, 89 and 51)
#: are all refused there, for the maker's printing specification, a person's print check and the maker's limits,
#: whatever the form.]
FINISHED_AT_REVIEW = "Finished when a reviewer approves it"
FINISHED_BY_THE_OWNER = "Finished when the owner accepts it"
CANNOT_FINISH_YET = "Cannot be finished yet"
#: §BH70(1), item 1: why a container cannot be finished yet, in the words its card says it
#: [the owner's answer of 2026-09-27: the maker's printing specification is a production note, never a blocker, so
#: it is no longer why. MEASURED after it, read-only, on his four containers (110, 91, 89, 51): each is refused by the
#: fidelity checks — 17 quantitative axes each, the base and motif reports' own, and the concept check written for
#: the dropper alone — and by its copy fit, front and back, unmeasured outside the dropper: the checks his §BH50(f)(5)
#: says must be measured before a design is accepted. It read "Its finish waits on the maker's printing
#: specification and a person's print check."]
CONTAINER_FINISH_WAITS = ("Its finish waits on checks not built yet: whether the drawing is true to its concept, "
                          "and whether its copy fits.")
#: [§BH71 (0a) and (0b), the owner's goal of 2026-09-28: "My approval overrides §BH50(f)(5). Unmeasured checks
#: (fidelity to the concept, copy fit) show as a warning beside Approve, never a block" and "Propose a batch-code
#: place for every form that lacks one, shown as a production note, not a blocker." MEASURED after both, read-only
#: (archive/work/bh71_trends_shapes_every_form/checks/b03_cards.py): a clean container record — its only codes unmeasured checks and a code place
#: never confirmed — waits at Gate 2 on the owner's acceptance alone, and with it is approved; on his compact 110 the
#: only things standing are its record's staleness and his acceptance. So a container is finished when the owner
#: accepts it and a reviewer approves it, and no card says it cannot be finished. CONTAINER_FINISH_WAITS and
#: CANNOT_FINISH_YET stay defined; no card says them.]
FINISHED_WHEN_ACCEPTED = "Finished when the owner accepts it and a reviewer approves it"
CONTAINER_FINISH = "What is not measured yet is shown beside Approve as a warning, never a block."

TARGET_CARDS = [
    {
        "value": DesignTarget.PRODUCT_CONTAINER.value,
        "name": "Product Container",
        # §BH70(1), items 1, 18 and 19: it read "Design the physical bottle, jar or tube before packaging." and
        # "Finished when the owner accepts it", under a bottle with a neck — his words: "The card copy says 'any
        # cosmetic product'"
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Design any cosmetic product itself — … — before its packaging. " + CONTAINER_FINISH
        "description": "Any cosmetic product itself — a lipstick, compact, palette, mascara, pencil, tube, jar or "
                       "bottle.",
        "status": FINISHED_WHEN_ACCEPTED,   # [§BH71 (0a) and (0b): it read CANNOT_FINISH_YET] §BH55 Phase 3: it read "Active"; its description was the B4a brief's own
        "icon": "forms",
        "active": True,
    },
    {
        "value": DesignTarget.PACKAGING.value,
        "name": "Packaging",
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Design artwork around an existing dieline or confirmed package structure."
        "description": "The box or carton around a product.",
        "status": FINISHED_AT_REVIEW,
        "icon": "carton",
        "active": True,
    },
    {
        "value": DesignTarget.PALETTE.value,
        "name": "Palette",
        # §BH55 Phase 2: was "Active" — it accepted a project, spent on its concepts and failed after Gate 1
        # [§BH70(2): "Palette must be startable from New design … It does not refuse me at the door." It read "Needs its
        # own design intent and case" and could not be chosen; it starts now as its case — a Product Container of the
        # Compact / Palette form, its concept made first — and its bottom line is the Product Container's]
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "…, designed as its case: its concept is made first, then you confirm the case's size
        # and closure, and its lid is designed from the concept. " + CONTAINER_FINISH
        "description": "An eyeshadow, blush or face palette: its concept is made first, then its case and lid.",
        "status": FINISHED_WHEN_ACCEPTED,   # §BH70(1) item 1 and §BH70(4): every container's line [§BH71: CANNOT_FINISH_YET]
        "icon": "palette",
        "active": True,
    },
    {
        "value": DesignTarget.COMPLETE_PRODUCT.value,
        "name": "Complete Product",
        # §BH70(1), items 1 and 18: it read "Container and packaging together, as one multi-stage project." and
        # "Finished when the owner accepts its bottle" — its container stage cannot be finished yet, so it never
        # reaches its packaging
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Any cosmetic product and its packaging, designed together as one project. "
        # + CONTAINER_FINISH
        "description": "Any cosmetic product and its box, designed together.",
        "status": FINISHED_WHEN_ACCEPTED,   # §BH55 Phase 3: it read "Active" [§BH71: CANNOT_FINISH_YET]
        "icon": "stack",
        "active": True,
    },
    {
        "value": DesignTarget.GIFT_SET.value,
        "name": "Gift Set",
        # §BH55 Phase 2: was "Multi-item presentation set with a shared structure." — the set is several of
        # ONE product; a set of different products is not made yet
        # §BH70(3), his words: "For Gift Set, tell me in plain words what the missing closure is and what it takes to
        # draw it." It read "its carton needs a corrected closure this system does not draw"
        # [the owner's answer of 2026-09-27: "Yes, switch the Gift Set carton to the corrected flap." Its carton is
        # drawn at 1.2 since, and every set up to a dozen closes; a reviewer approves it, and a colleague test-fits
        # the first sample (§BH70(3)). It read "… not yet approved: its top flap is cut from the carton's width …"]
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Several of the product in one carton, side by side on an insert: the carton sized to
        # hold them and designed like any carton, its top flap cut from the carton's depth so it closes. A colleague
        # test-fits the first sample."
        "description": "Several of one product side by side in one carton; a colleague test-fits the first one.",
        "status": FINISHED_AT_REVIEW,
        "icon": "gift",
        "active": True,
    },
    {
        "value": DesignTarget.DISPLAY_STAND.value,
        "name": "Display Stand",
        # §BH55 Phase 2: was "Retail stand or counter unit holding the product." — a counter display is made; a
        # floor stand is not, and the card says which
        # §BH70(3): it said "not yet approved: its tray's structure needs a tested physical sample" — a colleague
        # test-fits the sample, and nothing waits on it
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "A counter display sized to hold the product: its header card and tray lip, and the
        # tray's blank drawn provisionally for a converter — a colleague test-fits its first sample."
        "description": "A counter display that holds the product; a colleague test-fits the first one.",
        "status": FINISHED_AT_REVIEW,
        "icon": "stand",
        "active": True,
    },
    {
        "value": DesignTarget.MARKETING_MATERIAL.value,
        "name": "Marketing Material",
        # §BH55 Phase 2: was "Printed and digital collateral around the product." — the kit is printed; the
        # channel-sized pieces are Social Media's
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Printed pieces around the product: an A5 leaflet and an A4 poster, or the pieces your
        # brief names."
        "description": "A leaflet and a poster for the product, or the printed pieces you name.",
        "status": FINISHED_AT_REVIEW,
        "icon": "leaflet",
        "active": True,
    },
    {
        "value": DesignTarget.EXHIBITION_BOOTH.value,
        "name": "Exhibition Booth",
        # §BH55 Phase 2: was "Trade-show stand and its surrounding environment." — the stand's graphics are
        # made; its spatial design (plan, furniture, lighting, visitor flow) is not drawn, and the card says so
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "The stand's graphics at true size: a back wall, a counter front and a roll-up banner
        # around one key visual. The stand's floor plan is not drawn."
        "description": "A trade-show stand's graphics: its back wall, counter and roll-up banner.",
        "status": FINISHED_AT_REVIEW,
        "icon": "booth",
        "active": True,
    },
    {
        "value": DesignTarget.SOCIAL_MEDIA.value,
        "name": "Social Media",
        # §BH55 Phase 2: was "Channel-sized assets derived from the approved design." — the pieces are composed
        # around the concept approved for them; drawing them from ANOTHER task's approved design needs a way to pick
        # that design, which is not built
        # [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Channel-sized pieces around the product: a square and a portrait post, a story and a
        # link image, each at its exact pixel size."
        "description": "Posts, a story and a link picture for the product, each at its exact size.",
        "status": FINISHED_AT_REVIEW,
        "icon": "social",
        "active": True,
    },
]

# Rescue scope, 18 October 2026: names describe currently implemented output.
for card in TARGET_CARDS:
    if card['value'] == 'product_container':
        card['name'] = 'Product'
    elif card['value'] == 'packaging':
        card['name'] = 'Carton'
    elif card['value'] == 'display_stand':
        card.update(name='Display', description='Countertop graphics and a provisional flat tray. Stepped assembly is being rebuilt.', status='Graphics only — construction pending')
    elif card['value'] == 'exhibition_booth':
        card.update(name='Booth graphics', description='Wall and counter artwork only. Booth, tester and floor-stand engineering are outside this release.', status='Graphics only')
_order = ['product_container', 'display_stand', 'packaging']
TARGET_CARDS.sort(key=lambda c: _order.index(c['value']) if c['value'] in _order else len(_order))

#: Targets the create form may submit.
ACTIVE_TARGETS = [c["value"] for c in TARGET_CARDS if c["active"]]

#: Default selection. Product Container leads because it is the active
#: milestone, but Packaging is not "second" in any workflow sense — the
#: selector says so explicitly rather than implying an order.
#: [§BH55 Phase 3, 2026-09-20: Packaging leads now. The default was the one target a stranger can never finish —
#: a bottle's last approval is the owner's — chosen in July for a milestone that has closed; the create door's own
#: default, when no target is sent, was already Packaging.]
DEFAULT_TARGET = ""

# [his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"] it read "Product Container and Packaging are different design targets, not steps in a
# sequence. Choose Product Container to design the vessel itself; choose Packaging to design artwork around a
# structure you already have. Neither has to come first."
SELECTOR_EXPLANATION = "Choose Product, Display or Carton. Nothing is selected for you."

# Product Container creation collects HINTS only. The authoritative profile is
# confirmed later at the B3 gate (ConfirmContainerProfileView), which is where
# archetype, variant, cap, proportions and the reconstruction trigger live.
PROFILE_GATE_NOTE = (
    "These are starting hints, not specifications. Dimensions, proportions "
    "and the closure are confirmed later at the Confirm Profile step — you do "
    "not need technical measurements to start."
)

CONTAINER_HINT_FIELDS = [
    # §BH70(1), item 15: every form there is, read from the one declaration — it offered Bottle, Jar, Tube and Other,
    # so a palette, a lipstick or a pencil could not be hinted at all, and its examples were a serum's
    {"id": "container-archetype", "label": "Container type",
     "hint": "optional — auto if blank",
     "options": ([("", "Auto (infer from product)")]
                 + [(k, _declared.VOCABULARY[k]["label"]) for k in _declared.ARCHETYPES]
                 + [("other", "Other")])},
    {"id": "container-category", "label": "Product category",
     "hint": "optional — e.g. serum, lipstick, eyeliner, face powder", "options": None},
    {"id": "container-capacity", "label": "Capacity or size",
     "hint": "optional — e.g. 30 ml, 3.5 g, four pans; confirmed later", "options": None},
    {"id": "container-closure", "label": "Cap or closure",
     "hint": "optional — e.g. pump, screw cap, magnetic cap, clasp", "options": None},
]

#: §BH70(1), item 15: the targets whose design starts from the product's own shape, and so asks these hints — a Product
#: Container, and a Complete Product, whose first stage IS a product container. Only the first showed them.
HINT_TARGETS = ("product_container", "complete_product")


# --------------------------------------------------------------------------
# Confirm Profile UI-1 — the ONE owner-facing profile-editor catalog.
# Persisted keys are the backend vocabulary exactly (silhouettes.py +
# ConfirmContainerProfileView); only labels/descriptions are owner-facing.
# 'other' is an editor-level selection carried over from the B4a hint options
# — the confirmation contract (SUPPORTED_ARCHETYPES) does not accept it, so
# it is flagged confirmable: False rather than being hidden or silently
# converted to bottle.
# --------------------------------------------------------------------------

PROFILE_EDITOR_SCHEMA = "container_profile_editor_config/1.0"

#: §BH61(c): READ FROM THE ONE DECLARATION. This was the THIRD per-archetype registry found by a
#: failure — the owner chose a palette and this form offered him a Bottle. The drawable forms and their
#: vocabularies are the declaration's; only "Other" is the editor's own, because it is the honest
#: non-confirmable escape and has no vocabulary to declare.
def _points(segments, width: float, height: float) -> list:
    """A drawn path as points in shares of its box — each cubic sampled at eight steps — for a browser to scale."""
    out, last = [], (0.0, 0.0)
    for sg in segments:
        kind = type(sg).__name__
        if kind in ("MoveTo", "LineTo"):
            last = (sg.x, sg.y)
            out.append(last)
        elif kind == "CubicTo":
            for i in range(1, 9):
                t = i / 8.0
                m = 1.0 - t
                out.append((m ** 3 * last[0] + 3 * m * m * t * sg.x1 + 3 * m * t * t * sg.x2 + t ** 3 * sg.x,
                            m ** 3 * last[1] + 3 * m * m * t * sg.y1 + 3 * m * t * t * sg.y2 + t ** 3 * sg.y))
            last = (sg.x, sg.y)
    return [[round(x / width, 4), round(y / height, 4)] for x, y in out]


def _form_outlines(archetype: str) -> dict:
    """§BH71 PART 3: ``{variant: {"outline", "closure"}}`` — each variant drawn by the one drawing
    (``silhouettes.build_backbone``) at the form's own starting size, its first closure, as points in shares of its
    box. The shape step's preview scales these for a form it has no hand-drawn picture of — never a bottle's."""
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    nominal = _declared.nominal_of(archetype)
    closures = [k for k, _ in _declared.closures_of(archetype)]
    out = {}
    for variant, _label in _declared.variants_of(archetype):
        bb = build_backbone(ContainerProfile(
            archetype=archetype, variant=variant, cap_style=closures[0],
            width_mm=float(nominal["width_mm"]), height_mm=float(nominal["height_mm"])))
        out[variant] = {"outline": _points(bb.silhouette, bb.width_mm, bb.height_mm),
                        "closure": _points(bb.cap_region, bb.width_mm, bb.height_mm)}
    return out


CONTAINER_EDITOR_ARCHETYPES = [
    {"key": k, "label": _declared.VOCABULARY[k]["label"],
     "confirmable": True,
     "description": _declared.VOCABULARY[k]["description"],
     "variants": list(_declared.variants_of(k)),
     "caps": list(_declared.closures_of(k)),
     "proportions": list(_declared.proportions_of(k)),
     "has_cap_dimensions": _declared.VOCABULARY[k]["has_cap_dimensions"],
     "drawn_as": _declared.drawn_as_of(k),
     "nominal": _declared.nominal_of(k),
     # [his answer after test day finding 3, (4) round: a tube's width row reads as its diameter]
     "labels": _declared.size_labels_of(k),
     # §BH70(1): the form's OWN size limits where it declares them — a pencil is 7 mm across and the shared rows
     # stop at 20 — {proportion: (min, max)}; the four forms that declare none keep the shared rows exactly
     "ranges": _declared.ranges_of(k),
     # §BH71 PART 3: each variant's drawn outline and closure at the form's starting size, in shares of its box —
     # the one drawing the preview scales for a form it has no hand-drawn picture of
     "outlines": _form_outlines(k)}
    for k in _declared.ARCHETYPES
] + [
    {"key": "other", "label": _declared.NON_DRAWABLE["other"]["label"],
     "confirmable": False,
     "description": _declared.NON_DRAWABLE["other"]["description"],
     "pending_code": _declared.NON_DRAWABLE["other"]["pending_code"],
     # §BH64(d): a custom form still has a SIZE, and it has no neck — a neck is a bottle's word.
     # This was `[]`, which was harmless while the browser ignored the per-archetype list and drew the
     # global one; with the list finally wired it would have left a custom form with no size control at
     # all and a sentence naming measurements nobody could change.
     "variants": [], "caps": [],
     "proportions": ["height_mm", "width_mm", "depth_mm"], "has_cap_dimensions": False},
]
_CONTAINER_EDITOR_ARCHETYPES_WAS = [
    {"key": "bottle", "label": "Bottle", "confirmable": True,
     "description": "A vertical container with a defined body, shoulder, "
                    "neck and closure.",
     "variants": [("cylindrical", "Cylindrical"), ("tapered", "Tapered"),
                  ("square", "Square"), ("slim", "Slim")],
     # dropper is a real accepted cap_style (the live dropper-bottle pilot
     # uses it) — its absence from the old JS catalog was a gap
     "caps": [("screw", "Screw Cap"), ("pump", "Pump"),
              ("flip", "Flip Top"), ("dropper", "Dropper")]},
    {"key": "jar", "label": "Jar", "confirmable": True,
     "description": "A wider container with a broad opening and removable "
                    "lid.",
     "variants": [("standard", "Standard")],
     "caps": [("lid", "Lid"), ("screw", "Screw Cap")]},
    {"key": "tube", "label": "Tube", "confirmable": True,
     "description": "A flexible or rigid tubular container with a "
                    "dispensing closure.",
     "variants": [("standard", "Standard"), ("slim", "Slim")],
     "caps": [("screw", "Screw Cap"), ("flip", "Flip Top"),
              ("crimp", "Crimp Seal")]},
    # §BH55(a): the owner's Phase 1 brief is a hinged palette, and the three forms above could not draw one —
    # "compact" scanned to JAR and "palette" to BOTTLE. Confirmable, because silhouettes._compact draws it.
    {"key": "compact", "label": "Compact / Palette", "confirmable": True,
     "description": "A hinged case that opens flat — pans or a pressed cake in "
                    "the base, usually a mirror in the lid. Drawn in PLAN: the "
                    "width and height are the lid seen from above, and the "
                    "closed thickness is the depth.",
     "variants": [("rounded_rect", "Rounded Rectangle"), ("square", "Square"),
                  ("round", "Round")],
     "caps": [("clasp", "Clasp"), ("magnet", "Magnetic"), ("friction", "Friction Fit")]},
    {"key": "other", "label": "Other", "confirmable": False,
     "description": "A container form that does not fit the standard "
                    "Bottle, Jar or Tube profiles.",
     # UI-2A §5 outcome B: the reconstruction backend has no safe neutral
     # custom path (silhouettes builds bottle/jar/tube/compact only), so Other stays
     # selectable for exploration and non-confirmable, with the reason on
     # record rather than a silent coercion to bottle.
     "pending_code": "OTHER_CUSTOM_PROFILE_RECONSTRUCTION_PENDING",
     "variants": [], "caps": []},
]

#: bounded proportion controls — the SAME limits the old JS hardcoded, now
#: owned server-side. The mm values are HUMAN_CONFIRMED_CONCEPT_ONLY numbers
#: for the silhouette contract, never manufacturing dimensions.
CONTAINER_EDITOR_PROPORTIONS = [
    {"key": "height_mm", "label": "Overall Height", "min": 40, "max": 200,
     "step": 1, "unit": "mm", "default": 110},
    {"key": "width_mm", "label": "Body Width", "min": 20, "max": 120,
     "step": 1, "unit": "mm", "default": 40},
    {"key": "depth_mm", "label": "Body Depth", "min": 10, "max": 120,
     "step": 1, "unit": "mm", "default": 40},
    {"key": "neck_ratio", "label": "Neck Proportion", "min": 0.2, "max": 0.7,
     "step": 0.01, "unit": "", "default": 0.42},
]

PROPORTION_NOTE = ("These controls define relative silhouette proportions, "
                   "not manufacturing dimensions.")

#: provisional cap dimensions share one bounded range (the old JS hardcoded
#: 1–120 on the cap inputs; this is now the single authority)
CONTAINER_EDITOR_CAP_DIM_RANGE = {"min": 1, "max": 120}

#: the profile's authority level — concept reconstruction input, never
#: supplier-approved manufacturing dimensions
PROFILE_AUTHORITY = "HUMAN_CONFIRMED_CONCEPT_ONLY"


def validate_container_profile_payload(profile: dict) -> list:
    """UI-2A §9 — strict validation of the PROVIDED profile values.

    The browser's readiness gating is a courtesy; this is the verdict. Every
    provided numeric must parse, be finite and sit inside the editor ranges;
    a provided variant/closure must belong to the submitted archetype's
    catalog. Presence requirements stay with the versioned contract
    (``profile_is_confirmable``) — this layer never silently ignores a bad
    value the way the pre-UI-2A sanitizer did.
    """
    import math

    errors = []
    # §BH64(c)/§BH61(a): NO DEFAULT — the same `.get()` shape as the view's,
    # in the file §BH61(c) rewrote, and missed for the same reason: a search
    # for archetype literals cannot see a name that only appears as a default.
    # An ABSENT archetype is not this layer's refusal to make: the docstring
    # above divides the work — "presence requirements stay with the versioned
    # contract (`profile_is_confirmable`)" — and the view refuses an unknown or
    # absent archetype with a 400 before anything reads this. What changes here
    # is only that absent no longer READS AS BOTTLE, which silently validated a
    # bottle's variants and closures against a payload that named no form.
    archetype = str(profile.get("archetype") or "").lower()
    cfg = next((a for a in CONTAINER_EDITOR_ARCHETYPES
                if a["key"] == archetype), None)
    if cfg and cfg["confirmable"]:
        if profile.get("variant"):
            keys = [k for k, _ in cfg["variants"]]
            from apps.pipeline.services import learned_shapes
            if learned_shapes.kind_of(profile["variant"]) is not None:
                # [§BH71 PART 3: a lid shape this form learned is one of its variants — read only for a learned key,
                # so no other validation touches the record]
                keys += [k for k, _ in learned_shapes.variants_for(cfg["key"])]
            if str(profile["variant"]) not in keys:
                errors.append(
                    f"variant '{profile['variant']}' is not valid for "
                    f"{cfg['label']} (accepted: {', '.join(keys)})")
        if profile.get("cap_style"):
            keys = [k for k, _ in cfg["caps"]]
            if str(profile["cap_style"]) not in keys:
                errors.append(
                    f"cap_style '{profile['cap_style']}' is not valid for "
                    f"{cfg['label']} (accepted: {', '.join(keys)})")
        # §BH70(1), item 13: a measurement a form does not have is refused, never stored as verified — a compact's
        # record said a person had verified its neck ratio of 0.42, because the shape step sent a neck for every form
        # and this took it. §BH61(b), his words: "no neck proportion on a hinged case, no cap dimensions where there is
        # no cap."
        if profile.get("neck_ratio") is not None and "neck_ratio" not in cfg["proportions"]:
            errors.append(f"neck_ratio does not apply to {cfg['label']} — it has no neck")
        if not cfg["has_cap_dimensions"]:
            given = [k for k in ("cap_width_mm", "cap_depth_mm", "cap_height_mm") if profile.get(k) is not None]
            if given:
                errors.append(f"{', '.join(given)} do not apply to {cfg['label']} — it has no cap")

    # §BH70(1): THIS FORM'S ranges — the shared rows refused a 7 mm pencil and a 12 mm mascara at the server even
    # where a control could have offered them. `form_ranges` is the one reading of them, shared with the rows the
    # editor draws and the config it is served, so the slider and the verdict cannot disagree.
    ranges = form_ranges(archetype if cfg and cfg["confirmable"] else None)
    cap_rng = (CONTAINER_EDITOR_CAP_DIM_RANGE["min"],
               CONTAINER_EDITOR_CAP_DIM_RANGE["max"])
    for key in ("height_mm", "width_mm", "depth_mm", "neck_ratio",
                "cap_width_mm", "cap_depth_mm", "cap_height_mm"):
        if key not in profile or profile[key] is None:
            continue
        value = profile[key]
        if isinstance(value, bool):
            errors.append(f"{key} must be a number")
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            errors.append(f"{key} must be a number")
            continue
        if not math.isfinite(number):
            errors.append(f"{key} must be a finite number")
            continue
        lo, hi = ranges.get(key, cap_rng)
        if not (lo <= number <= hi):
            errors.append(f"{key} must be between {lo} and {hi}")
    # §BH71 PART 1: a ROUND compact's lid is a circle, so seen from above it is as long as it is wide — a round lid
    # confirmed 110 by 95 would be drawn as neither
    if archetype in ("compact", "tin") and str(profile.get("variant") or "") in ("round", "cushion") and not errors:
        w_mm, h_mm = profile.get("width_mm"), profile.get("height_mm")
        if w_mm is not None and h_mm is not None and abs(float(w_mm) - float(h_mm)) > 0.5:
            errors.append(f"a round {archetype}'s lid is a circle: seen from above it is as long as it is wide "
                          f"({float(w_mm):g} mm), not {float(h_mm):g} mm")
    return errors

_HINT_PATTERN = re.compile(
    r"\[Container type: (?P<container_type>[^;\]]*)"
    r"(?:; Product category: (?P<product_category>[^;\]]*))?"
    r"(?:; Capacity: (?P<capacity>[^;\]]*))?"
    r"(?:; Closure: (?P<closure>[^;\]]*))?\]")


def parse_container_hints(task_text: str) -> dict:
    """The B4a creation hints, recovered from the bracket block the composer
    appends to the brief. Free text stays free text — nothing here maps a
    hint onto a confirmed value. Empty dict when no block exists."""
    hints = {}
    for m in _HINT_PATTERN.finditer(task_text or ""):
        for key, value in m.groupdict().items():
            if value and value.strip():
                hints[key] = value.strip()
    return hints


#: [his test day finding 2, 2026-09-29, design 117: his brief said "Tube about 50 mm across, 180 mm tall" and the
#: shape step opened on the tube's own 130 x 35 mm — the start form's hints carry no size. A size a brief states in these
#: words is read — in mm or cm, one value per size — and opens the step as the brief's hint, never a confirmed value;
#: two different values for one size are not guessed between]
_BRIEF_SIZE_WORDS = {
    "width_mm": r"across|wide|in diameter|in width",
    "height_mm": r"tall|high|in height",
    "depth_mm": r"deep|thick|in depth",
}
_BRIEF_SIZE_RE = {key: re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(mm|cm)\s+(?:" + words + r")\b", re.IGNORECASE)
                  for key, words in _BRIEF_SIZE_WORDS.items()}


def brief_stated_sizes(task_text) -> dict:
    """``{size key: mm, …, "said": the brief's own words}`` for each size the brief states once, in words ("50 mm
    across", "18 cm tall") — or ``{}`` when it states none."""
    text = task_text if isinstance(task_text, str) else ""
    found, said = {}, []
    for key, rx in _BRIEF_SIZE_RE.items():
        matches = list(rx.finditer(text))
        values = {round(float(m.group(1)) * (10.0 if m.group(2).lower() == "cm" else 1.0), 1) for m in matches}
        if len(values) == 1:
            found[key] = values.pop()
            said.append(matches[0].group(0))
    if found:
        found["said"] = " · ".join(said)
    return found


def form_ranges(archetype=None) -> dict:
    """``{proportion: (min, max)}`` for this form: the shared rows, with the form's OWN limits where the one
    declaration gives them (§BH70(1), item 14: "Width can't go under 20 mm or depth under 10 mm, so a pencil,
    eyeliner or slim mascara can't be entered at its real size"). With no form, or a form that declares none, it is
    the shared rows exactly as they were. The ONE reading of a form's limits: the editor's rows (`proportions_for`),
    the config it is served and the server's validation all read this."""
    ranges = {p["key"]: (p["min"], p["max"]) for p in CONTAINER_EDITOR_PROPORTIONS}
    if _declared.is_known(archetype):
        ranges.update(_declared.ranges_of(archetype))
    return ranges


def proportions_for(archetype) -> list[dict]:
    """§BH61(b): only the proportions that APPLY to this form.

    His words: "no neck proportion on a hinged case, no cap dimensions where there is no cap". The flat list
    below was shown for every archetype, so a hinged case was asked for its Neck Proportion.
    [§BH70(1): and each row at THIS form's limits (`form_ranges`), so a pencil's width row reaches its 7 mm.]
    """
    keys = set(_declared.proportions_of(archetype))
    ranges = form_ranges(archetype)
    return [dict(p, min=ranges[p["key"]][0], max=ranges[p["key"]][1])
            for p in CONTAINER_EDITOR_PROPORTIONS if p["key"] in keys]


def _proposed_profile(task) -> dict | None:
    """§BH61(a): the profile THE PIPELINE PROPOSED for this task, whole, or None.

    Read from the task's own packaging output — the `container_profile/1.0` record the container target
    wrote. Never inferred, never defaulted: absent means None, and the caller says so.
    """
    try:
        output = task.packaging_outputs.order_by("-id").first()
    except Exception:                                   # noqa: BLE001 — absence is not an error here
        output = None
    spec = (getattr(output, "spec_sheet", None) or {}) if output is not None else {}
    record = spec.get("container_profile/1.0") or {}
    archetype = record.get("archetype")
    if not _declared.is_known(archetype):
        return None
    fields = record.get("fields") or {}

    def _v(name):
        f = fields.get(name)
        return f.get("value") if isinstance(f, dict) else None
    return {
        "archetype": archetype,
        "variant": _v("variant") or record.get("variant"),
        "cap_style": _v("cap_type") or record.get("cap_style"),
        # [his goal after the pitch page, B (11); the third brand-new brief, 137] each size the record proposes, read under
        # the record's own name for it (``body_height_mm``) — it was read as ``height_mm`` and so was never proposed:
        # every editor opened at the form's starting size, and a round lid's 110 x 95 was refused at its own door
        "proportions": {k: (_v("body_" + k) if k in ("height_mm", "width_mm", "depth_mm") else _v(k))
                        for k in _declared.proportions_of(archetype)},
        "source": "PIPELINE_PROPOSED",
    }


def _with_learned_shapes(archetypes: list) -> list:
    """§BH71 PART 3: the page's forms with the lid shapes each has learned (``services.learned_shapes``) among its
    variants, each with the server's own drawing of it — read per request, since learning adds them while the
    declaration, built once, cannot."""
    from apps.pipeline.services import learned_shapes
    from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
    for a in archetypes:
        if not a["confirmable"] or a["drawn_as"] != _declared.PLAN:
            continue
        for key, label in learned_shapes.variants_for(a["key"]):
            a["variants"].append({"key": key, "label": label})
            bb = build_backbone(ContainerProfile(
                archetype=a["key"], variant=key, cap_style=a["caps"][0]["key"],
                width_mm=float(a["nominal"]["width_mm"]), height_mm=float(a["nominal"]["height_mm"])))
            a["outlines"][key] = {"outline": _points(bb.silhouette, bb.width_mm, bb.height_mm),
                                  "closure": _points(bb.cap_region, bb.width_mm, bb.height_mm)}
    return archetypes


def _unknown_shape(task) -> dict | None:
    """§BH71 PART 3: the lid shape the proposal says no variant draws (``unknown_shape`` on the task's own
    ``container_profile/1.0`` record), while its variant is still unchosen; else None."""
    outputs = getattr(task, "packaging_outputs", None)          # a task not yet saved, or a stand-in, has none
    output = outputs.order_by("-id").first() if outputs is not None else None
    if output is None:
        return None
    record = (output.spec_sheet or {}).get("container_profile/1.0") or {}
    shape = record.get("unknown_shape")
    chosen = ((record.get("fields") or {}).get("variant") or {}).get("value")
    if not isinstance(shape, dict) or chosen:
        return None
    from apps.pipeline.services import learned_shapes
    said = {k: shape.get(k) for k in ("kind", "words", "source", "sentence")}
    # [§BH71 PART 3: "... and offers to learn it" — learnable when the approved concept's own trace shows it and the
    # system draws its kind; the one endpoint that learns it, and what it says when it cannot]
    said["learnable"] = learned_shapes.learnable(record) is not None
    said["learn_url"] = "/api/tasks/%d/learn_shape/" % task.id
    said["not_learnable"] = None
    if not said["learnable"]:
        said["not_learnable"] = (
            "It cannot be learned from this design: the system learns a lid only from an approved concept whose "
            "own outline shows it, and only one it draws — an oval. Choose the nearest shape yourself.")
    return said


def container_profile_editor_config(task) -> dict:
    """Server-rendered editor configuration (Confirm Profile UI-1 §19).

    One versioned contract carrying the accepted choices, bounded ranges,
    defaults, creation hints and gate eligibility — metadata only, no paths,
    no supplier assumptions, no production dimensions. The browser must not
    carry its own copy of any of it.
    """
    hints = parse_container_hints(task.task_text)
    return {
        "schema": PROFILE_EDITOR_SCHEMA,
        "gate_eligible": task.status == "awaiting_container_profile",
        "archetypes": _with_learned_shapes([
            {"key": a["key"], "label": a["label"],
             "description": a["description"],
             "confirmable": a["confirmable"],
             **({"pending_code": a["pending_code"]}
                if a.get("pending_code") else {}),
             "variants": [{"key": k, "label": lbl}
                          for k, lbl in a["variants"]],
             "caps": [{"key": k, "label": lbl} for k, lbl in a["caps"]],
             # §BH64(d): WHICH PROPORTIONS APPLY, AND HOW THE FORM IS SEEN.
             # `CONTAINER_EDITOR_ARCHETYPES` has carried per-archetype `proportions` since §BH61(c)
             # and THIS DICT DROPPED THEM, so the browser only ever received the global list and drew
             # a Neck Proportion slider for a hinged case. `proportions_for()` was written in the same
             # arc and never called by anything.
             "proportions": list(a["proportions"]),
             # [his answer after test day finding 3, (4) round: the form's own words for a size row, where it has any]
             **({"labels": dict(a["labels"])} if a.get("labels") else {}),
             # §BH61(b): "no cap dimensions where there is no cap" — the editor asks the cap's sizes by this
             "has_cap_dimensions": bool(a["has_cap_dimensions"]),
             # §BH70(1): the size limits the rows are drawn at for THIS form — the one reading, `form_ranges`
             **({"ranges": {k: {"min": lo, "max": hi} for k, (lo, hi) in form_ranges(a["key"]).items()
                            if k in a["proportions"]}}
                if a["confirmable"] else {}),
             # `drawn_as`/`nominal` are the DRAWABLE forms' only: "Other" keeps the honest `?` it has
             # always had, because it has no silhouette to draw and §BH61(c) leaves it the editor's own.
             # [his last goal before the pitch, 2026-10-16, Step 2: "real-world sizes (a blush compact is ~60–70 mm, not
             # 110)"] the form's starting size for what this brief names it holds
             **({"drawn_as": a["drawn_as"], "nominal": _declared.nominal_for(a["key"], task.task_text)}
                if a["confirmable"] else {}),
             # §BH71 PART 3: each variant's outline and closure from the one drawing, which the preview scales for a
             # form it has no hand-drawn picture of. Carried here as `proportions` had to be at §BH64(d): this dict
             # dropped it, and every new form was previewed as the empty frame.
             **({"outlines": a["outlines"]} if a["confirmable"] else {})}
            for a in CONTAINER_EDITOR_ARCHETYPES]),
        "proportions": [dict(p) for p in CONTAINER_EDITOR_PROPORTIONS],
        "proportion_note": PROPORTION_NOTE,
        # §BH61(a): NO DEFAULT ARCHETYPE. The form showed Bottle pre-selected for a palette because this key
        # said so unconditionally. It is gone. What replaces it is §BH61(a)'s other half:
        # §BH61(a): THE FORM SHOWS WHAT THE PIPELINE PROPOSED. `proposed` is the profile the pipeline actually
        # produced — pre-selected WHOLE, archetype with its own variant and closure — or None, and when it is
        # None the form says so rather than choosing. `no_proposal_reason` is the sentence it says.
        "proposed": _proposed_profile(task),
        # [§BH71 PART 3: the lid shape no variant draws, said — {kind, words, source, sentence} — while no shape is
        # chosen; the page chooses none for the person]
        "unknown_shape": _unknown_shape(task),
        # [the owner's goal of 2026-09-25, (d): the sentence in words; its code travels beside it, folded on screen]
        "no_proposal_reason": (
            None if _proposed_profile(task) else
            "No shape was proposed for this design, so nothing is chosen for you — choose its form yourself."),
        "no_proposal_code": None if _proposed_profile(task) else "CONTAINER_ARCHETYPE_UNRESOLVED",
        "initial_hints": hints,
        # [his test day finding 2: the sizes the brief states in words — the page opens on them where the record
        # gives none, within the form's own limits, labelled as the brief's]
        "brief_sizes": brief_stated_sizes(task.task_text) or None,
        "hints_status": "INITIAL_HINTS_ONLY",
        # [the owner's goal of 2026-09-25, (d): the same disclaimer in plain words]
        "preview_disclaimer": "A preview of the shape — not a production drawing",
    }


def card_for(value):
    return next((c for c in TARGET_CARDS if c["value"] == value), None)


def is_selectable(value):
    """Only an active card may be submitted from the create form."""
    return value in ACTIVE_TARGETS


# --------------------------------------------------------------------------
# Reference categories (B4b-2 prerequisite)
# --------------------------------------------------------------------------
# Section 8 requires the browser to read the limit and the accepted extension
# list from rendered context rather than carrying its own copy. Same reasoning
# as the target cards: the five labels and descriptions live here once, so the
# template, the JS and the tests cannot drift apart.
#
# The PERSISTED key stays 'color'. Only the owner-facing label says Colour.

REFERENCE_CATEGORIES = [
    {"key": "container", "label": "Container Reference",
     "description": "A bottle, jar, tube, palette, mascara component or "
                    "similar physical form used as visual guidance."},
    {"key": "logo", "label": "Brand Logo",
     "description": "An approved or provisional brand mark to consider during "
                    "concept development."},
    {"key": "label", "label": "Existing Label or Artwork",
     "description": "Existing typography, front artwork, decoration or layout "
                    "reference."},
    {"key": "inspiration", "label": "Visual Inspiration",
     "description": "Shape, material, styling, mood or competitor "
                    "inspiration."},
    {"key": "color", "label": "Colour Reference",
     "description": "Colour chips, palettes, product photography or "
                    "material-colour guidance."},
]

#: §BH69(2): the owner's inspiration picture — one box on New design for every kind of design, read into words and
#: never drawn from. It is not one of the product container's reference zones above: the "inspiration" zone there sent
#: the picture itself to the picture service, and the start page no longer draws it (START_REFERENCE_CATEGORIES).
INSPIRATION_CATEGORY = {
    "key": "inspiration_picture", "label": "Inspiration picture",
    "description": ("A screenshot or photograph you admire — read into words (layout, colours, mood, finish, type "
                    "style) before the design starts; never drawn from, and never a copy of another brand's work."),
}
#: [his final goal, 2026-10-05, B1: "An "Inside reference" picture slot beside the inspiration box (one or more
#: pictures)."] a picture of the inside print he wants — read into its pattern and style, drawn anew in vector in the
#: design's own colours, never pasted or copied; and never sent to the concept pictures
INSIDE_CATEGORY = {
    "key": "inside_reference", "label": "Inside reference",
    "description": ("A picture of the print you want inside the carton — read for its pattern and style, then drawn "
                    "anew in vector in the design's own colours; never pasted, never copied."),
}
#: [his final goal, 2026-10-05, B3: "Custom sticker: follows a sticker reference picture or the brief's words."] a picture
#: of the sticker he wants on the back — read for its shape, fill and border, drawn anew in the design's own colours
STICKER_CATEGORY = {
    "key": "sticker_reference", "label": "Sticker reference",
    "description": ("A picture of the sticker you want for the back's information — read for its shape, fill and "
                    "border, then drawn anew in the design's own colours when you choose a custom sticker."),
}
#: the product container's reference zones as the start page draws them — every one but "inspiration", whose place
#: the inspiration box takes for every kind of design
START_REFERENCE_CATEGORIES = [c for c in REFERENCE_CATEGORIES if c["key"] != "inspiration"]

REFERENCE_ONLY_NOTICE = (
    "All uploaded files are REFERENCE ONLY. They do not confirm dimensions, "
    "capacity, material, compatibility or production specifications."
)

#: B4b-3A §4 — one-line guidance shown beside each category on the Review
#: Board. Deliberately non-authoritative wording: nothing here may read as
#: confirmed geometry, approved dimensions or production artwork.
REFERENCE_REVIEW_NOTES = {
    "container": "Physical form and proportion guidance only.",
    "logo": "Brand-mark reference for concept development.",
    "label": "Typography, decoration or layout reference.",
    "inspiration": "Styling, mood, shape or material inspiration.",
    "color": "Colour relationship or material-colour guidance.",
}

#: Extensions that get a local browser preview. Everything else gets a neutral
#: file card - a PDF must never be handed to an <img>.
PREVIEWABLE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def reference_config():
    """The secure core's configuration, shaped for rendering into the page.

    Read from apps.pipeline.references so there is exactly one limit and one
    allowlist in the system.
    """
    from apps.pipeline import references as refs
    return {
        "max_file_bytes": refs.max_upload_bytes(),
        "max_file_mb": refs.max_upload_mb(),
        "allowed_extensions": refs.ALLOWED_EXTENSIONS,
        "previewable_extensions": PREVIEWABLE_EXTENSIONS,
        "categories": REFERENCE_CATEGORIES,
        "reference_only_notice": REFERENCE_ONLY_NOTICE,
        "upload_url": "/api/tasks/create/",
        "authorized_file_url_template":
            "/api/tasks/{task_id}/references/{reference_id}/",
    }
