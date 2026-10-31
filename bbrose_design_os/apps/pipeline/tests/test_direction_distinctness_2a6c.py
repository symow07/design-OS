"""Direction distinctness + originality corrections (Phase 2A-6C).

The task-#49 failure exposed two validator defects that rejected CORRECT
input: 'sans-serif' classified as SERIF_LED (collapsing every clean-sans set
into TYPOGRAPHY_NOT_DISTINCT), and anti-copy language ("must not be traced or
copied from the reference") flagged as an ORIGINALITY_VIOLATION.

These tests pin the contract's §3 target signatures as MUST-PASS and three
pastel recolorings as MUST-FAIL, and lock the originality polarity rule.
"""
from __future__ import annotations

import pytest

from apps.pipeline.direction_signature import (
    MIN_CLASSIFIED_PER_DIRECTION,
    MIN_MUTUAL_COMPARABLE_PER_PAIR,
    MIN_PAIRWISE_DIFFERENCES,
    PASSTHROUGH_DIMENSIONS,
    SIGNATURE_DIMENSIONS,
    UNCLASSIFIED,
    classify,
    direction_signature,
    explain_validation_failure,
    hierarchy_lead_segment,
    originality_violations,
    validate_semantic_distinctness,
)

# --- §3 contract target directions (Editorial Type Field / Radiant Geometric
# Halo / Powder Movement), encoded field-by-field from the contract. ---------

EDITORIAL_TYPE_FIELD = {
    "name": "Editorial Type Field",
    "design_axis": "typography-led",
    "layout_structure": "asymmetric editorial grid; oversized product "
                        "typography fills the front panel",
    "focal_hierarchy": "product name leads; typography is the artwork",
    "typography": "bold condensed modern sans-serif, large stacked wordmark",
    "color_system": "light blush pink, ivory and a minimal gold accent (pastel, tonal)",
    "graphic_elements": "no illustration; a very small controlled powder-dot "
                        "line accent under 10% of the panel",
    "emotional_tone": "refined, editorial, confident",
    "imagery_approach": "the concept render is a temporary reference only; "
                        "reconstruct as native vectors, do not trace it",
    "originality_notes": "original type-led system; do not reproduce the reference",
    "prompt_seed": "editorial type field, soft radiance",
}
RADIANT_GEOMETRIC_HALO = {
    "name": "Radiant Geometric Halo",
    "design_axis": "geometry-led",
    "layout_structure": "centered symmetrical composition with a circular "
                        "arched focal structure",
    "focal_hierarchy": "motif leads; the centered geometric structure is the "
                       "primary identity",
    "typography": "high-contrast serif for the name, paired with a restrained "
                  "sans for support",
    "color_system": "light sky blue, white and pale champagne (pastel, tonal)",
    "graphic_elements": "thin geometric halo, concentric arcs and controlled "
                        "radiance lines",
    "emotional_tone": "serene, calm, luminous",
    "imagery_approach": "temporary reference only; reconstruct the halo with "
                        "native vector geometry",
    "originality_notes": "original centered geometric identity; must not copy "
                         "the reference",
    "prompt_seed": "radiant geometric halo",
}
POWDER_MOVEMENT = {
    "name": "Powder Movement",
    "design_axis": "movement-led",
    "layout_structure": "diagonal corner-led movement crossing the front panel "
                        "and continuing onto one side panel",
    "focal_hierarchy": "motif leads; directional movement across panels is the "
                       "identity",
    "typography": "rounded geometric sans-serif, clean and humanist",
    "color_system": "light peach, soft mint and warm ivory (pastel, tonal)",
    "graphic_elements": "controlled native-vector powder stream, particles and "
                        "soft veil movement",
    "emotional_tone": "fresh, light and airy",
    "imagery_approach": "the reference render must not be traced; native "
                        "vectors only",
    "originality_notes": "original directional-movement system; do not "
                         "duplicate the reference",
    "prompt_seed": "powder movement across panels",
}
TARGETS = [EDITORIAL_TYPE_FIELD, RADIANT_GEOMETRIC_HALO, POWDER_MOVEMENT]


def _pastel_recoloring(palette):
    """One layout, one type style, one motif — only the palette hue changes."""
    return {
        "design_axis": "clean minimal cosmetics",
        "layout_structure": "centered symmetrical layout, product name centered",
        "focal_hierarchy": "product name leads",
        "typography": "clean modern sans-serif",
        "color_system": palette,
        "graphic_elements": "soft geometric arcs",
        "emotional_tone": "soft and elegant",
        "imagery_approach": "native vectors only",
        "originality_notes": "original",
        "prompt_seed": "soft radiance",
    }


class TestTargetsPass:
    def test_three_targets_are_meaningfully_distinct(self):
        codes, _ = validate_semantic_distinctness(TARGETS)
        assert codes == [], codes

    def test_targets_raise_no_originality_violation(self):
        assert originality_violations(TARGETS) == []

    def test_target_signature_matrix(self):
        sigs = [direction_signature(d) for d in TARGETS]
        # typography: three DIFFERENT systems (condensed sans / serif+sans /
        # geometric sans) — fine-grained taxonomy, all distinct
        typo = [s["typography_family"] for s in sigs]
        assert typo == ["CONDENSED_EDITORIAL_SANS", "MIXED_SERIF_SANS",
                        "GEOMETRIC_ROUNDED_SANS"], typo
        # three distinct motif families
        motif = {s["motif_family"] for s in sigs}
        # 2A-6D-CORR-2 §6: halo/concentric systems are their own family now
        assert motif == {"NONE_MATERIAL", "GEOMETRIC_HALO", "PARTICLE_FLOW"}
        # every direction clears the 5/7 coverage floor
        for s in sigs:
            classified = sum(1 for k, v in s.items()
                             if v not in ("", "UNCLASSIFIED"))
            assert classified >= 5, (s, classified)

    def test_each_pair_differs_on_at_least_three_dimensions(self):
        sigs = [direction_signature(d) for d in TARGETS]
        dims = list(sigs[0])
        for a in range(3):
            for b in range(a + 1, 3):
                diffs = [d for d in dims
                         if "UNCLASSIFIED" not in (sigs[a][d], sigs[b][d])
                         and sigs[a][d] != sigs[b][d]]
                assert len(diffs) >= 3, (a, b, diffs)


class TestRecoloringsFail:
    def test_three_pastel_recolorings_of_one_layout_fail(self):
        recolorings = [_pastel_recoloring(p) for p in
                       ("blush pink pastel", "sky blue pastel", "peach pastel")]
        codes, _ = validate_semantic_distinctness(recolorings)
        assert "DIRECTIONS_SUPERFICIALLY_VARIANT" in codes
        assert "TYPOGRAPHY_NOT_DISTINCT" in codes

    def test_identical_typography_across_all_three_fails(self):
        dirs = [dict(d, typography="clean modern sans-serif") for d in TARGETS]
        codes, _ = validate_semantic_distinctness(dirs)
        assert "TYPOGRAPHY_NOT_DISTINCT" in codes


class TestTypographyClassifierBugFix:
    def test_sans_serif_is_never_read_as_serif(self):
        # the original bug: "serif" substring of "sans-serif" → SERIF_LED
        for text in ("bold condensed modern sans-serif", "clean sans serif",
                     "rounded geometric sans-serif", "plain modern sans-serif"):
            assert "SERIF_LED" != classify(text, "typography_family"), text

    def test_genuine_serif_still_reads_serif_family(self):
        assert classify("classic roman serif", "typography_family") == "SERIF_LED"
        assert classify("refined didone serif",
                        "typography_family") == "HIGH_CONTRAST_SERIF"

    def test_serif_plus_sans_pairing_reads_mixed(self):
        assert classify("high-contrast serif for the name, paired with a "
                        "restrained sans for support",
                        "typography_family") == "MIXED_SERIF_SANS"


class TestTypographyTaxonomy:
    """§5 — two sans systems that differ in width/construction are two
    classes; the gate is refined, not weakened."""

    def test_condensed_editorial_vs_rounded_geometric_differ(self):
        a = classify("bold condensed editorial grotesk, oversized stacked name",
                     "typography_family")
        b = classify("soft rounded geometric sans", "typography_family")
        assert a == "CONDENSED_EDITORIAL_SANS"
        assert b == "GEOMETRIC_ROUNDED_SANS"
        assert a != b

    def test_rounded_geometric_vs_humanist_differ(self):
        a = classify("rounded geometric sans", "typography_family")
        b = classify("warm humanist sans with open apertures", "typography_family")
        assert a == "GEOMETRIC_ROUNDED_SANS"
        assert b == "HUMANIST_SANS"
        assert a != b

    def test_high_contrast_serif_plus_sans_is_mixed(self):
        assert classify("a high-contrast serif paired with a sans for support",
                        "typography_family") == "MIXED_SERIF_SANS"

    def test_three_identical_neutral_sans_collapse(self):
        dirs = [dict(EDITORIAL_TYPE_FIELD,
                     typography="neutral grotesk, clean and modern")
                for _ in range(3)]
        # differentiate the OTHER dimensions so ONLY typography could collapse
        for i, axis in enumerate(("typography-led", "geometry-led", "movement-led")):
            dirs[i] = dict(dirs[i], design_axis=axis)
        codes, _ = validate_semantic_distinctness(dirs)
        assert "TYPOGRAPHY_NOT_DISTINCT" in codes

    def test_two_sans_one_serif_does_not_collapse_typography(self):
        """§3 policy B: TYPOGRAPHY_NOT_DISTINCT fires only when ALL THREE are
        the same class. Two sans + one mixed is fine."""
        codes, _ = validate_semantic_distinctness(TARGETS)
        assert "TYPOGRAPHY_NOT_DISTINCT" not in codes


class TestOriginalityPolarity:
    def test_anti_copy_language_is_not_a_violation(self):
        anti = {"imagery_approach": "the reference must not be traced or "
                                    "copied into the production file",
                "originality_notes": "reconstruct as native vectors; do not "
                                     "reproduce the reference imagery"}
        assert originality_violations([anti]) == []

    def test_reconstruct_from_reference_is_not_a_violation(self):
        d = {"imagery_approach": "the concept render is a temporary reference "
                                 "only; rebuild it as native vectors"}
        assert originality_violations([d]) == []

    def test_genuine_reproduction_instruction_is_a_violation(self):
        d = {"concept_statement": "reproduce the competitor layout exactly",
             "graphic_elements": "copy the reference artwork one-to-one"}
        assert originality_violations([d, {}, {}]) == [
            "ORIGINALITY_VIOLATION:direction[0]"]

    def test_explicit_reproduction_phrase_is_a_violation(self):
        d = {"layout_structure": "make it identical to the reference layout"}
        assert originality_violations([d]) == ["ORIGINALITY_VIOLATION:direction[0]"]

    @pytest.mark.parametrize("wording", [
        "Baked Powder", "Polvo Horneado", "Soft Radiance", "Luminosidad Suave",
        "a soft radiant powder finish for BBROSE Baked Powder",
    ])
    def test_product_category_wording_is_never_a_violation(self, wording):
        d = {"concept_statement": wording, "prompt_seed": wording,
             "graphic_elements": wording}
        assert originality_violations([d]) == []


class TestRepairGuidance:
    def test_guidance_names_the_collapsed_dimension_and_demands_redesign(self):
        recolorings = [_pastel_recoloring(p) for p in
                       ("blush pink", "sky blue", "peach")]
        codes, _ = validate_semantic_distinctness(recolorings)
        lines = explain_validation_failure(recolorings, codes)
        text = "\n".join(lines)
        assert "TYPOGRAPHY_NOT_DISTINCT" in text
        assert "REPLACE" in text or "independently designed" in text
        # not a bare code dump — it must say what to change
        assert "typography" in text.lower()

    def test_guidance_explains_originality_without_banning_anti_copy(self):
        d = {"concept_statement": "reproduce the competitor layout exactly"}
        codes = originality_violations([d, {}, {}])
        lines = explain_validation_failure([d, {}, {}], codes)
        text = "\n".join(lines).lower()
        assert "original" in text
        assert "forbids copying" in text or "not the problem" in text


# ---------------------------------------------------------------------------
# §BH58(b)(c) — THE HIERARCHY DIMENSION WAS IMPLEMENTED AND BLIND.
#
# Measured over the twelve directions of tasks 84-87 — every run the owner's
# Rose Glow Palette brief has ever had — `hierarchy_family` was UNCLASSIFIED
# 12 times out of 12. Its cues ask for "name first" / "motif leads"; the
# planner has never once written that way. It writes an ordered list, which
# answers the same question better.
#
# Owner ruling §BH58(b): "a dimension which has been silently blank in every
# direction this system has ever written starts returning a value … an
# UNCLASSIFIED dimension was counting as nothing while the gate pretended it
# counted" — and "MIN_MUTUAL_COMPARABLE_PER_PAIR stays at 5. I am not touching
# it and neither are you."
# ---------------------------------------------------------------------------

#: §BH58(c): "classify all twelve from tasks 84, 85, 86 and 87, and report each one's
#: family. If the repair only recognises what task 87 happens to say, it is not a
#: classifier, and you will see that in the table." Verbatim, embedded so this is a
#: regression and not a live database read. Every one predates the reader.
HISTORICAL_HIERARCHIES = (
    (84, "Radiance Contour", "MOTIF_FIRST",
     "1. Arc-contour radiance field (full lid) \u2192 2. BBROSE rose-gold lockup \u2192 "
     "3. 'Rose Glow Palette' bilingual name block \u2192 4. Shade names on pan rims "
     "\u2192 5. Claims bar"),
    (84, "Petal Veil", "NAME_FIRST",
     "1. 'ROSE GLOW' large didone type \u2192 2. Petal-veil gradient field behind type "
     "\u2192 3. BBROSE rose-gold lockup \u2192 4. Arabic bilingual name \u2192 "
     "5. Shade identifiers \u2192 6. Claims bar at bottom"),
    (84, "Rose Relief", "MOTIF_FIRST",
     "1. Petal-tessellation emboss field (tactile, shelf-read) \u2192 2. BBROSE "
     "rose-gold foil lockup \u2192 3. Bilingual name (English + Arabic) \u2192 "
     "4. Shade colour strip \u2192 5. Claims icons"),
    (85, "Radiance Veil", "MOTIF_FIRST",
     "First read: radiance arc field covering the full lid. Second read: rose gold "
     "BBROSE lockup centred in the upper arc zone."),
    (85, "Petal Engraving", "MOTIF_FIRST",
     "First read: engraved linework field as a surface-level textural immersion. "
     "Second read: Blush name panel with BBROSE lockup."),
    (85, "Gilded Mirror", "LOGO_FIRST",
     "First read: large-scale BBROSE emboss-foil on the Warm Gold field. Second read: "
     "bilingual bold condensed name block on the Deep Rose panel."),
    (86, "Liquid Veil", "MOTIF_FIRST",
     "Primary: diagonal ribbon-flow field. Secondary: BBROSE lockup in rose-gold foil. "
     "Tertiary: bilingual serif product name."),
    (86, "Engraved Bloom", "MOTIF_FIRST",
     "Primary: engraved rose illustration (the dominant structural field, largest "
     "element). Secondary: bilingual slab-serif name."),
    (86, "Petal Architecture", "MOTIF_FIRST",
     "Primary: radial petal-polygon mandala (the dominant structural field, full lid). "
     "Secondary: BBROSE lockup (foil, centered)."),
    (87, "Radiance Arc", "MOTIF_FIRST",
     "Primary: open arc radiance field (geometric, expanding). Secondary: BBROSE "
     "wordmark in rose gold. Tertiary: bilingual product name in Deep Rose serif."),
    (87, "Liquid Veil", "MOTIF_FIRST",
     "Primary: flowing ribbon band field (three to five bands, diagonal cascade). "
     "Secondary: BBROSE wordmark in rose-gold foil centered in clear window."),
    (87, "Engraved Bloom Field", "MOTIF_FIRST",
     "Primary: tonal engraved contour-hatching field (perceived as surface texture "
     "before content is read). Secondary: rose-gold BBROSE wordmark floating above "
     "field."),
)


class TestHierarchyWasImplementedAndBlind:

    def test_all_twelve_historical_directions_now_classify(self):
        """§BH58(c). Zero of these twelve classified before; all twelve must now."""
        blank = [(t, n) for t, n, _e, text in HISTORICAL_HIERARCHIES
                 if classify(text, "hierarchy_family") == UNCLASSIFIED]
        assert blank == [], blank

    def test_each_of_the_twelve_reads_the_family_reported_to_the_owner(self):
        """The table in the §BH58 report, pinned. If any row moves, the report is stale."""
        got = [(t, n, classify(text, "hierarchy_family"))
               for t, n, _e, text in HISTORICAL_HIERARCHIES]
        want = [(t, n, e) for t, n, e, _text in HISTORICAL_HIERARCHIES]
        assert got == want

    def test_it_is_not_special_casing_task_87(self):
        """§BH58(c) in one assertion: "if the repair only recognises what task 87
        happens to say, it is not a classifier". Task 87 wrote three motif-led
        directions; a reader tuned to it would return one family for everything."""
        families = {classify(text, "hierarchy_family")
                    for _t, _n, _e, text in HISTORICAL_HIERARCHIES}
        assert families == {"MOTIF_FIRST", "NAME_FIRST", "LOGO_FIRST"}
        # and specifically: rows from runs that PREDATE this code carry the minority ones
        assert classify(HISTORICAL_HIERARCHIES[1][3], "hierarchy_family") == "NAME_FIRST"
        assert classify(HISTORICAL_HIERARCHIES[5][3], "hierarchy_family") == "LOGO_FIRST"

    def test_reading_the_dimension_REFUSES_two_of_the_owners_own_runs(self):
        """THE COST OF DOING THIS HONESTLY, pinned so it cannot be quietly tuned away.

        Tasks 86 and 87 each wrote three motif-led directions. With the dimension blind
        that was invisible; read, it collapses, and `hierarchy_family` IS in
        COLLAPSE_CODES. The repair that releases nothing is the one to trust.
        """
        for task in (86, 87):
            families = [classify(text, "hierarchy_family")
                        for t, _n, _e, text in HISTORICAL_HIERARCHIES if t == task]
            assert len(set(families)) == 1, task
        for task in (84, 85):
            families = [classify(text, "hierarchy_family")
                        for t, _n, _e, text in HISTORICAL_HIERARCHIES if t == task]
            assert len(set(families)) > 1, task


class TestHierarchyReaderRules:
    """The two rules the reader applies, each stated before the table was looked at."""

    def test_an_element_noun_outranks_a_material_adjective(self):
        """"engraved linework field" is a FIELD, made by engraving."""
        assert classify("Primary: engraved linework field. Secondary: name.",
                        "hierarchy_family") == "MOTIF_FIRST"

    def test_a_finish_with_no_element_noun_is_material_first(self):
        """...and MATERIAL_FIRST is still reachable, or the rule above would just be
        a way of never returning it."""
        assert classify("Primary: the tactile emboss. Secondary: name.",
                        "hierarchy_family") == "MATERIAL_FIRST"

    def test_a_locative_phrase_names_the_ground_not_the_figure(self):
        """Found by checking the one historical row whose answer cue order alone could
        have faked. Without the locative cut, the span holds both "field" and "bbrose"
        and the family is decided by table order rather than by what leads."""
        assert hierarchy_lead_segment(
            "First read: large-scale BBROSE emboss-foil on the Warm Gold field. "
            "Second read: x") == "large-scale BBROSE emboss-foil"
        assert classify("Primary: the radiance field behind the BBROSE lockup. "
                        "Secondary: x", "hierarchy_family") == "MOTIF_FIRST"

    def test_text_that_is_not_an_ordered_list_reads_as_empty_and_says_so(self):
        """§BH58(e): an empty return is a MEASURED outcome, not a swallowed failure."""
        assert hierarchy_lead_segment("product name leads") == ""
        assert hierarchy_lead_segment("") == ""
        # ...and the old cue vocabulary still classifies it, so nothing regressed
        assert classify("product name leads", "hierarchy_family") == "NAME_FIRST"

    def test_wording_neither_path_knows_is_still_refused(self):
        """The fail-closed property survives: this is not a rubber stamp."""
        assert classify("Primary: the vibe. Secondary: the other vibe.",
                        "hierarchy_family") == UNCLASSIFIED


class TestTheArithmeticIsTrue:
    """§BH58(b): "the signature declares seven dimensions and has six … measure which,
    say so plainly, and make the number true."

    Measured answer, which is NEITHER of the owner's two options: the seventh EXISTS and
    WAS implemented — `HIERARCHY_FAMILIES` is a real four-family table — and was blind.
    Separately, `axis` is a PASSTHROUGH, not a classifier, so seven declared is one
    passthrough plus six classifiers.
    """

    def test_seven_declared_is_one_passthrough_and_six_classifiers(self):
        from apps.pipeline.direction_signature import _TABLES
        dimensions = [d for d, _f in SIGNATURE_DIMENSIONS]
        assert len(dimensions) == 7
        assert PASSTHROUGH_DIMENSIONS == ("axis",)
        for dimension in dimensions:
            in_tables = dimension in _TABLES
            assert in_tables != (dimension in PASSTHROUGH_DIMENSIONS), dimension
        assert len([d for d in dimensions if d not in PASSTHROUGH_DIMENSIONS]) == 6

    def test_the_passthrough_always_counts_which_is_why_it_is_declared(self):
        """`axis` is never UNCLASSIFIED for non-empty prose and is never equal between
        two different axes, so it is a guaranteed +1 to every coverage count and every
        pairwise difference. Measured 0/12 blank and 12 distinct values over tasks 84-87.
        """
        a = direction_signature({"design_axis": "Vector-illustration-led ribbon field"})
        b = direction_signature({"design_axis": "Engraved-field-led contour hatching"})
        assert a["axis"] not in ("", UNCLASSIFIED)
        assert a["axis"] != b["axis"]

    def test_the_owner_nailed_thresholds_have_not_moved(self):
        """§BH58(b): "MIN_MUTUAL_COMPARABLE_PER_PAIR stays at 5 — I am not touching it
        and neither are you." A blind classifier was repaired instead. If a later change
        wants one of these to move, it needs his line, not this test edited."""
        assert MIN_MUTUAL_COMPARABLE_PER_PAIR == 5
        assert MIN_CLASSIFIED_PER_DIRECTION == 5
        assert MIN_PAIRWISE_DIFFERENCES == 3


# ---------------------------------------------------------------------------
# THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
# "The planner refusals on tasks 106 and 109." Task 109 was refused TYPOGRAPHY_NOT_DISTINCT with all three directions
# read SCRIPT_LED — and two of the three were sans systems whose "both scripts" named the Latin and Arabic WRITING
# SYSTEMS. The authority is his order; the method is the one §BH58(b) ruled for the hierarchy classifier — fix the
# reading, move no threshold (the test above).
# ---------------------------------------------------------------------------


class TestTheTypographyReaderSinceTheSecondAnswer:
    @pytest.mark.parametrize("text", [
        "condensed geometric sans, light, both scripts",
        "wide-tracked humanist sans-serif; humanist sans, both scripts, small",
        "a rounded geometric sans set in the two scripts",
        "neither script is set in italic; a rounded geometric sans",
        "Latin and Arabic scripts in one geometric sans",
        "condensed grotesk sans for the product descriptor",
        "humanist sans for the sub-descriptor line",
    ])
    def test_a_writing_system_or_a_word_holding_the_cue_is_not_a_script_face(self, text):
        assert classify(text, "typography_family") != "SCRIPT_LED"

    @pytest.mark.parametrize("text", [
        "a flowing brush script for the product name",
        "calligraphic display Arabic (Thuluth-style)",
        "hand-lettered wordmark with a script-like swash",
        "cursive signature lettering",
    ])
    def test_a_script_face_still_reads_script_led(self, text):
        assert classify(text, "typography_family") == "SCRIPT_LED"

    def test_task_109s_second_attempt_now_validates_on_the_same_bar(self):
        """AgentLog 1865, attempt 2, verbatim: refused TYPOGRAPHY_NOT_DISTINCT at 8294fa6 and nothing else. Read as it
        is written, its three directions are a script face, a condensed sans and a geometric sans."""
        from apps.pipeline.design_direction_generator import _validate
        from apps.pipeline.tests.fixtures_agentlog1844_1865 import TASK_109
        attempt = TASK_109["attempts"][1]
        assert attempt["codes"] == ["TYPOGRAPHY_NOT_DISTINCT"]
        assert [classify(d["typography"], "typography_family") for d in attempt["directions"]] == [
            "SCRIPT_LED", "CONDENSED_EDITORIAL_SANS", "GEOMETRIC_ROUNDED_SANS"]
        doc = {"design_intent": attempt["design_intent"], "directions": attempt["directions"]}
        document, codes, _warnings = _validate(TASK_109["brief"], doc,
                                               record_dimensions_mm=tuple(TASK_109["record_dimensions_mm"]))
        assert codes == [] and document is not None

    def test_the_aimed_repair_names_the_typography_words_and_kinds(self):
        """Task 109's repair said a direction "reads SCRIPT_LED from its typography" and named no word — the motif line
        beside it named its words and seven families. Typography now names both, like every other dimension."""
        from apps.pipeline.direction_signature import TYPOGRAPHY_KINDS, classification_evidence, known_families
        recolorings = [_pastel_recoloring(p) for p in ("blush pink", "sky blue", "peach")]
        codes, _ = validate_semantic_distinctness(recolorings)
        assert "TYPOGRAPHY_NOT_DISTINCT" in codes
        kind = classify(recolorings[0]["typography"], "typography_family")
        words = classification_evidence(recolorings[0]["typography"], "typography_family")
        assert (recolorings[0]["typography"], kind, words) == ("clean modern sans-serif", "SANS_LED", ["sans"])
        assert known_families("typography_family") == TYPOGRAPHY_KINDS and kind in TYPOGRAPHY_KINDS
        text = "\n".join(explain_validation_failure(recolorings, codes))
        line = next(line for line in text.splitlines() if line.startswith("- TYPOGRAPHY_NOT_DISTINCT"))
        assert "from the words ['sans'] in its typography" in line
        aim = text.splitlines()[text.splitlines().index(line) + 1]
        assert aim.startswith("  AIM:") and str([k for k in TYPOGRAPHY_KINDS if k != kind]) in aim
