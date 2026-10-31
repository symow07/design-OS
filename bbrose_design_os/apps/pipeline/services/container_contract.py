"""Product Container profile + decoration-zone contract (Phase 2B-1).

Two versioned records, both persisted as ADDITIVE JSON keys on
``PackagingOutput.spec_sheet`` (no DB columns, no new task status — the
existing ``awaiting_container_profile`` gate owns both confirmations):

    container_profile/1.0          the technical container structure
    container_decoration_zones/1.0 bounded, per-surface decoration areas

Nothing here calls a provider, composes artwork or touches the (still
raster) reconstruction — 2B-1 is the CONTRACT and the confirmation gate.

Authority model (§2/§3/§8): every profile field carries a ``source`` and a
``verification`` state. Photo-derived values are INFERRED_NONAUTHORITATIVE
until a human confirms them; only EXPLICIT_USER_FACT / VERIFIED_MANUFACTURER
_SPEC / VERIFIED_PRODUCT_RECORD (and an explicit user-confirmed visual
profile, for concept reconstruction only) may become production-confirmed
geometry — a confirmed visual profile never implies manufacturer tolerances.
"""
from __future__ import annotations

import hashlib
import json
import math
from apps.pipeline.targets.container import archetypes as _declared

PROFILE_SCHEMA = "container_profile/1.0"
ZONES_SCHEMA = "container_decoration_zones/1.0"

# --- verification states (§2) ------------------------------------------------
VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
INFERRED = "INFERRED_NONAUTHORITATIVE"
MISSING = "MISSING"
NOT_APPLICABLE = "NOT_APPLICABLE"
VERIFICATION_STATES = frozenset({VERIFIED, UNVERIFIED, INFERRED, MISSING,
                                 NOT_APPLICABLE})

# --- source authority (§3) ---------------------------------------------------
SRC_USER_FACT = "EXPLICIT_USER_FACT"
SRC_USER_VISUAL = "USER_CONFIRMED_VISUAL_PROFILE"
SRC_MFR_SPEC = "VERIFIED_MANUFACTURER_SPEC"
SRC_PRODUCT_RECORD = "VERIFIED_PRODUCT_RECORD"
SRC_INFERRED = "INFERRED_NONAUTHORITATIVE"
SRC_UNKNOWN = "UNKNOWN"
SOURCES = frozenset({SRC_USER_FACT, SRC_USER_VISUAL, SRC_MFR_SPEC,
                     SRC_PRODUCT_RECORD, SRC_INFERRED, SRC_UNKNOWN})
#: sources that may become production-confirmed GEOMETRY
PRODUCTION_GEOMETRY_SOURCES = frozenset({SRC_USER_FACT, SRC_MFR_SPEC,
                                         SRC_PRODUCT_RECORD})
#: a confirmed visual profile authorises CONCEPT reconstruction, not
#: manufacturer tolerances / printability
CONCEPT_RECONSTRUCTION_SOURCES = (PRODUCTION_GEOMETRY_SOURCES
                                  | {SRC_USER_VISUAL})

# --- surface vocabulary (§5) -------------------------------------------------
SURFACES = ("BODY_FRONT", "BODY_BACK", "BODY_LEFT", "BODY_RIGHT", "BODY_WRAP",
            "SHOULDER", "NECK", "CAP_FRONT", "CAP_BACK", "CAP_TOP", "CAP_WRAP",
            "BOTTOM", "CRIMP_ZONE")

#: §BH61(c): READ FROM THE ONE DECLARATION. This dict was the SECOND per-archetype registry the owner
#: found by a failure (§BH55(a) S5: the editor accepted `compact` and this did not). It is no longer a
#: second list — it is a projection of `targets.container.archetypes.VOCABULARY`, so a new form cannot
#: be drawable and undecoratable at the same time.
_ARCHETYPE_SURFACES = {
    k: _declared.surfaces_of(k) for k in _declared.ARCHETYPES
}
_ARCHETYPE_SURFACES_WAS = {
    # BOTTOM added 2026-07-24 (task #51 structural correction): a rigid bottle
    # has a bottom code area — the BOTTOM_CODE_ZONE must not require a crimp.
    "bottle": ("BODY_FRONT", "BODY_BACK", "BODY_LEFT", "BODY_RIGHT",
               "SHOULDER", "NECK", "CAP_FRONT", "CAP_TOP", "BOTTOM"),
    "jar": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CAP_TOP", "CAP_WRAP",
            "BOTTOM"),
    "tube": ("BODY_FRONT", "BODY_BACK", "BODY_WRAP", "CRIMP_ZONE",
             "CAP_FRONT", "CAP_TOP"),
    # §BH55(a): a hinged compact. Its surfaces are the owner's own two — "the lid artwork and the base panel" —
    # plus the two side walls of a closed case. The MIRROR and the PAN FIELD are deliberately absent: both are
    # inside the case and neither is printed, so they are geometry on the backbone (silhouettes._compact) and not
    # decoration surfaces. BASE_BOTTOM is the surface his brief says must be MEASURED to see whether it can hold
    # the regulatory copy — "the carton or the base, measured, not assumed" — which needs it to exist first.
    "compact": ("LID_TOP", "LID_EDGE", "BASE_BOTTOM", "BASE_EDGE"),
}


def surfaces_for(archetype: str, variant: str = "") -> tuple[str, ...]:
    """Available surfaces for an archetype (variant may prune, never add)."""
    base = _ARCHETYPE_SURFACES.get((archetype or "").lower(), ())
    if (variant or "").lower() == "square":
        # a square body has no continuous wrap surface
        base = tuple(s for s in base if s != "BODY_WRAP")
    return base

# --- curvature (§6) ----------------------------------------------------------
FLAT = "FLAT"
CYLINDRICAL = "CYLINDRICAL"
TAPERED_CYLINDRICAL = "TAPERED_CYLINDRICAL"
OVAL = "OVAL"
ROUNDED_RECT = "RECTANGULAR_WITH_ROUNDED_CORNERS"
CUSTOM_PROFILE = "CUSTOM_PROFILE"
CURVATURE_UNKNOWN = "UNKNOWN"
CURVATURES = frozenset({FLAT, CYLINDRICAL, TAPERED_CYLINDRICAL, OVAL,
                        ROUNDED_RECT, CUSTOM_PROFILE, CURVATURE_UNKNOWN})

# --- zone types (§4) + techniques -------------------------------------------
ZONE_TYPES = ("FRONT_PRINT_ZONE", "BACK_PRINT_ZONE", "LEFT_SIDE_PRINT_ZONE",
              "RIGHT_SIDE_PRINT_ZONE", "WRAP_LABEL_ZONE", "SCREEN_PRINT_ZONE",
              "PAD_PRINT_ZONE", "HOT_STAMP_ZONE", "CAP_PRINT_ZONE",
              "CAP_TOP_PRINT_ZONE", "NECK_BAND_ZONE", "SHRINK_SLEEVE_ZONE",
              "BOTTOM_CODE_ZONE")
TECHNIQUES = ("screen_printing", "pad_printing", "hot_stamping",
              "adhesive_label", "wrap_label", "shrink_sleeve", "emboss",
              "deboss",
              # technical coding, never decorative artwork (task #51
              # correction item 3) — named after the derived method so the
              # human reads exactly what will run on the bottom.
              "BOTTOM_INKJET_CODE")

# --- zone confirmation state -------------------------------------------------
ZONE_PROPOSED = "PROPOSED"
ZONE_USER_CONFIRMED = "USER_CONFIRMED"

# --- refusal / validator codes (§10/§11) ------------------------------------
PROFILE_CONFIRMATION_REQUIRED = "CONTAINER_PROFILE_CONFIRMATION_REQUIRED"
ZONE_CONFIRMATION_REQUIRED = "CONTAINER_DECORATION_ZONE_CONFIRMATION_REQUIRED"
SURFACE_PROJECTION_REVIEW_REQUIRED = "CONTAINER_SURFACE_PROJECTION_REVIEW_REQUIRED"
ZONE_OUT_OF_BOUNDS = "CONTAINER_ZONE_OUT_OF_BOUNDS"
#: §BH64(b) — the zone set beside this profile was derived from a
#: different one and no longer fits it. Raised instead of storing "a zone
#: that does not fit its own lid".
ZONE_PROFILE_DIVERGED = "CONTAINER_ZONE_PROFILE_DIVERGED"
#: [his test day finding 2, 2026-09-29, design 117: a zone set proposed for other sizes that STILL FITS was let
#: through — his tube set to 180 x 50 mm kept the 35 x 55 mm front proposed from the fallback 100 x 50, and would have
#: crowded his whole front into its upper part. A zone whose numbers are not its proposal for the sizes confirmed is
#: named by this, beside ZONE_OUT_OF_BOUNDS, and refused the same way]
ZONE_PROPOSED_FOR_OTHER_SIZES = "CONTAINER_ZONE_PROPOSED_FOR_OTHER_SIZES"
#: §BH64(b) follow-up — what a zone block written BEFORE that commit says when
#: asked which profile it came from. It is a real answer, not an absence: the
#: substitution notice names it instead of falling silent.
ZONE_SET_UNSTAMPED = "UNSTAMPED_PRE_BH64B"
ZONE_ZERO_AREA = "CONTAINER_ZONE_ZERO_AREA"
ZONE_SAFE_MARGIN_INVALID = "CONTAINER_ZONE_SAFE_MARGIN_INVALID"
ZONE_SURFACE_MISMATCH = "CONTAINER_ZONE_SURFACE_MISMATCH"
ZONE_SURFACE_KEY_UNRECOGNISED = "CONTAINER_ZONE_SURFACE_KEY_UNRECOGNISED"
ZONE_OVERLAP = "CONTAINER_ZONE_OVERLAP"
WRAP_SEAM_CONFLICT = "CONTAINER_WRAP_SEAM_CONFLICT"
CURVATURE_UNKNOWN_CODE = "CONTAINER_CURVATURE_UNKNOWN"
TECHNIQUE_UNVERIFIED = "CONTAINER_TECHNIQUE_UNVERIFIED"

# --- one spelling for the parent surface (§AA WI-R) --------------------------
#: The contract's spelling. Chosen over ``surface`` not by majority but because
#: ``surface`` is ALREADY TAKEN, correctly, by a different field: five modules
#: emit records whose own ``surface`` key names the surface the RECORD is about
#: (``back_panel``, ``container_wrap_geometry``, ``container_text_floor``,
#: ``container_production_metrics``, ``compose_vector_art``). Standardising
#: zones on ``surface`` would merge two fields that mean different things.
ZONE_SURFACE_KEY = "parent_surface"
#: spellings that look like they name the parent surface and are not read.
ZONE_SURFACE_ALIASES = ("surface",)


class ZoneSurfaceSpellingError(ValueError):
    """A zone named its parent surface with a key the contract does not read.

    Raised, not tolerated, because tolerating it is what the defect WAS. Ten
    of the eleven consumers measured in §AA WI-R accepted the alias and carried
    on with a different answer: the whole ``Surface-BODY_BACK`` group and its
    panel vanished from the composed artwork, ``build_wrap_geometry`` returned
    no wraps at all, the cylindrical distortion fell from 1.0 to 0.0, the
    handoff layer name became ``""``, a BODY_BACK zone was metered with
    ``role: front``, and the text floor fell back to 5.0 pt. Every one of those
    is a plausible-looking output. A raise is the only outcome a reader cannot
    mistake for a result.
    """


def zone_surface_problem(zone: dict) -> str | None:
    """The finding for a misspelled parent surface, or None.

    Validators want a code they can return over HTTP (§16: reject a malformed
    payload, never 500). Composers want the raise. Both read this, so the two
    boundaries cannot drift into two wordings of one refusal.
    """
    if not isinstance(zone, dict):
        return None
    aliases = [k for k in ZONE_SURFACE_ALIASES if k in zone]
    if not aliases:
        return None
    detail = ("both spellings are present, which of them is authority is not "
              "recorded anywhere" if ZONE_SURFACE_KEY in zone else
              f"{ZONE_SURFACE_KEY!r} is absent, so nothing reads it")
    return (f"{ZONE_SURFACE_KEY_UNRECOGNISED}: {zone.get('zone_id')} names its "
            f"parent surface with {aliases[0]!r} — {detail}. The contract "
            f"reads {ZONE_SURFACE_KEY!r}.")


def zone_surface(zone: dict) -> str | None:
    """This zone's parent surface, refusing any other spelling of the field.

    ``None`` when NEITHER spelling is present. That case is deliberately left
    alone: an absent key is a different condition, it is already reported by
    ``validate_zone`` as ``ZONE_SURFACE_MISMATCH: ... on None``, and turning it
    into a raise here would be a second fix riding on this one.
    """
    problem = zone_surface_problem(zone)
    if problem is not None:
        raise ZoneSurfaceSpellingError(problem)
    return zone.get(ZONE_SURFACE_KEY)


_PROFILE_FIELDS = (
    "archetype", "variant", "body_width_mm", "body_depth_mm",
    "body_height_mm", "aspect_ratio", "neck_width_mm", "neck_ratio",
    "shoulder_type", "shoulder_height_mm", "base_geometry", "cap_type",
    "cap_width_mm", "cap_depth_mm", "cap_height_mm", "closure_interface",
    "body_material", "cap_material", "body_transparency", "body_opacity",
    "body_base_color", "cap_color", "front_orientation", "back_orientation",
    "manufacturer_constraints",
)


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _hash(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()[:32]


def _field(value=None, *, source=SRC_UNKNOWN, verification=MISSING) -> dict:
    return {"value": value, "source": source, "verification": verification}


def fields_not_applying(archetype: str) -> frozenset:
    """The profile fields this form does not have — §BH70(1), item 17 of the list he was sent: "The records are shaped
    like a bottle. Every product record has neck, shoulder and cap fields". A NECK and its SHOULDER belong to a form
    that declares a neck proportion (a bottle); a CAP'S SIZES to a form that declares cap dimensions — his §BH61(b):
    "no neck proportion on a hinged case, no cap dimensions where there is no cap". Read from the one declaration; a
    form it does not know marks nothing. The cap's TYPE, colour and material are not among them: a compact's closure and
    its lid's colour are carried in those fields (`colour_sources`), under a bottle's name — the name is the words'
    matter (item 21), and the value applies."""
    if not _declared.is_known(archetype):
        return frozenset()
    out = set()
    if "neck_ratio" not in _declared.proportions_of(archetype):
        out |= {"neck_width_mm", "neck_ratio", "shoulder_type", "shoulder_height_mm"}
    if not _declared.vocabulary_of(archetype)["has_cap_dimensions"]:
        out |= {"cap_width_mm", "cap_depth_mm", "cap_height_mm"}
    return frozenset(out)


def build_inferred_profile(archetype: str, variant: str = "",
                           estimates: dict | None = None) -> dict:
    """Seed a container_profile/1.0 record (§8): every field
    INFERRED_NONAUTHORITATIVE or UNKNOWN/MISSING. Confirmation is the only
    place a state is promoted. ``estimates`` (e.g. from a photo) are stored
    as INFERRED values, never VERIFIED."""
    estimates = estimates or {}
    fields = {}
    for name in _PROFILE_FIELDS:
        if name == "archetype":
            fields[name] = _field(archetype, source=SRC_INFERRED,
                                  verification=INFERRED)
        elif name == "variant" and variant:
            fields[name] = _field(variant, source=SRC_INFERRED,
                                  verification=INFERRED)
        elif name in estimates and estimates[name] is not None:
            fields[name] = _field(estimates[name], source=SRC_INFERRED,
                                  verification=INFERRED)
        elif name == "manufacturer_constraints":
            # never inferred as verified facts (§2)
            fields[name] = _field({}, source=SRC_UNKNOWN,
                                  verification=UNVERIFIED)
        else:
            fields[name] = _field(None, source=SRC_UNKNOWN,
                                  verification=MISSING)
    record = {
        "schema_version": PROFILE_SCHEMA,
        "archetype": archetype,
        "variant": variant or (fields["variant"]["value"] or ""),
        "profile_source": SRC_INFERRED,
        "confirmation_state": "UNCONFIRMED",
        "confirmed_at": "",
        "confirmed_by": "",
        "fields": fields,
        # §BH70(1), item 17: which of these fields this form does not have — said on the record, beside the fields and
        # outside the profile hash, which his §AH4 (LIVE) holds byte-identical for a jar: "No stored confirmation is
        # invalidated. No persisted spec_sheet needs re-deriving. No jar in flight is disturbed." The fields keep their
        # state; the server refuses to fill them (`targets.ui.validate_container_profile_payload`).
        "not_applying": sorted(fields_not_applying(archetype)),
    }
    record["profile_hash"] = profile_hash(record)
    return record


def profile_hash(record: dict) -> str:
    """Canonical hash of the profile facts (excludes volatile timestamps and
    confirmation metadata)."""
    core = {"schema_version": record.get("schema_version"),
            "archetype": record.get("archetype"),
            "variant": record.get("variant"),
            "fields": {k: {"value": v.get("value"),
                           "source": v.get("source"),
                           "verification": v.get("verification")}
                       for k, v in (record.get("fields") or {}).items()}}
    return _hash(core)


def zone_hash(zone: dict) -> str:
    # §AA WI-R — identity is where a silent difference does the most harm: a
    # misspelled zone hashed cleanly to a DIFFERENT id, so the combined
    # confirmation hash moved and nothing said why. Refuse before hashing.
    zone_surface(zone)
    core = {k: zone.get(k) for k in (
        "zone_id", "zone_type", "parent_surface", "x", "y", "width",
        "height", "units", "curvature_type", "curvature_radius_mm",
        "safe_margin_mm", "max_artwork_coverage", "permitted_techniques",
        "permitted_color_count", "min_line_weight_mm", "min_text_size_pt",
        "registration_tolerance_mm", "source", "verification")}
    return _hash(core)


def zone_set_hash(zones: list[dict]) -> str:
    return _hash(sorted(zone_hash(z) for z in zones))


def combined_confirmation_hash(profile_record: dict,
                               zones: list[dict]) -> str:
    """§9: identity of a profile+zone confirmation; timestamps excluded, so a
    worker restart reads the identical record and a change to any load-bearing
    value invalidates it."""
    return _hash({"profile": profile_hash(profile_record),
                  "zones": zone_set_hash(zones)})


def zone_set_record(zones: list[dict], profile_record: dict, **extra) -> dict:
    """§BH64(b) THE ONE WRITER of the zone block, and the one source for its
    numbers.

    A zone's x/y/width/height mean nothing except against the surfaces of one
    profile. Before this, the two were stored side by side with nothing saying
    which profile the numbers were about, and a confirmation that edited a
    dimension persisted the edited profile next to zones proposed from the
    profile it replaced — a record that contradicted itself, and a screen that
    could never be confirmed again. Every write of ``spec[ZONES_SCHEMA]`` goes
    through here, so the block always carries the hash of the profile written
    beside it in the same act and the pair can never be written apart.
    """
    return {"schema_version": ZONES_SCHEMA,
            "zones": zones,
            "zone_set_hash": zone_set_hash(zones),
            "profile_hash": profile_hash(profile_record),
            **extra}


def zone_set_belongs_to(zone_block: dict | None, profile_record: dict) -> bool:
    """True when the stored zone block was derived from THIS profile. A block
    written before §BH64(b) carries no ``profile_hash`` and never claims to
    belong — it is judged by whether it still fits, below."""
    return bool(zone_block) and (zone_block.get("profile_hash")
                                 == profile_hash(profile_record))


def zone_profile_divergence(zone_block: dict | None, zones: list[dict],
                            profile_record: dict, proposal: list | None = None) -> list[str]:
    """§BH64(b) — the findings when a zone set that does not belong to this
    profile also does not fit it.

    Empty when the set belongs to the profile, and empty when it belongs to
    another one but its zones are still this profile's own proposal: a profile
    change that moved no surface cannot strand a zone, and refusing on the hash
    alone would refuse every edit that touched only a colour or a note.

    [his test day finding 2, 2026-09-29: "empty when it still FITS" let the
    machine's proposal for other sizes through whenever the new body was larger
    — one source for the numbers means the numbers of the sizes confirmed. A
    zone that carries the stored PROPOSAL's numbers unchanged, where that
    proposal was made for another profile and is not this one's, is named,
    fitting or not. A person's own numbers — a zone whose place or size differs
    from the stored proposal, or one the record holds as confirmed — are theirs:
    for those, fitting is the test, as before.]
    """
    if zone_set_belongs_to(zone_block, profile_record):
        return []
    found = [p for p in validate_zone_set(zones, profile_record)
             if p.startswith(ZONE_OUT_OF_BOUNDS)]
    block_zones = zone_block.get("zones") if isinstance(zone_block, dict) else None
    stored = {z.get("zone_id"): z for z in block_zones if isinstance(z, dict)} if isinstance(block_zones, list) else {}
    # [his yes of 2026-09-30] the proposal this profile's shape step makes — the caller's (from the concept's map)
    # where it hands one in, else the contract's own
    proposal = {z["zone_id"]: z for z in (proposal if proposal is not None
                                          else augment_code_zones(profile_record, propose_zones(profile_record)))}
    for zone in zones:
        was = stored.get(zone.get("zone_id"))
        if (was is None or was.get("user_confirmation_state") == ZONE_USER_CONFIRMED
                or _zone_geometry(zone) != _zone_geometry(was)):
            continue                     # a person's own numbers — whether they fit is the check above
        own = proposal.get(zone.get("zone_id"))
        if own is None or _zone_geometry(zone) != _zone_geometry(own):
            found.append(f"{ZONE_PROPOSED_FOR_OTHER_SIZES}: {zone.get('zone_id')} is "
                         f"{_zone_words(zone)}, proposed for other sizes; for these it is "
                         + (_zone_words(own) if own is not None else "not proposed at all"))
    return found


def _zone_geometry(zone: dict):
    """A zone's place and size — its surface, x, y, width and height to the hundredth of a mm — or None when it
    carries no numbers to compare."""
    try:
        return (zone_surface(zone), *(round(float(zone.get(k)), 2) for k in ("x", "y", "width", "height")))
    except (TypeError, ValueError):
        return None


def _zone_words(zone: dict) -> str:
    return "%s x %s mm at (%s, %s)" % (zone.get("width"), zone.get("height"), zone.get("x"), zone.get("y"))


# --- surface bounds + curvature (§5/§6) -------------------------------------

def _num(record: dict, name: str, default: float) -> float:
    f = (record.get("fields") or {}).get(name) or {}
    v = f.get("value")
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def surface_geometry(profile_record: dict) -> dict:
    """Per-surface flat bounds (mm) + curvature class, from the profile.
    Missing dimensions fall back to bounded defaults so the contract is
    always evaluable; unknown curvature stays UNKNOWN and blocks."""
    import math
    bw = _num(profile_record, "body_width_mm", 50.0)
    bd = _num(profile_record, "body_depth_mm", bw)
    bh = _num(profile_record, "body_height_mm", 100.0)
    cw = _num(profile_record, "cap_width_mm", bw * 0.5)
    ch = _num(profile_record, "cap_height_mm", bh * 0.12)
    nh = _num(profile_record, "shoulder_height_mm", bh * 0.12)
    # Task #51 correction item 4: an UNBOUNDED cap (no recorded cap dims) is
    # never classified as safely CYLINDRICAL — its curvature stays UNKNOWN,
    # which blocks confirmation of any cap zone with
    # CONTAINER_SURFACE_PROJECTION_REVIEW_REQUIRED until the user supplies
    # cap dimensions (or removes the optional cap zone). The w/h fallbacks
    # remain for bounds arithmetic only.
    fields = profile_record.get("fields") or {}
    cap_bounded = all(
        (fields.get(name) or {}).get("value") is not None
        for name in ("cap_width_mm", "cap_height_mm"))
    cap_curve = CYLINDRICAL if cap_bounded else CURVATURE_UNKNOWN
    cap_top_curve = FLAT if cap_bounded else CURVATURE_UNKNOWN
    variant = (profile_record.get("variant") or "").lower()
    body_curve = {"square": FLAT, "cylindrical": CYLINDRICAL,
                  "tapered": TAPERED_CYLINDRICAL,
                  "flacon": FLAT}.get(variant, CYLINDRICAL)      # [§BH71 PART 3: a flacon's faces are flat glass]
    side_curve = body_curve
    # Cross-section authority (task #51 structural correction): when the
    # profile carries an explicit rounded-rectangular base_geometry, the front
    # and back are FLAT readable central faces (the curved corner transitions
    # live on the sides) — front/back are never classified CYLINDRICAL unless
    # a circular cross-section is actually recorded.
    base_geom = str(((profile_record.get("fields") or {})
                     .get("base_geometry") or {}).get("value") or "").upper()
    if "ROUNDED" in base_geom and ("RECT" in base_geom or "CORNER" in base_geom):
        body_curve, side_curve = FLAT, ROUNDED_RECT
    # [his answer after test day finding 3, 2026-09-30, (4): "round" — a tube's width is its round diameter] a squeeze
    # tube's front and back are the faces it is pressed into, each half its circumference: π/2 of its round width
    face_w = round(math.pi / 2.0 * bw, 2) if profile_record.get("archetype") == "tube" else bw
    return {
        "BODY_FRONT": {"w": face_w, "h": bh, "curvature": body_curve},
        "BODY_BACK": {"w": face_w, "h": bh, "curvature": body_curve},
        "BODY_LEFT": {"w": bd, "h": bh, "curvature": side_curve},
        "BODY_RIGHT": {"w": bd, "h": bh, "curvature": side_curve},
        "BODY_WRAP": {"w": round(math.pi * bw, 2), "h": bh,
                      "curvature": CYLINDRICAL},
        "SHOULDER": {"w": bw, "h": nh, "curvature": OVAL},
        "NECK": {"w": _num(profile_record, "neck_width_mm", bw * 0.42),
                 "h": nh, "curvature": CYLINDRICAL},
        "CAP_FRONT": {"w": cw, "h": ch, "curvature": cap_curve},
        "CAP_BACK": {"w": cw, "h": ch, "curvature": cap_curve},
        "CAP_TOP": {"w": cw, "h": cw, "curvature": cap_top_curve},
        "CAP_WRAP": {"w": round(math.pi * cw, 2), "h": ch,
                     "curvature": cap_curve},
        "BOTTOM": {"w": bw, "h": bd, "curvature": FLAT},
        # [his answer after test day finding 3, (4) round: the crimp is the flat end, as wide as the tube's faces]
        "CRIMP_ZONE": {"w": face_w, "h": bh * 0.08, "curvature": FLAT},
        # §BH55(a) compact, in PLAN: bw x bh are the lid footprint seen from above and bd is the CLOSED
        # THICKNESS, which the lid and the base divide between them. Flat, because a compact's faces are flat —
        # the rounded corners are the variant's, not a curvature the printer wraps around.
        "LID_TOP": {"w": bw, "h": bh, "curvature": FLAT},
        "BASE_BOTTOM": {"w": bw, "h": bh, "curvature": FLAT},
        "LID_EDGE": {"w": bw, "h": round(bd / 2.0, 2), "curvature": ROUNDED_RECT},
        "BASE_EDGE": {"w": bw, "h": round(bd / 2.0, 2), "curvature": ROUNDED_RECT},
    }


def round_plan(profile_record: dict) -> bool:
    """§BH71 PART 1: a ROUND compact — its lid and its base circles across the plan, not the plan's rectangle. [§BH71
    PART 3: and a round tin, the same circles.]"""
    return profile_record.get("archetype") in ("compact", "tin") \
        and profile_record.get("variant") in ("round", "cushion")     # [§BH71 PART 3: a cushion is round]


def oval_plan(profile_record: dict) -> bool:
    """§BH71 PART 3: a compact or a tin whose lid is a LEARNED OVAL (``services.learned_shapes``) — its lid and its
    base the ellipse in the plan's width and length, not the plan's rectangle. The variant key names the geometry."""
    return profile_record.get("archetype") in ("compact", "tin") \
        and profile_record.get("variant") == "learned_oval"


def oval_face(zone: dict, surface: dict) -> bool:
    """The zone IS the oval lid's whole face — its box the plan's own, within the proposal's 0.1 mm rounding."""
    box = (0.0, 0.0, surface["w"], surface["h"])
    return all(abs(float(zone[k]) - v) <= 0.05 for k, v in zip(("x", "y", "width", "height"), box))


def outside_the_ellipse(zone: dict, surface: dict) -> float:
    """How far, in mm, a zone reaches beyond an oval surface's ellipse along the ray from its centre — 0.0 when it
    keeps inside: the lid's own face zone is the ellipse, any other zone keeps its four corners within it."""
    import math
    if oval_face(zone, surface):
        return 0.0
    a, b = surface["w"] / 2.0, surface["h"] / 2.0
    x, y, w, h = (float(zone[k]) for k in ("x", "y", "width", "height"))
    worst = 0.0
    for px in (x, x + w):
        for py in (y, y + h):
            dx, dy = px - a, py - b
            rho = math.hypot(dx / a, dy / b)
            if rho > 1.0:
                worst = max(worst, math.hypot(dx, dy) * (1.0 - 1.0 / rho))
    return worst


#: the surfaces a round compact's circle bounds — the lid seen from above and the base seen from below
ROUND_PLAN_SURFACES = ("LID_TOP", "BASE_BOTTOM")


def round_face(zone: dict, surface: dict) -> bool:
    """The zone IS the round lid's whole face — its box the circle's own, within the proposal's 0.1 mm rounding
    (§BH67(c)3, OWNER RULED: the compact's print zone is the whole lid)."""
    d = min(surface["w"], surface["h"])
    box = ((surface["w"] - d) / 2.0, (surface["h"] - d) / 2.0, d, d)
    return all(abs(float(zone[k]) - v) <= 0.05 for k, v in zip(("x", "y", "width", "height"), box))


def outside_the_circle(zone: dict, surface: dict) -> float:
    """How far, in mm, a zone reaches beyond a round surface's circle — 0.0 when it keeps inside: the lid's own face
    zone is the circle, any other zone keeps its four corners within it."""
    import math
    if round_face(zone, surface):
        return 0.0
    r = min(surface["w"], surface["h"]) / 2.0
    cx, cy = surface["w"] / 2.0, surface["h"] / 2.0
    x, y, w, h = (float(zone[k]) for k in ("x", "y", "width", "height"))
    far = max(math.hypot(px - cx, py - cy) for px in (x, x + w) for py in (y, y + h))
    return max(0.0, far - r)


def projected_dimensions(zone: dict, surface: dict) -> dict:
    """Flat artwork dims + projected surface dims (§6). Cylindrical wraps
    stretch along the width (arc length); flat surfaces map 1:1."""
    import math
    flat = {"width_mm": zone.get("width"), "height_mm": zone.get("height")}
    curve = surface.get("curvature")
    if curve in (CYLINDRICAL, TAPERED_CYLINDRICAL):
        r = zone.get("curvature_radius_mm") or (surface["w"] / math.pi / 2)
        arc = zone.get("width")
        proj = {"width_mm": arc, "height_mm": zone.get("height"),
                "wrap_radius_mm": round(r, 2),
                "note": "flat width is the arc length; the printed area wraps"}
    elif curve == FLAT:
        proj = dict(flat)
    else:
        proj = {"width_mm": None, "height_mm": None,
                "note": f"curvature {curve} not represented safely"}
    return {"flat": flat, "projected": proj}


# --- validators (§11) --------------------------------------------------------

def validate_profile(record: dict) -> list[str]:
    """Structural validity of a container_profile/1.0 record."""
    problems: list[str] = []
    if record.get("schema_version") != PROFILE_SCHEMA:
        problems.append(f"{PROFILE_CONFIRMATION_REQUIRED}: wrong schema")
        return problems
    if (record.get("archetype") or "").lower() not in _ARCHETYPE_SURFACES:
        problems.append(f"{PROFILE_CONFIRMATION_REQUIRED}: unknown archetype")
    for name, f in (record.get("fields") or {}).items():
        if f.get("verification") not in VERIFICATION_STATES:
            problems.append(
                f"{PROFILE_CONFIRMATION_REQUIRED}: {name} bad verification")
        if f.get("source") not in SOURCES:
            problems.append(
                f"{PROFILE_CONFIRMATION_REQUIRED}: {name} bad source")
    return problems


def profile_is_confirmable(record: dict) -> list[str]:
    """§10 step 1: the profile carries enough CONFIRMED structure to
    reconstruct a concept (dimensions from an authoritative or user-confirmed
    visual source). Returns blocker messages; empty = confirmable.

    2B-3V UI correction §4: body_depth_mm is REQUIRED — every supported
    archetype is a 3D body, and a missing depth silently collapsed the
    cross-section to a circle (task #51's 35×25 oval would have reconstructed
    wrong). A pure cylinder states depth explicitly (= width), never by
    omission."""
    problems = validate_profile(record)
    fields = record.get("fields") or {}
    for name in ("body_width_mm", "body_depth_mm", "body_height_mm"):
        f = fields.get(name) or {}
        if f.get("value") is None:
            problems.append(
                f"{PROFILE_CONFIRMATION_REQUIRED}: {name} is required")
        elif f.get("source") not in CONCEPT_RECONSTRUCTION_SOURCES:
            problems.append(
                f"{PROFILE_CONFIRMATION_REQUIRED}: {name} is "
                f"{f.get('source')} — confirm the value before use")
    return problems


def validate_zone(zone: dict, profile_record: dict) -> list[str]:
    """§11 deterministic zone checks (bounds, area, margin, surface,
    curvature, technique)."""
    problems: list[str] = []
    # §AA WI-R — the spelling is checked FIRST and returns, because every check
    # below reads the surface and a misspelled zone would otherwise collect a
    # pile of downstream findings that all have one cause.
    spelling = zone_surface_problem(zone)
    if spelling is not None:
        return [spelling]
    surfaces = surfaces_for(profile_record.get("archetype", ""),
                            profile_record.get("variant", ""))
    geom = surface_geometry(profile_record)
    surface = zone_surface(zone)
    if surface not in surfaces:
        problems.append(f"{ZONE_SURFACE_MISMATCH}: {zone.get('zone_id')} on "
                        f"{surface!r} (available: {list(surfaces)})")
        return problems
    sg = geom[surface]
    w, h = zone.get("width"), zone.get("height")
    x, y = zone.get("x"), zone.get("y")
    margin = zone.get("safe_margin_mm")
    if w is None or h is None or w <= 0 or h <= 0:
        problems.append(f"{ZONE_ZERO_AREA}: {zone.get('zone_id')}")
        return problems
    if x is None or y is None or x < 0 or y < 0 \
            or x + w > sg["w"] + 1e-6 or y + h > sg["h"] + 1e-6:
        problems.append(
            f"{ZONE_OUT_OF_BOUNDS}: {zone.get('zone_id')} "
            f"({x},{y},{w},{h}) exceeds {surface} {sg['w']}x{sg['h']}")
    elif oval_plan(profile_record) and surface in ROUND_PLAN_SURFACES and outside_the_ellipse(zone, sg) > 1e-6:
        # §BH71 PART 3: a learned oval lid's lid and base are ellipses — a zone inside the plan's box can leave them
        problems.append(
            f"{ZONE_OUT_OF_BOUNDS}: {zone.get('zone_id')} ({x},{y},{w},{h}) leaves the oval {surface}, "
            f"{sg['w']} x {sg['h']} mm, by {outside_the_ellipse(zone, sg):.1f} mm")
    elif round_plan(profile_record) and surface in ROUND_PLAN_SURFACES and outside_the_circle(zone, sg) > 1e-6:
        # §BH71 PART 1: a round compact's lid and base are circles — a zone inside the plan's box can still leave them
        problems.append(
            f"{ZONE_OUT_OF_BOUNDS}: {zone.get('zone_id')} ({x},{y},{w},{h}) leaves the round {surface}, "
            f"{min(sg['w'], sg['h'])} mm across, by {outside_the_circle(zone, sg):.1f} mm")
    if margin is None or margin < 0 or 2 * margin >= min(w, h):
        problems.append(f"{ZONE_SAFE_MARGIN_INVALID}: {zone.get('zone_id')}")
    curve = zone.get("curvature_type")
    if curve not in CURVATURES or curve == CURVATURE_UNKNOWN:
        problems.append(f"{CURVATURE_UNKNOWN_CODE}: {zone.get('zone_id')}")
    elif sg["curvature"] == CURVATURE_UNKNOWN:
        # item 4: the zone claims a curvature its (unbounded) parent surface
        # cannot support — an unbounded cap is never safely CYLINDRICAL.
        problems.append(
            f"{CURVATURE_UNKNOWN_CODE}: {zone.get('zone_id')} — parent "
            f"surface {surface} is unbounded (supply cap dimensions or "
            "remove the optional zone)")
    techs = zone.get("permitted_techniques") or []
    if not techs or any(t not in TECHNIQUES for t in techs):
        problems.append(f"{TECHNIQUE_UNVERIFIED}: {zone.get('zone_id')}")
    cov = zone.get("max_artwork_coverage")
    if cov is not None and not (0 < cov <= 1.0):
        problems.append(f"{ZONE_ZERO_AREA}: {zone.get('zone_id')} coverage")
    return problems


def validate_zone_set(zones: list[dict], profile_record: dict) -> list[str]:
    """All per-zone problems + cross-zone overlap on the same surface."""
    problems: list[str] = []
    for z in zones:
        problems.extend(validate_zone(z, profile_record))
    by_surface: dict[str, list[dict]] = {}
    for z in zones:
        # a misspelled zone already returned its own finding above; group it
        # under None rather than raising, so one bad zone cannot hide the
        # overlap findings of the good ones.
        surf = None if zone_surface_problem(z) else zone_surface(z)
        by_surface.setdefault(surf, []).append(z)
    for surface, group in by_surface.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if _overlap(group[i], group[j]) and not _overlap_allowed(
                        group[i], group[j]):
                    code = (WRAP_SEAM_CONFLICT
                            if "WRAP" in (surface or "") else ZONE_OVERLAP)
                    problems.append(
                        f"{code}: {group[i].get('zone_id')} & "
                        f"{group[j].get('zone_id')} on {surface}")
    return problems


#: §BH71 (0b): two zones that meet along an edge do not overlap. Their edges are numbers rounded to 0.1 mm whose
#: sums miss the next rounded edge by float noise — a base panel at 2.2 mm, 39.6 mm tall, ends at 41.800000000000004
#: and the code window below it starts at 41.8 — which refused the proposal at 62 of the sizes the shape step takes
#: (a compact 44 mm tall among them). A tolerance for float noise, not a design threshold: nothing that truly overlaps
#: by a millionth of a millimetre is a zone.
_EDGE_MM = 1e-6


def _overlap(a: dict, b: dict) -> bool:
    ax, ay, aw, ah = a.get("x", 0), a.get("y", 0), a.get("width", 0), a.get("height", 0)
    bx, by, bw, bh = b.get("x", 0), b.get("y", 0), b.get("width", 0), b.get("height", 0)
    # [§BH71 (0b): each edge within _EDGE_MM of its neighbour meets it. Was: ax + aw <= bx, exactly]
    return not (ax + aw <= bx + _EDGE_MM or bx + bw <= ax + _EDGE_MM
                or ay + ah <= by + _EDGE_MM or by + bh <= ay + _EDGE_MM)


def _overlap_allowed(a: dict, b: dict) -> bool:
    # e.g. a foil zone atop a print zone using compatible techniques
    compat = {"hot_stamping", "emboss", "deboss"}
    return bool((set(a.get("permitted_techniques") or []) & compat)
                or (set(b.get("permitted_techniques") or []) & compat))


def make_zone(zone_id: str, zone_type: str, parent_surface: str, *,
              x: float, y: float, width: float, height: float,
              curvature_type: str, safe_margin_mm: float = 3.0,
              max_artwork_coverage: float = 0.8,
              permitted_techniques: tuple[str, ...] = ("screen_printing",),
              curvature_radius_mm: float | None = None,
              source: str = SRC_INFERRED,
              verification: str = INFERRED,
              user_confirmation_state: str = ZONE_PROPOSED) -> dict:
    zone = {
        "zone_id": zone_id, "zone_type": zone_type,
        "parent_surface": parent_surface, "x": x, "y": y,
        "width": width, "height": height, "units": "mm",
        "curvature_type": curvature_type,
        "curvature_radius_mm": curvature_radius_mm,
        "safe_margin_mm": safe_margin_mm,
        "max_artwork_coverage": max_artwork_coverage,
        "permitted_techniques": list(permitted_techniques),
        "permitted_color_count": None, "min_line_weight_mm": None,
        "min_text_size_pt": None, "registration_tolerance_mm": None,
        "source": source, "verification": verification,
        "user_confirmation_state": user_confirmation_state,
    }
    zone["zone_hash"] = zone_hash(zone)
    return zone


def _cap_is_bounded(profile_record: dict) -> bool:
    """Cap zones are proposed only when the cap has recorded dimensions —
    a proposal on an unbounded cap surface can never be confirmed (item 1/4)."""
    fields = profile_record.get("fields") or {}
    return all((fields.get(name) or {}).get("value") is not None
               for name in ("cap_width_mm", "cap_height_mm"))


#: §BH70(1) — THE SLIM FORMS' PRINT AREAS: (width share, height share, safe margin mm, techniques). A lipstick, a
#: mascara and a pencil are printed on the front and the back of a body the eye walks around, like a tube — but
#: slim. The contract refuses a zone whose safe margin is half its width or more (`validate_zone`), and the bottle's
#: 3.0 mm margin needs a zone more than 6 mm across: a 7 mm pencil's 70 % zone is 4.9 mm. Each form takes the margin
#: its own narrowest declared width allows (`archetypes.ranges_of`), measured, so every size the shape step lets a
#: person enter can be confirmed: at 5 mm a pencil's zone is 4.5 mm with 1.0 mm margins; at 8 mm a mascara's is
#: 6.4 mm with 1.5; at 10 mm a lipstick's 7.0 mm with 1.5.
_SLIM_FORM_ZONES = {
    "lipstick": (0.70, 0.45, 1.5, ("screen_printing", "hot_stamping", "pad_printing")),
    "mascara": (0.80, 0.50, 1.5, ("screen_printing", "hot_stamping")),
    "pencil": (0.90, 0.60, 1.0, ("hot_stamping", "screen_printing")),
}


def propose_zones(profile_record: dict) -> list[dict]:
    """§12 bounded draft zones per archetype. Every zone is PROPOSED /
    INFERRED — a proposal is NEVER production authority. Cap zones are
    OPTIONAL and only proposed when the cap is bounded."""
    archetype = (profile_record.get("archetype") or "").lower()
    geom = surface_geometry(profile_record)
    cap_ok = _cap_is_bounded(profile_record)

    def centred(surface, cov_w=0.7, cov_h=0.6):
        sg = geom[surface]
        w, h = round(sg["w"] * cov_w, 1), round(sg["h"] * cov_h, 1)
        return (round((sg["w"] - w) / 2, 1), round((sg["h"] - h) / 2, 1),
                w, h, sg["curvature"])

    zones: list[dict] = []
    if archetype == "bottle":
        for zid, ztype, surf in (
                ("z_front", "FRONT_PRINT_ZONE", "BODY_FRONT"),
                ("z_back", "BACK_PRINT_ZONE", "BODY_BACK")):
            x, y, w, h, c = centred(surf)
            zones.append(make_zone(zid, ztype, surf, x=x, y=y, width=w,
                                   height=h, curvature_type=c))
        if cap_ok:
            x, y, w, h, c = centred("CAP_TOP")
            zones.append(make_zone(
                "z_cap_top", "CAP_TOP_PRINT_ZONE", "CAP_TOP",
                x=x, y=y, width=w, height=h, curvature_type=c,
                permitted_techniques=("pad_printing",)))
    elif archetype == "jar":
        x, y, w, h, c = centred("BODY_WRAP", cov_w=0.85)
        zones.append(make_zone(
            "z_wrap", "WRAP_LABEL_ZONE", "BODY_WRAP",
            x=x, y=y, width=w, height=h, curvature_type=c,
            permitted_techniques=("wrap_label",)))
        if cap_ok:
            x, y, w, h, c = centred("CAP_TOP", cov_w=0.85)
            zones.append(make_zone(
                "z_cap_top", "CAP_TOP_PRINT_ZONE", "CAP_TOP",
                x=x, y=y, width=w, height=h, curvature_type=c,
                permitted_techniques=("pad_printing",)))
    elif archetype == "compact":
        # §BH55(a): "the lid artwork and the base panel" — exactly two, because that is what he named and a
        # compact has no wrap and no cap to print on. The lid takes the generous coverage a hero face deserves;
        # the base is the regulatory surface and takes nearly all of itself, because the question his brief asks
        # of it is whether it CAN HOLD the copy, and a zone cropped for looks would answer that question falsely.
        #
        # §BH67(c)3, OWNER RULED 2026-09-24: "THE COMPACT'S PRINT ZONE IS THE WHOLE LID, inside bleed and the mark's
        # clear space. §BH66(a) already gave a compact lid to the concept's arrangement; a zone smaller than the lid
        # breaks that — the ring runs round the lid as the concept draws it." The zone IS the lid face — the plan less
        # the hinge band, `silhouettes.compact_lid_face`, the region the lid is drawn as — where it was an 82 x 78 %
        # inset the executor chose (2990725). Print keeps inside the lid's own edge by the zone's 3.0 mm safe margin,
        # which stands: a lid printed directly on the moulded part has no bleed (the transcription's reading, recorded
        # at the ruling). The mark's clear space is the face layout's (§AY2), unchanged. The base is not his (c)3's.
        from apps.pipeline.targets.container.silhouettes import compact_lid_face
        lid = geom["LID_TOP"]
        face = compact_lid_face(lid["w"], lid["h"], variant=profile_record.get("variant"))      # §BH71: its shape
        zones.append(make_zone(
            "z_lid", "FRONT_PRINT_ZONE", "LID_TOP",
            x=round(face["x_mm"], 1), y=round(face["y_mm"], 1), width=round(face["width_mm"], 1),
            height=round(face["height_mm"], 1),
            curvature_type=lid["curvature"],
            permitted_techniques=("screen_printing", "hot_stamping", "pad_printing")))
        x, y, w, h, c = centred("BASE_BOTTOM", cov_w=0.90, cov_h=0.90)
        if round_plan(profile_record):
            # §BH71 PART 1: a round compact's base is a circle across the plan's narrower side — its panel the 4:3
            # rectangle whose diagonal is 90 % of that circle, centred, so every corner keeps inside the base
            bg = geom["BASE_BOTTOM"]
            d = min(bg["w"], bg["h"])
            w, h = round(0.72 * d, 1), round(0.54 * d, 1)
            x, y = round((bg["w"] - w) / 2, 1), round((bg["h"] - h) / 2, 1)
        elif oval_plan(profile_record):
            # §BH71 PART 3: a learned oval's base is its ellipse — the round panel's shares of each axis, whose
            # corners keep inside it ((0.72 / 2)^2 / (1 / 2)^2 + (0.54 / 2)^2 / (1 / 2)^2 = 0.81)
            bg = geom["BASE_BOTTOM"]
            w, h = round(0.72 * bg["w"], 1), round(0.54 * bg["h"], 1)
            x, y = round((bg["w"] - w) / 2, 1), round((bg["h"] - h) / 2, 1)
        else:
            h = _leave_code_band(geom["BASE_BOTTOM"]["h"], y, h)   # [§BH71 (0b): room below for its code]
        zones.append(make_zone(
            "z_base", "BACK_PRINT_ZONE", "BASE_BOTTOM",
            x=x, y=y, width=w, height=h, curvature_type=c,
            permitted_techniques=("screen_printing", "pad_printing")))
    elif archetype == "tube":
        for zid, ztype, surf in (
                ("z_front", "FRONT_PRINT_ZONE", "BODY_FRONT"),
                ("z_back", "BACK_PRINT_ZONE", "BODY_BACK")):
            x, y, w, h, c = centred(surf, cov_h=0.55)
            zones.append(make_zone(zid, ztype, surf, x=x, y=y, width=w,
                                   height=h, curvature_type=c))
        # optional small cap mark — logo/mark only, tightly bounded, and only
        # when the cap itself is bounded (item 1/4)
        if cap_ok:
            x, y, w, h, c = centred("CAP_FRONT", cov_w=0.5, cov_h=0.4)
            zones.append(make_zone(
                "z_cap", "CAP_PRINT_ZONE", "CAP_FRONT",
                x=x, y=y, width=w, height=h, curvature_type=c,
                safe_margin_mm=1.0, max_artwork_coverage=0.3,
                permitted_techniques=("pad_printing", "hot_stamping")))
        # bottom/crimp is a decoration EXCLUSION — a bounded code zone only
        cg = geom["CRIMP_ZONE"]
        # §BH71 (0b): a short tube's band, see below. [§BH71 (0b), measured at F31: a tube 52 to 66 mm tall had a
        # 2.1 to 2.7 mm window whose 1.0 mm margins left it less than one line of its code (0.08 mm at 52) — the
        # margin is the one that leaves the window its line, `code_margin`. Was: 0.5 at or under a 2.0 mm band,
        # and 1.0 above it]
        crimp_margin = code_margin(max(cg["h"] * 0.5, 2.0))
        zones.append(make_zone(
            "z_crimp_code", "BOTTOM_CODE_ZONE", "CRIMP_ZONE",
            x=round(cg["w"] * 0.4, 1), y=0.0, width=round(cg["w"] * 0.2, 1),
            height=max(cg["h"] * 0.5, 2.0), curvature_type=cg["curvature"],
            # [§BH71 (0b): a tube 50 mm tall or shorter gets the 2.0 mm floor, which its 1.0 mm margins refused
            # (CONTAINER_ZONE_SAFE_MARGIN_INVALID) — its one code place could never be confirmed; the band takes
            # the narrower margin there, and every taller tube's window is unchanged]
            safe_margin_mm=crimp_margin, max_artwork_coverage=0.2,
            permitted_techniques=("BOTTOM_INKJET_CODE",)))
    elif archetype in _SLIM_FORM_ZONES:
        # §BH70(1): the front and the back, each at its form's own shares and margin (the table above), and — for a
        # lipstick, whose cap top is where a house mark is stamped — the same optional cap-top mark a bottle is
        # offered, only when the cap is bounded. A mascara's cap is its wand's grip and a pencil's is 8 mm across;
        # neither is offered one.
        cov_w, cov_h, margin, techniques = _SLIM_FORM_ZONES[archetype]
        for zid, ztype, surf in (
                ("z_front", "FRONT_PRINT_ZONE", "BODY_FRONT"),
                ("z_back", "BACK_PRINT_ZONE", "BODY_BACK")):
            x, y, w, h, c = centred(surf, cov_w=cov_w, cov_h=cov_h)
            zones.append(make_zone(zid, ztype, surf, x=x, y=y, width=w, height=h, curvature_type=c,
                                   safe_margin_mm=margin, permitted_techniques=techniques))
        if archetype == "lipstick" and cap_ok:
            x, y, w, h, c = centred("CAP_TOP", cov_w=0.8, cov_h=0.8)
            zones.append(make_zone(
                "z_cap_top", "CAP_TOP_PRINT_ZONE", "CAP_TOP",
                x=x, y=y, width=w, height=h, curvature_type=c, safe_margin_mm=1.0,
                permitted_techniques=("pad_printing", "hot_stamping")))
    elif archetype == "tin":
        # §BH71 PART 3: a tin's lid is its face, whole — the circle's own box when it is round (the whole lid, as a
        # round compact's is), its rectangle when it slides; its base takes the regulatory copy, inside its circle
        lid = geom["LID_TOP"]
        x0, y0, fw, fh = 0.0, 0.0, lid["w"], lid["h"]
        if round_plan(profile_record):
            d = min(lid["w"], lid["h"])
            x0, y0, fw, fh = (lid["w"] - d) / 2.0, (lid["h"] - d) / 2.0, d, d
        zones.append(make_zone(
            "z_lid", "FRONT_PRINT_ZONE", "LID_TOP", x=round(x0, 1), y=round(y0, 1), width=round(fw, 1),
            height=round(fh, 1), curvature_type=lid["curvature"], safe_margin_mm=2.0,
            permitted_techniques=("screen_printing", "hot_stamping", "pad_printing")))
        bg = geom["BASE_BOTTOM"]
        x, y, w, h, c = centred("BASE_BOTTOM", cov_w=0.90, cov_h=0.90)
        if round_plan(profile_record):
            d = min(bg["w"], bg["h"])
            w, h = round(0.72 * d, 1), round(0.54 * d, 1)
            x, y = round((bg["w"] - w) / 2, 1), round((bg["h"] - h) / 2, 1)
        elif oval_plan(profile_record):                            # [§BH71 PART 3: a learned oval tin]
            w, h = round(0.72 * bg["w"], 1), round(0.54 * bg["h"], 1)
            x, y = round((bg["w"] - w) / 2, 1), round((bg["h"] - h) / 2, 1)
        else:
            h = _leave_code_band(bg["h"], y, h)                    # [§BH71 (0b): room below for its code]
        zones.append(make_zone(
            "z_base", "BACK_PRINT_ZONE", "BASE_BOTTOM", x=x, y=y, width=w, height=h, curvature_type=c,
            safe_margin_mm=2.0, permitted_techniques=("screen_printing", "pad_printing")))
    elif archetype in _NEW_FORM_ZONES:
        # §BH71 PART 3: a sachet's, an oval stick's, a can's and an ampoule's front and back, each at its own shares
        # and margin (the table below) — a sachet's inside its seals, an ampoule's at the margin its narrowest allows
        cov_w, cov_h, margin, techniques = _NEW_FORM_ZONES[archetype]
        for zid, ztype, surf in (
                ("z_front", "FRONT_PRINT_ZONE", "BODY_FRONT"),
                ("z_back", "BACK_PRINT_ZONE", "BODY_BACK")):
            x, y, w, h, c = centred(surf, cov_w=cov_w, cov_h=cov_h)
            zones.append(make_zone(zid, ztype, surf, x=x, y=y, width=w, height=h, curvature_type=c,
                                   safe_margin_mm=margin, permitted_techniques=techniques))
    return zones


def _leave_code_band(base_h: float, y: float, h: float) -> float:
    """§BH71 (0b): a rectangular base panel's height, less what it must leave below it for the code band to hold one
    line (``code_band_mm``) — unchanged wherever the 5 % band already holds it (from some 36 mm tall; his compacts'
    95 mm leave 4.75)."""
    short = code_band_mm() - (base_h - (y + h))
    return round(h - short, 1) if short > 1e-9 else h


#: §BH71 PART 3 — the new forms' print areas: (width share, height share, safe margin mm, techniques). An ampoule is
#: 6 mm across at its narrowest, so its margin is 1.0 mm (its 80 % zone 4.8 mm across holds it); a sachet's shares
#: keep inside its seals; a can prints all round and a front and a back are what a person confirms of it.
_NEW_FORM_ZONES = {
    "sachet": (0.80, 0.70, 3.0, ("screen_printing",)),
    "oval_stick": (0.70, 0.50, 2.0, ("screen_printing", "hot_stamping", "pad_printing")),
    "aerosol": (0.80, 0.55, 3.0, ("screen_printing",)),
    "ampoule": (0.80, 0.45, 1.0, ("screen_printing", "pad_printing")),
}


#: §BH71 (0b), THE OWNER'S GOAL OF 2026-09-28: "Propose a batch-code place for every form that lacks one, shown as a
#: production note, not a blocker." Each form's own place for the filler's inkjet batch/date code, as a PROPOSED,
#: INFERRED, OPTIONAL zone — the person confirms it or skips it at the shape step, like the dropper's and the tube's:
#: * a bottle, a jar, a lipstick or a mascara — its BOTTOM, the dropper's own rule (half its width by three tenths
#:   of its depth, centred; a round base holds it, the window's corner 0.29 of the width from the centre);
#: * a compact — its base's underside, in the band below the base panel (read off the proposed z_base, never
#:   recomputed), a fifth of its width, centred;
#: * a pencil — it declares no bottom or end, so the back of its barrel near the butt end, below the back panel,
#:   three fifths of its width across and up to 20 mm along;
#: * a tube — its crimp already carries one (propose_zones).
#: Added AFTER propose_zones and never inside it: §AH4 (LIVE) pins the jar's proposal hashes and forbids moving
#: them (test_wiz_zone_contract.py). A proposal that already carries a code zone is returned as it is.
def code_line_mm() -> float:
    """§BH71 (0b): the height of one line of the bottom inkjet's own smallest text — its capability row's
    ``min_text_pt`` (``container_production_method._METHOD_DEFAULTS``), in millimetres. A code window that cannot
    hold this line inside its margins is no place for a code."""
    from apps.ire.container_production_method import _METHOD_DEFAULTS
    return float(_METHOD_DEFAULTS["BOTTOM_INKJET_CODE"]["min_text_pt"]) * 25.4 / 72.0


def code_margin(height_mm: float) -> float:
    """§BH71 (0b): a code window's safe margin — 1.0 mm where that still leaves it one line of its code, else the
    narrower 0.5 mm a small compact's band has always taken."""
    margin = 0.5
    if height_mm - 2.0 >= code_line_mm():
        margin = 1.0
    return margin


def code_band_mm() -> float:
    """§BH71 (0b): the least height a code window may have — one line inside the narrower margins, to 0.1 mm up."""
    return math.ceil((code_line_mm() + 2 * 0.5) * 10.0 - 1e-9) / 10.0


def bottom_code_zone(profile_record: dict) -> dict:
    """The code window on the BOTTOM — the dropper's rule, shared so its bytes never move.

    [§BH71 (0b): and never too thin for its code — where 30 % of the bottom is less than a line inside the
    margins (a mascara 16 mm across: 2.4 mm, a line of 0.4 inside its 1.0 margins), the margin narrows and the
    window deepens to the least that holds one, never past the bottom. Wherever the window held its line, its
    bytes are as they were.]"""
    bg = surface_geometry(profile_record)["BOTTOM"]
    zw, zh = round(bg["w"] * 0.5, 1), round(bg["h"] * 0.3, 1)
    margin = code_margin(zh)
    if zh - 2 * margin < code_line_mm():
        zh = round(min(bg["h"], code_band_mm()), 1)
    return make_zone(
        "z_bottom_code", "BOTTOM_CODE_ZONE", "BOTTOM",
        x=round((bg["w"] - zw) / 2, 1), y=round((bg["h"] - zh) / 2, 1),
        width=zw, height=zh, curvature_type=bg["curvature"],
        safe_margin_mm=margin, max_artwork_coverage=0.2,
        permitted_techniques=("BOTTOM_INKJET_CODE",))


def code_zone_for(profile_record: dict, zones: list[dict]) -> dict | None:
    """§BH71 (0b): the code place this form's own surfaces offer, proposed beside ``zones``; None for a form whose
    proposal carries its own (the tube) or that is not declared."""
    named = profile_record.get("archetype")
    if not named:                                     # a record naming no form is offered no place
        return None
    archetype = str(named).lower()
    geom = surface_geometry(profile_record)
    if archetype in ("bottle", "jar", "lipstick", "mascara", "oval_stick", "aerosol"):
        return bottom_code_zone(profile_record)
    if archetype in ("compact", "tin"):                  # [§BH71 PART 3: a tin's base, as a compact's]
        bg = geom["BASE_BOTTOM"]
        base = next((z for z in zones if z.get("zone_id") == "z_base"), None)
        top = round(base["y"] + base["height"], 1) if base else round(bg["h"] * 0.95, 1)
        h, w = round(bg["h"] - top, 1), round(bg["w"] * 0.2, 1)
        if round_plan(profile_record):
            # §BH71 PART 1: inside the round base — a fifth of its circle wide, the band the rectangle's plan leaves
            # at its foot (5 %) tall, at the top of the room below the panel, where the circle is still wide
            d = min(bg["w"], bg["h"])
            h, w = round(min(h, 0.05 * d), 1), round(0.2 * d, 1)
            if h - 2 * code_margin(h) < code_line_mm():
                # [§BH71 (0b): a circle 20 mm across left 1.0 mm, which its own margins took whole, and no place
                # was offered — the window deepens to the least that holds a line, as far as the circle holds
                # below the panel at its width]
                room = bg["h"] / 2.0 + math.sqrt(max(0.0, (d / 2.0) ** 2 - (w / 2.0) ** 2)) - top
                h = round(min(room, code_band_mm()), 1)
        if oval_plan(profile_record):
            # §BH71 PART 3: inside a learned oval's base — a fifth of its width, 5 % of its shorter axis tall,
            # deepened to hold a line as far as the ellipse holds below the panel at its width (the round rule's,
            # with its two radii apart)
            h, w = round(min(h, 0.05 * min(bg["w"], bg["h"])), 1), round(0.2 * bg["w"], 1)
            if h - 2 * code_margin(h) < code_line_mm():
                a, b = bg["w"] / 2.0, bg["h"] / 2.0
                room = b + b * math.sqrt(max(0.0, 1.0 - (w / 2.0 / a) ** 2)) - top
                h = round(min(room, code_band_mm()), 1)
        # [§BH71 (0b): the margin is the one that leaves the window its line — it was 1.0 above a 2.0 mm band,
        # so a band of 2.1 held 0.1 mm of code (a tin at its own starting size); a window that cannot hold a line
        # is no place. Was: margin 0.5 at or under 2.0 mm and 1.0 above it; refused only at or under twice its
        # margin]
        margin = code_margin(h)
        if h - 2 * margin < code_line_mm():
            return None
        return make_zone(
            "z_base_code", "BOTTOM_CODE_ZONE", "BASE_BOTTOM", x=round((bg["w"] - w) / 2, 1), y=top,
            width=w, height=h, curvature_type=bg["curvature"], safe_margin_mm=margin,
            max_artwork_coverage=0.2, permitted_techniques=("BOTTOM_INKJET_CODE",))
    if archetype == "sachet":
        # §BH71 PART 3: a sachet's one flat place for its code is its foot's seal, as a tube's is its crimp
        cg = geom["CRIMP_ZONE"]
        return make_zone(
            "z_seal_code", "BOTTOM_CODE_ZONE", "CRIMP_ZONE", x=round(cg["w"] * 0.4, 1), y=0.0,
            width=round(cg["w"] * 0.2, 1), height=round(max(cg["h"] * 0.5, 2.0), 1), curvature_type=cg["curvature"],
            safe_margin_mm=0.5, max_artwork_coverage=0.2, permitted_techniques=("BOTTOM_INKJET_CODE",))
    if archetype in ("pencil", "ampoule"):                # [§BH71 PART 3: an ampoule declares no end to print on]
        bg = geom["BODY_BACK"]
        w, h = round(bg["w"] * 0.6, 1), round(min(20.0, bg["h"] * 0.12), 1)
        return make_zone(
            "z_back_code", "BOTTOM_CODE_ZONE", "BODY_BACK", x=round((bg["w"] - w) / 2, 1),
            y=round(bg["h"] - 0.04 * bg["h"] - h, 1), width=w, height=h,
            curvature_type=bg["curvature"], safe_margin_mm=1.0, max_artwork_coverage=0.2,
            permitted_techniques=("BOTTOM_INKJET_CODE",))
    return None


#: [his yes of 2026-09-30, transcribed at 5d23649] the kinds of a concept map's parts that are the product's material,
#: not its print: a colour field and a closure are body and cap; a window is the frame the print sits in
MAP_MATERIAL_KINDS = ("field", "closure", "window")


def map_zone_form(profile_record: dict) -> bool:
    """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design, for a wand vial and a carton".] True for a form whose front the concept's map proposes: one
    drawn standing whose primary surface is its body's front — a tube, a wand vial, a jar, a pump bottle; never a face
    form (its lid's own reading lays it out) nor the dropper, which keeps the selected-concept contract's proposal."""
    archetype = profile_record.get("archetype")
    if not _declared.is_known(archetype) or _declared.is_face(archetype):
        return False
    if _declared.drawn_as_of(archetype) != _declared.ELEVATION:
        return False
    cap = ((profile_record.get("fields") or {}).get("cap_type") or {}).get("value")
    return cap != "dropper" and profile_record.get("variant") != "dropper"


def propose_zones_with_map(profile_record: dict, map_parts: list | None = None, *, flip: bool = False,
                           cap_top_share: float | None = None, body_top_share: float | None = None) -> list[dict]:
    """[His yes of 2026-09-30 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 5d23649): 117's print area re-proposed from his
    concept, which prints edge to edge where his confirmed front was 35 x 99 mm in the middle.] The print areas the shape
    step proposes — ``augment_code_zones(record, propose_zones(record))`` byte for byte when ``map_parts`` is empty — with
    the FRONT_PRINT_ZONE of a form the map proposes for (``map_zone_form``: a tube since his yes, every form drawn
    standing with a front since his go of 2026-10-02, a wand vial among them), where the concept's map names parts it
    prints, laid over their extent: the union of their boxes (fractions of the product, ``concept_design_map``) in the
    front's own millimetres — its width the front face's, its height the product's — turned end over end where ``flip``
    (the drawing stands the product the other way from the picture), its foot held above ``cap_top_share`` of the height
    where the cap stands at the foot and its top below ``body_top_share`` where the cap stands on top, and rounded to a
    tenth of a millimetre; every other field of the zone as the proposal made it."""
    zones = augment_code_zones(profile_record, propose_zones(profile_record))
    printed = [p for p in map_parts or [] if p.get("kind") not in MAP_MATERIAL_KINDS and p.get("box")]
    if not printed or not map_zone_form(profile_record):
        return zones
    x0 = min(float(p["box"][0]) for p in printed)
    y0 = min(float(p["box"][1]) for p in printed)
    x1 = max(float(p["box"][2]) for p in printed)
    y1 = max(float(p["box"][3]) for p in printed)
    if flip:
        y0, y1 = 1.0 - y1, 1.0 - y0
    if cap_top_share is not None:
        y1 = min(y1, float(cap_top_share))
    if body_top_share is not None:
        y0 = max(y0, float(body_top_share))             # [his go of 2026-10-02] below a cap that stands on top
    geom = surface_geometry(profile_record)
    face = geom["BODY_FRONT"]
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(1.0, x1), min(1.0, y1)
    if x1 <= x0 or y1 <= y0:
        return zones
    out = []
    for zone in zones:
        if zone.get("zone_type") == "FRONT_PRINT_ZONE" and zone.get("parent_surface") == "BODY_FRONT":
            zone = dict(zone, **_extent(x0, y0, x1, y1, face),
                        proposed_from="the concept picture's map: the parts it prints")
        elif (zone.get("zone_type") == "BACK_PRINT_ZONE" and zone.get("parent_surface") == "BODY_BACK"
              and "BODY_BACK" in geom):
            # [his test blocker on design 122 at the shape step, 2026-10-08: "the back print area stayed 38.5 × 66 mm
            # while the front grew to 55 × 99.9 mm; the back carries the most text and should grow with the tube"] the
            # back at least as large as the front's extent on its own surface, never smaller than its own proposal, and
            # clear of every other area there (a slim form's code place stands on its back)
            zone = _clear_of(dict(zone, **_union(zone, _extent(x0, y0, x1, y1, geom["BODY_BACK"])),
                                  proposed_from=BACK_FROM_FRONT), zone, zones)
        out.append(zone)
    return held_inside(profile_record, out)


#: [his test blocker on design 122 at the shape step] said on a back grown with its front
BACK_FROM_FRONT = "the front's extent, on the back: the back carries the most text"
#: … and the gap it keeps from another area on its surface, in millimetres
BACK_CLEAR_MM = 1.0


def _union(a: dict, b: dict) -> dict:
    """The area that holds both ``a`` and ``b`` (each ``x``, ``y``, ``width``, ``height`` in millimetres), to the
    tenth."""
    x, y = min(float(a["x"]), float(b["x"])), min(float(a["y"]), float(b["y"]))
    x1 = max(float(a["x"]) + float(a["width"]), float(b["x"]) + float(b["width"]))
    y1 = max(float(a["y"]) + float(a["height"]), float(b["y"]) + float(b["height"]))
    return {"x": round(x, 1), "y": round(y, 1), "width": round(x1 - x, 1), "height": round(y1 - y, 1)}


def _box(zone: dict) -> tuple[float, float, float, float]:
    x, y = float(zone["x"]), float(zone["y"])
    return x, y, x + float(zone["width"]), y + float(zone["height"])


def _clear_of(grown: dict, own: dict, zones: list[dict]) -> dict:
    """``grown`` (the back ``own`` grown with its front) stopped BACK_CLEAR_MM short of every other area on its surface
    it would overlap — above one that sits lower, below one that sits higher; ``own``, as proposed, where what is left
    would no longer hold it."""
    x0, y0, x1, y1 = _box(grown)
    others = [z for z in zones if z.get("zone_id") != own.get("zone_id")
              and z.get("parent_surface") == own.get("parent_surface")]
    for other in others:
        ox0, oy0, ox1, oy1 = _box(other)
        if ox1 <= x0 or ox0 >= x1 or oy1 <= y0 or oy0 >= y1:
            continue
        if (oy0 + oy1) / 2.0 >= (y0 + y1) / 2.0:
            y1 = min(y1, oy0 - BACK_CLEAR_MM)
        else:
            y0 = max(y0, oy1 + BACK_CLEAR_MM)
    held = dict(grown, y=round(y0, 1), height=round(y1 - y0, 1))
    hx0, hy0, hx1, hy1 = _box(held)
    ax0, ay0, ax1, ay1 = _box(own)
    holds = hx0 <= ax0 + 1e-6 and hy0 <= ay0 + 1e-6 and hx1 >= ax1 - 1e-6 and hy1 >= ay1 - 1e-6
    clear = all(_box(o)[2] <= hx0 or _box(o)[0] >= hx1 or _box(o)[3] <= hy0 or _box(o)[1] >= hy1 for o in others)
    if not (holds and clear):
        return own
    return held


def _extent(x0: float, y0: float, x1: float, y1: float, surface: dict) -> dict:
    """An area over the fractions ``x0..x1``, ``y0..y1`` of ``surface``, in its millimetres to the tenth; one its
    rounding carries past the surface's edge is held inside it after (``held_inside``)."""
    return {"x": round(x0 * surface["w"], 1), "y": round(y0 * surface["h"], 1),
            "width": round((x1 - x0) * surface["w"], 1), "height": round((y1 - y0) * surface["h"], 1)}


def held_inside(profile_record: dict, zones: list[dict]) -> list[dict]:
    """[His test blocker on design 122 at the shape step, 2026-10-08: "Find why, fix it for every design".] Every
    proposed print area inside the surface it is checked against (``validate_zone_set``): an area that runs past its
    surface's edge only by its rounding — 122's front, 55.0 mm on a 54.98 mm face (a 35 mm tube's half round), refused
    by the door that proposed it, so no confirm at those sizes could pass — is trimmed to the tenth inside it. Nothing
    else moves."""
    geom = surface_geometry(profile_record)
    out = []
    for zone in zones:
        sg = geom.get(zone.get("parent_surface"))
        if sg is None or zone.get("x") is None or zone.get("y") is None or not zone.get("width") or not zone.get("height"):
            out.append(zone)
            continue
        over_w = float(zone["x"]) + float(zone["width"]) - float(sg["w"])
        over_h = float(zone["y"]) + float(zone["height"]) - float(sg["h"])
        trimmed = {}
        if 1e-6 < over_w < 0.1:
            trimmed["width"] = math.floor((float(sg["w"]) - float(zone["x"])) * 10.0) / 10.0
        if 1e-6 < over_h < 0.1:
            trimmed["height"] = math.floor((float(sg["h"]) - float(zone["y"])) * 10.0) / 10.0
        out.append(dict(zone, **trimmed) if trimmed else zone)
    return out


def augment_code_zones(profile_record: dict, zones: list[dict]) -> list[dict]:
    """§BH71 (0b): ``zones`` with this form's code place added when none is there — the proposal a person
    confirms, at every door that proposes one."""
    zones = list(zones)
    if any(z.get("zone_type") == "BOTTOM_CODE_ZONE" for z in zones):
        return held_inside(profile_record, zones)
    zone = code_zone_for(profile_record, zones)
    # [his test blocker on design 122 at the shape step] every door's proposal held inside its surfaces
    return held_inside(profile_record, zones + ([zone] if zone else []))


def code_place_words(zone: dict | None) -> str:
    """Where a proposed code place is, in words: its surface, its size and its position in the surface's box."""
    if not zone:
        return "no place this form's surfaces can offer"
    where = {"BOTTOM": "on the bottom", "BASE_BOTTOM": "on the base's underside, at its foot",
             "BODY_BACK": "on the back of the barrel, near its end", "CRIMP_ZONE": "on the crimped end"}
    surface = str(zone["parent_surface"])
    said = surface.lower().replace("_", " ")
    if surface in where:
        said = where[surface]
    return "%s, a %.1f × %.1f mm window at (%.1f, %.1f)" % (said, zone["width"], zone["height"], zone["x"],
                                                            zone["y"])


def merge_product_record_dims(record: dict, product) -> dict:
    """Promote body width/depth/height from the task's PRODUCT RECORD
    (2B-3V UI correction §2). Source = VERIFIED_PRODUCT_RECORD (the value is
    exactly AS RECORDED on the product row), verification stays UNVERIFIED —
    a database record is not a manufacturer verification. Returns a NEW
    record with a fresh hash; fields the record lacks are left untouched."""
    import copy
    dims = {
        "body_width_mm": getattr(product, "width_mm", None),
        "body_depth_mm": getattr(product, "depth_mm", None),
        "body_height_mm": getattr(product, "height_mm", None),
    }
    out = copy.deepcopy(record)
    fields = out.setdefault("fields", {})
    for name, value in dims.items():
        if value is None:
            continue
        fields[name] = _field(float(value), source=SRC_PRODUCT_RECORD,
                              verification=UNVERIFIED)
    out["profile_hash"] = profile_hash(out)
    return out


def merge_user_profile(record: dict, user_values: dict,
                       source: str = SRC_USER_VISUAL) -> dict:
    """Promote the fields a human reviewed/confirmed. A user-confirmed
    visual profile authorises concept reconstruction only — manufacturer
    constraints stay UNVERIFIED unless supplied as a VERIFIED_MANUFACTURER_
    SPEC (out of 2B-1 scope). Returns a NEW record with a fresh hash."""
    import copy
    if source not in CONCEPT_RECONSTRUCTION_SOURCES:
        source = SRC_USER_VISUAL
    out = copy.deepcopy(record)
    fields = out.setdefault("fields", {})
    for name, value in (user_values or {}).items():
        if name not in _PROFILE_FIELDS or value is None:
            continue
        if name == "manufacturer_constraints":
            fields[name] = _field(value, source=SRC_UNKNOWN,
                                  verification=UNVERIFIED)
        else:
            fields[name] = _field(value, source=source, verification=VERIFIED)
        if name in ("archetype", "variant"):
            out[name] = value
    out["profile_source"] = source
    out["profile_hash"] = profile_hash(out)
    return out


def evaluate_confirmation(profile_record: dict,
                          zones: list[dict]) -> str | None:
    """§10 ordered refusal: profile → zones → curvature. Returns the first
    blocking code, or None when the profile + a fully user-confirmed,
    valid, projection-safe zone set are ready to reconstruct."""
    if profile_is_confirmable(profile_record):
        return PROFILE_CONFIRMATION_REQUIRED
    if not zones:
        return ZONE_CONFIRMATION_REQUIRED
    if any(z.get("user_confirmation_state") != ZONE_USER_CONFIRMED
           for z in zones):
        return ZONE_CONFIRMATION_REQUIRED
    problems = validate_zone_set(zones, profile_record)
    if any(p.startswith(CURVATURE_UNKNOWN_CODE) for p in problems):
        return SURFACE_PROJECTION_REVIEW_REQUIRED
    if problems:
        return ZONE_CONFIRMATION_REQUIRED
    return None


__all__ = [
    "PROFILE_SCHEMA", "ZONES_SCHEMA", "VERIFICATION_STATES", "SOURCES",
    "merge_user_profile", "merge_product_record_dims", "evaluate_confirmation",
    "PRODUCTION_GEOMETRY_SOURCES", "CONCEPT_RECONSTRUCTION_SOURCES",
    "SURFACES", "surfaces_for", "CURVATURES", "ZONE_TYPES", "TECHNIQUES",
    "ZONE_PROPOSED", "ZONE_USER_CONFIRMED",
    "PROFILE_CONFIRMATION_REQUIRED", "ZONE_CONFIRMATION_REQUIRED",
    "SURFACE_PROJECTION_REVIEW_REQUIRED", "ZONE_PROFILE_DIVERGED",
    "ZONE_PROPOSED_FOR_OTHER_SIZES", "ZONE_SET_UNSTAMPED",
    "zone_set_record", "zone_set_belongs_to", "zone_profile_divergence",
    "build_inferred_profile", "profile_hash", "zone_hash", "zone_set_hash",
    "combined_confirmation_hash", "surface_geometry", "projected_dimensions",
    "validate_profile", "profile_is_confirmable", "validate_zone",
    "validate_zone_set", "make_zone", "propose_zones",
    "SRC_USER_FACT", "SRC_USER_VISUAL", "SRC_MFR_SPEC", "SRC_PRODUCT_RECORD",
    "SRC_INFERRED", "SRC_UNKNOWN", "VERIFIED", "UNVERIFIED", "INFERRED",
    "MISSING", "NOT_APPLICABLE",
]
