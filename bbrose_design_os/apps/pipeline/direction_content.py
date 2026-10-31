"""Content-faithfulness validation for design directions (Phase 2A-6D).

The task-#50 direction set passed every existing gate while contradicting the
user's brief: it invented carton dimensions and a closure system, dropped the
required Spanish copy, made a photograph the printable surface, proposed a
70%-of-panel emboss against a 20% decorative cap, gave all three directions
the same spiral motif in three rendering media, and reused one warm-cream /
deep-rose / rose-gold palette throughout. The signature validator measures
whether three directions are DIFFERENT; nothing measured whether they were
FAITHFUL. This module is that second gate.

All checks are deterministic and clause/negation-aware (a direction saying
"no powder spiral" is not proposing a spiral). Checks that depend on brief
facts fire only when the brief declares them (required copy, coverage cap),
so legacy briefs are untouched; the structural check fires whenever the
brief supplies no dimensions — unknown structure must remain unknown.

Codes:
    UNCONFIRMED_STRUCTURE_ASSUMED   invented mm/closure facts, no dims given
    REQUIRED_COPY_MISSING           a required consumer-copy line is absent
    DECORATIVE_COVERAGE_EXCEEDED    coverage claim above the brief's cap
    PRODUCTION_RASTER_DEPENDENCY    photography as the printable surface
    DIRECTIONS_SHARE_CORE_MOTIF     one motif family in all three directions
    PALETTE_SYSTEMS_NOT_DISTINCT    one ground color / hex across all three
"""
from __future__ import annotations

import re

from .direction_signature import strip_negated_spans

_DIMENSION_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mm|cm)\b")
_DIMENSION_PAIR_RE = re.compile(r"\b\d+(?:\.\d+)?\s*[x×]\s*\d+")
_CLOSURE_TERMS = (
    "tuck-end", "tuck end", "auto-lock", "auto lock", "crash-lock",
    "crash lock", "snap-lock", "snap lock", "straight tuck", "reverse tuck",
    "side panels minimum", "side panel minimum", "glue-tab", "glue tab",
)

_COVERAGE_CAP_RE = re.compile(
    r"decorative\s+coverage[^\d%]{0,40}(\d{1,2})\s*%", re.IGNORECASE)
_DECOR_CONTEXT = ("motif", "illustration", "emboss", "engrav", "pattern",
                  "photograph", "photo", "artwork", "decorat", "swirl",
                  "spiral", "halo", "circle", "field", "image", "movement",
                  "graphic")
_FULL_COVERAGE_PHRASES = (
    "full-face", "full face", "full-bleed", "full bleed", "entire front",
    "entire face", "covers the entire", "bleeds to all edges",
    "bled to all", "covers the primary surface", "full-panel", "full panel",
    "covers all edges", "across the whole panel",
)

_PHOTO_TERMS = ("photograph", "photographic", "photography", "macro photo")

#: §BH57(b) — clause subjects that make a sentence a statement about the CONCEPT
#: RENDER (the picture OF the product) rather than about the printed surface.
#: `_check_raster_dependency` exists for "a direction whose PRINTED surface is a
#: photograph"; a concept render is photographic by definition — that is what an
#: image model is asked to make — so a clause about the render is out of its
#: scope. Measured on task 86: three good directions refused unrendered for
#: "Render is photographic in style; all printed decoration is vector-only",
#: which states the very compliance the check is looking for. Same class as the
#: task #50 "Zero photographic imagery" defect recorded at
#: direction_signature.py:128-135.
_RENDER_SUBJECT_CUES = ("render ", "the render ", "concept render ",
                        "the concept render ", "product render ",
                        "rendering ", "the rendering ", "renders ")

#: ...but only when the clause names no printed surface. The house splitter
#: deliberately does not break on "and" (it would sever a negation from the
#: words it governs — strip_negated_spans), so without this second half
#: "render is photographic and the lid is printed with it" would ride along on
#: its first three words. These close that hole instead of inheriting it.
_PRINTED_SURFACE_NOUNS = ("print", "lid", "surface", "decoration", "artwork",
                          "carton", "panel", "label", "pan ", "base ")

#: §BH68(a), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "THE PLANNER MUST PASS ITS OWN CHECK BEFORE I
#: TEST ... measure why the check still fails and fix the cause." Measured over every raster flag on record (20
#: directions, tasks 51-96): the check refused the CONCEPT RENDER far more often than a photographic print. The prompt
#: puts the render in `imagery_approach` and `prompt_seed` — "A photograph is fine HERE" — and the reader read those
#: fields and refused them: "the carton photographed at a 15-degree angle under raking light" (task 93), "compact
#: photographed at a 20° tilt on a pale pink silk-effect draped surface" (96), and after the repair told the planner to
#: write the render as its own sentence, "this lighting and photography exist only in the concept render file — nothing
#: photographic appears in the print artwork" (96). Two readings are added; the rule — no photograph may be the printed
#: decoration — is not moved:
#: 1. THE PRODUCT IS WHAT IS PHOTOGRAPHED: the only photograph in the clause is the product itself ("<the compact / the
#:    carton / the product> ... photographed", "a render photograph", "a photograph of the (physical) product"), no
#:    other photograph word remains, and the clause says nothing of print, artwork, decoration or a label.
#: 2. THE CLAUSE SAYS IT IS THE RENDER ("concept render", "packshot", "render file" ...) and names no printed surface —
#:    `_PRINTED_SURFACE_NOUNS` less the scene's own "surface" ("on a blush silk surface").
#: And, for this check only, "nothing ..." is a negation — "nothing photographic appears in the print artwork" — except
#: where it is affirmative ("nothing but a photograph ..."). The shared NEGATION_SPAN_CUES, which the diversity
#: classifiers read, are not touched.
#: [THE OWNER'S ANSWER OF 2026-09-27 TO THE §BH70 REPORT'S THIRD QUESTION: "Yes, free that check. Lipstick, mascara
#: and pencil are core products." The sentence this passed for a compact and refused for his slim forms
#: (acceptance-time entry 16) reads as the render for them too — with the eyeliner and liner a pencil is, and the gloss
#: and the vial his fourth answer brings. The check itself stays: a photograph as printed decoration still fires.]
_PRODUCT_NOUNS = ("compact", "carton", "bottle", "jar", "tube", "palette", "product", "box", "pack", "case",
                  "container", "dropper", "packshot", "lipstick", "mascara", "pencil", "eyeliner", "liner", "gloss",
                  "vial")
_PRODUCT_PHOTO_RE = re.compile(
    r"\b(?:%s)s?\b[^.;:]*?\bphotographed\b|\brender photographs?\b"
    r"|\bphotographs? of the (?:physical |closed |open )?(?:%s)s?\b"
    % ("|".join(_PRODUCT_NOUNS), "|".join(_PRODUCT_NOUNS)))
_PRINT_VETO = ("print", "artwork", "decoration", "label")
_RENDER_SCOPE_MARKERS = ("concept render", "concept-render", "render only", "render-only", "render file",
                         "render scene", "packshot")
_RENDER_SCOPE_VETO = tuple(noun for noun in _PRINTED_SURFACE_NOUNS if noun != "surface")
_NOTHING_RE = re.compile(r"\bnothing (?!but\b|except\b|other than\b|besides\b|save\b)")

#: Bounded core-motif families. One family present (non-negated) in all
#: three directions means one visual subject rendered three ways.
_MOTIF_GROUPS = {
    "SPIRAL": ("swirl", "spiral", "whorl"),
    "HALO": ("halo",),
    "FLORAL": ("petal", "floral", "flower"),
    "RIBBON": ("ribbon",),
    "VEIL": ("veil",),
    "PARTICLE": ("particle", "powder-dot", "powder dot", "dust scatter",
                 "powder dust"),
    "STRATA": ("strata",),
    "SUNBURST": ("sunburst",),
    "DROPLET": ("droplet",),
    "WAVE": ("wave", "ripple"),
    "HEART": ("heart",),
    "STAR": ("star ", "stars"),
}
_MOTIF_FIELDS = ("graphic_elements", "imagery_approach", "prompt_seed",
                 "layout_structure")

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
#: Ground-color lexicon (multi-word entries first so "warm cream" beats
#: "cream" and "blush pink" beats "pink" at the same position).
_COLOR_ANCHORS = (
    "warm cream", "light sky blue", "light blush pink", "blush pink",
    "light pink", "sky blue", "deep rose", "rose gold", "pale champagne",
    "light peach", "soft mint", "warm ivory", "light orange", "light green",
    "porcelain", "champagne", "terracotta", "lavender", "cream", "ivory",
    "blush", "peach", "mint", "beige", "nude", "white", "green", "blue",
    "pink", "gold",
    # his test day finding 1, 2026-09-29: coral — one of the colour worlds his brief named for design 116, and the one
    # of his colours this check could not see
    "coral",
)

_DIRECTION_TEXT_FIELDS = (
    "name", "design_axis", "concept_statement", "layout_structure",
    "focal_hierarchy", "typography", "color_system", "graphic_elements",
    "imagery_approach", "material_finish_direction", "emotional_tone",
    "product_target_fit", "target_structural_guidance", "prompt_seed",
)


def _affirmative_clauses(*texts):
    """Sentence segments stating what the design IS. Negated/contrastive
    spans are truncated by strip_negated_spans, so "no powder spiral" never
    counts as proposing a spiral and "occupying no more than 20%" never
    counts as a 20% coverage claim."""
    out = []
    for text in texts:
        out += [segment for segment in
                strip_negated_spans(text).split(" . ") if segment]
    return out


def _direction_text(direction):
    parts = []
    for field in _DIRECTION_TEXT_FIELDS:
        value = direction.get(field, "")
        parts.append("; ".join(value) if isinstance(value, (list, tuple))
                     else str(value or ""))
    return " . ".join(parts)


def validate_direction_content(brief, document, *, record_dimensions_mm=(), asked_motifs=()) -> list[str]:
    """Faithfulness codes for a structurally valid document, or []. `record_dimensions_mm` — the product record's own
    width, depth and height — are the sizes the structure check does not call assumed (§BH68(a)). `asked_motifs` — the
    core-motif groups his brief asks for (``asked_motifs``, his correction of 2026-10-07) — may stand in all three."""
    directions = document.get("directions") or []
    codes: list[str] = []
    codes += _check_structure_assumptions(brief, document, directions, record_dimensions_mm)
    codes += _check_required_copy(brief, directions)
    codes += _check_decorative_coverage(brief, directions)
    codes += _check_raster_dependency(directions)
    codes += _check_shared_core_motif(directions, asked=asked_motifs)
    if not brief_sets_colours(brief):
        # [his test finding on design 118, 2026-10-03] different colours only where the brief leaves colour open
        codes += _check_palette_distinctness(directions)
    codes += _check_house_accents(brief, directions)       # [his answer 4 of 2026-10-02: the one house accent, checked]
    return sorted(set(codes))


# --- structure -----------------------------------------------------------------


#: §BH68(a), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "measure why the check still fails and fix
#: the cause." MEASURED over every planning attempt on record for his brief (tasks 90-102): the brief GIVES the carton
#: die — "Carton die 170.5 x 122.5 mm" — and the product record holds it (width 170.5, depth 18, height 122.5 mm), but
#: the brief this check reads carries `dimensions` from the record's free-text field only, which is empty; so the check
#: refused the planner for repeating the brief's own die in 6 of the 18 attempts on record (the rejected payloads of
#: the nine failed runs, tasks 90-102). It never even read the die whole:
#: the sentence splitter the checks share cuts at every full stop, decimal points included, so "170.5 x 122.5 mm"
#: arrived as "5 x 122" and "5 mm". The check is not relaxed. Before any split, a measurement whose EVERY number is one
#: the record holds (within 0.05 mm) is read as "(the record's size)"; every other measurement — a lid diameter, a band
#: height, a margin — and every closure term is flagged exactly as before (on record: a 55 to 75 mm lid or lid label,
#: a 60 mm motif circle, a 4 mm inset or band, a 3 mm contour interval — all still refused). Where the brief's own
#: `dimensions` text is given the check stands down, as it did.
_RECORD_NUMBER = r"\d+(?:\.\d+)?"
_RECORD_UNIT = r"(?:\s*(?:mm|cm)\b)?"
_MEASUREMENT_RE = re.compile(r"(?<![\d.])" + _RECORD_NUMBER + _RECORD_UNIT
                             + r"(?:\s*[x×]\s*" + _RECORD_NUMBER + _RECORD_UNIT + r")*")
_MEASUREMENT_MARK_RE = re.compile(r"[x×]|(?:mm|cm)\b")
_RECORD_TOLERANCE_MM = 0.05
RECORD_SIZE_TEXT = "(the record's size)"


def record_sizes_neutralised(text, record_dimensions_mm=()) -> str:
    """`text` with every measurement whose numbers ALL are the product record's own width, depth or height read as
    RECORD_SIZE_TEXT; every other measurement left exactly as written. Read on the RAW field, before any split."""
    text = "" if text is None else str(text)
    if not record_dimensions_mm:
        return text

    def swap(match):
        expression = match.group(0)
        if not _MEASUREMENT_MARK_RE.search(expression):
            return expression
        scale = 10.0 if expression.rstrip().endswith("cm") else 1.0
        values = [float(value) * scale for value in re.findall(_RECORD_NUMBER, expression)]
        if all(any(abs(value - held) <= _RECORD_TOLERANCE_MM for held in record_dimensions_mm) for value in values):
            return RECORD_SIZE_TEXT
        return expression
    return _MEASUREMENT_RE.sub(swap, text)


def _structure_scopes(document, directions, record_dimensions_mm):
    """The texts the structure check reads, per scope, with the record's own sizes read as such (§BH68(a))."""
    def read(value):
        return record_sizes_neutralised(value, record_dimensions_mm)
    scopes = [("design_intent", [read(document.get(field, "")) for field in
                                 ("target_structural_guidance", "visual_objective", "composition")])]
    scopes += [(f"direction[{i}]", [read(d.get("target_structural_guidance", "")), read(d.get("layout_structure", ""))])
               for i, d in enumerate(directions)]
    return scopes


def _check_structure_assumptions(brief, document, directions, record_dimensions_mm=()):
    """No supplied dimensions → the document may not invent any (§brief:
    'Do not estimate dimensions… Do not silently select a generic carton
    structure'). §BH68(a): the product record's own sizes are not invented."""
    if (brief.get("dimensions") or "").strip():
        return []
    codes = []
    scopes = _structure_scopes(document, directions, record_dimensions_mm)
    for label, texts in scopes:
        for clause in _affirmative_clauses(*texts):
            if (_DIMENSION_RE.search(clause) or _DIMENSION_PAIR_RE.search(clause)
                    or any(term in clause for term in _CLOSURE_TERMS)):
                codes.append(f"UNCONFIRMED_STRUCTURE_ASSUMED:{label}")
                break
    return codes


# --- required copy --------------------------------------------------------------


def required_copy_missing(brief, direction) -> list:
    """The brief's required lines a direction does not carry word for word — what `_check_required_copy` reads, line
    by line, so the one retry can be told which (his test day finding 1, 2026-09-29: it was told none)."""
    haystack = " ".join(_direction_text(direction).lower().split())
    return [entry for entry in (brief.get("required_copy") or ())
            if str(entry).strip() and " ".join(str(entry).lower().split()) not in haystack]


def _check_required_copy(brief, directions):
    if not [entry for entry in (brief.get("required_copy") or ()) if str(entry).strip()]:
        return []
    return [f"REQUIRED_COPY_MISSING:direction[{index}]" for index, direction in enumerate(directions)
            if required_copy_missing(brief, direction)]


# --- decorative coverage ----------------------------------------------------------

#: Where a direction's coverage evidence came from (2A-6D-CORR-2 §2).
COVERAGE_STRUCTURED = "STRUCTURED_DECLARATION"
COVERAGE_AREA = "EXPLICIT_AREA_LANGUAGE"
COVERAGE_DERIVED = "DERIVED_BOUNDING_EXTENTS"
COVERAGE_UNKNOWN = "UNKNOWN"

#: A percentage is an AREA claim only with area vocabulary nearby.
#: " ink" keeps its word start — "blush pink" must never read as ink.
_AREA_CUES = ("coverage", "area", " ink", "occup", "of the face",
              "of the visible", "of visible")
_EXTENT_HEIGHT_WORDS = ("height", "tall", "vertical", "vertically")
_EXTENT_WIDTH_WORDS = ("width", "wide", "horizontal", "horizontally")
#: Shapes with equal width/height extents: ONE extent bounds BOTH axes, so a
#: "circle at 70% of panel width" derives a 49% bounding square — the Relief
#: Strata emboss circle stays a violation without conflating a lone band
#: extent with area.
_EQUAL_EXTENT_SHAPES = ("circle", "circular", "round", "disc", "square")
_PCT_RANGE_RE = re.compile(r"(\d{1,3})(?:\s*(?:[-–—]|to)\s*(\d{1,3}))?\s*%")
_WINDOW = 45


def coverage_cap_percent(brief) -> int | None:
    """The decorative-coverage cap the brief declares, or None (no check)."""
    for entry in brief.get("production_constraints") or ():
        match = _COVERAGE_CAP_RE.search(str(entry))
        if match:
            return int(match.group(1))
    return None


def _coverage_clauses(*texts):
    """Affirmative clauses for coverage scanning. Unlike _affirmative_clauses
    this rejoins colon-separated fragments — "total emboss coverage: 70%"
    must stay ONE clause, or the area cue separates from its percentage —
    while negation stripping still applies per fragment ("no more than 20%"
    never becomes a claim)."""
    out = []
    for text in texts:
        for sentence in re.split(r"[.;\n]", str(text or "")):
            clause = strip_negated_spans(sentence).replace(" . ", " ").strip()
            if clause:
                out.append(clause)
    return out


def _classify_percent(clause, match):
    """``("area"|"extent_h"|"extent_w"|"unknown", value)`` for one % match.

    Extent qualifiers win over area cues: "a halo occupying roughly 30% of
    panel height" contains "occup" but IS a bounding extent, not an area
    claim (2A-6D-CORR-2 §2)."""
    value = max(int(g) for g in match.groups() if g)
    after = clause[match.end():match.end() + _WINDOW]
    before = clause[max(0, match.start() - _WINDOW):match.start()]
    if any(word in after for word in _EXTENT_HEIGHT_WORDS):
        return "extent_h", value
    if any(word in after for word in _EXTENT_WIDTH_WORDS):
        return "extent_w", value
    if (any(cue in before for cue in _AREA_CUES)
            or any(cue in after for cue in _AREA_CUES)):
        return "area", value
    return "unknown", value


def coverage_findings(brief, directions) -> list[dict]:
    """Per-direction coverage evidence: what was declared, how it was read
    (STRUCTURED_DECLARATION / EXPLICIT_AREA_LANGUAGE /
    DERIVED_BOUNDING_EXTENTS / UNKNOWN), and whether it exceeds the cap.
    Deterministic; also the observability payload for failed runs."""
    cap = coverage_cap_percent(brief)
    findings = []
    fields = ("layout_structure", "graphic_elements", "imagery_approach",
              "material_finish_direction", "prompt_seed")
    for index, direction in enumerate(directions):
        finding = {"direction": index, "cap": cap,
                   "source": COVERAGE_UNKNOWN, "declared_pct": None,
                   "area_claims": [], "derived_estimates": [],
                   "full_coverage_phrases": [], "malformed": False,
                   "over_cap": False}
        structured = direction.get("decorative_coverage_pct")
        if structured is not None:
            try:
                finding["declared_pct"] = float(structured)
                finding["source"] = COVERAGE_STRUCTURED
            except (TypeError, ValueError):
                finding["malformed"] = True     # fail closed below
                finding["source"] = COVERAGE_STRUCTURED
        for clause in _coverage_clauses(*(direction.get(f, "") for f in fields)):
            clause = f" {clause} "
            # A clause is coverage-relevant with decorative vocabulary OR
            # explicit area language ("total ink coverage 45%" needs no
            # motif noun); anything else (a 40% x-height, a 50% opacity)
            # is never a coverage claim.
            if not (any(word in clause for word in _DECOR_CONTEXT)
                    or any(cue in clause for cue in _AREA_CUES)):
                continue
            for phrase in _FULL_COVERAGE_PHRASES:
                if phrase in clause:
                    finding["full_coverage_phrases"].append(phrase)
            extents = {"extent_h": [], "extent_w": []}
            for match in _PCT_RANGE_RE.finditer(clause):
                kind, value = _classify_percent(clause, match)
                if kind == "area":
                    finding["area_claims"].append(value)
                elif kind in extents:
                    extents[kind].append(value)
            heights, widths = extents["extent_h"], extents["extent_w"]
            if heights and widths:
                estimate = round(max(heights) * max(widths) / 100, 1)
                finding["derived_estimates"].append(estimate)
            elif ((heights or widths)
                  and any(shape in clause for shape in _EQUAL_EXTENT_SHAPES)):
                lone = max(heights or widths)
                finding["derived_estimates"].append(round(lone * lone / 100, 1))
        if finding["source"] == COVERAGE_UNKNOWN:
            if finding["area_claims"]:
                finding["source"] = COVERAGE_AREA
            elif finding["derived_estimates"]:
                finding["source"] = COVERAGE_DERIVED
        if cap is not None:
            declared = finding["declared_pct"]
            finding["over_cap"] = bool(
                finding["malformed"]
                or finding["full_coverage_phrases"]
                or (declared is not None and declared > cap)
                or any(v > cap for v in finding["area_claims"])
                or any(v > cap for v in finding["derived_estimates"]))
        findings.append(finding)
    return findings


def _check_decorative_coverage(brief, directions):
    if coverage_cap_percent(brief) is None:
        return []
    return [f"DECORATIVE_COVERAGE_EXCEEDED:direction[{f['direction']}]"
            for f in coverage_findings(brief, directions) if f["over_cap"]]


# --- photographic production dependency ---------------------------------------------


def raster_dependency_codes(directions):
    """Public, raw-safe raster-dependency check over a list of direction dicts
    (built or raw). Used to CO-SURFACE content codes alongside a schema failure
    (2B-3V): a payload that is both missing a required field AND photographic
    must return BOTH codes so the single bounded repair can fix both at once."""
    return _check_raster_dependency([d for d in (directions or [])
                                     if isinstance(d, dict)])


_RASTER_FIELDS = ("design_axis", "layout_structure", "graphic_elements",
                  "imagery_approach", "prompt_seed")


def _is_about_the_render(clause):
    """§BH57(b): True when this clause's subject is the concept render AND it
    names no printed surface — see _RENDER_SUBJECT_CUES. §BH68(a): or when the
    product is the only thing photographed and nothing is printed, or when the
    clause says it is the render and names no printed surface."""
    c = clause.strip()
    if any(c.startswith(cue) for cue in _RENDER_SUBJECT_CUES) and not any(
            noun in c for noun in _PRINTED_SURFACE_NOUNS):
        return True
    masked = _PRODUCT_PHOTO_RE.sub(" ", c)
    if (masked != c and not any(term in masked for term in _PHOTO_TERMS)
            and not any(word in c for word in _PRINT_VETO)):
        return True
    return (any(marker in c for marker in _RENDER_SCOPE_MARKERS)
            and not any(noun in c for noun in _RENDER_SCOPE_VETO))


def _raster_clauses(direction):
    """The affirmative clauses of the raster fields, each cut at a negating
    "nothing" (§BH68(a)) — a cut local to this check."""
    out = []
    for clause in _affirmative_clauses(*(direction.get(f, "") for f in _RASTER_FIELDS)):
        match = _NOTHING_RE.search(clause)
        clause = clause[:match.start()].strip() if match else clause
        if clause:
            out.append(clause)
    return out


def raster_offending_clause(direction):
    """The clause that trips the check, or "" — so the REPAIR can quote it
    instead of asserting a fact about the design (§BH57(b) Part B)."""
    for clause in _raster_clauses(direction):
        if _is_about_the_render(clause):
            continue
        if any(term in clause for term in _PHOTO_TERMS):
            return clause
    return ""


def _check_raster_dependency(directions):
    """A direction whose PRINTED surface is a photograph can never pass the
    platform's native-vector reconstruction — fail it at planning, not at
    Gate 2. Negated / reference-only photography language is fine, and so is
    a clause about the CONCEPT RENDER, which is photographic by definition
    (§BH57(b))."""
    codes = []
    for index, direction in enumerate(directions):
        if raster_offending_clause(direction):
            codes.append(f"PRODUCTION_RASTER_DEPENDENCY:direction[{index}]")
    return codes


# --- shared core motif -----------------------------------------------------------


def asked_motifs(text) -> tuple:
    """[His correction of 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a6b2092): "Design 120: a motif my brief
    asks for may appear in all three directions; they must still differ by idea, layout and type."] The core-motif
    groups his brief asks for: each group a word of which stands in an affirmative span of the brief's own FULL text
    (``strip_negated_spans`` — "no flowers" asks for none), read in the check's own words (``_MOTIF_GROUPS``). The
    planner's brief keeps only the first 200 characters of his text, and 120's "halftone-dot flowers" stand after them;
    the rose of a product's name is no motif word here (petal, floral, flower are), so a rose product asks for no
    motif by its name. MEASURED on 120's brief: ("FLORAL",).

    Only the words that ask for a design are read: never the words printed on the pack — its copy fields
    (``targets.container.product_words``, the brief read as finding 118 reads it), its quoted words — nor the lines
    that name the product (its title line, ``_NAMING_LINE_RE``). MEASURED on the stored briefs: 116's and 117's
    "Scent line: ... Rose Petals" and "Rosa Damascena Flower Water" in their back copy read FLORAL, an ingredient
    taken for an ask; 118's and 119's "liquid-swirl pattern" (SPIRAL) is the ask it is."""
    from apps.pipeline.targets.container import product_words
    lines = product_words(text).split("\n")
    title = next((i for i, line in enumerate(lines) if line.strip()), None)
    design = _QUOTED_RE.sub(" ", "\n".join(line for i, line in enumerate(lines)
                                           if i != title and not _NAMING_LINE_RE.match(line)))
    affirmative = strip_negated_spans(design)
    return tuple(sorted(group for group, words in _MOTIF_GROUPS.items() if any(w in affirmative for w in words)))


#: [his correction of 2026-10-07] the lines of a brief that name the product, never ask for its design
_NAMING_LINE_RE = re.compile(r"^[ \t]*(?:product|product name|name|arabic name|scent(?: line)?|fragrance|size|type|"
                             r"audience)[ \t]*:", re.I)
#: the words a brief quotes — printed on the pack, never an ask
_QUOTED_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”')


def asked_motif_families(groups) -> tuple:
    """The motif families (``direction_signature.MOTIF_FAMILIES``) the asked groups' own words classify as — the
    families whose collapse across the three ``validate_semantic_distinctness`` excuses (FLORAL's petal, floral and
    flower read BOTANICAL)."""
    from .direction_signature import UNCLASSIFIED, classify
    families = {classify(word.strip(), "motif_family") for group in groups or () for word in _MOTIF_GROUPS.get(group, ())}
    return tuple(sorted(f for f in families if f != UNCLASSIFIED))


def _check_shared_core_motif(directions, asked=()):
    """One motif family in all three directions is one idea three times — unless it is a motif his brief asks for (his
    correction of 2026-10-07): that one may stand in all three, and the three are then told apart by idea, layout and
    type (``validate_semantic_distinctness``)."""
    if len(directions) < 3:
        return []
    per_direction = []
    for direction in directions:
        clauses = _affirmative_clauses(
            *(direction.get(f, "") for f in _MOTIF_FIELDS))
        found = {group for group, words in _MOTIF_GROUPS.items()
                 if any(any(w in clause for w in words) for clause in clauses)}
        per_direction.append(found)
    shared = (set.intersection(*per_direction) if per_direction else set()) - set(asked or ())
    if shared:
        return [f"DIRECTIONS_SHARE_CORE_MOTIF:{sorted(shared)[0]}"]
    return []


# --- palette distinctness ----------------------------------------------------------

#: Neutrals a brief may legitimately require in EVERY palette (task #50
#: mandates ivory in all three). A shared neutral never collapses palette
#: systems (2A-6D-CORR-2 §3 — SHARED_NEUTRAL_ALLOWED); only the meaningful
#: chromatic system (primary / secondary / accents) is compared.
SHARED_NEUTRAL_ALLOWED = (
    "warm ivory", "warm cream", "off-white", "ivory", "cream", "white",
    "porcelain", "beige", "nude", "transparent",
)


def _anchor_sequence(color_system: str) -> list[str]:
    """Color anchors in first-mention order, longest match winning at each
    position ("light blush pink" swallows "blush" and "pink")."""
    text = " ".join(str(color_system or "").lower().replace("-", " ").split())
    hits = []
    for anchor in _COLOR_ANCHORS:
        start = 0
        while True:
            pos = text.find(anchor, start)
            if pos < 0:
                break
            hits.append((pos, -len(anchor), anchor))
            start = pos + 1
    taken, sequence = [], []
    for pos, neg_len, anchor in sorted(hits):
        end = pos - neg_len
        if any(pos < t_end and end > t_pos for t_pos, t_end in taken):
            continue
        taken.append((pos, end))
        if anchor not in sequence:
            sequence.append(anchor)
    return sequence


def _ground_anchor(color_system: str) -> str:
    """The first-mentioned color anchor — the ground, by writing convention."""
    sequence = _anchor_sequence(color_system)
    return sequence[0] if sequence else ""


def _check_palette_distinctness(directions):
    """Role-aware comparison (2A-6D-CORR-2 §3). The old any-shared-hex rule
    failed the retry because ivory #FAF3EC — which the brief REQUIRES in all
    three palettes — appeared everywhere. Now: drop allowed neutrals, then
    fail only when the meaningful systems collapse — all three chromatic
    primaries identical, all three chromatic systems identical, or (for
    neutral-only palettes) one identical neutral ground with nothing else."""
    if len(directions) < 3:
        return []
    # [his test day finding 1, 2026-09-29: "No hot pink", written in two of design 116's colour lines, was read as naming
    # pink, and three colour worlds read as one set. A colour a direction refuses is not a colour it names: each line is
    # read with its negated spans set aside, as the module's other checks read theirs. The three rules below unchanged]
    systems = [strip_negated_spans(str(d.get("color_system", ""))) for d in directions]
    sequences = [_anchor_sequence(s) for s in systems]
    chromatics = [[a for a in seq if a not in SHARED_NEUTRAL_ALLOWED]
                  for seq in sequences]
    if all(not chroma for chroma in chromatics):
        grounds = [seq[0] if seq else "" for seq in sequences]
        if all(grounds) and len(set(grounds)) == 1:
            return ["PALETTE_SYSTEMS_NOT_DISTINCT"]
        return []
    if not all(chromatics):
        return []                    # cannot read every system — no verdict
    primaries = [chroma[0] for chroma in chromatics]
    if len(set(primaries)) == 1:
        return ["PALETTE_SYSTEMS_NOT_DISTINCT"]
    if len({frozenset(chroma) for chroma in chromatics}) == 1:
        return ["PALETTE_SYSTEMS_NOT_DISTINCT"]
    hex_lists = [tuple(sorted({h.lower() for h in _HEX_RE.findall(s)}))
                 for s in systems]
    if all(hex_lists) and len(set(hex_lists)) == 1:
        return ["PALETTE_SYSTEMS_NOT_DISTINCT"]
    return []


#: [His answer 4 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "check the one house accent" — his
#: ruling of test day finding 1 (2026-09-29): "my brief's colours win, with BBROSE's logo and one house accent", told to
#: the planner since and never checked.] The house's own colours, by the names its canonical colour systems give them
#: (`seed_bbrose`: CS-001 Blush Core and CS-002 Nude Warm), longest first — their grounds' cream and the shared neutrals
#: left out, as the palette check leaves them; the two golds (Rose Gold, Warm Gold) one metal, by its plain name too
HOUSE_COLOUR_WORDS = ("deep rose", "cocoa rose", "rose gold", "warm gold", "pale petal", "soft sand", "blush", "gold")
#: the one colour each of them is counted as: every gold the house's one metal
HOUSE_COLOUR_OF = {"rose gold": "gold", "warm gold": "gold"}
HOUSE_ACCENTS_OVER_ONE = "HOUSE_ACCENTS_OVER_ONE"


def house_accents(brief, direction) -> list:
    """The house's colours (``HOUSE_COLOUR_WORDS``) a direction's ``color_system`` names — its affirmative spans, read
    as the palette check reads them — that the brief's own colours do not name, each once, in first-mention order."""
    text = " ".join(strip_negated_spans(str(direction.get("color_system", ""))).lower().replace("-", " ").split())
    taken, found = [], []
    for word in HOUSE_COLOUR_WORDS:
        for m in re.finditer(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text):
            if any(m.start() < end and m.end() > start for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), HOUSE_COLOUR_OF[word] if word in HOUSE_COLOUR_OF else word))
    briefed = " ".join(str(c).lower().replace("-", " ") for c in (brief.get("preferred_colors") or ()))
    out = []
    for _pos, colour in sorted(found):
        if colour not in out and not re.search(r"(?<![a-z])" + re.escape(colour) + r"(?![a-z])", briefed):
            out.append(colour)
    return out


def _check_house_accents(brief, directions):
    """[His answer 4 of 2026-10-02.] Where the brief names its colours, a direction that names more than ONE of the
    house's colours the brief does not is refused, by its place: ``HOUSE_ACCENTS_OVER_ONE:direction[i]``. A brief that
    names no colours keeps the house's colours, as before."""
    if not [c for c in (brief.get("preferred_colors") or ()) if str(c).strip()]:
        return []
    return [f"{HOUSE_ACCENTS_OVER_ONE}:direction[{i}]" for i, d in enumerate(directions)
            if isinstance(d, dict) and len(house_accents(brief, d)) > 1]


def brief_sets_colours(brief) -> bool:
    """[His test finding on design 118, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 833f82a): "When the brief sets
    one colour family, the three directions must differ by idea, layout, pattern and type, not by colour. ... Different
    colours are required only when the brief leaves colour open."] True when the brief names its colours: its three
    directions may then share them, and the palette check (`_check_palette_distinctness`) stands down — the directions
    are told apart by the semantic checks' layout, hierarchy, typography, motif and tone, as before."""
    return bool([c for c in ((brief or {}).get("preferred_colors") or ()) if str(c).strip()])


def palette_evidence(directions) -> dict:
    """§BH68(a): what `_check_palette_distinctness` measured, per direction, and which of its rules fired — the
    chromatic anchors in first-mention order (the first is the PRIMARY, by the writing convention it reads), the
    ground where a palette is all neutral, and the hexes."""
    rows = []
    for direction in directions:
        system = strip_negated_spans(str(direction.get("color_system", "")))      # finding 1: what it names, as read
        sequence = _anchor_sequence(system)
        chroma = [a for a in sequence if a not in SHARED_NEUTRAL_ALLOWED]
        rows.append({"primary": chroma[0] if chroma else None, "chromatic": chroma,
                     "ground": sequence[0] if sequence else None,
                     "hexes": sorted({h.lower() for h in _HEX_RE.findall(system)})})
    rule = None
    if len(rows) >= 3:
        if all(not r["chromatic"] for r in rows):
            rule = "the three palettes are all neutral on one ground" if len({r["ground"] for r in rows}) == 1 else None
        elif all(r["chromatic"] for r in rows):
            if len({r["primary"] for r in rows}) == 1:
                rule = "the three open on the same primary chromatic colour"
            elif len({frozenset(r["chromatic"]) for r in rows}) == 1:
                rule = "the three name the same set of chromatic colours"
            elif all(r["hexes"] for r in rows) and len({tuple(r["hexes"]) for r in rows}) == 1:
                rule = "the three carry the same hexes"
    return {"rows": rows, "rule": rule}


def shared_motif_evidence(directions, group) -> list:
    """§BH68(a): per direction, the words of core-motif ``group`` that `_check_shared_core_motif` found in its
    affirmative clauses."""
    words = _MOTIF_GROUPS.get(group, ())
    found = []
    for direction in directions:
        clauses = _affirmative_clauses(*(direction.get(f, "") for f in _MOTIF_FIELDS))
        found.append(sorted({w.strip() for w in words for clause in clauses if w in clause}))
    return found


def shared_motif_counts(directions, group) -> list:
    """Per direction, how many of its affirmative clauses name a word of core-motif ``group`` — where the motif is the
    direction's own and where it only passes through (his test day finding 1, 2026-09-29: on design 116 his Tropical
    Garden named rose petals in four clauses, the other two in one each, and the retry was told to strip it)."""
    words = _MOTIF_GROUPS.get(group, ())
    return [sum(1 for clause in _affirmative_clauses(*(d.get(f, "") for f in _MOTIF_FIELDS))
                if any(w in clause for w in words)) for d in directions]


def asked_motif_words(groups) -> list:
    """``[(group, words)]`` for the groups his brief asks for — what the planner is told it may carry in all three."""
    return [(group, tuple(w.strip() for w in _MOTIF_GROUPS.get(group, ()))) for group in groups or ()]


def motif_rule_words() -> tuple:
    """Every core-motif group and the words `_check_shared_core_motif` reads for it, and the fields it reads — the
    check's own, so what the planner is told is what is measured."""
    return [(group, tuple(w.strip() for w in words)) for group, words in _MOTIF_GROUPS.items()], _MOTIF_FIELDS


def shared_motif_words(group) -> tuple:
    """§BH68(a): every word `_check_shared_core_motif` counts for core-motif ``group``."""
    return tuple(w.strip() for w in _MOTIF_GROUPS.get(group, ()))


def structure_evidence(brief, document, directions, record_dimensions_mm=()) -> dict:
    """§BH68(a): per scope `_check_structure_assumptions` refused, the first clause it refused and what it matched."""
    if (brief.get("dimensions") or "").strip():
        return {}
    scopes = _structure_scopes(document, directions, record_dimensions_mm)
    out = {}
    for label, texts in scopes:
        for clause in _affirmative_clauses(*texts):
            match = (_DIMENSION_RE.search(clause) or _DIMENSION_PAIR_RE.search(clause))
            term = match.group(0) if match else next((t for t in _CLOSURE_TERMS if t in clause), None)
            if term:
                out[label] = {"clause": clause.strip(), "matched": term}
                break
    return out


__all__ = ["validate_direction_content", "coverage_cap_percent", "palette_evidence", "shared_motif_evidence",
           "shared_motif_words", "structure_evidence", "record_sizes_neutralised", "RECORD_SIZE_TEXT",
           "coverage_findings", "SHARED_NEUTRAL_ALLOWED", "HOUSE_COLOUR_WORDS", "HOUSE_ACCENTS_OVER_ONE",
           "house_accents", "brief_sets_colours",
           "COVERAGE_STRUCTURED", "COVERAGE_AREA", "COVERAGE_DERIVED",
           "COVERAGE_UNKNOWN"]
