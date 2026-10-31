"""§BH65(c) — THE ONE CONTRACT between what the planner writes and what the composer draws.

OWNER RULED 2026-09-22 (§BH65(c), ``OWNER_BLOCKER_CLEARANCE.md:23150-23253``, LIVE), repeating §BH57(c):

    "It knows eight node types, two fills, two treatments, while the planner writes engraved fields, tactile
    relief and spot-UV gloss. [...] make the mismatch impossible to repeat — the planner may specify only what
    the composer can draw, or the composer learns every word the planner writes, checked by one contract so
    this cannot silently diverge again."

THE BRANCH TAKEN, AND WHY. The composer learns the planner's words. The §BH60 clone measured the concept engine
as the part that works — it reached the owner's own elements from a brief that named none of them — so muzzling
it would throw away the half that works. And the planner's prompts are FROZEN through §BH65(d): (d) re-runs the
same brief, and a prompt edit would make the before and after two different planners.
  §BH67(a), OWNER RULED 2026-09-24 (``OWNER_BLOCKER_CLEARANCE.md:23350``, LIVE), WITHDREW that reading: the §BH60
  planner had been shown the original — FB2060 named 3 times in its directions, 9 in the void run, 0 in the clean
  one. The branch stands on its own reason: the composer learns every word, so the planner is never muzzled.

WHAT A TERM IS. Every word the planner is TAUGHT to write (its three prompts, pinned below by hash) and every word
it was MEASURED writing (60 directions and 15 Gate-1 variation records in the dev database, read-only, 2026-09-23)
is a term here, with ONE status:

  DRAWN        the composer draws it. Evidence is a node of the Document the run composed; a capability the
               emitter writes as its own PDF construct is proved on the emitted bytes by the conformance test.
  APPROXIMATED the composer draws a declared stand-in and says what it is (``how``) — never presented as the
               thing itself.
  TEACHING     the composer does not draw it YET. Each §BH65(c) commit shrinks this set, and the conformance test
               pins it, so it only ever shrinks by a commit that says so.
  GOVERNED     another RULED layer decides it and §BH55(3) freezes that layer: the composer draws what the layer
               chooses, not the planner's word (the face words — the role layer of §BH32(e)/§BH33 picks every
               face; the separations record decides white underbase and overprint).
  REFUSED      not drawable on this target (a die-cut is structure, not print). The prompts are frozen, so a
               refused word still in a prompt is pinned as a prompt change OWED, never quietly left.

THREE THINGS HOLD THE TWO SIDES TOGETHER:
  1. ``PLANNER_TEXTS_AUDITED`` pins a hash of every planner prompt this contract was audited against. Editing a
     prompt fails the conformance test until its words are re-declared here.
  2. The conformance tests prove every status: against the prompts and the four motif classifiers
     (``apps/pipeline/tests/test_design_direction_generator.py``, ``test_container_motif.py``) and against the
     emitted bytes (``apps/ire/tests/test_pdf_ai_emitter.py``).
  3. Every container run writes ``composer_vocabulary_realization/1.0``: each term the selected concept used,
     whether that run's Document drew it, and a NAMED code for each it did not. REPORT ONLY — it gates nothing,
     because §BH65 sets no threshold and governance stands still (§BH55(3)).

WHAT IT CANNOT SEE, SAID SO IT IS NOT ASSUMED: a word no term declares is invisible to the realization record.
The lexicon was built from the 75 real outputs above; a new word the model starts writing needs a new term.

Pure: no Django, no ORM. The planner's prompt constants are imported lazily, inside the functions that read them.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CONTRACT = "composer_vocabulary/1.0"
SCHEMA = "container_composer_vocabulary_realization/1.0"

DRAWN = "DRAWN"
APPROXIMATED = "APPROXIMATED"
TEACHING = "TEACHING"
GOVERNED = "GOVERNED"
REFUSED = "REFUSED"
STATUSES = (DRAWN, APPROXIMATED, TEACHING, GOVERNED, REFUSED)

UNDRAWN_CODE = "COMPOSER_VOCABULARY_UNDRAWN"
GOVERNED_CODE = "COMPOSER_VOCABULARY_GOVERNED"
REFUSED_CODE = "COMPOSER_VOCABULARY_REFUSED"
#: §BH67(b)3: a finish the concept's words only EVOKED ("tactile contrast") and never specified — read, recorded by
#: name, and not plated; it is not a finish the composer failed to draw
EVOKED_CODE = "COMPOSER_VOCABULARY_EVOKED_NOT_SPECIFIED"

AXES = ("finish", "primitive", "motif", "layout", "typography", "structure")


@dataclass(frozen=True)
class Term:
    key: str
    axis: str
    status: str
    #: the composer's name for what draws it — the key the evidence table reads
    capability: str
    #: one line: how it is drawn, what stands in for it, or why it is not
    how: str
    #: the planner's words for it, lower case; "-" matches a hyphen, a space or nothing
    words: tuple[str, ...]


# ---------------------------------------------------------------------------------------------------------------
# THE TERMS. Status is the MEASURED state of the composer at this commit, not the plan.
# ---------------------------------------------------------------------------------------------------------------

#: §BH65(c)2 — how every finish is drawn. Until (c)2: "the graph has no finish of any kind (graph.py: 8 node types,
#: SolidFill + GradientFill, opacity + clip); the concept's finish_signature reaches the motif spec's
#: `finish_assignments`, which is always {}" — the measured state at (c)1, kept here so the change reads.
_FINISH_DRAWN = ("graph.Finish on the element the concept's finish clause names (container_finishes): page 1 DEPICTS "
                 "it and its PLATE prints from its own page after the artwork, a 100 % black mask in register")

TERMS: tuple[Term, ...] = (
    # --- finishes: what the press does after the ink --------------------------------------------------------
    Term("foil", "finish", DRAWN, "finish:foil", _FINISH_DRAWN,
         ("foil", "foils", "foiled", "hot-foil", "hot-stamp", "hot-stamped", "foil-stamped", "cold-foil",
          "gilded", "gilt")),
    Term("metallic_ink", "finish", DRAWN, "finish:metallic_ink", _FINISH_DRAWN,
         ("metallic", "pearlescent", "pearl", "iridescent", "shimmer", "metallic-ink")),
    Term("spot_uv", "finish", DRAWN, "finish:spot_uv", _FINISH_DRAWN,
         ("spot-uv", "spot-gloss", "gloss-uv", "uv-gloss", "uv-varnish", "raised-uv", "uv-mask")),
    Term("gloss_varnish", "finish", DRAWN, "finish:gloss_varnish", _FINISH_DRAWN,
         ("gloss", "glossy", "high-gloss", "lacquer", "lacquered", "varnish", "varnished", "aqueous", "satin")),
    Term("soft_touch", "finish", DRAWN, "finish:soft_touch", _FINISH_DRAWN,
         ("matte", "matt", "soft-touch", "velvet", "laminate", "laminated", "lamination")),
    Term("emboss", "finish", DRAWN, "finish:emboss", _FINISH_DRAWN,
         ("emboss", "embossed", "embossing", "blind-emboss", "blind-embossed", "relief", "raised", "tactile",
          "sculpted")),
    Term("deboss", "finish", DRAWN, "finish:deboss", _FINISH_DRAWN,
         ("deboss", "debossed", "debossing")),
    Term("finish_mask", "finish", DRAWN, "finish:plate",
         "a finish MASK is the plate a finish prints from — each on its own page after the artwork",
         ("finish-mask", "finish-masks", "spot-mask", "spot-masks")),
    Term("white_ink", "finish", GOVERNED, "record:container_production_separations/1.0",
         "white underbase is decided by the separations record (CONTAINER_WHITE_UNDERBASE_REQUIRED), not drawn",
         ("white-ink", "underbase", "white-underbase")),
    Term("overprint", "finish", GOVERNED, "record:container_production_separations/1.0",
         "overprint and knockout are per-separation fields of the separations record, not artwork",
         ("overprint", "knockout")),

    # --- primitives and treatments: what the composer draws with ---------------------------------------------
    Term("bezier_path", "primitive", DRAWN, "path", "graph.Path: MoveTo / LineTo / CubicTo / ClosePath",
         ("bezier", "bézier", "vector-path", "closed-path", "compound-path")),
    Term("solid_fill", "primitive", DRAWN, "solid_fill", "graph.SolidFill",
         ("solid-fill", "flat-fill", "flat-colour", "flat-color")),
    Term("gradient", "primitive", DRAWN, "gradient_fill",
         "graph.GradientFill, linear or radial; emitted as a PDF shading",
         ("gradient", "gradients", "radial-gradient", "linear-gradient", "ombre", "ombré")),
    Term("opacity", "primitive", DRAWN, "opacity", "node and fill opacity",
         ("opacity", "translucent", "translucency", "semi-transparent", "transparency")),
    Term("clip_mask", "primitive", DRAWN, "clip", "Group.clip / Image.clip — a hard clipping path",
         ("clipping-mask", "clipping-path", "clip", "clipped", "clipping")),
    Term("stroke_rule", "primitive", DRAWN, "stroke", "graph.Stroke on a Path: a rule, hairline or keyline",
         ("hairline", "hairlines", "rule", "rules", "keyline", "outline", "outlined", "stroke")),
    Term("pattern_fill", "primitive", DRAWN, "pattern_fill",
         "§BH65(c)4: graph.PatternFill — lines, cross-hatch, dots, grain, rings — native vector marks cut to the shape",
         ("pattern", "patterned", "repeat", "repeating", "tile", "tiled", "tiling", "lattice", "all-over")),
    Term("texture_fill", "primitive", DRAWN, "texture_fill",
         "§BH65(c)4: a PatternFill grain or dot stipple — vector marks, never a raster texture",
         ("texture", "textured", "grain", "grained", "linen", "stipple", "stippled", "halftone")),
    Term("engraved_line_field", "primitive", DRAWN, "line_field",
         "§BH65(c)4: the engraved_field language — fine diagonal hatching crossed at a wider spacing, a "
         "PatternFill of lines",
         ("engraved", "engraving", "engrave", "etched", "etching", "hatch", "hatched", "hatching", "guilloche",
          "linework", "line-art", "fine-line")),
    Term("blend_mode", "primitive", DRAWN, "blend_mode",
         "§BH65(c)5: a node's blend_mode, emitted as the PDF blend mode in its own graphics state; the concept's own "
         "blend words set it on the concept's decoration (concept_front)",
         ("blend", "blending", "blend-mode", "multiply", "soft-light", "screen-blend", "overlay-blend")),
    Term("soft_mask", "primitive", DRAWN, "soft_mask",
         "§BH65(c)6: Group.opacity_mask — a true PDF luminosity soft mask, declared a transparency group so the "
         "preview's renderer honours it. A GradientFill's own per-stop opacity is still painted at ONE alpha "
         "(pdf_ai._paint_gradient, §BH50(d)-0), unchanged: the fidelity reader reads that value",
         ("fade", "fades", "faded", "fading", "feather", "feathered", "vignette", "soft-mask", "opacity-mask",
          "gradient-mask", "dissolve", "dissolving")),
    Term("glow", "primitive", DRAWN, "glow",
         "§BH65(c)6: a disc under a radial soft mask fading to nothing (concept_front: the concept's own glow words)",
         ("glow", "glows", "glowing", "luminous", "luminescent")),
    Term("soft_shadow", "primitive", APPROXIMATED, "soft_shadow",
         "§BH65(c)7: a stepped VECTOR shadow — the silhouette offset and drawn 8 times at 1/8 of its alpha, the "
         "stroke widening to twice the blur, so the edge softens — PDF has no blur, and this is never a raster",
         ("shadow", "shadows", "drop-shadow", "soft-shadow", "cast-shadow")),

    # --- layout: where the motif sits -------------------------------------------------------------------------
    Term("window", "layout", GOVERNED, "layout:window",
         "§BH65(c)3 draws it (compose_container.draw_concept_elements: the framed panel, its interior as the colour "
         "field says, the motif cut to it); WHERE it prints on the container front is §AU1's (C8, :5652) — above the "
         "mark's clear space when there is room, never below the supporting line — and what cannot print is recorded "
         "with its millimetres; ON A FACE (§BH66(a), :23254) the concept's own arrangement draws it where its words put it, inside the mark's clear space and with no motif behind the mark (compose_container._concept_face)",
         ("window", "windows", "cartouche", "medallion", "framed-panel")),
    Term("frame_ring", "layout", GOVERNED, "layout:frame",
         "§BH65(c)3 draws it (compose_container.draw_ring); on the container front §AU1 (C8, :5652) keeps it off — "
         "'nothing else prints on the front', and a ring prints its lower stroke below the supporting line; ON A FACE (§BH66(a), :23254) the concept's own arrangement draws it where its words put it, inside the mark's clear space and with no motif behind the mark (compose_container._concept_face)",
         ("frame", "framed", "framing", "border", "bordered", "ring", "rule-ring", "circumference")),
    Term("band", "layout", GOVERNED, "layout:band",
         "§BH65(c)9 draws it (the concept's motif as a FIELD across its region); where it prints on the container "
         "front is §AU1's (C8, :5652), as for the window — and a band on a surface this sheet does not draw, a "
         "compact's side band, is named NOT_DRAWN by the finish record; ON A FACE (§BH66(a), :23254) the concept's own arrangement draws it where its words put it, inside the mark's clear space and with no motif behind the mark (compose_container._concept_face)",
         ("band", "bands", "banded", "stripe", "stripes", "striped")),
    Term("edge_led", "layout", GOVERNED, "layout:edge",
         "§BH65(c)3 draws it (the motif led from its region's lower edge); where it prints on the container front "
         "is §AU1's, as for the window; ON A FACE (§BH66(a), :23254) the concept's own arrangement draws it where its words put it, inside the mark's clear space and with no motif behind the mark (compose_container._concept_face)",
         ("edge-led", "asymmetric", "asymmetrical", "off-centre", "off-center", "lower-edge")),
    Term("centred_stack", "layout", DRAWN, "layout:centred_stack",
         "the direct-print hierarchy: centred live-text tiers (compose_container._native_decoration)",
         ("centred", "centered", "centre-aligned", "center-aligned", "stacked", "stack")),

    # --- typography --------------------------------------------------------------------------------------------
    Term("live_type", "typography", DRAWN, "live_text", "graph.TextRun, live and editable",
         ("live-typography", "live-type", "live-text", "typeset")),
    Term("tracking", "typography", DRAWN, "tracking",
         "§BH65(c)8: TextRun.tracking_em — letter-spacing after every glyph but the last; the name tier takes the "
         "concept's own tracking words, and the text box every instrument reads is the box it prints",
         ("tracked", "tracking", "letterspaced", "letter-spaced", "letterspacing", "letter-spacing",
          "wide-tracked", "spaced-caps")),
    Term("small_caps", "typography", APPROXIMATED, "small_caps",
         "§BH65(c)8: printed as CAPITALS at the run's own size — a drawn small cap would print its lower-case "
         "letters under the size the §W2 floor instruments read",
         ("small-caps",)),
    Term("bilingual", "typography", GOVERNED, "arabic_run",
         "on the container front §AU1 (C8, :5652) rules EXACTLY ONE supporting line — a contract number only a "
         "superseding ruling changes — so an Arabic line under the name is a second tier the owner has not ruled; "
         "ON A FACE (§BH66(a), :23254) the Arabic line is the concept's own element, set from Product.name_ar as held "
         "where the concept's words put it (compose_container._concept_face)",
         ("arabic", "bilingual", "right-to-left", "rtl")),
    Term("typeface", "typography", GOVERNED, "font_roles",
         "the role layer (§BH32(e), §BH33) chooses every face — except that a face the concept NAMES from the granted "
         "set leads the product name (§BH67(c)5, concept_typeface; font_roles.CONCEPT_NAME); a style word names no "
         "face, and nothing outside the set is ever drawn",
         ("serif", "sans-serif", "sans", "script", "calligraphic", "didone", "monoline", "grotesk",
          "grotesque")),
    Term("lockup", "typography", DRAWN, "lockup",
         "the official lockup placed as fixed artwork — the controlled raster fallback until a vector master "
         "exists (compose_container: `logo`)",
         ("wordmark", "lockup", "logo")),

    # --- structure ---------------------------------------------------------------------------------------------
    Term("die_cut", "structure", REFUSED, "structure:die_cut",
         "a die-cut is carton STRUCTURE, not print on a container surface; the container composer has no "
         "surface to cut",
         ("die-cut", "die-cuts", "cut-out", "cutout", "perforation", "perforated")),
)

TERM_BY_KEY = {t.key: t for t in TERMS}

#: §BH67(b)3, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md:23350, LIVE): "THE FINISH READER INVENTS AN EMBOSS
#: from "tactile contrast". A finish that was not specified is not applied, the same rule as a colour." A finish
#: term is declared with two kinds of word. PROCESS words name what the press does and cuts a plate for — "emboss",
#: "hot-stamp", "spot UV", "varnish", "soft-touch". EVOKING words say how a surface looks or feels — "tactile",
#: "relief", "raised", "sculpted", "matte", "glossy", "satin", "pearl", "shimmer", "metallic" — and a surface can
#: look or feel that way with the press doing nothing: a moulded lid is glossy, a sidewall is sculpted, "pearl" is a
#: colour. The contract still DECLARES every word, so every word the planner writes is read and recorded; only a
#: process word SPECIFIES the finish, and only a specified finish is plated (``container_finishes``). The table is the
#: executor's reading of the trade's own names, each list stated here so a single word can be ruled on.
FINISH_PROCESS_WORDS = {
    "foil": ("foil", "foils", "foiled", "hot-foil", "hot-stamp", "hot-stamped", "foil-stamped", "cold-foil",
             "gilded", "gilt"),
    "metallic_ink": ("metallic-ink",),
    "spot_uv": ("spot-uv", "spot-gloss", "gloss-uv", "uv-gloss", "uv-varnish", "raised-uv", "uv-mask"),
    "gloss_varnish": ("lacquer", "lacquered", "varnish", "varnished", "aqueous"),
    "soft_touch": ("soft-touch",),
    "emboss": ("emboss", "embossed", "embossing", "blind-emboss", "blind-embossed"),
    "deboss": ("deboss", "debossed", "debossing"),
}
#: an evoking word that DOES name the process when the clause also names the process's own noun beside it:
#: "metallic rose-gold ink" is metallic ink; "velvet lamination" is the trade's name for soft-touch film. "Matte
#: laminate" is not here: a matte film is not a soft-touch film, and the composer has no plate for it.
FINISH_PROCESS_PAIRS = {
    "metallic_ink": {"metallic": ("ink", "inks"), "pearlescent": ("ink", "inks")},
    "soft_touch": {"velvet": ("laminate", "laminated", "lamination")},
}


def specifies(key: str, word: str, clause: str = "") -> bool:
    """Does ``word`` — a word ``scan`` found for the finish term ``key`` — SPECIFY that finish in ``clause``?"""
    word = _normalise(word).strip()
    for process in FINISH_PROCESS_WORDS.get(key, ()):
        if re.fullmatch(_word_re(process), word):
            return True
    for evoking, nouns in FINISH_PROCESS_PAIRS.get(key, {}).items():
        if re.fullmatch(_word_re(evoking), word) and any(
                re.search(_word_re(n), _normalise(clause)) for n in nouns):
            return True
    return False

#: the §BH65(c) set the composer is still being taught. The conformance test pins it; every commit that teaches
#: the composer a term moves it out of here in the same commit, and says so.
def teaching() -> tuple[str, ...]:
    return tuple(t.key for t in TERMS if t.status == TEACHING)


# ---------------------------------------------------------------------------------------------------------------
# THE MOTIF FAMILIES — every family name any of the four classifiers can emit, routed to what draws it.
# ---------------------------------------------------------------------------------------------------------------

#: The composing classifier's own routing (container_motif) — IMPORTED by it, so the two cannot diverge.
FAMILY_TO_LANGUAGE = {
    "GEOMETRIC_ABSTRACT": "strata_field",
    # 2B-3V-CORR-3 §2: droplet/particle families route to constellation generators by MAP, never by a second
    # lexical vote — POWDER/DEWDROP can structurally never resolve to ruled_field.
    "DEWDROP_CONSTELLATION": "dewdrop_constellation",
    "PARTICLE_FLOW": "powder_constellation",
    "POWDER_CONSTELLATION": "powder_constellation",
    "RADIANCE_LINES": "contour_terrain",
    "CONTOUR_STREAMS": "contour_terrain",
    "RIBBON_FLOW": "liquid_veil",
    # §BH67(b)1: petals are drawn as petals — a bloom of teardrop petals as the concept's words arrange them, where a
    # petal concept was drawn as scattered vertical ellipses (petal_scatter). A floral or blossom concept is a bloom.
    "SOFT_PETALS": "petal_bloom",
    "BOTANICAL_LINE_ART": "petal_scatter",
    "FLORAL_ABSTRACT": "petal_bloom",
    # §BH65(c)4: was "ruled_field", an approximation; a pattern repeat draws it as itself now
    "MICRO_PATTERN": "pattern_repeat",
    "TONAL_COLOR_FIELD": "quiet_ground",
    "EDITORIAL_RULE_SYSTEM": "ruled_field",
    "ENGRAVED_LINEWORK": "engraved_field",
    "HALO_RINGS": "halo_rings",
    # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    # "The lid is missing the concept's rule, ring and radial lines."] the radial family, drawn as itself: rays from one
    # centre, each ending in its node where the words say so. Until this task 110's "fine Bézier stroked lines emanating
    # from a single centre point" classified POWDER_CONSTELLATION — one hit each for three families, the tie to the
    # first listed — and a particle scatter was drawn. RADIANCE_LINES keeps its route: no recorded concept moves.
    "RADIAL_LINES": "radial_lines",
}
#: families whose nearest supported generator is an approximation (recorded as ``rendered_via``). §BH65(c)4 took
#: MICRO_PATTERN off this list: it has its own language now.
APPROXIMATE_FAMILIES = frozenset({"RADIANCE_LINES", "BOTANICAL_LINE_ART"})

#: The planner's OWN classifier (direction_signature.MOTIF_FAMILIES) validates that three directions are distinct;
#: it never composes. Its families are declared here so a family the planner reasons in is never one the composer
#: has not heard of. None = no route yet.
PLANNER_FAMILY_ROUTE = {
    "NONE_MATERIAL": None,           # "no motif" — nothing to draw, drawn as nothing
    "BOTANICAL": "petal_scatter",
    "LIQUID": "liquid_veil",
    # §BH65(c)4: the three that had no route
    "LINEAR_ENGRAVED": "engraved_field",
    "PATTERN_REPEAT": "pattern_repeat",
    "GEOMETRIC_HALO": "halo_rings",
    "GEOMETRIC_ABSTRACT": "strata_field",
    "PARTICLE_FLOW": "powder_constellation",
}

#: at (c)1: "the direct-print front — every production run since §BB7(c) — draws the §BB4 divider in the motif's
#: place; the language draws only as a reduced continuation on secondary BODY_* surfaces". §BH65(c)3:
_FRONT_DRAWS_THE_MOTIF = ("drawn on the direct-print front where §AU1 (C8, :5652) lets decoration print — above the "
                          "mark's clear space, or behind the type when the concept's own words put it there — and "
                          "recorded NOT_PLACED with its millimetres where it cannot; the §BB4 divider stays; and as a "
                          "reduced continuation on secondary BODY_* surfaces. ON A FACE (§BH66(a), :23254) it is drawn "
                          "where the concept's own words put it — in its window, or across the region they name — and "
                          "no motif element is drawn behind the mark")


def family_status(family: str) -> tuple[str, str | None, str]:
    """``(status, language, how)`` for a motif family name from ANY classifier. Unknown names are REFUSED by name,
    so a family the contract has not declared can never read as drawn."""
    if family == "NONE_MATERIAL":
        return DRAWN, None, "no motif was asked for; nothing is drawn"
    lang = FAMILY_TO_LANGUAGE.get(family) or PLANNER_FAMILY_ROUTE.get(family)
    if family not in FAMILY_TO_LANGUAGE and family not in PLANNER_FAMILY_ROUTE:
        return REFUSED, None, f"{family!r} is not a family this contract declares"
    if lang is None:
        return TEACHING, None, "no design language draws this family"
    if family in APPROXIMATE_FAMILIES:
        return APPROXIMATED, lang, f"its nearest language, {lang}, stands in for it — " + _FRONT_DRAWS_THE_MOTIF
    return DRAWN, lang, _FRONT_DRAWS_THE_MOTIF


def families() -> tuple[str, ...]:
    return tuple(sorted(set(FAMILY_TO_LANGUAGE) | set(PLANNER_FAMILY_ROUTE)))


# ---------------------------------------------------------------------------------------------------------------
# THE PLANNER TEXTS THIS CONTRACT WAS AUDITED AGAINST — a prompt edit fails the conformance test until re-declared.
# ---------------------------------------------------------------------------------------------------------------

PLANNER_TEXTS_AUDITED = {
    # §BH68(a), 2026-09-24: re-declared (3456634e2116cb47 -> 8cefb345ec389bc1) — each direction now DECLARES its
    # hierarchy family from the known set (NAME_FIRST, MOTIF_FIRST, MATERIAL_FIRST, LOGO_FIRST), named in the prompt and
    # in its JSON shape; the prompt teaches no word it did not teach before (the taught-terms test below still holds).
    # [his goal for the pitch, 2026-10-15, A (2)-(3)]: re-declared (8cefb345ec389bc1 -> 9898cba042e0c1a0) — the three
    # roles (trend-led, bold, minimal) named in the three-different paragraph, the logo the brand and never the theme,
    # no rose or arch unasked, "rose oil → petals" no longer the subject's example; no word is taught that was not before.
    "design_direction_generator.DIRECTOR_SYSTEM": "9898cba042e0c1a0",
    # §BH70(1), 2026-09-27: re-declared (adfbfea729b685bb -> 02447167234cdd46) — "The primary container itself (jar, bottle,
    # tube, compact) ... label zones" names the product itself, whatever its form (bottle, jar, tube, compact or palette,
    # lipstick, mascara, pencil), and its printed surfaces; no word is taught that was not before.
    # §BH71 PART 3, 2026-09-28: re-declared (02447167234cdd46 -> 12b3b7429943694e) — the list of forms "whatever its
    # form" names grows by the five the system now draws (tin, sachet, oval stick, aerosol can, ampoule); no word is
    # taught that was not before.
    "design_direction_generator.TARGET_GUIDANCE[product_container]": "12b3b7429943694e",
    # §BH67(c)4, 2026-09-24: both re-declared — the Gate-1 brief no longer forces the July house identities onto the
    # three slots (a2d8c169d7f28161 -> 853555ec6bf63809; f2b6aa13d3b5a3a3 -> 07e8e05947631cf2). The directives stop
    # teaching centred_stack, gloss_varnish and spot_uv — the words of the retired slot briefs — and the system prompt
    # stops teaching window, which only its forced id "A_PETAL_WINDOW" taught; no word is taught that was not before.
    # §BH70(1), 2026-09-27: both re-declared (853555ec6bf63809 -> ff436fc9c7af01b3; 07e8e05947631cf2 -> 0a7ab023748bfc95)
    # — item 4 of the list the owner was sent: the Gate-1 planner was told every product is "a bottle or tube" and that
    # each concept varies its "cap/body relationship". It is told the product's own form, as its brief and product
    # block name it, and the CLOSURE/body relationship (a cap, a lid, a clasp or none); the render is "of the product".
    # The JSON key `cap_body_signature` stays — the records carry it. No word is taught that was not before.
    # [his goal for the pitch, 2026-10-15, A (3)-(4)]: re-declared (ff436fc9c7af01b3 -> 93747948bd21277a) — the house
    # motifs are taken only where the brief asks (no rose, petals or arch unasked), and DEPTH AND DETAIL ON THE PRINTED
    # FACES is asked for: it teaches engraved_line_field (hatching), pattern_fill and glow, all DRAWN; it stops teaching
    # edge_led, the dewdrop constellation's "led from one side or the lower edge".
    "container_gate1.CONTAINER_GATE1_DIRECTIVES": "9b4361ad386d9ab2",
    # [his test findings on design 121, 2026-10-07, item 1] CONTAINER_SYSTEM re-declared (0a7ab023748bfc95 ->
    # fc25a70e5c4f7ead) — its JSON shape asks each variation for its direction's "direction_id" in a field of its own,
    # "never inside variation_id" (the live model folded the ids into its names on 121); no word is taught that was not
    # before. [His test blocker on design 122, 2026-10-07, item 3] re-declared (fc25a70e5c4f7ead -> e16f999f89516e9c) —
    # "THE PICTURE IS READ, NOT ONLY SEEN": the product alone, straight-on, on a plain backdrop that contrasts with it in
    # lightness, never in its own colour family; no word is taught that was not before.
    "container_gate1.CONTAINER_SYSTEM": "d2bf561b83568f12",
}

#: a REFUSED word the frozen prompts still teach — the prompt change is OWED, never made quietly. EMPTY since
#: §BH67(c)6, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md:23350, LIVE): "DIE-CUT: the planner's prompt stops
#: offering die-cut windows. The composer refuses them by name, so the planner may not promise them — §BH65(c)'s
#: contract, owed since (c)." DIRECTOR_SYSTEM's material/structural axis read "emboss relief, foil panel, die-cut
#: reveal at shelf scale" — a carton idea taught to a planner that also plans containers — and now reads "finish
#: contrast at shelf scale". No target draws a die-cut window: the container composer has no surface to cut, and the
#: carton dieline engine cuts only its tuck-lock slits (`dielines/geometry/engine.py`, `stadium_cutouts`). The term
#: stays declared and REFUSED, so a planner that still writes the word is read, recorded and refused by name.
PROMPT_CHANGES_OWED: frozenset = frozenset()


def planner_texts() -> dict[str, str]:
    from apps.pipeline import design_direction_generator as ddg
    from apps.pipeline.services import container_gate1 as g1
    return {
        "design_direction_generator.DIRECTOR_SYSTEM": ddg.DIRECTOR_SYSTEM,
        "design_direction_generator.TARGET_GUIDANCE[product_container]": ddg.TARGET_GUIDANCE["product_container"],
        "container_gate1.CONTAINER_GATE1_DIRECTIVES": g1.CONTAINER_GATE1_DIRECTIVES,
        "container_gate1.CONTAINER_SYSTEM": g1.CONTAINER_SYSTEM,
    }


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------------------------------------------
# SCANNING — which terms a text uses, with negated spans removed first.
# ---------------------------------------------------------------------------------------------------------------

def word_pattern(word: str) -> str:
    """The regex a declared word matches with: "-" is a hyphen, a space or nothing. Shared with the finish parser so
    a target word and a term word are read the same way."""
    return _word_re(word)


def _word_re(word: str) -> str:
    parts = [re.escape(p) for p in word.split("-")]
    return r"(?<![a-z0-9])" + r"[-\s]?".join(parts) + r"(?![a-z0-9])"


_WORD_RE = [(t.key, re.compile(_word_re(w))) for t in TERMS for w in t.words]


def _normalise(text: str) -> str:
    text = str(text or "").lower()
    return re.sub(r"[\u2010-\u2015\u2212]", "-", text)


normalise = _normalise


def scan(text: str, *, strip_negation: bool = True) -> dict[str, list[str]]:
    """``{term key: [the words found]}`` for one text. Negated spans ("no foil", "never a photograph") are removed
    first by the planner's own stripper, so a refusal in the text never reads as a request.

    THE LONGEST WORD WINS ITS SPAN. "spot gloss" is spot UV and is NOT also a flood gloss varnish; "raised UV" is
    spot UV and not an emboss; "rule ring" is a frame ring. A shorter word inside a longer declared phrase is
    consumed by it, so a compound can never request two finishes the concept did not ask for."""
    text = _normalise(text)
    if strip_negation:
        from apps.pipeline.direction_signature import strip_negated_spans
        text = strip_negated_spans(text)
    matches = [(m.start(), m.end(), key, m.group(0).strip())
               for key, rx in _WORD_RE for m in rx.finditer(text)]
    matches.sort(key=lambda m: (-(m[1] - m[0]), m[0]))
    taken: list[tuple[int, int]] = []
    found: dict[str, set] = {}
    for start, end, key, word in matches:
        if any(start < e and s < end for s, e in taken):
            continue
        taken.append((start, end))
        found.setdefault(key, set()).add(word)
    return {key: sorted(words) for key, words in sorted(found.items())}


# ---------------------------------------------------------------------------------------------------------------
# EVIDENCE — did THIS run's Document draw it? Read from the product artwork only, never the sheet's furniture.
# ---------------------------------------------------------------------------------------------------------------

#: the groups that hold the product artwork (the rest is the sheet: title, reference photo, swatches, SKU). §BH65(c)2:
#: the dropper sheet names its product groups differently ("Bottle", "Bottle-Glass", "FrontArtworkFlat",
#: "Surface-BODY_BACK") — at (c)1 this read only the container sheet's two and so read NOTHING on a dropper run
_ARTWORK_GROUPS = ("Container", "Surfaces", "FrontArtworkFlat")
#: the §BB4 divider is a rule, never a motif
_DIVIDER = "rule-front-single"


def _artwork(doc) -> list:
    from apps.ire.graph import Group
    out: list = []

    def walk(node):
        out.append(node)
        if isinstance(node, Group):
            for c in node.children:
                walk(c)
    for top in getattr(doc.root, "children", []):
        if isinstance(top, Group) and (top.name in _ARTWORK_GROUPS or top.role == "product"
                                       or (top.name or "").startswith("Surface-")):
            walk(top)
    return out


def _named(nodes, pred) -> list[str]:
    return sorted({(getattr(n, "name", "") or type(n).__name__) for n in nodes if pred(n)})


def _decoration(nodes) -> list:
    """The artwork without the product's own structure: the silhouette outline and the body/cap fills are the
    drawing of the object, never its decoration."""
    return [n for n in nodes if not (getattr(n, "name", "") or "").startswith(("silhouette", "body", "cap"))]


def _ev_path(nodes):
    from apps.ire.graph import CubicTo, Path
    return _named(_decoration(nodes), lambda n: isinstance(n, Path) and any(isinstance(s, CubicTo) for s in n.segments))


def _ev_solid(nodes):
    from apps.ire.graph import SolidFill
    return _named(_decoration(nodes), lambda n: isinstance(getattr(n, "fill", None), SolidFill))


def _ev_gradient(nodes):
    from apps.ire.graph import GradientFill
    return _named(nodes, lambda n: isinstance(getattr(n, "fill", None), GradientFill))


def _ev_opacity(nodes):
    return _named(_decoration(nodes), lambda n: n.opacity < 1.0
                  or getattr(getattr(n, "fill", None), "opacity", 1.0) < 1.0)


def _ev_clip(nodes):
    from apps.ire.graph import Group, Image
    return _named(nodes, lambda n: isinstance(n, (Group, Image)) and n.clip is not None)


def _ev_stroke(nodes):
    from apps.ire.graph import Path
    return _named(_decoration(nodes), lambda n: isinstance(n, Path) and n.stroke is not None)


def _ev_text(nodes):
    from apps.ire.graph import TextRun
    return _named(nodes, lambda n: isinstance(n, TextRun))


def _ev_lockup(nodes):
    from apps.ire import brand_mark
    from apps.ire.graph import Image
    # [the owner's second answer of 2026-09-25: the lockup drawn from its approved vector master is the lockup too]
    return _named(nodes, lambda n: (isinstance(n, Image) or brand_mark.is_mark(n)) and n.name == "logo")


def _ev_centred_stack(nodes):
    from apps.ire.compose_container import FRONT_DIRECT_PRINT_GROUP
    from apps.ire.graph import Group, TextRun
    return _named(nodes, lambda n: isinstance(n, Group) and n.name == FRONT_DIRECT_PRINT_GROUP
                  and any(isinstance(c, TextRun) for c in n.children))


def _finished(kind: str | None):
    def reader(nodes):
        return _named(nodes, lambda n: any(kind is None or f.kind == kind for f in getattr(n, "finishes", ())))
    return reader


def _ev_named(suffix: str):
    def reader(nodes):
        return _named(nodes, lambda n: (getattr(n, "name", "") or "").endswith(suffix))
    return reader


def _ev_motif(nodes):
    from apps.ire.graph import Group
    return _named(nodes, lambda n: isinstance(n, Group) and n.name.startswith("motif")
                  and any(getattr(c, "name", "") != _DIVIDER for c in n.children))


#: capability -> the reader that finds it in the artwork. A capability with no reader has no evidence, so a
#: TEACHING term can never read as drawn — and the conformance test holds every DRAWN term to having one.
_EVIDENCE = {
    "path": _ev_path, "solid_fill": _ev_solid, "gradient_fill": _ev_gradient, "opacity": _ev_opacity,
    "clip": _ev_clip, "stroke": _ev_stroke, "live_text": _ev_text, "lockup": _ev_lockup,
    "layout:centred_stack": _ev_centred_stack, "motif": _ev_motif,
    # §BH65(c)3: the concept's own arrangement, by the names the composer gives it
    "layout:window": _ev_named("window-frame"), "layout:frame": _ev_named("frame-ring"),
    "layout:edge": _ev_named("motif-edge"),
    "layout:band": _ev_named("motif-field"),                                                          # (c)9
    # §BH66(a): the Arabic line a face draws — a run whose text is in the Arabic script
    "arabic_run": lambda nodes: _named(nodes, lambda n: getattr(n, "type", "") == "text"
                                       and any("\u0600" <= ch <= "\u06ff" for ch in (getattr(n, "text", "") or ""))),
    # §BH65(c)4: a pattern is drawn where an element's fill is one
    "tracking": lambda nodes: _named(nodes, lambda n: bool(getattr(n, "tracking_em", None))),        # (c)8
    "small_caps": lambda nodes: _named(nodes, lambda n: getattr(n, "text_case", None) == "upper"),
    "soft_shadow": lambda nodes: _named(nodes, lambda n: getattr(n, "shadow", None) is not None),   # (c)7
    "soft_mask": lambda nodes: _named(nodes, lambda n: getattr(n, "opacity_mask", None) is not None),   # (c)6
    "glow": lambda nodes: _named(nodes, lambda n: (getattr(n, "name", "") or "").endswith("glow")),
    "blend_mode": lambda nodes: _named(nodes, lambda n: bool(getattr(n, "blend_mode", None))),   # §BH65(c)5
    "pattern_fill": lambda nodes: _named(nodes, lambda n: getattr(getattr(n, "fill", None), "type", "") == "pattern"),
    "texture_fill": lambda nodes: _named(nodes, lambda n: getattr(getattr(n, "fill", None), "type", "") == "pattern"
                                         and n.fill.kind in ("grain", "dots")),
    "line_field": lambda nodes: _named(nodes, lambda n: getattr(getattr(n, "fill", None), "type", "") == "pattern"
                                       and n.fill.kind in ("lines", "crosshatch")),
    # §BH65(c)2: a finish is drawn where an element of the artwork carries it
    **{f"finish:{k}": _finished(k) for k in ("foil", "metallic_ink", "spot_uv", "gloss_varnish", "soft_touch",
                                              "emboss", "deboss")},
    "finish:plate": _finished(None),
}
EVIDENCE_READERS = frozenset(_EVIDENCE)


def evidence(capability: str, doc) -> list[str]:
    """The names of the artwork nodes that realise ``capability`` in ``doc`` — empty when nothing does."""
    reader = _EVIDENCE.get(capability)
    return reader(_artwork(doc)) if reader else []


# ---------------------------------------------------------------------------------------------------------------
# THE RUN'S RECORD
# ---------------------------------------------------------------------------------------------------------------

#: the selected concept's own words about its DESIGN. The render ``prompt`` is not read: it describes the scene
#: the packshot stands in ("on warm cream linen", "a shallow shadow to the right"), which is not print.
CONCEPT_FIELDS = ("typography_signature", "composition_signature", "motif_signature", "cap_body_signature",
                  "decoration_zone_signature", "color_field_signature", "finish_signature",
                  "native_reconstruction_plan")


def realization(structured: dict | None, doc, motif_spec: dict | None = None, *,
                finishes: dict | None = None) -> dict:
    """``container_composer_vocabulary_realization/1.0`` — every term the selected concept used, whether this
    run's Document drew it, and a named code for each it did not. Report only: nothing reads it as a gate.

    §BH65(c)2: ``finishes`` is the finish application's own rows — each (finish, target) the concept's sentence
    named, APPLIED with its nodes or NOT_DRAWN / REFUSED_NO_VECTOR_MASTER with the reason — carried here so the one
    record says where every finish went, and its codes join this record's."""
    record = {"schema_version": SCHEMA, "contract": CONTRACT, "read_from": [], "terms": [], "motif": None,
              "undrawn": [], "governed": [], "refused": [], "codes": [],
              "finishes": list((finishes or {}).get("applied") or [])}
    if not structured:
        record["state"] = "NO_STRUCTURED_RECORD"
        return record
    record["state"] = "READ"
    words_by_key: dict[str, set] = {}
    said_in: dict[str, list] = {}           # §BH67(b)3: each word with the text it was said in
    for field in CONCEPT_FIELDS:
        text = structured.get(field)
        if not text:
            continue
        record["read_from"].append(field)
        for key, hits in scan(str(text)).items():
            words_by_key.setdefault(key, set()).update(hits)
            said_in.setdefault(key, []).extend((w, str(text)) for w in hits)
    for term in TERMS:
        if term.key not in words_by_key:
            continue
        # §BH65(c)3: a GOVERNED term with a reader is read too — a window §AU1 let print is drawn, and says so
        ev = evidence(term.capability, doc) if term.status in (DRAWN, APPROXIMATED, GOVERNED) else []
        row = {"term": term.key, "axis": term.axis, "status": term.status, "words": sorted(words_by_key[term.key]),
               "drawn": bool(ev), "evidence": ev[:12]}
        record["terms"].append(row)
        if term.status == GOVERNED and not ev:
            # §BH66(a): a governed term the run DREW — a face's window, ring or Arabic line — is drawn, and carries
            # no code saying a ruling withheld it
            record["governed"].append(term.key)
            record["codes"].append(f"{GOVERNED_CODE}:{term.key}")
        elif term.status == REFUSED:
            record["refused"].append(term.key)
            record["codes"].append(f"{REFUSED_CODE}:{term.key}")
        elif not ev and term.axis == "finish" and not any(specifies(term.key, w, t) for w, t in said_in[term.key]):
            # §BH67(b)3: evoked, never specified — not plated by rule, so not a finish the composer failed to draw
            row["evoked_only"] = True
            record.setdefault("evoked", []).append(term.key)
            record["codes"].append(f"{EVOKED_CODE}:{term.key}")
        elif not ev:
            record["undrawn"].append(term.key)
            record["codes"].append(f"{UNDRAWN_CODE}:{term.key}")
    record["codes"].extend((finishes or {}).get("codes") or [])
    # §BH65(c)3: the arrangement the concept's words asked for, what the composer drew of it, and what it could not
    # place and why — carried from the document the composer built
    record["front"] = (getattr(doc, "metadata", None) or {}).get("concept_front")
    family = (motif_spec or {}).get("requested_family")
    if family:
        status, lang, how = family_status(family)
        ev = evidence("motif", doc)
        record["motif"] = {"family": family, "status": status, "language": lang, "how": how,
                           "drawn": bool(ev), "evidence": ev[:12]}
        if not ev:
            record["undrawn"].append(f"motif:{family}")
            record["codes"].append(f"{UNDRAWN_CODE}:motif:{family}")
    return record


__all__ = [
    "CONTRACT", "SCHEMA", "DRAWN", "APPROXIMATED", "TEACHING", "GOVERNED", "REFUSED", "STATUSES", "AXES",
    "UNDRAWN_CODE", "GOVERNED_CODE", "REFUSED_CODE", "EVOKED_CODE", "Term", "TERMS", "TERM_BY_KEY", "teaching",
    "FINISH_PROCESS_WORDS", "FINISH_PROCESS_PAIRS", "specifies",
    "FAMILY_TO_LANGUAGE", "APPROXIMATE_FAMILIES", "PLANNER_FAMILY_ROUTE", "family_status", "families",
    "PLANNER_TEXTS_AUDITED", "PROMPT_CHANGES_OWED", "planner_texts", "text_hash", "scan", "word_pattern", "normalise", "evidence",
    "EVIDENCE_READERS", "CONCEPT_FIELDS", "realization",
]
