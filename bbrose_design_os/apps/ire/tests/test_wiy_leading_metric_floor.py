"""WI-Y / §AC1 — the metric floor, and the control that says whether it is one.

WHAT §AC1 RULED
---------------
*"The metric floor is the constraint. At 1.06 em the line boxes overlap by
0.959 mm. That is a FAIL. The leading rises until the metric floor clears, and
the number it must clear is 1.362 em."* The setting is **2.0 em**.

WHY THE CONTROL IS THE POINT OF THIS FILE
------------------------------------------
§AC1(d): *"A guard that passes 1.06 em because the current glyphs happen not
to touch is the ink floor wearing the metric floor's name. The control: the
same guard, at the same leading, on a synthetic product name containing a
descender, must return the SAME verdict."*

That is one half. **A control that cannot fail proves nothing**, so the other
half is asserted here too: on the same renders, the INK clearance genuinely
DOES move with the string, by 0.734953 mm — the face's descender depth. If it
did not, "metric" and "ink" would be one measurement under two names, the
control would pass for a guard that measures the wrong thing, and the §AC1(d)
requirement would be satisfied vacuously. Both halves, or neither is evidence.

The concrete consequence is stated as a number in
``test_an_ink_measuring_guard_would_have_flipped_and_here_is_its_window``: at
1.06 em an ink-based guard with ANY threshold between 0.338 and 1.073 mm
returns PASS for `Rose` and FAIL for a name with a `y` in it. That interval is
the guard §AC1 refused, priced.

THE GUARD IS WRITTEN AGAINST ZERO, NOT AGAINST 1.362
-----------------------------------------------------
1.362 em is not a constant of the design. It is what zero box clearance works
out to AT 9.0 pt IN THIS FACE, and it is reproduced here to 3.6e-07 em by
measurement. A guard written against the literal 1.362 would keep reporting a
floor that had moved underneath it the moment the size or the face changed —
§AC0(a) on the other axis: the constraint that survives a change of content is
the one that binds, and a face is content too.

WHAT THIS FILE RECORDS AND DOES NOT FIX
----------------------------------------
* **The two survivors are both above 1 on the quantity §AC1(c)'s bet names,
  and the pre-authorised fallback is the worse of the two.** Recorded with its
  magnitude in `TestTheBetIsNamedAndTheMeasurementItRidesOnIsTaken`. No
  leading is proposed; §AC1(c) reserves the judgement to the owner looking at
  the render, and this file renders it.
* **`compose_dropper_sheet` still does not pass `product_name` to the front.**
  §AC1(e) authorised the parameter, and the parameter is the instrument. The
  WIRING is a separate question that needs a line-breaking ruling nobody has
  made. WI-U recorded it; it is still true and it is asserted as still true.
  [§BH68(d), 2026-09-24: NO LONGER TRUE. The owner ruled the source — "Derive
  it from the product record; print nothing where the record is silent" — and
  the line-breaking is the composer's own `wrap_name`, which every supplied
  line already passed through. With no ruled hierarchy the sheet's
  `product_name` now fills the front's name slot; `FRONT_NAME_LINES` is gone.
  WI-U's legs (3b) and (4) are discharged in test_wiu_front_collision.py.]
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import sys

import pytest

from apps.ire import back_panel, compose_dropper
from apps.ire.compose_dropper import NAME_LEADING_EM, NAME_LEADING_INCUMBENT_EM

#: The two-`tools`-directories collision and why file-path loading is the only
#: lever: see `test_wiv_leading_comparison.py:40-78`, which measured it. The
#: loader is that file's, unchanged in mechanism — a second copy of a solved
#: problem is cheaper than a shared helper that two suites can break for each
#: other, and the borrow is what makes the tool's own `from tools.…` import
#: resolve to this root rather than the git root's package.
_TOOL_NAME = "_wiy_leading_floor_byfile"
_ROOT = pathlib.Path(__file__).resolve().parents[3]
_TOOL_PATH = _ROOT / "tools" / "wiy_leading_floor.py"
_WIV_NAME = "_wiy_borrowed_wiv_byfile"
_WIV_PATH = _ROOT / "tools" / "wiv_leading_comparison.py"


def _load(name, path):
    mod = sys.modules.get(name)
    if mod is not None:
        return mod
    borrowed = {k: sys.modules.pop(k) for k in list(sys.modules)
                if k == "tools" or k.startswith("tools.")}
    pkg = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec("tools", None, is_package=True))
    pkg.__path__ = [str(_ROOT / "tools")]
    sys.modules["tools"] = pkg
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod            # before exec, for self-reference
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            del sys.modules[name]
            raise
    finally:
        for k in [k for k in sys.modules
                  if k == "tools" or k.startswith("tools.")]:
            del sys.modules[k]
        sys.modules.update(borrowed)
    return mod


def _tool():
    return _load(_TOOL_NAME, _TOOL_PATH)


RULED_PT = 9.0
EM_MM = RULED_PT * back_panel.MM_PER_PT          # named conversion, §Z1(b)

#: §AC1's own numbers, transcribed from `OWNER_BLOCKER_CLEARANCE.md` §AC1 and
#: §AC1(c). They are here to be CHECKED AGAINST, not to be computed from: a
#: test that derives the ruling's figures from the same code the ruling was
#: derived from agrees with itself and with nothing else.
RULED_FLOOR_EM = 1.362
RULED_OVERLAP_MM = 0.959
RULED_HEADROOM_EM = 0.638
DEAD = 1.06
SET = 2.0
INCUMBENT = 3.0047244094488192

#: The face's descender depth at the ruled size, MEASURED (see
#: `test_the_control_is_not_vacuous_because_the_ink_really_does_move`). It is
#: the same figure for `y`, `g`, `p` and `j`, which is why one synthetic name
#: covers §AC1(a)'s whole list.
DESCENDER_MM = 0.734953


@pytest.fixture(scope="module")
def t():
    return _tool()


class TestTheFloorIsMeasuredAndAgreesWithTheRuling:
    """§AC1's number, re-derived from an artefact rather than trusted."""

    def test_the_metric_floor_is_1_362_em_and_it_was_not_typed_in(self, t):
        """The floor is the face's line box, read off an emitted PDF and
        divided by one em. §AC1 says 1.362; this reads 1.362 to seven
        decimals. Two independent routes to one number is the only reason to
        believe either."""
        box_h = t.line_box_height()
        floor_em = box_h / EM_MM
        assert floor_em == pytest.approx(RULED_FLOOR_EM, abs=1e-6), (
            f"the ruling says {RULED_FLOOR_EM} em, the artefact says "
            f"{floor_em:.6f} em")
        assert box_h == pytest.approx(4.324351, abs=1e-6)

    def test_the_floor_does_not_move_with_the_string(self, t):
        """The property that makes it a floor at all.

        A line box runs ascent to descent and is drawn whether or not a glyph
        reaches either end, so its height is a fact about the FACE and the
        SIZE. Asserted across a name with no descender, a plausible next SKU
        with one, and a synthetic with every descender the face has — the
        spread is EXACTLY zero, not merely small.
        """
        heights = {n[0]: t.line_box_height(n) for _lbl, n in t.NAMES}
        assert len(set(heights.values())) == 1, heights
        assert set(heights) == {"Rose", "Peony", "Rogypj"}

    def test_the_dead_leading_overlaps_by_the_figure_the_ruling_quotes(
            self, t):
        """§AC1's headline measurement, reproduced: 0.959 mm of overlap."""
        c = t.box_clearance(DEAD, t.SHIPPING)
        assert c < 0
        assert abs(c) == pytest.approx(RULED_OVERLAP_MM, abs=5e-4), (
            f"§AC1 quotes {RULED_OVERLAP_MM} mm, measured {abs(c):.6f}")

    def test_the_set_leading_clears_by_the_headroom_the_ruling_claims(self, t):
        """§AC1(c): *'2.0 em clears the metric floor by 0.638 em'*."""
        head = (t.box_clearance(SET, t.SHIPPING)) / EM_MM
        assert head == pytest.approx(RULED_HEADROOM_EM, abs=5e-4)
        assert SET - RULED_FLOOR_EM == pytest.approx(RULED_HEADROOM_EM,
                                                     abs=5e-4)


class TestTheAc1dNegativeControl:
    """§AC1(d), both halves. Either alone is not evidence."""

    @pytest.mark.parametrize("em,expected", [(DEAD, "FAIL"), (SET, "PASS"),
                                             (INCUMBENT, "PASS")])
    def test_the_verdict_does_not_move_with_the_string(self, t, em, expected):
        """THE CONTROL §AC1(d) ASKED FOR.

        One verdict per leading across all three names. If this ever returns
        two different words in one row, the guard is measuring ink and §AC1(d)
        says in terms that it is void — so the failure message says so rather
        than reporting a number.
        """
        got = {n[0]: t.verdict(em, n) for _lbl, n in t.NAMES}
        assert set(got.values()) == {expected}, (
            f"THE GUARD IS VOID: at {em} em the verdict moved with the "
            f"string — {got}. §AC1(d): if the verdict changes with the "
            f"string, the instrument is measuring ink.")

    @pytest.mark.parametrize("em", [DEAD, SET, INCUMBENT])
    def test_and_not_merely_the_verdict_but_the_number_behind_it(self, t, em):
        """A verdict is a threshold applied to a quantity, and a control that
        only watches the verdict would miss a quantity drifting toward the
        threshold. The BOX CLEARANCE itself is identical across all three
        names to nine decimal places."""
        cs = {round(t.box_clearance(em, n), 9) for _lbl, n in t.NAMES}
        assert len(cs) == 1, f"box clearance moved with the string: {cs}"

    def test_the_control_is_not_vacuous_because_the_ink_really_does_move(
            self, t):
        """THE HALF §AC1(d) IMPLIES AND DOES NOT SPELL OUT.

        If the ink clearance were also invariant, the control above would pass
        for an ink-measuring guard and would prove nothing at all. It is not
        invariant: at every leading the ink moves by the face's descender
        depth the moment line one gains a descender, and by exactly that same
        amount for `y`, `g`, `p` and `j` — which is why one synthetic name
        covers the whole of §AC1(a)'s list.
        """
        for em in (DEAD, SET, INCUMBENT):
            ink = {lbl: t.ink_clearance(em, n) for lbl, n in t.NAMES}
            assert ink["shipping"] - ink["plausible"] == pytest.approx(
                DESCENDER_MM, abs=1e-5), (em, ink)
            assert ink["plausible"] == pytest.approx(ink["synthetic"],
                                                     abs=1e-9), (em, ink)

    def test_an_ink_measuring_guard_would_have_flipped_and_here_is_its_window(
            self, t):
        """The guard §AC1 refused, priced.

        At 1.06 em `Rose` clears by 1.073 mm of white and `Peony` by 0.338.
        Any ink-based threshold strictly inside that interval passes the
        shipping name and fails the next SKU — silently, because nothing in
        the pipeline renders the next SKU. That is §AC1(a)'s *"coincidence
        with a measurement next to it"* as an interval of wrong answers.
        """
        rose = t.ink_clearance(DEAD, t.SHIPPING)
        peony = t.ink_clearance(DEAD, t.PLAUSIBLE)
        assert rose == pytest.approx(1.073032, abs=1e-5)
        assert peony == pytest.approx(0.338079, abs=1e-5)
        assert rose > 0 and peony > 0        # BOTH pass an ink guard at zero
        for threshold in (0.4, 0.6, 0.8, 1.0):
            assert (rose >= threshold) and not (peony >= threshold)
        # ...while the metric guard returns one word for both.
        assert t.verdict(DEAD, t.SHIPPING) == t.verdict(DEAD, t.PLAUSIBLE)
        assert t.verdict(DEAD, t.SHIPPING) == "FAIL"


class TestTheGuardIsWrittenAgainstZeroAndNotAgainstTheFigure:
    """§AC0(a) applied to the face: 1.362 is a consequence, not a constant."""

    def test_source_guard_the_verdict_holds_no_1_362_literal_to_go_stale(
            self, t):
        """SOURCE-STRING GUARD (§Y2(b)).

        `verdict()` must compare a measured clearance against zero. If someone
        later writes the floor in as a number, the guard starts asserting a
        remembered property of a face nobody re-measured — and the whole
        argument of this file is that a remembered measurement is not one.
        The ruling's figure may appear in the tool as a value to CHECK
        AGAINST (`RULED_FLOOR_EM`), which is the opposite use.

        ITS DOMAIN IS THE EXECUTABLE BODY AND THAT IS NOT A DETAIL. The first
        draft matched against `inspect.getsource` whole and went red on
        `verdict`'s own docstring, which contains "1.362" in the sentence
        EXPLAINING why it must not be a literal. A source-string guard whose
        domain is "the characters in the file" fires on the prose that
        justifies it — the same class of error as measuring a line box and
        calling it ink, one level up. The docstring is stripped through the
        AST rather than by a regex over quotes, because a guard that parses
        its subject the way Python does cannot be fooled by a string that
        merely looks like code.
        """
        import ast
        import inspect
        import textwrap
        src = textwrap.dedent(inspect.getsource(t.verdict))
        fn = ast.parse(src).body[0]
        body = fn.body
        if (isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]                # the docstring, and only it
        code = "\n".join(ast.get_source_segment(src, n) for n in body)
        assert code, "verdict() has no executable body"
        assert ">= 0.0" in code, code
        assert "1.362" not in code, (
            "the guard has been rewritten against the literal floor; it will "
            f"now report a floor that has moved underneath it:\n{code}")
        # and the prose it is NOT allowed to fire on is still there, so this
        # test cannot pass by the docstring having been deleted.
        assert "1.362" in (ast.get_docstring(fn) or "")

    def test_and_the_floor_is_a_consequence_of_the_size(self, t):
        """The same face at a different size has a different floor in em? No —
        in EM it is the same, and that is the point: the em ratio is a
        property of the face and the millimetres are not. Stated as the
        identity the guard relies on."""
        box_h = t.line_box_height()
        assert box_h / EM_MM == pytest.approx(RULED_FLOOR_EM, abs=1e-6)
        assert box_h == pytest.approx((box_h / EM_MM) * EM_MM, abs=1e-12)


class TestWhatAc1ChangedInProduction:
    """The constant swap, and the exception §AC1(e) named."""

    def test_the_setting_is_2_0_and_the_incumbent_keeps_its_name(self):
        """§AC1(f): *'Deleting the number would delete the evidence that the
        accident happened.'* Both constants exist and they are different."""
        assert NAME_LEADING_EM == SET
        assert NAME_LEADING_INCUMBENT_EM == INCUMBENT
        assert NAME_LEADING_EM != NAME_LEADING_INCUMBENT_EM

    def test_the_name_lines_parameter_defaults_to_todays_artwork(self):
        """§AC1(e)'s parameter is the instrument, and an instrument that
        changed the artwork by existing would be a production change wearing a
        control's name. `None` is the shipping path."""
        # §BH68(d): the module default is gone — `None` prints no name; the sheet hands in the record's
        assert not hasattr(compose_dropper, "FRONT_NAME_LINES")
        import inspect
        sig = inspect.signature(compose_dropper._front_typography)
        assert sig.parameters["name_lines"].default is None

    def test_and_the_parameter_actually_reaches_the_artwork(self, t):
        """The control would be theatre if it did not. Rendering with a
        different name must produce different ink; asserted by measuring the
        ink, because a parameter that is accepted and ignored is exactly the
        failure this proves against."""
        a = t.ink_clearance(SET, t.SHIPPING)
        b = t.ink_clearance(SET, t.SYNTHETIC)
        assert a != b

    def test_source_guard_the_sheet_does_not_wire_product_name_to_the_front(
            self):
        """SOURCE-STRING GUARD (§Y2(b)). It asserts nothing about behaviour:
        it reads literals out of `compose_dropper_sheet`'s source and says
        which are present and how often. A wiring done under a different local
        name would pass it, and a pure rename would fail it. Declared on the
        way in rather than admitted to the backlog later — the §Y2 register is
        an invariant this sprint and did not move.

        RECORDED, NOT FIXED — WI-U's finding, NARROWED BY §BB7(g)(a) AND STILL
        OPEN AT THE PART THAT MATTERS.

        §AC1(e) authorised the PARAMETER as the instrument for the control.
        §BB7(g)(a) has now plumbed the sheet: `hierarchy_lines` arrives and is
        destructured into `name_lines`/`descriptor` for both panels. So the
        second literal this test used to look for — `"name_lines" not in src` —
        is FALSE by design, and asserting it would now be asserting that the
        ruled plumbing had not been built.

        WHAT IS STILL TRUE IS THE HALF WI-U ACTUALLY CARED ABOUT: the sheet's
        own `product_name` argument does not reach the front. The front is fed
        from `hierarchy_lines`, which no production call site passes, because
        the owner reserved the SOURCE question — *"If §3 needs a per-product
        source for the hierarchy rather than the ruled FACIAL SERUM literal,
        that is a measured proposal to bring back, not a decision to make."* So
        the gap did not close; it moved from "there is no mechanism" to "the
        mechanism exists and is deliberately unfed".

        [§BH68(d), 2026-09-24: THE GAP CLOSED. The owner ruled the source, and
        the sheet's `product_name` fills the name slot whenever no hierarchy is
        supplied — the shipping path. This test's name records what was true
        when it was written; its four string legs still hold and did not move.
        The structural claim is WI-U's leg (3b), asserted on the parse tree.]

        THE STRUCTURAL HALF OF THIS GUARD IS THE NEXT TEST, AND THE SPLIT IS
        THE POINT OF THIS PARAGRAPH. It was written here first, as two more
        legs asserting on `ast.parse(src)`. Measured, that cost the §Y2 census
        this entire guard: `_is_pure_guard` requires EVERY leg to be a
        source-string claim, `len(feeds) == 1` is not one, and the classifier's
        count fell 16 -> 15 with the derived gap 12 -> 13. Four legs scored,
        two did not, and one impure leg is enough.

        TWO RESPONSES WERE AVAILABLE AND THE CHEAPER ONE WAS WRONG. Editing the
        three census numbers would have recorded a real movement — that file's
        docstrings are a log of exactly such movements — but it would have
        logged the cause as a classifier blind spot when the honest cause is
        that one test was making two KINDS of claim. §AK3 is already written
        down in `brand_strings.sites`: "One idea, one spelling cuts both ways —
        two ideas may not share one." A string claim and a structural claim are
        two ideas. Split, both are stronger, the register did not move, and no
        instrument had to be retuned to accommodate a test of mine.
        """
        import inspect
        src = inspect.getsource(compose_dropper.compose_dropper_sheet)
        assert "product_name" in src            # it arrives
        assert "hierarchy_lines" in src         # §BB7(g)(a): so does the ruled
        assert "name_lines=front_lines" in src  # hierarchy, and it reaches
        assert src.count("name_lines=front_lines") == 3      # BOTH panels, and Gate 2's print-size block (2026-09-25)

    def test_and_what_feeds_the_derivation_is_checked_structurally(self):
        """The other half of the guard above, and deliberately NOT declared.

        A string scan is fooled by a rename, and `"hierarchy_lines" in src`
        would pass on a comment. This asks the parse tree what actually feeds
        the derivation, so a wiring done under any local name is caught as long
        as it flows from `product_name` — which is the half WI-U cared about.

        It reads source and asserts nothing about behaviour, so it is a guard
        in the ordinary sense. It is still not a §Y2 one: that register is of
        source-string guards, its marker says so in those words, and its
        classifier is RIGHT to score `len(feeds) == 1` as not a string claim.
        Naming this `test_source_guard_` would have declared a structural check
        to be a string check, and then required three census numbers to be
        edited to make the declaration come true. Neither the register nor the
        count moved.
        """
        import ast
        import inspect
        # `ast.parse` needs a dedented, standalone unit; the source of a
        # module-level function is already at column 0.
        tree = ast.parse(
            inspect.getsource(compose_dropper.compose_dropper_sheet))
        feeds = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Name)
                 and c.func.id == "front_copy_from_hierarchy"]
        assert len(feeds) == 1
        assert [a.id for a in feeds[0].args
                if isinstance(a, ast.Name)] == ["hierarchy_lines"]


class TestTheBetIsNamedAndTheMeasurementItRidesOnIsTaken:
    """§AC1(c) named a losing condition. This measures its correlate.

    NO LEADING IS PROPOSED. §AC1(c) reserves the judgement to the owner
    looking at a true-scale render, and WI-Y's deliverable is that render.
    What is asserted here is the arithmetic the judgement will be made beside,
    because §AB0(b) requires a ruling to know the measurement it bets against
    and §AC1(c) says in terms that this one was made *"from arithmetic"* with
    the render unseen.
    """

    def test_both_survivors_spread_the_name_wider_than_its_own_margin(self, t):
        """Two lines read as one unit when they are closer to each other than
        the pair is to its neighbour. Neither survivor is."""
        rows, floor_em, ceiling = t.cohesion()
        by_em = {round(em, 4): (inside, below, ratio)
                 for em, inside, below, ratio in rows}
        assert by_em[2.0][2] == pytest.approx(1.334, abs=1e-3)
        assert by_em[round(INCUMBENT, 4)][2] == pytest.approx(3.436, abs=1e-3)
        assert by_em[2.0][2] > 1.0 and by_em[round(INCUMBENT, 4)][2] > 1.0

    def test_the_gap_below_the_name_is_the_same_at_both_and_that_is_wi_u(
            self, t):
        """The comparison has one variable in it, and WI-U is why."""
        rows, _f, _c = t.cohesion()
        belows = [below for _em, _in, below, _r in rows]
        # §BH50(b): at the 5.0 pt re-lay the two readings differ by 2 nm
        # (1.518001 / 1.518003), the float arithmetic of two leadings'
        # baselines; "the same" is asserted to 10 nm, the tolerance
        # test_wiu_front_collision.py holds scale-invariance to
        assert max(belows) - min(belows) < 1e-5, belows
        assert belows[0] == pytest.approx(1.518, abs=1e-3)

    def test_the_pre_authorised_fallback_is_the_worse_of_the_two_here(self, t):
        """A FINDING, and the one most worth the owner's attention.

        §AC1(c): *'if 2.0 loses, 3.0047 is the fallback and it needs no new
        ruling to take.'* On the quantity the losing condition names, 3.0047
        is 2.58x further from cohesion than 2.0 is. If 2.0 loses for reading
        as two unrelated lines, the pre-authorised fallback loses harder, and
        taking it would need a ruling after all.
        """
        rows, _f, _c = t.cohesion()
        ratios = {round(em, 4): r for em, _i, _b, r in rows}
        assert ratios[round(INCUMBENT, 4)] > ratios[2.0]
        assert (ratios[round(INCUMBENT, 4)]
                / ratios[2.0]) == pytest.approx(2.575, abs=5e-3)

    def test_the_window_that_would_satisfy_it_contains_neither_survivor(
            self, t):
        """Stated as an interval, which is what §AC1(b) calls a floor: *'the
        floor says only which values are legal.'* Naming a legal interval is
        the same kind of statement and is not a setting."""
        _rows, floor_em, ceiling = t.cohesion()
        assert floor_em == pytest.approx(1.362, abs=1e-3)
        assert ceiling == pytest.approx(1.840, abs=1e-3)
        assert not (floor_em <= SET < ceiling)
        assert not (floor_em <= INCUMBENT < ceiling)


class TestTheComparisonToolSurvivedTheConstantSwap:
    """The defect §AC1 created in WI-V's tool, and its guard."""

    def test_the_three_wiv_leadings_are_three_distinct_numbers(self):
        """WHY THIS TEST EXISTS, AS A MEASUREMENT.

        `tools/wiv_leading_comparison.py` read its incumbent panel from
        `compose_dropper.NAME_LEADING_EM`. §AC1 set that constant to 2.0, so
        the three-panel comparison silently became 1.06 / 2.00 / 2.00 — with
        the captions computed from the same variable, so every label agreed
        with its own artwork and the sheet looked correct. The suite loads
        that module and never asserted `LEADINGS`, so nothing went red.

        Repaired at the source as part of §AC1, since §AC1 caused it. This is
        the guard against the silent recurrence: three panels, three numbers.
        """
        wiv = _load(_WIV_NAME, _WIV_PATH)
        ems = [em for _label, em in wiv.LEADINGS]
        assert len(set(ems)) == 3, f"the comparison lost a variable: {ems}"
        assert sorted(ems) == [DEAD, SET, INCUMBENT]
        assert wiv.INCUMBENT == NAME_LEADING_INCUMBENT_EM
        assert wiv.SHIPPED == NAME_LEADING_EM

    def test_and_the_labels_are_computed_from_the_values_they_label(self):
        """The reason the defect was invisible: nothing could disagree. Kept
        that way — a hand-typed caption could drift from its panel — and the
        distinctness check above is what makes it safe."""
        wiv = _load(_WIV_NAME, _WIV_PATH)
        for label, em in wiv.LEADINGS:
            assert label.startswith(f"{em:.2f}"[:4].rstrip("0").rstrip(".")
                                    ) or f"{em:.4f}" in label or \
                f"{em:.2f}" in label, (label, em)
