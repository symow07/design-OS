"""Semantic distinctness for design directions — Phase 2A-2.

The `design_intent/1.0` contract enforces the *structural* floor (distinct names, axes,
layout strings, color strings). This module adds the *semantic* floor: three directions
that differ only in wording are still one idea, and the point of showing a user three
options is that they are three options.

Method: each direction is reduced to a bounded **signature** — one normalized category per
dimension, classified by deterministic keyword tables. No embeddings, no model call, no
similarity scores: the same text always classifies the same way, and a failure names the
dimension that collapsed.

Honesty rule for the classifier (tightened in 2A-2-CORR-1): unrecognized wording
classifies as `UNCLASSIFIED` and is reported as a diagnostic warning — but coverage is a
hard floor. A direction the tables largely cannot read fails with
`DIRECTION_SIGNATURE_INSUFFICIENT`, because a validator that cannot read two directions
cannot vouch that they differ. Raw wording differences alone are never sufficient; new
vocabulary earns acceptance by being added to the bounded tables, not by slipping through
them.
"""
from __future__ import annotations

import re as _re

UNCLASSIFIED = "UNCLASSIFIED"

#: Signature dimensions, and the direction field each is classified from.
SIGNATURE_DIMENSIONS = (
    ("axis", "design_axis"),
    ("composition_family", "layout_structure"),
    # §BH68(a): DECLARED by the planner from the known set (`HIERARCHY_FAMILY_NAMES`), never read from prose
    ("hierarchy_family", "hierarchy_family"),
    ("typography_family", "typography"),
    ("color_relationship", "color_system"),
    ("motif_family", "graphic_elements"),
    ("emotional_tone", "emotional_tone"),
)

#: §BH58(b) — SEVEN DIMENSIONS ARE DECLARED AND ONE OF THEM IS NOT A CLASSIFIER.
#: `axis` is a PASSTHROUGH: `direction_signature` lowercases the raw `design_axis`
#: prose for it and it is not in `_TABLES`. Measured over the twelve directions of
#: tasks 84-87: blank 0/12, and 12 distinct values in 12 directions. So it is never
#: UNCLASSIFIED and never equal between two directions — it contributes a guaranteed
#: +1 to every coverage count below AND to every pairwise difference. The pairwise
#: comment already admitted this; the coverage comment said "of the seven dimensions"
#: and did not. Seven declared = ONE passthrough + SIX classifiers. Stated here so it
#: is a fact of the module rather than something inferable from a function body.
PASSTHROUGH_DIMENSIONS = ("axis",)
#: Pairwise: two directions must differ in at least this many CLASSIFIED dimensions,
#: or they are paraphrases. The contract already guarantees distinct axes, so this
#: requires two further genuine differences per pair.
MIN_PAIRWISE_DIFFERENCES = 3
#: Fail-closed coverage floor (2A-2-CORR-1): a validator that cannot READ a direction
#: cannot vouch for its distinctness. Each direction must classify at least this many of
#: the seven declared dimensions — SIX classifiers plus the `axis` passthrough, which
#: always counts — and each pair must share at least this many mutually classified
#: dimensions, or the set fails with DIRECTION_SIGNATURE_INSUFFICIENT — wording the
#: tables don't know is grounds for refusal, never for a pass-with-warnings. New
#: vocabulary earns acceptance by being added to the bounded tables, not by slipping
#: through them.
#: §BH58(b): these three are NAILED by the owner — "MIN_MUTUAL_COMPARABLE_PER_PAIR
#: stays at 5 — I am not touching it and neither are you." A blind classifier was
#: repaired instead; no floor moved. `test_the_owner_nailed_thresholds_have_not_moved`
#: pins all three.
MIN_CLASSIFIED_PER_DIRECTION = 5
MIN_MUTUAL_COMPARABLE_PER_PAIR = 5

# --- keyword tables (bounded, deterministic; first match in order wins) ------------
COMPOSITION_FAMILIES = (
    ("CENTERED_EMBLEM", ("logo centered", "centered logo", "centered lockup",
                         "emblem centered", "centred logo")),
    ("TYPE_DOMINANT", ("oversized name", "type fills", "typography dominates",
                       "wordmark fills", "letterform", "type composition",
                       "name fills", "oversized serif", "oversized type")),
    ("PATTERN_WRAP", ("pattern wraps", "repeating pattern", "all faces", "allover",
                      "wraps all", "tiled")),
    ("MOTIF_FIELD", ("illustration", "engraving", "botanical field", "hero motif",
                     "motif carries", "drawn field", "mural")),
    ("MATERIAL_RELIEF", ("emboss", "deboss", "foil panel", "die-cut", "relief",
                         "sculpted", "debossed", "embossed")),
    ("ASYMMETRIC_SPLIT", ("split", "asymmetric", "off-center", "off-centre",
                          "diagonal", "two-panel", "corner-led", "cross-panel",
                          "continuing onto")),
    # A centered SYMMETRIC focal structure (halo/arch/radial) is distinct from
    # a centered LOGO emblem — the banned-set rule keys on CENTERED_EMBLEM
    # only, so this family is a legitimate composition (2A-6C).
    ("CENTERED_FOCAL", ("centered symmetric", "centred symmetric", "symmetrical",
                        "arched focal", "circular focal", "radial", "concentric",
                        "halo", "centered arch", "centred arch")),
    ("GRID_BANDED", ("band", "grid", "stacked", "horizon line", "ruled")),
)
HIERARCHY_FAMILIES = (
    ("NAME_FIRST", ("name first", "name leads", "name dominates", "product name is",
                    "title first", "name, then")),
    ("MOTIF_FIRST", ("motif first", "illustration leads", "pattern first",
                     "graphic leads", "image first", "motif leads", "droplet first")),
    ("MATERIAL_FIRST", ("material first", "finish leads", "emboss leads",
                        "foil first", "texture first", "finish first")),
    ("LOGO_FIRST", ("logo first", "brand mark first", "lockup first", "logo leads")),
)
#: §BH68(a), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "the planner DECLARES its hierarchy family from
#: the known set, nothing guesses it from prose". The known set is these four; the planner writes one of them in each
#: direction's `hierarchy_family` (design_intent/1.2) and the signature reads that declaration. Task 92's second
#: direction is why: "typography-led", its ordered hierarchy led by "Oversized ghosted Arabic letterform field", and
#: the §BH58(b) reader below classed it MOTIF_FIRST on the noun "field". The cue tables and that reader stay in the
#: module as the §BH58(b)/(c) record — `classify(text, "hierarchy_family")` still answers for the twelve directions of
#: tasks 84-87 — but the signature no longer consults them.
HIERARCHY_FAMILY_NAMES = tuple(family for family, _ in HIERARCHY_FAMILIES)


def declared_hierarchy_family(value) -> str:
    """The declared family in its canonical spelling, or UNCLASSIFIED — a declaration outside the known set, or none,
    is never guessed at. Case, spaces and hyphens are spelling, not meaning: "name first" is NAME_FIRST."""
    token = "_".join(str(value or "").strip().upper().replace("-", " ").split())
    return token if token in HIERARCHY_FAMILY_NAMES else UNCLASSIFIED

# §BH58(b) — READING A HIERARCHY WRITTEN AS AN ORDERED LIST.
#
# The cues above ask "which element leads" and expect the answer phrased as "name
# first" / "motif leads". The planner has NEVER ONCE written it that way. Measured over
# tasks 84-87, `hierarchy_family` was UNCLASSIFIED in 12 of 12 directions — a dimension
# implemented and blind, silently costing every direction one of its seven while the
# gate counted as though it had read something. The owner ruled that shut (§BH58(b),
# the §BH16 reading: silence grants nothing and must not quietly refuse either).
#
# What the planner writes instead, in three forms, all of which answer the SAME question
# better than the cue phrases do:
#     "1. Arc-contour radiance field -> 2. BBROSE rose-gold lockup -> 3. ..."
#     "First read: radiance arc field ... Second read: rose gold BBROSE lockup ..."
#     "Primary: diagonal ribbon-flow field. Secondary: BBROSE lockup in rose-gold foil."
#
# So: find the first ranked item, and classify what it NAMES.

#: Openers that mark an ordered hierarchy list.
_RANK_OPENERS = ("primary:", "primary -", "primary —", "first read:",
                 "first read -", "first read —", "1.", "1)", "1 -", "1 —",
                 "top:", "lead:", "leads with:", "first:")

#: Where the first ranked item ENDS. The locative patterns matter as much as the rank
#: markers: a locative phrase names the GROUND, not the figure. In "large-scale BBROSE
#: emboss-foil ON THE Warm Gold field" the element is the mark and the field is where it
#: sits, so without this the family would be decided by cue order over a span containing
#: both — and "the radiance field BEHIND the BBROSE lockup" would read LOGO_FIRST.
_LEAD_ENDINGS = (r"\u2192", r"->", r"\bsecond read\b", r"\bsecondary\b", r"\b2[.)]",
                 r"\bthen\b", r"\.", r";",
                 r"\bon the\b", r"\bbehind\b", r"\bover the\b", r"\babove\b",
                 r"\bwithin\b", r"\bagainst\b", r"\bbeneath\b", r"\bacross the\b")

#: What the leading element IS. ELEMENT NOUNS OUTRANK MATERIAL ADJECTIVES: "engraved
#: linework field" is a field made by engraving (MOTIF_FIRST), and MATERIAL_FIRST is for
#: a lead naming a finish with NO element noun. That rule is applied uniformly and it
#: costs: under it tasks 86 and 87 read MOTIF_FIRST three times and collapse. It was not
#: weakened afterwards to spare them.
_LEAD_ELEMENTS = (
    ("LOGO_FIRST", ("bbrose", "lockup", "logo", "brand mark", "brandmark", "wordmark",
                    "monogram")),
    ("NAME_FIRST", ("product name", "name block", "name panel", "the name",
                    "product title", "title block", "display type", "didone type",
                    "serif type", "type as the", "'rose glow'", "‘rose glow’")),
    ("MOTIF_FIRST", ("field", "pattern", "illustration", "motif", "mandala", "ribbon",
                     "arc", "bloom", "petal", "graphic", "tessellation", "linework",
                     "engraving", "rosette", "lattice", "veil", "burst", "scatter")),
    ("MATERIAL_FIRST", ("emboss", "deboss", "foil", "relief", "texture", "finish",
                        "varnish", "spot-uv", "spot uv", "gloss", "matte")),
)


def hierarchy_lead_segment(text: str) -> str:
    """The first ranked item of an ordered hierarchy, or "" when it is not ordered.

    Public so a caller can SEE what was read — an empty return is a measured outcome
    (the text is not an ordered list), never a swallowed failure.
    """
    joined = " ".join(str(text or "").split())
    low = joined.lower()
    start = None
    for opener in _RANK_OPENERS:
        index = low.find(opener)
        if index != -1 and (start is None or index < start):
            start = index + len(opener)
    if start is None:
        return ""
    rest = joined[start:]
    cut = len(rest)
    for pattern in _LEAD_ENDINGS:
        match = _re.search(pattern, rest, flags=_re.I)
        if match and match.start() < cut:
            cut = match.start()
    return rest[:cut].strip()


def _classify_hierarchy(text) -> str:
    """The cue tables first, then the ordered-list reader (§BH58(b))."""
    normalized = f" {strip_negated_spans(text)} "
    for family, keywords in HIERARCHY_FAMILIES:
        if any(keyword in normalized for keyword in keywords):
            return family
    lead = hierarchy_lead_segment(text).lower()
    if lead:
        for family, keywords in _LEAD_ELEMENTS:
            if any(keyword in lead for keyword in keywords):
                return family
    return UNCLASSIFIED
# Typography is classified by a dedicated function (_classify_typography),
# NOT this flat table — see below. The taxonomy is fine-grained (2A-6C-CORR):
# two sans systems that differ in width/construction (a condensed editorial
# grotesk vs a rounded geometric sans) must NOT collapse into one class. The
# table remains only so the dimension is registered; classify() routes
# typography to the richer function.
TYPOGRAPHY_FAMILIES = ()

# Cue vocabularies for typographic INTENT (serif/sans, width, geometry,
# contrast, construction). Deterministic, no model call — the richer signal
# comes from reading more of the description, not from a similarity score.
_SCRIPT_CUES = ("script", "calligraph", "hand-lettered", "handwritten", "cursive")
#: THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"): "The
#: planner refusals on tasks 106 and 109." Task 109 was refused TYPOGRAPHY_NOT_DISTINCT with all three directions read
#: SCRIPT_LED, and two of the three were not script faces: "condensed geometric sans, light, both scripts" — the SCRIPTS
#: there are the Latin and Arabic WRITING SYSTEMS. The cue was matched as a bare substring, so it also read "script"
#: inside "descriptor" (tasks 47, 92, 102 — 102's own TYPOGRAPHY_NOT_DISTINCT was that misread). Measured over the record:
#: 45 of 141 typography texts read SCRIPT_LED and 27 of those rested on nothing else. A cue now counts only where a WORD
#: begins with it, and a writing-system phrase is set aside before the cues are read. The authority is his order;
#: the method is the one §BH58(b) ruled for the hierarchy classifier — fix the reading, move no threshold.
_WRITING_SYSTEM_RE = _re.compile(
    r"\b(?:both|two|the two|all|each|either|neither|every|multiple|several|latin|arabic|english|roman|cyrillic|"
    r"greek|hebrew|chinese|japanese|korean|thai|devanagari|bilingual|dual)\s+scripts?\b"
    r"|\bscripts?\s+(?:support|coverage)\b|\bmulti-?script\b")
_SCRIPT_CUE_RE = _re.compile(r"\b(?:" + "|".join(_re.escape(c) for c in _SCRIPT_CUES) + ")")
_SERIF_WORDS = ("serif", "didone", "roman", "slab", "antiqua", "garald",
                "transitional serif")
_SANS_WORDS = ("sans", "grotesk", "grotesque", "gothic")
_MIX_PHRASES = ("serif with sans", "serif against", "paired with a sans",
                "sans for support", "serif for the name", "serif for the product",
                "serif paired", "serif and sans", "serif plus sans",
                "serif alongside", "serif for the primary", "serif with a sans",
                "sans for the supporting", "serif headline with a sans")
_CONDENSED_CUES = ("condensed", "compressed", "narrow", "editorial grotesk",
                   "editorial sans", "condensed grotesk", "tall and narrow")
_GEOMETRIC_CUES = ("geometric", "rounded", "circular", "geometric face",
                   "geometric sans")
_HUMANIST_CUES = ("humanist", "humanistic", "calligraphic sans", "open aperture")
_NEUTRAL_CUES = ("neutral grotesk", "grotesk", "grotesque", "gothic",
                 "helvetica", "swiss")
_HIGH_CONTRAST_CUES = ("high-contrast", "high contrast", "didone", "modern serif",
                       "hairline serif", "fine-contrast", "sharp contrast")
_DISPLAY_SERIF_CUES = ("display serif", "slab", "chunky serif", "fat serif")
_CUSTOM_CUES = ("custom letterform", "bespoke letter", "custom lettering",
                "logotype-led", "wordmark drawn")
_MINIMAL_CUES = ("minimal type", "restrained type", "understated typography",
                 "type-minimal", "pared-back type", "quiet typography")
_TYPE_AS_IMAGE_CUES = ("type-as-image", "type as image", "monumental type",
                       "typographic mural", "letters as the artwork",
                       "type is the artwork", "typography is the artwork",
                       "oversized stacked")


#: Cues that flip the rest of a sentence segment from a proposal into a
#: prohibition/contrast. Shared by typography classification and the
#: content-faithfulness validators (2A-6D).
NEGATION_SPAN_CUES = (
    "not ", "never ", "no ", "n't ", "avoid", "without", "rather than",
    "instead of", "must not", "do not", "don't", "cannot", "refrain",
    "distinct from", "unlike",
    # "Zero photographic imagery" is a compliance DECLARATION — the replan of
    # task #50 was rejected because this cue was missing and the declaration
    # itself matched _PHOTO_TERMS (PRODUCTION_RASTER_DEPENDENCY ×3).
    "zero ", "free of ", "-free ",
    # Contrast phrases (2A-6D-CORR-2 §5): "materially different from the
    # high-contrast serif of direction 2" describes what this direction is
    # NOT — the retry's Powder Drift classified MIXED_SERIF_SANS because
    # only "distinct from" was recognized. Span-truncation keeps what comes
    # BEFORE the cue, so "uses a serif, different from direction 1" still
    # classifies as serif.
    "different from", "differs from", "different than", "contrasted with",
    "in contrast to",
)
_SENTENCE_SPLIT_RE = None      # initialized lazily below (needs _re)


def strip_negated_spans(text: str) -> str:
    """Text with every negated/contrastive SPAN removed.

    Splits on sentence-level separators only ([.;:\\n]) and, within each
    segment, cuts from the earliest negation cue to the segment end — so
    "geometric uppercase sans — distinct from the serif and script of other
    directions" keeps the sans and drops the contrast, and "No decorative
    script" disappears entirely. Clause splitters like "and"/"," are NOT used
    here: they sever a negation from the words it governs.
    """
    global _SENTENCE_SPLIT_RE
    if _SENTENCE_SPLIT_RE is None:
        _SENTENCE_SPLIT_RE = _re.compile(r"[.;:\n]")
    joined = " ".join(str(text or "").lower().split())
    kept = []
    for segment in _SENTENCE_SPLIT_RE.split(joined):
        segment = f" {segment.strip()} "
        cut = min((segment.find(cue) for cue in NEGATION_SPAN_CUES
                   if cue in segment), default=-1)
        remainder = segment[:cut].strip() if cut >= 0 else segment.strip()
        if remainder:
            kept.append(remainder)
    return " . ".join(kept)


def _has(text, cues):
    return any(cue in text for cue in cues)


def _has_serif(text):
    """A serif CUE that is not merely the 'serif' inside 'sans-serif'."""
    residue = text.replace("sans-serif", " ").replace("sans serif", " ") \
                  .replace("sanserif", " ")
    return _has(residue, _SERIF_WORDS)


def _script_hits(text):
    """The script-face cues in ``text`` — each at the START of a word, a writing-system phrase set aside first."""
    return [m.group(0) for m in _SCRIPT_CUE_RE.finditer(_WRITING_SYSTEM_RE.sub(" ", text))]


def _hits(text, cues):
    return [cue for cue in cues if cue in text]


#: every kind the typography reader returns, in the order it tests them — the known set the aimed repair names
TYPOGRAPHY_KINDS = ("SCRIPT_LED", "MIXED_SERIF_SANS", "CONDENSED_EDITORIAL_SANS", "GEOMETRIC_ROUNDED_SANS",
                    "HUMANIST_SANS", "NEUTRAL_GROTESK", "SANS_LED", "HIGH_CONTRAST_SERIF", "DISPLAY_SERIF", "SERIF_LED",
                    "TYPE_AS_IMAGE", "CUSTOM_LETTERFORM", "TYPE_MINIMAL")


def _typography_reading(text):
    """``(kind, words)``: `_classify_typography`'s verdict and the words that decided it — so the repair loop can
    name what the validator READ (§BH68(a)), for typography as for every other dimension."""
    t = f" {strip_negated_spans(text)} "
    script = _script_hits(t)
    if script:
        return "SCRIPT_LED", script
    residue = t.replace("sans-serif", " ").replace("sans serif", " ").replace("sanserif", " ")
    serif, sans, mix = _hits(residue, _SERIF_WORDS), _hits(t, _SANS_WORDS), _hits(t, _MIX_PHRASES)
    if mix or (serif and sans):
        return "MIXED_SERIF_SANS", mix + serif + sans
    if sans:
        for kind, cues in (("CONDENSED_EDITORIAL_SANS", _CONDENSED_CUES), ("GEOMETRIC_ROUNDED_SANS", _GEOMETRIC_CUES),
                           ("HUMANIST_SANS", _HUMANIST_CUES), ("NEUTRAL_GROTESK", _NEUTRAL_CUES)):
            words = _hits(t, cues)
            if words:
                return kind, sans + words
        return "SANS_LED", sans
    if serif:
        for kind, cues in (("HIGH_CONTRAST_SERIF", _HIGH_CONTRAST_CUES), ("DISPLAY_SERIF", _DISPLAY_SERIF_CUES)):
            words = _hits(t, cues)
            if words:
                return kind, serif + words
        return "SERIF_LED", serif
    for kind, cues in (("TYPE_AS_IMAGE", _TYPE_AS_IMAGE_CUES), ("CUSTOM_LETTERFORM", _CUSTOM_CUES),
                       ("TYPE_MINIMAL", _MINIMAL_CUES)):
        words = _hits(t, cues)
        if words:
            return kind, words
    return UNCLASSIFIED, []


def _classify_typography(text):
    """Fine-grained typographic-system classification (2A-6C-CORR §5).

    Distinguishes serif/sans, width (condensed), geometry (geometric/rounded,
    humanist, grotesk) and contrast, so two DIFFERENT sans systems are two
    different classes. Order matters: a serif+sans pairing is MIXED before any
    single-family verdict; specific sans subclasses precede the generic
    NEUTRAL_GROTESK / SANS_LED fallbacks; and bare-'serif' SERIF_LED is only
    reached after the sans branch, so 'sans-serif' can never read as serif.

    Negated mentions are stripped BEFORE matching (2A-6D): task #50's
    "No decorative script" classified as SCRIPT_LED, and "distinct from the
    serif and script of other directions" did the same — a description of
    what the typography is NOT must never classify it.

    [THE OWNER'S SECOND ANSWER OF 2026-09-25: the verdict is `_typography_reading`'s — the same order and the same
    cues, a script cue now counting only at the start of a word and never in a writing-system phrase (task 109).]
    """
    return _typography_reading(text)[0]


COLOR_RELATIONSHIPS = (
    ("HIGH_CONTRAST", ("high contrast", "black and white", "stark", "high-contrast")),
    ("DARK_JEWEL", ("deep ", "dark ", "jewel", "midnight", "forest", "oxblood")),
    ("MONOCHROME_ACCENT", ("monochrome", "single accent", "one accent",
                           "single saturated")),
    ("TONAL_PASTEL", ("pastel", "tonal", "blush tones", "soft gradient", "powdery")),
    ("NEUTRAL_METALLIC", ("rose gold", "gold ", "metallic", "foil", "porcelain",
                          "ivory", "champagne", "nude ")),
)
# NONE_MATERIAL stays FIRST (raw-text precheck) so "no illustration … tiny
# powder-dot accent" reads as effectively-no-motif rather than as a powder
# motif. Motif classification is SCORED, not first-match (2A-6D-CORR-2 §6):
# specific evidence outranks generic shape evidence, so "dot particles
# rendered as circles" is PARTICLE_FLOW even though GEOMETRIC_ABSTRACT sits
# earlier in the table and matches "circles". GEOMETRIC_HALO (halo /
# concentric ring systems) is its own family: a centered halo crown and a
# generic abstract composition are different motif systems.
MOTIF_FAMILIES = (
    ("NONE_MATERIAL", ("no motif", "none;", "material only", "finish only",
                       "no graphic", "unadorned", "no illustration",
                       "no main illustration", "typography is the artwork",
                       "type is the artwork", "no hero motif")),
    ("BOTANICAL", ("botanical", "floral", "petal", "leaf", "rose ", "flower")),
    ("LIQUID", ("droplet", "water", "dew", "liquid", "wave", "ripple", "fluid")),
    ("LINEAR_ENGRAVED", ("engrav", "etched", "line art", "linework", "keyline",
                         "fine line")),
    ("PATTERN_REPEAT", ("pattern", "repeat", "tile", "lattice")),
    ("GEOMETRIC_HALO", ("halo", "concentric", "radial ring", "ring of light",
                        "arc crown")),
    ("GEOMETRIC_ABSTRACT", ("geometric", "abstract", "grid", "circles", "arcs",
                            "arc", "radiance", "radial", "sunburst",
                            "contour")),
    ("PARTICLE_FLOW", ("powder", "particle", "veil", "mist", "stream",
                       "drift", "flowing movement", "soft movement",
                       "movement across")),
)
#: Families whose cues are generic shape vocabulary — they win only when no
#: specific system out-scores them (2A-6D-CORR-2 §6).
_GENERIC_MOTIF_FAMILIES = frozenset({"GEOMETRIC_ABSTRACT"})
TONE_FAMILIES = (
    # "soft" is deliberately NOT a keyword: this brief (and most pastel
    # cosmetics briefs) says "soft" in every direction, so classifying it
    # would collapse the tone dimension. Directions earn a tone from their
    # DISTINCTIVE word (refined / serene / fresh / …), not from "soft".
    ("SERENE", ("serene", "calm", "quiet", "tranquil", "hushed", "still",
                "luminous")),
    ("OPULENT", ("opulent", "luxurious", "lavish", "rich", "sumptuous", "decadent")),
    ("ROMANTIC", ("romantic", "tender", "intimate", "dreamy", "soft-hearted")),
    ("REFINED", ("refined", "elegant", "understated", "sophisticated",
                 "polished", "editorial", "restrained")),
    ("FRESH", ("fresh", "crisp", "clean", "dewy", "bright morning", "airy",
               "radiant", "light and airy")),
    ("DRAMATIC", ("dramatic", "bold", "striking", "intense", "theatrical")),
    ("PLAYFUL", ("playful", "joyful", "whimsical", "lively")),
    ("CLINICAL", ("clinical", "precise", "laboratory", "scientific", "exacting")),
)
_TABLES = {
    "composition_family": COMPOSITION_FAMILIES,
    "hierarchy_family": HIERARCHY_FAMILIES,
    "typography_family": TYPOGRAPHY_FAMILIES,
    "color_relationship": COLOR_RELATIONSHIPS,
    "motif_family": MOTIF_FAMILIES,
    "emotional_tone": TONE_FAMILIES,
}
#: Dimension → the stable reason code emitted when all three directions collapse into
#: one classified family on that dimension.
COLLAPSE_CODES = {
    "typography_family": "TYPOGRAPHY_NOT_DISTINCT",
    "motif_family": "MOTIF_NOT_DISTINCT",
    "hierarchy_family": "HIERARCHY_NOT_DISTINCT",
    "emotional_tone": "EMOTIONAL_TONE_NOT_DISTINCT",
}

#: [His correction of 2026-10-07] the three share the motif his brief asks for and one composition family: they do not
#: differ by layout. Raised only where the motif collapse was excused for his brief.
COMPOSITION_NOT_DISTINCT = "COMPOSITION_NOT_DISTINCT"

#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (2): "Every "not
#: distinct" check: it never stops a design. On failure it retries once with the reason; if it still fails, it shows me
#: the three anyway with a note, and I choose."]
#: Every check that three directions are too alike: the collapse codes above, the layout check his correction added,
#: the paraphrase floor, the coverage floor (the check cannot read the three apart enough to vouch for them — the
#: executor's reading, his to veto: its floors stay where he nailed them, only what a miss does changes), the palette and
#: shared-motif checks, and the plan's own word-for-word duplicates of idea, layout and colours. A set refused by these
#: and nothing else is shown to him after its one retry, with a note. A duplicate id or name stays a refusal: they are
#: how he and the record tell the three apart.
ALIKE_CODES = frozenset(COLLAPSE_CODES.values()) | frozenset({
    COMPOSITION_NOT_DISTINCT, "DIRECTIONS_SUPERFICIALLY_VARIANT", "DIRECTION_SIGNATURE_INSUFFICIENT",
    "PALETTE_SYSTEMS_NOT_DISTINCT", "DIRECTIONS_SHARE_CORE_MOTIF",
    "DUPLICATE_DESIGN_AXIS", "DUPLICATE_LAYOUT_STRUCTURE", "DUPLICATE_COLOR_SYSTEM"})
#: … the key the planning's own record and the concept step's carry them under, read for the note beside the three
SHOWN_ALIKE_KEY = "shown_alike"


#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (1): "In a
#: Complete Product, the carton CONTINUES the approved container: same mood, motif, colours, type and logo treatment as
#: 122's approved tube (red line-art roses, oval window, blush pink). Its three options differ only by layout and
#: composition on the carton (e.g. full all-over pattern / oval window front / pattern band + clean panels), never by
#: mood or personality. The distinctness checks for mood, colour and motif don't apply to it."]
#: What a design continuing its container is read apart by: its layout alone — its idea, its composition and its
#: hierarchy, each pair differing in two of them (the idea, which every pair differs in, and one more); and the checks
#: that do not apply to it — its three share the container's mood, motif, colours and type (the executor's reading of
#: "colour" and "type": the palette check and the word-for-word colours, and the type check — his to veto).
LAYOUT_DIMENSIONS = ("axis", "composition_family", "hierarchy_family")
CONTINUATION_MIN_PAIRWISE_DIFFERENCES = 2
CONTINUATION_STANDS_DOWN = frozenset({
    "EMOTIONAL_TONE_NOT_DISTINCT", "MOTIF_NOT_DISTINCT", "TYPOGRAPHY_NOT_DISTINCT", "PALETTE_SYSTEMS_NOT_DISTINCT",
    "DIRECTIONS_SHARE_CORE_MOTIF", "DUPLICATE_COLOR_SYSTEM"})


def stands_down(code) -> bool:
    """Whether ``code`` is a check that does not apply to a design continuing its approved container."""
    return str(code).split(":", 1)[0].strip() in CONTINUATION_STANDS_DOWN


def alike_code(code) -> bool:
    """Whether ``code`` — its own text, with or without a ": …" or ":direction[i]" tail — is a "not distinct" check."""
    return str(code).split(":", 1)[0].strip() in ALIKE_CODES


def shown_alike(result):
    """What a step's record keeps of three shown though too alike — their codes, which attempts came back refused for
    that alone and how many were made — or None where they passed (a result from before carries neither)."""
    codes = result.alike if isinstance(getattr(result, "alike", None), tuple) else ()
    if not codes:
        return None
    return {"codes": list(codes), "alike_attempts": list(result.alike_attempts), "attempts": int(result.attempts)}

#: A direction may study references; it may not instruct reproduction of them.
#: A hit requires an AFFIRMATIVE copy verb governing a prior-work target WITHIN
#: ONE CLAUSE (2A-6C). The old check ANDed a verb and a target as bare
#: substrings across the whole text, so a direction that CORRECTLY forbids
#: copying — "the reference must not be traced or copied; reconstruct as native
#: vectors" — was flagged as an originality violation. The brief pushes exactly
#: that native-vector / "temporary reference only" language, so the false
#: positive fired routinely.
_COPY_VERBS = ("copy", "copies", "copied", "copying",
               "replicate", "replicates", "replicated",
               "reproduce", "reproduces", "reproduced",
               "trace", "traces", "traced", "tracing",
               "duplicate", "duplicates", "duplicated",
               "recreate", "recreates", "recreated", "mimic", "clone")
_COPY_TARGETS = ("reference", "historical", "existing design", "past bbrose",
                 "original artwork", "competitor", "the attached", "old layout",
                 "previous design", "prior artwork", "the reference image")
#: Explicit reproduction phrases — a violation regardless of clause structure.
_COPY_PHRASES = ("identical to the", "exactly like the", "same as the reference",
                 "pixel-for-pixel", "one-to-one recreation", "carbon copy of")
#: Negation cues that flip a copy verb from an instruction into a prohibition.
#: A verb governed by any of these in its clause is anti-copy language, not a
#: violation.
_NEGATIONS = ("not", "never", "no ", "n't", "avoid", "without", "rather than",
              "instead of", "must not", "do not", "don't", "cannot", "refrain")


#: Prefix tolerance for token matching: a cue matches a token it starts when
#: the token adds at most this many characters ("particle"→"particles",
#: "engrav"→"engraving" — but never "arc"→"architecture").
_PREFIX_SLACK = 3


def _classify_scored(text, table, *, prefix_tokens=False, generic=frozenset()):
    """Evidence-scored classification (2A-6D-CORR-2 §4/§6).

    First-substring-wins classified all three retry tones as SERENE because
    "quietly" contains "quiet". Here every family scores its DISTINCT cue
    hits and the best score wins:

      * single-word cues match whole tokens (hyphens split, so "spa-calm"
        yields "calm" but "quietly" never yields "quiet"); with
        ``prefix_tokens`` a cue also matches tokens it starts, bounded by
        _PREFIX_SLACK — motif cues are stems ("engrav", "particle");
      * phrase cues (with a space) match as substrings and score 3 — a
        specific phrase beats a generic word;
      * word cues score 2, or 1 for families in ``generic`` — specific
        systems outrank generic shape vocabulary;
      * ties break to table order, deterministically; zero evidence is
        UNCLASSIFIED.
    """
    stripped = strip_negated_spans(text).replace("-", " ")
    normalized = f" {stripped} "
    tokens = set(_re.findall(r"[a-z0-9]+", stripped))
    best_family, best_score = UNCLASSIFIED, 0
    for family, cues in table:
        word_score = 1 if family in generic else 2
        score = 0
        for cue in cues:
            cue_text = cue.strip().replace("-", " ")
            if " " in cue_text:
                if cue_text in normalized:
                    score += 3
            elif any(token == cue_text
                     or (prefix_tokens and token.startswith(cue_text)
                         and len(token) <= len(cue_text) + _PREFIX_SLACK)
                     for token in tokens):
                score += word_score
        if score > best_score:
            best_family, best_score = family, score
    return best_family


def classify(text, dimension) -> str:
    """Deterministic classification. Typography routes to the fine-grained
    _classify_typography (2A-6C-CORR); motif and emotional tone use scored
    classification (2A-6D-CORR-2 — specific evidence beats generic shape
    words, and "quietly" never matches the cue "quiet"); the remaining
    dimensions use their keyword table, first match in order winning.

    Negated spans are stripped before matching (2A-6D): "no centered halo"
    must not classify as a halo motif. The one exception is checked FIRST on
    the raw text: NONE_MATERIAL's own keywords ("no motif", "no illustration")
    ARE negation phrases — they state the absence that defines the family.
    """
    if dimension == "typography_family":
        return _classify_typography(text)
    raw = f" {' '.join(str(text).lower().split())} "
    if dimension == "motif_family":
        none_keywords = dict(MOTIF_FAMILIES)["NONE_MATERIAL"]
        if any(keyword in raw for keyword in none_keywords):
            return "NONE_MATERIAL"
        return _classify_scored(
            text, MOTIF_FAMILIES[1:], prefix_tokens=True,
            generic=_GENERIC_MOTIF_FAMILIES)
    if dimension == "emotional_tone":
        return _classify_scored(text, TONE_FAMILIES)
    if dimension == "hierarchy_family":
        return _classify_hierarchy(text)
    normalized = f" {strip_negated_spans(text)} "
    for family, keywords in _TABLES[dimension]:
        if any(keyword in normalized for keyword in keywords):
            return family
    return UNCLASSIFIED


def known_families(dimension) -> tuple:
    """§BH68(a): the families a dimension can read — the known set the repair loop names when it moves a direction.
    The fine-grained typography reader keeps no flat table, so its guidance names kinds instead (below)."""
    if dimension == "hierarchy_family":
        return HIERARCHY_FAMILY_NAMES
    if dimension == "typography_family":
        return TYPOGRAPHY_KINDS               # the owner's second answer of 2026-09-25: the repair names typography's kinds
    return tuple(family for family, _ in _TABLES.get(dimension) or ())


def classification_evidence(text, dimension) -> list:
    """§BH68(a): the words in ``text`` that decided its family on ``dimension`` — what the validator READ, so the
    repair loop can name them and the second attempt can remove them. Empty where nothing classified, and for the
    dimensions that are not read from words (the axis passthrough, the declared hierarchy family) or that have no
    flat cue table (typography)."""
    if dimension in ("axis", "hierarchy_family"):
        return []
    if dimension == "typography_family":
        # the owner's second answer of 2026-09-25: typography names the words that decided it, like every other
        # dimension — task 109's repair said "reads SCRIPT_LED from its typography" and named no word
        return _typography_reading(text)[1]
    family = classify(text, dimension)
    if family == UNCLASSIFIED:
        return []
    cues = dict(_TABLES[dimension]).get(family, ())
    if dimension == "motif_family" and family == "NONE_MATERIAL":
        raw = f" {' '.join(str(text).lower().split())} "
        return [cue.strip() for cue in cues if cue in raw]
    stripped = strip_negated_spans(text)
    if dimension in ("motif_family", "emotional_tone"):
        spaced = stripped.replace("-", " ")
        normalized = f" {spaced} "
        tokens = set(_re.findall(r"[a-z0-9]+", spaced))
        found = []
        for cue in cues:
            cue_text = cue.strip().replace("-", " ")
            if " " in cue_text:
                hit = cue_text in normalized
            else:
                hit = any(token == cue_text or (dimension == "motif_family" and token.startswith(cue_text)
                                                and len(token) <= len(cue_text) + _PREFIX_SLACK)
                          for token in tokens)
            if hit:
                found.append(cue.strip())
        return found
    normalized = f" {stripped} "
    return [keyword.strip() for keyword in cues if keyword in normalized]


def direction_signature(direction) -> dict:
    """The bounded, machine-readable signature of one direction."""
    signature = {}
    for dimension, field in SIGNATURE_DIMENSIONS:
        value = direction.get(field, "")
        if dimension == "axis":
            signature[dimension] = " ".join(str(value).lower().split())
        elif dimension == "hierarchy_family":
            signature[dimension] = declared_hierarchy_family(value)        # §BH68(a): declared, never guessed
        else:
            signature[dimension] = classify(value, dimension)
    return signature


def validate_semantic_distinctness(directions, *, asked_motif_families=(), continuation=False):
    """`(codes, warnings)` for a structurally valid three-direction set.

    [His correction of 2026-10-07: "a motif my brief asks for may appear in all three directions; they must still
    differ by idea, layout and type."] ``asked_motif_families`` — the families of the motifs his brief asks for
    (``direction_content.asked_motif_families``): all three reading one of them is not MOTIF_NOT_DISTINCT. The three
    must then still differ — by idea (no two the same design_axis: DIRECTIONS_SUPERFICIALLY_VARIANT), by layout (not
    one composition family across all three: COMPOSITION_NOT_DISTINCT) and by type (TYPOGRAPHY_NOT_DISTINCT, as for
    every set). The executor's reading of "differ", his to veto: not all three alike, the sense every collapse code
    here has.

    * insufficient classified coverage (per direction, or mutually per pair) →
      DIRECTION_SIGNATURE_INSUFFICIENT — the validator refuses to vouch for what it
      cannot read;
    * a dimension where all three CLASSIFIED values are equal → its collapse code;
    * a pair differing in fewer than MIN_PAIRWISE_DIFFERENCES classified dimensions →
      DIRECTIONS_SUPERFICIALLY_VARIANT (paraphrase floor);
    * all three compositions CENTERED_EMBLEM → DIRECTIONS_SUPERFICIALLY_VARIANT (the
      banned centered-logo-on-a-box set, whatever the colors say);
    * a dimension where nothing classified → a warning, never a verdict.

    ``continuation`` ([his test blocker on design 123, 2026-10-09, (1)]): the three continue an approved container — they
    are read apart by layout alone (``LAYOUT_DIMENSIONS``): no collapse code for their shared mood, motif or type; not one
    composition family in all three (COMPOSITION_NOT_DISTINCT); each pair differing in
    ``CONTINUATION_MIN_PAIRWISE_DIFFERENCES`` of the layout's dimensions. The coverage floors stand as he nailed them.
    """
    signatures = [direction_signature(direction) for direction in directions]
    codes, warnings = [], []
    dimension_names = [dimension for dimension, _ in SIGNATURE_DIMENSIONS]

    # fail-closed coverage floor: enough classified evidence to compare at all
    for index, signature in enumerate(signatures):
        classified = sum(1 for dimension in dimension_names
                         if signature[dimension] not in ("", UNCLASSIFIED))
        if classified < MIN_CLASSIFIED_PER_DIRECTION:
            codes.append("DIRECTION_SIGNATURE_INSUFFICIENT")
            warnings.append(f"SIGNATURE_COVERAGE_direction[{index}]:{classified}/7")
    for first in range(len(signatures)):
        for second in range(first + 1, len(signatures)):
            mutual = sum(
                1 for dimension in dimension_names
                if signatures[first][dimension] not in ("", UNCLASSIFIED)
                and signatures[second][dimension] not in ("", UNCLASSIFIED))
            if mutual < MIN_MUTUAL_COMPARABLE_PER_PAIR:
                codes.append("DIRECTION_SIGNATURE_INSUFFICIENT")

    excused = None
    for dimension, code in COLLAPSE_CODES.items():
        if continuation and dimension not in LAYOUT_DIMENSIONS:
            continue                                # [his blocker on 123, (1)] shared with the container, by his rule
        values = [signature[dimension] for signature in signatures]
        classified = [value for value in values if value != UNCLASSIFIED]
        if len(classified) == len(values) and len(set(classified)) == 1:
            if dimension == "motif_family" and classified[0] in set(asked_motif_families or ()):
                excused = classified[0]             # his brief asks for it: it may stand in all three
                continue
            codes.append(code)
        elif not classified:
            warnings.append(f"UNCLASSIFIED_{dimension.upper()}")
    if excused is not None and len(signatures) >= 3:
        layouts = [signature["composition_family"] for signature in signatures]
        if UNCLASSIFIED not in layouts and len(set(layouts)) == 1:
            codes.append(COMPOSITION_NOT_DISTINCT)
        axes = [signature["axis"] for signature in signatures if signature["axis"]]
        if len(set(axes)) < len(axes):
            codes.append("DIRECTIONS_SUPERFICIALLY_VARIANT")

    if continuation and len(signatures) >= 3:
        # [his blocker on 123, (1)] "Its three options differ only by layout and composition"
        layouts = [signature["composition_family"] for signature in signatures]
        if UNCLASSIFIED not in layouts and len(set(layouts)) == 1:
            codes.append(COMPOSITION_NOT_DISTINCT)

    if all(signature["composition_family"] == "CENTERED_EMBLEM"
           for signature in signatures):
        codes.append("DIRECTIONS_SUPERFICIALLY_VARIANT")

    compared = LAYOUT_DIMENSIONS if continuation else dimension_names
    floor = CONTINUATION_MIN_PAIRWISE_DIFFERENCES if continuation else MIN_PAIRWISE_DIFFERENCES
    for first in range(len(signatures)):
        for second in range(first + 1, len(signatures)):
            differences = 0
            for dimension in compared:
                left = signatures[first][dimension]
                right = signatures[second][dimension]
                if UNCLASSIFIED in (left, right):
                    continue                      # unknown wording never counts either way
                if left != right:
                    differences += 1
            if differences < floor:
                codes.append("DIRECTIONS_SUPERFICIALLY_VARIANT")
    return sorted(set(codes)), sorted(set(warnings))


#: Clause boundaries: sentence enders plus the connectives that separate an
#: instruction from a prohibition ("reconstruct as vectors; do not trace it").
_CLAUSE_SPLIT = _re.compile(r"[.;:\n]|,\s|\band\b|\bbut\b|\bwhile\b|\bwhereas\b")
_WORD = _re.compile(r"[a-z0-9'\-]+")


def _clause_is_affirmative_copy(clause: str) -> bool:
    """True when a clause AFFIRMATIVELY instructs copying a prior-work target.

    A copy verb + a prior-work target must both sit in the clause, and the
    clause must not be negated. "must not be traced or copied from the
    reference" is a prohibition (negated) → not a violation.
    """
    if not any(target in clause for target in _COPY_TARGETS):
        return False
    words = set(_WORD.findall(clause))
    if not (words & set(_COPY_VERBS)):        # exact tokens (inflections listed)
        return False
    if any(neg in clause for neg in _NEGATIONS):
        return False
    return True


def explain_validation_failure(directions, codes) -> list[str]:
    """Human-readable, dimension-level repair guidance (2A-6C §4).

    Turns opaque codes into instructions a model can act on: which dimension
    collapsed and to which family, which pair collided, what an originality
    hit matched, and — crucially — that a failed direction must be REPLACED
    with a different signature, not paraphrased. Returns a list of lines.
    """
    signatures = [direction_signature(d) for d in directions]
    names = [d.get("name") or f"direction[{i}]"
             for i, d in enumerate(directions)]
    dims = [dim for dim, _ in SIGNATURE_DIMENSIONS]
    lines: list[str] = []

    fields = dict(SIGNATURE_DIMENSIONS)
    for dimension, code in COLLAPSE_CODES.items():
        if code in codes:
            fam = next((s[dimension] for s in signatures
                        if s[dimension] != UNCLASSIFIED), "the same family")
            # §BH68(a): AIMED — which directions, what each READ and from which words, which one to keep, and the
            # families of the known set the others can move to. Nothing here is a claim the validator did not measure.
            field = fields[dimension]
            read = []
            for i, direction in enumerate(directions):
                if dimension == "hierarchy_family":
                    read.append(f"{names[i]} declares {signatures[i][dimension]}")
                    continue
                words = classification_evidence(direction.get(field, ""), dimension)
                read.append(f"{names[i]} reads {signatures[i][dimension]}"
                            + (f" from the words {words} in its {field}" if words else f" from its {field}"))
            unused = [f for f in known_families(dimension) if f != fam]
            lines.append(
                f"- {code}: all three directions read as {fam!r} on '{dimension}' — " + "; ".join(read) + ".")
            if len(names) >= 3:
                lines.append(
                    f"  AIM: keep {names[0]} as it is; move {names[1]} and {names[2]} to two DIFFERENT families"
                    + (f" of the known set — choose from {unused}" if unused else "")
                    + (". Re-declare their hierarchy_family AND rebuild each one's focal hierarchy so the declared "
                       "element really leads." if dimension == "hierarchy_family" else
                       f". Remove the words that classified them from those two directions' {field} — while those "
                       "words stay, the validator reads the same family again."))

    if COMPOSITION_NOT_DISTINCT in codes and len(names) >= 3:
        # [his correction of 2026-10-07] the motif his brief asks for stands in all three: their layouts must differ
        fam = signatures[0]["composition_family"]
        read = []
        for i, direction in enumerate(directions):
            words = classification_evidence(direction.get("layout_structure", ""), "composition_family")
            read.append(f"{names[i]} reads {signatures[i]['composition_family']}"
                        + (f" from the words {words} in its layout_structure" if words else " from its layout_structure"))
        unused = [f for f in known_families("composition_family") if f != fam]
        lines.append(f"- {COMPOSITION_NOT_DISTINCT}: the motif the brief asks for may stand in all three directions, "
                     f"so they must differ by idea, layout and type — but all three read as {fam!r} on "
                     "'composition_family' — " + "; ".join(read) + ".")
        lines.append(f"  AIM: keep {names[0]}'s layout; give {names[1]} and {names[2]} two DIFFERENT composition "
                     f"families" + (f" — choose from {unused}" if unused else "") + ", and remove the words that "
                     "classified them from those two directions' layout_structure — while those words stay, the "
                     "validator reads the same layout again. Keep the brief's motif in all three.")

    if "TYPOGRAPHY_NOT_DISTINCT" in codes:
        lines.append(
            "  Typography must differ in KIND across the three, e.g. a "
            "condensed sans, a high-contrast serif paired with a sans, and a "
            "rounded/humanist sans — not one type style in three sizes.")

    if "DIRECTION_SIGNATURE_INSUFFICIENT" in codes:
        for i, s in enumerate(signatures):
            unread = [d for d in dims if s[d] in ("", UNCLASSIFIED)]
            if unread:
                lines.append(
                    f"- DIRECTION_SIGNATURE_INSUFFICIENT: {names[i]} could not "
                    f"be classified on {unread}. Describe those dimensions in "
                    "concrete, conventional design terms (composition, "
                    "typography kind, motif kind, hierarchy, tone).")
                # §BH68(a): name the field each unread dimension is read from, and its known set
                for d in unread:
                    if d == "hierarchy_family":
                        lines.append(f"  AIM: declare {names[i]}'s hierarchy_family as one of "
                                     f"{list(HIERARCHY_FAMILY_NAMES)}.")
                    elif known_families(d):
                        lines.append(f"  AIM: {names[i]}'s {fields[d]} names none of the {d} families the validator "
                                     f"reads — {list(known_families(d))}; say which one it is in plain words.")

    if "DIRECTIONS_SUPERFICIALLY_VARIANT" in codes:
        for a in range(len(signatures)):
            for b in range(a + 1, len(signatures)):
                shared = [d for d in dims
                          if signatures[a][d] not in ("", UNCLASSIFIED)
                          and signatures[a][d] == signatures[b][d]]
                diffs = [d for d in dims
                         if UNCLASSIFIED not in (signatures[a][d], signatures[b][d])
                         and signatures[a][d] != signatures[b][d]]
                if len(diffs) < MIN_PAIRWISE_DIFFERENCES:
                    lines.append(
                        f"- {names[a]} and {names[b]} collide: they share "
                        f"{shared or 'most dimensions'} and differ on only "
                        f"{diffs}. Fully REPLACE one of them with a different "
                        "composition + typography + motif combination.")
                    # §BH68(a): aimed — which one, and how many of the shared dimensions must change
                    need = MIN_PAIRWISE_DIFFERENCES - len(diffs)
                    lines.append(
                        f"  AIM: keep {names[a]}; change {names[b]} on at least {need} of {shared} (a pair must differ "
                        f"on {MIN_PAIRWISE_DIFFERENCES} classified dimensions and these two differ on {len(diffs)}).")

    for code in codes:
        if code.startswith("ORIGINALITY_VIOLATION"):
            lines.append(
                f"- {code}: this direction instructs reproducing prior/"
                "reference work. Describe an ORIGINAL visual system. Language "
                "that FORBIDS copying (\"do not trace the reference\") is fine "
                "and is not the problem — an affirmative copy instruction is.")

    # Content-faithfulness codes (2A-6D) get actionable guidance.
    _CONTENT_GUIDANCE = {
        "UNCONFIRMED_STRUCTURE_ASSUMED": (
            "the brief supplies NO carton dimensions or structure — remove "
            "every invented measurement, proportion and closure system "
            "(tuck-end, auto-lock, panel sizes). Structure is confirmed by a "
            "human later; describe the design independent of carton geometry."),
        "REQUIRED_COPY_MISSING": (
            "this direction omits required consumer copy from the brief. "
            "Every direction must explicitly carry every required line."),
        "DECORATIVE_COVERAGE_EXCEEDED": (
            "this direction's decorative elements exceed the brief's coverage "
            "cap. Reduce the motif to the permitted share of the panel — no "
            "full-face or full-bleed decorative fields."),
        # the owner's second answer of 2026-09-25: this line said "this direction makes photography the printable
        # surface" — a claim the validator did not measure (§BH68(a)), and a photograph word a planner could copy
        "PRODUCTION_RASTER_DEPENDENCY": (
            "the printed artwork must be rebuildable from native vectors — "
            "describe a vector-expressible printed surface; a concept render "
            "of the product in its scene belongs in a sentence of its own."),
        "DIRECTIONS_SHARE_CORE_MOTIF": (
            "all three directions render the SAME core motif in different "
            "media. Different rendering (photo/engraving/emboss) of one "
            "subject is one idea. Give each direction its own motif system."),
        "PALETTE_SYSTEMS_NOT_DISTINCT": (
            "the three palettes read as ONE system — the same primary chromatic "
            "colour, the same set of chromatic colours, the same hexes, or one "
            "neutral ground. Give each direction its own palette structure, not "
            "one palette re-lit."),
    }
    handled_prefixes = tuple(_CONTENT_GUIDANCE)
    for code in codes:
        for prefix, guidance in _CONTENT_GUIDANCE.items():
            if code.startswith(prefix):
                lines.append(f"- {code}: {guidance}")
                break

    # Never drop a code: any failure not given a dimension-level explanation
    # above (e.g. structural contract codes like DUPLICATE_LAYOUT_STRUCTURE or
    # OUTPUT_NOT_JSON) is still surfaced verbatim so the model sees it.
    explained = set(COLLAPSE_CODES.values()) | {
        "TYPOGRAPHY_NOT_DISTINCT", "DIRECTION_SIGNATURE_INSUFFICIENT",
        "DIRECTIONS_SUPERFICIALLY_VARIANT", COMPOSITION_NOT_DISTINCT}
    for code in codes:
        if (code in explained or code.startswith("ORIGINALITY_VIOLATION")
                or code.startswith(handled_prefixes)):
            continue
        lines.append(f"- {code}: fix this contract violation in the named field.")

    lines.append(
        "Replace each failed direction as an independently designed system "
        "(composition, typography, motif, hierarchy, tone all reconsidered). "
        "Do not merely change adjectives or colours.")
    return lines


def originality_violations(directions) -> list:
    """Directions instructing reproduction of prior work are refused, with the
    offending direction named. Reference context informs patterns; it is never
    a template — and language that FORBIDS copying is not a violation.

    A hit is either an explicit reproduction phrase, or an affirmative copy
    verb governing a prior-work target within a single, non-negated clause.
    Product-category wording (Baked Powder, Soft Radiance, …) is never a
    trigger by itself: it carries no copy verb and no prior-work target.
    """
    codes = []
    fields = ("concept_statement", "layout_structure", "graphic_elements",
              "imagery_approach", "prompt_seed", "originality_notes")
    for index, direction in enumerate(directions):
        # Join fields with a clause separator so a negation in one field
        # ("no photography") cannot mask a copy instruction in another
        # ("replicate the reference") by forming one run-on clause.
        joined = " . ".join(str(direction.get(f, "")).lower() for f in fields)
        joined = " ".join(joined.split())
        explicit = any(phrase in joined for phrase in _COPY_PHRASES)
        clause_hit = any(_clause_is_affirmative_copy(clause)
                         for clause in _CLAUSE_SPLIT.split(joined))
        if explicit or clause_hit:
            codes.append(f"ORIGINALITY_VIOLATION:direction[{index}]")
    return codes
