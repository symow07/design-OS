"""Native container motif contract (Phase 2B-2A, slice 1).

Derives ``container_motif_spec/1.0`` from the SELECTED concept's structured
variation + the visual graph + the confirmed decoration zones, and binds it to
the bounded, deterministic, no-raster/no-trace motif engine already shipped for
packaging (``apps/ire/design_language.py``). We do NOT build a parallel motif
library: the mandate's family names collapse onto the existing
``DesignLanguage`` recipes, and that collapse is recorded honestly
(``requested_family`` vs ``rendered_via``) rather than hidden.

Language selection routes through ``design_language.resolve_language`` so a
motif that cannot be responsibly rebuilt from the supported primitives fails
closed with ``VECTOR_RECONSTRUCTION_REVIEW_REQUIRED`` (§3) — never traced,
never rasterised, never silently swapped for an unrelated generic motif.

The motif is authored from the selected variation, never from the user brief
or direction prose alone (§1).
"""
from __future__ import annotations

import hashlib
import json
import re

from apps.ire.composer_vocabulary import APPROXIMATE_FAMILIES, FAMILY_TO_LANGUAGE
from apps.ire.container_finishes import assignments as finish_assignments
from apps.ire.design_language import (
    VectorReconstructionReviewRequired,
    resolve_language,
)
from apps.pipeline.services.container_contract import (INFERRED, MISSING,
                                                       VERIFIED, zone_surface)

SCHEMA = "container_motif_spec/1.0"
VECTOR_RECONSTRUCTION_REVIEW_REQUIRED = "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"

# reconstruction capability
CAP_SUPPORTED = "SUPPORTED"
CAP_REVIEW_REQUIRED = "REVIEW_REQUIRED"
CAP_NONE = "NONE"                 # the selected concept carries no motif

# --- mandate motif families (§2) --------------------------------------------
FAMILIES = (
    "GEOMETRIC_ABSTRACT", "PARTICLE_FLOW", "POWDER_CONSTELLATION",
    "DEWDROP_CONSTELLATION",
    "RADIANCE_LINES", "CONTOUR_STREAMS", "RIBBON_FLOW", "SOFT_PETALS",
    "BOTANICAL_LINE_ART", "FLORAL_ABSTRACT", "MICRO_PATTERN",
    "TONAL_COLOR_FIELD", "EDITORIAL_RULE_SYSTEM",
    # §BH65(c)4: the planner's LINEAR_ENGRAVED and GEOMETRIC_HALO, named in the composer's own classifier
    "ENGRAVED_LINEWORK", "HALO_RINGS",
    # [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."]
    "RADIAL_LINES",
)

#: keyword evidence to classify the selected motif signature → a mandate family
_FAMILY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # DEWDROP before POWDER (2B-3V-CORR-3): dew/droplet vocabulary names the
    # droplet family, never a generic particle field.
    ("DEWDROP_CONSTELLATION", ("dewdrop", "dew drop", "droplet", "dew",
                               "teardrop", "water drop", "drop")),
    # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    # "The lid is missing the concept's rule, ring and radial lines."] BEFORE POWDER, whose "particle" would otherwise take
    # a radial concept on a tie. Every word MEASURED against every Gate-1 variation on record before it was chosen
    # (``test_container_motif._RECORDED_VARIATIONS``, 21, and task 110): the bare "radial" is refused — six petal and
    # dewdrop records say "radial gradient", "radial fan", "radial cluster" — as are "ray" (RADIANCE_LINES' own) and
    # "focal point" (it would move 50 B's radiance hairlines). With these, task 110's "lines emanating from a single
    # centre point" reads RADIAL_LINES by two words to one, and every recorded variation reads as it did.
    ("RADIAL_LINES", ("radial line", "radial ray", "radial stroke", "radiating", "emanating", "sunburst",
                      "starburst", "spoke", "centre point", "center point")),
    ("POWDER_CONSTELLATION", ("powder", "constellation", "particle", "speck",
                              "dust", "dot", "sparkle")),
    ("PARTICLE_FLOW", ("scatter", "drift", "float", "disperse")),
    # §BH65(c)4: before RADIANCE and EDITORIAL, whose "line"/"glow" would otherwise take an engraving or a halo
    ("ENGRAVED_LINEWORK", ("engrav", "etched", "guilloche", "hatch", "linework")),
    ("HALO_RINGS", ("halo", "concentric", "ring of light", "radial ring")),
    ("RADIANCE_LINES", ("radiance", "ray", "burst", "shine", "glow")),
    ("CONTOUR_STREAMS", ("contour", "topographic", "terrain", "stream",
                         "wave", "ripple")),
    ("RIBBON_FLOW", ("ribbon", "liquid", "veil", "pour", "flow", "silk",
                     "drape", "fluid")),
    ("SOFT_PETALS", ("petal", "bloom")),
    ("BOTANICAL_LINE_ART", ("botanical", "leaf", "stem", "vine", "line art",
                            "line-art")),
    ("FLORAL_ABSTRACT", ("floral", "flower", "rose", "blossom")),
    ("MICRO_PATTERN", ("micro", "tiny", "fine pattern", "allover", "texture")),
    ("EDITORIAL_RULE_SYSTEM", ("rule", "ruled", "line", "stripe", "pinstripe",
                               "grid", "editorial")),
    ("GEOMETRIC_ABSTRACT", ("geometric", "strata", "band", "block",
                            "architectural", "abstract")),
    ("TONAL_COLOR_FIELD", ("tonal", "gradient", "wash", "ombre", "field",
                           "minimal")),
)

#: honest collapse: mandate family → the DesignLanguage that renders it. Where
#: the nearest supported generator is not a literal match (BOTANICAL_LINE_ART /
#: FLORAL_ABSTRACT → elliptical petals, RADIANCE_LINES → contour streams) the
#: spec surfaces ``rendered_via`` so the label never outruns the geometry.
#:
#: §BH65(c): the table now LIVES IN THE ONE CONTRACT (apps/ire/composer_vocabulary.py) and is imported at the top
#: of this module, not copied — the same objects, so the composing classifier and the contract cannot say
#: different things. Moved byte-for-byte: no family routes anywhere it did not.
_FAMILY_TO_LANGUAGE = FAMILY_TO_LANGUAGE
#: families whose nearest supported generator is an approximation (recorded)
_APPROXIMATE_FAMILIES = APPROXIMATE_FAMILIES

#: body surfaces that may legitimately carry a motif field
_MOTIF_SURFACES = ("BODY_FRONT", "BODY_BACK", "BODY_LEFT", "BODY_RIGHT",
                   "BODY_WRAP")


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _hash(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()[:32]


#: §BH67(b)1, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md:23350, LIVE): "THE MOTIF IS THE WRONG FAMILY. Draw
#: the family the concept named, or refuse by name if it cannot be drawn." MEASURED over every Gate-1 variation record
#: on record (21, read-only 2026-09-24): all five A_PETAL_WINDOW concepts — tasks 51, 84, 88, 89 and 91, "seven-to-nine
#: slender Bézier teardrop petals", "petal-droplets" — classified DEWDROP_CONSTELLATION, because the scan counted
#: SUBSTRINGS ("drop" inside "teardrop" and "droplet"; "rose" inside "rose-gold"; "flow" inside "flower") and a shape
#: word as a family. The rules, each read off those records: a keyword is a WHOLE word (a plural folded in) and counts
#: each time it is said; a colour's "rose" (rose-gold, Deep Rose) is no flower; a SHAPE word before a petal, leaf or
#: bloom ("teardrop petals") describes it and is not a family of its own; and the house's own "petal droplets" — the
#: words of the July Gate-1 petal-window directive, offered as an option since §BH67(c)4
#: (`container_gate1.CONTAINER_GATE1_DIRECTIVES`) — are petals. Measured after: exactly the five petal windows change,
#: to SOFT_PETALS; the other sixteen records classify as they did.
_STEMS = frozenset({"engrav"})
#: the 2C-2E negation scrub, named once so the classifier and the fallback read a refusal the same way
_NEGATED = re.compile(r"\b(?:no|not|without|never|zero)\b[^;,.—]*")
#: [his answer of 2026-10-05, W6: "type-only is a real design style"] a motif sentence that names the type alone — "type
#: only", "typographic", "the mark and the name alone", "only the name" — names no motif
_TYPE_ONLY = re.compile(
    r"\btype[\s-]*only\b|\btypograph(?:y|ic)(?:[\s-]*(?:only|alone|led))?\b"
    r"|\b(?:the\s+)?(?:name|mark|words|letters|lettering|type)\b[^;,.—]*\b(?:alone|only)\b"
    r"|\bonly\b[^;,.—]*\b(?:name|mark|words|letters|lettering|type)\b")
_ROSE_COLOUR = re.compile(
    r"(?<![a-z])(?:(?:deep|dusty|pale|soft|antique|blush|dark|light|warm|cool|old|tea)[\s-]+rose"
    r"|rose[\s-]*(?:gold|pink|plum|quartz|nude|beige|brown|tint|tone|toned|tinted|blush|copper|metal|metallic|foil|"
    r"red|wine|mauve|taupe))(?![a-z])")
_HOUSE_PETALS = re.compile(r"(?<![a-z])petal[\s-]+(?:droplets?|drops?)(?![a-z])")
_SHAPE_BEFORE_ELEMENT = re.compile(
    r"(?<![a-z])(?:teardrop|tear[\s-]drop|droplet|drop|dewdrop)[\s-]+"
    r"(?=(?:petals?|leaf|leaves|blooms?|flowers?|blossoms?)(?![a-z]))")


def _keyword_re(kw: str):
    body = r"[\s-]+".join(map(re.escape, kw.replace("-", " ").split()))
    return re.compile(r"(?<![a-z])" + body + (r"[a-z]*" if kw in _STEMS else r"(?:s|es)?") + r"(?![a-z])")


_FAMILY_RES = tuple((family, tuple(_keyword_re(kw) for kw in kws)) for family, kws in _FAMILY_KEYWORDS)


def classify_family(signature: str) -> str | None:
    text = (signature or "").lower()
    if not text.strip():
        return None
    # 2C-2E: NEGATED vocabulary must never summon a motif — "no botanical or
    # floral element" names what the concept EXCLUDES. The keyword scan was
    # negation-blind and classified the live pilot's "no decorative motif …
    # no botanical or floral element" as FLORAL_ABSTRACT.
    text = _NEGATED.sub(" ", text)
    # §BH67(b)1: a colour is no flower, the house's petal droplets are petals, a shape word describes a petal
    text = _SHAPE_BEFORE_ELEMENT.sub("", _HOUSE_PETALS.sub("petals", _ROSE_COLOUR.sub(" ", text)))
    best, best_score = None, 0
    for family, patterns in _FAMILY_RES:
        score = sum(len(rx.findall(text)) for rx in patterns)
        if score > best_score:
            best, best_score = family, score
    return best


_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                 "ten": 10, "eleven": 11, "twelve": 12}
_NUM = r"(?:" + "|".join(_NUMBER_WORDS) + r"|\d{1,2})"
_PETAL_COUNT_RE = re.compile(r"(?<![a-z-])(?P<a>" + _NUM + r")(?:[\s-]*(?:to|-|–|or)[\s-]*(?P<b>" + _NUM
                             + r"))?[\s-]+(?:[a-zé-]+[\s-]+){0,4}?petals?(?![a-z])")
_OPACITY_RE = re.compile(r"(\d{1,3})\s?%\s*(?:vector\s+|fill\s+)?opacity")


def _number(word: str) -> int:
    return _NUMBER_WORDS.get(word) or int(word)


def petal_parameters(signature: str, *, colour_field: str = "") -> dict:
    """§BH67(b)1 — the petals the concept's own words ask for: how many ("seven-to-nine" is eight, the middle of
    the range; "seven" is seven), how they are arranged (a FAN, a RADIAL bloom or cluster, a SCATTER), whether every
    second one is an outline ("alternating filled … and … outline"), how slender, at what opacity. Each value says
    where it came from; a value the words do not give is the generator's own default, and says so."""
    text = (signature or "").lower().replace("—", " ")
    out = {"count": None, "arrangement": None, "outline": "none", "width_ratio": 0.42, "opacity": None,
           "why": {}}
    m = _PETAL_COUNT_RE.search(_HOUSE_PETALS.sub("petals", text))
    if m:
        a = _number(m.group("a"))
        out["count"] = (a + _number(m.group("b"))) // 2 if m.group("b") else a
        out["why"]["count"] = m.group(0).strip()
    for arrangement, rx in (("fan", r"fan(?:s|ned|ning)?"), ("scatter", r"scatter\w*|strewn"),
                            ("radial", r"radial\w*|rosette\w*|cluster\w*|bloom\w*|wreath\w*|circle\w*|burst\w*")):
        hit = re.search(r"(?<![a-z])(?:%s)(?![a-z])" % rx, text)
        if hit:
            out["arrangement"], out["why"]["arrangement"] = arrangement, hit.group(0)
            break
    # a petal IS an outline only where the words say so; "spot-UV outline on each petal edge" is a finish on a filled
    # petal (task 88, measured), and belongs to the finish reader
    if re.search(r"alternat\w*[^;]*outline", text):
        out["outline"], out["why"]["outline"] = "alternate", "alternating filled and outline"
    elif re.search(r"(?<![a-z])(outline[\s-]+(?:forms?|petals?|shapes?)|in[\s-]+outline|outlined[\s-]+petals?|"
                   r"stroke-only|line-only)(?![a-z])", text):
        out["outline"], out["why"]["outline"] = "all", "the petals are outlines"
    if re.search(r"(?<![a-z])(slender|narrow|elongated|thin)(?![a-z])", text):
        out["width_ratio"], out["why"]["width_ratio"] = 0.28, "slender"
    op = _OPACITY_RE.search(text)
    # the colour-field sentence gives the petals' opacity where the motif sentence does not ("Deep Rose #8B3A52 at
    # 55% vector opacity on interior petals", task 91)
    field = next((c for c in re.split(r"[;\n]", (colour_field or "").lower()) if re.search(r"petal", c)), "")
    op = op or _OPACITY_RE.search(field)
    if op:
        out["opacity"], out["why"]["opacity"] = round(int(op.group(1)) / 100.0, 2), op.group(0)
    from apps.ire.design_language import PETAL_DEFAULTS
    for key in ("count", "arrangement"):
        if out[key] is None:
            out[key] = PETAL_DEFAULTS[key]
            out["why"][key] = "not in the words — the petal language's own default"
    return out


#: [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines."] the opacity a concept's "reduced opacity" is read as
#: when its words give no number — HALF, the executor's reading, recorded on the spec beside the words that asked for it;
#: a number in the words ("at 40% opacity") is always taken instead, and one line from the owner changes this one
REDUCED_OPACITY = 0.5
_REDUCED_OPACITY_RE = re.compile(r"(?<![a-z])(?:reduced|low|lowered|soft|faint|subtle)[\s-]+opacity(?![a-z])")
_RAY_NODE_RE = re.compile(r"(?<![a-z])(?:end|ends|ending|tipped|terminat\w*)(?![a-z])[^;,.]*?"
                          r"(?<![a-z])(?:nodes?|dots?|beads?|circles?)(?![a-z])")
_RAY_TAPER_RE = re.compile(r"(?<![a-z])(?:taper\w*|thinning|sparser|fewer)(?![a-z])[^;.]*?"
                           r"(?<![a-z])(?:rim|edge|edges|outward|perimeter)(?![a-z])")


def radial_parameters(signature: str) -> dict:
    """[the owner's second answer of 2026-09-25] The rays the concept's own words ask for — whether each ends in a node
    ("each ending in a small filled circular node"), whether they taper toward the rim ("density tapering toward the
    rim"), at what opacity ("at 40% opacity"; "at reduced opacity" is ``REDUCED_OPACITY``, said so). Each value says
    where it came from; a value the words do not give is the radial language's own default, and says so."""
    from apps.ire.design_language import RADIAL_DEFAULTS
    text = signature.lower() if signature is not None else ""
    out = {"rays": None, "nodes": False, "taper": False, "opacity": None, "why": {}}
    op = _OPACITY_RE.search(text)
    reduced = _REDUCED_OPACITY_RE.search(text)
    if op:
        out["opacity"], out["why"]["opacity"] = round(int(op.group(1)) / 100.0, 2), op.group(0)
    elif reduced:
        out["opacity"] = REDUCED_OPACITY
        out["why"]["opacity"] = ("%s — the words give no number: %.2f, the executor's reading (REDUCED_OPACITY)"
                                 % (reduced.group(0), REDUCED_OPACITY))
    for key, rx in (("nodes", _RAY_NODE_RE), ("taper", _RAY_TAPER_RE)):
        hit = rx.search(text)
        if hit:
            out[key], out["why"][key] = True, hit.group(0)
    for key in ("rays", "opacity"):
        if out[key] is None:
            out[key] = RADIAL_DEFAULTS[key]
            out["why"].setdefault(key, "not in the words — the radial language's own default")
    return out


def _field(value, *, source, verification):
    return {"value": value, "source": source, "verification": verification}


def build_motif_spec(structured: dict | None, visual_graph: dict | None,
                     zones: list[dict], profile_record: dict | None) -> dict:
    """Assemble container_motif_spec/1.0. Deterministic; no provider.

    * no structured motif signal → capability NONE (nothing to render)
    * a supported signal → capability SUPPORTED with requested_family +
      rendered_via
    * an unrebuildable signal → capability REVIEW_REQUIRED (fail closed, §3)
    """
    fields = (visual_graph or {}).get("fields") or {}
    signature = ""
    primary_signature = ""
    if structured:
        # 2B-3V-CORR-3 §2: the motif family is named by the MOTIF'S OWN
        # description (motif_signature + title). Composition vocabulary
        # ("flush-left editorial stack") describes layout, not the motif —
        # it is consulted only when the motif signature itself says nothing.
        primary_signature = " ".join(str(structured.get(k) or "") for k in (
            "motif_signature", "title"))
        signature = " ".join(str(structured.get(k) or "") for k in (
            "motif_signature", "title", "composition_signature"))
    # motif surfaces = confirmed body zones that can carry a field
    target = [(z.get("zone_id"), zone_surface(z)) for z in (zones or [])
              if zone_surface(z) in _MOTIF_SURFACES]
    target_surfaces = sorted({s for _, s in target})
    target_zones = [zid for zid, _ in target]

    spec: dict = {
        "schema_version": SCHEMA,
        "source_identity": (structured or {}).get("variation_id", ""),
        "selected_concept_relationship": "AUTHORED_FROM_SELECTED_VARIATION",
        "target_surfaces": target_surfaces,
        "target_zones": target_zones,
        "motif_bounds": fields.get("motif_centroid", {}).get("value")
        and {"centroid": fields["motif_centroid"]["value"]} or None,
        "motif_centroid": _field(
            fields.get("motif_centroid", {}).get("value"),
            source="LOCAL_IMAGE_ANALYSIS", verification=INFERRED)
        if fields.get("motif_centroid", {}).get("value") is not None
        else _field(None, source="UNKNOWN", verification=MISSING),
        "motif_density": _field(
            fields.get("motif_density", {}).get("value"),
            source="LOCAL_IMAGE_ANALYSIS", verification=INFERRED)
        if fields.get("motif_density", {}).get("value") is not None
        else _field(None, source="UNKNOWN", verification=MISSING),
        "motif_coverage": _field(
            (structured or {}).get("decorative_coverage_pct"),
            source="SELECTED_VARIATION_RECORD", verification=VERIFIED)
        if structured and structured.get("decorative_coverage_pct") is not None
        else _field(None, source="UNKNOWN", verification=MISSING),
        "scale_range": [0.7, 1.3],
        "rotation_range": [-15.0, 15.0],
        "repetition_behavior": "deterministic_seeded_field",
        "continuation_behavior": "reduced_on_secondary_surfaces",
        "opacity_range": [0.35, 1.0],
        "stroke_range": [0.12, 0.32],
        # §BH65(c)2: the concept's own finish sentence, clause by clause — this slot was ALWAYS {} from 2B-2A
        # until §BH65(c)2, and the finishes the concept named reached nothing that draws
        "finish_assignments": finish_assignments((structured or {}).get("finish_signature")),
    }

    if not signature.strip():
        spec.update({"requested_family": None, "rendered_via": None,
                     "motif_variant": None,
                     "reconstruction_capability": CAP_NONE,
                     "verification": MISSING})
        spec["motif_hash"] = motif_hash(spec)
        return spec

    requested_family = (classify_family(primary_signature)
                        or classify_family(signature))
    motif_words = str((structured or {}).get("motif_signature") or "")
    # [his answer W6] and a sentence naming the type alone ("type only", "the mark and the name alone") names none either
    if not requested_family and motif_words.strip() and not _TYPE_ONLY.sub(
            " ", _NEGATED.sub(" ", motif_words.lower())).strip(" ,.;:—-"):
        # §BH67(b)1: "no decorative motif, no botanical or floral element" names no motif — so none is drawn, and
        # the record says why. Until (b)1 the lexical fallback below read the WHOLE record, prompt and negations
        # included, and drew an "abstract botanical motif" for it (pinned as a defect in test_au3_divider_gates).
        spec.update({"requested_family": None, "rendered_via": None, "motif_variant": None,
                     "reconstruction_capability": CAP_NONE, "verification": VERIFIED,
                     "why_none": "the concept's own motif sentence names no motif: " + motif_words[:160]})
        spec["motif_hash"] = motif_hash(spec)
        return spec
    try:
        # 2B-3V-CORR-3 §2: a classified family routes through the HONEST
        # family→language map — never a second whole-text lexical vote (which
        # let three substring hits of "line/rule/graphic" outvote seven
        # occurrences of "constellation" and rendered task #51's dewdrops as
        # diagonal rules). Only an unclassified signature falls back to the
        # lexical resolver, which fails closed below its evidence floor.
        if requested_family:
            from apps.ire.design_language import get_language
            language = get_language(_FAMILY_TO_LANGUAGE[requested_family])
        else:
            # §BH67(b)1: a negated word never votes — "no floral element" summons no floral motif
            language = resolve_language(direction=None, variation={
                k: (_NEGATED.sub(" ", v.lower()) if isinstance(v, str) else v)
                for k, v in (structured or {}).items()})
        rendered_via = language.name
        approximate = requested_family in _APPROXIMATE_FAMILIES
        if rendered_via == "petal_bloom":
            # §BH67(b)1: the petals the concept's own words ask for, bound to the generator by language_for_spec
            spec["petals"] = petal_parameters(primary_signature,
                                              colour_field=str((structured or {}).get("color_field_signature") or ""))
        if rendered_via == "radial_lines":
            # [the owner's second answer of 2026-09-25: the rays the concept's own words ask for, bound the same way]
            spec["radial"] = radial_parameters(primary_signature)
        spec.update({
            "requested_family": requested_family,
            "rendered_via": rendered_via,
            "rendered_via_is_approximate": approximate,
            "motif_variant": language.label,
            "primary_swatches": list(language.defaults.swatches.to_dict())
            if language.defaults else [],
            "reconstruction_capability": CAP_SUPPORTED,
            "verification": VERIFIED,
        })
    except VectorReconstructionReviewRequired as exc:
        spec.update({
            "requested_family": requested_family,
            "rendered_via": None, "motif_variant": None,
            "reconstruction_capability": CAP_REVIEW_REQUIRED,
            "review_code": VECTOR_RECONSTRUCTION_REVIEW_REQUIRED,
            "review_detail": str(exc),
            "supported": list(getattr(exc, "supported", ()) or ()),
            "verification": MISSING,
        })
    spec["motif_hash"] = motif_hash(spec)
    return spec


def motif_hash(spec: dict) -> str:
    """Deterministic identity (no timestamps present)."""
    core = {k: spec.get(k) for k in (
        "schema_version", "source_identity", "requested_family",
        "rendered_via", "reconstruction_capability", "target_surfaces",
        "target_zones", "scale_range", "rotation_range",
        "repetition_behavior", "continuation_behavior")}
    return _hash(core)


def language_for_spec(spec: dict):
    """The DesignLanguage a SUPPORTED spec renders through (or None)."""
    if spec.get("reconstruction_capability") != CAP_SUPPORTED:
        return None
    from apps.ire.design_language import get_language
    try:
        language = get_language(spec.get("rendered_via") or "")
    except VectorReconstructionReviewRequired:
        return None
    if language.name == "petal_bloom" and spec.get("petals"):
        # §BH67(b)1: the concept's own count, arrangement and outline pattern, bound to the petal generator
        import functools
        from dataclasses import replace
        from apps.ire.design_language import gen_petal_bloom
        petals = {k: v for k, v in spec["petals"].items() if k != "why"}
        return replace(language, generators=(functools.partial(gen_petal_bloom, petals=petals),))
    if language.name == "radial_lines" and spec.get("radial"):
        # [the owner's second answer of 2026-09-25: the concept's own nodes, taper and opacity, bound to the rays]
        import functools
        from dataclasses import replace
        from apps.ire.design_language import gen_radial_lines
        radial = {k: v for k, v in spec["radial"].items() if k != "why"}
        return replace(language, generators=(functools.partial(gen_radial_lines, radial=radial),))
    return language


__all__ = [
    "SCHEMA", "FAMILIES", "CAP_SUPPORTED", "CAP_REVIEW_REQUIRED", "CAP_NONE",
    "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED", "classify_family",
    "build_motif_spec", "motif_hash", "language_for_spec",
    "REDUCED_OPACITY", "radial_parameters",
]
