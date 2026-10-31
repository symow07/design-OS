"""WI-U / §AB2 — the front collision, and the property that makes it impossible.

WHAT §AB2 ASKED FOR
-------------------
*"9.0 pt is the correct product-name size. The −1.389 mm overlap is a placement
bug, not a size verdict."* — and §AB2(a): *"fix the collision by moving the
support line, not by shrinking the name."*

So there are two claims to prove and they are not the same claim. That the
overlap is gone is easy and is one assertion. That NOTHING ELSE MOVED is the
one that matters, because the cheap way to clear a collision is to shrink the
thing that collides, and that is the move the ruling forbids. The size, the
horizontal extents and the baselines of every run above the support line are
asserted UNCHANGED against numbers read from the pre-WI-U artefact.

WHY THE FIX IS NOT "USE A BIGGER FRACTION"
-------------------------------------------
``leading`` is PHYSICAL — 9.54 mm at 9.0 pt, and the same 9.54 mm however
large the panel is drawn. The support line sat at ``zh * 0.545``, a fraction
of the DRAWN zone. Two quantities, one scaling and one not, with no
relationship between them: at s=1.22 the fraction had grown 22% and the block
had not, so panel 5 cleared by +0.891 mm — and 1:1, the only scale that
prints, overlapped by −1.389 mm. **The sheet concealed the defect by never
drawing the scale that has it.**

Raising 0.545 to some larger number would have cleared the overlap and left
that mechanism in place, so the next leading change would put it back. Both
support baselines now hang off the name block's last baseline, which makes the
support stack one physical object with the type above it. The test that
matters is therefore not "is the gap positive" but
``test_the_clearance_is_now_the_same_at_every_scale`` — the bug's mechanism was
scale-dependence, and scale-independence is its absence.

It also matters for the NEXT work item. WI-V renders 1.06 / 2.0 / 3.0047 em at
9.0 pt. Against a fixed fraction, two of those three collide by different
amounts, and the owner would have been shown three collisions and asked to
judge leading. No leading is chosen here — §AB3 reserves that, and this file
issues no opinion on it.

THE NUMBERS ARE MEASURED, AND ONE OF THEM IS BORROWED
------------------------------------------------------
1.175 em was not picked for looking right. It reproduces the clearance of the
6.5 pt render, the only front layout in this repository ever rendered, seen and
called clean — *"the layout is clean and every run clears"*. Off that artefact
it is +1.5194 mm; at 9.0 pt this delivers +1.5181 mm, and the 0.0013 mm is what
a 3-decimal em constant costs. 0.866 em carries the old support→net distance
across to within 0.00005 mm, so the one relationship in the block that was
never broken is preserved rather than re-tuned.

WHAT THIS FILE RECORDS AND DOES NOT FIX
----------------------------------------
Two findings are asserted as findings, per §AB4(c) and §AB0(a):

* **The front does not render the SKU's name.** ``product_name`` reaches the
  document title and nothing else; ``Rose`` / ``Damascena`` are literals inside
  the producer. §AB2(f) asked for the headroom *"so the next SKU meets a known
  limit instead of a surprise"* — the headroom below is real, but the mechanism
  that would consume it does not exist yet, and saying so is the point of
  measuring it.
* **The empty lower band.** §AB2(c) records it and expressly does not rule on
  it. Moving the support line down consumed some of it as a side effect; the
  before and after are both measured here so the side effect is visible and is
  not mistaken for an answer.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import pathlib
import shutil
import tempfile

import pymupdf
import pytest

from apps.ire import back_panel
from apps.ire import compose_dropper
from apps.ire import unit_analysis as ua
from apps.ire.compose_dropper import (NAME_LEADING_EM,
                                      NAME_LEADING_INCUMBENT_EM, NET_LEAD_EM,
                                      SUPPORT_LEAD_EM, _front_typography)
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.front_hierarchy import ruled_front_hierarchy
from apps.ire.graph import Color, Document, Group, TextRun
from apps.ire.tests.test_back_panel import _FRONT_NAME_LINES, _FRONT_RECORD, _FRONT_ZONE, _GEOMETRY

# this file's renders and mutants live in a folder of its own, removed when the run ends (the clean-up of 2026-10-04:
# they were fixed /tmp/_wiu_* files that outlived every run)
_WIU_TMP = tempfile.mkdtemp(prefix="wiu_")
import atexit  # noqa: E402
atexit.register(shutil.rmtree, _WIU_TMP, True)

K = 72.0 / 25.4
ZONE_W = float(_FRONT_ZONE["width"])          # 22.0 mm
ZONE_H = float(_FRONT_ZONE["height"])         # 42.3 mm
RULED_PT = 9.0
HERO_S = 1.22
FLAT_S = 34.0 / ZONE_W

#: Read off the PRE-WI-U artefact by `tools/wiu_front_collision.py`. These are
#: what the negative control compares against; they are transcribed here so the
#: test states the prior state rather than assuming the reader remembers it.
PRE = {
    "BBROSE":    (6.0, 9.885, 18.115, 6.236),
    "Rose":      (9.0, 10.396, 17.604, 12.296),
    "Damascena": (9.0, 5.286, 22.714, 21.836),
}
PRE_COLLISION_MM = -1.389
PRE_HERO_CLEAR_MM = 0.891      # the same defect at panel 5's 1.22x, pre-WI-U
CLEAN_6_5_MM = 1.5194          # the clearance 1.175 em was set to reproduce

#: §AC1 — WHAT THE LEADING RULING DID TO WI-U'S PINS, AS ONE NUMBER.
#:
#: `PRE` is a transcription of the PRE-WI-U artefact and stays exactly as
#: measured; re-transcribing it would delete the state WI-U was compared
#: against. What §AC1 changed is the leading, so every run BELOW the name
#: block's first line rises by the same distance, and that distance is
#: derived from the two named constants rather than typed in:
#:
#:     (3.0047244094488192 - 2.0) x 9.0 pt x MM_PER_PT = 3.190 mm
#:
#: WI-U's claim — *the support line moved and the NAME did not* — is not
#: weakened by this and is not allowed to be: the size and both horizontal
#: extents of all three runs are still asserted against `PRE` unchanged, and
#: `Rose`, the first line, is still asserted at its `PRE` baseline to the
#: micron. Only the runs BELOW the first name line are permitted to have
#: moved, all by this one figure, which is the rigidity WI-U built.
#:
#: The conversion is `back_panel.MM_PER_PT` and NOT the `(25.4 / 72.0)` that
#: two older lines in this file still spell out, because the first draft of
#: this constant used the bare ratio and WI-T's analyser reported it as an
#: eighth finding — MM_FROM_PT, correctly, since a bare ratio carries no units
#: and it could see a `_PT` source reaching an `_MM` sink with no conversion
#: it recognised in between. WI-V hit the identical thing and set the
#: precedent (`test_wit_unit_analysis.py:626-633`): repair at the source, do
#: not admit it to the register as a fourth false positive. Classifying it
#: costs the instrument its edge permanently; naming the constant costs
#: nothing. The two older bare ratios below are NOT repaired here — they are
#: WI-U's lines, they do not fire, and touching them would be a chained fix.
AC1_LEADING_SHIFT_MM = ((NAME_LEADING_INCUMBENT_EM - NAME_LEADING_EM)
                        * RULED_PT * back_panel.MM_PER_PT)

#: Which of the three `PRE` runs sit below the first name line. `BBROSE` and
#: `Rose` are above the leading and must not have moved by so much as a micron.
AC1_MOVED_BY = {"BBROSE": 0.0, "Rose": 0.0,
                "Damascena": AC1_LEADING_SHIFT_MM}

#: §BH50(b), OWNER RULED 2026-09-13 — the support line and the net content are set at the 5.0 pt floor
#: and RE-LAID (compose_dropper.SUPPORT_LEAD_EM 1.365, NET_LEAD_EM 1.156) so the two clearances this file
#: pins are kept. The re-lay's own displacement of the two box tops, measured off the shipped PDF, is
#: named here the way `AC1_LEADING_SHIFT_MM` is, so WI-U's displacement stays asserted as the quantity it
#: always was: the support line's top holds (to 0.0003 mm — the re-derived lead lowers the baseline by
#: exactly the ascent the larger size adds), and the net content's top drops by 0.7693 mm (the support
#: line's larger descent and the re-derived net lead, less the net's own larger ascent).
BH50B_RELAY_MOVED_BY = {"N I G": 0.0, "30 ml": 0.7693}
#: ...the empty lower band the re-lay consumed, measured the same way (16.470 -> 14.739 mm).
BH50B_RELAY_BAND_MM = 1.731
#: §BH67(c)2, OWNER RULED 2026-09-24: "Derive both from the product record; where the record is silent, print
#: nothing." The composer no longer holds the dropper's descriptor or its net content, so the words every reading in
#: this file was measured with are handed in the way the production call hands in a product record's — as
#: `descriptor` and `net_content` — and every measured number stands unchanged. They are the WI-U instrument's
#: inputs, not any product's copy: the product the words were written for, BBR-SK-201, records neither in this form.
WIU_DESCRIPTOR = _FRONT_RECORD["descriptor"]
WIU_NET_CONTENT = _FRONT_RECORD["net_content"]
#: §BH68(d), OWNER RULED 2026-09-24: the front's name is the product record's, and `FRONT_NAME_LINES` — the module's
#: "Rose" / "Damascena" — is gone. WI-U's instrument measures THAT front, so it now hands the name in: to the lockup as
#: its two lines, and to the sheet as the ruled hierarchy's name tier, which `wrap_name` breaks into the same two lines.
WIU_NAME_LINES = _FRONT_NAME_LINES
WIU_NAME_HIERARCHY = [{"text": "Rose Damascena", "kind": "product_name", "rel": 1.0}]
#: the sizes and the net lead the historical readings below were taken at
BEFORE_BH50B_SUPPORT_PT = 3.4
NET_LEAD_EM_BEFORE_BH50B = 0.866


def _spans(pdf):
    d = pymupdf.open(pdf)
    rows = []
    for blk in d[0].get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for sp in line.get("spans", []):
                if sp["text"].strip():
                    rows.append((sp["text"].strip(), sp["size"],
                                 [v / K for v in sp["bbox"]]))
    d.close()
    return sorted(rows, key=lambda r: r[2][1])


def render(producer=_front_typography, s=1.0, nm=RULED_PT, tmp=None):
    """The producer called as the sheet calls it, measured off its own PDF.

    Never recomputed from the composer's intent — §Z1's lesson was that a claim
    contradicting the artefact is a finding about your instrument.
    """
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    kids, placements, _lg, _zr = producer(
        _GEOMETRY, zone, 3.0, 3.0 - closure_h * s, s, None,
        prefix="t-", name_min=nm, descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT,
        name_lines=WIU_NAME_LINES)                  # §BH68(d): the name is handed in, as the sheet hands in the record's
    doc = Document(title="t", page_w=ZONE_W * s + 6, page_h=ZONE_H * s + 6,
                  root=Group(name="T", role="decoration",
                             children=list(kids)))
    path = str(tmp or _WIU_TMP + "/_wiu_test.pdf")
    emit_pdf_ai(doc, path)
    return _spans(path), placements


def run(rows, prefix):
    return next(r for r in rows if r[0].startswith(prefix))


def gap(rows, a, b):
    """Vertical clear space between two runs, from the inked boxes."""
    return run(rows, b)[2][1] - run(rows, a)[2][3]


@pytest.fixture(scope="module")
def shipped():
    return render()[0]


@pytest.fixture(scope="module")
def mutant():
    """The real producer's source with the two placement lines put back.

    A MUTATION, in the shape WI-T used: the shipped source, textually reverted
    at one point, executed, measured. Built once as a fixture because the two
    tests below both need it — an earlier draft had the second test read a
    ``/tmp`` file the first test happened to have written, which is an ordering
    dependency that passes under ``-p no:randomly`` and is a lie under anything
    else.
    """
    src = pathlib.Path(__file__).parent.parent.joinpath(
        "compose_dropper.py").read_text()
    # §AC1(e) reshaped the two lines above these: the last name baseline is now
    # computed once as `last_baseline` because the block can hold more than two
    # lines. The mutation's target is unchanged in meaning — replace the
    # name-anchored placement with the zone fractions — and this guard sentence
    # is why that reshape could not pass silently.
    old = ("    support_y = last_baseline + em_mm * SUPPORT_LEAD_EM\n"
           "    net_y = support_y + em_mm * NET_LEAD_EM\n")
    assert old in src, "the fix's shape changed; update this mutation"
    path = pathlib.Path(_WIU_TMP + "/_wiu_mutant.py")
    path.write_text(src.replace(old, "    support_y = zy + zh * 0.545\n"
                                     "    net_y = zy + zh * 0.61\n"))
    spec = importlib.util.spec_from_file_location("_wiu_mutant", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mutant_gap(mod, s, leading=None, support_pt=None):
    """The mutant's Damascena→support clearance at scale `s`.

    `leading` overrides the mutant module's own copy of `NAME_LEADING_EM`, so
    the historical readings can be reproduced under the leading they were taken
    at rather than asserted against a value §AC1 has since changed.
    `support_pt` does the same for the support line's size, which §BH50(b)
    raised from 3.4 to 5.0 pt: a larger run's taller box sits one ascent closer
    to the name, so every mutant reading moves by it and the mechanism does not.
    """
    was, was_pt = mod.NAME_LEADING_EM, mod.SUPPORT_PT
    if leading is not None:
        mod.NAME_LEADING_EM = leading
    if support_pt is not None:
        mod.SUPPORT_PT = support_pt
    try:
        rows, _ = render(producer=mod._front_typography, s=s,
                         tmp=_WIU_TMP + f"/_wiu_mutant_{s:.4f}_{leading}_{support_pt}.pdf")
        return gap(rows, "Damascena", "N I G")
    finally:
        mod.NAME_LEADING_EM, mod.SUPPORT_PT = was, was_pt


class TestTheCollisionIsGoneAndTheNameIsUntouched:
    """§AB2(a): move the support line, do not shrink the name. Both halves."""

    def test_the_overlap_that_was_ruled_a_placement_bug_is_gone(self, shipped):
        assert PRE_COLLISION_MM < 0                    # the premise
        g = gap(shipped, "Damascena", "N I G")
        assert g > 0, f"still overlapping by {-g:.3f} mm"
        assert round(g, 3) == 1.518

    def test_no_run_on_the_front_overlaps_any_other(self, shipped):
        """The stated defect was one pair. A fix that clears that pair by
        pushing something into the pair below it is not a fix, so every
        adjacent pair is checked and not just the named one."""
        bad = [(a[0][:18], b[0][:18], b[2][1] - a[2][3])
               for a, b in zip(shipped, shipped[1:])
               if b[2][1] - a[2][3] <= 0]
        assert bad == []

    def test_the_name_did_not_shrink_and_did_not_move(self, shipped):
        """The assertion §AB2(a) actually turns on.

        Size and both horizontal extents against the pre-WI-U artefact. If the
        collision had been cleared the forbidden way — a smaller name — every
        row here would move, and the first one would move most.

        §AC1 UPDATE. The baseline column is now asserted against `PRE` PLUS a
        DECLARED shift, and the declaration is per-run rather than global:
        `BBROSE` and `Rose` are required to be at their pre-WI-U baselines to
        the micron, exactly as before, and only `Damascena` is permitted to
        have moved. A blanket tolerance here would have let the leading ruling
        hide a size change, which is the one thing this test exists to catch —
        so the size and the two horizontal extents stay pinned at `PRE` with
        no allowance at all, because §AC1 authorised a LEADING and nothing
        else about the type.
        """
        for text, (pt, x0, x1, y0) in PRE.items():
            got = run(shipped, text)
            assert got[1] == pytest.approx(pt, abs=1e-6), text
            assert got[2][0] == pytest.approx(x0, abs=1e-3), f"{text} x0"
            assert got[2][2] == pytest.approx(x1, abs=1e-3), f"{text} x1"
            assert got[2][1] == pytest.approx(y0 - AC1_MOVED_BY[text],
                                              abs=1e-3), f"{text} top"

    def test_only_the_two_runs_the_ruling_named_moved(self, shipped):
        """Everything above the support line is byte-identical; the support
        line and the net content are exactly what §AB2(a) said to move.

        §AC1 UPDATE, AND IT IS WI-U'S FIX BEING PAID FOR. WI-U put both of
        these baselines on the name block's LAST line so the leading could
        change without dragging the stack below it apart. §AC1 changed the
        leading, so both rose by `AC1_LEADING_SHIFT_MM` and by nothing else —
        and the net WI-U displacement, +2.907 mm, is still asserted as the
        quantity it always was, now with the leading term named beside it
        instead of folded into a new literal. Re-baselining these two numbers
        to what they happen to read today would have deleted the evidence that
        the two effects are separable, which is the whole content of WI-U.
        """
        assert {t for t in PRE} == {"BBROSE", "Rose", "Damascena"}
        wiu_only = 2.907                       # WI-U's own displacement
        assert wiu_only > AC1_LEADING_SHIFT_MM - 0.5   # they are comparable
        for text, pre_top in (("N I G", 24.771), ("30 ml", 27.672)):
            got = run(shipped, text)[2][1] - BH50B_RELAY_MOVED_BY[text]
            assert round(got - pre_top + AC1_LEADING_SHIFT_MM, 3) == wiu_only
        # ...and they moved by the SAME amount, because the block below the
        # name is rigid. A support line that moved without the net content
        # would have opened a new gap and closed another. §BH50(b): the
        # re-lay's own displacement is named beside WI-U's and §AC1's.
        assert (round(run(shipped, "N I G")[2][1]
                      - BH50B_RELAY_MOVED_BY["N I G"] - 24.771, 3)
                == round(run(shipped, "30 ml")[2][1]
                         - BH50B_RELAY_MOVED_BY["30 ml"] - 27.672, 3)
                == round(wiu_only - AC1_LEADING_SHIFT_MM, 3) == -0.283)


class TestTheClearanceIsBorrowedFromTheOnlyCleanRender:
    """§AB0(a) — the value is a measurement, so it is checked as one."""

    def test_it_reproduces_the_6_5_pt_clearance_the_owner_called_clean(
            self, shipped):
        got = gap(shipped, "Damascena", "N I G")
        assert got == pytest.approx(CLEAN_6_5_MM, abs=0.002), (
            f"1.175 em was chosen to reproduce {CLEAN_6_5_MM} mm and "
            f"delivers {got:.4f} mm")

    def test_the_support_to_net_relationship_was_carried_across_unchanged(
            self, shipped):
        """0.866 em restates the old ``(0.61 - 0.545) * 42.3`` distance.

        The one relationship in this block that was never broken is preserved,
        so the fix cannot be accused of re-tuning it. The residual is stated
        rather than hidden in a tolerance: the exact carry-across ratio is
        0.8659842519685039 and the constant is its THREE-DECIMAL rounding, so
        the net-content line sits 5.0e-5 mm — fifty nanometres, four orders of
        magnitude below the emitter's own rounding — below where it sat. An
        earlier draft of this test asserted ``abs=5e-5`` and failed, because
        the residual is 5.00e-5 and not 4.99e-5; the tolerance was the wrong
        number, not the constant, and the honest repair is to name the ratio
        the constant rounds rather than to widen the window until it passes.
        """
        exact = (0.61 - 0.545) * ZONE_H / (RULED_PT * (25.4 / 72.0))
        # §BH50(b): 0.866 em carried the relationship at 3.0 / 3.4 pt and is
        # history now; at 5.0 pt the same clearance takes 1.156 em, the nearest
        # a three-decimal em lands (1.2679 mm), asserted as the clearance below
        assert round(exact, 3) == NET_LEAD_EM_BEFORE_BH50B
        assert NET_LEAD_EM == 1.156
        residual = abs(NET_LEAD_EM_BEFORE_BH50B * RULED_PT * (25.4 / 72.0)
                       - (0.61 - 0.545) * ZONE_H)
        assert residual == pytest.approx(5.0e-5, abs=1e-6), (
            f"carry-across residual is {residual:.3e} mm")
        assert gap(shipped, "N I G", "30 ml") == pytest.approx(1.267,
                                                               abs=1e-3)

    def test_the_two_constants_are_em_of_the_name_and_not_of_the_zone(self):
        """The dimensional claim, stated so it cannot quietly stop being true.
        Both are pure ratios applied to a point size through MM_PER_PT."""
        assert 0.0 < SUPPORT_LEAD_EM < 3.0 and 0.0 < NET_LEAD_EM < 3.0
        assert ua.UnitAnalyser(
            "compose_dropper.py",
            pathlib.Path(__file__).parent.parent.joinpath(
                "compose_dropper.py").read_text()).run() == []


class TestTheMechanismIsGoneAndNotJustItsSymptom:
    """The defect was scale-dependence. Its absence is the deliverable."""

    @pytest.mark.parametrize("s", [1.0, HERO_S, FLAT_S, 0.68, 1.85])
    def test_the_clearance_is_now_the_same_at_every_scale(self, s):
        """Pre-WI-U this same sweep read −1.389 / +0.891 / +7.172 — three
        different layouts wearing one name. The panel scale is a DRAWING
        instruction and it may not change the artwork's proportions.
        """
        rows, _ = render(s=s)
        assert gap(rows, "Damascena", "N I G") == pytest.approx(1.518,
                                                                abs=1e-3)
        assert run(rows, "Damascena")[1] == RULED_PT

    def test_restoring_the_fraction_brings_the_scale_dependence_back(
            self, mutant):
        """The negative control, re-pointed at the MECHANISM after §AC1.

        THIS TEST USED TO ASSERT A SIGN AND THAT WAS THE WRONG ASSERTION.
        It required the mutant to reproduce −1.389 mm at s=1.0, and after §AC1
        set the leading to 2.0 em it read +1.801 mm and failed. The temptation
        is to call that a repair and re-baseline. It is not one. Nothing about
        the mutant changed; the name block simply sits 3.190 mm higher, so the
        fixed fraction it is measured against no longer catches it at 1.0.

        A control that turns on the sign of one gap at one scale was always
        testing a symptom. The defect this file exists to make impossible is
        SCALE-DEPENDENCE — a physical leading measured against a fraction of a
        drawn zone — so that is what is asserted: across the same five scales
        the shipped code holds to three microns, the mutant swings 12.1 mm, and
        it is still negative somewhere inside the sweep.
        """
        scales = [1.0, HERO_S, FLAT_S, 0.68, 1.85]
        # §BH50(b): the pinned readings were taken with the support line at 3.4 pt
        mut = [mutant_gap(mutant, s, support_pt=BEFORE_BH50B_SUPPORT_PT)
               for s in scales]
        real = [gap(render(s=s, tmp=_WIU_TMP + f"/_wiu_real_{s:.4f}.pdf")[0],
                    "Damascena", "N I G") for s in scales]

        assert max(real) - min(real) < 1e-5, (
            f"the shipped clearance moved with the panel scale: {real}")
        assert max(mut) - min(mut) == pytest.approx(12.125, abs=1e-3), (
            f"the mutant's spread across the sweep is the defect: {mut}")
        assert min(mut) < 0 < max(mut), (
            f"the mutant must still collide somewhere in the sweep: {mut}")
        # ...and where it collides is now 0.68, not 1.0.
        assert mut[scales.index(0.68)] == pytest.approx(-1.515, abs=1e-3)
        assert mut[scales.index(1.0)] == pytest.approx(1.801, abs=1e-3)
        # ...and at the shipped 5.0 pt the defect is the same defect: the same
        # spread, still colliding inside the sweep, every reading one ascent lower
        at_floor = [mutant_gap(mutant, s) for s in scales]
        assert max(at_floor) - min(at_floor) == pytest.approx(12.125, abs=1e-3)
        assert min(at_floor) < 0 < max(at_floor)

    def test_and_the_historical_readings_reproduce_under_their_own_leading(
            self, mutant):
        """PRE_COLLISION_MM is not stale and is not deleted — it is CONDITIONAL.

        −1.389 mm and +0.891 mm were measured at the incumbent 3.0047 em. Run
        the mutant at the leading those numbers were taken under and it returns
        them to a thousandth of a millimetre, which is the strongest available
        statement that §AC1 changed the leading and touched nothing else in
        this block. Re-baselining the constants to what the mutant reads today
        would have thrown away exactly this check.
        """
        inc = NAME_LEADING_INCUMBENT_EM
        pt = BEFORE_BH50B_SUPPORT_PT       # §BH50(b): and the size they were taken at
        assert mutant_gap(mutant, 1.0, leading=inc, support_pt=pt) == \
            pytest.approx(PRE_COLLISION_MM, abs=1e-3)
        assert mutant_gap(mutant, HERO_S, leading=inc, support_pt=pt) == \
            pytest.approx(PRE_HERO_CLEAR_MM, abs=1e-3)

    def test_and_ac1_would_have_hidden_this_bug_deeper_not_fixed_it(
            self, mutant):
        """A FINDING, recorded and not acted on, in the §AB0(a) shape.

        §AB2 diagnosed the concealment precisely: the defective code cleared by
        +0.891 mm at panel 5's 1.22× and overlapped by −1.389 mm at 1:1, *"the
        sheet concealed the defect by never drawing the scale that has it"*.
        Measure the same concealment at §AC1's leading and it is WORSE. The
        zero-crossing has moved from between 0.68 and 1.0 — 1:1, the only scale
        that prints — down below 0.68, so the unfixed code would have looked
        clean at every scale the sheet actually draws.

        The order the two work items landed in is therefore load-bearing. Had
        §AC1 preceded WI-U, the front collision would have been invisible to
        the render that found it. Nothing is fixed here; WI-U already removed
        the mechanism, and this states what the mechanism would have cost had
        it survived one more sprint.
        """
        assert mutant_gap(mutant, 1.0) > 0                    # +1.801
        assert mutant_gap(mutant, HERO_S) > 0                 # +4.081
        assert mutant_gap(mutant, 0.68) < 0                   # −1.515
        # the leading is the only thing that moved the crossing: same mutant,
        # same scale, the incumbent leading, and 1.0 is negative again.
        assert mutant_gap(mutant, 1.0, leading=NAME_LEADING_INCUMBENT_EM) < 0


class TestThePlacementRecordFollowsTheArtwork:
    """The decoration placements are derived now, not hand-matched."""

    def test_the_recorded_placement_tracks_the_run_it_describes(self):
        rows, placements = render()
        support = [p for p in placements if p["kind"] == "support_text"]
        assert len(support) == 3            # BBROSE, support line, net content
        ny = support[1]["ny"] * ZONE_H + 3.0
        assert ny == pytest.approx(run(rows, "N I G")[2][1], abs=0.35), (
            "the placement record and the run it describes have drifted")


class TestPanelEightConformsToPanelFive:
    """§AB2(d) — one spelling, and it is panel 8 that conforms."""

    def test_every_front_on_the_sheet_sets_the_name_at_the_ruled_size(self):
        """Pre-WI-U the sheet drew the front twice at two different type
        programmes and called both the front — panel 5 at the 9.0 default and
        panel 8 at an explicit 6.5. §AA2 recorded the disagreement; §AB2(d)
        ruled it.
        """
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_back_panel import (_BACK_ZONE, _LIVE,
                                                    _METHODS)
        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name="Rose Damascena", sku="X",
            back_sections=_LIVE, revision_status="WI-U", methods_record=_METHODS,
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)
        emit_pdf_ai(doc, _WIU_TMP + "/_wiu_sheet.pdf")
        sizes = {round(r[1], 3) for r in _spans(_WIU_TMP + "/_wiu_sheet.pdf")
                 if r[0].startswith("Damascena")}
        assert sizes == {RULED_PT}, (
            f"the sheet still disagrees with itself about the front: {sizes}")

    def test_the_ruling_exposed_a_hierarchy_gate_that_misread_its_own_marker(
            self):
        """§AB0(c) — the defect the ruling UNCOVERED, separated from the ruling.

        Making panel 8 conform broke three container-confirmation tests, and a
        negative control (revert `compose_dropper.py`, re-run) proved WI-U was
        the cause. The cause is NOT the ruling. `validate_typography_hierarchy`
        identifies a product-name run by `startswith("product-name")`, which
        misses `flat-product-name-hero-1` — the specimen panel's second name
        line — so it fell through to `other` and was scored as *competing
        supporting copy*. Its sibling `flat-product-name-hero-0` escaped by
        accident, because its TEXT is "Rose" and the token test caught it.

        While panel 8 sat 2.5 pt below panel 5 the gate passed for the wrong
        reason: the misclassified line was merely shorter than the name. At one
        spelling the two are equal, `name_size <= max(support)` fires, and the
        gate reports that the name fails to dominate — itself.

        This test asserts the classification, not the symptom, so it stays
        meaningful if the sizes ever change again (§AB2(b) says they will).
        """
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.container_motif_fidelity import (
            NON_ARTWORK_TEXT_PREFIXES, validate_typography_hierarchy)
        from apps.ire.tests.test_back_panel import (_BACK_ZONE, _LIVE,
                                                    _METHODS)
        name = "Rose Damascena Night Repair Oil"
        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name=name, sku="X", back_sections=_LIVE,
            revision_status="WI-U", methods_record=_METHODS,
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)

        runs = [n for n, _ in doc.walk() if n.type == "text"]
        token = [r for r in runs if "rose" in str(r.text or "").lower()]
        names = [r for r in runs if r in token
                 or str(r.name).startswith("product-name")
                 or "-product-name" in str(r.name)]
        other = [r for r in runs if r not in names
                 and not str(r.name).startswith(NON_ARTWORK_TEXT_PREFIXES)]

        # BOTH lines of BOTH name blocks are the product name, on either panel
        assert {str(r.name) for r in names} >= {
            "product-name-hero-0", "product-name-hero-1",
            "flat-product-name-hero-0", "flat-product-name-hero-1"}
        # and none of them is scored as supporting copy
        assert not [r for r in other if "product-name" in str(r.name)]
        assert validate_typography_hierarchy(doc, name)["failures"] == []

    def test_but_the_repaired_gate_still_fails_a_genuinely_small_name(self):
        """The control on the repair — §AB0(c) again, pointed at my own fix.

        A gate that stops failing is not a gate. Widening the marker must not
        widen what PASSES, so the same sheet is re-scored with the name run
        down at 4.0 pt and the gate is required to bite. Without this, the
        repair above is indistinguishable from deleting the check.
        """
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.container_motif_fidelity import (
            PRODUCT_NAME_TOO_SMALL, validate_typography_hierarchy)
        # [his correction of 2026-10-07] the hot stamp CONFIRMED: only a confirmed method holds a label at its 6 pt
        from apps.ire.tests.test_back_panel import _BACK_ZONE, _LIVE
        from apps.ire.tests.test_back_panel import _CONFIRMED_METHODS as _METHODS
        name = "Rose Damascena Night Repair Oil"
        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name=name, sku="X", back_sections=_LIVE,
            revision_status="WI-U", methods_record=_METHODS,
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)
        for n, _ in doc.walk():
            if n.type == "text" and "product-name" in str(n.name):
                n.size_pt = 4.0
        assert PRODUCT_NAME_TOO_SMALL in validate_typography_hierarchy(
            doc, name)["failures"]

    def test_the_ruled_size_is_the_default_and_is_not_restated(self):
        """The ruling lives in the signature and at NO call site.

        Restating a default at one of two call sites is how the two drifted
        apart in the first place, so neither call site may pass ``name_min``
        at all — not 6.5, and deliberately not 9.0 either.

        THE INSTRUMENT IS NOT A GREP, AND THE FIRST DRAFT PROVED WHY. This
        test was first written as ``"name_min=6.5" not in src`` and it failed
        — on the COMMENT four lines above the call site, which explains in
        prose why the argument was removed. A substring scan cannot tell code
        from the sentence describing the code, so it reported the fix as
        absent while the fix was sitting right there. That is the same defect
        WI-T was built to remove, appearing in WI-T's own sprint, so the
        repair is the WI-T one: parse the file and ask the syntax tree.
        """
        path = pathlib.Path(__file__).parent.parent.joinpath(
            "compose_dropper.py")
        tree = ast.parse(path.read_text())

        passed_at_call_sites = [
            (n.lineno, kw.value)
            for n in ast.walk(tree) if isinstance(n, ast.Call)
            for kw in n.keywords if kw.arg == "name_min"]
        assert passed_at_call_sites == [], (
            "name_min is passed at "
            f"{[ln for ln, _ in passed_at_call_sites]}; the ruled size is the "
            "default and a call site that restates it can drift from it")

        defaults = [d.value for fn in ast.walk(tree)
                    if isinstance(fn, ast.FunctionDef)
                    and fn.name == "_front_typography"
                    for a, d in zip(fn.args.args[-len(fn.args.defaults):],
                                    fn.args.defaults)
                    if a.arg == "name_min"]
        assert defaults == [RULED_PT]
        # and the running function agrees with the file that was parsed
        assert (inspect.signature(_front_typography)
                .parameters["name_min"].default == RULED_PT)


class TestTheHeadroomAb2fAskedFor:
    """§AB2(f) — *"a limit that is only found by exceeding it is a limit
    nobody measured."*"""

    @staticmethod
    def width_mm(text, pt=RULED_PT, font="serif-bold"):
        doc = Document(title="w", page_w=400.0, page_h=20.0,
                       root=Group(name="W", role="decoration", children=[
                           TextRun(name="t", text=text, x=5.0, y=12.0,
                                   size_pt=pt, color=Color.from_hex("#3A2A30"),
                                   font=font, align="left")]))
        emit_pdf_ai(doc, _WIU_TMP + "/_wiu_width.pdf")
        return _spans(_WIU_TMP + "/_wiu_width.pdf")[0][2][2] - 5.0

    def test_the_instrument_agrees_with_the_production_path(self, shipped):
        """Before quoting a headroom, check the ruler against the artefact the
        composer actually produced."""
        assert self.width_mm("Damascena") == pytest.approx(
            run(shipped, "Damascena")[2][2] - run(shipped, "Damascena")[2][0],
            abs=1e-3)

    def test_the_headroom_is_four_and_a_half_millimetres(self, shipped):
        """The name's headroom to the ZONE — the outer bound since §BH50(g)(1); the verdict on the name is the
        safe area's (§BH50(g)(2)), pinned in test_the_product_name_is_front_copy_and_is_judged_like_any_other_run.
        Here the harness's untagged emission (legacy faces) is measured against the zone as history."""
        dam = run(shipped, "Damascena")
        used = dam[2][2] - dam[2][0]
        assert used == pytest.approx(17.428, abs=1e-3)
        assert ZONE_W - used == pytest.approx(4.572, abs=1e-3)

    def test_no_run_crosses_the_zone_at_the_ruled_size(self, shipped):
        """WI-M's claim that the measurement killed, re-checked rather than
        inherited: the name does NOT overflow horizontally — the ZONE, the outer
        bound since §BH50(g)(1); against the governing safe area the name's second
        line is over (§BH50(g)(2)), which its own test pins."""
        # §BH50(b): the support line is set at 5.0 pt now. This harness draws an
        # untagged document, so it measures in the legacy faces (NotoSans), where
        # the line is 22.174 mm and crosses the 22.0 mm zone by 0.087 mm a side;
        # the product never draws it there. The tagged sheet draws it in the role
        # map's Poppins-Regular, 21.504 mm, and the zone holds it: the composer's
        # own record says so, and that record is what reaches the spec sheet.
        for text, _pt, (x0, _y0, x1, _y1) in shipped:
            if text.startswith("N I G"):
                assert x1 - x0 == pytest.approx(22.174, abs=1e-3), text
                continue
            assert x0 >= 3.0 - 1e-6 and x1 <= 25.0 + 1e-6, text
        fit = _sheet().metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        support = next(r for r in fit["runs"] if r["name"] == "front-support")
        # §BH50(g)(1) (re-typed §BH53(a)): the zone is the OUTER BOUND, held; the governing safe area is
        # unmeasured on this harness zone (no safe_margin_mm), so the verdict is UNMEASURED, never HELD
        assert (support["face"], support["size_pt"], support["outer_bound_state"], support["state"]) == (
            "Poppins-Regular", 5.0, "HELD", "UNMEASURED")
        assert support["width_mm"] == pytest.approx(21.5036, abs=1e-4)
        assert support["spare_mm"] == pytest.approx(0.4964, abs=1e-4)
        assert fit["overruns"] == []

    def test_the_fit_is_total_and_measures_the_safe_area_beside_the_zone(self):
        """§BH50(f)(3), then §BH50(g)(1) (re-typed §BH53(a)): the verdict is
        against the zone's confirmed SAFE AREA, which governs; the zone is
        recorded beside it as the outer bound; the record carries its codes
        (the vertical axis unmeasured, with its cost); the hero name is
        measured verdict-free; a zone with no usable safe margin leaves the
        governing leg UNMEASURED — a code per run, never HELD."""
        fit = _sheet().metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        support = next(r for r in fit["runs"] if r["name"] == "front-support")
        # the harness's front zone carries no safe_margin_mm: the governing
        # safe-area leg is UNMEASURED on every run, and says so as a code
        assert fit["safe_area_mm"] is None and support["safe_area_state"] == "UNMEASURED"
        assert support["state"] == "UNMEASURED" and support["outer_bound_state"] == "HELD"
        # §BH50(g)(2): the name runs are judged like any other run — here unmeasured too, in walk order
        # THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — the vertical line names its reason where it
        # cannot measure; it read "CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical" until then
        assert fit["codes"] == ["CONTAINER_FRONT_COPY_FIT_UNMEASURED: product-name-hero-0 (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: product-name-hero-1 (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: front-support (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: front-net-content (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (the zone record carries no usable safe margin)"]
        assert fit["axis"].startswith("horizontal")
        assert fit["vertical"].startswith("UNMEASURED")
        assert [r["name"] for r in fit["name_runs"]] == [
            "product-name-hero-0", "product-name-hero-1"]
        assert all("width_mm" in r for r in fit["name_runs"])
        # task 52's own zone: 22.0 mm wide, safe margin 3.0 -> a 16.0 mm safe
        # area, which GOVERNS: the support line holds the outer bound and is
        # refused on the safe area by its millimetres; the net content is held
        with_margin = dict(_FRONT_ZONE, safe_margin_mm=3.0)
        doc = compose_dropper.compose_dropper_sheet(
            _GEOMETRY, zones=[with_margin], reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X", back_sections=None,
            revision_status="TEST", drawing_source="PARAMETRIC",
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)
        fit = doc.metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert fit["safe_area_mm"] == 16.0 and fit["safe_margin_mm"] == 3.0
        support = next(r for r in fit["runs"] if r["name"] == "front-support")
        net = next(r for r in fit["runs"] if r["name"] == "front-net-content")
        assert support["state"] == "EXCEEDS_SAFE_AREA" and support["safe_area_state"] == "OVER"
        assert support["outer_bound_state"] == "HELD" and support["spare_mm"] == pytest.approx(0.4964, abs=1e-4)
        assert support["spare_to_safe_area_mm"] == pytest.approx(-5.5036, abs=1e-4)
        assert net["state"] == "HELD" and net["safe_area_state"] == "INSIDE"     # inside the safe area: clean
        assert fit["safe_area_note"].startswith("GOVERNS") and "MEASURED, NOT RULED" in fit["safe_area_note"]
        assert fit["limit_source"].startswith("OWNER_TYPED — §BH50(g)(1)")
        # §BH50(g)(2): the product name is front copy — "Damascena" is refused on the safe area like the support
        # line, in the face and at the size the sheet draws it; "Rose" is inside
        hero = {r["name"]: r for r in fit["name_runs"]}
        assert (hero["product-name-hero-0"]["state"], hero["product-name-hero-1"]["state"]) == ("HELD", "EXCEEDS_SAFE_AREA")
        assert hero["product-name-hero-1"]["width_mm"] == pytest.approx(19.5897, abs=1e-4)
        assert fit["overruns"] == [{"code": compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA, "run": "product-name-hero-1", "over_mm": 3.5897, "limit_mm": 16.0}, {"code": compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA, "run": "front-support", "over_mm": 5.5036, "limit_mm": 16.0}]
        # THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — measured at print size on
        # this 42.3 mm zone, every run's ink is inside the safe band, so the vertical line that closed this list goes
        assert fit["codes"] == ["CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: product-name-hero-1 +3.5897 mm", "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: front-support +5.5036 mm"]
        assert {r["state"] for r in fit["vertical_runs"]} == {"HELD"}
        assert fit["name_note"].startswith("§BH50(g)(2)")

    def test_a_refused_face_is_not_drawn_and_an_empty_face_map_is_unmeasured_never_a_raise(self):
        """§BH50(f)(3): the fit used to substitute 'regular' for a role it
        lacked and raise KeyError on an empty map — a measuring instrument
        parking the reconstruction (aria.py), i.e. blocking exploration.
        Now a refused role's run reads NOT_DRAWN (the emitter skips it), an
        empty map reads UNMEASURED, both are codes at acceptance, and nothing
        raises."""
        from unittest import mock
        doc = _sheet()
        zone = _FRONT_ZONE
        with mock.patch("apps.ire.text_metrics.resolve_metric_faces", return_value={}):
            fit = compose_dropper.front_copy_fit(doc, zone)
        assert {r["state"] for r in fit["runs"]} == {"UNMEASURED"}
        assert f"{compose_dropper.FRONT_COPY_FIT_UNMEASURED}: front-support (UNMEASURED)" in fit["codes"]
        with mock.patch("apps.ire.text_metrics.resolve_metric_faces",
                        return_value={"heading": ("Poppins-Bold", "/x")}):
            fit = compose_dropper.front_copy_fit(doc, zone)
        assert {r["state"] for r in fit["runs"]} == {"NOT_DRAWN"}
        assert all(r["face"] is None for r in fit["runs"])
        assert f"{compose_dropper.FRONT_COPY_FIT_UNMEASURED}: front-net-content (NOT_DRAWN)" in fit["codes"]

    def test_a_placeholder_run_is_a_geometric_fact_never_copy_verified(self):
        """§BH50(f)(2)/(3): a front run drawn as a placeholder reads
        PLACEHOLDER — its width is measured and its copy is unwritten; it is
        never HELD."""
        from apps.ire.graph import TextRun
        doc = _sheet()
        for node, _ in doc.walk():
            if getattr(node, "name", "") == "front-net-content":
                node.text = "CONTENT_VERIFICATION_REQUIRED"
        fit = compose_dropper.front_copy_fit(doc, _FRONT_ZONE)
        net = next(r for r in fit["runs"] if r["name"] == "front-net-content")
        assert net["state"] == "PLACEHOLDER" and "width_mm" in net
        assert not any(c.startswith(compose_dropper.FRONT_COPY_EXCEEDS_ZONE) for c in fit["codes"])
        assert isinstance(doc.root, TextRun) is False

    def test_a_zone_that_cannot_hold_the_small_copy_at_the_floor_is_named(self):
        """§BH50(b): 'if the panel cannot hold them at 5.0 pt ... the composer
        says so by name', and nothing shrinks to fit. A 20.0 mm front zone
        cannot hold the 21.504 mm support line: it is still drawn at 5.0 pt and
        the overrun is named with its millimetres; the net content is held."""
        narrow = dict(_FRONT_ZONE, width=20.0)
        doc = compose_dropper.compose_dropper_sheet(
            _GEOMETRY, zones=[narrow], reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X", back_sections=None,
            revision_status="TEST", drawing_source="PARAMETRIC",
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)
        fit = doc.metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        # §BH50(g)(1): the zone is the outer bound and its code keeps its meaning; this harness zone has
        # no safe margin, so the governing verdict is UNMEASURED on both runs (a code each), never HELD
        assert [(r["name"], r["size_pt"], r["outer_bound_state"], r["state"]) for r in fit["runs"]] == [
            ("front-support", 5.0, "EXCEEDS_ZONE", "UNMEASURED"),
            ("front-net-content", 5.0, "HELD", "UNMEASURED")]
        assert fit["overruns"] == [{
            "code": compose_dropper.FRONT_COPY_EXCEEDS_ZONE,
            "run": "front-support", "over_mm": 1.5036, "limit_mm": 20.0}]
        # §BH50(f)(3): the overrun is a code — at acceptance, never a blocker
        assert fit["codes"] == ["CONTAINER_FRONT_COPY_FIT_UNMEASURED: product-name-hero-0 (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: product-name-hero-1 (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_EXCEEDS_ZONE: front-support +1.5036 mm", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: front-support (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: front-net-content (safe area unmeasured on this zone record)", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (the zone record carries no usable safe margin)"]

    def test_the_product_name_is_front_copy_and_is_judged_like_any_other_run(self):
        """§BH50(g)(2), re-typed §BH53(a): "THE PRODUCT NAME IS FRONT COPY — the
        floor and the safe area apply to it like any other run." On the task-52
        zone the name's second line is refused on the safe area by its
        millimetres with the outer bound held; the first line is inside; the
        §W2 floor walk already judges both name runs (printed on the product,
        declared) and finds them above 5.0 pt; the name's own floors stand."""
        from apps.ire import container_text_floor
        with_margin = dict(_FRONT_ZONE, safe_margin_mm=3.0)
        doc = compose_dropper.compose_dropper_sheet(
            _GEOMETRY, zones=[with_margin], reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X", back_sections=None,
            revision_status="TEST", drawing_source="PARAMETRIC",
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)
        fit = doc.metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        hero = {r["name"]: r for r in fit["name_runs"]}
        one = hero["product-name-hero-1"]
        assert (one["state"], one["outer_bound_state"], one["safe_area_state"]) == ("EXCEEDS_SAFE_AREA", "HELD", "OVER")
        assert one["size_pt"] == 9.0 and one["spare_to_safe_area_mm"] == pytest.approx(16.0 - one["width_mm"], abs=1e-4)
        assert hero["product-name-hero-0"]["state"] == "HELD"
        assert any(c.startswith(f"{compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA}: product-name-hero-1 +") for c in fit["codes"])
        # the floor: both name runs are in §W2's walk as copy printed on the product, at 9.0 pt above 5.0
        floor = container_text_floor.measure_text_floor(doc)
        judged = {r["node_name"]: r for r in floor["runs"]}
        assert {"product-name-hero-0", "product-name-hero-1"} <= set(judged)
        assert not any(judged[n]["below"] for n in ("product-name-hero-0", "product-name-hero-1"))
        # the name's own floors are not moved by (g)(2)
        from apps.ire import container_fidelity
        assert container_fidelity._MIN_NAME_PT == 8.0
        # without a margin nothing reads HELD for the name either
        bare = compose_dropper.front_copy_fit(doc, _FRONT_ZONE)
        assert {r["state"] for r in bare["name_runs"]} == {"UNMEASURED"}

    def test_the_safe_area_governs_and_the_zone_is_the_outer_bound(self):
        """§BH50(g)(1), re-typed §BH53(a): "THE 16.0 mm SAFE AREA GOVERNS THE
        FRONT … Record the 22.0 mm zone beside it as the outer bound." A run
        inside the zone and over the safe area is refused on the safe area by
        its millimetres, the zone held beside it; a run past both carries both
        codes, each true; a run inside the safe area is clean; the governing
        width's source is his typed word, on the record; and with no margin on
        the zone record nothing reads HELD."""
        narrow = dict(_FRONT_ZONE, width=20.0, safe_margin_mm=3.0)      # a 14.0 mm safe area
        doc = compose_dropper.compose_dropper_sheet(
            _GEOMETRY, zones=[narrow], reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X", back_sections=None,
            revision_status="TEST", drawing_source="PARAMETRIC",
            descriptor=WIU_DESCRIPTOR, net_content=WIU_NET_CONTENT)
        fit = doc.metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert fit["schema_version"] == "container_front_copy_fit/1.1"
        support = next(r for r in fit["runs"] if r["name"] == "front-support")
        net = next(r for r in fit["runs"] if r["name"] == "front-net-content")
        assert (support["state"], support["outer_bound_state"]) == ("EXCEEDS_SAFE_AREA", "EXCEEDS_ZONE")
        assert (net["state"], net["outer_bound_state"]) == ("HELD", "HELD")          # 13.4867 mm inside 14.0
        # §BH50(g)(2): the name is judged first in walk order — "Damascena" 19.5897 mm over the 14.0 mm safe area by
        # 5.5897, inside the 20.0 mm outer bound; "Rose" inside both
        assert fit["codes"] == [
            f"{compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA}: product-name-hero-1 +5.5897 mm",
            f"{compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA}: front-support +7.5036 mm",
            f"{compose_dropper.FRONT_COPY_EXCEEDS_ZONE}: front-support +1.5036 mm"]
        # THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — every run of this 42.3 mm
        # zone is inside its safe band at print size, so the vertical line that closed this list goes
        assert {r["state"] for r in fit["vertical_runs"]} == {"HELD"}
        assert [(o["code"], o["run"]) for o in fit["overruns"]] == [
            (compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA, "product-name-hero-1"),
            (compose_dropper.FRONT_COPY_EXCEEDS_SAFE_AREA, "front-support"),
            (compose_dropper.FRONT_COPY_EXCEEDS_ZONE, "front-support")]
        assert "§BH50(g)(1)" in fit["limit"] and fit["limit_source"].startswith("OWNER_TYPED — §BH50(g)(1)")
        assert "outer bound" in fit["outer_bound"].lower()
        # the verdict moved: a run between the safe area and the zone read HELD before §BH53 and is refused
        # now, the zone held beside it — task 52's own case
        wide = dict(_FRONT_ZONE, safe_margin_mm=3.0)                             # 22.0 mm, a 16.0 mm safe area
        fit2 = compose_dropper.compose_dropper_sheet(
            _GEOMETRY, zones=[wide], reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X", back_sections=None,
            revision_status="TEST", drawing_source="PARAMETRIC", descriptor=WIU_DESCRIPTOR,
            net_content=WIU_NET_CONTENT).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        s2 = next(r for r in fit2["runs"] if r["name"] == "front-support")
        assert (s2["safe_area_state"], s2["state"], s2["outer_bound_state"]) == ("OVER", "EXCEEDS_SAFE_AREA", "HELD")
        # the safe-area verdict is decided by the zone record's margin and nothing else: no margin, no HELD
        assert {r["state"] for r in compose_dropper.front_copy_fit(doc, _FRONT_ZONE)["runs"]} == {"UNMEASURED"}

    def test_the_limit_is_millimetres_and_a_character_count_is_a_bad_proxy(
            self):
        """The useful half of the answer, and the reason it is not "12 chars".

        Twenty-six ``i`` fit inside 22.0 mm and only seven ``m`` do — the same
        limit is 3.7x longer in characters depending on which characters. Any
        spec written as a character count is therefore wrong by up to that
        factor, so the limit goes in the queue in MILLIMETRES with the
        character counts underneath it as illustration only.

        BOTH BOUNDARIES ARE ASSERTED, IN BOTH DIRECTIONS. A first draft of
        this test asserted that seven ``m`` OVERFLOW; seven ``m`` are 20.780
        mm and fit comfortably. The tool had printed 7 and 26 as the longest
        counts that FIT and the test read them as the shortest that fail, so
        the assertion tested a claim the measurement never made. Pinning the
        pass AND the fail on each side is what makes that mistake impossible
        to repeat — and it is §AB0(a) applied to my own arithmetic: only a
        different measurement moves a measured quantity.
        """
        assert self.width_mm("m" * 7) == pytest.approx(20.780, abs=1e-3)
        assert self.width_mm("m" * 8) == pytest.approx(23.749, abs=1e-3)
        assert self.width_mm("m" * 7) <= ZONE_W < self.width_mm("m" * 8)
        assert self.width_mm("i" * 26) == pytest.approx(21.298, abs=1e-3)
        assert self.width_mm("i" * 27) == pytest.approx(22.117, abs=1e-3)
        assert self.width_mm("i" * 26) <= ZONE_W < self.width_mm("i" * 27)
        assert 26 / 7 > 3.7                 # the size of the proxy's error
        # every real single-word candidate tested fits; the first overflow is
        # a TWO-word name, which is a line-breaking question and not a width
        # one, and nothing in the producer breaks lines.
        assert self.width_mm("Frankincense") == pytest.approx(19.768,
                                                              abs=1e-3)
        assert self.width_mm("Rosa Centifolia") > ZONE_W

    def test_but_the_front_does_not_render_the_skus_name_at_all(self):
        """RECORDED, NOT FIXED — §AB4(c), NOW HALF-DISCHARGED BY §AC1(e).

        §AB2(f) wants the next SKU to meet a known limit. When WI-U wrote this
        it could not meet any limit: ``_front_typography`` took no product-name
        argument at all, ``product_name`` reached the document title and
        nothing else, and the two front lines were the literals "Rose" and
        "Damascena". The headroom above was a real measurement of a mechanism
        that did not exist — worth knowing BEFORE someone wired the two
        together and discovered the limit by exceeding it, which is exactly the
        outcome §AB2(f) is trying to avoid.

        AND THE FINDING WAS WORSE THAN THE ONE I FIRST WROTE DOWN. This test
        first asserted ``"product_name" not in front`` and failed, on
        ``place("product_name", 0.29, 0.24)``: the PLACEMENT RECORD — the
        machine-readable artefact downstream consumers read — names that block
        "product_name", while the artwork underneath it contained a hard-coded
        one. The record was not merely silent about the SKU, it asserted a
        binding that was not there.

        WHAT §AC1(e) MOVED, AND WHAT IT POINTEDLY DID NOT. The name is now a
        parameter — that was the named exception, and it exists because
        §AC1(d)'s descender control is impossible without it. So half of this
        finding is discharged and the assertions below say so by MEASURING the
        new shape rather than by being deleted. The other half stands
        UNCHANGED and is the half that matters to §AB2(f): the sheet still
        does not pass its `product_name` to the front, so the drawn name is
        still a default that no SKU can reach, and the placement record still
        claims a binding that is not made. Deleting a finding because part of
        it was fixed is how the remaining part stops being counted.

        AND THE DAY CAME. Leg (3) below used to assert that neither call site
        passes `name_lines`, and said in terms *"so it flips the day someone
        wires it."* §BB7(g)(a) is that day: `hierarchy_lines` now arrives at the
        sheet and is destructured into both panels. The test is reconciled to
        the new shape rather than deleted, and the reconciliation is NOT a
        weakening — leg (3) got longer, because there are now two properties to
        hold where there was one. It asserts that BOTH call sites are fed, from
        the SAME pair of locals (the §AB2(d) property, in the only form an AST
        can carry), and that the thing feeding them is `hierarchy_lines` and not
        `product_name`.

        WHY THE FINDING IS STILL OPEN AFTER BEING PLUMBED. The mechanism exists
        end to end and no production caller uses it:
        `targets/container/__init__.py` passes no `hierarchy_lines`. That is the
        owner's reservation — the dropper front carries a DIFFERENT product's
        copy from the container's ruled `FACIAL SERUM`, and he ruled that
        choosing between them is *"a measured proposal to bring back, not a
        decision to make."* So §AB2(f)'s question — can the next SKU reach the
        front — has moved from "no, there is no path" to "yes, and the path is
        deliberately unwired pending a ruling". Leg (4) is untouched: the
        placement record still claims a binding no shipping caller makes.
        """
        path = pathlib.Path(__file__).parent.parent.joinpath(
            "compose_dropper.py")
        src = path.read_text()
        tree = ast.parse(src)
        fn, = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_front_typography"]

        # (1) DISCHARGED by §AC1(e): a parameter now carries name lines in,
        #     and it is a plain positional-or-keyword arg with a default, so
        #     every existing call site keeps working untouched.
        assert "name_lines" in {a.arg for a in fn.args.args}
        assert not fn.args.kwonlyargs
        assert (inspect.signature(_front_typography)
                .parameters["name_lines"].default is None)

        # (2) the two literals left the function body and became ONE named
        #     module constant. Asserted in both directions: gone from the
        #     function, present at module scope. A test that only checked the
        #     first would pass on a version that had simply deleted them.
        #     §BB7(g)(a) gave the DESCRIPTOR the same treatment for the same
        #     reason, so the same pair of assertions is made about it.
        literals = {c.value for c in ast.walk(fn)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        assert not ({"Rose", "Damascena"} & literals)
        # §BH68(d) RULED THE SOURCE, and the constant is GONE rather than moved, as the descriptor's was: the name is
        # the product record's, handed in by the sheet, and a silent record prints no name
        assert not hasattr(compose_dropper, "FRONT_NAME_LINES")
        assert "N I G H T   R E P A I R   O I L" not in literals
        # §BH67(c)2 RULED THE SOURCE, and the constant is GONE rather than moved: the descriptor and the net content
        # are the product record's, handed in by the caller, and a silent record prints nothing. The net-content
        # literal left the function body the same day.
        assert not hasattr(compose_dropper, "FRONT_DESCRIPTOR")
        assert "30 ml / 1.01 fl. oz." not in literals
        assert (inspect.signature(_front_typography)
                .parameters["net_content"].default is None)
        assert (inspect.signature(_front_typography)
                .parameters["descriptor"].default is None)

        # (3) DISCHARGED BY §BB7(g)(a), AND THE ASSERTIONS GREW RATHER THAN
        #     SHRANK. Both call sites are fed, and — the §AB2(d) property —
        #     they are fed from the SAME two names, so the sheet cannot show
        #     two different fronts and call both the front. This is the AST
        #     form of that claim; `test_bb7g_both_panels_take_one_hierarchy`
        #     below is the emitted-ink form, and neither replaces the other.
        sheet, = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == "compose_dropper_sheet"]
        assert "product_name" in {a.arg for a in sheet.args.args
                                  } | {a.arg for a in sheet.args.kwonlyargs}
        assert "hierarchy_lines" in {a.arg for a in sheet.args.kwonlyargs}
        front_calls = [c for c in ast.walk(sheet) if isinstance(c, ast.Call)
                       and isinstance(c.func, ast.Name)
                       and c.func.id == "_front_typography"]
        assert len(front_calls) == 2
        fed = [{kw.arg: getattr(kw.value, "id", None) for kw in c.keywords}
               for c in front_calls]
        assert all(f.get("name_lines") == "front_lines"
                   and f.get("descriptor") == "front_descriptor" for f in fed)
        # §BH67(c)2: and the net content reaches both panels from ONE local too — the record's, never a literal
        assert all(f.get("net_content") == "net_content" for f in fed)

        # (3b) DISCHARGED BY §BH68(d), OWNER RULED 2026-09-24: "Derive it from the product record; print nothing where
        #      the record is silent." The ruled hierarchy still feeds the front where a caller supplies one; where none
        #      is supplied — the shipping path, which passes no `hierarchy_lines` — the sheet's own `product_name`, the
        #      record's name, fills the name slot, and an empty one fills it with nothing. Every SKU reaches the front.
        derive = [c for c in ast.walk(sheet) if isinstance(c, ast.Call)
                  and isinstance(c.func, ast.Name)
                  and c.func.id == "front_copy_from_hierarchy"]
        assert len(derive) == 1
        assert [a.id for a in derive[0].args
                if isinstance(a, ast.Name)] == ["hierarchy_lines"]
        target = pathlib.Path(__file__).parents[3].joinpath(
            "apps", "pipeline", "targets", "container", "__init__.py")
        calls = [c for c in ast.walk(ast.parse(target.read_text()))
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                 and c.func.id == "compose_dropper_sheet"]
        assert len(calls) == 1
        assert "hierarchy_lines" not in {kw.arg for kw in calls[0].keywords}
        assert "product_name" in {kw.arg for kw in calls[0].keywords}
        fills = [n for n in ast.walk(sheet) if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", None) == "front_lines" for t in n.targets)
                 and "product_name" in {getattr(x, "id", None) for x in ast.walk(n.value)}]
        assert len(fills) == 1                    # the record's name fills the slot the hierarchy leaves empty

        # (4) DISCHARGED BY §BH68(d): the placement record's product-name binding is now made — the record's name
        #     reaches it on the shipping path.
        keys = [c.args[0].value for c in ast.walk(fn)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                and c.func.id == "place" and c.args
                and isinstance(c.args[0], ast.Constant)]
        assert "product_name" in keys

    def test_and_the_placement_record_reuses_one_key_for_three_blocks(self):
        """RECORDED, NOT FIXED — §AB4(c), and NOT MINE.

        Three separate blocks — the logo fallback, the support line and the
        net content — all record themselves as ``support_text``, so the record
        cannot distinguish them and a consumer reading it by key gets whichever
        one it happens to iterate onto. This is pre-existing: the same three
        calls are present at ``e3d3d6a``, the commit WI-U's negative control is
        pinned to, with the literals 0.515 and 0.585. WI-U changed what two of
        those rows CONTAIN and deliberately not what they are CALLED, because
        renaming a key is a downstream-contract change and §AB4(c) forbids the
        chain. Pinned so the next sprint inherits a measurement, not a hunch.
        """
        path = pathlib.Path(__file__).parent.parent.joinpath(
            "compose_dropper.py")
        fn, = [n for n in ast.walk(ast.parse(path.read_text()))
               if isinstance(n, ast.FunctionDef)
               and n.name == "_front_typography"]
        keys = [c.args[0].value for c in ast.walk(fn)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                and c.func.id == "place" and c.args
                and isinstance(c.args[0], ast.Constant)]
        assert keys.count("support_text") == 3
        assert len(keys) == len(["logo", "support_text", "motif",
                                 "product_name", "support_text",
                                 "support_text"])


class TestTheEmptyLowerBandIsRecordedAndNotRuled:
    """§AB2(c) — seen, measured, and deliberately not answered."""

    def test_the_band_is_measured_before_and_after_the_move(self, shipped):
        """Moving the support line down consumed part of the empty band. That
        is a SIDE EFFECT of clearing the collision, not a response to §AB2(c),
        and the numbers are recorded together so it cannot later be read as
        though the question had been addressed.

        THREE STATES NOW, AND THE THIRD RUNS AGAINST THE RULING'S OWN STATED
        REASON. §AC1(c) argued for 2.0 em partly because 3.0047 "pushes the
        name apart at exactly the point where AB2(c) recorded that the
        composition has an unresolved vertical problem". Tightening the
        leading does not redistribute the composition — it lifts the whole
        block, support stack included, off the bottom of the zone. So the
        empty lower band GROWS by the full `AC1_LEADING_SHIFT_MM`, from 31.4%
        of the zone back to 38.9%, which is MORE than the 38.3% that §AB2(c)
        recorded as a problem in the first place.

        This does not touch the ruling: §AC1(a)'s metric floor kills 1.06 em
        whatever the band does, and 2.0 versus 3.0047 does not turn on this.
        It is recorded because the argument FOR 2.0 em cited this quantity,
        and the quantity moved the other way. §AB2(c) still reserves the
        vertical composition and nothing here answers it.
        """
        zone_bottom = 3.0 + ZONE_H
        now = zone_bottom - max(r[2][3] for r in shipped)
        before = zone_bottom - 29.113                  # pre-WI-U lowest ink
        after_wiu = 13.280                             # WI-U, at 3.0047 em
        after_ac1 = 16.470                             # §AC1, at 2.0 em
        assert before == pytest.approx(16.187, abs=0.01)
        assert after_ac1 == pytest.approx(after_wiu + AC1_LEADING_SHIFT_MM,
                                          abs=0.01)
        # §BH50(b), A FOURTH STATE: the re-lay at the 5.0 pt floor holds the
        # clearances above it, so the stack grows downward and consumes
        # BH50B_RELAY_BAND_MM of the band — a side effect, recorded, and not a
        # response to §AB2(c), which still reserves the vertical composition
        assert now == pytest.approx(after_ac1 - BH50B_RELAY_BAND_MM, abs=0.01)
        assert now == pytest.approx(14.739, abs=0.01)
        assert round(100 * before / ZONE_H, 1) == 38.3
        assert round(100 * after_wiu / ZONE_H, 1) == 31.4
        assert round(100 * after_ac1 / ZONE_H, 1) == 38.9
        assert round(100 * now / ZONE_H, 1) == 34.8
        # the band is now SMALLER again than the state §AB2(c) called a problem
        assert now < before

    def test_and_nothing_was_added_to_fill_it(self, shipped):
        """Five runs before, five runs after. §AB2(c) reserves the decision,
        so the temptation to put something in the gap is left untouched."""
        assert len(shipped) == 5


# ---------------------------------------------------------------------------
# §BB7(g)(a) — the third composer is plumbed, and the source is not chosen
# ---------------------------------------------------------------------------

def _sheet(**kw):
    """One composed dropper sheet, DB-free, at the live front geometry."""
    back_zone = {"zone_id": "z-back", "zone_type": "BACK_PRINT_ZONE",
                 "x": 0, "y": 0, "width": 22, "height": 36}
    # §BH67(c)2: the record's two lines arrive as the caller's words — the WI-U words unless a test passes others,
    # or None, a silent record
    # §BH68(d): and the front's NAME is the record's too. These tests measure the WI-U front, whose name is the two
    # lines "Rose" / "Damascena" — so they hand that name in as the ruled hierarchy's name tier unless a test passes its
    # own; `product_name` moved into the defaults so a test can hand in another record's name.
    return compose_dropper.compose_dropper_sheet(
        _GEOMETRY, zones=[_FRONT_ZONE, back_zone], reference_path=None,
        logo_path=None, sku="FB3093", back_sections=None, revision_status="TEST",
        prior_outputs=None, **{"drawing_source": "PARAMETRIC", "descriptor": WIU_DESCRIPTOR,
                               "net_content": WIU_NET_CONTENT, "product_name": "Rose Damascena Night Repair Oil",
                               "hierarchy_lines": WIU_NAME_HIERARCHY, **kw})   # §BH49(a): this evidence measures the PARAMETRIC composition (the typed numbers); the product path draws M3 by construction


def _front_runs(doc, group):
    """``(name, size_pt, text)`` for every text run under ``group``."""
    out, stack = [], [(doc.root, ())]
    while stack:
        node, chain = stack.pop()
        chain = chain + (str(getattr(node, "name", "") or ""),)
        if getattr(node, "type", "") == "text" and group in chain:
            out.append((node.name, node.size_pt, node.text, round(node.y, 4)))
        for kid in getattr(node, "children", []) or []:
            stack.append((kid, chain))
    return sorted(out, key=lambda r: r[3])


class TestTheThirdComposerIsPlumbedAndTheSourceIsNotChosen:
    """§BB7(g)(a) — *"any executor who assumes one patch fits all three is
    wrong before he starts."*

    The other two call sites hand `ruled_front_hierarchy(...)` straight to
    `_native_decoration`, which sizes each tier from its KIND. This composer
    cannot take that patch: it has a fixed three-block lockup with its own
    sizes, its own leading and TWO panels drawing the same front at different
    scales. So the tiers are destructured into the arguments the lockup already
    has, and the two panels are fed from one pair of locals.

    WHAT IS DELIBERATELY NOT DECIDED HERE. The owner ruled that the dropper
    fixture carries a DIFFERENT product's copy and that choosing a source for
    the hierarchy — the ruled `FACIAL SERUM` literal, or something per-product
    — is *"a measured proposal to bring back, not a decision to make."* The
    last test in this class is that instruction made executable.
    """

    def test_the_default_path_is_bit_identical(self):
        """The plumbing costs production nothing, asserted on emitted ink.

        Every run the front draws today, at the size and the baseline it draws
        it at, with no caller passing a hierarchy. The descriptor now arrives
        through an argument and the name lines now pass through `wrap_name`;
        both are no-ops at the default, and this is what says so.
        """
        assert _front_runs(_sheet(), "FRONT_DIRECT_PRINT") == [
            ("front-brand", 6.0, "BBROSE", 92.7808),
            ("product-name-hero-0", 9.0, "Rose", 101.5538),
            ("product-name-hero-1", 9.0, "Damascena", 107.9038),
            # §BH50(b): set at the 5.0 pt floor and re-laid — 3.4 pt at 111.6344
            # and 3.0 pt at 114.384 until 2026-09-13
            ("front-support", 5.0, WIU_DESCRIPTOR, 112.2377),
            ("front-net-content", 5.0, WIU_NET_CONTENT, 115.908)]

    def test_a_silent_record_prints_neither_line_and_moves_nothing_else(self):
        """§BH67(c)2 — "where the record is silent, print nothing." No descriptor and no net content on the record:
        the mark and the name are drawn exactly where they were, the rule keeps its place below the name, and
        neither line is drawn — no module default stands in, and the record of the front's literal copy is empty.
        A record that holds them prints them AS HELD, in the record's own spelling."""
        spoken = _front_runs(_sheet(), "FRONT_DIRECT_PRINT")
        doc = _sheet(descriptor=None, net_content=None)
        silent = _front_runs(doc, "FRONT_DIRECT_PRINT")
        assert silent == spoken[:3]
        assert [n for n, *_ in silent] == ["front-brand", "product-name-hero-0", "product-name-hero-1"]
        assert doc.metadata["copy_literals"] == []

        def rule_y(d):
            return [n for n, _ in d.walk() if (n.name or "") == "rule-front-single"][0].segments[0].y
        assert rule_y(doc) == rule_y(_sheet())
        # the record's own words, as held: BBR-SK-201's net_weight, and a descriptor its record could carry
        held = _front_runs(_sheet(descriptor="night repair oil", net_content="30 ml e 1 fl. oz."),
                           "FRONT_DIRECT_PRINT")
        assert [(n, t) for n, _sz, t, _y in held][3:] == [
            ("front-support", "night repair oil"), ("front-net-content", "30 ml e 1 fl. oz.")]
        rows = _sheet(net_content="30 ml e 1 fl. oz.").metadata["copy_literals"]
        assert [(r["node"], r["text"]) for r in rows] == [
            ("front-net-content", "30 ml e 1 fl. oz."), ("flat-front-net-content", "30 ml e 1 fl. oz.")]
        assert all(r["source"].startswith("Product.net_weight") for r in rows)

    def test_bh68d_the_front_name_is_the_records_and_a_silent_record_prints_none(self):
        """§BH68(d), OWNER RULED 2026-09-24: "THE DROPPER'S "Rose" / "Damascena" is FACIAL SERUM again. Derive it from
        the product record; print nothing where the record is silent." With no ruled hierarchy — the shipping path —
        the front's name is the sheet's `product_name`, broken by the composer's own `wrap_name` at the name's size.
        The record "Rose Damascena" reproduces the WI-U front bit for bit. Another record prints its own name on BOTH
        panels and "Rose" / "Damascena" nowhere on the sheet. An empty, blank or absent name prints no name and places
        none: the mark stays where it was and the two lines below close up under it, as the stacked lockup sets them."""
        from apps.ire.compose_container import wrap_name
        wiu = _front_runs(_sheet(), "FRONT_DIRECT_PRINT")
        assert _front_runs(_sheet(hierarchy_lines=None, product_name="Rose Damascena"), "FRONT_DIRECT_PRINT") == wiu

        doc = _sheet(hierarchy_lines=None, product_name="Focus Pressed Powder")
        hero = [(n, sz, tx) for n, sz, tx, _y in _front_runs(doc, "FRONT_DIRECT_PRINT")]
        flat = [(n[len("flat-"):], sz, tx) for n, sz, tx, _y in _front_runs(doc, "FrontArtworkFlat")]
        assert hero == flat                                    # both panels, one name
        names = [tx for n, _sz, tx in hero if n.startswith("product-name-hero")]
        assert names == ["Focus Pressed", "Powder"] == wrap_name("Focus Pressed Powder", RULED_PT, ZONE_W * 0.94)
        assert [tx for n, _sz, tx in hero if not n.startswith("product-name-hero")] == [
            "BBROSE", WIU_DESCRIPTOR, WIU_NET_CONTENT]
        drawn = [node.text for node, _ in doc.walk() if getattr(node, "type", "") == "text"]
        assert drawn and not [t for t in drawn if "Rose" in t or "Damascena" in t]

        for silent in ("", "   ", None):
            quiet = _sheet(hierarchy_lines=None, product_name=silent)
            runs = _front_runs(quiet, "FRONT_DIRECT_PRINT")
            assert [n for n, *_ in runs] == ["front-brand", "front-support", "front-net-content"]
            assert runs[0] == wiu[0]                           # the mark is drawn exactly where it was
            assert [(n, sz, tx) for n, sz, tx, _y in _front_runs(quiet, "FrontArtworkFlat")] == [
                ("flat-" + n, sz, tx) for n, sz, tx, _y in runs]
            assert "product_name" not in {p["kind"] for p in quiet.metadata["placements"]}
        assert "product_name" in {p["kind"] for p in doc.metadata["placements"]}

    def test_the_production_call_hands_in_the_record(self):
        """§BH67(c)2 at the one production call site: the descriptor is `front_hierarchy.descriptor_for` — §BH65(b)1's
        derivation — and the net content `front_hierarchy.net_content_for`, `Product.net_weight` as held; a silent
        record gives None and the line is not drawn."""
        from types import SimpleNamespace
        from apps.ire.front_hierarchy import net_content_for
        target = pathlib.Path(__file__).parents[3].joinpath(
            "apps", "pipeline", "targets", "container", "__init__.py")
        call, = [c for c in ast.walk(ast.parse(target.read_text()))
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                 and c.func.id == "compose_dropper_sheet"]
        passed = {kw.arg: kw.value for kw in call.keywords}
        assert passed["descriptor"].func.id == "_descriptor_for"
        # [his answers after the fixes for design 122, 2026-10-08, (2): "the drawing must always print my brief's size"]
        # re-pinned: the net content is `targets.container.net_content` — his brief's size, else `net_content_for`, the
        # record's as held (test_container_target HisAnswers122TheBriefsSizeTests)
        assert passed["net_content"].func.id == "net_content"
        assert net_content_for(SimpleNamespace(net_weight=" 30 ml e 1 fl. oz. ")) == "30 ml e 1 fl. oz."
        assert net_content_for(SimpleNamespace(net_weight="")) is None
        assert net_content_for(SimpleNamespace(net_weight=None)) is None
        assert net_content_for(None) is None

    def test_and_the_wrap_that_now_sits_in_the_path_is_a_no_op_for_it(self):
        """The bit-identity above is not luck, and this is the mechanism.

        `wrap_name` is now in the default path, so it must return each default
        line unchanged or the artwork moves. "Damascena" estimates 14.985 mm
        against a 20.680 mm limit, and the boundary is pinned in BOTH
        directions so the margin cannot silently vanish under a size change.
        """
        from apps.ire.compose_container import (_CHAR_ADVANCE_MM_PER_PT,
                                                wrap_name)
        limit = ZONE_W * 0.94
        assert limit == pytest.approx(20.680, abs=1e-3)
        # §BH68(d): the two lines the record name these tests compose with, "Rose Damascena", breaks into
        for line in ("Rose", "Damascena"):
            assert wrap_name(line, RULED_PT, limit) == [line]
        assert wrap_name("Rose Damascena", RULED_PT, limit) == ["Rose", "Damascena"]
        est = len("Damascena") * RULED_PT * _CHAR_ADVANCE_MM_PER_PT
        assert est == pytest.approx(14.985, abs=1e-3)
        assert 12 * RULED_PT * _CHAR_ADVANCE_MM_PER_PT <= limit
        assert 13 * RULED_PT * _CHAR_ADVANCE_MM_PER_PT > limit

    def test_bb7g_both_panels_take_one_hierarchy(self):
        """§AB2(d) IN ITS EMITTED FORM. One sheet, two panels, same copy.

        The panel-5 / panel-8 divergence §AB2 ruled on happened because one
        call site restated what the other took by default. A supplied hierarchy
        is a caller's input and cannot live in a signature default, so the
        thing that keeps the two together is that both read the same locals.
        Asserted on the ink: identical node names but for the `flat-` prefix,
        identical sizes, identical strings.

        THE BASELINES ARE NOT COMPARED AND MUST NOT BE. The panels sit at
        different places on the sheet at different scales; equal `y` would mean
        the artwork was broken, not that the copy agreed.
        """
        doc = _sheet(hierarchy_lines=[
            {"text": "Rose Damascena Night Repair Oil",
             "kind": "product_name", "rel": 1.0},
            # ⟪PROVISIONAL⟫ AND NOT A PLAUSIBLE DESCRIPTOR, on purpose.
            # `tools/brand_strings.py` reported an earlier draft of this line —
            # which used a letter-spaced "FACIAL SERUM" — as an
            # UNMARKED_BRAND_STRING under §AE2(c), and it was right twice over:
            # the string was not the owner's, and it was a RESHAPING of a
            # string that is. A test fixture inventing brand copy is the defect
            # the register exists to catch, so the fixture is marked rather
            # than the register widened. `test_av2_brand_strings.py` is what
            # noticed; it is not adjusted here.
            {"text": "⟪PROVISIONAL⟫ PLACEHOLDER-SUPPORT", "kind": "descriptor",
             "rel": 0.8}])
        hero = [(n, sz, tx) for n, sz, tx, _ in
                _front_runs(doc, "FRONT_DIRECT_PRINT")]
        flat = [(n[len("flat-"):], sz, tx) for n, sz, tx, _ in
                _front_runs(doc, "FrontArtworkFlat")]
        assert hero == flat
        assert [tx for _, _, tx in hero] == [
            "BBROSE", "Rose Damascena", "Night Repair", "Oil",
            "⟪PROVISIONAL⟫ PLACEHOLDER-SUPPORT", "30 ml / 1.01 fl. oz."]

    def test_and_the_break_is_the_same_at_both_scales_because_it_must_be(self):
        """WHY THE WRAP MEASURES THE UNSCALED ZONE, stated as a property.

        A point size does not scale (§Z1(a)); a drawn width does. Wrapping
        against `zone["width"] * s` would break one name into different lines
        on the two panels of one sheet — the §AB2(d) defect in a new costume,
        and undetectable by any test that only looked at one panel. The test
        above proves the two agree; this one proves the agreement survives the
        scales being different, which is the part that could regress.

        THE FIXTURE IS TWO NAMES BECAUSE ONE OF THEM DID NOT PROVE THE TITLE.
        With only the SKU's name this test detected the unit error, but by the
        wrong route: at 9 pt the scaled widths are 25.230 (hero) and 31.960
        (flat), and that name breaks into two lines at BOTH of them, so the bug
        would have shown up as 2 name lines instead of 3 and NOT as the panels
        disagreeing. A test called "the same at both scales" that would pass
        under a bug making the scales differ is the overclaiming this sprint
        keeps finding in its own prose, and it was found here by searching the
        space rather than by reasoning about it: of the 6,461 two-to-six-word
        names buildable from a 14-word sample of this family's vocabulary,
        1,777 break differently at the two scaled widths. (That figure was
        first written as 9,908 from memory of the probe rather than from its
        output, and corrected by re-running it. A count in a docstring is an
        assertion nothing executes, which is the only reason it could have
        stayed wrong.)

        "Damascena Repair" is the smallest of them and is now the second
        fixture. Unscaled it is two lines on both panels; against the scaled
        widths it is two lines on the hero and ONE on the flat. So the second
        loop below fails on a genuine panel-to-panel divergence, which is what
        §AB2(d) actually names.
        """
        assert HERO_S != pytest.approx(FLAT_S)
        for name, want in (("Rose Damascena Night Repair Oil", 3),
                           ("Damascena Repair", 2)):
            doc = _sheet(hierarchy_lines=[
                {"text": name, "kind": "product_name", "rel": 1.0}])
            for group, pre in (("FRONT_DIRECT_PRINT", ""),
                               ("FrontArtworkFlat", "flat-")):
                names = [n for n, _, _, _ in _front_runs(doc, group)
                         if n.startswith(pre + "product-name-hero")]
                assert names == [f"{pre}product-name-hero-{i}"
                                 for i in range(want)], (
                    f"{name!r} broke into {len(names)} lines on {group}, not "
                    f"{want} — if the two panels disagree the wrap is "
                    "measuring a scaled drawing length against a point size")

    def test_a_net_content_tier_is_ignored_and_the_direction_is_the_point(self):
        """FAIL-CLOSED ON REGULATED COPY, per `front_hierarchy.py:26-34`.

        The ruled hierarchy has no net-content tier because §AE2(b) classes net
        content REGULATED — manifest row B5, BLOCKING. If one ever arrives
        here, the front must not print it: a front drawing a regulated quantity
        from a hierarchy nobody ruled is artwork asserting a legal claim on no
        authority. The composer keeps its own literal and drops the tier.
        """
        doc = _sheet(hierarchy_lines=[
            {"text": "30 ml", "kind": "net_content", "rel": 0.6},
            # §AE2(c) REPAIR. This tier read `"kind": "not_a_kind"` until
            # `test_av2_brand_strings` halted the commit on it with
            # UNKNOWN_BRAND_KIND. The register cannot tell a new brand kind
            # somebody forgot to register from a deliberately-invalid one in a
            # negative test — and the answer to that is to repair the fixture,
            # not to widen the register, because the escape hatch would be the
            # exact hole the register exists to close. A tier carrying text and
            # NO kind key lands on the same composer branch (`.get("kind")` is
            # None, so neither comparison matches) without asserting a brand
            # claim anybody has to adjudicate.
            {"text": "kindless tier", "rel": 0.5}])
        runs = _front_runs(doc, "FRONT_DIRECT_PRINT")
        assert "30 ml" not in [tx for _, _, tx, _ in runs]
        assert "kindless tier" not in [tx for _, _, tx, _ in runs]
        # and the tier being dropped did not drop the front's own line — since §BH67(c)2 the RECORD's net content,
        # handed in by the caller, where it was the composer's literal
        assert ("front-net-content", compose_dropper.NET_CONTENT_PT,
                WIU_NET_CONTENT) in [(n, sz, tx) for n, sz, tx, _ in runs]

    def test_a_malformed_hierarchy_cannot_overwrite_copy_twice(self):
        """First tier of a kind wins, and empty text is not copy.

        A second `descriptor` tier would otherwise silently replace the first,
        which is the same class of defect as one product's copy replacing
        another's — just inside a single call.
        """
        f = compose_dropper.front_copy_from_hierarchy
        assert f(None) == (None, None)
        assert f([]) == (None, None)
        assert f([{"text": "", "kind": "descriptor"}]) == (None, None)
        assert f([{"text": "  ", "kind": "product_name"}]) == (None, None)
        # §AE2(c) REPAIR: these two read "A" and "B" until
        # `test_av2_brand_strings` halted the commit with UNMARKED_BRAND_STRING
        # on both. A one-letter descriptor is still a descriptor to the
        # register, and the register is right about that — its job is to know
        # every string this codebase could put on a front as brand copy, and it
        # cannot grade them by length. Marked, they say what they actually are:
        # ordering fixtures nobody ruled.
        assert f([{"text": "⟪PROVISIONAL⟫ FIRST", "kind": "descriptor"},
                  {"text": "⟪PROVISIONAL⟫ SECOND", "kind": "descriptor"}]) \
            == (None, "⟪PROVISIONAL⟫ FIRST")
        assert f([{"text": " Rose Nectar ", "kind": "product_name"}]) == \
            (["Rose Nectar"], None)

    def test_bb7g_no_container_descriptor_on_the_dropper(self):
        """THE OWNER'S INSTRUCTION, MADE EXECUTABLE RATHER THAN PROMISED.

        *"The dropper fixture carries a DIFFERENT product's copy (NIGHT REPAIR
        OIL). Do not overwrite one product's copy with another's."*

        `front_hierarchy.DESCRIPTOR` is `FACIAL SERUM`, ruled by §BB7(a) for the
        container front. The dropper front draws an OIL. Nothing stops a future
        executor wiring the ruled hierarchy into this composer in one line — it
        would look like finishing the job — so the refusal is asserted at the
        place it would happen: the shipping call site passes no hierarchy, and
        the composed sheet carries no run holding the container's descriptor.

        THIS IS NOT A CLAIM THAT THE WIRING IS WRONG. It is a claim that it is
        the OWNER'S to make. If he rules that the dropper takes the ruled
        literal, this test changes with the ruling cited — which is the point of
        it failing loudly rather than the artwork changing quietly.

        §BH65(b)1 (2026-09-22) RULED THE CONTAINER FRONT'S SOURCE, NOT THIS ONE:
        "Derive it from the product". `front_hierarchy.DESCRIPTOR` no longer
        exists — the container front takes each product's own descriptor from
        its record — so the ruled string is read from the REGISTER that holds
        it. The dropper's own source is still unchosen, which is what this
        class's name says, and every assertion below still holds.
        """
        from tools import brand_strings as bs
        DESCRIPTOR = next(e.text for e in bs.RULED_STRINGS if e.ruling == "C9")
        assert DESCRIPTOR == "FACIAL SERUM"
        assert DESCRIPTOR != WIU_DESCRIPTOR

        # §BH67(c)2 (2026-09-24) RULED THE DROPPER'S SOURCE TOO: "Derive both from the product record; where the
        # record is silent, print nothing." The shipping call still hands this composer no hierarchy — it hands it
        # the product's own descriptor, `descriptor_for`, which for a serum record is the serum's word and for
        # BBR-SK-201's "carton" is nothing. The assertions below still hold, each for the reason it states.

        # (a) the SHIPPING call site hands this composer no hierarchy. Both
        #     halves of the refusal are asserted here rather than one of them
        #     being asserted elsewhere and described here: a docstring that
        #     claims a neighbour's assertion is how a guard comes to look
        #     stronger than it is. `test_but_the_front_does_not_render_the_
        #     skus_name_at_all` reads the same call for a DIFFERENT subject —
        #     whether `product_name` reaches the front — and the one line they
        #     share is cheaper than either of them being incomplete.
        target = pathlib.Path(__file__).parents[3].joinpath(
            "apps", "pipeline", "targets", "container", "__init__.py")
        call, = [c for c in ast.walk(ast.parse(target.read_text()))
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                 and c.func.id == "compose_dropper_sheet"]
        assert "hierarchy_lines" not in {kw.arg for kw in call.keywords}

        # (b) so the emitted front, on the path production takes, holds this
        #     product's descriptor and not the other product's.
        for group in ("FRONT_DIRECT_PRINT", "FrontArtworkFlat"):
            texts = [tx for _, _, tx, _ in _front_runs(_sheet(), group)]
            assert DESCRIPTOR not in texts
            assert WIU_DESCRIPTOR in texts

        # (c) and the guard is not vacuous: the ruled hierarchy really does
        #     carry `FACIAL SERUM` into this composer's arguments, so (a) is
        #     the only thing keeping it off the artwork.
        #     §BH65(b)1: the hierarchy carries the descriptor it is GIVEN; the
        #     serum fixture is given the owner's ruled serum descriptor.
        assert compose_dropper.front_copy_from_hierarchy(
            ruled_front_hierarchy("Rose Nectar", descriptor=DESCRIPTOR)) == \
            (["Rose Nectar"], "FACIAL SERUM")
        assert DESCRIPTOR in [
            tx for _, _, tx, _ in _front_runs(
                _sheet(hierarchy_lines=ruled_front_hierarchy(
                    "Rose Nectar", descriptor=DESCRIPTOR)),
                "FRONT_DIRECT_PRINT")]


class TestTheDescriptorIsDerivedFromTheProduct:
    """§BH65(b)1 — "Derive it from the product; where no record says what the
    product is, print nothing rather than a wrong word."

    `FACIAL SERUM` printed on every container front for eleven runs and was
    right on at most one: a lip gloss, a night repair oil, four fixtures that
    name no product, a palette and a pressed-powder compact all carried a
    serum's descriptor. These pin the derivation against the real values the
    product table holds, measured on 2026-09-23."""

    def test_the_record_is_passed_through_exactly_as_held(self):
        from apps.ire.front_hierarchy import descriptor_from_record as d
        assert d("pressed powder compact") == "pressed powder compact"
        assert d("palette") == "palette"
        assert d("lip gloss") == "lip gloss"
        assert d("  eyeshadow palette ") == "eyeshadow palette"

    def test_no_record_prints_nothing(self):
        from apps.ire.front_hierarchy import descriptor_from_record as d
        assert d("") is None and d(None) is None and d("   ") is None

    def test_a_packaging_word_says_what_it_is_packed_in_and_prints_nothing(self):
        """Three product rows read `carton` — one of them a night repair OIL.
        A carton is what the product ships in, so printing it would be the
        wrong word his ruling forbids."""
        from apps.ire.front_hierarchy import descriptor_from_record as d
        for word in ("carton", "Carton", "bottle", "jar", "tube", "compact"):
            assert d(word) is None, word

    def test_the_packaging_words_are_the_declaration_not_a_list_written_here(self):
        from apps.ire import front_hierarchy as fh
        from apps.pipeline.targets.container import archetypes as A
        assert fh.PACKAGING_WORDS == set(A.ARCHETYPES) | {"carton"}

    def test_there_is_no_default_descriptor(self):
        """The keyword is REQUIRED: a caller must say which descriptor it means.
        A default of FACIAL SERUM would be the defect; a default of None would
        let a caller forget the product without anybody noticing."""
        import inspect as _inspect
        from apps.ire.front_hierarchy import ruled_front_hierarchy as rfh
        param = _inspect.signature(rfh).parameters["descriptor"]
        assert param.kind is _inspect.Parameter.KEYWORD_ONLY
        assert param.default is _inspect.Parameter.empty
        with pytest.raises(TypeError):
            rfh("Rose Glow Palette")                                   # noqa

    def test_nothing_printed_keeps_the_name_and_the_direct_print_front(self):
        """Dropping the descriptor tier drops ONE run and nothing else: the name
        tier stands, so `direct_print` is still on from every path."""
        tiers = ruled_front_hierarchy("Rose Glow Palette", descriptor=None)
        assert tiers == [{"text": "Rose Glow Palette", "kind": "product_name",
                          "rel": 1.0}]
        texts = [tx for _, _, tx, _ in _front_runs(
            _sheet(hierarchy_lines=tiers), "FRONT_DIRECT_PRINT")]
        assert "FACIAL SERUM" not in texts

    def test_the_spec_key_wins_and_a_legacy_spec_is_derived_from_its_product(self):
        from types import SimpleNamespace
        from apps.ire.front_hierarchy import SPEC_KEY, descriptor_for
        powder = SimpleNamespace(product_type="pressed powder compact")
        assert descriptor_for({SPEC_KEY: "palette"}, powder) == "palette"
        assert descriptor_for({SPEC_KEY: None}, powder) is None      # recorded: nothing
        assert descriptor_for({}, powder) == "pressed powder compact"  # legacy spec
        assert descriptor_for({}, None) is None


#: THE OWNER'S ANSWER TO THE §BH68 REPORT, 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block of that date — it carries
#: no section number): "BBR-SK-201's name on the dropper breaks into four lines, the only break that fits." Task 52's
#: confirmed front since §BH54(f) — 27.6 x 40.0 mm at a 3.0 mm safe margin, a 21.6 mm safe area — and BBR-SK-201's own
#: name and net content as the target derives them (exploration_render.frozen_inputs on task 52, read-only,
#: 2026-09-25); no descriptor, the record's product_type being the packaging word "carton".
_T52_FRONT = {"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "x": 2.7, "y": 10.0, "width": 27.6,
              "height": 40.0, "safe_margin_mm": 3.0}
_SK201_NAME = "Rose Damascena Night Repair Oil"
_SK201_NET = "30 ml e 1 fl. oz."


def _sk201_sheet(zone):
    back = {"zone_id": "z-back", "zone_type": "BACK_PRINT_ZONE", "x": 0, "y": 0, "width": 22, "height": 36}
    return compose_dropper.compose_dropper_sheet(
        _GEOMETRY, zones=[zone, back], reference_path=None, logo_path=None, product_name=_SK201_NAME,
        sku="BBR-SK-201", back_sections=None, revision_status="TEST", drawing_source="PARAMETRIC",
        descriptor=None, net_content=_SK201_NET)


class TestTheNameBreaksIntoTheFewestLinesThatFit:
    """Built as a rule for every name, never for the one SKU — §BH68(d): "a hard-coded product word is one defect class,
    not one defect". The ruled wrap stands wherever its lines fit the safe area; where one does not, the fewest lines,
    up to four, whose every line fits, measured as `front_copy_fit` measures the drawn run; the most room first."""

    def test_bbr_sk_201_breaks_into_four_lines_on_task_52s_front_and_every_line_is_held(self):
        doc = _sk201_sheet(_T52_FRONT)
        want = ["Rose", "Damascena", "Night", "Repair Oil"]
        for group, pre in (("FRONT_DIRECT_PRINT", ""), ("FrontArtworkFlat", "flat-")):
            names = [t for n, _, t, _ in _front_runs(doc, group) if str(n).startswith(pre + "product-name-hero")]
            assert names == want, (group, names)
        fit = doc.metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert fit["safe_area_mm"] == 21.6
        assert [(r["text"], r["state"]) for r in fit["name_runs"]] == [(w, "HELD") for w in want]
        # the refusals by name are gone; the vertical axis is still unmeasured, and still blocks acceptance
        # [THE OWNER'S SECOND ANSWER OF 2026-09-25: Gate 2 measures the front's height now, and on this 40.0 mm front
        # it refuses the net content by name — TestGate2MeasuresTheFrontsHeight]
        assert fit["codes"] == ["CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND: front-net-content +2.0683 mm"]
        assert max(r["width_mm"] for r in fit["name_runs"]) == pytest.approx(19.5897, abs=1e-3)   # "Damascena"

    def test_the_wrap_alone_set_two_lines_the_first_wider_than_the_front(self):
        """What the ruled wrap sets on this front, and why it cannot stand: it measures no line (§BD(b))."""
        from apps.ire.compose_container import wrap_name
        assert wrap_name(_SK201_NAME, 9.0, 27.6 * 0.94) == ["Rose Damascena Night", "Repair Oil"]
        doc = _sk201_sheet(_T52_FRONT)
        face = doc.metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]["name_runs"][0]["face"]
        from apps.ire.text_metrics import text_width_mm_measured
        assert text_width_mm_measured("Rose Damascena Night", 9.0 * back_panel.MM_PER_PT, face) == pytest.approx(
            38.808, abs=1e-3)

    def test_two_four_line_breaks_fit_no_three_line_break_does_and_the_one_with_more_room_is_drawn(self):
        """His "the only break that fits": two four-line breaks fit, and the executor took the one with the most room,
        told him before it was built — one line from him reverses it."""
        from itertools import combinations

        from apps.ire.text_metrics import text_width_mm_measured
        fit = _sk201_sheet(_T52_FRONT).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        face, safe = fit["name_runs"][0]["face"], fit["safe_area_mm"]
        words = _SK201_NAME.split()

        def widest(n):
            out = {}
            for cuts in combinations(range(1, len(words)), n - 1):
                b = (0, *cuts, len(words))
                lines = tuple(" ".join(words[x:y]) for x, y in zip(b, b[1:]))
                out[lines] = max(text_width_mm_measured(ln, 9.0 * back_panel.MM_PER_PT, face) for ln in lines)
            return out

        assert all(w > safe for n in (1, 2, 3) for w in widest(n).values())
        four = {lines: round(w, 4) for lines, w in widest(4).items() if w <= safe}
        assert four == {("Rose", "Damascena", "Night", "Repair Oil"): 19.5897,
                        ("Rose", "Damascena", "Night Repair", "Oil"): 21.028}
        assert compose_dropper.front_name_lines(_SK201_NAME, 9.0, _T52_FRONT) == ["Rose", "Damascena", "Night",
                                                                                  "Repair Oil"]

    def test_where_the_wraps_lines_fit_they_stand_bit_for_bit(self):
        from apps.ire.compose_container import wrap_name
        for name in ("Rose", "Damascena", "Repair Oil"):
            assert compose_dropper.front_name_lines(name, 9.0, _T52_FRONT) == wrap_name(name, 9.0, 27.6 * 0.94) \
                == [name]

    def test_a_line_the_wraps_estimate_passes_and_the_face_does_not_breaks_by_measure(self):
        """"Rose Damascena": the wrap's estimate sets it on one line, and drawn it is 28.5909 mm on a 21.6 mm safe area
        — so it breaks by measure, into the two lines every earlier render drew it in."""
        from apps.ire.compose_container import wrap_name
        from apps.ire.text_metrics import text_width_mm_measured
        assert wrap_name("Rose Damascena", 9.0, 27.6 * 0.94) == ["Rose Damascena"]
        face = _sk201_sheet(_T52_FRONT).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]["name_runs"][0]["face"]
        assert text_width_mm_measured("Rose Damascena", 9.0 * back_panel.MM_PER_PT, face) == pytest.approx(
            28.5909, abs=1e-3)
        assert compose_dropper.front_name_lines("Rose Damascena", 9.0, _T52_FRONT) == ["Rose", "Damascena"]

    def test_where_no_break_of_four_lines_fits_the_wrap_stands_and_the_gate_refuses_it_by_name(self):
        """On the 22.0 mm front (a 16.0 mm safe area) "Damascena" alone is wider than the safe area, so no break fits:
        the wrap's lines stand and Gate 2 refuses them by name, exactly as before."""
        from apps.ire.compose_container import wrap_name
        narrow = dict(_FRONT_ZONE, safe_margin_mm=3.0)
        assert compose_dropper.front_name_lines(_SK201_NAME, 9.0, narrow) == wrap_name(_SK201_NAME, 9.0, 22.0 * 0.94) \
            == ["Rose Damascena", "Night Repair", "Oil"]
        fit = _sk201_sheet(narrow).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: product-name-hero-0 +12.5909 mm" in fit["codes"]

    def test_a_zone_with_no_safe_margin_is_not_measured_and_the_wrap_stands(self):
        from apps.ire.compose_container import wrap_name
        assert "safe_margin_mm" not in _FRONT_ZONE
        assert compose_dropper.front_name_lines(_SK201_NAME, 9.0, _FRONT_ZONE) == wrap_name(_SK201_NAME, 9.0,
                                                                                             22.0 * 0.94)

    def test_the_break_is_measured_in_the_face_the_gate_measures_the_drawn_name_in(self):
        from apps.ire.text_metrics import resolve_metric_faces
        fit = _sk201_sheet(_T52_FRONT).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        face = compose_dropper._face_for_role(compose_dropper._NAME_ROLE,
                                              resolve_metric_faces(compose_dropper._PALETTE_SURFACE))
        assert {r["face"] for r in fit["name_runs"]} == {face} == {"Montserrat-Bold"}

    def test_at_print_size_four_lines_carry_the_net_content_below_the_safe_band_recorded_not_ruled(self):
        """[THE OWNER'S SECOND ANSWER OF 2026-09-25: the gate measures it now — TestGate2MeasuresTheFrontsHeight.]
        FRONT_COPY_VERTICAL_COST: the gate does not measure the vertical axis, because the sheet never draws the
        front at print size — the hero is drawn at 1.22x and the flat at 1.85x, the type held at its point size, so on
        the sheet the net content sits inside the band. Composed at s = 1, as that cost names, four lines carry the
        net content's baseline 39.054 mm down the 40.0 mm front: 2.054 mm below the safe band's foot at 37.0, 0.946 mm
        inside the zone; two lines left it at 26.354. Recorded, not ruled — how to make the room is the owner's."""
        from apps.ire.graph import TextRun as _Run
        kids, _pl, _logo, (_zx, zy, _zw, zh) = compose_dropper._front_typography(
            _GEOMETRY, _T52_FRONT, 0.0, 0.0, 1.0, None, name_lines=[_SK201_NAME], descriptor=None,
            net_content=_SK201_NET)
        runs, stack = {}, list(kids)
        while stack:
            n = stack.pop()
            stack.extend(getattr(n, "children", []) or [])
            if isinstance(n, _Run):
                runs[n.name] = n
        assert zh == 40.0
        assert [round(runs["product-name-hero-%d" % i].y - zy, 3) for i in range(4)] == [12.0, 18.35, 24.7, 31.05]
        assert runs["front-net-content"].y - zy == pytest.approx(39.054, abs=1e-3)
        assert runs["front-net-content"].y - zy - (40.0 - 3.0) == pytest.approx(2.054, abs=1e-3)


class TestGate2MeasuresTheFrontsHeight:
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block of that date headed "Before I
    start testing"): "Make Gate 2 measure the front's height." The front block is composed at print size in memory and
    every judged run's INK — its own glyph outlines in the face the emitter draws — is held against the zone's safe band,
    its safe margin in from the top edge and from the foot. Task 52's front and BBR-SK-201's own inputs throughout."""

    def test_on_task_52s_40_mm_front_the_net_content_is_refused_by_name(self):
        fit = _sk201_sheet(_T52_FRONT).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert fit["codes"] == ["CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND: front-net-content +2.0683 mm"]
        rows = {r["name"]: r for r in fit["vertical_runs"]}
        net = rows["front-net-content"]
        assert (net["state"], net["safe_foot_mm"]) == ("EXCEEDS_SAFE_BAND", 37.0)
        assert net["ink_bottom_mm"] == pytest.approx(39.0683, abs=1e-3)
        assert {rows["product-name-hero-%d" % i]["state"] for i in range(4)} == {"HELD"}
        assert fit["vertical"].startswith("MEASURED at print size")

    def test_on_a_43_mm_front_every_run_holds_and_the_front_carries_no_code(self):
        fit = _sk201_sheet(dict(_T52_FRONT, height=43.0)).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert fit["codes"] == []
        net = {r["name"]: r for r in fit["vertical_runs"]}["front-net-content"]
        assert net["state"] == "HELD" and net["spare_foot_mm"] == pytest.approx(0.0317, abs=1e-3)

    def test_the_ink_is_read_from_the_glyphs_and_not_from_a_model(self):
        """"Repair Oil" reaches below its baseline by its p's descender; "30 ml e 1 fl. oz." by an overshoot only. The
        brand instrument's model would put the descender under both (0.271 em, `container_brand_usage`)."""
        from apps.ire import back_panel as bp
        fit = _sk201_sheet(_T52_FRONT).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        rows = {r["name"]: r for r in fit["vertical_runs"]}
        below = {k: (r["ink_bottom_mm"] - r["baseline_mm"]) / (r["size_pt"] * bp.MM_PER_PT) for k, r in rows.items()}
        assert below["product-name-hero-3"] == pytest.approx(0.194, abs=2e-3)       # "Repair Oil": the p
        assert below["front-net-content"] == pytest.approx(0.008, abs=2e-3)         # no descender, an overshoot
        assert below["product-name-hero-1"] == pytest.approx(0.008, abs=2e-3)       # "Damascena"

    def test_a_zone_with_no_safe_margin_is_unmeasured_and_says_why(self):
        fit = _sk201_sheet(_FRONT_ZONE).metadata[compose_dropper.FRONT_COPY_FIT_SCHEMA]
        assert "CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (the zone record carries no usable safe margin)" in \
            fit["codes"]
        assert fit["vertical"].startswith("UNMEASURED") and fit["vertical_runs"] == []

    def test_a_fit_handed_no_print_size_block_stays_unmeasured(self):
        doc = _sk201_sheet(_T52_FRONT)
        fit = compose_dropper.front_copy_fit(doc, _T52_FRONT)
        assert fit["codes"][-1] == ("CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (no print-size block was handed to "
                                    "the instrument)")
