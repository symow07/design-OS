"""WI-T — the instrument that would have found `max(8.0, zh * 0.14)`, measured.

WHAT §AB ASKED FOR, AND WHY THE FIX IS THE SMALLER HALF
-------------------------------------------------------
§AB4 WI-T, verbatim: *"`compose_container.py:245`, `size = max(8.0, zh *
0.14)`: a POINT size derived from a MILLIMETRE zone height. §Z1(b), live, in
production, on the container front. THE FIX IS NOT THE DELIVERABLE. WI-Q
proved a grep finds 17 of 21 sites and misses precisely this one, so the
deliverable is the INSTRUMENT that would have found it — semantic or
AST-level, knowing a `_mm` quantity from a `_pt` one — PLUS the fix it
catches. Behavioural, not a source read."*

`apps/ire/unit_analysis.py` is that instrument. This file is the evidence that
it works, in the only form §AA accepts: it is run, and what it says is
compared against what is true. Nothing here asserts on the text of a source
file — every assertion is made about `Finding` objects the analyser COMPUTED
or about `size_pt` values a composer EMITTED.

THE MUTATION TABLE — 3 CAUGHT, 1 ESCAPED, AND THE ESCAPE IS THE POINT
----------------------------------------------------------------------
WI-S's discipline: mutate the real module, re-run the watching instrument, and
report per-module rather than as a score. Four mutations, each restoring a
defect this commit removed, applied to the REAL `compose_container.py` source:

    native front, both bindings restored        CAUGHT   (finding at the sink)
    native front, FIRST binding only            ESCAPED  (0 findings)
    direct-print hero, pre-fix verbatim         CAUGHT
    legacy fallback, pre-fix verbatim           CAUGHT

The escape is not a surprise to be explained away — it is the module
docstring's declared flow-insensitivity, arriving in the form it was predicted
to take. `size` is bound twice in that function. Restore the millimetre
derivation at the first binding and the analyser still reads the SECOND, which
this commit made a legitimate `mm / (mm/pt) = pt` conversion, and the last
binding wins. A real regression that reintroduced only the first line would
pass. §AB0(c) asks a negative control to separate a defect from a regression;
this one separates them and then says which side of the line it cannot see.

WHAT THIS COSTS IN MILLIMETRES — THREE PATHS, THREE DIFFERENT ANSWERS
-----------------------------------------------------------------------
§AA's standing rule, next to the work. The honest answer is not "nothing", and
it is different on each of the three paths the fix touched.

**The native front — the live production path — is unchanged at every product
the repo builds.** Both non-test callers pass `native=True`
(`targets/container/__init__.py:1060`, `services/native_handoff.py:217`), and
on that path the old `max(8.0, zh * 0.14)` was pinned to its 8.0 pt floor
until the bottle reached **59.369 x 163.265 mm** (measured by bisection at the
110/40 aspect, `test_the_crossover_is_where_the_old_formula_left_its_floor`).
Below that: byte-identical. Above it the name used to grow with the bottle
(9.8 pt at 70x200, 14.7 at 100x300, 19.6 at 140x400) and now holds at 8.0.
That is §Z1(b) being obeyed, and it is a change — stated as one.

**The direct-print hierarchy changes from 40x110 upward** (the descriptor tier
was 3.85 pt, is now 3.2). That branch has no caller in the repo: it is reached
only via `hierarchy_lines`, and `test_container_line_weight.py`
::`test_wiring_the_branch_up_forces_the_rationale_to_be_revisited` already
asserts repo-wide that the only files touching that keyword are the composer,
its rationale module, and that test.

**The legacy non-native fallback changes at every size** — 3.0 pt at 20x60 and
3.744 at 40x110 both become 3.75. There was no value that preserved it,
because it was scale-dependent everywhere; 3.75 is what the 40x110 reference
bottle produced, rounded. Not production-reachable: `native = native or
bool(zones)`, and both production callers pass both.

WHERE THE THREE INSTRUMENTS DISAGREE, ON REAL NUMBERS
-------------------------------------------------------
Neither this analyser nor WI-Q's perturbation harness contains the other, and
the test class below demonstrates the gap in BOTH directions rather than
claiming the new instrument is simply better.

  * §Z1(c)'s shape at the REAL dropper front zone (42.30 mm, from
    `test_back_panel._FRONT_ZONE`): `max(3.4, zh * 0.034)` is 1.438 pt at
    baseline and 2.157 at WI-Q's x1.5, so the 3.4 floor binds at BOTH and the
    value never moves. WI-Q reports it clean. This analyser reports
    PT_FROM_MM. That is the case §Z1(c) named as invisible to perturbation
    *by construction*, and it is why a third instrument was worth building.
  * The container sheet's chrome — `sheet-title`, `reference-label`,
    `panel-BODY_BACK-label` — is sized off `layout["k"]`, a dimension carried
    through a dict. This analyser returns UNKNOWN for that subscript and says
    nothing; WI-Q catches all three and still holds them in its register. And
    the blind spot is doing this analyser a favour: inline `k` and it fires
    FALSELY, because `k = max(0.35, H / 190.0)` is a ratio whose 190.0 is a
    millimetre constant written as a bare literal. On these three nodes the
    perturbation harness is simply the more accurate instrument. Both halves
    measured in `test_and_seeing_through_the_dict_would_have_made_it_worse`.

THE REGISTER, WITH ITS DENOMINATOR
-----------------------------------
Seven findings across `apps/`, from **817 dimension comparisons**. Three
certain, four resting on the coefficient assumption. Classified below in
`REGISTER` rather than summarised, because the four that are not true findings
are the measure of how much the instrument costs to use:

    visual_quality_program.py:271   TRUE     mm compared against pt
    info_panel.py:374               TRUE     an area/volume added to a mm y
    test_wij_type_size_units.py:124 FIXTURE  WI-J's own defective control
    test_wij_type_size_units.py:153 FIXTURE  the same, unassumed
    info_panel.py:402               FALSE    character counts, not geometry
    vq1_close1_package.py:101       FALSE    PIL pixels named `.height`
    palt_m4b_a_evidence.py:257      FALSE    a matplotlib axis in pixels

The three FALSE ones share one cause: this repo has raster code whose `.width`
and `.height` are PIXELS, and `MM_ATTRIBUTES` declares those names to be
millimetres. That is a declared assumption in the analyser and it is wrong in
`apps/ire/vq1_close1_package.py` and the two evidence renderers. It was left
declared and wrong rather than patched with an owner heuristic, because tuning
an instrument until its own register looks clean is the failure mode this
sprint exists to name.

`compose_container.py` reports **0 findings from 29 comparisons** — clean, and
not clean by having stopped looking.

§AB4(c): the two TRUE findings are RECORDED AND NOT FIXED. They are outside
WI-T, and WI-T is the sprint's only permitted chained fix.
"""
from __future__ import annotations

import pathlib

import pytest

from apps.ire import unit_analysis as ua
from apps.ire.compose_container import compose_container_graph
from apps.ire.tests.test_back_panel import _FRONT_ZONE
from apps.ire.tests.test_wiq_type_scale_independence import (PERTURB,
                                                             sized_nodes,
                                                             sizes_compared,
                                                             sizes_that_move)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (ContainerProfile,
                                                         build_backbone)

APPS = pathlib.Path(__file__).resolve().parents[2]
CONTAINER = APPS / "ire" / "compose_container.py"


def kinds(findings) -> list[str]:
    return [f.kind for f in findings]


# ---------------------------------------------------------------------------
# controls: the analyser is run on snippets whose right answer is known
# ---------------------------------------------------------------------------
class TestItRefusesTheThingsAGrepWouldCondemn:
    """False positives are the whole reason §Y2 distrusts source guards. Every
    snippet here mentions millimetres next to a point size and every one of
    them is correct code."""

    def test_a_size_chosen_as_type_is_not_a_finding(self):
        """§Z1(b) being OBEYED. `9.0` is dimensionless and satisfies any sink,
        which is the definition of choosing a size as type."""
        assert ua.analyse_source(
            'def f(zone_height_mm):\n'
            '    return TextRun(name="n", x=0.0, y=0.0, size_pt=9.0)\n') == []

    def test_wij_s_exonerated_conversion_is_not_a_finding(self):
        """`p.width * 2.835 * 0.075` — WI-J defended this and was right. An
        earlier version of the analyser condemned it, which is recorded in
        `unit_analysis`'s docstring as the false positive that bought the rule
        refusing the coefficient assumption against a conversion."""
        assert ua.analyse_source(
            'def f(p):\n'
            '    return TextRun(name="n", x=0.0, y=0.0,\n'
            '                   size_pt=max(8.0, p.width * 2.835 * 0.075))\n'
        ) == []

    def test_a_declared_rate_makes_a_fit_to_width_legitimate(self):
        """mm / (count * mm/pt) = pt. This is the shape this commit gave the
        native front's re-fit, and an instrument that could not tell it from
        `zw * 0.13` would have forced the fix to delete a working feature."""
        assert ua.analyse_source(
            'def f(zw, longest, _CHAR_ADVANCE_MM_PER_PT):\n'
            '    return TextRun(name="n", x=0.0, y=0.0,\n'
            '        size_pt=(zw * 0.94) / (longest * _CHAR_ADVANCE_MM_PER_PT))\n'
        ) == []

    def test_a_point_size_scaled_by_a_dimensionless_weight_is_not_a_finding(self):
        """The 17 nodes WI-Q registers on clause (B) alone are this shape.
        They are scale-dependent and they are NOT unit errors, and the two
        instruments have to disagree about them for either to mean anything."""
        assert ua.analyse_source(
            'def f(rel):\n'
            '    HERO_NAME_PT = 9.0\n'
            '    return TextRun(name="n", x=0.0, y=0.0,\n'
            '                   size_pt=HERO_NAME_PT * max(1.0, rel))\n') == []

    def test_an_unknown_quantity_produces_nothing(self):
        """UNKNOWN is the default and never accuses. This under-reports on
        purpose — a register that includes guesses is a register nobody acts
        on, and acting on it is the entire point."""
        assert ua.analyse_source(
            'def f(mystery):\n'
            '    return TextRun(name="n", x=0.0, y=0.0, size_pt=mystery)\n'
        ) == []


class TestItCatchesTheFourShapesZ1Names:
    def test_the_defect_section_ab_named(self):
        """`max(8.0, zh * 0.14)` where `zh` is a millimetre height. The literal
        floor does not launder it: `max` lets a literal adopt its neighbour's
        dimension, so the result is millimetres and the point sink says so."""
        found = ua.analyse_source(
            'def f(zone_height_mm):\n'
            '    zh = zone_height_mm\n'
            '    return TextRun(name="n", x=0.0, y=0.0,\n'
            '                   size_pt=max(8.0, zh * 0.14))\n')
        assert kinds(found) == [ua.PT_FROM_MM]

    def test_it_runs_backwards_too(self):
        """§Z1(b) inverted — a millimetre coordinate built from a point size
        with no conversion. This is the shape WI-P fixed in `compose_dropper`,
        and an instrument that only looked at `size_pt` would never see it."""
        found = ua.analyse_source(
            'def f(size_pt, y_mm):\n'
            '    return TextRun(name="n", x=0.0, y=y_mm + size_pt)\n')
        assert ua.MIXED in kinds(found)

    def test_a_millimetre_added_to_a_point_is_a_finding(self):
        found = ua.analyse_source(
            'def f(width_mm, size_pt):\n'
            '    total_mm = width_mm + size_pt\n')
        assert kinds(found) == [ua.MIXED]

    def test_a_millimetre_compared_against_a_point_is_a_finding(self):
        """A unit error that decides a BRANCH, which is worse than one that
        decides a number. `visual_quality_program.py:271` is this shape in
        live code and is in the register below, unfixed."""
        found = ua.analyse_source(
            'def f(gap_mm, size_pt):\n'
            '    if gap_mm > size_pt * 1.45:\n'
            '        return 1\n')
        assert kinds(found) == [ua.MIXED]


class TestItSeesWhatTheGrepCannot:
    """§AB's charge, restated: the deliverable is the instrument that would
    have found the site a `size_pt` grep misses."""

    def test_it_finds_the_fifth_positional_argument_of_centered_text(self):
        """The string `size_pt` does not occur anywhere in this snippet. WI-Q
        measured that this is how 4 of 21 container nodes hide, and that those
        four included the one §AB sent this sprint to fix."""
        source = ('def f(zone_height_mm):\n'
                  '    zh = zone_height_mm\n'
                  '    centered_text("product-name-0", "ROSE", 0.0, 0.0,\n'
                  '                  max(8.0, zh * 0.14), None)\n')
        assert "size_pt" not in source          # the premise, not the assertion
        assert kinds(ua.analyse_source(source)) == [ua.PT_FROM_MM]

    def test_it_reads_dimensions_and_not_spellings(self):
        """§Y2's objection to source guards is that they compare spellings.
        The same arithmetic under a name with no `_mm` in it is still caught,
        because the dimension came from the declared root `.height`."""
        assert kinds(ua.analyse_source(
            'def f(zone):\n'
            '    q = zone.height * 0.14\n'
            '    return TextRun(name="n", x=0.0, y=0.0, size_pt=q)\n')) \
            == [ua.PT_FROM_MM]

    def test_a_docstring_full_of_millimetres_is_not_a_finding(self):
        """The other half of the same claim. A string guard goes red on prose;
        this reads the AST, so prose is invisible to it."""
        assert ua.analyse_source(
            'def f():\n'
            '    """size_pt derived from a millimetre zone height, 0.14 mm."""\n'
            '    return TextRun(name="n", x=0.0, y=0.0, size_pt=9.0)\n') == []


# ---------------------------------------------------------------------------
# the deployment: the real module, mutated
# ---------------------------------------------------------------------------
#: Each entry restores, VERBATIM, a millimetre derivation this commit removed.
#: The replacements are applied to the real `compose_container.py` source in
#: memory — nothing is written to disk and nothing is asserted about the text.
MUTATIONS: dict[str, tuple] = {
    "native front, both bindings": (
        ("size = FRONT_NAME_PT", "size = max(8.0, zh * 0.14)"),
        ("size = max(FRONT_NAME_PT,\n"
         "                       (zw * 0.94) / (longest * _CHAR_ADVANCE_MM_PER_PT))",
         "size = max(8.0, (zw * 0.94) / (longest * 0.185))"),
    ),
    "native front, first binding only": (
        ("size = FRONT_NAME_PT", "size = max(8.0, zh * 0.14)"),
    ),
    # §BD(a) MOVED THE CODE AND THIS MOVES WITH IT, in the same commit, which
    # is exactly what `mutate`'s own refusal message asks for. The composer's
    # two-way conditional became `_hero_tier_pt` when the descriptor got a
    # third size. The RESTORED mm-derivation is unchanged, because what this
    # control proves is that the analyser still catches a millimetre-derived
    # point size — not that the composer spells its sizes any particular way.
    "direct-print hero": (
        ("size_pt = _hero_tier_pt(kind) * max(1.0, rel)",
         "base = zh * 0.125\n"
         '            size_pt = max(9.0, base * rel) if kind == "product_name" '
         "else max(3.2, base * rel)"),
    ),
    "legacy fallback": (
        ("FALLBACK_NAME_PT, ink_for(body_c)",
         "max(3.0, lw * s * 0.13), ink_for(body_c)"),
    ),
}

#: MEASURED, per mutation. `False` is an ESCAPE and is stated as one.
MUTATION_CAUGHT = {
    "native front, both bindings": True,
    "native front, first binding only": False,
    "direct-print hero": True,
    "legacy fallback": True,
}


def mutate(name: str) -> list:
    source = CONTAINER.read_text()
    for old, new in MUTATIONS[name]:
        assert source.count(old) == 1, (
            f"the {name} mutation no longer matches the composer — if the "
            "code moved, move the mutation with it; a mutation that matches "
            "nothing is a control that proves nothing")
        source = source.replace(old, new)
    return ua.UnitAnalyser("mutated.py", source).run()


class TestTheInstrumentIsCatchableAgainstTheRealComposer:
    """Snippets prove the machinery. This proves the deployment — the same
    distinction `TestTheGuardIsCatchableAgainstTheRealComposer` draws in WI-Q,
    and the reason its author found a blind spot rather than asserting one
    was absent."""

    @pytest.mark.parametrize("name", sorted(MUTATIONS))
    def test_each_mutation_lands_as_measured(self, name):
        found = [f for f in mutate(name) if f.kind == ua.PT_FROM_MM]
        assert bool(found) is MUTATION_CAUGHT[name], (
            f"the {name} mutation now behaves differently from the measured "
            f"result recorded in MUTATION_CAUGHT ({MUTATION_CAUGHT[name]}). "
            "If that is an improvement, update the table AND the docstring's "
            "mutation count in the same commit.")

    def test_three_of_four_are_caught_and_the_fourth_is_named(self):
        """Stated as a ratio so it cannot decay into 'the mutations pass'."""
        assert sum(MUTATION_CAUGHT.values()) == 3
        assert len(MUTATION_CAUGHT) == 4
        assert MUTATION_CAUGHT["native front, first binding only"] is False

    def test_the_escape_is_flow_insensitivity_and_here_is_the_mechanism(self):
        """A LIMIT, demonstrated rather than asserted.

        `size` is assigned twice in `_native_decoration`. Restoring the
        millimetre derivation at only the first assignment escapes, because
        the analyser reads assignments in source order and the last one wins —
        and the second assignment is now a legitimate mm/(mm/pt) conversion.
        Restore BOTH and it is caught. So the instrument sees this defect
        only when nothing correct is written after it, which is a real hole
        and not a hypothetical one.
        """
        assert [f for f in mutate("native front, both bindings")
                if f.kind == ua.PT_FROM_MM]
        assert not [f for f in mutate("native front, first binding only")
                    if f.kind == ua.PT_FROM_MM]

    def test_the_repaired_composer_is_clean_and_still_being_looked_at(self):
        """0 findings is only evidence beside the number of comparisons that
        produced it. An analyser that lost its grip on this file would report
        the same zero with a denominator near zero.

        29 -> 30 AT §AY2. The one new check is `compose_container.py:300`, the
        ternary picking `HERO_NAME_PT` or `HERO_SUPPORT_PT`, and NOT the
        millimetre-from-point-size arithmetic the tranche is actually about —
        located rather than inferred, and reconciled against `TREE_CHECKS`
        beside the run of per-tranche records above.

        30 -> 29 AT §BD(a)/(b), AND IT IS THE §AY2 CHECK ABOVE GOING BACK OUT.
        That ternary was written TWICE — the keep-out block and the tier loop
        each held a copy of the size formula — so it was worth two checks, and
        `_hero_tier_pt` unified both into one function whose `return`s the
        analyser does not compare. The full ten-out / nine-in attribution, and
        the measurement showing no respelling of the helper recovers it, are in
        the `TREE_CHECKS` block below; this assertion is the same fall seen at
        the file rather than at the repo.

        29 -> 30 AT §BH65(c)8: `wrap_name` (:323) adds a tracked run's
        letter-spacing to its width estimate, millimetre to millimetre — the
        same check the `TREE_CHECKS` block records, seen at the file.

        30 -> 36 AT §BH66(a): `_concept_face`, the face the concept arranges —
        the type's width inside the ring, a rule's millimetres plus one em of
        the name through `concept_face.MM_PER_PT` (:1066); the Arabic line's
        size bound to its `_pt` name (:1071); and each face run's `x=` and
        `size_pt=` sinks, the name (:1145) and the Arabic line (:1155). Six
        checks, zero findings: the first draft named the conversion `PT_MM`,
        which the analyser cannot read, and it reported the MIXED it saw.

        36 -> 38 AT §BH66(b): the rule moves BELOW the name. Three checks in,
        one out: the tier loop names each line's baseline before it is set
        (:500), the name's ink bottom adds a quarter em through
        `_INK_MM_PER_PT` (:502), and a front with no supporting line puts the
        rule half the name's tier step below its ink (:542); the rule's old
        height above the name, `zy + zh * 0.24`, is gone.

        ZERO FINDINGS IS ASSERTED ON THE LINE ABOVE AND IT IS NOT FREE HERE.
        The extraction cost this file a MIXED at `compose_container.py:498`
        before `size` was renamed `size_pt`, and that red was the reason the
        rename happened. A green here is now evidence about the SUFFIX, which
        is the only thing still declaring the dimension the ternary used to.

        [38 -> 50 AT THE OWNER'S SECOND ANSWER OF 2026-09-25: "The lid is
        missing the concept's rule, ring and radial lines." Twelve checks, zero
        findings, all in `_trim_rays_at_mark`, which shortens a ray at the
        mark's clear space: a point at a share of the ray's millimetre run
        (:1197, :1212 — four each), the ray's length (:1205, two) and its node's
        move (:1217, two). The rule, the ring's corner and their colours add
        none. Located to the line in the `TREE_CHECKS` block.]

        [50 -> 57 AT §BH70(1), the owner's goal of 2026-09-26: the sheet's own
        words kept on its page. Seven checks, zero findings: the fit in
        `chrome_size_pt` (:402, one), the reference label kept on the page
        (:1756, :1757 — three) and its size into `centered_text` (:1760, one),
        and the swatch row's end (:2023, two). Located to the line in the
        `TREE_CHECKS` block.]

        [57 -> 58 AT THE SAME GOAL: a name its front would cut is refused,
        never drawn cut (§BD(b)) — `line_mm > front_mm` in
        `refuse_a_clipped_name` (:411, one). Located to the line in the
        `TREE_CHECKS` block.]

        [58 -> 59 AT §BH71 PART 1, the owner's goal of 2026-09-28: a round
        lid's print kept inside its circle — the name's size taken as the
        named point size in `_outside_the_round_lid` (:1363, one). Located to
        the line in the `TREE_CHECKS` block.]

        [59 -> 60 AT his answer of 2026-09-29 to the §BH71 report, (4): the
        lid draws the record's shade — its runs set at the shade's named
        point size in `_concept_face` (:1932, one). Located to the line in
        the `TREE_CHECKS` block.]

        [60 -> 66 AT his answer after test day finding 3 (2026-09-30): the
        front drawn from its concept's map, each traced part held inside his
        confirmed front — `max`/`min` of a part's millimetres against the
        front's in `_map_front_group` (:2002, six). Located to the line in the
        `TREE_CHECKS` block.]

        [66 -> 72 AT the same answer: the mark drawn from its master where the
        picture prints it — the drawing's millimetres bound and the mark's
        left edge held inside his front in `_map_mark_box` (:1980, :1984,
        :1985 — six). Located to the line in the `TREE_CHECKS` block.]

        [72 -> 83 AT the same answer: the front's type set where its picture
        prints it — each line's size from its traced height and width, its
        ink centred in its traced rows, its baselines and its sinks, in
        `_map_type_group` (:2020-:2061 — eleven). Located to the line in the
        `TREE_CHECKS` block.]

        [83 -> 84 AT his second look at 117 (2026-10-02, "add the Arabic
        lines"): a line of one run centred where the picture centres it, in
        `_map_type_group` (:2158 — one). Located to the line in the
        `TREE_CHECKS` block.]

        [84 -> 86 AT his go of 2026-10-02 (the map path for a wand vial): the
        house mark kept clear of a picture's parts where it prints none, in
        `_mark_clear_of` — the closure's edge against half the product's
        height (:2361) and the front's middle (:2375) — two. Located to the
        line in the `TREE_CHECKS` block.]

        [86 -> 92 AT the same go (the map path for a wand vial): a line set
        where its picture prints it never under the print floor, in
        `_map_type_group` and its figure — the floor named (:1993), the size
        the picture printed (:2166), the floor taken over it (:2167, two) and
        its record (:2168, :2263) — six. Located to the line in the
        `TREE_CHECKS` block.]

        [92 -> 95 AT the owner's finding on design 119, 2026-10-03 (a display
        or turned line drawn as the picture letters it): its size taken
        across its letters, its width where it stands on end and its height
        where it does not, in `_map_type_group` (:2211 — two differences and
        their choice, three). Located to the line in the `TREE_CHECKS`
        block.]

        [95 -> 96 AT the clean-up's wiring check, 2026-10-05, its finding
        W11 (a jar's wrap label read on its front as the front view draws
        it): the label's two ends round the unrolled wrap, its start plus its
        width, in `_front_view_zone` (:302 — one). Located to the line in the
        `TREE_CHECKS` block.]

        [96 -> 98 AT his answer of 2026-10-05, W10 (a jar's back copy on the
        back of its wrap label): the label's two ends round the unrolled
        wrap, its start plus its width, in `_wrap_back_ends` (:324 — one),
        and the next panel's place, a panel's width plus the gap between
        them, in `compose_information_panels` (:388 — one). Located to the
        line in the `TREE_CHECKS` block.]

        [98 -> 100 AT his go of 2026-10-08 (line art in any colour; small
        text set; 122 made drawable): a front line set no wider than the
        zone's safe area, millimetre to millimetre, in `_map_type_group`
        (:2363 — one), and a name set as lettering kept at its largest
        line's size, point to point (:2413 — one). Located to the line in
        the `TREE_CHECKS` block.]

        [100 -> 101 AT his test blocker on design 122 at reconstruction
        (2026-10-08): a concept's line taken for the name where its words
        are the first of the name's, two at least or the whole name, word
        count to word count, in `_name_start` (:2317 — one). Located to the
        line in the `TREE_CHECKS` block.]

        [101 -> 102 AT his second test blocker on design 123 (2026-10-09): a
        name the picture sets over several lines set at one size, each line's
        width held to the safe area's, millimetre to millimetre, in
        `_map_type_group` (:2434 — one). Located to the line in the
        `TREE_CHECKS` block.]

        [102 -> 106 AT his second test blocker on design 123, (4) (122's
        rose, whole and scaled, in a concept's one big bloom): the bloom's
        place on the product, its width and height each to its own side's
        millimetres (:2980 — two), and the rose as large as its place holds,
        its smaller side to the other (:2981 — two). Located to the line in
        the `TREE_CHECKS` block.]

        [106 -> 107 AT his goal of 2026-10-10, item 6 (the front's name in ONE
        ink): the name's lines' read inks counted against its lines
        (:2517 — one); its two type runs' sizes each one binding now, where
        each was one before (:2630, :2663 — two, for the two gone at :2569,
        :2599). Located to the line in the `TREE_CHECKS` block.]

        [107 -> 110 AT his goal of 2026-10-12, item 7 (a line the concept
        prints in small spaced capitals set so): the capitals' size from
        their own height (:2563 — one), and the line's top placed in its box
        (:2660, :2666 — two: the line's own, and the capitals'). Located to
        the line in the `TREE_CHECKS` block.]

        [110 -> 106 AT his goal after the pitch page, 2026-10-15, A (1) and
        A (6) (each line in its concept's face, held inside its frame): the
        front's lines measured in their own faces through ``measure_mm`` and
        ``line_width_mm``, whose returns the instrument does not type — the
        four comparisons that read the Latin estimate gone with it.]

        [106 -> 111 AT his last goal before the pitch, 2026-10-16, Step 2 (each design against its concept): a line no
        frame holds kept inside the product's own outline at its rows (``_outline_room``: the room against its pad,
        the line's width and its edges against the room — three), and the mark never wider than the picture's own
        (``_map_mark_box``: its width against the most — two).]

        [111 -> 126 AT his fixes to 142 (Cherry Kiss), 2026-10-17, (1) (a vertical script name set vertically, whole and
        inside the panel): a line the picture stands on end set on end — its size from its box's width and length, its
        baseline and ink placed across the box, its length centred down it, its ink box against the front (fifteen).]
        """
        analyser = ua.UnitAnalyser(str(CONTAINER), CONTAINER.read_text())
        assert analyser.run() == []
        assert analyser.checks == 126


# ---------------------------------------------------------------------------
# the three instruments, disagreeing on real numbers
# ---------------------------------------------------------------------------
class TestWhereThisInstrumentAndWiQDisagree:
    """§Z1(c) named a shape no perturbation can see. Here it is, at the real
    dropper front zone height, seen by one instrument and not the other."""

    #: the LIVE dropper front zone, from `test_back_panel._FRONT_ZONE`
    ZH = float(_FRONT_ZONE["height"])

    def _z1c(self, scale: float):
        from apps.ire.graph import Color, Document, Group, TextRun
        return Document(page_w=210.0, page_h=297.0, root=Group(
            name="root", role="artwork", children=[
                TextRun(name="front-support", text="ROSE", x=10.0, y=10.0,
                        size_pt=max(3.4, self.ZH * scale * 0.034),
                        color=Color.from_hex("#5A2A3A"))]))

    def test_the_literal_floor_binds_at_both_scales(self):
        """The premise of the disagreement, measured rather than assumed: the
        millimetre term is 1.438 pt at baseline and 2.157 pt at WI-Q's x1.5,
        so 3.4 wins at both and the emitted value cannot move."""
        assert round(self.ZH, 2) == 42.30
        assert round(self.ZH * 0.034, 3) == 1.438
        assert round(self.ZH * PERTURB * 0.034, 3) == 2.157

    def test_wiq_reports_it_clean_and_is_not_reporting_on_nothing(self):
        assert sizes_that_move(self._z1c) == set()
        assert sizes_compared(self._z1c) == 1

    def test_this_analyser_reports_it_as_a_unit_error(self):
        """THE DISCRIMINATING CLAIM. Same expression, opposite verdicts, and
        this one is right: it is a point size derived from a millimetre
        height, however still it holds."""
        assert kinds(ua.analyse_source(
            'def f(zone_height_mm):\n'
            '    zh = zone_height_mm\n'
            '    centered_text("front-support", "X", 0.0, 0.0,\n'
            '                  max(3.4, zh * 0.034), None)\n')) \
            == [ua.PT_FROM_MM]

    def test_and_wiq_sees_three_container_nodes_this_analyser_does_not(self):
        """The disagreement runs BOTH ways, which is why neither instrument
        retires the other. The sheet chrome is sized off `layout["k"]` — a
        dimension carried through a dict, which this analyser reads as UNKNOWN
        and declines to judge. WI-Q catches all three by perturbation."""
        assert ua.analyse_source(
            'def f(layout):\n'
            '    _k = layout["k"]\n'
            '    centered_text("sheet-title", "X", 0.0, 0.0,\n'
            '                  max(7.0, 20 * _k), None)\n') == []
        from apps.ire.tests.test_wiq_type_scale_independence import container
        assert {"sheet-title", "reference-label", "panel-BODY_BACK-label"} \
            <= sizes_that_move(container)

    def test_and_seeing_through_the_dict_would_have_made_it_worse(self):
        """The blind spot above is doing the analyser a FAVOUR, and saying so
        is the difference between reporting a limit and excusing one.

        Inline `k` and the analyser fires — falsely. `k = max(0.35, H / 190.0)`
        divides a millimetre height by the 190 mm reference frame, so it is a
        RATIO; but 190.0 is written as a bare literal, so the analyser reads
        `H / 190.0` as millimetres and condemns the unit-correct chrome.

        The root cause is the one §Z1(a) exists to remove: a dimensioned
        constant written without a name. Every declared root in
        `unit_analysis` is a place the repo told the analyser what a quantity
        is, and a bare 190.0 tells it nothing. Recorded and NOT patched with a
        special case — §AB4(c), and a special case here would be fitting the
        instrument to the file it is measuring.
        """
        found = ua.analyse_source(
            'def f(backbone):\n'
            '    H = backbone.height_mm\n'
            '    k = max(0.35, H / 190.0)\n'
            '    centered_text("sheet-title", "X", 0.0, 0.0,\n'
            '                  max(7.0, 20 * k), None)\n')
        assert kinds(found) == [ua.PT_FROM_MM]
        # and named as a millimetre it is correctly silent, which is the whole
        # of §Z1(a) in two lines
        assert ua.analyse_source(
            'def f(backbone):\n'
            '    HERO_FRAME_MM = 190.0\n'
            '    k = max(0.35, backbone.height_mm / HERO_FRAME_MM)\n'
            '    centered_text("sheet-title", "X", 0.0, 0.0,\n'
            '                  max(7.0, 20 * k), None)\n') == []


# ---------------------------------------------------------------------------
# what the fix did to the artwork, on all three paths
# ---------------------------------------------------------------------------
ZONES = cc.propose_zones(cc.build_inferred_profile("bottle"))
#: every product size the sweep visits, smallest to largest
SIZES = ((20.0, 60.0), (30.0, 90.0), (40.0, 110.0), (50.0, 140.0),
         (70.0, 200.0), (100.0, 300.0), (140.0, 400.0))


def front(width_mm: float, height_mm: float) -> dict:
    backbone = build_backbone(ContainerProfile(
        archetype="bottle", height_mm=height_mm, width_mm=width_mm))
    return sized_nodes(compose_container_graph(
        backbone, product_name="Rose Nectar", name_lines=["Rose Nectar"],
        zones=ZONES, native=True, sku="RN-001"))


class TestTheNameIsNowChosenAsTypeAtEveryProductSize:
    @pytest.mark.parametrize("width_mm,height_mm", SIZES)
    def test_the_product_name_holds_at_eight_points(self, width_mm, height_mm):
        """A 20x speed-run across the sizes the repo builds, from a 20x60
        sample bottle to a 140x400 one. The old formula gave 8.0, 8.0, 8.0,
        8.0, 9.8, 14.7, 19.6 down that list."""
        assert front(width_mm, height_mm)["product-name-0"] == 8.0

    def test_the_crossover_is_where_the_old_formula_left_its_floor(self):
        """MEASURED, by evaluating the OLD expression on the REAL geometry
        rather than by remembering a number. `max(8.0, zh * 0.14)` sits on its
        floor until the label zone reaches 8.0 / 0.14 = 57.143 mm on the
        sheet; at the 110/40 aspect that is a 59.369 x 163.265 mm bottle.

        This is what "the live path is unchanged" means, exactly: below this
        the fix is byte-identical and above it the name stops growing with the
        bottle, which is the rule being obeyed.
        """
        from apps.ire.compose_container import _fit, _sheet_layout

        def old_size(width_mm: float) -> float:
            height_mm = width_mm * 110.0 / 40.0
            backbone = build_backbone(ContainerProfile(
                archetype="bottle", height_mm=height_mm, width_mm=width_mm))
            layout = _sheet_layout(backbone)
            s = _fit(backbone.width_mm, backbone.height_mm,
                     layout["con_box"])[0]
            return max(8.0, backbone.label_zone[3] * s * 0.14)

        lo, hi = 50.0, 70.0
        for _ in range(40):
            mid = (lo + hi) / 2.0
            lo, hi = (lo, mid) if old_size(mid) > 8.0 else (mid, hi)
        assert round(hi, 3) == 59.369
        assert round(hi * 110.0 / 40.0, 3) == 163.265
        # and on both sides of it the NEW value is the same number
        assert front(hi - 5.0, (hi - 5.0) * 110.0 / 40.0)["product-name-0"] \
            == front(hi + 5.0, (hi + 5.0) * 110.0 / 40.0)["product-name-0"] \
            == 8.0

    def test_the_name_still_wraps_rather_than_shrinking(self):
        """The feature the fix had to keep. VQR-1 requires a long name to WRAP
        into up to three balanced lines instead of dropping below the 8 pt
        legibility floor, and a fix that simply deleted the millimetre term
        would have taken the wrap with it."""
        backbone = build_backbone(ContainerProfile(
            archetype="bottle", height_mm=110.0, width_mm=40.0))
        long_name = "Rose Damascena Restorative Facial Elixir"
        sizes = sized_nodes(compose_container_graph(
            backbone, product_name=long_name, name_lines=[long_name],
            zones=ZONES, native=True, sku="RN-001"))
        lines = [n for n in sizes if n.startswith("product-name-")]
        assert len(lines) > 1
        assert {sizes[n] for n in lines} == {8.0}


class TestTheOtherTwoPathsChangedAndHereIsByHowMuch:
    """§AA's standing rule taken literally: the paths where the answer is NOT
    "nothing" get their numbers stated, not omitted."""

    #: §BB7(a) — THE DESCRIPTOR TIER BELOW IS THE OWNER'S RULED STRING.
    #:
    #: This slot held a FABRICATED §AE2(c) descriptor from before §AV2 until
    #: 2026-08-27, carrying a ⟪PROVISIONAL⟫ marker because tools/brand_strings.py
    #: refused it unmarked on its first run against apps/. The instruction left
    #: here then was "Do not strip it to make the fixture read nicely; supply C9
    #: from the owner instead." C9 was supplied — the owner typed it at §BB7(a)
    #: — so the substitute is retired the way it was told to be retired, and the
    #: fixture reads nicely as a side effect rather than as the reason.
    #:
    #: THE RETIRED STRING IS NOT NAMED HERE, ON PURPOSE. Its whole history —
    #: what it was, that it was found rather than planted, the byte count that
    #: falsified itself, and the marker that was kept on it — lives in
    #: test_av2_brand_strings.py, which is the record of the finding. Naming it
    #: in a second file would keep this file inside
    #: test_the_string_is_mentioned_only_where_the_finding_is_recorded, whose
    #: subject is a placeholder becoming established by attrition. A dead
    #: placeholder spreading through its own obituaries is that same failure.
    #:
    #: "FACIAL SERUM" is registered in brand_strings.RULED_STRINGS against
    #: ruling C9, and THIS FILE IS ONE OF ITS PINNED SITES. Moving it to another
    #: file without adding that file to the register is RULED_STRING_OFF_SITE;
    #: changing its case or spacing is RULED_STRING_ALTERED. Both refuse on the
    #: commit path, not only in the suite.
    #:
    #: The other two tiers are ruled out BY NAME in brand_strings.NOT_OURS:
    #: "ROSE NECTAR" is the established product record value (97 sites), and
    #: "30 ml" is §AE2(b) NET CONTENT and belongs to tools/reserved_copy.py —
    #: which, measured, cannot presently see it in this shape.
    HIERARCHY = [{"text": "ROSE NECTAR", "kind": "product_name", "rel": 1.0},
                 {"text": "FACIAL SERUM", "kind": "descriptor",
                  "rel": 0.8},
                 {"text": "30 ml", "kind": "net_content", "rel": 0.6}]

    def _hero(self, width_mm: float, height_mm: float) -> dict:
        backbone = build_backbone(ContainerProfile(
            archetype="bottle", height_mm=height_mm, width_mm=width_mm))
        return sized_nodes(compose_container_graph(
            backbone, product_name="Rose Nectar", zones=ZONES, native=True,
            sku="RN-001", hierarchy_lines=self.HIERARCHY))

    @pytest.mark.parametrize("width_mm,height_mm", SIZES)
    def test_the_direct_print_hierarchy_is_flat(self, width_mm, height_mm):
        """9.0 for the name, 5.0 for the descriptor and 3.2 for every other
        support tier, at every size. The old formula gave the descriptor
        3.2 / 3.2 / 3.85 / 4.9 / 7.0 / 10.5 / 14.0 down this list, so this path
        DID change from 40x110 upward.

        §AB2 rules 9.0 pt stands, and 9.0 is what this tier already was at
        every size below 140x400 — the fix pins it rather than choosing it.

        THE DESCRIPTOR READ 3.2 UNTIL §BD(a), WHICH IS THE WHOLE OF THIS TEST'S
        CHANGE. The owner ruled it its OWN constant at the screen/pad-print
        floor rather than lifting `HERO_SUPPORT_PT`, so `net_content` below is
        the control that proves the other tiers did NOT move: had the constant
        been raised instead, both lines would read 5.0 and this file could not
        tell the two outcomes apart.

        FLATNESS IS STILL WHAT IS BEING ASSERTED. Three sizes are not a
        gradient — each is a literal that holds at every zone, which is the
        §Z1(b) property this test exists for. What would break it is a size
        that MOVES with `width_mm`/`height_mm`, and the parametrisation is
        what would catch that.

        §BD(b) PUT SOMETHING THAT *DOES* MOVE WITH THE ZONE NEXT TO SOMETHING
        THAT MUST NOT, WHICH IS WHY THE NAME TIER IS NOW READ AS A SET. The
        name wraps, so at 20x60 it arrives as `product-name-hero-0/-1` and
        everywhere else as the bare `product-name-hero`. The LINE COUNT is a
        function of the zone width and is ruled to be; the SIZE is not, and
        reading every `product-name-hero*` node at once asserts both at once —
        that they all carry 9.0, and that nothing about wrapping reached the
        point size. Only 20x60 wraps, and that is measured, not assumed: at
        30x90 the zone allows 20.304 mm and `ROSE NECTAR` estimates 18.315,
        while at 20x60 it allows 13.536. Pinning the count per zone is what
        stops a future change from wrapping every size and calling it flat.
        """
        sizes = self._hero(width_mm, height_mm)
        hero = {n: s for n, s in sizes.items()
                if n.startswith("product-name-hero")}
        assert set(hero.values()) == {9.0}
        assert len(hero) == (2 if width_mm == 20.0 else 1)
        assert sizes["front-descriptor"] == 5.0
        assert sizes["front-net_content"] == 3.2

    def test_the_legacy_fallback_is_flat_and_it_used_to_be_three_values(self):
        """3.0 at 20x60, 3.744 at 40x110 and 13.104 at 140x400 all become
        3.75 — the 40x110 reference bottle's own value, rounded. No constant
        preserved this path, because it was scale-dependent everywhere; the
        choice is recorded rather than presented as a no-op."""
        seen = set()
        for width_mm, height_mm in SIZES:
            backbone = build_backbone(ContainerProfile(
                archetype="bottle", height_mm=height_mm, width_mm=width_mm))
            # `native = native or bool(zones)`: the legacy branch needs both
            sizes = sized_nodes(compose_container_graph(
                backbone, product_name="Rose Nectar", native=False))
            seen.add(sizes["container-name"])
        assert seen == {3.75}


# ---------------------------------------------------------------------------
# the register, classified, with its denominator
# ---------------------------------------------------------------------------
TRUE_FINDING = "TRUE"
DELIBERATE_FIXTURE = "FIXTURE"
FALSE_POSITIVE_PIXELS = "FALSE_PIXELS"
#: [the owner's message of 2026-10-29, "Re-pin the four checks per PLAN.md" — CURRENT_DECISIONS.md, "Owner: quality, not
#: count"] the cost of THE COEFFICIENT ASSUMPTION that `unit_analysis`'s docstring declares in advance: "an unrecognised
#: conversion ... that NAMED_CONSTANTS do not list ... would be read as a coefficient and its result given the wrong
#: dimension". Read, classified, not patched (the instrument is not tuned to clear its own register).
FALSE_POSITIVE_COEFFICIENT = "FALSE_COEFFICIENT"

#: (file, line, kind) -> classification. Every finding the analyser produces
#: over `apps/`, judged one at a time. §AB4(c): the TRUE ones are RECORDED
#: AND NOT FIXED — they are outside WI-T.
REGISTER = {
    ("visual_quality_program.py", 271, ua.MIXED): TRUE_FINDING,
    ("info_panel.py", 374, ua.MIXED): TRUE_FINDING,
    ("test_wij_type_size_units.py", 124, ua.PT_FROM_MM): DELIBERATE_FIXTURE,
    ("test_wij_type_size_units.py", 153, ua.PT_FROM_MM): DELIBERATE_FIXTURE,
    ("info_panel.py", 402, ua.MIXED): FALSE_POSITIVE_PIXELS,
    # [his review of 119, 2026-10-05, points 6 and 3] info_panel.py's two lines are svg_info_panel's own, unchanged —
    # moved 14 down (330 → 344, 358 → 372) by title_ar, written above them, 2 more (→ 346, 374) by draw_info_panel's
    # ground, said in its docstring, and 25 more (→ 371, 399) by its laid-out path for a carton (point 2)
    ("vq1_close1_package.py", 101, ua.MIXED): FALSE_POSITIVE_PIXELS,
    ("palt_m4b_a_evidence.py", 257, ua.MIXED): FALSE_POSITIVE_PIXELS,
    # [Day 6 of the rescue, 2026-10-19] the per-surface fidelity instrument compares a PyMuPDF drawing rect's area with
    # half the page area to skip a page-sized field fill: `.width`/`.height` on a fitz Rect are POINTS, both members
    # alike, the coefficient dimensionless — the same declared cause as the three above (names declared mm, holding
    # another unit). Read, classified, not patched.
    # [the owner's message of 2026-10-29, the four checks re-pinned] day6_surface_fidelity.py left apps/ with the Day 4–6
    # masters (git mv to archive/, 462bd2b); its finding left with it — not a repair, its file is no longer measured.
    # [the same message] the one finding never classified, read: the face builder's band lettering (it came from
    # round_files_ornament.py:94 with its code, dd45c7b) sizes a run as `min(height_mm * PT * INK_SHARE / (top - bottom),
    # length_mm * PT / (advance_em + gaps_em))` — millimetres times round_files_export.PT (72 / 25.4, points per
    # millimetre) over em counts (fractions of the size), i.e. points — and compares it with MIN_SIZE_PT, points. The
    # units agree. `PT` is not in NAMED_CONSTANTS, so the coefficient assumption reads it as dimensionless and `size` as
    # millimetres: an ASSUMED finding, never certain.
    # [the owner's goal of 2026-10-29, §3] the same line, unchanged, moved 1069 → 1637 by the 300 ppi panels, the
    # product nets, the flat hand-off, the painting's proof as a gate and the dead ends moved out (d4981e0 … f76ffaf)
    # [the owner's ruling of 2026-10-29, English only] the same line again, 1637 → 1651, by the bottle's English rows
    # and the type revision
    # [the owner's goal of 2026-10-29, the shape check] 1651 → 1673, by the refit of a face to its new outline
    # [the same goal, §2: the face built in layers] 1673 → 1705, by the layer fitting written above it
    # [the owner's goal of 2026-10-29, $2 per design] 1705 → 1745, by painted_plain and board_fits written above it;
    # [the owner's round-4 faults, 2026-10-29] 1745 → 2021, by hard_rules, settle_net, the fold-turn words, read_between, the walls' pattern, the measured holds, the truths, the products' own material, the note said last and the flat words above it
    # [the owner's part 1, 2026-10-30] 2021 → 2060, the same line again: the layering's section went from below it, the
    # stand's raster became its own function and the writer's piece-placing went from above it
    ("round_files_faces.py", 2060, ua.MIXED): FALSE_POSITIVE_COEFFICIENT,
}

#: MEASURED over `apps/`. The denominator is the point: seven out of eight
#: hundred is an instrument that looked; seven out of nine is one that barely
#: did, and the two are indistinguishable from the numerator alone.
#:
#: 817 -> 819 at WI-U, and the ATTRIBUTION was measured rather than assumed
#: because the obvious guess was wrong. WI-U moved the front support baselines
#: off `zh * 0.545` and onto `block_top + leading + em_mm * <ratio>`, so the
#: first draft of this comment credited the two extra comparisons to the
#: producer. Running the analyser on `compose_dropper.py` at the pre-WI-U
#: commit and at the fix returns **7 comparisons both times**: a fraction of a
#: millimetre zone and a point size converted to millimetres are the same
#: amount of dimensional surface, and swapping one for the other is a wash.
#:
#: The +2 is `apps/ire/tests/test_wiu_front_collision.py`, WI-U's own new test
#: file, which does millimetre arithmetic of its own. It is NOT excluded the
#: way the line below excludes 1: that exclusion exists because an instrument
#: must not be part of its own measurement, and WI-U's tests measure a front
#: panel, not this analyser. They are ordinary corpus and they count as such.
#:
#: The NUMERATOR did not move — still seven findings, the same seven keys — so
#: WI-U added measurable surface without adding a defect. That distinction is
#: the whole reason the denominator is written down beside the numerator, and
#: this test failing on WI-U's commit is the instrument working, not drifting:
#: a corpus census that never moves is one nobody is re-running.
#:
#: 819 -> 821 at WI-V, attribution measured again rather than inferred from the
#: shape of the commit. `apps/ire/tests/test_wiv_leading_comparison.py` reads
#: **2 comparisons**, and `compose_dropper.py` reads **7 both before and
#: after** — WI-V's change to that file is a COMMENT, and a comment is not in
#: the AST. The two numbers agreeing across the repair is the cleanest
#: demonstration this file has of why WI-T is an AST instrument and the WI-V
#: comment probe is a `tokenize` one: neither can see the other's subject, and
#: a grep would have reported a diff for both.
#:
#: The numerator did not move at WI-V either — seven findings, the same seven
#: keys. It did have to be EARNED: the first draft wrote `EM_MM = RULED_PT *
#: 25.4 / 72.0` and the analyser reported an eighth finding, MM_FROM_PT,
#: correctly — a bare ratio carries no units, so it could see a pt going into
#: an mm sink and not the conversion in between. That was repaired at the
#: source by using `back_panel.MM_PER_PT` rather than admitted to the register
#: as a fourth false positive. Classifying it would have cost the instrument
#: some of its edge permanently; naming the constant cost one line.
#:
#: 821 -> 823 at WI-W, attribution measured per file rather than inferred from
#: the diff: `back_panel_ledger.py` reads **1** and `test_wiw_line_ledger.py`
#: reads **1**. Both were located to the line, because a denominator bumped
#: without knowing WHAT was added has stopped being a measurement:
#:   * `back_panel_ledger.py:134` — `size_pt=float(size_pt)` reaching a `size_pt=`
#:     sink. A type size travelling as type, which is §Z1(b) obeyed.
#:   * `test_wiw_line_ledger.py:230` — `record["capacity"][floor]
#:     ["height_available_mm"] == truth`, mm against mm.
#:
#: The second one has a history worth keeping. It did not exist when WI-W's
#: tests first ran green; it was added because a mutation control found that
#: `test_the_budget_is_echoed_exactly_and_never_scaled` — the test NAMED for
#: §AB1(f)'s no-assumed-layer-count prohibition — stayed green while the budget
#: was silently doubled underneath it. It asserted the number the ledger PRINTS,
#: not the number it MEASURES AGAINST. Tying the two together is the line above,
#: so this instrument's denominator moved by one because another instrument
#: caught the executor asserting a conclusion and calling it a premise.
#:
#: The numerator did not move: seven findings, the same seven keys, zero from
#: either new file. WI-W added measurable surface without adding a defect, as
#: WI-U and WI-V did.
#:
#: 823 -> 825 at WI-Y (§AC1), and this one is DECLARED AGAINST A STANDING
#: INVARIANT rather than merely recorded. Sprint 14's invariant list says
#: `TREE_CHECKS` stays 823. It moved by two, and both are located to the line:
#:   * `test_wiu_front_collision.py` 2 -> 3, at `AC1_LEADING_SHIFT_MM` — the
#:     constant that carries §AC1's 3.190 mm into WI-U's pinned baselines.
#:   * `test_wiy_leading_metric_floor.py` 0 -> 1, at `EM_MM = RULED_PT *
#:     back_panel.MM_PER_PT`, in a file that did not exist at HEAD.
#: Both are legal comparisons: findings from both files are 0.
#:
#: `compose_dropper.py` reads **7**, before and after, exactly as at WI-U,
#: WI-V and WI-W — the production change §AC1 authorised added ZERO
#: dimensional surface, which is the sharpest available statement that a
#: leading ruling is a constant swap. Measured HEAD-versus-tree per file, not
#: inferred from the diff: two files moved, no other file moved by so much as
#: one check.
#:
#: Note that `tools/` is outside `APPS` and is not censused, so the WI-Y
#: instrument itself contributes nothing here. That is not a loophole being
#: used — the tool is not production code and never was in the denominator —
#: but it is stated because a denominator that silently excludes the place the
#: work went would be worse than a moving one.
#:
#: THE ALTERNATIVE WAS AVAILABLE AND IS WORSE. Writing 3.190 as a literal
#: keeps the denominator at 823 and deletes the derivation, so the next
#: leading change silently falsifies WI-U's pins instead of moving them. The
#: invariant's own preamble is *"none moves without an explicit sentence
#: naming whose movement it is"*; this is that sentence. If the owner meant
#: the stricter reading — that the census may not move at all this sprint —
#: the revert is this constant back to a literal and one line here, and the
#: close report says so rather than leaving the choice buried in a number.
#:
#: RECORDED AT WI-Y, NOT FIXED — `UnitAnalyser.run()` IS NOT IDEMPOTENT, AND
#: THIS NUMBER IS ITS OUTPUT. Calling `run()` twice on one instance returns 2
#: findings where there is 1 and leaves `checks` at 4 where it is 2; a third
#: call gives 3 and 6. It re-walks and APPENDS rather than resetting, so BOTH
#: the numerator and the denominator of this register scale with how many
#: times somebody asked. Measured on `tools/wiv_leading_comparison.py`:
#: (1, 2) -> (2, 4) -> (3, 6).
#:
#: It is latent, not live: `census()` constructs one analyser per file and
#: calls `run()` exactly once, and the `tree` fixture below calls `mine.run()`
#: once. So 825 and 7 are correct as measured TODAY. What is not safe is the
#: assumption that they stay correct under a caller who retries, logs, or
#: asserts on `run()` twice — the second call would inflate both numbers and
#: `test_the_denominator_is_stated_beside_the_numerator` would fail pointing
#: at the tree instead of at the instrument, which is the worst kind of red.
#:
#: NOT REPAIRED HERE ON PURPOSE. §AC forbids chained fixes and names exactly
#: one exception, which is not this. The repair is small — reset the
#: accumulators at the top of `run()`, or memoise it — and it belongs to
#: whoever owns `unit_analysis.py` next, with its own before/after.
#:
#: **REPAIRED AT WI-3E**, which §AE1 hands to the executor by name, by the
#: first of the two routes above. The before/after this paragraph asked for:
#: (1,1) -> (2,2) -> (3,3) on a one-finding subject before, (1,1) -> (1,1) ->
#: (1,1) after. `TREE_CHECKS` did NOT move across the repair and could not
#: have — the census calls `run()` once per analyser, which is the same
#: sentence that made the defect latent in the first place. `TestRunIsIdempotent`
#: at the foot of this file is the red that was watched failing first.
#:
#: **825 -> 827 AT WI-Z**, and the sentence naming whose movement it is: the
#: §AC2(b) ``(N, B)`` wiring. Attributed per file by the same HEAD-vs-tree
#: measurement WI-Y used, run with `run()` called ONCE per analyser because of
#: the defect recorded directly above:
#:
#:     +1   1 -> 2   apps/ire/back_panel_ledger.py
#:     +1   0 -> 1   apps/ire/tests/test_wiz_surface_plan.py
#:     net +2, and no other file in `apps/` moved by one check.
#:
#: The ledger's is `surface_budget`, which takes `width_mm`, `height_mm` and
#: `size_pt` and hands them to `capacity` — a millimetre pair and a point size
#: crossing one call, which is exactly the shape §Z1 exists to watch, so it
#: SHOULD be in the denominator. The test file's is its `ZONE_W, ZONE_H` pair.
#:
#: THE NUMERATOR DID NOT MOVE. Findings are still 7 and `REGISTER` still
#: matches key-for-key, which is the number that would mean something went
#: wrong. A denominator that rises while the numerator holds is new code being
#: looked at and found clean; the reverse, or both moving together, is what
#: would need explaining. §Z1(b) — no `size_pt` derived from a millimetre
#: quantity — holds in `surface_budget`: `size_pt` arrives from the caller and
#: is passed through untouched, and B comes back as a LINE COUNT, which is
#: dimensionless and cannot re-enter the mm side.
#:
#: **827 -> 839 AT WI-2A**, the largest single move this sprint, and the
#: sentence naming whose movement it is: §AC3's splitting packer, which is two
#: entirely new files rather than an edit to existing ones. Measured the same
#: way, `run()` once per analyser:
#:
#:     +5   0 -> 5   apps/ire/back_panel_packer.py
#:     +7   0 -> 7   apps/ire/tests/test_wi2a_split_packer.py
#:     net +12, and the arithmetic RECONCILES: 827 + 5 + 7 = 839 exactly, so
#:     no other file in `apps/` moved by so much as one check. That is a
#:     stronger statement than the per-file scan alone and it is the reason
#:     both numbers are quoted.
#:
#: The packer's five are its `width_mm`/`height_mm`/`size_pt` triples crossing
#: into `capacity_for_pieces` and `bp.layout` — the same shape as the ledger's
#: `surface_budget` and in the denominator for the same reason. The test
#: file's seven are its `ZONE_W, ZONE_H` pair and the synthetic-document
#: helpers that carry a size into `bp.layout`.
#:
#: THE NUMERATOR DID NOT MOVE, for the third work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key. §Z1(b) holds across the
#: whole packer by construction rather than by inspection: the module's
#: outputs are LINE COUNTS and CUT POSITIONS, both dimensionless integers, and
#: the one millimetre quantity it handles — the panel geometry — is passed
#: through to `back_panel_ledger.capacity` untouched. No `size_pt` anywhere in
#: it is derived from a millimetre quantity because no `size_pt` in it is
#: derived at all; it arrives from the caller and is forwarded.
#: **839 -> 840 AT WI-3C**, and the sentence naming whose movement it is: the
#: §AH ruling's deciding measurement, written into `test_wiz_zone_contract.py`
#: as an assertion instead of left in the ruling as prose. Measured the same
#: way, `run()` once per analyser, HEAD against tree:
#:
#:     +1   0 -> 1  apps/ire/tests/test_wiz_zone_contract.py
#:     net +1, and the arithmetic RECONCILES: the raw per-file totals are 840
#:     at HEAD and 841 in the tree, which become 839 and 840 after this file
#:     subtracts its own single check in the `tree` fixture below. No other
#:     file in `apps/` moved by so much as one.
#:
#: Located to the line, because a denominator bumped without knowing WHAT was
#: added has stopped being a measurement:
#:   * `test_wiz_zone_contract.py` — `geom["BODY_WRAP"]["w"] >
#:     geom["BODY_FRONT"]["w"] * 3`, two millimetre quantities compared across
#:     a dimensionless multiplier. Legal, and it SHOULD be in the denominator:
#:     it is the one assertion carrying §AH1's finding that a jar's wrap is the
#:     developed cylinder (125.66 mm) and its front is not (40.00 mm), which is
#:     the entire basis on which `z_wrap` was confirmed as a fourth zone.
#:
#: THE NUMERATOR DID NOT MOVE, for the fourth work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key.
#:
#: A NEAR-MISS BELONGS BESIDE THIS NUMBER. The first draft of that assertion
#: compared 40π against the ZONE width rather than the SURFACE width — 106.8,
#: which is 0.85 × 125.66 because `propose_zones` centres the wrap at 85 %
#: coverage. It survived only because the zone dict spells the key `width` and
#: the draft asked for `width_mm`, so it raised `KeyError` instead of failing
#: by 19 mm against a tolerance that was already sitting in the line, waiting
#: to be widened. This instrument would not have caught it: mm against mm is
#: mm against mm whether or not the two are the same mm. That is a real limit
#: of the analyser and it is recorded here rather than in a commit message,
#: because the next person to trust this denominator should know what kind of
#: wrongness it is blind to.
#:
#: **840 -> 842 AT WI-3F**, and the sentence naming whose movement it is: the
#: repair to a §Y2 count that had rotted in a docstring, which replaced the
#: rotted sentence with assertions. Measured the same way, HEAD against tree:
#:
#:     +2   0 -> 2  apps/pipeline/tests/test_wig_source_string_guards.py
#:     net +2, and the arithmetic RECONCILES: raw per-file totals 841 at HEAD
#:     and 843 in the tree, which become 840 and 842 after this file subtracts
#:     its own single check in the `tree` fixture below. No other file in
#:     `apps/` moved by so much as one.
#:
#: Located to the line, and both checks are on ONE line:
#:   * `test_wig_source_string_guards.py:710` — `len(full) - len(visible) ==
#:     len(full - visible)`. The subtraction is one check and the comparison is
#:     the other. All four quantities are COUNTS, so the statement is
#:     dimensionless end to end and produces no finding.
#:
#: This is the first entry in this block whose mover is OUTSIDE `apps/ire`, and
#: that is worth a sentence: the census fixture takes the whole of `apps/`, so
#: `apps/pipeline` has always been in the denominator and simply had not moved.
#: A reader who assumed this number tracked the ire package would have been
#: wrong for four work items without being contradicted.
#:
#: **842 -> 843 AT WI-3I**, and the mover is again outside `apps/ire`.
#: Measured the same way, HEAD (`e955a36`) against tree, every file in
#: `apps/` compared:
#:
#:     +1   0 -> 1  apps/pipeline/tests/test_rbv3_review_package.py
#:     net +1, and no other file in `apps/` moved by one.
#:
#: Located to the line by bisection — `test_rbv3_review_package.py:516`:
#:
#:     assert dims["front_width_mm"] != dims["side_depth_mm"]
#:
#: One comparison, one check, no finding. Both operands are millimetres, so
#: the statement is dimensionally consistent and the analyser passes it.
#:
#: WORTH THE SENTENCE, because it is the blind spot named at the top of this
#: block arriving in person. `front_width_mm` and `side_depth_mm` are
#: DIFFERENT QUANTITIES that happen to share a unit, and the analyser
#: compares mm against mm "whether or not the two are the same mm". This
#: particular line exists because RBV-3 shipped `side_depth_mm or
#: front_width_mm` — a fallback that printed the FRONT width in the DEPTH
#: field on the owner's dashboard, invisible in real evidence because the
#: committed P1 subject has W == D == 37.4 mm. So the analyser counted, as
#: a well-formed check, the assertion written to catch a conflation the
#: analyser itself cannot see. The denominator grew by one; the instrument's
#: reach did not.
#:
#: THE NUMERATOR DID NOT MOVE, for the sixth work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key.
#:
#: **843 -> 844 AT §AV3**, and the sentence naming whose movement it is: the
#: RUNTIME half of the §AE2(c) brand-string guard. Measured the same way,
#: HEAD (`6cf65f8`) against tree, every `.py` file in `apps/` compared with
#: `run()` called once per analyser:
#:
#:     +1   0 -> 1  apps/ire/tests/test_av3_brand_string_runtime.py
#:     net +1, and no other file in `apps/` moved by so much as one check.
#:
#: Located to the line by bisection —
#: `test_av3_brand_string_runtime.py:37`, the `_text` helper:
#:
#:     TextRun(name=name, text=text, x=0.0, y=0.0, size_pt=size_pt, ...)
#:
#: A millimetre pair and a point size crossing one call, which is the same
#: shape as `surface_budget` at WI-Z and the packer's five at WI-2A, and it is
#: in the denominator for the same reason. §Z1(b) holds trivially: `size_pt`
#: arrives as a default argument and is forwarded, derived from nothing.
#:
#: THE SENTENCE THAT IS ACTUALLY WORTH THE SPACE HERE is about the file that
#: did NOT move the number. `apps/ire/brand_string_runtime.py` is 156 lines of
#: new production code and it contributes **ZERO** checks, because it handles
#: no dimensional quantity of any kind — it walks a document and asks whether a
#: string contains a token. That is what this denominator is for: it says, in a
#: number, that the §AV3 guard added no dimensional surface to the repository,
#: which is a much more specific claim than "the tests pass". A guard for
#: brand copy that HAD moved this number would be doing something it was not
#: asked to do.
#:
#: THE NUMERATOR DID NOT MOVE, for the seventh work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key.
#:
#: **844 -> 851 AT §AU3**, the §AE2(c) brand-usage validator, and the largest
#: move since WI-2A. Measured HEAD (`ad3db82`) against tree, every `.py` file in
#: `apps/` compared, `run()` called once per analyser:
#:
#:     +6   0 -> 6  apps/ire/container_brand_usage.py
#:     +1   4 -> 5  apps/ire/tests/test_container_line_weight.py
#:     net +7, and the arithmetic RECONCILES: raw per-file totals 845 at HEAD
#:     and 852 in the tree, which become 844 and 851 after this file subtracts
#:     its own single check. No other file in `apps/` moved by so much as one.
#:
#: THE ATTRIBUTION WAS MEASURED AND THE OBVIOUS GUESS WAS WRONG, which is the
#: second time this block has had to say so (WI-U was the first). The tranche
#: added one production module and two test files, so the natural reading is
#: that all seven belong to the new module. Six do. The seventh is in a file
#: the tranche merely EDITED, and no diff-shaped inference would have found it.
#:
#: Located to the line, because a denominator bumped without knowing WHAT was
#: added has stopped being a measurement:
#:   * `container_brand_usage.py:254` — `lx1, ly1 = logo.x + logo.w, logo.y +
#:     logo.h`. TWO checks on one line: each addition is a millimetre length
#:     meeting a millimetre offset. This is the logo's far corner, and it is
#:     the pair of additions the clear-space geometry is built on.
#:   * `container_brand_usage.py:272, :274, :276, :278` — one check each, the
#:     four sides of the keep-out band: `box[3] > margin[1] and box[3] <= ly0 +
#:     _EPS_MM` and its three rotations. Every operand is mm, so all four are
#:     dimensionally consistent and produce no finding.
#:   * `test_container_line_weight.py:141` — `ELEMENTS["container_front_rule"]
#:     ["width_mm"] != round(divider_mm, 6)`, added at §AU2 to assert the thing
#:     §W4 actually ruled: that the Gate-A divider and the container front rule
#:     are two objects. The ratio pinned three lines above it is a consequence;
#:     this is the ruling. mm against mm, no finding.
#:
#: THE SENTENCE WORTH THE SPACE is again about what did NOT move it.
#: `test_au3_brand_usage.py` (19 tests) and `test_au3_divider_gates.py` (24
#: tests) contribute **ZERO** checks between them, and the reason is a property
#: of the instrument that should be stated rather than mistaken for a clean
#: bill of health: those files compare measured millimetres against LITERALS,
#: and `_agree` gives a literal whatever dimension it sits beside, so one
#: definite operand leaves `len(real) - 1 == 0`. The tests are not being
#: pronounced dimensionally sound here; they are largely INVISIBLE to this
#: analyser. A reader taking a zero as a verdict would be reading it backwards.
#:
#: THE NUMERATOR DID NOT MOVE, for the eighth work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key — and that is the load-
#: bearing statement about `container_brand_usage.py`, a module whose entire
#: job is millimetre arithmetic against a cap height. Six new dimensional
#: comparisons, zero of them mixed. §Z1(b) holds by construction: nothing in
#: the module derives a `size_pt` at all — it reads cap ratios out of a PNG and
#: multiplies them by type sizes that arrive from the document.
#:
#: **851 -> 854 AT §AY2**, the keep-out that drops the front stack below the
#: mark's clear space. Measured HEAD (`c470b88`) against tree, every `.py` file
#: in `apps/` compared, `run()` called once per analyser:
#:
#:     +1   29 -> 30  apps/ire/compose_container.py
#:     +2    0 ->  2  apps/ire/tests/test_au3_brand_usage.py
#:     net +3, and the arithmetic RECONCILES: raw per-file totals 852 at HEAD
#:     and 855 in the tree, which become 851 and 854 after this file subtracts
#:     its own single check. No other file in `apps/` moved by so much as one.
#:
#: THE ATTRIBUTION WAS MEASURED AND THE OBVIOUS GUESS WAS WRONG AGAIN — the
#: third time (WI-U, then §AU3), which has stopped being a coincidence and is
#: now the reason this block refuses to accept a diff-shaped inference. The
#: tranche's whole point is a shift computed in millimetres from a point size,
#: so the natural reading is that the shift arithmetic is what got counted. It
#: is not. Both new checks were located by instrumenting the two increment
#: sites and recording a line number with each:
#:   * `compose_container.py:300` — the CONDITIONAL, not the arithmetic:
#:     `size0 = (HERO_NAME_PT if t0.get("kind") == "product_name" else
#:     HERO_SUPPORT_PT) * ...`. `_agree` runs over the two branches of a
#:     ternary exactly as it runs over the two sides of a `+`, because a
#:     conditional is a place where two dimensions meet and only one survives.
#:     Both branches are pt, they agree, no finding.
#:   * `test_au3_brand_usage.py:338` — TWO checks on one line, the same shape
#:     as `container_brand_usage.py:254` at §AU3: `keepout_y = ly + lh +
#:     p["logo_cap_height_mm"]`. What makes the operands definite is worth
#:     naming, because nothing on that line is suffixed: `_lx, ly, _lw, lh =
#:     p["placed_mm"]` unpacks a SUBSCRIPT, so the positional correspondence
#:     is unavailable and all four names inherit the whole value's dimension —
#:     and the whole value is mm because the string KEY ends in `_mm`. §Z1(a)
#:     reaching inside a dict literal's subscript is the only reason this line
#:     is visible at all.
#:
#: THE SENTENCE WORTH THE SPACE is what those two located checks imply about
#: the ones that are missing. The expression this tranche exists for —
#:
#:     tops = [text_ink_top(y_cursor + size0 * _BASELINE_DROP_MM_PER_PT, size0)]
#:     shift = max(0.0, keepout_y - min(tops))
#:
#: contributes **ZERO** checks, and not because it is clean. `size0 *
#: _BASELINE_DROP_MM_PER_PT` is pt x (mm/pt), which `_combine_mul` resolves to
#: mm without a comparison ever happening; the `+` that follows meets
#: `y_cursor`, which is UNKNOWN, and one unknown operand ends the agreement
#: before it starts. `y_cursor`, `rule_y`, `shift` and `keepout_y` are all
#: unsuffixed locals, so §Z1(a) declares nothing about them and the instrument
#: has nothing to compare. This is the WI-Q lesson arriving from the other
#: direction: the denominator can be made to look reassuring not by an
#: analyser that stopped looking, but by code that never gave it anything to
#: look at. The mm-vs-pt arithmetic in the new keep-out was checked by
#: composing four container fronts and measuring the emitted geometry, which
#: is a different instrument entirely, and it caught a real error this
#: analyser could not have seen (a 0.4643 shift applied where the rule needed
#: 1.8074).
#:
#: How much is being missed was MEASURED rather than guessed at, because "the
#: instrument cannot see this" is itself a quantity (§AY0(d)). The same block
#: transcribed with every local suffixed — `y_cursor_mm`, `rule_y_mm`,
#: `shift_mm`, `keepout_y_mm` and the two zone operands they are built from —
#: reports **6 checks and 0 findings**. So the visible fraction of this
#: tranche's dimensional arithmetic is 1 in 7, the hidden six are sound, and
#: the fix is a rename across a live composer's local names, which is §AE2(c)
#: work and not a test-file edit to be smuggled in beside a denominator.
#:
#: THE NUMERATOR DID NOT MOVE, for the ninth work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key.
#:
#: **854 -> 856 AT §BB7(e), AND THE NUMBER IS NOT THIS COMMIT'S ALONE.**
#:
#: This block was first written to record 854 -> 853, a FALL of one. That fall
#: is real, it is this commit's, and everything below about it stands unedited.
#: What the first writing did not know is that a SECOND uncommitted changeset —
#: another session's A1 closeout — was sitting in the same working tree when
#: the gate measured. **The census walks the WORKING TREE, not the index**, so
#: it counts both, and the gate refused with `assert 856 == 853`.
#:
#: Measured HEAD against tree, every modified `.py` in `apps/` compared,
#: `run()` once per analyser, the two changesets attributed SEPARATELY because
#: attributing them jointly would be the whole defect this block exists to
#: prevent:
#:
#:     THIS COMMIT (C16(b)):
#:     +0    7 ->  7  apps/ire/compose_dropper.py
#:     +0    2 ->  2  apps/ire/container_line_weight.py
#:     -1    5 ->  4  apps/ire/tests/test_container_line_weight.py
#:     +0    1 ->  1  apps/ire/tests/test_wit_unit_analysis.py
#:                                                          subtotal  -1
#:
#:     NOT THIS COMMIT (A1 closeout, lands next, its own message):
#:     +0    0 ->  0  apps/pipeline/services/p1_pilot_evidence.py
#:     +0   40 -> 40  apps/pipeline/services/p1_pilot_geometry.py
#:     +0    2 ->  2  apps/pipeline/services/p1_v3_evidence.py
#:     +3    0 ->  3  apps/pipeline/tests/test_p1_pilot_geometry.py
#:                                                          subtotal  +3
#:
#:     RECONCILES: 855 at HEAD, -1 +3 = 857 raw on the tree — the raw census
#:     re-measured in-process and read back as 857 — which becomes 856 after
#:     this file subtracts its own single check. Those eight are the only
#:     files in `apps/` the tree modifies at all, so no other file CAN have
#:     moved.
#:
#: THE INCONSISTENCY THIS PIN CARRIES, STATED RATHER THAN LEFT TO BE FOUND. A
#: checkout of THIS commit alone counts 854 raw and 853 here, not 856. The pin
#: says 856 because 856 is what the gate measured and what the tree holds once
#: the A1 closeout lands in the very next commit. The window is one commit
#: long. It is not a defect that can be engineered away: a census is a property
#: of a TREE, and when two independent changesets share one tree neither can
#: pin a self-consistent global count — only the last to land can. Per-source
#: attribution above is the substitute for a guarantee that cannot exist, and
#: writing the number without it is what would make this dishonest.
#:
#: WHOSE MOVEMENT IT IS: C16(b). The owner ruled the dropper front rule to
#: 0.30 mm, which is what the container front rule was already ruled to at
#: §AU2. `test_the_rule_production_draws_is_a_different_element` had proved the
#: two elements distinct with `dropper.width_mm != container.width_mm`, and
#: that is the check that is gone — isolated to that one assertion, not
#: inferred from the diff: the tree file with only that hunk reverted counts 5.
#:
#: THE CHECK DID NOT STOP BEING PERFORMED, IT STOPPED BEING TRUE, and those are
#: different losses. A ruling made the two operands equal, so an inequality
#: over them is not coverage that lapsed but an assertion that had become
#: false. The re-proof the owner ordered in its place is `emitted` — True for
#: the rule production draws, False for the one on the unreached branch — and a
#: bool is dimensionless, so this instrument cannot see it and should not be
#: expected to. That is the WI-Q lesson from a third direction: the denominator
#: can fall without the analyser going quiet, when the code stops offering it a
#: dimensional comparison because the dimension stopped being the distinction.
#:
#: THE ATTRIBUTION WAS MEASURED AND THE FIRST MEASUREMENT WAS WRONG — mine this
#: time, not a guess about the code. The first attribution run reported +4 for
#: a single-line hunk, because it re-inserted the assertion with
#: `str.replace()` and no count, and its anchor occurs four times in the file.
#: The reconciliation is what caught it: 4 + 4 = 8 does not meet HEAD's 5.
#: Quoting both totals is the reason this block can tell a real move from a
#: broken instrument, and that is the second time the pair has earned its space.
#:
#: AND THE SECOND MEASUREMENT WAS WRONG TOO, in the re-measure that produced
#: 856. The attribution script read `.checks` off a freshly constructed
#: `UnitAnalyser` without calling `run()`, and every file in both changesets
#: came back 0 — including files known to hold checks. A clean +0 for eight
#: files is a measurement-shaped zero standing where "not yet measured"
#: belongs: the A137 shape, third instance recorded against this block's own
#: tooling rather than against the code under test. What caught it was
#: implausibility, not a guard. The ordering contract is visible six lines
#: below in `tree()` — `mine.run()` is asserted BEFORE `mine.checks` is read —
#: and the script had the fixture in front of it and still got it wrong.
#:
#: THE NUMERATOR DID NOT MOVE, for the tenth work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key — and it did not move
#: across the A1 closeout either, which added 3 checks and 0 findings.
#:
#: **856 -> 861 AT §BC(h), AND THIS ONE IS SELF-CONSISTENT.**
#:
#: The disclosure above — that a checkout of the C16(b) commit alone reads 853
#: while the pin says 856, because two changesets shared one tree — **is now
#: closed and stays readable.** The A1 closeout landed at `7958466`, the window
#: it described was one commit wide, and from that commit onward the pin and a
#: fresh checkout agree. Nothing about that block is edited; a disclosure that
#: gets deleted once it stops applying teaches the next reader nothing.
#:
#: This move has one author and one source file. Measured HEAD against tree,
#: `run()` before `.checks` in every case:
#:
#:     +5    0 ->  5  apps/ire/tests/test_c10_mark_width.py   (new file)
#:     +0    7 ->  7  apps/ire/compose_dropper.py
#:                                                          subtotal  +5
#:
#:     RECONCILES: 856 pinned, 862 raw on the tree, 861 here after this file
#:     subtracts its own single check. Those two are the only files in `apps/`
#:     the changeset touches, so no other file CAN have moved. `compose_dropper`
#:     was checked rather than assumed: the ruling replaced an inline `0.40`
#:     with a module constant and added a long comment, and neither the rename
#:     nor the prose changed what the analyser sees — a comment carries no
#:     dimensional flow, and `zw * MARK_ZONE_SHARE` is the same shape of
#:     expression as `zw * 0.40`.
#:
#:     RE-MEASURED, BECAUSE THE FIRST FIGURE WAS WRITTEN BEFORE THE FILE WAS
#:     FINISHED. This block first said +3 -> 859, measured accurately against a
#:     six-test draft. An audit then found the draft's docstring overclaiming
#:     which node it read, and the repair added the scale-invariance and
#:     body-diameter classes — which are dimensional, so the count moved again.
#:     The number is re-measured rather than adjusted: the earlier figure is
#:     recorded here as superseded rather than quietly overwritten, because a
#:     denominator edited to match a memory is the failure this whole block
#:     guards against.
#:
#: WHOSE MOVEMENT IT IS: C10, the mark-width floor. All five new checks are
#: millimetre readings in `test_c10_mark_width.py`: the ruled render, the two
#: negative controls that drive the emitted width BELOW the floor at the
#: retired 0.40 and the 0.545 near-miss, the physical-width recovery across the
#: sheet's own 1.22x and 1.5455x scales, and the body-diameter edge at which
#: the derived zone stops clearing the floor. **They are checks precisely
#: because the assertions are dimensional**: §BC(h) required the floor proved
#: on the emitted node's width in millimetres rather than on the share, and a
#: millimetre comparison is exactly what this instrument counts. The contrast
#: with C16(b) three paragraphs up is worth keeping in view — that ruling COST
#: a check by turning a dimensional inequality into a boolean, and this one
#: BUYS five by turning a ruling into a dimensional measurement. Same
#: instrument, opposite signs, and neither is a statement about quality.
#:
#: THE NUMERATOR DID NOT MOVE, for the eleventh work item running. Findings are
#: still 7, `REGISTER` still matches key-for-key, and the new file reports zero
#: findings of its own.
#:
#: **861 -> 862 AT §BB7(c), AND IT IS ONE CHECK IN ONE ASSERTION.**
#:
#: Measured across all seven files the changeset touches under `apps/`, `run()`
#: before `.checks` in every case:
#:
#:     +1    4 ->  5  apps/ire/tests/test_container_line_weight.py
#:     +0   30 -> 30  apps/ire/compose_container.py
#:     +0    2 ->  2  apps/ire/container_line_weight.py
#:     +0    - ->  0  apps/ire/front_hierarchy.py            (new file)
#:     +0    0 ->  0  apps/ire/tests/test_av2_brand_strings.py
#:     +0    0 ->  0  apps/pipeline/services/native_handoff.py
#:     +0    1 ->  1  apps/pipeline/targets/container/__init__.py
#:                                                          subtotal  +1
#:
#:     RECONCILES: 863 raw on the tree, 862 here after this file subtracts its
#:     own single check. Those seven are the only files in `apps/` the changeset
#:     touches, so no other file CAN have moved.
#:
#:     A NEW FILE THAT ADDS ZERO CHECKS IS THE ONE FIGURE WORTH DEFENDING here,
#:     because a clean zero on an unmeasured file is the A137 shape this block
#:     has recorded against its own tooling twice. It is real:
#:     `front_hierarchy.py` holds a string, a ratio (`DESCRIPTOR_REL = 0.8`) and
#:     a list build. There is no millimetre and no point in it — the tiers it
#:     returns are RELATIVE, and the composer multiplies them into type sizes
#:     at `compose_container.py:358`, which is where the dimension enters and
#:     where that file's 30 checks already sit.
#:
#: WHOSE MOVEMENT IT IS, and it is the mirror of C16(b) three blocks up. The
#: single check is `test_container_line_weight.py:275`:
#:
#:     assert container["width_mm"] == dropper["width_mm"]
#:
#: C16(b) COST a check by turning a dimensional inequality into a boolean. This
#: ruling BUYS one by the reverse move, for the reverse reason: §BB7(c) wired
#: the container front, so `emitted` — a boolean — stopped telling the two
#: rules apart, and what the test now pins is that their two independently-held
#: millimetre values agree. A boolean distinction became a dimensional one.
#: Same instrument, opposite signs, and neither is a statement about quality.
#:
#: THE NUMERATOR DID NOT MOVE, for the twelfth work item running. Findings are
#: still 7 and `REGISTER` still matches key-for-key — across a changeset that
#: wired two production call sites, which is the largest behavioural change any
#: of the twelve has carried.
#:
#: **862 -> 863 AT §BD(a)/(b), AND THE TOTAL ROSE WHILE PRODUCTION FELL.**
#: THREE THINGS MOVED UNDERNEATH IT, in two directions, on two kinds of file.
#: Thirteen tranches in, this is the first time a production file LOST a check.
#: A falling denominator is precisely how this instrument goes quiet — the
#: census exists to catch exactly that — so a total that moved the *reassuring*
#: way is not an explanation either, and is expressly not accepted as one here.
#:
#: **THIS BLOCK FIRST DECLARED 862 AND WAS WRONG BY ONE.** Recorded rather than
#: silently corrected, because how it was caught is the part worth keeping. The
#: table was assembled from the files the tranche was REMEMBERED to touch,
#: reconciled against itself, and read as sound — and it omitted
#: `test_wif_reconstruct_container.py` entirely, which this same tranche had
#: edited an hour earlier. Nothing internal to the write-up could have caught
#: that: a table that is missing a row still adds up. What caught it was
#: RUNNING `test_the_denominator_is_stated_beside_the_numerator`, which said
#: `assert 863 == 862`. The rule this argues for is already this block's own
#: and was not followed: the file list is taken from `git status`, never from
#: a memory of what was edited.
#:
#: Measured across every file the tranche touches under `apps/`, `run()` before
#: `.checks` in every case, the file list taken from `git status`:
#:
#:     -1   30 -> 29  apps/ire/compose_container.py            PRODUCTION
#:     +0    2 ->  2  apps/ire/container_production_method.py  PRODUCTION
#:     +0    0 ->  0  apps/ire/front_hierarchy.py    (comment-only edit)
#:     +1    0 ->  1  apps/ire/tests/test_av2_brand_strings.py TEST
#:     +1    1 ->  2  apps/pipeline/tests/
#:                      test_wif_reconstruct_container.py      TEST
#:                                                       subtotal  +1
#:
#:     RECONCILES: 864 raw on the tree, 863 here after this file subtracts its
#:     own single check. Those are the only files in `apps/` this tranche
#:     touches beyond the §BB7(c) rows directly above, so no other file CAN
#:     have moved; `test_container_line_weight.py` still reads 5 and still
#:     holds the +1 §BB7(c) bought there.
#:
#: **A PRODUCTION FILE READING ZERO IS ALSO A MEASUREMENT, AND THIS ONE
#: CORRECTS AN EXPECTATION.** `container_production_method.py` reads 2 on both
#: sides of the `_in_artwork` repair — the repair was expected to show up here
#: and does not. That is the honest answer rather than a disappointing one: it
#: added a fourth string prefix to a deny-list, and a string prefix carries no
#: dimension. The instrument the repair actually restores is
#: `CONTAINER_MINIMUM_TEXT_SIZE_FAILED`, which measures POINTS on the emitted
#: document — but it measures them at RUNTIME, on nodes, not in any source
#: comparison this analyser can read. The two instruments do not overlap, and
#: judging that repair by this dial would have been reading the wrong one.
#:
#: **THE -1 IS THE FINDING; THE TWO +1s ARE SEPARATE AND CANCEL NOTHING.**
#: A check on a test file does not stand in for a check on production code —
#: they measure different things, and only one of them is what ships. Writing
#: down a total that rose and moving on would have made the number look healthy
#: while the production surface quietly shrank, which is verbatim the failure
#: the `tree` fixture's own docstring warns about ("hiding the overlap by
#: writing 818 down would have made the number look stable while quietly
#: measuring something else"). All three are therefore accounted for
#: SEPARATELY below.
#:
#: THE FIRST +1, located to the line by the same logging method as the -1:
#: `test_av2_brand_strings.py:310`, `assert len(uses) == len(uses[0][5].sites)`
#: — an `exact` against an `exact`, two COUNT dimensions agreeing. It arrived
#: because that test's docstring claimed the site count was "asserted against
#: the REGISTER rather than against a literal" while the code underneath said
#: `== 2`. Repairing the code to match its own prose replaced the literal with
#: a comparison of two real quantities, and a comparison of two real quantities
#: is what this census counts. The set-equality line beside it counts for
#: NOTHING — a set comparison reads `unknown` — which is the cleanest available
#: demonstration that this denominator tracks dimensional surface and not
#: assertions, and that a rising census cannot be manufactured by adding tests.
#:
#: THE SECOND +1, located the same way and a sharper version of the same
#: demonstration: `test_wif_reconstruct_container.py:430`,
#:
#:     assert all(r["size_pt"] < r["floor_pt"] for r in below)
#:
#: a PT against a PT — two independently-carried point quantities meeting, the
#: emitted size and the profile's floor. FOUR assertions replaced TWO in that
#: test and EXACTLY ONE OF THE FOUR IS DIMENSIONAL. The node-name list reads
#: `unknown` on both sides. `[r["size_pt"] ...] == [9.0, 9.0, 5.0]` and
#: `[r["floor_pt"] ...] == [12.0, 12.0, 12.0]` each put a real PT beside a LIST
#: literal, which reads unknown, and one unknown operand makes the whole
#: comparison unknown (`_agree`, "one unknown operand and the whole expression
#: is unknown"). The assertion they REPLACED bought nothing either:
#: `below[0]["size_pt"] < 12.0` is a PT beside a bare literal, and a literal
#: adopts whatever it sits beside, so `len(real) - 1` is zero. Three added
#: assertions bought no check, one strengthened comparison bought one, and
#: nothing was lost — the census told them apart without being asked to.
#:
#: WHOSE MOVEMENT IT IS, located by logging every comparison the analyser makes
#: on HEAD's source and on the tree and DIFFING THE TWO LOGS — not by reading
#: the changeset and inferring. Ten comparisons at HEAD are absent from the
#: tree and nine in the tree are absent from HEAD, which nets to the -1 but is
#: not what happened:
#:
#:     8 of each are the SAME check on a line that MOVED — `centered_text`'s
#:       three sinks, its two `+/-` operands, `y_cursor +=`, `gap`'s step
#:       conditional, and `if est > zw * 0.94` reappearing as
#:       `if est <= max_w_mm` inside `wrap_name`.
#:    +1  y_cursor += line_step if j + 1 < len(lines) else gap   NEW at §BD(b)
#:    -2  size0 = (HERO_NAME_PT if ... else HERO_SUPPORT_PT)     GONE
#:        size  = (HERO_NAME_PT if ... else HERO_SUPPORT_PT)
#:
#: THE TWO LOSSES ARE ONE LOSS COUNTED TWICE, and that is the whole finding.
#: The size formula had TWO copies — one in the keep-out block, one in the tier
#: loop — so the analyser was counting a DUPLICATION as surface. §BD(a) made a
#: third size, `_hero_tier_pt` unified the copies, and an analyser that
#: compares the arms of a ternary does not compare the `return` statements of a
#: function. What was lost compared `HERO_NAME_PT` against `HERO_SUPPORT_PT`:
#: a PT constant against a PT constant, the weakest comparison in the census,
#: and it was worth two only because it was written twice.
#:
#: NOT RECOVERABLE BY RESPELLING THE HELPER, and that was MEASURED rather than
#: asserted: `if/if/return`, one ternary over the two support sizes, and a
#: nested ternary over all three each read **29**. The dimension does not
#: re-enter until the call site. So 29 is the honest number and this is the
#: third spelling to produce it, not the first one that was tried.
#:
#: THE `_pt` SUFFIXES IN THAT LOOP ARE LOAD-BEARING, NOT TIDYING. `size` ->
#: `size_pt` and `size0` -> `size0_pt` had to happen with the extraction: the
#: analyser reads a `_PT`-suffixed CONSTANT as a declaration, because §Z1(a)'s
#: suffix law fires when a name is BOUND, and a `def` binds no dimension. So
#: `_hero_tier_pt(kind)` returned unknown, `gap` stopped being a millimetre and
#: `gap / zh` read as a reciprocal length. That produced a real MIXED at
#: `compose_container.py:498` which is NOT in `REGISTER` because it was
#: repaired at the PRODUCER, per the WI-V precedent above: naming the value
#: cost one word, and classifying it would have cost the instrument its edge
#: permanently.
#:
#: THE NUMERATOR DID NOT MOVE, for the thirteenth work item running — 7
#: findings, `REGISTER` matching key-for-key, across a tranche that changed a
#: ruled type size, put a second line on the front, and widened a production
#: deny-list.
#: §BH39(d) (2026-09-08): 863 → 864, located to the line — `apps/ire/materials_placement.py::credit_node`, a
#: dimensioned parameter `size_pt` flowing into `TextRun(size_pt=…)`: the credit node the placement seam draws has a
#: point size, and the census counts the unit-carrying interface it is. Not a finding; the register stays 7.
#: §BH45(f) (2026-09-11): 864 → 863, located to the line — `apps/pipeline/services/supplier_dispatch.py::dispatch`,
#: the comparison `len(sent) == len(rows)` that computed `dispatch_complete`. The owner ruled that count a literal
#: (sent counts are 0 by construction; they move only from an owner-typed sent date on the tracking sheet,
#: transcribed by ruling), so the comparison left the tree. Measured HEAD-versus-tree per file: supplier_dispatch.py
#: 1 -> 0, no other file moved. Not a finding; the register stays 7.
#: §BH48(b)(ii) (2026-09-12): 863 → 865, located to the line — two millimetre sums the M3 drawing source adds:
#: `apps/ire/compose_dropper.py::_bottle_group_m3`, `max(top_pts) - min(top_pts)` (two abscissae of the glass
#: outline's top — the NECK_GLASS half-width the fidelity reader measures), and
#: `apps/pipeline/targets/container/__init__.py::reconstruct_container`, `closure_h = collar_height_mm +
#: bulb_height_mm` rebuilt for the label zone when the profile is derived from the fit — the same sum the
#: PARAMETRIC branch already carries at its own line. Measured HEAD-versus-tree per file: compose_dropper.py
#: 7 -> 8, targets/container/__init__.py 1 -> 2, no other file moved. Not a finding; the register stays 7.
#: (§BH50(f)(8) line 7, 2026-09-17: rule 3 now reads the visible waist; the half-width above still sizes the drawn
#: NECK_GLASS, whose top edge alone closure_assembly_connection reads — no fidelity rule reads the width, and closure_h
#: sizes the label zone only. §AZ0(u).)
#: §BH50(b) (2026-09-13): 865 → 870, located to the line — the composer's record of whether the confirmed front
#: zone holds the small copy at the 5.0 pt floor, `apps/ire/compose_dropper.py::front_copy_fit`: the binding
#: `zone_width_mm = float(zone["width"])` and the three millimetre checks against it, `zone_width_mm - width_mm`,
#: `width_mm <= zone_width_mm` and `width_mm > zone_width_mm`; and `apps/ire/tests/test_wiu_front_collision.py
#: ::mutant_gap`, the binding `was_pt = mod.SUPPORT_PT`, which restores the size the historical readings were
#: taken at. Measured HEAD-versus-tree per file: compose_dropper.py 8 -> 12, test_wiu_front_collision.py 3 -> 4,
#: no other file moved. Not a finding; the register stays 7.
#: §BH50(f)(1) (2026-09-16): 870 → 873, located to the line — the product-copy minimum the floor's scope gives the
#: typography record, `apps/ire/container_typography_metrics.py::measure_typography_metrics`, `smallest =
#: min(judged_sizes) if judged_sizes else smallest_view` (the minimum over the point sizes of the runs the floor
#: judges — the copy printed on the product — where the page-wide minimum stood); the fixture binding
#: `apps/ire/tests/test_container_text_floor.py::_declared`, `run = _run(name=name, size_pt=size_pt, text=text)`,
#: which builds a run with its print scope declared; and `apps/pipeline/tests/test_container_confirmation_2c2e.py`
#: `::test_the_w2_floor_reads_the_copy_printed_on_the_product_and_nothing_else`, the comparison
#: `assert typo["min_annotation_pt"] == min(a["size_pt"] for a in annotations)` (the sheet's smallest annotation,
#: published beside the product's minimum under its own name). Measured HEAD-versus-tree per file:
#: container_typography_metrics.py 1 -> 2, test_container_text_floor.py 1 -> 2, test_container_confirmation_2c2e.py
#: 0 -> 1, no other file moved. Not a finding; the register stays 7.
#: §BH50(f)(3) (2026-09-16): 873 → 875, located to the line — two millimetre facts the total front-copy fit records
#: beside the zone, in `apps/ire/compose_dropper.py::front_copy_fit`: the spare to the zone's confirmed safe area,
#: `row["spare_to_safe_area_mm"] = round(safe_area_mm - width_mm, 4)`, and its state, `row["safe_area_state"] =
#: "INSIDE" if width_mm <= safe_area_mm else "OVER"` (both recorded verdict-free, MEASURED NOT RULED); the zone
#: comparison itself moved from `if width_mm > zone_width_mm:` to `over = round(row["width_mm"] - zone_width_mm, 4)`,
#: one check for one. Measured HEAD-versus-tree per file: compose_dropper.py 12 -> 14, no other file moved. Not a
#: finding; the register stays 7.
#: §BH50(g)(1), re-typed §BH53(a) (2026-09-18): 875 → 877, located to the line — the safe area GOVERNS the front, so
#: `apps/ire/compose_dropper.py::front_copy_fit` now decides each run against it, `row["state"] = "HELD" if width_mm
#: <= safe_area_mm else "EXCEEDS_SAFE_AREA"` (:936), and names the overrun in millimetres, `over =
#: round(row["width_mm"] - row["safe_area_mm"], 4)` (:946); the zone's comparison and its overrun moved intact (the
#: zone is the recorded OUTER BOUND, `outer_bound_state`), one check for one. Measured HEAD-versus-tree per file by
#: removing each new statement in turn: compose_dropper.py 14 -> 16 (15 without either new line, 14 without both), no
#: other file moved. Not a finding; the register stays 7.
#: §BH54(b) (k) 4 (2026-09-19): 877 → 878, located to the line — the room a piece of back copy has, measured for
#: the owner as he types: `apps/dashboard/copy_room.py::rooms`, `others = required - copy_lines * pitch` (what every
#: other line and gap of the panel needs, in millimetres: the panel's required height less this piece's copy lines
#: at the line pitch — both read from the back panel's own record, `height_required_mm` and `line_height_mm`).
#: Measured per file by removing each new statement in turn: copy_room.py (a new file) 0 -> 1, 0 without that
#: line; the eight changed files read HEAD == tree. Not a finding; the register stays 7.
#: §BH54(b) (n) (2026-09-19): 878 → 880, located to the line — the back panel's margin is READ from its zone's record:
#: `apps/ire/back_panel.py::zone_margin`, `room = min(float(zone["width"]), float(zone["height"]))` (the smaller of
#: the zone's two millimetre sides, which a usable margin must leave a column inside); and its test,
#: `apps/ire/tests/test_back_panel.py::TestTheBackCarriesItsZonesOwnSafeMargin`, the binding `margin_mm=
#: zone["safe_margin_mm"]` in the `bp.layout(…)` call the composed record is compared with. `layout`'s own two lines
#: moved one check for one (`- 2 * MARGIN_MM` → `- 2 * margin_mm`). Measured per file, by removing each new statement
#: in turn: back_panel.py 9 -> 10, test_back_panel.py 6 -> 7, test_container_confirmation_2c2e.py 1 -> 1; each back
#: to its HEAD count without its one statement. Not a finding; the register stays 7.
#: §BH54(b) (o) (2026-09-19): 880 → 881, located to the line — the hero-leading check compares like with like:
#: `apps/ire/container_concept_fidelity.py::measure_concept_fidelity`, `leading_em = gap_mm / (size_pt * MM_PER_PT)`.
#: The gap's own subtraction moved one check for one (`gap = …` → `gap_mm = …`). WHY THE DEFECT WAS NEVER A FINDING
#: HERE, measured on this instrument: as it stood — `gap <= size * 1.45` — the names carried no unit and it saw
#: nothing; the SAME line with its units named, `gap_mm <= size_pt * 1.45`, is a finding, MIXED, "comparison over mm
#: and pt"; the fix is two checks and no finding. fidelity.py 1 -> 2; test_wiv_leading_comparison.py 2 -> 2; no
#: other file moved. Not a finding; the register stays 7.
#: §BH55 Phase 1 p1-capacity (2026-09-19): 881 → 883, located to the line — a bottle's size proposal holds its scale
#: inside the editor's own ranges: `apps/pipeline/targets/container/__init__.py::_bottle_size_for`, `lo =
#: max(rng["width_mm"][0] / ref["width_mm"], rng["height_mm"][0] / ref["height_mm"])` and `hi =
#: min(rng["width_mm"][1] / ref["width_mm"], rng["height_mm"][1] / ref["height_mm"])` — the scale's floor and
#: ceiling, each the larger (smaller) of two ratios of millimetres, the editor's range over the confirmed reference.
#: Measured per file by removing each new statement in turn: container/__init__.py 2 -> 4 (3 without either line, 2
#: without both); test_gate1_concept_selection.py 0 -> 0; no other file moved. Not a finding; the register stays 7.
#: §BH55 Phase 2 p2-marketing (2026-09-19): 883 → 908, located to the line — one NEW file, the artwork targets'
#: composer, and their tests in the declared file that owns target creation. `apps/ire/compose_artwork.py` (new) 0 ->
#: 22: the headline's fit, `size_pt = min(max_pt, _REF_PT
#: * (avail_mm / widest_mm))` (the min and its binding) and `if size_pt >= min_pt` (:195-196, 3); the format's scale,
#: `short = min(tw, th)`, `max_pt, min_pt = short * …` (two bindings), `copy_pt = max(COPY_FLOOR_PT, …)` (the max and
#: its binding) and `pitch_mm = copy_pt * MM_PER_PT * …` (:270-276, 6); the portrait test `th >= tw` (:287, 1); the
#: info page's picture top, `b + th * (1.0 - INFO_VISUAL_SHARE)` (:296, 1); and the presentation sheet's own
#: geometry — a label's x, its y and the sum under it, the running x, the page's width and height, the title's x and
#: y (:418-425, 11). `apps/pipeline/tests/test_create_design_target.py` 0 -> 3: a run's width against its box (:173)
#: and the headline's floor, `min(fmt.width_mm, fmt.height_mm)` and its comparison (:261). No other file moved. THE FIRST
#: VERSION WAS A FINDING, and the analyser was right: `size = min(max_pt, avail_mm / widest)` read as a min over pt
#: and ~mm — the width had been measured at 1 pt, a millimetre-per-point no name said; it is now measured at 10 pt
#: and scaled by a ratio of two millimetres, the same arithmetic with every unit its own. Not a finding; the
#: register stays 7.
#: §BH55 Phase 2 p2-display (2026-09-19): 908 → 922, located to the line — one NEW file, the fit engine, and the
#: composer. `apps/ire/fit_grid.py` (new) 0 -> 10: an arrangement's inner width and depth, each a sum and its binding
#: (:49-50, 4); the lip and the back wall from the unit's height, three floors in two max (:68-69, 3); the tray's
#: outer width and depth (:70-71, 2); the header card's height (:72, 1). `apps/ire/compose_artwork.py` 22 -> 26: the
#: owner's 5.0 pt floor under the headline's own, `max(HEADLINE_FLOOR_PT, …)`, and the range kept whole, `max_pt =
#: max(max_pt, min_pt)` (:290-291, +3); the presentation sheet 11 -> 12 — a structure panel's label and its advance
#: counted (:476-479, +5), and the pieces' own label and advance no longer (:470-473, −4): the sheet's scale is now
#: NAMED a ratio of two millimetres (`tallest_mm`, :459), where the analyser had read it as a length, and
#: `fmt.page_h * s` is a length it does not dimension. THE FIRST VERSION WAS TWO FINDINGS, and the analyser was right:
#: with the scale unnamed, a panel's label and its advance read `e["h_mm"] * s` as mm²; naming the ratio is the
#: same arithmetic with every unit its own. The name held to its box's height (a bisection inside its own range)
#: compares quantities the analyser does not dimension and adds no check. No other file moved. Not a finding; the
#: register stays 7.
#: §BH55 Phase 2 p2-gift (2026-09-19): 922 → 926, located to the line — a gift set's insert, beside the display's tray:
#: `apps/ire/fit_grid.py::insert_for` 10 -> 14 — the height the pieces need, the piece's height and the headroom above
#: it, a sum and its binding (:128, 2), and a cut-out's step across and down, the piece's width and depth each with the
#: space around it (:147, 2). The search for the least height the dimension gate accepts and the ranking by the
#: carton's size run on subscripts and loop values the analyser does not dimension, and count nothing. The dieline
#: agent's carton proposal, now ONE helper for the container stage's size and a set's, reads 3 -> 3 — nothing copied;
#: the new target module reads 0. No other file moved. Not a finding; the register stays 7.
#: §BH55 Phase 2 p2-front (2026-09-19): 926 → 939, located to the line — the carton front's type, set as type and
#: MEASURED: `apps/ire/compose.py` 13 -> 26, the type builder 3 -> 16. New: the name's pitch, the line's pitch and the
#: name's cap height, each a point size carried into millimetres and bound (:303, :304, :305, 3); the balanced lines
#: kept only when as many as the measured wrap's (:313, 1); the panel's width inside its safe margin, a difference and
#: its binding (:320, 2); where the name's last line stands and where its first does, each a sum and its binding (:325,
#: :326, 4); the block's top (:332, 2); and that top against the logo's foot (:340, 1). Kept: the panel's centre (:319)
#: and the two sizes at their size sinks (:331, :348), now 9.0 and 6.0 pt chosen as type where they were a fraction of
#: the panel's width. No other file moved. Not a finding; the register stays 7.
#: §BH55 Phase 3 p3-materials (2026-09-20): 939 → 940, located to the line — the materials' pictures:
#: `apps/dashboard/materials_library.py` 0 -> 1 — a page's long edge, the larger of its width and its height, two
#: lengths in the page's own points that agree (:225, 1), dividing the picture's edge into a scale. The search, the
#: colour distances and the paging run on names the analyser does not dimension and count nothing; the view reads 0.
#: No other file moved. Not a finding; the register stays 7.
#: §BH55(a) s1-compact (2026-09-20): 940 → 953, located to the line — the compact's case, the first archetype
#: this system could not draw and the form the owner's Phase 1 brief asks for:
#: `apps/pipeline/targets/container/silhouettes.py` 23 -> 36, ALL THIRTEEN inside `_compact` and NONE in the new
#: `_circle` helper, which draws four cubics and dimensions nothing (measured by analysing each function alone).
#: Every one is a millimetre bound to another millimetre in the case's own plan, which is the same shape as the
#: Phase 2 front's entry above: the case's corner radius, the lesser of its width and its height (:402, 1); the pan
#: field's top, the hinge plus a share of the lid's depth (:411, 2); the field's width inside its inset (:412, 1);
#: the field's height, a difference and its binding, the clasp end left clear (:413, 2); the gutter, the lesser of
#: the two field edges (:414, 1); the mirror's width and height (:441, 2); the artwork zone's height (:445, 1); and
#: where that zone stands, its left and its top (:446, 3). The row count, the pan diameter and the pan positions run
#: on a search and a loop the analyser does not dimension and count nothing. No other file moved — the editor's new
#: entry is data and reads 0, and the inference scan is a regex. Not a finding; the register stays 7.
#: §BH65(c)3 (2026-09-23): 953 → 955, located to the line — `apps/ire/tests/test_au3_divider_gates.py:442`, the
#: assertion that the concept's behind-the-type field starts below the mark: the mark's bottom edge, a sum of two
#: lengths (1), held against the field's top (1). The window's clear-space assertion at :430 reads 0 — its `clear`
#: comes back from a function the analyser does not dimension. The composer's new placement code moves nothing the
#: analyser reads (`compose_container.py` 29 -> 29) and `concept_front.py` (new) reads 0. Not a finding; the register
#: stays 7.
#: §BH65(c)4 (2026-09-23): 955 → 956, located to the line — `apps/ire/emitters/pdf_ai.py::_paint_pattern` 0 -> 1: the
#: halo rings' radius, one spacing out and stepped by the spacing (:951, :954), held against the pattern's reach, a
#: millimetre against a millimetre (1). The lines, dots and grain step through names the analyser does not dimension
#: and count nothing; `design_language.py`'s three new generators read 0. Not a finding; the register stays 7.
#: §BH65(c)8 (2026-09-23): 956 → 957, located to the line — `apps/ire/compose_container.py::wrap_name` :323, the
#: width estimate taking a tracked run's letter-spacing: em x points x `_TRACKING_MM_PER_PT`, a millimetre added to the
#: millimetre estimate (1). THE FIRST DRAFT WAS A FINDING and the analyser was right: the conversion was named
#: `_PT_TO_MM_EXACT`, which it cannot read, so it saw points added to millimetres; named with its `_MM_PER_PT`
#: suffix it is the same arithmetic with every unit its own. `geometry_report._text_bbox_mm`'s tracking term reads 0.
#: Not a finding; the register stays 7.
#: §BH66(a) (2026-09-24): 957 → 964, located to the line — six in `apps/ire/compose_container.py::_concept_face` (the
#: type width inside the ring :1066, the Arabic size's `_pt` binding :1071, the name's `x=`/`size_pt=` :1145 and the
#: Arabic line's :1155) and one in `apps/ire/concept_face.py::layout` :427, a band's conditional height, a block's
#: millimetres on both arms. THE FIRST DRAFT WAS TWO FINDINGS and the analyser was right both times: the point
#: conversion was named `PT_MM`, which it cannot read, and a dimensionless ratio was named `per_mm`, which it read — as
#: the naming law says it must — as a length. Named `MM_PER_PT` and `block_ratio`, the arithmetic is unchanged and every
#: unit is its own. Not a finding; the register stays 7.
#: §BH66(b) (2026-09-24): 964 → 969, located to the line — `apps/ire/compose_container.py::_native_decoration`, where the
#: rule moved below the name: +3 (the tier loop's named baseline :500, the name's ink bottom through `_INK_MM_PER_PT`
#: :502, the no-supporting-line rule height :542) and -1 (the rule's old height above the name, `zy + zh * 0.24`); and
#: +3 in `apps/ire/tests/test_au3_divider_gates.py`, the tests that read it — the name run nearest ABOVE the rule
#: (:933), the supporting run nearest BELOW it (:934), the direct-print zone's height off its own clip (:971).
#: `compose_dropper.py` holds at 16: its rule reads millimetres the analyser does not dimension. Not a finding; the
#: register stays 7.
#: §BH67(c)3 (2026-09-24): 969 → 970, located to the line — `apps/pipeline/targets/container/silhouettes.py
#: ::compact_lid_face` :427, the ONE definition of the lid face the compact's zone proposal now reads: the face's
#: height, the plan's height less the hinge band (1). `_compact` reads its face back through the keys that carry their
#: unit (`face["y_mm"]`, …), so its thirteen stand. THE FIRST DRAFT LOST NINE and the analyser was right to lose them:
#: it unpacked the face from a bare tuple, which the analyser does not dimension, and every length `_compact` derives
#: from the hinge — the pan field, the mirror, the artwork zone — fell to unknown (36 -> 27). Not a finding; the
#: register stays 7.
#: §BH67(b)2 (2026-09-24): 970 → 972, located to the line — both in the new `apps/ire/display_name.py::_leading`, the
#: reader that takes a concept's display name only as the record's own leading phrase: the quoted phrase's word count
#: against the record name's, `len(want) > len(have)` :63 and `len(want) == len(have)` :65 — a count against a count,
#: dimensionless on both sides (2). `compose_container.py` holds at 38 and the target at 4: the display name reaches
#: them as text. Not a finding; the register stays 7.
#: §BH67(d)2 (2026-09-24): 972 → 973, located to the line — `apps/pipeline/targets/container/__init__.py
#: ::reconstruct_container` :1761, the layout measure's run height: a name run's size in points through the named
#: conversion, `_r.size_pt * _MM_PER_PT`, a millimetre bound to a millimetre (1). THE FIRST DRAFT WAS A FINDING and the
#: analyser was right: it wrote the conversion as the bare `25.4 / 72.0`, which it cannot read, so it saw points bound
#: to `_size_mm` (MM_FROM_PT, certain); imported as `back_panel.MM_PER_PT` it is the same arithmetic with every unit its
#: own. `concept_face.py` holds at 1 (its one check is `layout`'s, §BH66(a)): the new follow pass moves millimetres
#: the analyser does not dimension. Not a finding; the register stays 7.
#: THE OWNER'S ANSWER TO THE §BH68 REPORT (2026-09-25, OWNER_BLOCKER_CLEARANCE.md, the block of that date): 973 → 974,
#: located to the line — `apps/ire/compose_dropper.py::front_name_lines` :922, the dropper name's break measured in the
#: face the emitter draws: the name's size in points through the named conversion, `size_pt * back_panel.MM_PER_PT`,
#: a millimetre bound to a millimetre (1). The composer's other sixteen stand. Not a finding; the register stays 7.
#: THE OWNER'S SECOND ANSWER OF 2026-09-25 ("Make Gate 2 measure the front's height."): 974 → 977, located to the line —
#: `apps/ire/compose_dropper.py::_vertical_fit`, the print-size block's ink against the zone's safe band: the run's size
#: in points through the named conversion, `size_mm = run["size_pt"] * back_panel.MM_PER_PT` :1019, a millimetre bound
#: to a millimetre (1); the ink's top and foot, each a millimetre baseline less a millimetre offset, `ink_top =
#: run["baseline_mm"] - extent[0] * size_mm` :1020 and `ink_bottom = ...` :1021 (2). `text_metrics.ink_extent_em`
#: works in em fractions the analyser does not dimension, 0 -> 0. Not a finding; the register stays 7.
#: THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines." 977 → 993, located to the line — sixteen, all in
#: the radial lines: `apps/ire/compose_container.py::_trim_rays_at_mark`, the rays shortened at the mark's clear
#: space, a ray's point at a share of its run, `xt, yt = x0 + t * (x1 - x0), y0 + t * (y1 - y0)` :1197 and :1212,
#: each a millimetre start plus a share of a millimetre run (4 + 4), its length off the same run `((x1 - x0) ** 2 +
#: (y1 - y0) ** 2) ** 0.5` :1205 (2), its node's move `dx, dy = xt - x1, yt - y1` :1217 (2) — the composer 38 → 50;
#: and `apps/ire/design_language.py::gen_radial_lines`, the stroke bound to its `_mm` name `stroke_mm =
#: params.stroke_min_mm` :492, the node's radius `node_r_mm` :493, where the rays begin `inner_mm = n * stroke_mm / (2.0
#: * math.pi)` :494, and a ray's reach against it `reach_mm <= inner_mm` :504 — 0 → 4. The rule's place
#: (`concept_face.place_rule`), the ring's corner (`compose_container._ring_on_the_lid`) and the colour readers move
#: millimetres the analyser does not dimension (dict and list reads), 0 → 0; the tests that read them add none. Not a
#: finding; the register stays 7.
#: THE OWNER'S SECOND ANSWER OF 2026-09-25 ("When I approve the logo trace, switch the mark to it so gold foil can
#: print."): 993 → 994, located to the line — `apps/ire/tests/test_c10_mark_width.py`, the dropper front drawn from an
#: approved master, `closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"] + ...)` :301, two
#: millimetres summed (1) — the same sum the file already makes at :101. `apps/ire/brand_mark.py` adds none: the master's
#: geometry is in its own units, which the analyser does not dimension, 0 -> 0. Not a finding; the register stays 7.
#: §BH69(1), THE OWNER'S APPROVAL OF 2026-09-26 ("Remove the supplier code."): 994 → 992, located to the line —
#: `apps/pipeline/services/supplier_eml.py::generate`, `len(bodies) == len(rows)` :267, and
#: `apps/pipeline/services/supplier_sent_validation.py::validate`, `len(verified) == len(rows)` :246, a comparison each
#: (1 + 1), left the tree with their modules; supplier_dispatch.py held none since §BH45(f). No other file moved. Not a
#: finding; the register stays 7.
#: §BH70(1), THE OWNER'S GOAL OF 2026-09-26 ("A 'Complete Product' is ANY cosmetic product, not a bottle"): 992 → 1002,
#: located to the line — `apps/pipeline/targets/container/silhouettes.py::_capped_body`, the one outline the new
#: lipstick, mascara and pencil share: `min(base_radius, W / 2.0, (H - cap_h) / 2.0)` :532 (1), `cx - cw / 2.0` and
#: `cx + cw / 2.0` :533 (2), `H - cap_h` :552 (1), `cx - lw / 2.0` and `cap_h + (body_h - lh) / 2.0` :554 (3) —
#: millimetres against millimetres, 37 → 44 in the file. The three builders that call it add none. And its test,
#: `apps/pipeline/tests/test_container_silhouettes.py::test_the_slim_forms_are_drawn_closed_with_the_print_on_the_body_
#: below_the_cap`: `ly >= cap_bottom` :68 (1), and `lx + lw` and `ly + lh` :69 (2) — 0 → 3 in the file. No other
#: file moved. Not a finding; the register stays 7.
#: §BH70(1), THE SAME GOAL, THE SHEET'S OWN WORDS KEPT ON ITS PAGE: 1002 → 1009, located to the line —
#: `apps/ire/compose_container.py`: `est_mm <= room_mm` in `chrome_size_pt` :402 (1); the reference label kept on the
#: page, `_ref_box[0] + _ref_box[2] / 2` against `_room_x0_mm + _ref_half_mm` :1756 (1) and
#: `_room_x0_mm + _room_mm - _ref_half_mm` :1757 (2), and its size `_ref_label_pt` into `centered_text` :1760 (1); the
#: swatch row's end `_row_end_mm = _room_x0_mm + _room_mm` :2023, the sum (1) and the named millimetres it is stored
#: in (1) — millimetres against millimetres and a point size into a point sink, 50 → 57 in the file. Its tests add
#: none. No other file moved. Not a finding; the register stays 7.
#: §BH70(1), THE SAME GOAL, A NAME ITS FRONT WOULD CUT REFUSED, NEVER DRAWN CUT (his §BD(b)): 1009 → 1012, located to
#: the line — `apps/ire/compose_container.py::refuse_a_clipped_name`, `line_mm > front_mm` :411 (1), 57 → 58 in the
#: file; `apps/pipeline/targets/container/__init__.py::name_fits_front`, `word_mm <= front_mm` :180 (1), 5 → 6; and
#: its test, `apps/ire/tests/test_compose_container.py`, `refused.value.line_mm > refused.value.front_mm` :281 (1),
#: 0 → 1 — millimetres against millimetres. No other file moved. Not a finding; the register stays 7.
#: §BH70(1), THE SAME GOAL, ITEM 5 OF THE LIST HE WAS SENT — THE GENERIC PATH'S FRONT COPY MEASURED ACROSS: 1012 → 1015,
#: located to the line, all three in its tests — `apps/ire/tests/test_compose_container.py::test_bh70_the_generic_front_
#: copy_is_measured_across_against_the_confirmed_zone`, `safe_mm = float(front["width"]) - 2 *
#: float(front["safe_margin_mm"])` :339, the difference (1) and the named millimetres it is stored in (1), 1 → 3 in the
#: file; `apps/pipeline/tests/test_wif_reconstruct_container.py::TheDisplayWordmarkReachesTheFaceTests::test_bh70_the_
#: lids_front_copy_is_measured_across_and_what_is_not_says_why`, `r["width_mm"] < r["safe_area_mm"]` :1025 (1), 2 → 3
#: — millimetres against millimetres. The instrument and the reading add none. No other file moved. Not a finding; the
#: register stays 7.
#: §BH70(1), THE SAME GOAL, ITEM 21 OF THE LIST HE WAS SENT — THE FORM'S OWN WORDS: 1015 → 1018, located to the line, all
#: three in one test fixture — `apps/pipeline/tests/test_browser_profile_editor.py::_ProfileEditorFixtures._confirmable_
#: task`, now taking a form and its size, `width_mm, depth_mm, height_mm = size_mm` :152, three named millimetres (3),
#: 0 → 3 in the file. The words change none. No other file moved. Not a finding; the register stays 7.
#: §BH71 (0b), THE OWNER'S GOAL OF 2026-09-28 — A BATCH-CODE PLACE FOR EVERY FORM: 1018 → 1023, located to the line —
#: `apps/pipeline/services/container_contract.py::code_zone_for`, the compact's code band read off the base panel the
#: proposal just made, `base["y"] + base["height"]` :807 (1) and the conditional that takes it or the plan's own 0.95
#: share :807 (1), and the band's height, the plan's height less its top :808 (1), 0 → 3 in the file; `apps/pipeline/
#: tests/test_gate1_concept_selection.py::DropperZoneTests::test_bh71_every_form_is_offered_a_code_place_of_its_own`,
#: the band's top against the base panel's foot :200 — the sum (1) and the comparison (1), 0 → 2 — millimetres against
#: millimetres. No other file moved. Not a finding; the register stays 7.
#: §BH71 PART 1, THE OWNER'S GOAL OF 2026-09-28 — THE DRAWN SHAPE COMES FROM THE CONCEPT: 1023 → 1032, located to the
#: line — `apps/pipeline/targets/container/silhouettes.py`: the round lid's face in `compact_lid_face`, `d_mm =
#: min(float(width_mm), float(height_mm))` :444, the min (1) and the named millimetres it is stored in (1); the case's
#: corner in `_compact`, `r_case = min(W, H) * min(0.5, max(0.0, corner_share))` :476 (1), the check it replaces
#: (HEAD's `r_case = min(W, H) * 0.08` :455, 1) gone; the round case's pan field, `side_mm = face["width_mm"] * 0.62`
#: :495 (1), and its insets `cx - side_mm / 2.0` and `H / 2.0 - side_mm / 2.0` :496 (2); the round lid's label box,
#: `cx - lw / 2` and `H / 2.0 - lh / 2.0` :546 (2) — 44 → 51 in the file; `apps/pipeline/targets/ui.py`, a round
#: compact's two sides, `abs(float(w_mm) - float(h_mm)) > 0.5` :434 (1), 0 → 1; and its test, `apps/pipeline/tests/
#: test_wif_reconstruct_container.py::TheLidIsTracedFromItsConceptTests`, `self.confirmed["height_mm"] ==
#: self.confirmed["width_mm"]` :1299 (1), 3 → 4 — millimetres against millimetres. The tracer, `apps/pipeline/services/
#: concept_outline.py` (new), adds none: it measures pixels and shares of them. No other file moved. Not a finding;
#: the register stays 7.
#: §BH71 PART 1, THE SAME GOAL — A ROUND LID'S ZONES AND PRINT INSIDE ITS CIRCLE: 1032 → 1040, located to the line —
#: `apps/pipeline/services/container_contract.py`: the round lid's own face zone, `d = min(surface["w"],
#: surface["h"])` in `round_face` :461 (1); the circle's radius in `outside_the_circle`, `min(surface["w"],
#: surface["h"]) / 2.0` :472 (1); the round base's panel in `propose_zones`, `d = min(bg["w"], bg["h"])` :754 (1)
#: and its place, `(bg["w"] - w) / 2` and `(bg["h"] - h) / 2` :756 (2); the round base's code window in
#: `code_zone_for`, `d = min(bg["w"], bg["h"])` :854 (1) and `min(h, 0.05 * d)` :855 (1) — 3 → 10 in the file;
#: `apps/ire/compose_container.py::_outside_the_round_lid`, the name's size taken as the named point size,
#: `size_pt = set_["size_pt"]` :1363 (1), 58 → 59 — millimetres against millimetres, a point size into a point
#: sink. Its tests add none. No other file moved. Not a finding; the register stays 7.
#: §BH71 PART 1, THE SAME GOAL — EVERY FORM DRAWN STANDING TAKES ITS OUTLINE FROM ITS CONCEPT: 1040 → 1045, located to
#: the line — `apps/pipeline/targets/container/silhouettes.py::_traced_elevation`, the body below the traced closure,
#: `body_h = H - body_top` :718 (1), and the label's top in it, `ly = body_top + body_h * 0.26` :720 (1), 51 → 53 in the
#: file; its test, `apps/pipeline/tests/test_container_silhouettes.py::test_bh71_a_form_drawn_in_elevation_is_drawn_
#: from_its_traced_outline`, the label inside the traced body, `ly > cap_foot` and `lx + lw < 40.0` and `ly + lh <
#: 144.0` :136 (3), 3 → 6 — millimetres against millimetres. The tracer (`concept_outline.py`) adds none: it measures
#: pixels and shares of them. No other file moved. Not a finding; the register stays 7.
#: §BH71 PART 3, THE SAME GOAL — FIVE NEW FORMS, EACH A SHAPE THE SYSTEM CAN DRAW: 1045 → 1071, located to the line —
#: `apps/pipeline/targets/container/silhouettes.py`: the tin's round lid, `d = min(W, H)` :764 (1), and its slide
#: lid's traced corner, `min(W, H) * min(0.5, ...)` :769 (1); the sachet's seal, `max(3.0, min(W, H) * 0.06)` :783 (1),
#: the room inside its seals, `W - left - right` and `H - 2.0 * seal` :791 (3), and its label's place in it :793 (3);
#: the can's body under its cap, `body_top = cap_h + H * 0.11` :829 (1) and `cap_h + H * 0.03` :833 (1), `body_h = H -
#: body_top` :836 (1); the ampoule's, `body_top = tip * H + H * 0.10` :866 (1) and `body_h` :867 (1) — 53 → 67 in the
#: file; `apps/pipeline/services/container_contract.py::propose_zones`, the round tin's lid, `min(lid["w"],
#: lid["h"])` :816 (1) and its box `(lid["w"] - d) / 2.0`, `(lid["h"] - d) / 2.0` :817 (2), its base panel, `min(bg["w"],
#: bg["h"])` :825 (1) and its place :827 (2) — 10 → 16; its tests, `apps/pipeline/tests/test_container_silhouettes.py::
#: test_bh71_each_new_form_is_drawn_by_a_builder_of_its_own`, the label inside its box :77 (4) and a drawing per variant
#: :80 (1), 6 → 11, and `apps/pipeline/tests/test_browser_profile_editor.py`, a picture per form :403 (1), 3 → 4 —
#: millimetres against millimetres. No other file moved. Not a finding; the register stays 7.
#: §BH71 (0b), THE SAME GOAL — EVERY PROPOSED CODE PLACE HOLDS ITS CODE: 1071 → 1073, located to the line —
#: `apps/pipeline/tests/test_gate1_concept_selection.py::DropperZoneTests::test_bh71_every_code_place_holds_one_line_
#: of_its_code`, the window's room inside its margins, `min(z["width"], z["height"]) - 2 * z["safe_margin_mm"]` :240 (2),
#: 2 → 4 — millimetres against millimetres (the line it must hold is 2.0 pt turned to millimetres by the contract's own
#: `code_line_mm`). `container_contract.py` stays 16. No other file moved. Not a finding; the register stays 7.
#: §BH71 PART 3, THE SAME GOAL — THE CATALOGUE'S OTHER 34 PACKAGINGS, EACH A FORM, VARIANT AND CLOSURE THE SYSTEM DRAWS:
#: 1073 → 1079, located to the line — `apps/pipeline/targets/container/silhouettes.py`: the airless bottle's overcap as
#: its neck, `min(cap_w, W * 0.98)` :329 (1), and the airless jar's body below its button and lid, `body_top = top +
#: lid_h` :407 (1) — 67 → 69; its test, `apps/pipeline/tests/test_container_silhouettes.py::test_bh71_every_catalogue_
#: shape_is_a_shape_the_system_draws_at_its_own_size`, the label inside its box, `lx + lw <= bb.width_mm + 1e-6` and
#: `ly + lh <= bb.height_mm + 1e-6` :85 (4), 11 → 15 — millimetres against millimetres. No other file moved. Not a
#: finding; the register stays 7.
#: §BH71 PART 3, THE SAME GOAL — A LID THE CONCEPT SHOWS IS LEARNED AND DRAWN (A LEARNED OVAL): 1079 → 1091, located to
#: the line — `apps/pipeline/targets/container/silhouettes.py::_compact`, an oval case's pan field centred,
#: `cx - field_w / 2.0` and `H / 2.0 - field_h / 2.0` :585 (2), 69 → 71; `apps/pipeline/services/container_contract.py`:
#: the oval compact's and the oval tin's base panel centred, `(bg["w"] - w) / 2` and `(bg["h"] - h) / 2` :811 and :888
#: (4), the oval's code window, `min(h, 0.05 * min(bg["w"], bg["h"]))` :1010 (1) and the room the ellipse holds below
#: the panel, `b + b * math.sqrt(...) - top` :1013 (2), 16 → 23; its tests, `apps/pipeline/tests/test_gate1_concept_
#: selection.py::DropperZoneTests::test_bh71_a_learned_oval_lids_zones_keep_inside_its_ellipse`, the code window's
#: room inside its margins :270 (2), 4 → 6, and `apps/pipeline/tests/test_wif_reconstruct_container.py::
#: TheLearnedOvalLidIsDrawnTests`, the confirmed oval shorter than wide :1381 (1), 4 → 5 — millimetres against
#: millimetres. No other file moved. Not a finding; the register stays 7.
#: §BH71 PART 2, THE SAME GOAL — THE TREND BOARD: 1091 → 1092, located to the line — `apps/pipeline/services/
#: trend_board.py::subject_of` (a new file), the longest of a catalogue shape's words the brief says, `len(word) >
#: len(heard)` :136 (1), 0 → 1 — characters against characters. No other file moved. Not a finding; the register
#: stays 7.
#: HIS ANSWER OF 2026-09-29 TO THE §BH71 REPORT, (4) — THE LID DRAWS THE RECORD'S SHADE: 1092 → 1096, located to the
#: line — `apps/ire/concept_face.py::layout`, the air beside the shade line, `room = shade_gap if SHADE in (a, b) and
#: shade_gap is not None else gap` :409 (1), 1 → 2; `apps/ire/compose_container.py::_concept_face`, the shade's runs
#: set at its named point size, `size_pt=shade_set["size_pt"]` :1932 (1), 59 → 60; its test, `apps/pipeline/tests/
#: test_wif_reconstruct_container.py::TheLidDrawsTheRecordsShadeTests`, the shade line below the Arabic name and in the
#: face's lower fifth, `name_ar_y < runs["product-shade"].y and (runs["product-shade"].y - zy) / zh > 0.8` :1423 (2),
#: 5 → 7 — millimetres against millimetres, points against points. No other file moved. Not a finding; the register
#: stays 7.
#: HIS TEST DAY FINDING 3 (2026-09-30, DESIGN 117) — THE TUBE TEMPLATE DRAWS A SQUEEZE TUBE: 1096 → 1106, located to the
#: line — `apps/pipeline/targets/container/silhouettes.py::_squeeze_tube` (a new builder), the shoulder's foot and the
#: crimp band's top, `y2 = cap_h + TUBE_SHOULDER_H * H` :450 (1) and `y3 = H - TUBE_CRIMP_H * H` :451 (1), the body's
#: reach, `body_h = y3 - y2` :466 (1), the label's place on it, `ly, lh = y2 + body_h * 0.22, body_h * 0.55` :467 (1),
#: and the body's width where the label starts, `reach = round_w + (W - round_w) * (ly - y2) / body_h` :468 (3), 71 → 78;
#: its test, `apps/pipeline/tests/test_container_silhouettes.py::test_finding3_a_squeeze_tube_is_drawn_a_tube_not_a_
#: bottle`, the cap's measured width `max(...) - min(...)` :353 (1) and the label inside the body below the cap and above
#: the crimp :359 (2), 15 → 18 — millimetres against millimetres. No other file moved. Not a finding; the register
#: stays 7.
#: HIS TEST DAY FINDING 3 (2026-09-30, DESIGN 117) — A TUBE'S FRONT COPY IN THE FRONT HE CONFIRMED: 1106 → 1108, located
#: to the line — its test, `apps/pipeline/tests/test_container_target.py::TheTubesFrontCopyIsLaidInTheZoneHeConfirmedTests
#: ::test_finding3_a_tubes_label_is_the_front_he_confirmed_held_on_its_body`, the label at his front's own height and
#: inside its width, `(ly, lh) == (40.5, 99.0) and 7.5 <= lx and lx + lw <= 42.5` :184 (1), and inside the drawn body's
#: span, `left <= lx + 1e-9 and lx + lw <= right + 1e-9` :186 (1), 0 → 2 — millimetres against millimetres. No other
#: file moved. Not a finding; the register stays 7.
#: HIS TEST DAY FINDING 3 (2026-09-30, DESIGN 117) — A TUBE ITS CONCEPT STANDS ON ITS CAP IS DRAWN ON ITS CAP: 1108 →
#: 1114, located to the line — `apps/pipeline/targets/container/silhouettes.py::_stood_on_closure` (new), the label
#: turned end over end with the drawing, `ly = H - ly - lh` :899 (2), 78 → 80; its test, `apps/pipeline/tests/test_
#: container_silhouettes.py::test_finding3_a_tube_its_concept_stands_on_its_cap_is_drawn_on_its_cap`, the label clear of
#: the cap and the logo above the name, `ly + lh <= min(cap_ys) and bb.anchors["logo"][1] < bb.anchors["product_name"]
#: [1]` :393 (2), and a transparent tube's fill the body above its cap, `fill.h > 0.5 * (cap_top - fill.y) > 1.0 and
#: fill.y + fill.h <= cap_top + 1e-6` :403 (2), 18 → 22 — millimetres against millimetres. No other file moved. Not a
#: finding; the register stays 7.
#: HIS TEST DAY FINDING 3 (2026-09-30, DESIGN 117) — THE BODY IN ITS CONCEPT'S TWO COLOUR FIELDS: 1114 → 1120, located to
#: the line — its test, `apps/pipeline/tests/test_2b3v_corr4_geometry.py::test_finding3_the_body_is_drawn_in_its_concepts
#: _two_colour_fields`, one colour read at every height the profile is read, `len(trace["axis_colours"]) == len(trace[
#: "profile"])` :94 (1), and the lower field from the split to the foot, `abs(field.y - (top + split * (foot - top))) <
#: 1e-6 and field.y + field.h >= foot - 1e-6` :109 (5), 0 → 6 — heights against heights, millimetres against
#: millimetres. No other file moved. Not a finding; the register stays 7.
#: HIS TEST DAY FINDING 3 (2026-09-30, DESIGN 117) — HIS FRONT LEAVES THE CONCEPT'S OWN ELEMENTS THEIR ROOM: 1120 → 1121,
#: located to the line — its test, `apps/pipeline/tests/test_2b3v_corr4_geometry.py::test_finding3_his_front_leaves_the_
#: concepts_own_elements_their_room_above_the_mark`, the mark's top and foot read in the drawing's millimetres,
#: `(mark.y + mark.h - top) / mm` :199 (1), 6 → 7 — millimetres against millimetres. No other file moved. Not a
#: finding; the register stays 7.
#: HIS ANSWER AFTER TEST DAY FINDING 3 (2026-09-30) — THE SCORE, THE DRAWING AGAINST THE CONCEPT: 1121 → 1122, located to
#: the line — `apps/pipeline/services/concept_design_map.py::score`, a part's offset read in the product's own
#: millimetres, its width for x and its height for y, `(w if i % 2 == 0 else h)` :624 (1), 0 → 1 — millimetres against
#: millimetres. No other file moved. Not a finding; the register stays 7.
#: HIS ANSWER AFTER TEST DAY FINDING 3 (2026-09-30), (4) ROUND — A TUBE DRAWN AS WIDE AS ITS FLAT END: 1122 → 1124, located
#: to the line — `apps/pipeline/tests/test_container_silhouettes.py::test_finding3_a_squeeze_tube_is_drawn_a_tube_not_a_
#: bottle`, its width now the drawing's own (`W = bb.width_mm`, π/2 of the round 50) where it was a literal, so the
#: flip-top against it, `abs(cap_w - 0.96 * 2 / math.pi * W) < 0.01` :357 (1), and the label inside it,
#: `lx + lw < W` :363 (1), are counted, 22 → 24 — millimetres against millimetres. No other file moved. Not a finding;
#: the register stays 7.
#: HIS ANSWER AFTER TEST DAY FINDING 3 (2026-09-30) — THE FRONT DRAWN FROM ITS CONCEPT'S MAP: 1124 → 1143, located to the
#: line — `apps/ire/compose_container.py::_map_front_group` (new), a traced part held inside his confirmed front (his yes,
#: transcribed at 5d23649: "drawn from the map only inside the area he confirms"), `x0, x1, y0, y1 = max(x0, zx),
#: min(x1, zx + zw), max(y0, zy), min(y1, zy + zh)` :2002 (6), 60 → 66; its test, `apps/pipeline/tests/test_2b3v_corr4_
#: geometry.py::test_his_answer_the_front_draws_the_band_its_edge_and_the_rule_its_picture_traced`, the sheet's scale and
#: origin read off the drawn body `s = ...`, `ox = ...`, `oy = ...` :281-283 (4), the edge's width and the rule's place
#: against them :287-288 (5), his front's right edge `right = ...` :298 (1), and a wider rule's cut on each side
#: :306-307 (3), 7 → 20 — millimetres against millimetres (its first draft set the rule's height against a bare
#: `180.0`, which the analyser read as MIXED; it is the drawing's own `bb.height_mm`). No other file moved. Not a
#: finding; the register stays 7.
#: HIS ANSWER AFTER TEST DAY FINDING 3 (2026-09-30) — THE MARK FROM ITS MASTER WHERE THE PICTURE PRINTS IT: 1143 → 1158,
#: located to the line — `apps/ire/compose_container.py::_map_mark_box` (new), the drawing's own millimetres bound
#: `w_mm, h_mm = backbone.width_mm, backbone.height_mm` :1980 (2), the mark's left edge at the picture's ink, held inside
#: his front, `x0 = max(fx0 * w_mm, ...)` :1984 (1) and `x0 = min(x0, ... - ww)` :1985 (3), 66 → 72; its test,
#: `apps/pipeline/tests/test_2b3v_corr4_geometry.py::test_his_answer_the_mark_is_drawn_from_its_master_where_the_picture_
#: prints_it`, the sheet's scale and origin read off the drawn body :378-380 (4), the mark's height at the picture's ink
#: :381 (1) and its place :383 (4), 20 → 29 — millimetres against millimetres. No other file moved. Not a finding; the
#: register stays 7.
#: HIS ANSWER AFTER TEST DAY FINDING 3 (2026-09-30) — THE FRONT'S TYPE SET WHERE ITS PICTURE PRINTS IT: 1158 → 1171, located
#: to the line — `apps/ire/compose_container.py::_map_type_group` (new), a line's size from its traced height
#: `size_pt = bh / lines_em / _INK_MM_PER_PT` :2020 (1) and from its height and width `size_pt = min(bh /
#: MAP_TYPE_INK_EM / _INK_MM_PER_PT, bw / width_mm_per_pt)` :2032 (2), its ink centred in its traced rows :2036 (2), its
#: baselines :2037 (2), the name's centre :2042 (1), each run's `size_pt=` sink :2043 (1) and :2057 (1), and its drawn
#: rows :2061 (1), 72 → 83 (its first draft divided millimetres by a bracketed sum and by a width taken at one point,
#: which the analyser read as PT_FROM_MM at :2019 and :2030; each is now named — `lines_em`, `width_mm_per_pt` — and
#: read as points); its test, `apps/pipeline/tests/test_2b3v_corr4_geometry.py::test_his_answer_the_front_sets_its_type_
#: where_its_picture_prints_it`, the English run left of the Arabic at one size :432 (2), 29 → 31 — millimetres against
#: millimetres, points against points. No other file moved. Not a finding; the register stays 7.
#: HIS ANSWER AFTER TEST DAY FINDING 3 (2026-09-30), (3) — THE NAME DRAWN AS THE PICTURE'S TRACED LETTERING: 1171 → 1172,
#: located to the line — `apps/ire/container_fidelity.py::measure_fidelity`, a traced name's size against the name's
#: floor, `traced["size_pt"] >= _MIN_NAME_PT` :154 (1), 1 → 2 — points against points. No other file moved. Not a
#: finding; the register stays 7.
#: HIS LOOK AT 117 DRAWN FROM ITS MAP (2026-10-02) — THE ENGLISH WORDS ADDED, A BILINGUAL LINE'S RUNS ANCHORED TOWARD
#: THEIR JOIN: 1172 → 1173, located to the line — its test, `apps/pipeline/tests/test_2b3v_corr4_geometry.py::
#: test_his_look_the_english_words_the_picture_prints_are_added_with_its_separators`, the gap between the two runs
#: against one space's width `(runs[1].x - runs[0].x) - name_width_estimate_mm(" ", …)` :506 (1), 31 → 32 —
#: millimetres against millimetres. No other file moved (the composer's anchoring adds no check: 83 → 83). Not a
#: finding; the register stays 7.
#: HIS LOOK AT 117 DRAWN FROM ITS MAP (2026-10-02) — THE ARCHES BETWEEN THE DRIPS IN THE PICTURE'S OWN GRADIENT: 1173 →
#: 1174, located to the line — its test, `apps/pipeline/tests/test_vqr2b_concept_analysis.py::ConceptOutlineTraceTests::
#: test_his_look_the_arches_between_the_drips_take_the_pictures_own_gradient`, the drawn gradient's stops against the
#: traced ones `len(arches.fill.stops) == len(stops)` :951 (1), 3 → 4 — a count against a count. No other file moved
#: (the composer 83 → 83). Not a finding; the register stays 7.
#: HIS LOOK AT 117 DRAWN FROM ITS MAP (2026-10-02) — "AND ALSO THE 3D": THE SQUEEZE TUBE IN 3D: 1174 → 1175, located to
#: the line — `apps/pipeline/services/tube_proof.py::tube_mesh` (new), the crimp's rib laid on either face
#: `z += rib if z >= 0.0 else -rib` :96 (1), 0 → 1 — millimetres against millimetres. Its engine script and its test add
#: none (0 → 0, 32 → 32). Not a finding; the register stays 7.
#: HIS SECOND LOOK AT 117 (2026-10-02) — "ADD THE ARABIC LINES": 1175 → 1176, located to the line — `apps/ire/
#: compose_container.py::_map_type_group`, a line of one run centred where the picture centres it `x, align = fx0 * w +
#: bw / 2.0, "center"` :2158 (1), 83 → 84 — millimetres against millimetres (the run's `size_pt=` sink moved a line, one
#: for one). No other file moved. Not a finding; the register stays 7.
#: HIS RULES FOR CLONING A DESIGN FROM A PICTURE (2026-10-02), RULE 5 — "THE BACK IS DRAWN": 1176 → 1177, located to the
#: line — its test, `apps/pipeline/tests/test_2b3v_corr4_geometry.py::test_his_rules_the_back_is_drawn_from_the_briefs_
#: back_copy_at_the_size_it_prints`, the panel's foot inside the grown sheet `box.y + box.h <= doc.page_h` :557 (1),
#: 32 → 33 — millimetres against millimetres. The composer, the map's reader, the target and the placeholder record add
#: none (84 → 84, 1 → 1, 6 → 6, 0 → 0). Not a finding; the register stays 7.
#: HIS RULES FOR CLONING A DESIGN FROM A PICTURE (2026-10-02), RULE 2 — "SHAPES ARE REDRAWN AS CLEAN CURVES": 1177 → 1178,
#: located to the line — its test, `apps/pipeline/tests/test_vqr2b_concept_analysis.py::ConceptOutlineTraceTests::test_his_
#: rules_the_drips_are_redrawn_as_clean_curves_their_gold_even_and_open_at_the_rule`, the cubics drawn against the 4 px
#: steps along the band `len(list(curves(fill))) <= steps / 2` :1170 (1), 4 → 5 — a count against a count. The map's
#: tracer and the composer add none (1 → 1, 84 → 84). Not a finding; the register stays 7.
#: HIS GO OF 2026-10-02 — THE MAP PATH FOR A WAND VIAL: WHERE ITS PICTURE PRINTS NO MARK THE HOUSE MARK KEEPS CLEAR OF ITS
#: PARTS: 1178 → 1182, located to the line — `apps/ire/compose_container.py::_mark_clear_of`, the closure's edge against
#: half the product's height `min(cap_ys) < h / 2.0` :2361 (1) and the front's middle `float(zone["x"]) +
#: float(zone["width"]) / 2.0` :2375 (1), 84 → 86 — millimetres against millimetres; and its test, `apps/pipeline/tests/
#: test_2b3v_corr4_geometry.py::test_his_go_where_a_vials_picture_prints_no_mark_the_house_mark_keeps_clear_of_its_parts`,
#: the body's width and height from its own points `max(xs) - min(xs), max(ys) - min(ys)` :1131 (2), 33 → 35 — millimetres
#: against millimetres. Not a finding; the register stays 7.
#: HIS GO OF 2026-10-02 — THE MAP PATH FOR A WAND VIAL: A LINE SET WHERE ITS PICTURE PRINTS IT NEVER UNDER THE PRINT FLOOR:
#: 1182 → 1188, located to the line — `apps/ire/compose_container.py`: `MAP_TYPE_FLOOR_PT = FALLBACK_FLOOR_PT` :1993 (1),
#: `_map_type_group`'s `pictured_pt = size_pt` :2166 (1), `size_pt = max(size_pt, MAP_TYPE_FLOOR_PT)` :2167 (2), `if is_name
#: and size_pt > pictured_pt` :2168 (1) and its record's `if size_pt > pictured_pt` :2263 (1), 86 → 92 — points against
#: points. Its test and the target's fit instrument add none (35 → 35, 6 → 6). Not a finding; the register stays 7.
#: HIS GO OF 2026-10-02 — THE MAP PATH FOR A CARTON, ITS DRAWING: 1188 → 1198, located to the line — its test, `apps/ire/
#: tests/test_compose.py::test_his_go_a_cartons_front_is_drawn_from_its_own_concepts_map`, each drawn part's box on the
#: front panel `ground.x + x0 * front.width` and `ground.y + y0 * front.height` :212-:213 (4) and the mark clear of it
#: `logo.y + logo.h <= py0 + 1e-6 or ...` :214-:215 (6), 0 → 10 — millimetres against millimetres. The composer, the
#: carton's target, ARIA, the dieline agent and the export service add none (26 → 26, 0 → 0, 0 → 0, 3 → 3, 0 → 0). Not
#: a finding; the register stays 7.
#: HIS ANSWER 3 OF 2026-10-02 — "THE SCORE'S YARDSTICK IS A FULL-SIZE TRACE OF THE CONCEPT": 1198 → 1201, located to the
#: line — `apps/pipeline/services/concept_design_map.py::score_traced`, the product's size taken in millimetres `w_mm,
#: h_mm = size_mm` :2586 (2) and each coordinate's offset at its own axis's millimetres `w_mm if i % 2 == 0 else h_mm`
#: :2622 (1), 1 → 4 — millimetres against millimetres. Its test and the container target add none (5 → 5, 6 → 6). Not a
#: finding; the register stays 7.
#: HIS GO OF 2026-10-02 — THE MAP PATH FOR A WAND VIAL: A NAME THE MAP SETS IS NOT STOPPED AT THE RULED SIZE: 1201 → 1202,
#: located to the line — its test, `apps/pipeline/tests/test_container_target.py::ContainerFlowTests::test_his_go_a_vials_
#: name_is_not_stopped_where_its_map_sets_it`, the word's width against the front's `stop["word_mm"] > stop["front_mm"]`
#: :588 (1), 2 → 3 — millimetres against millimetres. The target and the view add none (6 → 6, 0 → 0). Not a finding;
#: the register stays 7.
#: THE OWNER'S FINDING ON DESIGN 119, 2026-10-03 — A DISPLAY OR TURNED LINE DRAWN AS THE PICTURE LETTERS IT: 1202 → 1205,
#: located to the line — `apps/ire/compose_container.py::_map_type_group`, the line's size taken across its letters
#: `across = (tx1 - tx0) if t.get("rotation") in (90, -90) else (ty1 - ty0)` :2211 (3: the two differences and their
#: choice), 92 → 95 — millimetres against millimetres. The map's setter and its test add none. Not a finding; the
#: register stays 7.
#: THE OWNER'S FINDING ON DESIGN 119, 2026-10-03 — EVERY PANEL VECTOR, ITS EDGE-TO-EDGE PARTS CONTINUED ROUND THE CARTON:
#: 1205 → 1208, located to the line — its test, `apps/ire/tests/test_compose.py::test_his_finding_on_119_every_panel_is_
#: vector_and_continues_the_concepts_ground_and_graphics`, each continued strip against its panel `abs(band.w -
#: p.width)` and `abs(band.h - 0.2 * p.height)` :245 (2) and `abs(rule.h - 0.008 * p.height)` :246 (1), 10 → 13 —
#: millimetres against millimetres. The composer, ARIA and the export service add none (26 → 26, 0 → 0, 0 → 0). Not a
#: finding; the register stays 7.
#: THE OWNER'S FINDING ON DESIGN 119, 2026-10-03 — HIS BRIEF'S SIDE COPY ON BOTH SIDES: 1208 → 1218, located to the line —
#: `apps/ire/compose.py::_side_copy_nodes`, the size the side copy is set at, the front's smallest typed line never under
#: the floor `size_pt = max(min(sizes) if sizes else FRONT_LINE_PT, MAP_TYPE_FLOOR_PT)` :265 (3), the side's length inside
#: its margins :270 (1), its middle :271 (2), the first line's place across it :272 (1), each line's baseline :280 (2)
#: and each run's size :284 (1), 26 → 36 — points against points, millimetres against millimetres. The map's readers,
#: the carton's and the set's targets and their tests add none. Not a finding; the register stays 7.
#: THE CLEAN-UP OF 2026-10-04 — ONE ENGINE PER JOB, THE LEFTOVER RASTER CODE (E1/E2): 1218 → 1211, located to the code
#: that left — `apps/ire/compose.py::_motif_nodes` (7), the motif's per-panel placement, removed with the raster motif
#: path; compose.py 36 → 29. Nothing added. Not a finding; the register stays 7.
#: THE CLEAN-UP OF 2026-10-04 — THE OLD DASHBOARD'S LEFTOVERS (E7–E10d with F8): 1211 → 1210, located to the file that
#: left — `apps/pipeline/batch_views.py` (1), the batch API no page called, removed with its routes. Nothing added.
#: Not a finding; the register stays 7.
#: THE CLEAN-UP OF 2026-10-04 — THE WIRING CHECK (HIS GOAL, PART 3): 1210 → 1213, located to the line — its new file,
#: `apps/pipeline/tests/test_wiring_check.py`, the pixels-per-millimetre a test picture is drawn at, the smaller of its
#: two axes' `min(900.0 / h_mm, 520.0 / w_mm)` :149 (1) and `min(700.0 / h_mm, 560.0 / w_mm)` :174 (1), and a lid's
#: corner from its smaller side `min(pw, ph)` :184 (1), 0 → 3 — pixels against pixels. Nothing else moved. Not a
#: finding; the register stays 7.
#: THE CLEAN-UP OF 2026-10-05 — THE WIRING CHECK'S FINDING W11, A JAR'S WRAP LABEL READ ON ITS FRONT AS THE FRONT VIEW
#: DRAWS IT: 1213 → 1215, located to the line — `apps/ire/compose_container.py::_front_view_zone`, the label's two ends
#: round the unrolled wrap `float(zone["x"]) + float(zone["width"])` :302 (1), 95 → 96 — millimetres against
#: millimetres; and its test, `apps/ire/tests/test_compose_container.py::test_w11_a_jars_wrap_label_is_read_on_its_front_
#: as_the_front_view_draws_it`, the projected label's centre `seen["x"] + seen["width"] / 2.0` :567 (1), 3 → 4 —
#: millimetres against millimetres. Not a finding; the register stays 7.
#: HIS ANSWER OF 2026-10-05, W9 — "LET THE COPY BOX GROW TO FIT; NO HOLD FOR UNDER 2 MM": 1215 → 1216, located to the line
#: — `apps/ire/compose_artwork.py::compose_format`, how many nodes the picture was drawn as, the count after it less the
#: count before `len(nodes) - pic_at` :337 (1), 26 → 27 — a count against a count, dimensionless (the instrument logs
#: where each check is counted; the box's growth, its tolerance and its states add none). Not a finding; the register
#: stays 7.
#: HIS ANSWER OF 2026-10-05, W10 — "A JAR'S BACK COPY GOES ON THE BACK OF ITS WRAP LABEL ... NEVER NOWHERE": 1216 → 1219,
#: located to the line — `apps/ire/compose_container.py::_wrap_back_ends`, the wrap label's two ends `float(wrap["x"]) +
#: float(wrap["width"])` :324 (1), and `compose_information_panels`, the next panel's place `float(zone["width"]) +
#: _bp.PANEL_GAP_MM` :388 (1), 96 → 98 — millimetres against millimetres; and its test,
#: `apps/ire/tests/test_compose_container.py::test_w10_…`, each end's width against the narrowest end used `z["width"]
#: >= bp.WRAP_END_MIN_MM` :594 (1), 4 → 5. Not a finding; the register stays 7.
#: HIS RULE 4 OF 2026-10-05 — "SMOOTH THE SILHOUETTE'S EDGE INTO CLEAN CURVES": 1219 → 1220, located to the line by the
#: instrument's own count log — its test, `apps/pipeline/tests/test_vqr2b_concept_analysis.py::HisRuleFourTests`, the
#: cleaned ring's points against the traced edge's `len(ring) < len(raw)` :2813 (1), 5 → 6 — a count against a count,
#: dimensionless; the tracer's `_clean_ring` adds none. Not a finding; the register stays 7.
#: HIS REVIEW OF 119, 2026-10-05, POINT 3 — "THE BACK PANEL MUST MATCH THE OTHER PANELS": 1220 → 1222, located to the line
#: by the per-file count at HEAD and in the tree: test_compose.py:284, the drawn back's fills measured against the back
#: panel's width and height — two comparisons, millimetres against millimetres, nothing found.
#: HIS REVIEW OF 119, 2026-10-05, POINT 2 — "THE BACK PANEL IS LAID OUT, NOT CRAMMED": 1222 → 1231, located to the line by
#: the instrument's own count log — the new `apps/dielines/exporters/label_layout.py` (0 → 3): the title's lines times
#: the leading `:187` and the size stepped down to the floor `:234`, `:238`, points against points; `compose.py` (29 → 32):
#: the side copy's free height under the copy moved to its side `:319` (1), `:320` (2), millimetres against
#: millimetres; and its tests `test_compose.py` (15 → 18): a span inside a panel's safe margin `:343`, `:344`, millimetres
#: against millimetres, and the moves said against the moves made `:364`, a count against a count. Not a finding; the
#: register stays 7.
#: HIS REVIEW OF 119, 2026-10-05, POINT 4 — "NOTHING INSIDE THE SAFE MARGIN": 1231 → 1234, located to the line by the
#: instrument's own count log — its test, `test_compose.py::test_his_review_point_four_…`: the front's safe rectangle
#: `:478`, `:479` and the band still edge to edge `:499`, millimetres against millimetres; `compose.inside_safe` adds
#: none the instrument can type. Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, C8 — "A LINE THAT BREAKS DROPS ITS SEPARATOR": 1234 → 1237, located to the line by the
#: instrument's own count log — its test, `test_compose.py::test_his_final_goal_c8_…`: the two broken lines' distance
#: against the size they are set at `:568` (2, millimetres against points made millimetres by MM_PER_PT) and the one
#: line's runs on one baseline `:570` (1, millimetres). Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, A — "THE SAFE MARGIN RULE APPLIES TO CONTAINERS TOO": 1237 → 1251, located to the line
#: by the instrument's own count log — `test_2b3v_corr4_geometry.py`: the mark's top now read at the zone's margin
#: `:394` (3 where its old line read 2, millimetres); its test, `test_his_final_goal_a_a_…`: the shape and the
#: descriptor across inside the margin `:1238` (5) and down inside it `:1240` (5), the band still edge to edge `:1242`
#: (3), millimetres against millimetres; `compose.inside_safe` and `compose_container` add none the instrument can type.
#: Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, C5 — "THE INFO IS ONE DESIGNED BLOCK": 1251 → 1250, located to the line by the
#: instrument's own count log — `label_layout.py` 3 → 6: the steps' body and fine sizes against their floors `:376`,
#: `:378`, `:379`, `:380`, `:382` and the title's lines in its own lead `:411` (points), where one size's loop and the
#: title in the one lead stood (`:194`, `:241`, `:245`); `compose.py` 32 → 27: the side's height under a moved block
#: (`:326`, `:327` ×2) and the back's size loop (`:399`, `:401`) gone with the moves; `test_compose.py` 24 → 25: the
#: sticker's radius in millimetres `:385` and the side copy centred in its side `:496`, where the moved blocks' said
#: count stood `:364`. Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, B1 — "INSIDE AND TOP PRINTING": 1250 → 1254, located to the line by the instrument's
#: own count log — `test_compose.py` 25 → 29, its test `test_his_final_goal_b1_the_lid_mark_reads_from_the_front`:
#: the turned mark's centre on the lid's `:753` (2) and its width and height `:754`, `:755` (millimetres); the inside's
#: share of the page and the wiring check's are ratios the instrument cannot type (written so: a page's area and a
#: drawing's, both points, read as mm² against pt², stood as two false findings). Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, C5b — THE STOP'S THREE OFFERS: 1254 → 1259, located to the line by the instrument's own
#: count log — `compose.py` 27 → 31: a panel against the glue strip `:425` (millimetres), the inside's panels against
#: the languages `:427` (a count) and the back's width and height taken `:541` (2, millimetres);
#: `test_dimension_gate_structure.py` 0 → 1: the wider offer's width against the record's `:309` (millimetres). Not a
#: finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, B3 — THE BACK INFO, A STICKER, PRINTED OR HIS OWN: 1259 → 1261, located to the line by
#: the instrument's own count log — `back_info.py` 0 → 1: a double border's width added to the pad `:120`
#: (millimetres); `test_compose.py` 29 → 30: the default sticker's radius `:857` (millimetres). Not a finding; the
#: register stays 7.
#: HIS FINAL GOAL, 2026-10-05, A2 — CONTAINER BACK LABELS TRILINGUAL: 1261 → 1264, located to the line by the
#: instrument's own count log — `back_panel.py` 10 → 13: the fine print's size chosen `:305`, its lowest `:461` (his 5 pt
#: fallback against a method's floor), its step `:463` and the layout laid at it `:465` (points), where the one size every
#: run took stood `:458`. Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, B2 — A PRINT-READY DIELINE: 1264 → 1270, located to the line by the instrument's own
#: count log — `test_geometry.py` 1 → 3: 1.3's creases and slits counted against 1.2's `:333` and the thumb notch at
#: the front's middle `:336` (millimetres); `test_compose.py` 30 → 34: the drawn creases `:905` and cuts `:907` counted
#: against the die's folds and slits, the production PDF's `:932` (2) (counts). Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, C7 — THE SYSTEM CHECKS ITS OWN WORK: 1270 → 1278, located to the line by the
#: instrument's own count log — `self_check.py` 0 → 8: two lines on one baseline `:504`, `:506` (millimetres) and a
#: line's box against its panel's safe margin `:539` (3), `:540` (3) (millimetres). Not a finding; the register stays 7.
#: HIS FINAL GOAL, 2026-10-05, B4 — NO PROMPT STEP: 1278 → 1279, located to the line by the instrument's own count log —
#: `gate1_prompts.py` 1 → 2: the prompts counted against the planned directions `:226` (a count). Not a finding; the
#: register stays 7.
#: HIS FINAL GOAL, 2026-10-05, C7b — A CONTAINER'S BACK PANEL READ WITH ITS OWN MARGIN: 1279 → 1277, located to the line
#: by the instrument's own count log — `self_check.py` 8 → 6: the safe-margin test `:540`, `:541` now reads the
#: region's own margin (a value from its record, which the instrument cannot type: 3 + 3 checks become 1 + 1) and the
#: overrun measured `:542`, `:543` (millimetres). Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-06, ITEMS 10–12 — THE CARTON'S FLAPS, SIDES AND TITLE: 1277 → 1297, located to the line by the
#: instrument's own count log — `compose.py` 31 → 44: the side's graphic box `:481`, its raster mark `:496`, its copy's
#: size `:504`, the name's run `:507` (2) and foot `:509`, the name and the copy set along it `:538`, `:554`, the record
#: `:560` (millimetres and points); `test_compose.py` 34 → 36: the copy centred in the name's column `:509` (3, one
#: check gone `:497`); `test_wiring_check.py` 3 → 8: a dot of the invented pattern `:1242` (2), `:1243` (2) and a side's
#: name at a real size `:1284` (millimetres, points). Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-06, ITEM 11 — THE SIDES CARRY THE FRONT'S OWN LETTERING: 1297 → 1298, located to the line by the
#: instrument's own count log — `test_vqr2b_concept_analysis.py` 6 → 7: the side's column the lettering stands in `:2780`
#: (millimetres). Not a finding; the register stays 7.
#: HIS SECOND GOAL OF 2026-10-06, ITEM 1 — ALL LABEL INFORMATION ON THE BACK STICKER: 1298 → 1302, located to the line by
#: the instrument's own count log — `back_panel.py` 13 → 15: the narrower face's trial layout `:513` and its fine-print
#: step `:519`; `compose.py` 44 → 43: the inside label's glued-panel test `:647` and its column count `:649` gone with it,
#: the back tried wider `:640`; `test_compose.py` 36 → 37: the widened carton's width `:842`;
#: `test_dimension_gate_structure.py` 1 → 3: the inside offer's check `:309` gone, the widened width confirmed `:315`, on
#: the job `:319` and kept when drawn again `:329`. Not a finding; the register stays 7.
#: HIS SECOND GOAL OF 2026-10-06, ITEM 2 — TOP-TIER DIELINES: 1302 → 1323, located to the line by the instrument's own
#: count log — two new modules: `geometry/trade_tuck.py` 0 → 14 (the creases at inside + t `:99` (3), the dust flap's
#: depth `:105` (3), the glue flap's clearance `:106`–`:111` (3), the flap zone `:114`, the four crease x's `:117`–`:120`)
#: and `geometry/fold_check.py` 0 → 7 (the tube square `:86` (4), a panel's right edge `:91`, the glue flap in its panel's
#: height `:106`, the side walls' mean `:145`) — millimetres throughout. Not a finding; the register stays 7.
#: HIS SECOND GOAL OF 2026-10-06, ITEM 2 — THE PRODUCTION SHEET'S LEGEND IN ITS COLUMN: 1323 → 1325, located to the line
#: by the instrument's own count log — `test_trade_tuck.py` 0 → 2: the title block's divide found as the upright line
#: as tall as the block, 44 mm in points `:293` (2). Not a finding; the register stays 7.
#: HIS CORRECTION OF 2026-10-07 — A LABEL THAT DOES NOT FIT GETS SMALLER, EVENLY, TO 3 PT: 1325 → 1314, located to the
#: line by the instrument's own count log — `label_layout.py` 6 → 4 (the fine print's own steps `:453`, `:454`, `:456`
#: gone; `FINE_FLOOR_PT = FLOOR_PT` `:23` new); `back_panel.py` 15 → 14 (the fine-print and narrower-face steps `:496`,
#: `:498`, `:513`, `:519` gone; the whole label's shrink `:477`, `:517`, `:518` new); `compose.py` 43 → 42 (the widening's
#: width `:649` gone); `container_text_floor.py` 1 → 0 (`"below": size < floor` `:312` now reads a floor the analyser
#: cannot type, from `back_panel.label_floor_pt`); `test_compose.py` 37 → 36, `test_wik_back_panel_floor.py` 10 → 8 and
#: `test_dimension_gate_structure.py` 3 → 0 (the widening's and the held-up height's assertions gone). Not a finding; the
#: register stays 7.
#: HIS CORRECTION OF 2026-10-07, DESIGN 120 — A MOTIF HIS BRIEF ASKS FOR MAY STAND IN ALL THREE DIRECTIONS: 1314 → 1315,
#: located to the line by the instrument's own count log — `direction_signature.py` 1 → 2: the three ideas compared,
#: `len(set(axes)) < len(axes)` `:687` (1). Not a finding; the register stays 7.
#: HIS GO OF 2026-10-08 — LINE ART AND FRAMES IN ANY COLOUR, SMALL TEXT SET, 122 MADE DRAWABLE: 1315 → 1317, located to the
#: line by the instrument's own count log — `compose_container.py` 98 → 100: a map-set line no wider than the zone's safe
#: area `bw = min(bw, safe_width_mm * MAP_TYPE_SAFE_FILL)` `:2363` (millimetres), a name set as lettering kept at its
#: largest line's size `:2413` (points). Not a finding; the register stays 7.
#: HIS TEST BLOCKER ON DESIGN 122 AT THE SHAPE STEP — A PROPOSED AREA HELD INSIDE ITS SURFACE, THE BACK GROWN WITH THE
#: FRONT: 1317 → 1331, located to the line by the instrument's own count log — `container_contract.py` 23 → 35: the area
#: holding the back's own proposal and the front's extent, its corner `:1169` (2) and far edges `:1170` (3), `:1171` (3),
#: and how far an area runs past its surface `:1225` (2), `:1226` (2); `test_container_contract.py` 0 → 2: 122's front on
#: its face `:416` (2) — millimetres throughout. Not a finding; the register stays 7.
#: HIS TEST BLOCKER ON DESIGN 122 AT RECONSTRUCTION — THE NAME AT THE SIZE THE CONCEPT SHOWS: 1331 → 1334, located to the
#: line by the instrument's own count log — `compose_container.py` 100 → 101: a line taken for the name where its words
#: are the first of the name's, two at least or the whole name `:2317` (word counts); `test_container_fidelity.py`
#: 0 → 1: a name run at the size a test sets `:206` (points); `test_vqr2b_concept_analysis.py` 7 → 8: 149's name above
#: the print floor `:565` (points). Not a finding; the register stays 7.
#: HIS TEST FINDING ON DESIGN 122'S DRAWING, C — THE BACK LABEL USING ITS WHOLE AREA: 1334 → 1340, located to the line by
#: the instrument's own count log — `back_panel.py` 14 → 17: the column the copy is wrapped to, at a share of the zone's
#: `:356` (where `:315` was), grown while it stands `:590`, `:594`, the size it grew from `:600` (points and millimetres,
#: each to its own); `test_back_panel.py` 7 → 9: 122's last line near its foot `:686` (2); `test_wiring_check.py` 8 → 9:
#: 149's back grown `:2224`. Not a finding; the register stays 7.
#: HIS TEST BLOCKER ON DESIGN 123, (2) — NO "NOT DISTINCT" CHECK STOPS A DESIGN: 1340 → 1341, located to the line by the
#: instrument's own count log — `design_intent.py` 0 → 1: the directions sharing an idea, layout or colours word for word
#: `:314` (counts). Not a finding; the register stays 7.
#: HIS SECOND TEST BLOCKER ON DESIGN 123 — GARDEN WRAP DRAWN AS THE PICTURE PRINTS IT: 1341 → 1342, located to the line by
#: the instrument's own count log — `compose_container.py` 101 → 102: a name over several lines set at one size, each
#: line's width held to the safe area's `:2434` (millimetres). Not a finding; the register stays 7.
#: HIS SECOND TEST BLOCKER ON DESIGN 123, (4) AND (2) — 122'S ROSE IN THE BLOOM; THE ONE CHECK MEASURES WHERE IT DRAWS:
#: 1342 → 1355, located to the line by the instrument's own count log — `compose_container.py` 102 → 106: the bloom's
#: place in millimetres `:2980` (2), the rose as large as its place holds `:2981` (2); `packaging.py` 0 → 1: where two
#: glyphs of drawn copy meet, in millimetres `:200`; `test_compose.py` 36 → 44: the rose's own proportions `:1397` (2),
#: the part's box `:1404` (2), the rose's size at its bloom `:1405` (4). Not a finding; the register stays 7.
#: HIS TEST FINDINGS ON DESIGN 123, (2) — A PANEL WITH NOTHING FROM A PICTURE CONTINUES THE FRONT: 1355 → 1364, located to
#: the line by the instrument's own count log — `compose.py` 42 → 47: the back's own edge against its side's, to chain
#: the folds `:492` (2), the side's name at half the front's size, never under the real size `:670` (3);
#: `test_compose.py` 44 → 47: the field run to the side's fold `:1502`, the side's name against the front's `:1512` (2);
#: `test_wiring_check.py` 9 → 10: the field's clip no wider than its side `:1579`. Not a finding; the register stays 7.
#: HIS TEST FINDINGS ON DESIGN 123, (1) — EVERY PANEL ITS LAYOUT PICTURE GIVES DRAWN FROM IT: 1364 → 1367, located to the
#: line by the instrument's own count log — `compose.py` 47 → 48: a panel clipped between the body's folds `:258`;
#: `carton_layout.py` 0 → 2: the front's own parts carried, counted against the panel's `:348` (2). Not a finding; the
#: register stays 7.
#: HIS GOAL OF 2026-10-10, ITEM 1 — NO PLANNER OR CONCEPT CHECK EVER STOPS A DESIGN: 1367 → 1368, located to the line by
#: the instrument's own count log — `aria.py` 0 → 1: the prompts counted against the directions, to bind them by their
#: order `:620`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-10, ITEM 2 — A PALETTE IS ITS LID AND ITS OPEN TRAY: 1368 -> 1389, located to the line by the
#: instrument's own count log — `palette_tray.py` 0 -> 9: the insert inside the case's wall `:141` (2), every pan the
#: largest the insert holds, its name's band in millimetres `:149` (2), the grid's width `:151` and height `:152` (2),
#: centred `:153` (2); `test_compose_container.py` 5 -> 17: each name centred under its own pan `:694` (2), under it
#: `:695`, no wider than it `:696`, every pan one size `:697`, the frame inside the insert `:702` (3), `:703` (3), the
#: sheet grown to hold it `:704`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-10, ITEMS 5 AND 9 — ONE SCALLOP ROUND THE CARTON; THE GARDEN MOVED, NEVER MIRRORED: 1389 -> 1409,
#: located to the line by the instrument's own count log — `compose.py` 48 -> 53: the back's fold-chain check gone with
#: the mirror `:521` (-2), each panel's shift from the front `:568` (3) `:570`, a band's edge read bin by bin `:648`, the
#: front's band to its own fold `:720` (2); `test_compose.py` 47 -> 58: the row `:1682`, a whole number of arcs round it
#: `:1686`, their widths `:1688` alike `:1689`, their heights alike `:1690`, each panel's clip inside it `:1699`, the
#: garden's shift `:1719` where it ends `:1720` (4); `test_wiring_check.py` 10 -> 14: the carton's round `:1849` (2), the
#: scallop round it `:1851`, its arcs alike `:1859`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-10, ITEM 6 — THE FRONT IN ITS OWN SANS, ONE COLOUR, SOFT ROOM: 1409 -> 1410, located to the line
#: by the instrument's own count log — `compose_container.py` 106 -> 107: the name's lines' read inks counted against
#: its lines `:2517`; the type runs' sizes `:2630`, `:2663` for the two gone at `:2569`, `:2599`. Not a finding; the
#: register stays 7.
#: HIS GOAL OF 2026-10-10, ITEM 2 — THE TRAY PASSES GATE 2, ITS NAMES NEVER UNDER THE FLOOR: 1410 -> 1415, located to
#: the line by the instrument's own count log — `palette_tray.py` 9 -> 10: the names' floor named as the print floor's
#: own `:47`; `test_compose_container.py` 17 -> 21: the floor and the size set at it `:742` (2), the long name's two
#: lines `:746`, each no wider than its pan `:752`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-10, ITEM 10 (WITH ITEM 5'S CURLED BAND) — THE INSIDE HIS REFERENCE PAINTS: 1415 -> 1416, located
#: to the line by the instrument's own count log — `test_compose.py` 58 -> 59: a traced band's arcs never flatter than
#: their least rise `:2041`. Not a finding; the register stays 7.
#: HIS TEST BLOCKER ON DESIGN 124, ITEMS 2 TO 5 — A COMPACT'S LID DRAWN FROM ITS MAP AND ITS ART: 1416 -> 1418, located to
#: the line by the instrument's own count log — `test_compose_container.py` 21 -> 23: the lid's traced regions each
#: drawn `:853`, its sky's bands each drawn `:854`. Not a finding; the register stays 7.
#: HIS BUG ON DESIGN 124 — THE LAYERED ILLUSTRATOR FILE CARRIES WHAT THE DRAWING DRAWS: 1418 -> 1420, located to the
#: line by the instrument's own count log — `native_ai.py` 0 -> 2: a pattern's rings stepped out to its reach `:155`, a
#: QR's side in points `:267`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-12, ITEM 5 — THE ℮ AT LEAST 3 MM TALL WHEREVER IT PRINTS: 1420 -> 1421, located to the line by the
#: instrument's own count log — `test_compose.py` 59 -> 60: the drawn sign's height against its 3 mm floor `:2483`. Not
#: a finding; the register stays 7.
#: HIS GOAL OF 2026-10-12, ITEMS 7 AND 8 — A LID AS THE CONCEPT SHOWS IT: 1421 -> 1426, located to the line by the
#: instrument's own count log — `compose_container.py` 107 -> 110: the capitals' size from their height `:2563`, the
#: line's top in its box `:2660`, `:2666`; `test_compose.py` 60 -> 62: the capitals' height against the picture's
#: `:2549`, the glow's bands each drawn `:2602`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-12, ITEMS 9 TO 13 — EVERY PALETTE'S TRAY AS ITS PICTURE PRINTS IT: 1426 -> 1430, located to the
#: line by the instrument's own count log — `test_compose.py` 62 -> 66: the lid's inside and the insert drawn their height
#: and a hinge apart `:2775` (two), the insert's ground a lid and a hinge below its top `:2777` (two). Not a finding; the
#: register stays 7.
#: HIS GOAL OF 2026-10-12, ITEM 14 — EVERY PALETTE'S AND COMPACT'S BACK LAID OUT AS PACKAGING: 1430 -> 1444, located to
#: the line by the instrument's own count log — `back_panel.py` 17 -> 27: a column's width from the panel's `:507` (two),
#: against its floor `:508`, the size stepped down to the label's floor `:529` and up to its ceiling `:534`, each
#: column's place `:545` (three), the packed layout handed its size and floor `:672` and its size taken `:677`;
#: `test_compose.py` 66 -> 70: the size within its ceiling `:2811`, each column to the panel's foot `:2817`, each column
#: at its place `:2818` (two). Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-13, ITEM 11 — A TEST RUN DRAWS ONE CONCEPT OF THE THREE PLANNED: 1444 -> 1445, located to the line
#: by the instrument's own count log — `aria.py` 1 -> 2: fewer concepts drawn than planned, said `:677`. Not a finding;
#: the register stays 7.
#: HIS GOAL OF 2026-10-13, ITEM 2 — A PALETTE OR COMPACT LIES FLAT: 1445 -> 1446, located to the line by the instrument's
#: own count log — `test_compose.py` 70 -> 71: the label laid out wide, as seen, on a box lying flat `:3240`. Not a
#: finding; the register stays 7.
#: HIS GOAL OF 2026-10-13, ITEMS 3-6 — A CALM PAGE: 1446 -> 1450, located to the line by the instrument's own count log —
#: `views_of.py` 0 -> 3: a line of type's width measured, at least its size `:44`, and its left edge by its alignment
#: `:45` (two); `test_browser_recon_result.py` 0 -> 1: no new tab and no browser dialog `:517`. Not a finding; the register
#: stays 7.
#: HIS GOAL OF 2026-10-13, ITEMS 7-9 — GEOMETRY DRAWN, GLOWS AND GRADIENTS SMOOTH: 1450 -> 1452, located to the line by
#: the instrument's own count log — `line_geometry.py` 0 -> 2: the longer leg drawn on both sides `:253`, a curve's bins
#: nine in ten held `:339`; `test_compose.py` 71 -> 72: its log names two new lines — the arch's stroke its own width `:3303`,
#: the dashes left out of the trace `:3556` — net one with the draft's own lines rewritten; `test_compose_container.py`
#: 23 -> 22: the lid's sky counted band by band, one band a row of its field, is one smooth mesh now (its count gone).
#: Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-13, ITEMS 7-10 — THE DRAWING AND THE LAYERED FILE AGREE: 1452 -> 1469, located to the line by the
#: instrument's own count log — `graph.py` 0 -> 1: a mesh's alphas four for each of its patches `:214`; `test_compose.py`
#: 72 -> 88: its log names the new lines — a glow's alphas one for each patch `:3631`, a re-laid arch's width `:3669`, and
#: the layered file's gradient read against Illustrator's measured run, its box `:3781`-`:3783`, its sample points
#: `:3787`, its turned span `:3794` and a point's place on it `:3795`. Not a finding; the register stays 7.
#: HIS GOAL OF 2026-10-13, ITEMS 1, 3, 4, 7-10 — THE WIRING CHECK'S NEW DETECTORS: 1469 -> 1470, located to the line by the
#: instrument's own count log — `test_compose.py` 88 -> 89: the trace's glow pieces left out, as many as it says `:3456`.
#: Not a finding; the register stays 7.
#: HIS GOAL FOR THE PITCH, 2026-10-15, B (10) — 124'S ARCH ONE BRIGHT GOLD LINE: 1470 -> 1469, the gilded line's separate
#: bright-core stroke (its own floor width) left the lid's art — `lid_art.py` one check fewer. Not a finding; the register
#: stays 7.
#: HIS GOAL AFTER THE PITCH PAGE, 2026-10-15, A (2) AND A (3) — SHAPES AND PROPORTIONS FROM THE CONCEPT: 1469 -> 1473,
#: located to the line by the instrument's own count — `targets/container/__init__.py` 6 -> 10: a size the form's own
#: starting size in millimetres, its width and its height each against `NOMINAL_MATCH_MM` (`concept_proportion_size`,
#: four). Not a finding; the register stays 7.
#: HIS GOAL AFTER THE PITCH PAGE, 2026-10-15, A (4) AND A (5) — EVERY ELEMENT DRAWN, EVERY MARK AND LINE READABLE: 1469 ->
#: 1471, located by file with the instrument's own count — `legibility.py` 0 -> 1 (a line of type's band, its size in
#: millimetres beside its set width); `test_compose.py` 88 -> 89 (the traced frame's box against its drawn pixels). Not a
#: finding; the register stays 7.
#: HIS GOAL AFTER THE PITCH PAGE, 2026-10-15, A (1) AND A (6) — EACH LINE IN ITS CONCEPT'S FACE, HELD INSIDE ITS FRAME:
#: the three above together 1469 -> 1475, then -> 1472, located by file with the instrument's own count —
#: `lettering_faces.py` 0 -> 1 (a line's size in millimetres beside its drawn width); `compose_container.py` 110 -> 106:
#: the front's lines measured in their own faces (``measure_mm``, ``line_width_mm``), where four comparisons read the
#: Latin estimate the instrument types — the name's lines against their width, the capitals' natural width, the one
#: size's division, the line's width at one point. Not a finding; the register stays 7.
#: HIS REVIEW OF 127, 130, 131 AND 132, 2026-10-15, C (1) — THE PATTERN WRAPS THE WHOLE PACK: 1472 -> 1476, located by
#: file with the instrument's own count — `compose.py` 53 -> 57: a further copy of the front's field laid only where it
#: reaches TILE_REACH_MM onto its panel, across `:775` (two), and up or down onto a flap `:894` (two). Not a finding; the
#: register stays 7.
#: HIS REVIEW OF 127, 130, 131 AND 132, 2026-10-15, C (4) — A REDRAW'S OWN LETTERING NEVER PRINTED UNDER THE LIVE WORDS:
#: 1476 -> 1479, located by file with the instrument's own count — `lid_art.py` 0 -> 3 (``without_words``: a box of type
#: padded by a share of its own height, and a traced shape's box against it on both axes). Not a finding; the register
#: stays 7.
#: HIS REVIEW OF 127, 130, 131 AND 132, 2026-10-15, C (7) — NEVER AN EMPTY LABEL: 1479 -> 1480, located by file with the
#: instrument's own count — `test_container_target.py` 3 -> 4 (the smallest back, 15 × 25 mm, given the type's whole
#: standard copy, its panel against its zone). Not a finding; the register stays 7.
#: HIS GOAL AFTER THE PITCH PAGE, 2026-10-15, B (10) — 140'S CARTON: ONE FIELD DRAWN ONCE, ITS MOTIF OVER IT, ITS FILE
#: DRAWN FOR THE SIZE IT PRINTS AT, ITS NAME WHOLE ON THE SIDES: 1480 -> 1486, located by file with the instrument's own
#: count — `inside_print.py` 0 -> 1 (``drawn_at``: a ring's box at the size it prints against the self-check's speck);
#: `targets/container/__init__.py` 10 -> 11 (``one_field_once``: a field's box against ROUND_FIELD_SHARE);
#: `test_compose.py` 89 -> 93 (the repeated motif's ring against its tolerance, and the side's name against its safe
#: frame on both axes). Not a finding; the register stays 7.
#: HIS LAST GOAL BEFORE THE PITCH, 2026-10-16, STEP 2 — EACH DESIGN AGAINST ITS CONCEPT: 1486 -> 1493, located by file
#: with the instrument's own count — `compose_container.py` 106 -> 111 (the line held inside the product's outline, three;
#: the mark no wider than the picture's, two); `test_compose_container.py` 22 -> 24 (the parting line's width, and the
#: level line at the cap's foot). Not a finding; the register stays 7.
#: HIS FIXES TO 142 (CHERRY KISS), 2026-10-17, (1) — A VERTICAL SCRIPT NAME SET VERTICALLY, WHOLE AND INSIDE THE PANEL:
#: 1493 -> 1512, located by file with the instrument's own count — `compose_container.py` 111 -> 126 (a line set on end:
#: its size from its box's width and length, its baseline and its ink placed across its box, its length centred down
#: it, its ink box against the front — fifteen); `compose_dropper.py` 20 -> 23 (a run set on end held against the
#: zone's height and its safe height — three); `test_wiring_check.py` 14 -> 15 (the ℮ against its line's capitals,
#: his word of the same day on it). Not a finding; the register stays 7.
# Rescue: historical coverage floor, not a per-edit census. Report the measured denominator below.
TREE_CHECKS = 1512
CERTAIN_FINDINGS = 3   # 3 -> 4 at Day 6: day6_surface_fidelity.py:482 needs no coefficient assumption; 4 -> 3 on
#: 2026-10-29 (the owner's message, the four checks re-pinned): that file left apps/ with the Day 4–6 masters, and the
#: face builder's band-size line that took its place in the count is an ASSUMED finding


@pytest.fixture(scope="module")
def tree():
    """The whole of `apps/`, LESS this file.

    This test lives inside `apps/`, so the census counts its own source and
    the denominator moves whenever the test is edited — the first run came
    back 818 because `height_mm = width_mm * 110.0 / 40.0` in the crossover
    test is itself a dimension comparison. Subtracting it visibly is the
    honest fix: an instrument should not be part of its own measurement, and
    hiding the overlap by writing 818 down would have made the number look
    stable while quietly measuring something else.
    """
    findings, checks = ua.census(APPS)
    mine = ua.UnitAnalyser(__file__, pathlib.Path(__file__).read_text())
    assert mine.run() == []          # and it had better not be a FINDING
    assert mine.checks == 1
    return findings, checks - mine.checks


class TestTheRegisterIsAMeasurementAndNotAnImpression:
    def test_every_finding_in_the_repo_has_been_classified(self, tree):
        findings, _ = tree
        assert {f.key for f in findings} == set(REGISTER), (
            "the repo's dimensional findings no longer match the classified "
            "register. A NEW key is a finding nobody has read yet; a MISSING "
            "key is either a repair (delete it here, in the commit that "
            "repaired it) or an instrument that stopped seeing.")

    def test_the_denominator_is_stated_beside_the_numerator(self, tree, record_testsuite_property):
        findings, checks = tree
        # 7 -> 8 at Day 6 (day6_surface_fidelity.py:482, classified above); still 8 on 2026-10-29: that file left with the
        # Day 4–6 masters, and the face builder's band-size line, never classified before, is classified above
        assert len(findings) == len(REGISTER) == 8
        record_testsuite_property("unit_analysis_findings", len(findings))
        record_testsuite_property("unit_analysis_checks", checks)
        assert checks >= TREE_CHECKS, "Dimensional analysis coverage fell below the historical floor"

    def test_how_much_of_the_register_rests_on_the_coefficient_assumption(
            self, tree):
        """The assumption is what made the analyser able to see real code at
        all (see `unit_analysis`'s docstring). Its cost is a number: four of
        the seven findings would not exist without it."""
        findings, _ = tree
        assert len(ua.certain(findings)) == CERTAIN_FINDINGS
        assert len(ua.assumed(findings)) == len(findings) - CERTAIN_FINDINGS

    def test_two_findings_are_true_and_neither_is_repaired_here(self, tree):
        """§AB4(c): WI-T is the sprint's ONLY chained fix, and it is the
        container front. These two are live defects in other files and they
        stay recorded and unrepaired, on the record, with a line number."""
        findings, _ = tree
        true = {f.key for f in findings if REGISTER[f.key] == TRUE_FINDING}
        assert true == {("visual_quality_program.py", 271, ua.MIXED),
                        ("info_panel.py", 374, ua.MIXED)}

    def test_the_three_false_positives_share_one_declared_cause(self, tree):
        """Not a mystery and not three separate bugs: `MM_ATTRIBUTES` declares
        `.width`/`.height` to be millimetres, and these three files hold
        PIXELS under those names. Left declared-and-wrong rather than patched
        with an owner heuristic, because tuning an instrument until its own
        register looks clean is what this sprint is about."""
        findings, _ = tree
        false = {f.key[0] for f in findings
                 if REGISTER[f.key] == FALSE_POSITIVE_PIXELS}
        # three -> four at Day 6: day6_surface_fidelity.py holds POINTS (a fitz Rect) under the same declared-mm names;
        # four -> three on 2026-10-29 (the owner's message, the four checks re-pinned): that file left with the Day 4–6 masters
        assert false == {"info_panel.py", "vq1_close1_package.py", "palt_m4b_a_evidence.py"}
        assert "height" in ua.MM_ATTRIBUTES and "width" in ua.MM_ATTRIBUTES

    def test_the_one_coefficient_false_positive_is_the_assumptions_declared_cost(self, tree):
        """The face builder's band-size line (classified 2026-10-29): a points-per-millimetre constant the analyser does
        not list, read as a coefficient. It rests on the assumption — never certain — and it is the only one."""
        findings, _ = tree
        coefficient = [f for f in findings if REGISTER[f.key] == FALSE_POSITIVE_COEFFICIENT]
        assert {f.key[0] for f in coefficient} == {"round_files_faces.py"}
        assert not any(f.certain for f in coefficient)
        assert "PT" not in ua.NAMED_CONSTANTS

    def test_it_independently_flagged_wij_s_own_defective_fixtures(self, tree):
        """Cross-validation against an instrument built for the same rule by a
        different route. WI-J hand-wrote a defective producer and a chosen-as-
        type counterpart; this analyser, which knows nothing about WI-J,
        flags the two defective ones and not the clean one."""
        findings, _ = tree
        wij = {f.key for f in findings
               if f.key[0] == "test_wij_type_size_units.py"}
        assert wij == {("test_wij_type_size_units.py", 124, ua.PT_FROM_MM),
                       ("test_wij_type_size_units.py", 153, ua.PT_FROM_MM)}


#: WI-3E. A source with exactly ONE finding and ONE check, held as a STRING so
#: it contributes nothing to this file's own census — the `tree` fixture
#: asserts `mine.checks == 1`, and a real `width_mm + size_pt` written here
#: would make that 2 and take the register's denominator with it. The analyser
#: sees `ast.Constant`, which has no dimension, so this is invisible to it.
IDEMPOTENCE_SUBJECT = '''
def f(width_mm, size_pt):
    total = width_mm + size_pt
    return total
'''


class TestRunIsIdempotent:
    """WI-3E — the defect §AC recorded at WI-Y and declined to repair.

    `run()` re-walked the tree and APPENDED to `self.findings` and
    `self.checks` without resetting them, so calling it twice on one instance
    returned two findings where there is one and left `checks` at two where it
    is one. Recorded then as *"latent, not live"*, which was true: `census()`
    constructs one analyser per file and calls `run()` exactly once, and the
    `tree` fixture does the same. §AC forbade chained fixes and named exactly
    one exception, which was not this, so it was written down and left.

    §AE1 hands it back to the executor by name. This class is the red that came
    first, and it was watched failing before a line of `run()` changed:

        call 1: findings=1 checks=1
        call 2: findings=2 checks=2
        call 3: findings=3 checks=3

    WHY IT WAS WORTH FIXING RATHER THAN DOCUMENTING AGAIN. The duplicate
    findings carry an IDENTICAL key — `('<path>', 3, 'MIXED')` three times over
    — and `test_every_finding_in_the_repo_has_been_classified` compares
    `{f.key for f in findings}`, a SET. So the corruption is **invisible** to
    the test that reads like the thorough one and visible only to
    `len(findings) == len(REGISTER) == 7`, which reads like a formality. The
    two are not redundant, and which of them is load-bearing is the opposite of
    what their names suggest.
    """

    def _analyser(self):
        return ua.UnitAnalyser("<idempotence>", IDEMPOTENCE_SUBJECT)

    def test_the_subject_has_exactly_one_finding_and_one_check(self):
        """The premise, measured, before anything is asserted about repeating
        it. §AD0(a): a prediction about a count is not a measurement of it, and
        every number in this class is relative to these two."""
        a = self._analyser()
        assert len(a.run()) == 1
        assert a.checks == 1

    def test_calling_run_twice_returns_what_calling_it_once_returned(self):
        """THE DEFECT. Red before the fix at `findings=2`, green after."""
        a = self._analyser()
        first = list(a.run())
        second = list(a.run())
        assert second == first, (
            "run() is not idempotent: a second call appended to the findings "
            "of the first. Both halves of this instrument's register scale "
            "with how many times somebody asked.")

    def test_the_denominator_does_not_scale_with_the_number_of_calls(self):
        """The half that would corrupt `TREE_CHECKS` rather than `REGISTER`,
        asserted separately because they are separate accumulators and a fix
        that reset one and forgot the other would pass the test above."""
        a = self._analyser()
        a.run()
        assert a.checks == 1
        a.run()
        assert a.checks == 1
        a.run()
        assert a.checks == 1

    def test_three_calls_agree_with_three_fresh_instances(self):
        """The property stated positively: `run()` is a function of the source
        and nothing else. A fresh analyser per call is what `census()` does and
        is therefore the definition of correct here — so the repaired instance
        must agree with it, not merely with itself.
        """
        repeated = self._analyser()
        for _ in range(3):
            got = repeated.run()
            fresh = self._analyser()
            assert [f.key for f in got] == [f.key for f in fresh.run()]
            assert repeated.checks == fresh.checks

    def test_the_census_path_was_never_affected_and_still_is_not(self):
        """§AA in the other direction — the recorded claim that the defect was
        *"latent, not live"* was never asserted, only stated. If it had been
        wrong, every number this module has ever reported would have been
        wrong too. Asserted now, once, so the historical claim is on the
        record as checked rather than as believed.
        """
        one = ua.analyse_source(IDEMPOTENCE_SUBJECT, "<idempotence>")
        two = ua.analyse_source(IDEMPOTENCE_SUBJECT, "<idempotence>")
        assert [f.key for f in one] == [f.key for f in two] == [
            ("<idempotence>", 3, "MIXED")]
