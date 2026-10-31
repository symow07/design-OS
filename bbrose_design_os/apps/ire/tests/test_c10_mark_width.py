"""§BC(h) — C10: the mark on the dropper front clears the print floor.

WHY THIS FILE EXISTS AND WHY IT IS NOT A CHECK ON A NUMBER. The owner ruled the
mark's share of the front zone to 0.55. A test that asserted
``MARK_ZONE_SHARE == 0.55`` would restate the ruling and measure nothing: it
would pass identically if the composer stopped placing a mark, if the zone
changed width underneath it, or if the share were multiplied by a scale on the
way to the page. §BC(h) requires the assertion to be made **on the EMITTED
geometry, not on the factor**, which is the discipline C16(b) established when
a width-based inequality had to be re-proved on the ``emitted`` property rather
than deleted for having become an equality.

So: the front is composed through the production producer at unit scale, so
that drawing units ARE millimetres, and the width read off the node that
producer emits.

**AND THAT IS NOT THE NODE ON THE SHEET, WHICH THIS FILE SAYS RATHER THAN
GLOSSES.** An audit of the first draft of this docstring caught it claiming the
front is composed "the way the sheet composes it" and that the width is read
off "the node that reaches the document". Both are false as written.
``compose_dropper_sheet`` never calls the producer at ``s=1.0``: the hero panel
draws at ``hero_s = 1.22`` and panel 8 at ``flat_s = 34/22.0 = 1.5455``, so the
mark nodes actually in the emitted sheet are **14.762 mm and 18.700 mm wide**.
No node in that document is 12.10 mm.

**The floor still holds, and the reason is scale invariance, which is asserted
below rather than argued here.** ``s`` multiplies the zone and the mark
identically — ``zw = zone["width"] * s`` and ``logo_w = zw * MARK_ZONE_SHARE``
— so ``mark / zone`` is exactly ``MARK_ZONE_SHARE`` at every scale, and the
mark on the 22.0 mm PHYSICAL zone is 12.10 mm however large the review sheet
draws it. ``TestTheFloorSurvivesTheSheetsOwnScales`` composes at both real
sheet scales and proves it, so the layer this file measures at is a measured
property and not a claim in a comment.

The distinction matters beyond wording: a reviewer who took "the node that
reaches the document" literally and wired a width check to the SHEET would read
14.762 and 18.700, pass by magnification, and fail on any panel drawn below
``s = 0.985``.

WHY THE BRANCH MATTERS. It would be easy to conclude the old 8.80 mm mark was
harmless because ``compose_container_graph`` is the composer everything talks
about. It is not the one this product renders.
``apps/pipeline/targets/container/__init__.py:1050`` reads
``if geometry is not None:`` and routes to ``compose_dropper_sheet``; the
``compose_container_graph`` call at :1081 is the ``else``. **Whenever a
confirmed dropper geometry exists — which is the product being built — the mark
placed is this one.** `test_au3_brand_usage.py:135` records the same finding
from the other side and correctly declines to fix it there.

WHAT IS DELIBERATELY NOT TESTED HERE. ``evaluate_brand_usage`` is not wired to
this composer, and §BC(h) says in terms that wiring it MUST NOT be done
silently alongside the ruling. This file therefore reads the floor CONSTANT
from ``container_brand_usage`` — so the two cannot drift apart — while making
no claim that the evaluator runs on this path. It does not.
"""
import pytest
from django.conf import settings

from apps.ire import compose_dropper
from apps.ire.container_brand_usage import MINIMUM_WIDTH_MM_PRINT
from apps.ire.tests.test_back_panel import _FRONT_ZONE, _GEOMETRY

#: The ruling's arithmetic, restated so a reader need not run the test to see
#: what the margin is. NOT asserted against the emitted width — that would be
#: the factor check this file exists to avoid.
ZONE_W_MM = float(_FRONT_ZONE["width"])          # 22.0
RETIRED_SHARE = 0.40                             # 8.80 mm — the incumbent
TRAP_SHARE = 0.545                               # 11.99 mm — still fails

#: The two scales `compose_dropper_sheet` actually draws the front at.
#: `compose_dropper.py:828` and `:859`. Neither is 1.0, which is the whole
#: point of `TestTheFloorSurvivesTheSheetsOwnScales`.
HERO_S = 1.22
FLAT_S = min(34.0 / ZONE_W_MM, 70.0 / float(_FRONT_ZONE["height"]))

#: `propose_zones` derives the front zone as 70% of the body diameter
#: (`container_contract.py:551`, `centred(cov_w=0.7)`), rounded to 0.1.
#: Restated here so the coupling between a BODY dimension and a MARK floor is
#: visible in the file that depends on it.
ZONE_COVERAGE_W = 0.7


def _mark(share=None, monkeypatch=None, scale=1.0):
    """The mark node the production front emits, at the requested scale.

    ``s=1.0`` is what makes the returned width a millimetre quantity: every
    positional argument to ``_front_typography`` is a millimetre and ``s``
    multiplies them, so at unity the node's ``w`` is mm with no conversion for
    a later reader to get wrong.

    Composed with the REAL brand asset. ``image_node`` returns ``None`` for a
    missing file and ``intrinsic_aspect`` returns ``None`` for an unreadable
    one — in either case the composer takes its text fallback and places no
    mark at all. A test that quietly measured the fallback would report a
    passing floor for a front with no logo on it, so the mark's existence is
    asserted before its width is read.
    """
    if share is not None:
        monkeypatch.setattr(compose_dropper, "MARK_ZONE_SHARE", share)
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    kids, placements, logo_used, _zr = compose_dropper._front_typography(
        _GEOMETRY, zone, 3.0, 3.0 - closure_h * scale, scale,
        settings.BRAND_LOGO_PATH, prefix="c10-")
    marks = [k for k in kids if getattr(k, "name", None) == "c10-logo"]
    assert marks, (
        "the composer placed no mark, so there is no width to measure and a "
        "floor assertion here would be vacuous")
    return marks[0], logo_used, placements


class TestTheMarkClearsThePrintFloor:

    def test_the_emitted_mark_clears_the_floor_on_the_branch_production_uses(
            self):
        """The assertion §BC(h) ruled: emitted width, against the floor."""
        mark, logo_used, _ = _mark()
        assert logo_used == "front-controlled-fallback"
        assert mark.w >= MINIMUM_WIDTH_MM_PRINT, (
            f"emitted mark is {mark.w:.2f} mm against a "
            f"{MINIMUM_WIDTH_MM_PRINT} mm print floor")

    def test_the_headroom_the_owner_bought_is_the_tenth_of_a_millimetre(self):
        """0.55 was chosen over 0.546 for headroom; this is how much there is.

        Read off the emitted node rather than multiplied out, so that a change
        to the zone width shows up here as lost headroom instead of passing
        because the arithmetic still agrees with itself.
        """
        mark, _, _ = _mark()
        assert mark.w - MINIMUM_WIDTH_MM_PRINT == pytest.approx(0.10,
                                                                abs=5e-3)

    def test_the_height_is_the_assets_own_and_is_not_chosen(self):
        """Widening the mark must not have stretched it.

        ``intrinsic_aspect`` exists so that no composer picks a logo height.
        The floor is a WIDTH rule, and the cheapest wrong way to satisfy a
        width rule is to scale one axis.
        """
        from apps.ire.nodes import intrinsic_aspect
        mark, _, _ = _mark()
        ratio = intrinsic_aspect(settings.BRAND_LOGO_PATH)
        assert ratio is not None
        assert mark.h == pytest.approx(mark.w * ratio, rel=1e-9)


class TestTheFloorDiscriminates:
    """A floor that nothing can fail is not a floor.

    Both controls drive the EMITTED width across the boundary rather than
    asserting anything about the share, which is the whole point: if a later
    change made the share stop reaching the page, these two would start
    passing at every value and the failure would be visible as a control that
    no longer controls.
    """

    def test_the_retired_share_does_not_clear_it(self, monkeypatch):
        mark, _, _ = _mark(RETIRED_SHARE, monkeypatch)
        assert mark.w < MINIMUM_WIDTH_MM_PRINT
        assert mark.w == pytest.approx(8.80, abs=5e-3)

    def test_and_the_near_miss_the_owner_avoided_does_not_clear_it_either(
            self, monkeypatch):
        """0.545 -> 11.99 mm. This is the trap §BC(h) names.

        It is worth a test of its own because it is the value a later reader
        would derive if they solved ``12.0 / 22.0`` and rounded to three
        places. The rounding goes the wrong way and the artwork fails.
        """
        mark, _, _ = _mark(TRAP_SHARE, monkeypatch)
        assert mark.w < MINIMUM_WIDTH_MM_PRINT
        assert mark.w == pytest.approx(11.99, abs=5e-3)


class TestTheFloorSurvivesTheSheetsOwnScales:
    """The layer question, answered by measurement instead of by assertion.

    An audit asked the only question that could have made this whole file
    theatre: is the width read at `s=1.0` the width that gets PRINTED, or does
    the sheet transform it afterwards so a node-level reading proves nothing?

    The answer is that the sheet magnifies — 1.22x on the hero panel and
    1.5455x on panel 8 — and that magnification is exactly why the reading
    holds, because `s` multiplies the zone and the mark by the same factor.
    That is asserted here at BOTH real sheet scales rather than reasoned about
    in a comment, so that a future change which broke the proportionality
    (a mark sized from something other than `zw`, an absolute clamp, a scale
    applied to one and not the other) fails here rather than shipping.
    """

    @pytest.mark.parametrize("s", [1.0, HERO_S, FLAT_S])
    def test_the_mark_holds_its_share_of_the_zone_at_every_scale(self, s):
        mark, _, _ = _mark(scale=s)
        drawn_zone = ZONE_W_MM * s
        assert mark.w / drawn_zone == pytest.approx(
            compose_dropper.MARK_ZONE_SHARE, rel=1e-12)

    @pytest.mark.parametrize("s", [1.0, HERO_S, FLAT_S])
    def test_and_so_the_physical_mark_clears_the_floor_at_every_scale(self,
                                                                     s):
        """`mark.w / s` is the millimetre width on the real 22.0 mm zone."""
        mark, _, _ = _mark(scale=s)
        assert mark.w / s >= MINIMUM_WIDTH_MM_PRINT

    def test_the_sheet_nodes_are_not_the_twelve_point_one_and_that_is_stated(
            self):
        """The claim the first docstring got wrong, pinned as a fact.

        If someone later wires a width check to the SHEET's nodes, these are
        the numbers they will read. They pass the floor by magnification, not
        by conforming to it, and the same check would FAIL on any panel drawn
        below s = 12.0 / 12.10 = 0.9917.
        """
        hero, _, _ = _mark(scale=HERO_S)
        flat, _, _ = _mark(scale=FLAT_S)
        assert hero.w == pytest.approx(14.762, abs=5e-3)
        assert flat.w == pytest.approx(18.700, abs=5e-3)
        assert hero.w > MINIMUM_WIDTH_MM_PRINT
        assert flat.w > MINIMUM_WIDTH_MM_PRINT


class TestTheZoneWidthThisFloorRestsOn:
    """What the fixture does NOT cover, measured instead of left implicit.

    The module docstring says a factor check would pass if the zone changed
    width underneath it. That is true — but this file reads the zone from
    `test_back_panel._FRONT_ZONE`, a FIXTURE, so strictly it proves the floor
    for a 22.0 mm zone and not for whatever production derives tomorrow. An
    audit made that point and it is correct.

    The coupling is therefore stated and pinned here: production derives the
    front zone as 70% of the BODY DIAMETER, so C10's mark floor is one rounding
    step away from a bottle dimension nobody thinks of as typography.
    """

    @staticmethod
    def _mark_mm(body_d):
        """The mark width production would draw for a given body diameter."""
        return (round(body_d * ZONE_COVERAGE_W, 1)
                * compose_dropper.MARK_ZONE_SHARE)

    def test_the_fixture_zone_is_the_one_the_derivation_produces(self):
        d = float(_GEOMETRY["body_diameter_mm"])
        assert round(d * ZONE_COVERAGE_W, 1) == ZONE_W_MM

    def test_the_confirmed_body_clears_the_floor_by_three_tenths_of_a_mm(self):
        """And the margin is in BODY diameter, not in the share.

        31.2 mm of body gives a 21.8 mm zone gives an 11.99 mm mark — the same
        11.99 the 0.545 trap produces, arrived at from a completely different
        direction. **A body re-measurement of -0.3 mm would put C10 back below
        its floor without anyone touching a typography number.** That is the
        finding this class exists to make un-missable.
        """
        d = float(_GEOMETRY["body_diameter_mm"])
        assert self._mark_mm(d) >= MINIMUM_WIDTH_MM_PRINT
        fails = [x / 10 for x in range(300, int(round(d * 10)) + 1)
                 if self._mark_mm(x / 10) < MINIMUM_WIDTH_MM_PRINT]
        assert fails, "nothing smaller fails, so this is not a real edge"
        assert max(fails) == pytest.approx(31.2, abs=1e-9)
        assert self._mark_mm(31.2) == pytest.approx(11.99, abs=5e-3)
        assert d - max(fails) == pytest.approx(0.3, abs=1e-9)


class TestTheRecordedPlacementIsNotTheDrawnMark:
    """A finding this ruling exposed and deliberately did NOT repair.

    ``_front_typography.place()`` records every placement with fixed
    ``nx=0.15, nw=0.70`` — a 15.4 mm band on a 22.0 mm zone — regardless of
    what was drawn. Before this ruling the mark was 8.80 mm and the record
    claimed 15.4; after it the mark is 12.10 and the record still claims 15.4.

    **The ruling improved the drawing and did not touch the record**, so the
    disagreement is smaller and still there. It is pinned here so that the next
    reader finds it as a measured fact rather than rediscovering it, and so
    that repairing it later is a visible change to this test rather than a
    silent one. §AC forbids doing it in the ruling's own commit.
    """

    def test_the_placement_record_still_describes_a_band_and_not_the_mark(
            self):
        mark, _, placements = _mark()
        logo = next(p for p in placements if p["kind"] == "logo")
        assert logo["nw"] == 0.70
        recorded_mm = logo["nw"] * ZONE_W_MM
        assert recorded_mm == pytest.approx(15.4, abs=5e-3)
        assert recorded_mm != pytest.approx(mark.w, abs=0.1)


class TestTheMarkFromItsApprovedVectorMasterClearsTheSameFloor:
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." The dropper's front handed an approved vector master — a SYNTHETIC
    fixture (apps/ire/tests/brand_mark_fixtures.py), never the owner's trace — keeps the ruled width (the share of the
    zone does not move), takes the MASTER's ink aspect for its height, and is measured in the print-size block as the
    mark it is: the ``front-brand`` fallback run is not set beside it."""

    def _front(self, master, scale=1.0):
        zone = dict(_FRONT_ZONE, x=0, y=0)
        closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                     + (_GEOMETRY.get("visible_neck_mm") or 3.0))
        return compose_dropper._front_typography(
            _GEOMETRY, zone, 3.0, 3.0 - closure_h * scale, scale, None, prefix="c10-", logo_master=master)

    def test_the_mark_keeps_the_ruled_width_and_takes_the_masters_ink_aspect(self):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        master = B.read_master(FX.POTRACE_STYLE)
        raster, _logo_used, _ = _mark()
        kids, _placements, logo_used, _zr = self._front(master)
        marks = [k for k in kids if getattr(k, "name", None) == "c10-logo"]
        assert [m.type for m in marks] == ["asset_ref"] and logo_used == B.ZONE_USED
        mark = marks[0]
        assert (mark.x, mark.y, mark.w) == (raster.x, raster.y, raster.w)
        assert mark.w >= MINIMUM_WIDTH_MM_PRINT
        assert mark.h == pytest.approx(mark.w * FX.POTRACE_INK_ASPECT, rel=1e-12)
        assert not [k for k in kids if getattr(k, "name", "") == "c10-front-brand"]

    def test_the_print_size_block_is_measured_with_the_mark_the_sheet_draws(self):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        from apps.ire.tests.test_back_panel import _FRONT_NAME_LINES
        master = B.read_master(FX.POTRACE_STYLE)
        without = compose_dropper.print_size_runs(_GEOMETRY, _FRONT_ZONE, None, name_lines=_FRONT_NAME_LINES,
                                                  descriptor=None, net_content=None)
        with_mark = compose_dropper.print_size_runs(_GEOMETRY, _FRONT_ZONE, None, name_lines=_FRONT_NAME_LINES,
                                                    descriptor=None, net_content=None, logo_master=master)
        assert "front-brand" in {r["name"] for r in without}
        assert "front-brand" not in {r["name"] for r in with_mark}

    def test_both_sheet_marks_are_drawn_from_the_master_and_the_census_line_says_so(self):
        from apps.ire import brand_mark as B
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests import brand_mark_fixtures as FX
        from apps.ire.tests.test_back_panel import _BACK_ZONE
        master = B.read_master(FX.POTRACE_STYLE)
        doc = compose_dropper_sheet(_GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
                                    logo_path=settings.BRAND_LOGO_PATH, product_name="Rose Damascena", sku="X",
                                    back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST",
                                    logo_master=master)
        marks = {n.name: n for n, _ in doc.walk() if B.is_mark(n)}
        assert sorted(marks) == ["flat-logo", "logo"]
        assert not [n for n, _ in doc.walk() if n.type == "image" and "logo" in (n.name or "")]
        census = next(n for n, _ in doc.walk() if n.name == "census-line").text
        assert "2 marks from the approved vector master" in census and "controlled logo fallback" not in census
        assert doc.metadata["logo_zone_used"] == B.ZONE_USED


class TestTheDropperLockupTakesItsFoilOnTheProductAndNeverOnItsFlatView:
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." The dropper sheet is the path the product renders through. Its
    lockup appears twice — the hero ``logo`` on the product and ``flat-logo`` in the sheet's flat depiction — and both
    end in "logo", so the only thing keeping foil off the depiction is the finish reader's choice of the PRODUCT group
    (``container_finishes._product``, §BH65(c)10). With the raster both were refused and the choice was never
    exercised; drawn from a master (a SYNTHETIC fixture), the foil must land on the hero alone and its plate must be the
    master's outlines."""

    def test_the_foil_lands_on_the_hero_mark_only_and_plates_its_outlines(self, tmp_path):
        import fitz
        import numpy as np

        from apps.ire import brand_mark as B
        from apps.ire import container_finishes as F
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.tests import brand_mark_fixtures as FX
        from apps.ire.tests.test_back_panel import _BACK_ZONE
        master = B.read_master(FX.POTRACE_STYLE)
        doc = compose_dropper_sheet(_GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
                                    logo_path=settings.BRAND_LOGO_PATH, product_name="Rose Damascena", sku="X",
                                    back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST",
                                    logo_master=master)
        result = F.apply(doc, F.assignments("BBROSE wordmark in rose-gold foil"), brand_metallic_hex="#C9A24B")
        assert [(r["state"], r["nodes"]) for r in result["applied"] if r["target"] == "lockup"] == [
            (F.APPLIED, ["logo"])]
        marks = {n.name: n for n, _ in doc.walk() if B.is_mark(n)}
        assert [f.plate for f in marks["logo"].finishes] == ["FOIL_ROSE_GOLD"] and marks["flat-logo"].finishes == []
        usage = {}
        out = emit_pdf_ai(doc, str(tmp_path / "dropper_foil.ai"), usage_out=usage)
        assert [(p["plate"], p["items"]) for p in usage[F.SCHEMA]["plates"]] == [("FOIL_ROSE_GOLD", ["logo"])]
        with fitz.open(out) as pdf:
            pix = pdf[1].get_pixmap(dpi=1200, alpha=True)
            cov = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., 3] / 255.0
        k, hero, flat = 1200 / 25.4, marks["logo"], marks["flat-logo"]
        share = float(cov[int(hero.y * k):int((hero.y + hero.h) * k), int(hero.x * k):int((hero.x + hero.w) * k)].mean())
        assert abs(share - float(B.coverage(master, 400, margin=0).mean())) < 0.04 and share < 0.5
        assert float(cov[int(flat.y * k):int((flat.y + flat.h) * k), int(flat.x * k):int((flat.x + flat.w) * k)].sum()) == 0.0
