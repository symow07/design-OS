"""§BH54(k) SLICE 2, THE DESIGN LOOP — an EXPLORATION RENDER, started from the dashboard, at no gate cost.

"See variations side by side at full size, adjust a parameter and re-render, as EXPLORATION under §BH51(a) as ratified:
ungoverned, no commit, no gate, no register entry, never claiming a state it has not earned. Trying a design must not
cost a gate — that is the whole reason this front exists." (OWNER RULING §BH54(k) 2, typed 2026-09-18.)

What a render is: the task's own composer inputs, read the way `reconstruct_container` derives them and never written
back; the product's drawing composed in this process (the M3 backbone by construction, §BH49(a)), emitted to a temporary
.ai outside every governed root, rasterised, and the PNG and ONE record written to the exploration store — which is
outside the repository, MEDIA_ROOT, both var/ trees and every source the brain reads (§BH53(c): it persists until he
discards it). Nothing else is written: no row, no MEDIA_ROOT byte, no AgentLog, no ledger line, no provider call — this
module imports no provider client and no agent. The record carries the §BH51(a) words as its one status and claims no
state; the codes the drawing carries travel beside it as information, because a picture is shown whatever they say
(§BH50(f)(5), §BH51(d)). The colours are today's (§BH54(j)), every surface-fallback literal named on the record.

A LID'S FACE, AND THE TWO KNOBS THAT TRY HIS COLOURS AND FACES ON IT. [The owner's goal of 2026-09-25, "THE UI, DESIGNED
THIS TIME", rule (d): "The library is usable WHILE designing, not a separate trip." His pick for the design page, the
answer to the UI directions of that date: C's — "pick an element and try colours and faces from a library that stays
open" (the option's words are the executor's; he chose them).] The loop draws a confirmed FACE form — a compact's lid,
drawn in plan — as well as the dropper, from exactly the inputs production derives for it
(`targets.container.face_form_inputs`: the functions `reconstruct_container` itself calls). The concept picture's
reading is taken ONLY from the design's record: reading it is a paid step on the governed path, and the loop never
pays. On a face the loop turns two knobs, each limited to the governed sets — §BH51 (c)3: "THE LIBRARIES — the 35
granted faces, the colour roles including Warm Gold, the 4,832 governed materials … usable while designing", and its
HARD STOP: "a face or colour outside the governed sets reaching a render":
  - a COLOUR on an element of the face, from the brand's own palette as the composer's colour sources read it;
  - a FACE on a role — the name's, from the granted catalogue through the role layer; the Arabic name's, only the face
    the role layer draws Arabic in (§BH33(1): "Cairo-Bold leaves every Arabic chain").
A knob changes one picture and nothing else — "Until I choose, the product keeps today's colours" (§BH54(j)): no record
of the task is written, and the picture's record names every colour and face it tried. Never a knob (§BH54(k)): the M3
heights and widths, the 31.5 mm anchor, type sizes and leading — the name's size included —, anything outside the
governed sets, a REFERENCE asset.

`explorations.py` reads and never writes; this module is the store's one writer.
"""
from __future__ import annotations

import copy
import dataclasses
import datetime
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings

from . import explorations

STATUS_CITE = "§BH51(a), OWNER_BLOCKER_CLEARANCE.md:21309-21314; ratified §BH53(c); §BH54(k) 2"
SHEET_STATUS_LINE = "EXPLORATION — NEVER VERIFIED, NEVER ACCEPTED, NEVER EVIDENCE"
DEFAULT_DPI = 200

#: refusals, by name — a render that cannot be made says why and writes nothing
RENDER_NEEDS_CONTAINER_TASK = "EXPLORATION_RENDER_NEEDS_A_CONTAINER_TASK"
RENDER_NEEDS_CONFIRMED_PROFILE = "EXPLORATION_RENDER_NEEDS_A_CONFIRMED_DROPPER_PROFILE"
RENDER_NEEDS_M3 = "EXPLORATION_RENDER_DRAWS_THE_M3_BACKBONE_ONLY"
RENDER_STORE_INSIDE_A_GOVERNED_ROOT = "EXPLORATION_STORE_INSIDE_A_GOVERNED_ROOT"
RENDER_RECORD_WOULD_CLAIM = "EXPLORATION_RECORD_WOULD_CLAIM_A_STATE"
RENDER_COMPOSE_REFUSED = "EXPLORATION_RENDER_REFUSED_BY_THE_COMPOSER"
RENDER_REFERENCE_ASSET = "EXPLORATION_REFUSED_REFERENCE_ASSET"
#: a face form's own: the concept's reading is not on the record, or the record refuses the derivation by name
RENDER_NEEDS_THE_CONCEPTS_READING = "EXPLORATION_NEEDS_THE_CONCEPTS_READING"
RENDER_FACE_FORM_REFUSED = "EXPLORATION_FACE_FORM_REFUSED_BY_ITS_RECORD"

_PICTURE = re.compile(r"^R(\d{3})$")


class RenderRefused(Exception):
    """A render that is not made. `code` is the refusal's name; str() is the sentence shown to him."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: REFUSED — {detail}" if detail else f"{code}: REFUSED")


# ---------------------------------------------------------------------------------------------------------------------
# §BH54(k) 2 — "adjust a parameter and re-render". The knobs an exploration may turn, measured on the composer
# (archive/work/bh54_design_loop_slice2/maps/loop.md): the two print zones' rectangles, the product name, the six unwritten back pieces as DRAFT
# words (§BH54(h): "I must be able to try designs with the copy unwritten" — or half-written), the four retained
# appearance fields, the raster's dpi. Never a knob: the M3 heights and widths, the 31.5 mm anchor, type sizes and
# leading, a colour (§BH54(j)), a face (his line), a reference asset. A knob changes THIS picture's inputs in memory and
# nothing else: no record of the task is written, and the record of the picture names every knob turned. [The owner's
# pick of 2026-09-25 gave a lid's face two more: a colour and a face, each from the governed sets — below.]
KNOB_REFUSED = "EXPLORATION_KNOB_REFUSED"
ZONE_KNOBS = {"front": "FRONT_PRINT_ZONE", "back": "BACK_PRINT_ZONE"}
ZONE_FIELDS = ("x", "y", "width", "height")
ZONE_RANGE = (0.0, 120.0)
COPY_PIECES = ("DESCRIPTION", "INGREDIENTS", "DIRECTIONS", "WARNINGS", "MANUFACTURER", "NET CONTENT")
COPY_LIMIT = 6000
APPEARANCE_RANGES = {"base_thickness_mm": (0.5, 10.0), "shoulder_radius_mm": (0.0, 12.0),
                     "frost_intensity": (0.0, 1.0), "translucency": (0.0, 1.0)}
DPI_RANGE = (72, 300)

# ---------------------------------------------------------------------------------------------------------------------
# A LID'S FACE — the two knobs of the owner's pick ("pick an element and try colours and faces from a library that stays
# open"), each limited to a governed set. The elements a colour can be tried on are named by the colour key the
# container composer READS for a face (apps/ire/compose_container.py `compose_container_graph` / `_concept_face`):
# `cap` fills the lid's face (a plan form's cap region) and is the window's centre and glow (the concept-front plan's
# ground); `ink` sets the name AND its Arabic line — one ink, so the Arabic name takes no colour of its own — and
# strokes the window's frame; `rule` and `ring` stroke the concept's own lines; `motif` gives every colour of the motif.
#: (form field suffix, the composer's colour key, in words, what it paints)
COLOUR_ELEMENTS = (
    ("ground", "cap", "the lid's ground", "the lid's face, and the window's centre and glow where the concept draws "
                                          "them"),
    ("name", "ink", "the name", "the name and its Arabic line — one ink — and the window's frame where the concept "
                                "draws one"),
    ("rule", "rule", "the rule", "the concept's rule between the name and the Arabic line"),
    ("ring", "ring", "the ring", "the ring traced on the lid's outline"),
    ("motif", "motif", "the motif", "the motif, in the one colour chosen for all of it"),
)
#: (form field suffix, in words) — the roles a face can be tried on
FACE_ROLES = (("name", "the name"), ("name_ar", "the Arabic name"))
#: the font role the face composer marks the Arabic line with (compose_container.py `_concept_face`: font="regular") —
#: so the layer role its Arabic words resolve through is `font_roles.roles_for_text(ARABIC_LINE_FONT, words)`
ARABIC_LINE_FONT = "regular"
#: the container sheet's own ink (compose_container.py `_INK`), for the exploration's status line on a face's sheet
STATUS_INK = "#3F2620"
COLOUR_OUTSIDE_THE_PALETTE = "EXPLORATION_COLOUR_OUTSIDE_THE_BRAND_PALETTE"
COLOUR_NOT_SEEN = "EXPLORATION_COLOUR_NOT_SEEN_ON_THIS_DESIGN"
FACE_OUTSIDE_THE_SET = "EXPLORATION_FACE_OUTSIDE_THE_GRANTED_SET"
FACE_CANNOT_SET_THE_ROLE = "EXPLORATION_FACE_CANNOT_SET_THIS_ROLE"
FACE_DID_NOT_DRAW = "EXPLORATION_FACE_DID_NOT_DRAW"
KNOBS_FOR_A_FACE_ONLY = "EXPLORATION_COLOUR_AND_FACE_KNOBS_ARE_FOR_A_LIDS_FACE"
KNOBS_FOR_THE_BOTTLE_ONLY = "EXPLORATION_GLASS_AND_BACK_WORDS_ARE_FOR_THE_BOTTLE"
DROPPER_KEEPS_ITS_OWN = ("the bottle sheet draws its own fixed colours and faces today (the dropper composer's palette, "
                         "kept as ruled at §BH50(f)(9)); a colour or a face is tried on a lid's face only")
_HEX_KNOB = re.compile(r"^#?([0-9A-Fa-f]{6})$")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _number(name: str, raw, low: float, high: float) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        raise RenderRefused(KNOB_REFUSED, f"{name} is not a number: {str(raw)[:40]!r}") from None
    if not (low <= value <= high):
        raise RenderRefused(KNOB_REFUSED, f"{name} = {value:g} is outside {low:g}–{high:g}")
    return value


def parse_knobs(post) -> dict:
    """The knobs a form POST carries — only the fields he filled; a blank field is 'as the task stands'. A value that is
    not a number, or lies outside its range, refuses the whole render by name: nothing is drawn from a half-read form.
    A colour is `colour_<element>` = #RRGGBB and a face `face_<role>` = a catalogue stem; whether each is in its governed
    set is decided against the task (`frozen_inputs`), since the set is the task's brand's and the layer's."""
    knobs: dict = {}
    for prefix in ZONE_KNOBS:
        rect = {f: _number(f"{prefix}_{f}", post.get(f"{prefix}_{f}"), *ZONE_RANGE)
                for f in ZONE_FIELDS if str(post.get(f"{prefix}_{f}", "")).strip() != ""}
        if rect:
            knobs[f"{prefix}_zone"] = rect
    name = str(post.get("product_name", "")).strip()
    if name:
        knobs["product_name"] = name[:80]
    copy = {piece: " ".join(str(post.get("copy_" + piece.lower().replace(" ", "_"), "")).split())
            for piece in COPY_PIECES}
    copy = {piece: text for piece, text in copy.items() if text}
    for piece, text in copy.items():      # §BH54(b) (k) 4: a draft is never CUT — it was, silently, at 1,200
        if len(text) > COPY_LIMIT:
            raise RenderRefused(KNOB_REFUSED, f"{piece} is {len(text)} characters, over the {COPY_LIMIT} a DRAFT may "
                                "carry; nothing is cut to fit — save the words as your copy, which has no limit")
    if copy:
        knobs["draft_copy"] = copy
    looks = {f: _number(f, post.get(f), *rng) for f, rng in APPEARANCE_RANGES.items()
             if str(post.get(f, "")).strip() != ""}
    if looks:
        knobs["appearance"] = looks
    if str(post.get("dpi", "")).strip() != "":
        knobs["dpi"] = int(_number("dpi", post.get("dpi"), *DPI_RANGE))
    colours = {}
    for element, _key, _words, _paints in COLOUR_ELEMENTS:
        raw = str(post.get("colour_" + element, "")).strip()
        if raw:
            m = _HEX_KNOB.match(raw)
            if m is None:
                raise RenderRefused(KNOB_REFUSED, "colour_%s is not a colour — a colour is written #RRGGBB: %r"
                                    % (element, raw[:40]))
            colours[element] = "#" + m.group(1).upper()
    if colours:
        knobs["colours"] = colours
    faces = {}
    for role, _words in FACE_ROLES:
        raw = str(post.get("face_" + role, "")).strip()
        if raw:
            if len(raw) > 80 or "/" in raw or "\\" in raw:
                raise RenderRefused(KNOB_REFUSED, "face_%s is not the name of a face: %r" % (role, raw[:40]))
            faces[role] = raw
    if faces:
        knobs["faces"] = faces
    return knobs


def describe(knobs: dict, before: dict) -> list[str]:
    """What a picture changed, in words, against the task's standing values — a knob set to its standing value is
    not a change and is dropped from the record."""
    lines = []
    for prefix in ZONE_KNOBS:
        rect = knobs.get(f"{prefix}_zone") or {}
        moved = {f: v for f, v in rect.items() if abs(v - float(before["zones"][prefix].get(f) or 0)) > 1e-9}
        if moved:
            was = before["zones"][prefix]
            now = {**was, **moved}
            lines.append("%s zone %g × %g at (%g, %g) → %g × %g at (%g, %g)" % (
                prefix, was["width"], was["height"], was["x"], was["y"], now["width"], now["height"], now["x"], now["y"]))
    if knobs.get("product_name") and knobs["product_name"] != before["product_name"]:
        lines.append("product name %r → %r" % (before["product_name"], knobs["product_name"]))
    for piece, text in (knobs.get("draft_copy") or {}).items():
        lines.append("%s: DRAFT words, %d characters — typed in the loop, never verified, never copy" % (piece, len(text)))
    for f, v in (knobs.get("appearance") or {}).items():
        if abs(v - float(before["appearance"].get(f) or 0)) > 1e-9:
            lines.append("%s %g → %g" % (f, before["appearance"].get(f), v))
    if knobs.get("dpi") and knobs["dpi"] != DEFAULT_DPI:
        lines.append("raster %d dpi" % knobs["dpi"])
    words = {element: element_words for element, _key, element_words, _paints in COLOUR_ELEMENTS}
    for element, hx in (knobs.get("colours") or {}).items():
        stood = (before.get("colours") or {}).get(element) or {}
        if [hx] != stood.get("hexes"):
            lines.append("%s in %s — it stood in %s" % (words[element], (before.get("palette") or {}).get(hx, hx),
                                                          stood.get("words")))
    role_words = dict(FACE_ROLES)
    for role, stem in (knobs.get("faces") or {}).items():
        stood = (before.get("faces") or {}).get(role) or {}
        if stem != stood.get("stem"):
            lines.append("%s set in %s — it stood in %s" % (role_words[role], _face_words(stem), stood.get("words")))
    return lines


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _refuse_reference_bytes(placed) -> None:
    """§BH54(b) (k) 3: "a REFERENCE asset placed in an exploration is refused by name." Decided on the BYTES — the tier
    record by sha256, never a path — and by the reference folders' identity (the /files/ door's two clauses, §BH54
    item (b)); ahead of any composing. An untiered file is the system's own output and is placed. `placed` is
    [(what it is, its path or None)]."""
    from . import history
    tiers, root = history.tiers_by_sha(), history.media_root()
    for label, path in placed:
        if not path:
            continue
        resolved = Path(path).resolve()
        folder = history.reference_folder(resolved, root)
        row = None if folder else tiers.get(history.sha256_of(resolved))
        if folder or (row and row != ["PRODUCTION"]):
            why = ("under media/%s, a REFERENCE-class directory" % folder if folder
                   else "tier %s by the tier record" % " + ".join(row))
            raise RenderRefused(RENDER_REFERENCE_ASSET, "%s %s — %s; only PRODUCTION bytes and the system's own "
                                "untiered outputs are placed" % (label, resolved.name, why))


def frozen_inputs(task, knobs: dict | None = None) -> dict:
    """The composer inputs of a container task, derived the way `reconstruct_container` derives them
    (apps/pipeline/targets/container/__init__.py) — read, never written. A confirmed dropper draws on the M3 backbone; a
    confirmed FACE form (a compact's lid) draws through `targets.container.face_form_inputs`. Anything else — and a
    dropper whose record declares a drawing source other than the M3 backbone — is refused by name."""
    from apps.ire import front_hierarchy as _front
    from apps.pipeline.targets.container import net_content as _container_net_content
    from apps.ire.container_production_method import build_production_methods
    from apps.pipeline.services import selected_concept_contract as scc
    from apps.pipeline.targets import container as C
    from apps.pipeline.targets.container import m3_backbone as m3

    if getattr(task, "design_target", "") != "product_container":
        raise RenderRefused(RENDER_NEEDS_CONTAINER_TASK, f"task {task.pk} is a {task.design_target} task")
    output = (task.packaging_outputs.exclude(spec_sheet=None).order_by("-pk").first())
    spec = (output.spec_sheet or {}) if output is not None else {}
    geometry = scc.confirmed_dropper_geometry(spec) if spec else None
    knobs = knobs or {}
    if geometry is None:
        face = _confirmed_face(spec)
        if face:
            return _face_inputs(task, output, spec, knobs)
        raise RenderRefused(RENDER_NEEDS_CONFIRMED_PROFILE,
                            f"task {task.pk} carries no HUMAN-confirmed dropper dimensions and no confirmed face form "
                            "(a compact's lid, drawn in plan) to draw from")
    if knobs.get("colours") or knobs.get("faces"):
        raise RenderRefused(KNOBS_FOR_A_FACE_ONLY, DROPPER_KEEPS_ITS_OWN)
    source = m3.drawing_source_of(spec)
    if source != m3.DRAWING_M3_FIT:
        raise RenderRefused(RENDER_NEEDS_M3, f"task {task.pk}'s record declares the drawing source {source!r}")
    standing = {"appearance": {f: geometry.get(f) for f in APPEARANCE_RANGES}}
    geometry = {**geometry, **(knobs.get("appearance") or {})}      # the four retained fields, before the derivation
    # §BH70(1): the form the RECORD names, never assumed — a record that says compact but carries a dropper's numbers
    # is refused by its form here (§BH61(b)), not drawn as the dropper those numbers describe
    _form = ((spec.get("container_profile/1.0") or {}).get("archetype"))
    _profile, geometry_m3, _derivation = m3.m3_profile_geometry(m3.ANCHOR_MM, geometry, _form)

    media = str(settings.MEDIA_ROOT)
    uploads = C._uploaded_paths(task)
    image = output.approved_image
    concept = image.image_file.path if (image is not None and image.image_file) else None
    reference = uploads.get("container") or concept
    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The house mark through its one switch (apps/ire/brand_mark.py):
    # `png` is exactly the raster picked here before, `master` the approved vector master when one is on file
    from apps.ire import brand_mark as _brand_mark
    _house = _brand_mark.house_mark(uploads)
    logo, logo_master = _house["png"], _house["master"]
    zones = [dict(z) for z in (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []]
    standing["zones"] = {prefix: {f: next((z.get(f) for z in zones if z.get("zone_type") == kind), None)
                                  for f in ZONE_FIELDS} for prefix, kind in ZONE_KNOBS.items()}
    for prefix, kind in ZONE_KNOBS.items():                         # a copy of the record's zone, moved in memory
        for z in zones:
            if z.get("zone_type") == kind:
                z.update(knobs.get(f"{prefix}_zone") or {})
    methods = build_production_methods(zones, spec.get("container_profile/1.0") or {})
    back_sections, _content_codes = C._back_sections_from_record(task.product)
    draft = knobs.get("draft_copy") or {}
    back_sections = [dict(s, text=draft[s["heading"]]) if s.get("heading") in draft else s for s in back_sections]
    standing["product_name"] = spec.get("product_name", "")
    priors = []
    rejected = sorted(k for k in spec if k.startswith("container_reconstruction_rejected"))
    for i, key in enumerate(rejected):
        png = ((spec.get(key) or {}).get("rejected_output") or {}).get("design_preview")
        path = os.path.join(media, png) if png else ""
        if path and os.path.exists(path):
            priors.append((f"REJECTED r{i + 1}" if i == 0 else f"CORR-{i} (rejected)", path))
    _refuse_reference_bytes([("the reference image", reference), ("the logo", logo),
                             *[("the prior output %s" % name, prior) for name, prior in priors]])
    return {"form": "dropper", "task": task.pk, "output": output.pk, "geometry": geometry_m3, "standing": standing,
            "profile_record": spec.get("container_profile/1.0") or {},
            "kwargs": dict(zones=zones, reference_path=reference, logo_path=logo,
                           product_name=knobs.get("product_name") or spec.get("product_name", ""),
                           sku=spec.get("sku", ""),
                           back_sections=back_sections, prior_outputs=priors, methods_record=methods,
                           drawing_source=source, backbone=None,
                           # §BH67(c)2: the same record the production sheet reads — or nothing
                           descriptor=_front.descriptor_for(spec, task.product),
                           net_content=_container_net_content(task),    # [his answers on 122, (2)] his size
                           # [the owner's second answer of 2026-09-25: only when a master is on file, so the inputs
                           # of every exploration drawn without one hash as they always did]
                           **_brand_mark.master_kwargs(logo_master))}


# ---------------------------------------------------------------------------------------------------------------------
# A LID'S FACE
# ---------------------------------------------------------------------------------------------------------------------

def _confirmed_face(spec: dict) -> str | None:
    """The archetype when the record holds a CONFIRMED face form — a form whose declared primary surface is its face
    (`archetypes.is_face`), its profile confirmed at the gate (the confirmation view writes `confirmation_state`
    "CONFIRMED" and `container_confirmation` together, apps/pipeline/views.py) — else None."""
    from apps.pipeline.targets.container import archetypes as A
    record = spec.get("container_profile/1.0") or {}
    archetype = record.get("archetype")
    if not (A.is_known(archetype) and A.is_face(archetype)):
        return None
    if record.get("confirmation_state") != "CONFIRMED" or not spec.get("container_confirmation"):
        return None
    return archetype


def confirmed_profile(spec: dict) -> dict:
    """The confirmed profile exactly as the governed resume hands it on — the retry door's `_confirmed_clean`
    (apps/pipeline/views.py): the confirmed record's archetype and variant, the cap from its `cap_type` field, the body's
    height, width and depth, the neck ratio; nothing it does not hold."""
    record = spec.get("container_profile/1.0") or {}
    fields = record.get("fields") or {}

    def value(name):
        return (fields.get(name) or {}).get("value")
    return {k: v for k, v in {
        "archetype": record.get("archetype"), "variant": record.get("variant") or None,
        "cap_style": value("cap_type"), "height_mm": value("body_height_mm"), "width_mm": value("body_width_mm"),
        "depth_mm": value("body_depth_mm"), "neck_ratio": value("neck_ratio")}.items() if v is not None}


def _reading_on_record(task, spec, **kw) -> dict:
    """The concept picture's reading EXACTLY as the governed path cached it on the design's record
    (`concept_layout.cached`, the one cache check `cached_or_read` makes) — and NEVER a read: this reader imports no
    provider client, calls none, and refuses by name when the record holds no reading of this picture."""
    from apps.pipeline.services import concept_layout
    held, why = concept_layout.cached(spec, kw.get("image_path"))
    if held is None:
        raise RenderRefused(RENDER_NEEDS_THE_CONCEPTS_READING, (
            "the design's concept picture has not been read for this drawing yet (%s). Reading it is a paid step on "
            "the governed path — a vision call, its cost on the task's ledger — and the loop never pays; it is made "
            "when the design is reconstructed on the governed path" % why))
    return held


def brand_palette(task) -> list[dict]:
    """The colours a colour knob may take: the brand's palette exactly as the composer's colour sources read it
    (`targets.container.brand_palette_systems`, the reading `_brand_palette` flattens) — one row per colour, by hex, with
    its name, system, role and usage, and the systems that hold it too. The Metallic swatch — Rose Gold, "Metallic 10122
    C", which carries no hex — is offered at the colour production depicts it in (`colour_sources.metallic_hex`: the
    brand's own Metallic hex, else the flat stand-in)."""
    from apps.pipeline.targets import container as C
    from apps.pipeline.targets.container import colour_sources as CS
    systems = C.brand_palette_systems(task)
    metal_hex, metal_words = CS.metallic_hex([sw for _s, palette in systems for sw in palette], C._DEFAULT_CAP_HEX)
    rows: dict = {}
    for system, palette in systems:
        for sw in palette:
            if not isinstance(sw, dict) or not sw.get("name"):
                continue
            raw = str(sw.get("hex") or "")
            if _HEX.match(raw):
                hx, depicted = raw.upper(), None
            elif sw.get("role") == CS.METALLIC_ROLE:
                hx, depicted = metal_hex, metal_words
            else:
                continue
            row = rows.get(hx)
            if row is None:
                rows[hx] = {"hex": hx, "name": sw["name"], "system": system.name, "role": sw.get("role"),
                            "usage": sw.get("usage"), "also_in": [], "depicted": depicted,
                            "words": "%s %s (%s, %s)" % (sw["name"], hx, system.name, sw.get("role"))}
            elif system.name != row["system"] and system.name not in row["also_in"]:
                row["also_in"].append(system.name)
    return list(rows.values())


def _colour_words(hexes: list, palette: dict) -> str:
    return ", ".join(palette.get(h, h) for h in hexes) if hexes else "no colour of its own"


def _face_words(stem: str) -> str:
    from apps.ire import font_roles as FR
    entry = FR.catalogue().get(stem) or {}
    return "%s (%s)" % (entry.get("family") or stem, stem)


def _name_lead(stem: str) -> dict:
    """The face tried on the name, as the lead the composer marks the name with (`font_roles.CONCEPT_NAME`) and the
    role layer verifies and embeds — the layer, never a path handed to the composer. Refused by name when the stem is
    not a granted face, cannot set a Latin name, or does not verify for the name's role today."""
    from apps.ire import font_roles as FR
    from apps.ire.concept_typeface import LEADS
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    entry = FR.catalogue().get(stem)
    if entry is None:
        raise RenderRefused(FACE_OUTSIDE_THE_SET, (
            "%r is not a face of the granted set (the 35 brand faces and the Noto trio, each re-hashed against its "
            "record); no face outside the set reaches a picture" % stem))
    if not entry.get("latin"):
        raise RenderRefused(FACE_CANNOT_SET_THE_ROLE, "%s carries no Latin letters, so it cannot set the name"
                            % _face_words(stem))
    record = FR.verify_candidate("display", stem) or {}
    if record.get("verification") != VERIFIED_FOR_PRODUCTION:
        raise RenderRefused(FACE_CANNOT_SET_THE_ROLE, (
            "the role layer does not verify %s for the name today (%s), so it is not drawn"
            % (_face_words(stem), record.get("verification"))))
    return {"verdict": LEADS, "stem": stem, "family": entry.get("family"), "element": "name",
            "words": "the face the owner tried on the name in the design loop",
            "why": "tried in the design loop — a granted file the role layer verifies; never the concept's words and "
                   "never a record of the task"}


def _arabic_face(stem: str, standing: dict | None) -> None:
    """The face tried on the Arabic name: only the face the role layer draws the Arabic line in today. §BH33(1): "Cairo-
    Bold leaves every Arabic chain and keeps only its Latin display role" — measured by the layer: it has the letters
    and lacks the shapes this emitter's Arabic shaping draws, so a line set in it would lose letters without a sign."""
    from apps.ire import font_roles as FR
    entry = FR.catalogue().get(stem)
    if entry is None:
        raise RenderRefused(FACE_OUTSIDE_THE_SET, (
            "%r is not a face of the granted set (the 35 brand faces and the Noto trio, each re-hashed against its "
            "record); no face outside the set reaches a picture" % stem))
    if standing is None:
        raise RenderRefused(FACE_CANNOT_SET_THE_ROLE, "this design draws no Arabic name, so no face can be tried on it")
    if stem == standing["stem"]:
        return
    if entry.get("arabic_letters") and entry.get("arabic_forms_missing"):
        why = ("it has the Arabic letters but lacks %d of the letter shapes this emitter's Arabic shaping draws, so the "
               "line would lose letters without a sign (the role layer's own measurement; §BH33(1): \"Cairo-Bold "
               "leaves every Arabic chain\")" % entry["arabic_forms_missing"])
    elif entry.get("arabic_letters") and entry.get("arabic_marks_missing"):
        why = "it lacks %d of the Arabic marks the line keeps (§BH33(3))" % entry["arabic_marks_missing"]
    elif not entry.get("arabic"):
        why = "it carries no Arabic letters"
    else:
        why = "the loop draws the Arabic line only in the face the role layer resolves for it; another is not built"
    raise RenderRefused(FACE_CANNOT_SET_THE_ROLE, "%s cannot set the Arabic name: %s. The Arabic name prints in %s"
                        % (_face_words(stem), why, standing["words"]))


def _standing_faces(typeface: dict | None, name_ar) -> dict:
    """The faces the name and the Arabic name print in as the design stands — the role layer's own resolution: the
    concept's lead when it names a granted face that verifies, else the display chain; the Arabic line's chain."""
    from apps.ire import font_roles as FR
    from apps.ire.concept_typeface import LEADS
    lead = (typeface or {}).get("name") or {}
    if lead.get("verdict") == LEADS and lead.get("stem"):
        drawn = FR.resolve_role_with(lead["stem"], "display")
        how = ("the concept's own face" if drawn.get("stem") == lead["stem"]
               else "the display chain — the concept's own face did not verify")
    else:
        drawn = FR.resolve_role("display")
        how = "the display chain — the concept names no granted face that can lead"
    faces = {"name": {"stem": drawn.get("stem"), "words": _face_words(drawn.get("stem") or ""), "how": how}}
    if name_ar:
        roles = sorted(FR.roles_for_text(ARABIC_LINE_FONT, name_ar))       # never empty: a run needs one role
        role = next((r for r in roles if r.startswith("arabic-")), roles[0])
        arabic = FR.resolve_role(role)
        faces["name_ar"] = {"stem": arabic.get("stem"), "words": _face_words(arabic.get("stem") or ""),
                            "how": "the role layer's %s chain" % role, "role": role}
    return faces


def _derive(task, output, confirmed: dict, **knobs) -> dict:
    """`targets.container.face_form_inputs` with the reader that never pays — a record that refuses the derivation
    (an unverifiable variation, an unresolvable form) refused by name, never a server error on a page."""
    from apps.pipeline.targets import container as C
    try:
        return C.face_form_inputs(task, output, confirmed, read_layout=_reading_on_record, **knobs)
    except RenderRefused:
        raise
    except Exception as exc:  # noqa: BLE001 — a record that refuses the derivation is said by name, never a 500
        raise RenderRefused(RENDER_FACE_FORM_REFUSED, "%s — %s" % (type(exc).__name__, str(exc)[:400])) from exc


def _colours_of(derived: dict, named: dict) -> dict:
    """{element: {hexes, words, source}} — the colour each element of the face prints in, and the record it came
    from, in words."""
    out = {}
    for element, key, _words, _paints in COLOUR_ELEMENTS:
        hx, source = derived["colors"].get(key), derived["sources"].get(key)
        hexes = list(hx) if isinstance(hx, list) else ([hx] if hx else [])
        out[element] = {"hexes": hexes, "words": _colour_words(hexes, named),
                        "source": source if isinstance(source, str) else "; ".join(source or [])}
    return out


def _face_inputs(task, output, spec: dict, knobs: dict) -> dict:
    """A confirmed face form's inputs — `face_form_inputs`, the derivation `reconstruct_container` calls — derived as
    the design stands and, when a knob changes the derivation, again with the knobs turned in memory, every one from its
    governed set or refused by name. Whatever differs between the two is named: what he turned, and what followed."""
    if knobs.get("appearance") or knobs.get("draft_copy"):
        raise RenderRefused(KNOBS_FOR_THE_BOTTLE_ONLY, (
            "a lid's face has no glass and draws no back-panel words: the four glass fields and the draft back words "
            "are tried on the bottle"))
    zones = [dict(z) for z in (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []]
    standing = {"form": "face", "product_name": spec.get("product_name", ""),
                "zones": {prefix: {f: next((z.get(f) for z in zones if z.get("zone_type") == kind), None)
                                   for f in ZONE_FIELDS} for prefix, kind in ZONE_KNOBS.items()}}
    moved = {}
    for prefix, kind in ZONE_KNOBS.items():
        rect = knobs.get(f"{prefix}_zone")
        if rect:
            if not any(z.get("zone_type") == kind for z in zones):
                raise RenderRefused(KNOB_REFUSED, "this design has no %s zone to move" % prefix)
            moved[kind] = dict(rect)
    palette = brand_palette(task)
    named = {row["hex"]: row["words"] for row in palette}
    systems = sorted({row["system"] for row in palette} | {s for row in palette for s in row["also_in"]})
    keys = {element: key for element, key, _words, _paints in COLOUR_ELEMENTS}
    colours = {}
    for element, hx in (knobs.get("colours") or {}).items():
        if hx not in named:
            raise RenderRefused(COLOUR_OUTSIDE_THE_PALETTE, (
                "%s is not a colour of the brand's palette (%s); a colour is tried only from the palette's own "
                "colours — no colour outside the governed set reaches a picture" % (
                    hx, ", ".join(systems) if systems else "this brand has no palette on record")))
        colours[keys[element]] = (hx, "the owner's colour, tried in the design loop — %s; never a record of the "
                                      "task: the product keeps today's colours until he chooses (§BH54(j))"
                                      % named[hx])
    faces = knobs.get("faces") or {}
    name_lead = _name_lead(faces["name"]) if "name" in faces else None
    confirmed = confirmed_profile(spec)
    plain = _derive(task, output, confirmed)                                      # the design as it stands
    turned = dict(colours=colours or None, name_face=name_lead, moved_zones=moved or None,
                  product_name=knobs.get("product_name"))
    derived = _derive(task, output, confirmed, **turned) if any(turned.values()) else plain
    compose = derived["compose"]
    _refuse_reference_bytes([("the reference image", compose.get("reference_path")),
                             ("the logo", compose.get("logo_path"))])
    name_ar = ((plain["concept_front"].get("face") or {}).get("name_ar"))
    standing["faces"] = _standing_faces(plain["typeface"], name_ar)
    if "name_ar" in faces:
        _arabic_face(faces["name_ar"], standing["faces"].get("name_ar"))
    standing["palette"] = named
    standing["colours"] = _colours_of(plain, named)
    drawn = _colours_of(derived, named)
    tried = [{"element": element, "key": keys[element], "colour": named[hx],
              "stood": standing["colours"][element]["words"]}
             for element, hx in (knobs.get("colours") or {}).items()
             if [hx] != standing["colours"][element]["hexes"]]
    followed = [{"element": element, "colour": row["words"], "stood": standing["colours"][element]["words"],
                 "why": "derived as production derives it from the colours turned — a motif is never printed in "
                        "its own ground (colour_sources.motif_colours)"}
                for element, row in drawn.items()
                if element not in (knobs.get("colours") or {}) and row["hexes"] != standing["colours"][element]["hexes"]]
    tried_faces = []
    if name_lead is not None and name_lead["stem"] != standing["faces"]["name"]["stem"]:
        tried_faces.append({"role": "the name", "stem": name_lead["stem"], "face": _face_words(name_lead["stem"]),
                            "stood": standing["faces"]["name"]["words"]})
    return {"form": "face", "task": task.pk, "output": output.pk, "geometry": None, "standing": standing,
            "profile_record": derived["profile_record"], "kwargs": compose, "derived": derived,
            "tried": {"colours": tried, "followed": followed, "faces": tried_faces}}


def _product_nodes(doc):
    """(node, under an ink finish) for every node of the product's own artwork — the top-level group the composer marks
    role "product" — a node under an ink finish when it or an enclosing group carries one (the emitter paints such a node
    in the finish's depiction on the picture, `pdf_ai._draw_ink_finished`)."""
    from apps.ire.container_finishes import INK_FINISHES
    from apps.ire.graph import Group

    def walk(node, inked):
        here = inked or any(f.kind in INK_FINISHES for f in (getattr(node, "finishes", None) or []))
        yield node, here
        if isinstance(node, Group):
            for child in node.children:
                yield from walk(child, here)
    for top in getattr(doc.root, "children", ()):
        if isinstance(top, Group) and top.role == "product":
            yield from walk(top, False)


def _painted_by(doc, element: str) -> list:
    """[(node, under ink)] for the nodes the colour key of ``element`` paints on the drawn face."""
    from apps.ire.graph import Group, TextRun
    nodes = list(_product_nodes(doc))
    if element == "ground":
        return [(n, ink) for n, ink in nodes if (n.name or "") == "cap"]
    if element == "name":
        return [(n, ink) for n, ink in nodes if (isinstance(n, TextRun) and (n.name or "").startswith("product-name"))
                or (n.name or "") == "window-frame"]
    if element == "rule":
        return [(n, ink) for n, ink in nodes if (n.name or "").endswith("rule-front-single")]
    if element == "ring":
        return [(n, ink) for n, ink in nodes if (n.name or "") == "frame-ring"]
    motif_groups = [n for n, _ink in nodes if isinstance(n, Group) and re.match(r"^motif-", n.name or "")]
    leaves = {id(leaf) for g in motif_groups for leaf, _i in _leaves_of(g)}
    return [(n, ink) for n, ink in nodes if id(n) in leaves]


def _leaves_of(group):
    from apps.ire.graph import Group
    for child in group.children:
        if isinstance(child, Group):
            yield from _leaves_of(child)
        else:
            yield child, False


def _checked_face(doc, inputs: dict) -> list[str]:
    """After the face is drawn and its finishes applied: every face tried is the face that draws, and every colour
    tried shows somewhere on the picture — else refused by name, before a byte is written. Returns what the record says
    of a colour that shows only in part."""
    from apps.ire import font_roles as FR
    notes = []
    for face in inputs["tried"]["faces"]:
        drew = (FR.resolve_document(doc)["resolutions"].get(FR.CONCEPT_NAME) or {}).get("stem")
        if drew != face["stem"]:
            raise RenderRefused(FACE_DID_NOT_DRAW, "%s was tried on the name and the role layer drew %s instead"
                                % (face["face"], _face_words(drew) if drew else "the display chain's face"))
    words = {element: element_words for element, _key, element_words, _paints in COLOUR_ELEMENTS}
    for row in inputs["tried"]["colours"]:
        painted = _painted_by(doc, row["element"])
        if not painted:
            raise RenderRefused(COLOUR_NOT_SEEN, "this design draws no %s, so a colour on it cannot be seen"
                                % words[row["element"]].replace("the ", "", 1))
        foiled = [n for n, inked in painted if inked]
        if all(inked for _n, inked in painted):
            raise RenderRefused(COLOUR_NOT_SEEN, (
                "%s prints in the concept's own foil on this design — the picture paints it in the metal — so a colour "
                "on it cannot be seen; a finish is not a knob" % words[row["element"]]))
        if foiled:
            notes.append("%s: %d of its %d drawn parts print in the concept's foil and keep the metal"
                         % (words[row["element"]], len(foiled), len(painted)))
    return notes


def standing_values(task) -> dict:
    """The values the loop page shows beside each knob: what the task's record carries today."""
    return frozen_inputs(task)["standing"]


def explorable(task) -> dict:
    """What the task's history page offers: {"form": True}, or {"form": False, "reason": <the refusal, by name>} for a
    container task no exploration can be drawn of, or {} for any other task (the page then says nothing)."""
    if getattr(task, "design_target", "") != "product_container":
        return {}
    try:
        frozen_inputs(task)
    except RenderRefused as exc:
        return {"form": False, "reason": str(exc)}
    return {"form": True}


def knob_offer(task) -> dict:
    """FOR THE DESIGN PAGE, READ-ONLY: what can be tried on this design. On a lid's face: the elements a colour can be
    tried on — each with its colour as the design stands and the record it came from, in words, and whether a colour
    on it shows on this design — the palette to offer, the roles a face can be tried on with their standing faces, and
    the granted faces to offer, each with its specimen. Otherwise the refusal, in words. Composes the standing face in
    memory to say exactly what is drawn and what prints in a foil; writes nothing, spends nothing."""
    from urllib.parse import quote

    from apps.ire import font_roles as FR
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    from apps.pipeline.targets import container as C
    empty = {"elements": [], "palette": [], "roles": [], "faces": []}
    try:
        inputs = frozen_inputs(task)
    except RenderRefused as exc:
        return dict(empty, form=None, refused=exc.code, why=str(exc))
    if inputs["form"] != "face":
        return dict(empty, form="dropper", refused=KNOBS_FOR_A_FACE_ONLY,
                    why="%s: REFUSED — %s" % (KNOBS_FOR_A_FACE_ONLY, DROPPER_KEEPS_ITS_OWN))
    try:
        doc, _finish = C.draw_face_form(inputs["derived"])
    except Exception as exc:  # noqa: BLE001 — a page is told why by name, never a server error
        return dict(empty, form=None, refused=RENDER_COMPOSE_REFUSED,
                    why="%s: REFUSED — %s — %s" % (RENDER_COMPOSE_REFUSED, type(exc).__name__, str(exc)[:300]))
    standing = inputs["standing"]
    elements = []
    for element, _key, words, paints in COLOUR_ELEMENTS:
        painted = _painted_by(doc, element)
        shown = [n for n, inked in painted if not inked]
        why_not = (None if shown else
                   "this design draws no %s" % words.replace("the ", "", 1) if not painted else
                   "it prints in the concept's own foil on this design, so a colour on it cannot be seen")
        elements.append({"element": element, "field": "colour_" + element, "words": words, "paints": paints,
                         "standing": standing["colours"][element], "can_take_a_colour": not why_not,
                         "why_not": why_not})
    catalogue = FR.catalogue()
    name_faces = [stem for stem in sorted(catalogue, key=lambda s: ((catalogue[s].get("family") or s).lower(), s))
                  if catalogue[stem].get("latin")
                  and (FR.verify_candidate("display", stem) or {}).get("verification") == VERIFIED_FOR_PRODUCTION]
    roles = [{"role": "name", "field": "face_name", "words": "the name", "standing": standing["faces"]["name"],
              "offer": name_faces, "not_offered": []}]
    arabic = standing["faces"].get("name_ar")
    if arabic is not None:
        others = [stem for stem, e in sorted(catalogue.items()) if stem != arabic["stem"]
                  and (e.get("arabic") or e.get("arabic_letters"))]
        not_offered, can = [], []
        for stem in others:
            try:
                _arabic_face(stem, arabic)
            except RenderRefused as exc:
                not_offered.append({"stem": stem, "face": _face_words(stem), "why": str(exc)})
            else:                           # a face that CAN set the Arabic name is offered, never silently dropped
                can.append(stem)
        roles.append({"role": "name_ar", "field": "face_name_ar", "words": "the Arabic name", "standing": arabic,
                      "offer": ([arabic["stem"]] if arabic.get("stem") else []) + can, "not_offered": not_offered})
    offered = {stem: [r["role"] for r in roles if stem in r["offer"]] for r in roles for stem in r["offer"]}
    # the specimen route (apps/dashboard/urls.py, `face_specimen`) serves every catalogue stem; its path is written here
    # as this module writes the pictures' — never through `reverse`, which loads the project's whole URL map, and with
    # it the pipeline's error module, which imports the provider SDKs for their exception classes
    faces = [{"family": catalogue[stem].get("family") or stem, "stem": stem, "roles": offered[stem],
              "specimen": "/dashboard/brand/faces/%s.png" % quote(stem, safe="")} for stem in offered]
    return {"form": "face", "elements": elements, "palette": brand_palette(task), "roles": roles, "faces": faces}


def inputs_sha256(inputs: dict) -> str:
    """The identity of what a picture was drawn from: the numbers and words as canonical JSON, every input file by the
    sha256 of its bytes — never by its path, which is the machine's and not the design's."""
    if inputs.get("form") == "face":
        return _face_inputs_sha256(inputs)
    kw = dict(inputs["kwargs"])
    files = {"reference": kw.pop("reference_path", None), "logo": kw.pop("logo_path", None)}
    priors = kw.pop("prior_outputs", []) or []
    master = kw.pop("logo_master", None)
    body = {"geometry": inputs["geometry"], "kwargs": kw,
            "files": {k: (_sha256_file(v) if v else None) for k, v in files.items()},
            "prior_outputs": [(label, _sha256_file(path)) for label, path in priors]}
    if master is not None:
        # [the owner's second answer of 2026-09-25: the approved vector master by the sha256 of its bytes]
        body["logo_master_sha256"] = master.sha256
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _face_inputs_sha256(inputs: dict) -> str:
    """A face's identity: its confirmed profile (the backbone is drawn from it), the composer's whole call and the
    finishes' inputs as canonical JSON — the concept's reading by its picture's sha256, never its path — and every input
    file by the sha256 of its bytes."""
    derived = inputs["derived"]
    kw = dict(inputs["kwargs"])
    files = {"reference": kw.pop("reference_path", None), "logo": kw.pop("logo_path", None)}
    master = kw.pop("logo_master", None)
    front = copy.deepcopy(kw.pop("concept_front", None) or {})
    image = (((front.get("face") or {}).get("vision_layout")) or {}).get("image")
    if isinstance(image, dict):
        image.pop("path", None)
    body = {"form": "face", "profile": dataclasses.asdict(derived["profile"]), "kwargs": kw, "concept_front": front,
            "finish": derived["finish"], "files": {k: (_sha256_file(v) if v else None) for k, v in files.items()}}
    if master is not None:
        body["logo_master_sha256"] = master.sha256
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def study_slug(task_pk: int, day: datetime.date | None = None) -> str:
    return "t%d-loop-%s" % (task_pk, (day or datetime.datetime.now(datetime.timezone.utc).date()).isoformat())


def _next_picture(study_dir: Path) -> str:
    taken = [int(m.group(1)) for m in (_PICTURE.match(p.stem) for p in study_dir.glob("R*.json")) if m]
    return "R%03d" % (max(taken, default=0) + 1)


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


NOTHING_CHANGED = "nothing — the task's inputs as they stand"


def _stamp_status(doc) -> None:
    """The exploration's status on the face's sheet itself, as the bottle sheet prints it (its `revision_status`): a
    sheet annotation above the title, never on the product."""
    from apps.ire.graph import SHEET_ANNOTATION, Color, PrintScope, TextRun
    doc.root.children.append(TextRun(name="exploration-status", text=SHEET_STATUS_LINE, x=6.0, y=6.0, size_pt=6.0,
                                     color=Color.from_hex(STATUS_INK), font="bold", align="left",
                                     print_scope=PrintScope(kind=SHEET_ANNOTATION)))


def render(task, user, *, knobs: dict | None = None) -> tuple[str, str]:
    """One exploration picture of `task`. Returns (study slug, picture id). Writes the store and nothing else."""
    import fitz                                                   # PyMuPDF: rasterises to bytes, no file

    from apps.ire import colour_roles as CR
    from apps.ire.compose_dropper import compose_dropper_sheet
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.targets import container as C

    if not explorations.store_is_outside_governed_roots():
        raise RenderRefused(RENDER_STORE_INSIDE_A_GOVERNED_ROOT, str(explorations.store_root()))
    from apps.pipeline.services import container_contract as cc

    knobs = knobs or {}
    inputs = frozen_inputs(task, knobs)
    face = inputs["form"] == "face"
    changed = describe(knobs, inputs["standing"])
    if face:
        words = {element: element_words for element, _key, element_words, _paints in COLOUR_ELEMENTS}
        changed += ["%s followed, derived as production derives it (a motif is never printed in its own ground): %s "
                    "— it stood in %s" % (words[row["element"]], row["colour"], row["stood"])
                    for row in inputs["tried"]["followed"]]
    dpi = int(knobs.get("dpi") or DEFAULT_DPI)
    moved = [z for z in inputs["kwargs"]["zones"] if z.get("zone_type") in ZONE_KNOBS.values()
             and any(f"{p}_zone" in knobs for p, kind in ZONE_KNOBS.items() if kind == z.get("zone_type"))]
    contract = [problem for z in moved for problem in cc.validate_zone(z, inputs["profile_record"])]
    finish, partly = {}, []
    try:
        if face:
            doc, finish = C.draw_face_form(inputs["derived"])
            partly = _checked_face(doc, inputs)
            _stamp_status(doc)
        else:
            doc = compose_dropper_sheet(inputs["geometry"], revision_status=SHEET_STATUS_LINE, **inputs["kwargs"])
        usage: dict = {}
        with tempfile.TemporaryDirectory(prefix="bbrose_exploration_") as tmp:     # outside every governed root
            ai = emit_pdf_ai(doc, os.path.join(tmp, "render.ai"), usage_out=usage)
            with fitz.open(ai) as pdf:
                pix = pdf[0].get_pixmap(dpi=dpi, alpha=False)
                png, size = pix.tobytes("png"), [pix.width, pix.height]
    except RenderRefused:
        raise
    except (ValueError, OSError, RuntimeError) as exc:
        # the composer's and the emitter's own refusals, by their names: a REFERENCE asset at the placement seam
        # (PlacementRefused, ahead of every byte), provisional copy, a face outside the governed set, a missing file
        raise RenderRefused(RENDER_COMPOSE_REFUSED, "%s — %s" % (type(exc).__name__, str(exc)[:400])) from exc

    fit = doc.metadata.get("container_front_copy_fit/1.1") or {}
    back = doc.metadata.get("container_back_panel/1.0") or {}
    rows = (usage.get(CR.USAGE_SCHEMA) or {}).get("rows") or []
    now = datetime.datetime.now(datetime.timezone.utc)
    slug = study_slug(task.pk, now.date())
    study_dir = explorations.store_root() / slug
    study_dir.mkdir(parents=True, exist_ok=True)
    picture = _next_picture(study_dir)
    record = {
        "status": explorations.EXPLORATION_STATUS,
        "status_words": STATUS_CITE,
        "study": slug,
        "picture": picture,
        "what_changed": "; ".join(changed) or NOTHING_CHANGED,
        "knobs": knobs,
        "draft_copy_sections": sorted((knobs.get("draft_copy") or {})),
        "zone_contract_findings": contract,     # information: what the confirmed contract says of a zone moved here
        "task": task.pk,
        "output": inputs["output"],
        "inputs_sha256": inputs_sha256(inputs),
        "zones_drawn": [{k: z.get(k) for k in ("zone_id", "x", "y", "width", "height", "safe_margin_mm")}
                        for z in inputs["kwargs"]["zones"]],
        "codes_on_the_drawing": {"front_copy": list(fit.get("codes") or []), "back_panel": list(back.get("codes") or []),
                                 "note": "information, never a verdict: an exploration is shown whatever its drawing "
                                         "carries, and readiness is computed only on the governed path"},
        "fallback_literals_still_drawn": sorted({r.get("hex") for r in rows if r.get("source") == "SURFACE_FALLBACK"
                                                 and r.get("hex")}),
        "colours": "today's (§BH54(j)) — no colour is chosen here",
        "sheet_status_line": SHEET_STATUS_LINE,
        "sheet_texts_fixed_in_the_module": ["sheet-title", "panel-label-hero", "confirmed-dims"],
        "picture_file": picture + ".png",
        "picture_sha256": hashlib.sha256(png).hexdigest(),
        "picture_px": size,
        "dpi": dpi,
        "made_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "made_by": "%s, from the dashboard — apps/dashboard/exploration_render.py" % user.get_username(),
    }
    if face:
        tried = inputs["tried"]
        record.update({
            "form": "a lid's face, drawn in plan — the face form's inputs as reconstruct_container derives them "
                    "(targets.container.face_form_inputs), the concept's reading from the design's record",
            "codes_on_the_drawing": dict(record["codes_on_the_drawing"], finishes=list(finish.get("codes") or [])),
            "colours": ("tried in the loop for this picture alone — the product keeps today's colours until he "
                        "chooses (§BH54(j))" if tried["colours"] else record["colours"]),
            "colours_tried": tried["colours"],
            "colours_that_followed": tried["followed"],
            "colours_seen_in_part": partly,
            "faces_tried": tried["faces"],
            "faces_as_they_stand": {role: row["words"] for role, row in inputs["standing"]["faces"].items()},
            # the faces the emitted file itself embeds, read back from it by the emitter's own usage counter
            "faces_embedded": sorted((usage.get("reconciliation") or {}).get("embedded") or []),
            "sheet_texts_fixed_in_the_module": ["sheet-title", "reference-label", "sku", "swatch-label-*",
                                                "exploration-status"],
        })
    claim = explorations.claims(record)
    if claim:                                                       # never write a record the reader would refuse
        raise RenderRefused(RENDER_RECORD_WOULD_CLAIM, claim)
    _write(study_dir / (picture + ".png"), png)
    _write(study_dir / (picture + ".json"), json.dumps(record, indent=1, ensure_ascii=False).encode())
    index_path = study_dir / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        index = {"status": explorations.EXPLORATION_STATUS, "status_words": STATUS_CITE, "study": slug,
                 "task": task.pk, "made_at": record["made_at"], "pictures": []}
    index["pictures"].append({"picture": picture, "record": picture + ".json", "file": picture + ".png",
                              "sha256": record["picture_sha256"]})
    index["updated_at"] = record["made_at"]
    _write(index_path, json.dumps(index, indent=1, ensure_ascii=False).encode())
    return slug, picture


def picture_codes(record: dict) -> list[str]:
    """Every code a picture's record carries, as the page shows them: the drawing's codes (the front copy, the back
    panel, a face's finishes) and what the confirmed contract says of a zone moved here."""
    codes = []
    for key, value in (record.get("codes_on_the_drawing") or {}).items():
        if key != "note" and isinstance(value, list):
            codes.extend(value)
    return codes + list(record.get("zone_contract_findings") or [])
