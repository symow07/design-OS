"""§Z1(b) backwards — a MILLIMETRE offset derived from a POINT size.

WI-J fixed a point size derived from a millimetre length. The line directly
underneath it carried the same law running backwards::

    leading = name_size * 1.06        # mm offset, pt input, no conversion

and the backwards direction is the more expensive one, because nothing about
the result looks wrong. `1.06` reads as an em ratio — tight leading, which is
exactly what the comment beside it claimed. Applied to a point size and added
to a millimetre coordinate it is a ratio of mm-per-pt, and the leading it
actually set was `1.06 / (25.4/72)` = 3.0047 em: three times the type size,
in a block whose own comment SAID "two serif lines with tight leading".

Past tense as of WI-V: §AB3(c) ruled that comment a false statement that does
not wait for a design decision, and it is gone. This paragraph is left
standing because it is the record of what the defect looked like, and a
sentence describing a repaired comment in the present tense would become the
next false statement — which is the failure mode this whole file is about.

WI-J's reason for not grepping holds here and is stronger. `compose.py` and
`compose_vector_art.py` convert correctly through 72/25.4, and this repo has a
live example of the false positive one line-length away: `compose_vector_art`
:581 reads `name_h * 1.06`, the same literal on the same kind of quantity —
but `name_h = front.height * 0.115` is millimetres already, so the expression
is correct and a search for `1.06` would condemn it. So this file measures
BEHAVIOUR, and the behaviour it measures is the dual of WI-J's:

    WI-J   perturb a MILLIMETRE input ->  every point size HOLDS STILL
    WI-P   perturb the MM-PER-POINT   ->  a millimetre offset MOVES

A millimetre offset genuinely derived from a point size passes through the
conversion constant, so it scales when that constant does. An unconverted one
never touches the constant and does not move — and not moving is the failure.
That separates the two cases without reading a character of source, and it
keeps separating them whatever em value the artwork settles on, which matters
because the em value here is not settled (below).

**The guard is exercised against a known-bad producer as well as the real
one** (`TestTheGuardCatchesTheDefectItWasWrittenFor`). The known-bad producer
is the pre-fix expression verbatim: `name_size * 1.06`.

WHAT THIS FIX CHANGED IN PRODUCTION OUTPUT: nothing.

That is not a hope, it is a measurement, and it is the reason `NAME_LEADING_EM`
is 3.0047244094488192 rather than the 1.06 the expression looked like it was
asking for. Setting 1.06 em would close the hero gap from 9.54 mm to 3.3655 mm
and the flat panel's from 6.89 mm to 2.4306 mm. That is a visible
re-proportioning of the front, which §AA2(d) forbids this sprint, and of
the name block, which §AA2(c) reserves to the owner. So the unit path
was corrected and the proportion was left exactly where it stood. Measured
three ways, all recorded in `OWNER_REVIEW_QUEUE.md` under WI-P:

  * the two producers place the two lines identically — 0 ULP apart at
    `name_min=6.5`, 3 ULP at 9.0, asserted below and permanent;
  * across the whole composed sheet, 1 of 187 nodes moved 1 coordinate, by
    1 ULP (2.842e-14 mm);
  * emitted through the real `emit_pdf_ai`, the artwork is byte-identical to
    HEAD once the emitter's own `/CreationDate`, `/ModDate` and `/ID` are
    masked — and the mask was validated by first checking that two runs of
    IDENTICAL code hash the same, which on the first attempt they did not.

That last control is why the byte claim is worth making. Before the `/ID` mask
was widened to allow the newline ReportLab writes after it, two runs of the
same code differed at 56 byte positions and HEAD-vs-fixed differed at 60; the
difference between those two numbers was the emitter's clock, not the artwork.

The byte comparison itself is NOT a test here, deliberately. It compares
against `git show HEAD:`, and once WI-P is committed HEAD becomes the fixed
version and the comparison passes vacuously forever. It lives in the queue as
a dated measurement with its method written down. What lives here instead is
the same claim in a form that cannot go stale: the defective producer is kept
in this file, and the fixed producer is required to agree with it.

WHAT THIS FIX DID NOT DO: it did not make the leading typographically tight.
3.0047 em is now written down as a named constant instead of hiding inside a
units bug, and that is the whole of the change in what anybody can see. The
number was always there. It is a design question with a measured price and it
is the owner's under §AA2(c); `TestTheEmRatioIsNowTheOwnersQuestion` pins
it so it cannot drift while it waits for a ruling.

Scope, stated so it is not overread: this measures ONE offset in ONE producer.
Nothing enforces the mm-from-pt direction repo-wide. That gap is WI-Q's and is
recorded in `OWNER_REVIEW_QUEUE.md`, not papered over here.
"""
import math

import pytest

from apps.ire import back_panel
from apps.ire.compose_dropper import (NAME_LEADING_EM,
                                      NAME_LEADING_INCUMBENT_EM,
                                      _front_typography)
from apps.ire.tests.test_wij_type_size_units import _GEOMETRY, _ZONE, _named   # §BH68(d): the name, handed in

#: the two `name_min` values the composed sheet actually draws: panel 5's hero
#: block and panel 8's flat reproduction of the same artwork.
HERO_NAME_MIN = 9.0
FLAT_NAME_MIN = 6.5

#: the pre-fix expression, kept verbatim as the falsifying producer.
DEFECT_FACTOR = 1.06

#: §AC1 — THE RULING THAT ARRIVED WHILE THIS FILE WAS WAITING FOR IT.
#:
#: The module docstring above says the em ratio "is a design question with a
#: measured price and it is the owner's under §AA2(c)". It was answered:
#: §AC1 ruled the METRIC floor binding, killed 1.06 em (the line boxes overlap
#: by 0.959 mm), and set the leading to 2.0 em.
#:
#: WHAT THAT DOES TO THIS FILE, and it is not "update the numbers". WI-P's
#: subject was the UNIT PATH and its deliverable was a zero-effect proof:
#: `mm = pt x MM_PER_PT x em`, with the em ratio left at whatever the artwork
#: already had. That proof is still exactly as valid and must not be softened,
#: so the zero-effect comparison below is re-pointed at the INCUMBENT — the
#: number WI-P preserved — rather than at whatever the composer is set to
#: today. WI-P proved the conversion was right; §AC1 then changed the ratio.
#: Conflating the two would make WI-P's proof vanish the moment anybody used
#: the freedom WI-P created.
AC1_SET_EM = 2.0


def _name_block(producer, name_min, mm_per_pt=None) -> dict:
    """``{node name: y}`` for the two name-block lines, in millimetres.

    ``mm_per_pt`` swaps the conversion constant for the duration of the call.
    The producer reads it as ``back_panel.MM_PER_PT`` — an attribute
    lookup on the module, resolved when the line runs — so a producer that
    converts sees the substitution and one that does not cannot.

    If someone later rewrites that lookup as a module-level
    ``from apps.ire.back_panel import MM_PER_PT``, this probe stops reaching
    the producer and the tests below FAIL. That is the intended direction of
    failure: loud, not silent.
    """
    original = back_panel.MM_PER_PT
    if mm_per_pt is not None:
        back_panel.MM_PER_PT = mm_per_pt
    try:
        children, _, _, _ = producer(dict(_GEOMETRY), dict(_ZONE), 158.0, 28.0,
                                     1.22, None, name_min=name_min, **_named(producer))
    finally:
        back_panel.MM_PER_PT = original
    return {str(n.name): float(n.y) for n in children
            if "product-name-hero" in str(n.name)}


def leading_mm(producer, name_min=HERO_NAME_MIN, mm_per_pt=None) -> float:
    """The millimetre offset between the two lines of the name block."""
    ys = _name_block(producer, name_min, mm_per_pt)
    return ys["product-name-hero-1"] - ys["product-name-hero-0"]


def offset_tracks_the_conversion(producer, name_min=HERO_NAME_MIN) -> dict:
    """Does the millimetre offset travel through the mm-per-point constant?

    This is the guard. Returns the two measurements and the ratio between
    them; the caller asserts the ratio. A converted offset scales with the
    constant, so the ratio is the factor the constant was scaled by. An
    unconverted one never reads the constant, so the ratio is 1.0.

    The tests below are four applications of it.
    """
    base = leading_mm(producer, name_min)
    doubled = leading_mm(producer, name_min,
                         mm_per_pt=back_panel.MM_PER_PT * 2.0)
    return {"mm_at_the_real_constant": base,
            "mm_at_twice_the_constant": doubled,
            "ratio": (doubled / base) if base else float("nan")}


class TestTheOffsetTravelsThroughTheConversion:
    """§Z1(b) backwards, as an observation of what the producer emits."""

    @pytest.mark.parametrize("name_min", [HERO_NAME_MIN, FLAT_NAME_MIN])
    def test_doubling_the_millimetres_in_a_point_doubles_the_offset(self,
                                                                    name_min):
        """The offset is a length. Redefine the point and the length moves.

        Not asserted exactly: 9.54 and 19.08 divide to 1.9999999999999984,
        because the offset is a product of three floats and doubling one of
        them is not associative. A tolerance is the honest form of this
        assertion and 1e-12 is eleven orders of magnitude tighter than the
        1.0 an unconverted offset returns.
        """
        seen = offset_tracks_the_conversion(_front_typography, name_min)
        assert seen["ratio"] == pytest.approx(2.0, abs=1e-12), seen

    def test_the_offset_is_a_millimetre_quantity_and_the_input_is_points(self):
        """The dependency the fix is about actually exists.

        A guard for "the offset tracks the type size" is worthless if the
        offset does not depend on the type size at all, so that is measured
        before anything else is concluded from it. 9.0 pt and 6.5 pt must give
        different offsets, and the larger type the larger offset.
        """
        hero = leading_mm(_front_typography, HERO_NAME_MIN)
        flat = leading_mm(_front_typography, FLAT_NAME_MIN)
        assert hero > flat > 0
        assert hero / flat == pytest.approx(HERO_NAME_MIN / FLAT_NAME_MIN,
                                            rel=1e-12)


class TestTheGuardCatchesTheDefectItWasWrittenFor:
    """The falsifying input, so this is a guard and not an intention.

    A test that only ever runs against corrected code proves the code and the
    guard are consistent; it does not prove the guard would notice. These
    supply the missing half from both sides — the pre-fix expression must be
    caught, and a correctly converted one must not be.
    """

    @staticmethod
    def _defective(g, zone, ox, oy, s, logo_path, prefix="", name_min=9.0):
        """The line as it stood before the fix, verbatim.

        Everything except the offset is copied from the real producer, so the
        only thing the guard can be reacting to is the missing conversion.
        """
        from apps.ire.graph import Color, TextRun

        ink = Color.from_hex("#5A2A3A")
        closure_h = (g["collar_height_mm"] + g["bulb_height_mm"]
                     + (g.get("visible_neck_mm") or 3.0))
        zy = oy + (closure_h + float(zone["y"])) * s
        zh = float(zone["height"]) * s
        name_size = name_min
        leading = name_size * DEFECT_FACTOR          # <- the defect
        block_top = zy + zh * 0.30
        return ([TextRun(name=f"{prefix}product-name-hero-0", text="Rose",
                         x=0.0, y=block_top, size_pt=name_size, color=ink),
                 TextRun(name=f"{prefix}product-name-hero-1", text="Damascena",
                         x=0.0, y=block_top + leading, size_pt=name_size,
                         color=ink)],
                [], "", (0.0, 0.0, 1.0, 1.0))

    @staticmethod
    def _converted(g, zone, ox, oy, s, logo_path, prefix="", name_min=9.0,
                   name_lines=None):
        """The same producer with the conversion put back, and nothing else
        changed — including the em ratio, which stays at the artwork's.

        `NAME_LEADING_INCUMBENT_EM`, NOT the live setting. This staticmethod
        IS WI-P's deliverable: it is the fixed producer that the defective one
        above must agree with, and the agreement is the zero-effect claim. Its
        ratio is therefore pinned to the value WI-P preserved. Pointing it at
        `NAME_LEADING_EM` would make the pair agree by construction at
        whatever the leading happens to be, and the proof would evaporate.

        `name_lines` is accepted and ignored so this stays signature-
        compatible with the real producer after §AC1(e); the two lines it
        draws are WI-P's own subject and are not a parameter of the claim.
        """
        from apps.ire.graph import Color, TextRun

        ink = Color.from_hex("#5A2A3A")
        closure_h = (g["collar_height_mm"] + g["bulb_height_mm"]
                     + (g.get("visible_neck_mm") or 3.0))
        zy = oy + (closure_h + float(zone["y"])) * s
        zh = float(zone["height"]) * s
        name_size = name_min
        leading = name_size * back_panel.MM_PER_PT * NAME_LEADING_INCUMBENT_EM
        block_top = zy + zh * 0.30
        return ([TextRun(name=f"{prefix}product-name-hero-0", text="Rose",
                         x=0.0, y=block_top, size_pt=name_size, color=ink),
                 TextRun(name=f"{prefix}product-name-hero-1", text="Damascena",
                         x=0.0, y=block_top + leading, size_pt=name_size,
                         color=ink)],
                [], "", (0.0, 0.0, 1.0, 1.0))

    def test_the_unconverted_offset_does_not_move_and_that_is_the_catch(self):
        """The pre-fix expression is blind to the conversion constant.

        Its ratio is exactly 1.0 — not approximately, exactly, because the
        constant appears nowhere in `name_size * 1.06` and the two calls run
        identical arithmetic. This is what the real producer returning 2.0
        rules out.

        The offset is pinned as 9.54 to nine places and NOT as a raw float.
        The first draft of this test asserted `9.540000000000001`, which is
        what `9.0 * 1.06` evaluates to — and the producer emits
        `9.540000000000006`, because the offset is recovered by subtracting
        two coordinates near 101 and 111 rather than computed directly. Both
        are 9.54 mm. Only one of them was measured, and pinning the other
        would have been an expectation dressed as an observation.
        """
        seen = offset_tracks_the_conversion(self._defective)
        assert seen["ratio"] == 1.0
        assert seen["mm_at_the_real_constant"] \
            == seen["mm_at_twice_the_constant"]
        assert round(seen["mm_at_the_real_constant"], 9) == 9.54

    def test_the_converted_offset_moves_and_that_is_the_release(self):
        seen = offset_tracks_the_conversion(self._converted)
        assert seen["ratio"] == pytest.approx(2.0, abs=1e-12), seen

    @pytest.mark.parametrize("name_min", [HERO_NAME_MIN, FLAT_NAME_MIN])
    def test_the_defect_and_the_fix_place_the_two_lines_in_the_same_spot(
            self, name_min):
        """The zero-effect claim, in the one form that cannot go stale.

        Comparing against `git show HEAD:` stops meaning anything the moment
        WI-P is committed. Comparing against the defect kept in this file
        means the same thing forever: the offset was corrected in units and
        left alone in size.

        The two are not bit-identical and this does not pretend they are —
        3 ULP at 9.0 pt, 0 ULP at 6.5 pt, from multiplying three floats in a
        different order. 3 ULP of a 9.54 mm offset is 5.3e-15 mm.

        §AC1 RE-POINTS THE RIGHT-HAND SIDE AND WEAKENS NOTHING. The fixed
        producer is now `self._converted` rather than the shipping
        `_front_typography`, because the shipping one has since been RULED to
        2.0 em and is no longer making WI-P's claim. `_converted` is WI-P's
        fix, byte for byte, with the em ratio at the incumbent — so the
        comparison still says exactly what it always said: correcting the
        units moved the artwork by 3 ULP. What it must NOT be allowed to say
        is that the artwork never moved, because §AC1 moved it deliberately,
        and the test below measures that separately.
        """
        defect = leading_mm(self._defective, name_min)
        fixed = leading_mm(self._converted, name_min)
        assert abs(fixed - defect) <= 4 * math.ulp(defect), (defect, fixed)
        assert round(fixed, 9) == round(defect, 9) == round(
            name_min * DEFECT_FACTOR, 9)

    @pytest.mark.parametrize("name_min,shipped_mm", [(HERO_NAME_MIN, 6.35),
                                                     (FLAT_NAME_MIN,
                                                      4.586111111)])
    def test_and_ac1_then_moved_it_on_purpose_by_this_much(self, name_min,
                                                           shipped_mm):
        """The other half, kept apart from the half above ON PURPOSE.

        WI-P's proof is "the units fix moved nothing". §AC1's ruling is "the
        ratio moves, to 2.0 em". Both are true and they are about different
        things, so they get different tests: put in one, the second would read
        as the first having failed.

        The shipping producer is now 3.190 mm tighter at 9.0 pt and 2.304 mm
        tighter at 6.5 pt than the incumbent WI-P preserved — a 33.4%
        reduction in the gap at both sizes, since both are one ratio applied
        to a type size.
        """
        shipped = leading_mm(_front_typography, name_min)
        incumbent = leading_mm(self._converted, name_min)
        assert round(shipped, 9) == shipped_mm
        assert shipped == pytest.approx(
            name_min * back_panel.MM_PER_PT * AC1_SET_EM, rel=1e-12)
        assert incumbent / shipped == pytest.approx(
            NAME_LEADING_INCUMBENT_EM / AC1_SET_EM, rel=1e-12)
        assert round(100 * (1 - shipped / incumbent), 1) == 33.4


class TestTheEmRatioWasTheOwnersQuestionAndHasBeenAnswered:
    """§AA2(c) — the name block's proportion is a design ruling, not a fix.

    The unit correction made the ratio visible and did not touch it. These
    pinned what became visible so the number could not drift while it waited
    for the ruling, and so the ruling would have an exact price attached when
    it came. §AC1 IS THAT RULING, and the class is renamed rather than
    deleted: the incumbent it was guarding is still a named constant under
    §AC1(f), and the price it computed is now a bill that was paid rather than
    a quote.
    """

    def test_the_leading_the_artwork_had_was_three_em_not_one(self):
        """Unchanged in substance, re-pointed at the constant that now holds
        the number. This is the accident's fingerprint: 3.0047... is exactly
        1.06 divided by the conversion constant, which is what proves the
        provenance was a units bug and not a choice anyone made."""
        assert NAME_LEADING_INCUMBENT_EM == pytest.approx(
            DEFECT_FACTOR / (25.4 / 72.0), rel=1e-15)
        assert 3.0 < NAME_LEADING_INCUMBENT_EM < 3.01

    def test_and_the_ruled_setting_is_a_round_number_that_is_not_derived(self):
        """The complement, and the point of §AC1(f) keeping both named.

        The incumbent is an artefact of arithmetic nobody intended; the
        setting is a decision somebody made. Asserting that 2.0 is NOT
        expressible as the old accident is what keeps the two distinguishable
        in a year, when only the constants are left.
        """
        assert NAME_LEADING_EM == AC1_SET_EM
        assert NAME_LEADING_EM != NAME_LEADING_INCUMBENT_EM
        assert NAME_LEADING_EM != pytest.approx(
            DEFECT_FACTOR / (25.4 / 72.0), rel=1e-3)

    @pytest.mark.parametrize("name_min,expected_mm", [(HERO_NAME_MIN, 9.54),
                                                      (FLAT_NAME_MIN, 6.89)])
    def test_the_gap_the_two_panels_used_to_draw(self, name_min, expected_mm):
        """Kept as a measurement of the incumbent, which §AC1(f) preserves as
        the fallback if the true-scale render loses §AC1(c)'s bet. A fallback
        with no measured value attached is not a fallback."""
        assert round(name_min * back_panel.MM_PER_PT
                     * NAME_LEADING_INCUMBENT_EM, 9) == expected_mm

    def test_what_one_point_zero_six_em_would_have_cost_and_why_it_is_dead(
            self):
        """The price this class was written to compute, and the answer.

        WI-P wrote: *"If the owner rules that 1.06 was the intent,
        `NAME_LEADING_EM` becomes 1.06 and the hero gap loses 6.17 mm — 65% of
        it."* The owner did not so rule. §AC1 ruled 1.06 em a FAIL, because at
        9.0 pt the two line boxes OVERLAP by 0.959 mm and only the absence of
        a descender in `Rose` keeps the ink apart — a property of the string,
        not of the setting.

        Both numbers are kept: the price WI-P quoted, and the reason it was
        never paid. The quote was correct and the transaction was refused.
        """
        mm_per_pt = 25.4 / 72.0
        for name_min, lost in ((HERO_NAME_MIN, 6.1745),
                               (FLAT_NAME_MIN, 4.4594)):
            incumbent = name_min * mm_per_pt * NAME_LEADING_INCUMBENT_EM
            at_106 = name_min * mm_per_pt * DEFECT_FACTOR
            assert round(incumbent - at_106, 4) == lost
            assert at_106 / incumbent == pytest.approx(
                1.0 / NAME_LEADING_INCUMBENT_EM * DEFECT_FACTOR, rel=1e-9)
        # and what was actually paid, at the hero size: less than half of it
        paid = (HERO_NAME_MIN * mm_per_pt
                * (NAME_LEADING_INCUMBENT_EM - NAME_LEADING_EM))
        assert round(paid, 4) == 3.19
        assert paid < 6.1745
        # 1.06 em is below the face's own metric floor and is not legal at any
        # name. The floor is measured, not quoted, in test_wiy_*.
        assert DEFECT_FACTOR < 1.362 < NAME_LEADING_EM


class TestTheOtherOneOhSixInTheRepoIsNotThisDefect:
    """The false positive a grep would have produced, measured not asserted.

    `compose_vector_art._concept_finish_layers` computes `y + name_h * 1.06`
    — the same literal, on a quantity with the same kind of name, one module
    away. It is
    correct: `name_h` is `front.height * 0.115`, already millimetres, so the
    1.06 is a genuine ratio of a length. This is the concrete reason WI-J gave
    for refusing a source-string guard, and it is checked rather than asserted
    so that WI-Q inherits a fact instead of a claim.
    """

    def test_the_finish_mask_offset_is_millimetres_times_a_ratio(self):
        from apps.ire.compose_vector_art import _concept_finish_layers
        from apps.ire.graph import Color

        class _Box:
            x, y, width, height = 10.0, 20.0, 60.0, 90.0

        class _Accent:
            @staticmethod
            def color():
                return Color.from_hex("#B08D57")

        class _Swatches:
            accent = _Accent()

        class _Params:
            swatches = _Swatches()

        groups = _concept_finish_layers(_Box(), {"EMBOSS": True}, _Params(),
                                        [], lambda v: v, lambda v: v)
        masks = [n for grp in groups for n in (grp.children or [])]
        powder = [n for n in masks if str(n.name) == "EMBOSS-powder"]
        assert len(powder) == 1, sorted(str(n.name) for n in masks)

        # `name_h` is `front.height * 0.115` — a millimetre length — so the
        # mask's own height IS name_h and the 1.06 offset above the unshifted
        # row is millimetres times a ratio. No conversion belongs here, and
        # the guard above would have been wrong to demand one.
        name_h = _Box.height * 0.115
        unshifted = _Box.y + _Box.height * 0.34 - name_h * 0.8
        assert round(float(powder[0].h), 9) == round(name_h, 9)
        assert round(float(powder[0].y) - unshifted, 9) \
            == round(name_h * DEFECT_FACTOR, 9)

        # and the thing that makes it NOT this defect: it is blind to the
        # conversion constant for the right reason — there is no point size
        # anywhere in it. Both quantities are millimetres.
        assert round(name_h, 9) == round(_Box.height * 0.115, 9)
