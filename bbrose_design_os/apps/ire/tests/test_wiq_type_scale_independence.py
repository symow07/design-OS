"""§Z1(b) enforced repo-wide — a `size_pt` must not move when the product does.

WI-J measured ONE producer and said so in its own docstring: "this measures
ONE producer. §Z1(b) is a repo-wide rule and nothing enforces it repo-wide."
This file is that enforcement, at the only level where "repo-wide" is
tractable: every composer takes a millimetre-defined product and returns a
Document full of `size_pt` values, so the rule can be stated as one
observation made of all four of them at once.

    A point size derived from a millimetre quantity MOVES when that
    millimetre quantity moves; a point size chosen as type does not.

BEHAVIOURAL, NOT A SOURCE READ — AND THE REPO PROVES WHY
--------------------------------------------------------
§AA required this and `compose_container.py` demonstrates the requirement,
though not in the way a bigger number would suggest. Grepping that file for
`size_pt` finds FOUR lines (:362, :367, :682, :712). Running it found 21
scale-dependent nodes from EIGHT exercised producers (ten exist; two serve
code-panel surfaces this fixture does not emit). The gap is
`nodes.centered_text(name, text, cx, y, size_pt, ...)`, which takes the size
as its fifth POSITIONAL argument.

Counted by node the grep did well — 17 of 21. Counted by producer it found
four of eight. **And the four it missed were not a random half.**
`product-name-0` was sized `max(8.0, zh * 0.14)` at :244, with a width
fallback `(zw * 0.94) / (longest * _CHAR_W)` at :256 — a millimetre length
assigned straight into a point field, with no conversion anywhere. That is
the SHAPE of the defect §Z1 was written for. The 17 the grep would find are
`pt * dimensionless` and unit-correct.

The grep is not wrong by volume. It is wrong exactly where it costs.

AMENDED BY SPRINT 13, WI-T — 21 IS NOW 20, AND THE ONE THAT LEFT IS THE ONE
----------------------------------------------------------------------------
§AB4 sent WI-T at `product-name-0` specifically, calling it "the only live
production defect in the sprint", and it is repaired. Per this file's own
instruction in `test_the_register_only_shrinks`, the entry is DELETED from
`SCALE_DEPENDENT` by the commit that repaired it, and the counts move with
it: 25 registered becomes 24, and the container's 21 becomes 20.

The past tense above is deliberate. The measurement stands as taken — the
grep DID miss the worst node, and that is why WI-T exists — and what changed
is the code, not the reading. §AB0(a): a closed quantity reopens on a
different measurement, and this is one.

Two things did NOT change and are worth naming so the shrink is not read as
more than it is. The grep-visible count is still exactly **17**, so the
repair came entirely out of the invisible four; and three of those four
remain (`sheet-title`, `reference-label`, `panel-BODY_BACK-label`). They are
sized off `layout["k"]`, where `k = max(0.35, H / 190.0)` is a height over
the 190 mm reference frame and therefore genuinely dimensionless — a
clause-(B) violation and not a unit error.

**This guard is the only one of the three that gets those three right, and
it is worth being precise about why.** The grep cannot see them at all. WI-T's
analyser is silent on them, but not because it judged them: it reads
`layout["k"]` as UNKNOWN, a dict being a hole in its model. Inline `k` and it
fires FALSELY, because 190.0 is a millimetre constant written as a bare
literal and the analyser has no way to know. Measured both ways in
`test_wit_unit_analysis.py`
::`test_and_seeing_through_the_dict_would_have_made_it_worse`. Three
instruments, and on this node the perturbation harness is the accurate one.

TWO CLAUSES, AND AN HONEST NOTE ABOUT WI-J'S PARENTHETICAL
-----------------------------------------------------------
§Z1(b) carries two separable claims about a point size:

  (A) UNIT CORRECTNESS  — is the number dimensionally a point size?
  (B) SCALE INDEPENDENCE — does it hold still when the product's mm change?

WI-J's docstring defends `compose.py` and `compose_vector_art.py` against a
grep, on the ground that they "derive point sizes from millimetre widths
*correctly*, by multiplying through 72/25.4". That defence is entirely about
clause (A), and it is correct: `max(8.0, p.width * 2.835 * 0.075)` is
dimensionally sound, and a string guard would have condemned it wrongly.

This guard registers those same sites anyway, on clause (B), which is a
different charge and a true one: §AA named "the same SCALE-DEPENDENT
property", and their output does move. Stated plainly so it cannot be
misread later: **being in the register is not an accusation of a unit bug**,
and for 24 of the 25 entries it was not one. Those 24 are `pt x
dimensionless` — sound on (A), registered on (B) alone.

`product-name-0` was the single exception and is the reason the distinction
had to be drawn rather than assumed: it failed BOTH clauses. Sprint 13's
WI-T repaired it, so **all 24 remaining entries are clause-(B) only** and
this register no longer holds a single unit error. Drawing the distinction is
what made it possible to send one work item at one node instead of at
twenty-five. See GREP_INVISIBLE.

WHAT THIS COSTS IN MILLIMETRES: NOTHING
----------------------------------------
Per §AA's standing rule, said next to the work rather than in a footnote:
**this work item changed no artwork whatsoever.** It added a test file and
edited no producer. The 25 registered violations were RECORDED, NOT FIXED —
§AA4(c) forbids chained fixes, and re-sizing type is re-proportioning, which
§AA2(d) forbids outright for sprint 12. (Sprint 13's WI-T repaired exactly
one of them under an explicit §AB4(c) exception, and the cost in millimetres
of THAT change is stated in `test_wit_unit_analysis.py`, not here.)

There is a second zero worth naming. The live FB3093 dropper composes
through `compose_dropper_sheet` (`targets/container/__init__.py:1046`), and
that composer holds **0 of 61** sizes still. Every one of the 25 violations
is on a branch this product does not take. All four composers are live code
reached by non-test callers — `:1053` and `native_handoff.py:217` for the
container graph, `native_handoff.py:85` and `export_service.py:258` for
vector art, `export_service.py:330` for components — so these are reachable
by other archetypes, not dead code. They are simply code no product has yet
walked, which is §AA's own precedent: a constraint the pipeline never
reaches is a constraint nobody has tested. The clean composer is the one the
product uses; the rotten ones are the ones it doesn't.

A NEW DEFECT, RECORDED AND NOT FIXED
-------------------------------------
At the fixture height below, `compose_container_graph` emits back-section
copy at **1.158 pt** and headings at **1.389 pt** — type too small to print
or read, produced by `2.0 * k` and `2.4 * k` where `k = max(0.35, H/190)`.
That is a fresh finding, it is not repaired here, and §AA4(c) is the reason.

THE PERTURBATION, AND WHY IT IS 1.5 AND NOT 2
----------------------------------------------
×2 is not a legal product: the dieline geometry engine raises GeometryError
("tuck shoulder curve (18.31 mm) does not fit inside the tuck lip (16.00
mm)") for a doubled carton, and ×1.75 fails the same way. ×1.5 is legal for
all four composers. The factor also has to be large enough to escape the
`max(FLOOR, ...)` clamps — several sizes sit ON their floor at baseline
(`product-name` at 8.0, `subtitle` at 5.5), so a small nudge would leave
them clamped and the guard would under-report. ×1.5 clears every floor here.

WHAT THE INTERSECTION HIDES, NAMED RATHER THAN SWEPT
-----------------------------------------------------
Sizes are compared only on nodes BOTH runs emit. The sets are not identical:
scaling the dropper up drops `back-panel-0-copy-2` and gains
`back-panel-6-copy-1` and `back-panel-6-heading-0`. That is reflow — a
larger panel holds more copy and wraps it differently — which is
millimetre-driven layout and is exactly what §Z1(b) does NOT govern. The
rule is about the value in the `size_pt` field, so the intersection is the
right comparison and the appearing nodes are not a miss.

WHAT THIS GUARD CANNOT SEE, MEASURED
-------------------------------------
A perturbation guard is blind to any quantity the perturbation conserves,
and the dropper sheet contains one. It draws the front zone twice: the hero
panel at a FIXED scale s = 1.22, and the flat panel FITTED to a fixed frame,
where `s` falls exactly as the zone grows —

    product 1.0x -> zone 42.30 mm x s 1.545455 = 65.37 mm
    product 1.5x -> zone 63.45 mm x s 1.030303 = 65.37 mm

— so a point size derived from `zone_height * s` moves in the hero panel and
is caught, and does not move in the flat panel and is not. `0 of 61` for the
dropper therefore means: every hero size verified, flat sizes verified only
against derivations other than the fitted product. This is demonstrated, not
asserted, by `TestTheGuardIsCatchableAgainstTheRealComposer` — it
reintroduces WI-J's defect into the live composer and watches half of it
escape. The assertion I first wrote there (that both panels are caught)
FAILED, and the failure was right. Not fixed: §AA4(c), and §AA4(d) puts the
`flat-` panel outside sprint 12 by name.

FIXTURE PROVENANCE
-------------------
Every number quoted above is FIXTURE-SUPPLIED, not measured off a real
product. `_GEOMETRY`, `_FRONT_ZONE`, `_BACK_ZONE`, `_LIVE` and `_METHODS`
come from `test_back_panel.py`; the container baseline is a FIXTURE bottle
of 110 x 40 mm built here; the two cartons are the FIXTURE dimensions in
`test_compose_vector_art.py` and `test_compose.py`. "1.158 pt" is what this
fixture bottle produces, and a different height produces a different number
— the defect is the dependence, not the particular value.
"""
from __future__ import annotations

import pytest

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON
from apps.ire.compose import compose_components_graph
from apps.ire.compose_container import compose_container_graph
from apps.ire.compose_dropper import compose_dropper_sheet
from apps.ire.compose_vector_art import VectorArtStyle, compose_vector_art_graph
from apps.ire.graph import Color, Document, Group, TextRun
from apps.ire.tests.test_back_panel import (_BACK_ZONE, _CONFIRMED_METHODS, _FRONT_RECORD, _FRONT_ZONE,
                                            _GEOMETRY, _LIVE, _METHODS)
from apps.ire.tests.test_compose_vector_art import _INFO
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (ContainerProfile,
                                                         build_backbone)

#: the millimetre factor every composer accepts. See the docstring: x1.75 and
#: x2 raise GeometryError in the dieline engine, and a factor much smaller
#: than this leaves the `max(FLOOR, ...)` clamps binding.
PERTURB = 1.5


def sized_nodes(doc: Document) -> dict[str, float]:
    """{node name: size_pt} for every text node in a composed Document."""
    out: dict[str, float] = {}

    def walk(node) -> None:
        size = getattr(node, "size_pt", None)
        if size is not None:
            out[str(node.name)] = float(size)
        for child in getattr(node, "children", None) or []:
            walk(child)

    walk(doc.root)
    return out


def sizes_that_move(compose) -> set[str]:
    """Names whose `size_pt` changes when the product's millimetres change.

    This is the whole guard. `compose` is any callable that builds a product
    at a millimetre scale factor and returns a Document.
    """
    base, bigger = sized_nodes(compose(1.0)), sized_nodes(compose(PERTURB))
    return {n for n in set(base) & set(bigger) if base[n] != bigger[n]}


def sizes_compared(compose) -> int:
    """How many nodes the comparison actually looked at.

    Without this a composer that emits no text at all would pass
    `sizes_that_move() == set()` vacuously, and the guard would be reporting
    silence as compliance.
    """
    base, bigger = sized_nodes(compose(1.0)), sized_nodes(compose(PERTURB))
    return len(set(base) & set(bigger))


# --------------------------------------------------------------------------
# the four composers, each built at a millimetre scale factor
# --------------------------------------------------------------------------
def dropper(scale: float, methods=None) -> Document:
    # [his correction of 2026-10-07] the hot stamp CONFIRMED, whose 6 pt holds the back label still at every scale; the
    # same stamp unconfirmed lets the label shrink to fit (TestHisCorrectionOf20261007ChoosesTheLabelsSizeByItsFit)
    geometry = {k: (v * scale if k.endswith("_mm") else v)
                for k, v in _GEOMETRY.items()}
    zones = [{k: (v * scale if k in ("x", "y", "width", "height") else v)
              for k, v in zone.items()} for zone in (_FRONT_ZONE, _BACK_ZONE)]
    return compose_dropper_sheet(
        geometry, zones=zones, reference_path=None, logo_path=None,
        product_name="Rose Damascena", sku="X", back_sections=_LIVE,
        revision_status="TEST", methods_record=_CONFIRMED_METHODS if methods is None else methods,
        drawing_source="PARAMETRIC", **_FRONT_RECORD)      # §BH67(c)2: the record's two front lines, handed in   # §BH49(a): this evidence measures the PARAMETRIC composition (the typed numbers); the product path draws M3 by construction


def container(scale: float) -> Document:
    backbone = build_backbone(ContainerProfile(
        archetype="bottle", height_mm=110.0 * scale, width_mm=40.0 * scale))
    return compose_container_graph(
        backbone, product_name="Rose Nectar", name_lines=["Rose Nectar"],
        zones=cc.propose_zones(cc.build_inferred_profile("bottle")),
        native=True, back_sections=_LIVE,
        # `sku` is REQUIRED for coverage, not decoration: the `sku` TextRun at
        # :682 — one of the two lines §AA named by number — is emitted only
        # `if sku:`. Without this the guard would have reported on the other
        # nine producers and silently skipped one of the two it was sent for.
        sku="RN-001")


def _carton(template: str, dims: dict, scale: float, **kw):
    return calculate_dieline(DielineInputJSON(
        template=template, unit="mm",
        dimensions={k: v * scale for k, v in dims.items()},
        metadata={"product_name": "Skynte Foundation",
                  "product_type": "foundation"}, **kw))


def vector_art(scale: float) -> Document:
    return compose_vector_art_graph(
        _carton("skynte_foundation_tuck_carton",
                {"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0}, scale,
                print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
                construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                              "thickness_compensation": True}),
        style=VectorArtStyle(), logo_path=None,
        product_name="Skynte Foundation",
        subtitle="Silk Veil Fluid Foundation", panel_info=_INFO)


def components(scale: float) -> Document:
    return compose_components_graph(
        _carton("straight_tuck_end_carton",
                {"width_mm": 35.0, "depth_mm": 25.0, "height_mm": 95.0}, scale,
                print_settings={}, construction={}),
        product_name="ROSE NECTAR", subtitle="LIP GLOSS", panel_info=_INFO)


COMPOSERS = {"compose_dropper_sheet": dropper,
             "compose_container_graph": container,
             "compose_vector_art_graph": vector_art,
             "compose_components_graph": components}

#: Every `size_pt` in the repo that moves when the product's millimetres do,
#: MEASURED, not guessed. §Y2's shrink-only pattern: new entries fail, and a
#: repaired entry must be deleted from here in the same commit that repairs
#: it. This is a BACKLOG, NOT A DISCHARGE — being registered records that the
#: violation is known and unfixed, and §Z1(b) is not satisfied by it.
SCALE_DEPENDENT: dict[str, frozenset] = {
    # the LIVE dropper path — 0 of 61. This entry is the one worth defending.
    "compose_dropper_sheet": frozenset(),
    # 20 of 21 sized nodes. `k = max(0.35, H / 190.0)` is the common root for
    # all twenty. `product-name-0` was the 21st and had a worse one of its
    # own — DELETED by sprint 13's WI-T, which repaired it. This is the
    # shrink-only rule working as designed: the entry left because the code
    # changed, in the commit that changed it.
    "compose_container_graph": frozenset({
        "back-section-0-copy", "back-section-0-heading",
        "back-section-1-copy", "back-section-1-heading",
        "back-section-2-copy", "back-section-2-heading",
        "back-section-3-copy", "back-section-3-heading",
        # [his final goal, 2026-10-05, A2] back-section-4, -5 and -6 (copy and heading) DELETED — NOT REPAIRED: the
        # strip now draws only the sections its box holds (three languages ran past its foot, drawn to be clipped
        # away), and this fixture's strip holds four. Their size is the same `n * k` as 0–3's, which stay registered.
        "panel-BODY_BACK-label", "reference-label",
        "sheet-title", "sku", "swatch-label-body", "swatch-label-cap",
    }),
    # 2 of 2 — `front.width * 2.835 * ...` at :611 and :617. UNIT-CORRECT
    # (clause A); registered on clause B only. See the docstring.
    "compose_vector_art_graph": frozenset({"product-name", "subtitle"}),
    # 2 of 2 — `p.width * 2.835 * ...` at compose.py:273 and :279. Same note.
    # [§BH55 Phase 2, 2026-09-19: REPAIRED — the carton front's name is set at 9.0 pt and its line at 6.0 pt, chosen
    # as type and measured inside the panel (compose.py FRONT_NAME_PT, FRONT_LINE_PT); both entries DELETED in the
    # commit that repaired them, as this register asks.]
    "compose_components_graph": frozenset(),
}

#: stated as a number so it cannot decay into an impression (§Y2's discipline).
#: WAS 25 at sprint 12; WI-T repaired `product-name-0` and it is 24.
#: §BH55 Phase 2 (2026-09-19): the carton front's name and its line repaired — 22.
#: [his final goal, 2026-10-05, A2] 22 -> 16: the strip's sections 4–6 no longer drawn in this fixture (not repaired).
REGISTERED_TOTAL = 16
#: §BH68(d) (2026-09-24): 86 -> 84 — the dropper's front now prints the record's name, "Rose Damascena", wrapped by the
#: front's width, and the 1.5x product's wider front sets it on ONE line: its two `product-name-hero-1` runs exist at
#: one scale only, so two fewer nodes are compared. No type size moves (`sizes_that_move` is still empty).
#: [his final goal, 2026-10-05, A2] 84 -> 78: the same six strip runs, no longer drawn, no longer compared.
#: [his final goal, 2026-10-05, B2: "bleed and safe lines; dimensions labelled"] 78 -> 87: the carton's guides set their
#: words — `glue-label` and the eight `dim-*` labels (the carton's size, its flat width and height, each panel's width)
#: — nine more nodes compared, at fixed sizes: none moves (`sizes_that_move` of the carton is still empty).
#: [his second goal of 2026-10-06, item 2: TRADE_RULES.md R1, E3] 87 -> 88: the die's grain and side shown,
#: `dim-grain`, one more guide word compared, at a fixed size: none moves.
COMPARED_TOTAL = 88

#: The container nodes a `grep size_pt` CANNOT see, because their size is the
#: fifth POSITIONAL argument to `nodes.centered_text`. There were FOUR; WI-T
#: repaired one and there are three. The other 17 come from the four
#: `size_pt=` lines and a grep would find them — that 17 has not moved, so
#: the whole of the repair came out of the part the grep could not see.
#:
#: These three are sized `max(FLOOR, n * k)` where `k = max(0.35, H / 190.0)`
#: is a height over the 190 mm reference frame — dimensionless, so they are
#: clause-(B) only and unit-correct. NOT FIXED: §AB4(c) makes WI-T the
#: sprint's single permitted chained fix and it is spent on the front.
GREP_INVISIBLE = frozenset({"panel-BODY_BACK-label",
                            "reference-label", "sheet-title"})

#: The fourth, kept by name rather than deleted, because deleting it would
#: erase the finding that justified the work item that repaired it.
#:
#: `product-name-0` was sized `max(8.0, zh * 0.14)` at :244 with a width
#: fallback `(zw * 0.94) / (longest * _CHAR_W)` at :256 — a millimetre height
#: and a millimetre width assigned straight into a point field. That is the
#: SHAPE of WI-J's original defect, not merely scale-dependence, and it was
#: invisible to the grep. This file recorded that whether `0.14` silently
#: absorbed the 2.835 mm->pt factor "is not knowable from the source". §AB
#: sent WI-T to find out; `apps/ire/unit_analysis.py` computes the dimension
#: and answers no, and the size is now the chosen `FRONT_NAME_PT = 8.0`.
GREP_INVISIBLE_REPAIRED = frozenset({"product-name-0"})


def text_positions_that_move(compose) -> set[str]:
    """Names whose (x, y) changes under the same perturbation.

    The control for a null result. `sizes_that_move(dropper) == set()` is
    only evidence if the perturbation actually REACHES that composer's
    typography; if it did not, the empty set would be a disconnected
    instrument reading zero, which is how §Z1's original defect survived
    underneath a green axis in the first place.
    """
    def coords(doc):
        out = {}

        def walk(node):
            if getattr(node, "size_pt", None) is not None:
                out[str(node.name)] = (float(node.x), float(node.y))
            for child in getattr(node, "children", None) or []:
                walk(child)

        walk(doc.root)
        return out

    base, bigger = coords(compose(1.0)), coords(compose(PERTURB))
    return {n for n in set(base) & set(bigger) if base[n] != bigger[n]}


class TestTheRuleHoldsWhereTheProductActuallyGoes:
    def test_the_live_dropper_composer_holds_every_size_still(self):
        """The composer the shipping product uses reports clean.

        NOT "fully §Z1(b)-clean" — see WHAT THIS GUARD CANNOT SEE. The flat
        panel's fitted scale conserves `zone_height * s`, so this zero covers
        every hero size and only part of the flat panel's.
        """
        assert sizes_that_move(dropper) == set()

    def test_and_it_is_not_clean_by_emitting_no_type(self):
        """Guards against a vacuous pass: silence is not compliance."""
        # §BH68(d): 61 -> 59 — see COMPARED_TOTAL; the record's name sets on one line on the 1.5x front
        assert sizes_compared(dropper) == 59

    def test_the_perturbation_does_reach_the_dropper_typography(self):
        """THE CONTROL. 16 of those 61 text nodes MOVE ON THE SHEET when the
        bottle grows — so the perturbation is live in this composer and the
        sizes are holding still on purpose, not because nothing was pushed.

        Not all 61 move: the presentation sheet places most labels at fixed
        sheet coordinates, and only type inside the scaled product panels
        travels. That is the correct behaviour and it is what §Z1(b) asks
        for — the type REPOSITIONS with the product and does not RESIZE.
        """
        # §BH68(d): 16 -> 17. `product-name-hero-1` leaves the count (on the 1.5x front the name is one line, so there
        # is no second line to move), and the flat panel's support line and net content join it: with one line above
        # them they sit one leading higher at 1.5x. The type repositions and does not resize — the claim stands.
        assert len(text_positions_that_move(dropper)) == 17
        assert sizes_that_move(dropper) == set()


class TestTheRegisterOfEverythingStillBroken:
    @pytest.mark.parametrize("name", sorted(COMPOSERS))
    def test_no_new_scale_dependent_size_enters_the_repo(self, name):
        new = sizes_that_move(COMPOSERS[name]) - SCALE_DEPENDENT[name]
        assert not new, (
            f"§Z1(b): these {name} nodes now change size when the product's "
            "millimetres change, which means a point size is being derived "
            "from a millimetre length:\n  " + "\n  ".join(sorted(new)))

    @pytest.mark.parametrize("name", sorted(COMPOSERS))
    def test_the_register_only_shrinks(self, name):
        fixed = SCALE_DEPENDENT[name] - sizes_that_move(COMPOSERS[name])
        assert not fixed, (
            f"these {name} nodes are registered as scale-dependent but no "
            "longer are — delete them from SCALE_DEPENDENT in the commit "
            "that repaired them:\n  " + "\n  ".join(sorted(fixed)))

    def test_the_backlog_is_a_number_not_an_impression(self):
        assert sum(len(v) for v in SCALE_DEPENDENT.values()) == REGISTERED_TOTAL
        assert sum(len(sizes_that_move(c)) for c in COMPOSERS.values()) \
            == REGISTERED_TOTAL

    def test_the_backlog_is_a_share_of_something_countable(self):
        """24 out of how many? A violation count with no denominator can be
        made to look small by emitting less type."""
        assert sum(sizes_compared(c) for c in COMPOSERS.values()) \
            == COMPARED_TOTAL


class TestTheGuardSeesWhatAGrepCannot:
    """§AA required behaviour over a source read. This is why."""

    def test_it_catches_sizes_passed_positionally_through_centered_text(self):
        """`centered_text(name, text, cx, y, size_pt, ...)` — the string
        "size_pt" appears nowhere in the expressions that size these."""
        assert GREP_INVISIBLE <= sizes_that_move(container)

    def test_the_container_is_worse_than_its_size_pt_count_suggests(self):
        """4 `size_pt=` lines in the file; 20 scale-dependent nodes from 8
        producers actually exercised here (10 exist; 2 serve code-panel
        surfaces this fixture does not emit). It was 21 before WI-T. [His final goal, 2026-10-05, A2: 14 — the strip's
        sections 4–6, six runs, are no longer drawn in this fixture; not repaired.]"""
        assert len(sizes_that_move(container)) == 14

    def test_the_size_pt_grep_would_have_found_most_nodes_but_not_the_worst(
            self):
        """The honest version of "a grep is not enough".

        By NODE a `size_pt` grep did fine: 17 of 21. By PRODUCER it found 4
        of the 8 exercised — half. And what it missed was not a random half:
        `product-name-0` was sized off a millimetre height with no conversion
        at all, the same shape as the defect §Z1 was written for, while the
        17 it would find are `pt * dimensionless` and unit-correct.

        The grep is not wrong by volume. It is wrong exactly where it costs.

        WI-T repaired that node and the arithmetic makes the point again from
        the other side: 17 of 20 now, because the 17 the grep could see did
        not move and the repair came wholly out of the three it could not.
        """
        moving = sizes_that_move(container)
        # [his final goal, 2026-10-05, A2] 17 -> 11 and 20 -> 14: the six strip runs no longer drawn are grep-visible
        assert len(moving - GREP_INVISIBLE) == 11
        assert len(moving) == 14

    def test_the_node_wi_t_repaired_is_kept_by_name_and_is_no_longer_moving(
            self):
        """The register shrinks; the FINDING does not disappear with it.
        Deleting `product-name-0` outright would leave a repo in which the
        thing that justified WI-T had no trace, which is how a fix comes to
        look like it was never needed."""
        assert GREP_INVISIBLE_REPAIRED == {"product-name-0"}
        assert not (GREP_INVISIBLE_REPAIRED & sizes_that_move(container))
        assert "product-name-0" in sized_nodes(container(1.0))

    def test_the_sku_line_section_aa_named_is_actually_exercised(self):
        """§AA named `:682` by number, and it emits only `if sku:`. Without a
        sku in the fixture this guard would have skipped it in silence."""
        assert "sku" in sizes_that_move(container)


class TestTheGuardCatchesTheDefectItWasWrittenFor:
    """Without this, a green register would be consistent with a guard that
    cannot fail — the same reasoning WI-J used, applied to this one."""

    INK = Color.from_hex("#5A2A3A")

    def _doc(self, size_pt: float) -> Document:
        return Document(page_w=210.0, page_h=297.0, root=Group(
            name="root", role="artwork", children=[
                TextRun(name="specimen", text="ROSE", x=10.0, y=10.0,
                        size_pt=size_pt, color=self.INK)]))

    def _defective(self, scale: float) -> Document:
        """A point size derived from a millimetre height — the real defect."""
        height_mm = 104.0 * scale
        return self._doc(height_mm * 0.05)

    def _unit_correct_but_scale_dependent(self, scale: float) -> Document:
        """Converts through 2.835 mm->pt CORRECTLY and is still a clause-B
        violation. This is the shape WI-J's parenthetical defends and this
        guard registers anyway."""
        width_mm = 40.0 * scale
        return self._doc(max(4.0, width_mm * 2.835 * 0.075))

    def _chosen_as_type(self, scale: float) -> Document:
        """A point size chosen as type. The product moves; this does not."""
        return self._doc(9.0)

    def test_the_defective_producer_is_caught(self):
        assert sizes_that_move(self._defective) == {"specimen"}

    def test_a_correct_conversion_is_still_caught_on_clause_b(self):
        assert sizes_that_move(self._unit_correct_but_scale_dependent) \
            == {"specimen"}

    def test_type_chosen_as_type_is_not_condemned(self):
        """The false-positive control. A guard that flagged this would be
        unusable, and a string guard grepping for arithmetic near a size
        would have no way to tell it from the two above."""
        assert sizes_that_move(self._chosen_as_type) == set()

    def test_the_clean_control_is_not_clean_by_being_empty(self):
        assert sizes_compared(self._chosen_as_type) == 1


class TestTheGuardIsCatchableAgainstTheRealComposer:
    """Synthetic controls prove the machinery; this proves the deployment.

    The registered 24 already show the guard failing against real code. What
    that does NOT show is that a REGRESSION in the one composer reporting
    clean would be caught — and that composer is the only one the shipping
    product uses, so it is the entry worth defending. WI-J's exact pre-fix
    expression is injected back into the real `compose_dropper_sheet` here.
    """

    def test_reintroducing_wij_s_defect_is_caught_through_the_real_composer(
            self, monkeypatch):
        import apps.ire.compose_dropper as cd

        real = cd._front_typography

        # §BB7(g)(a) — `**kwargs` REPLACES A TRANSCRIBED SIGNATURE, and the
        # transcription was already wrong before §3 touched it. This double
        # listed `name_min` but not `name_lines`, which §AC1(e) added; it
        # survived only because no call site passed that argument. §3 passes
        # two, and a double that names its parameters raises `TypeError` the
        # moment the real function grows one — a test failing on the shape of
        # the code it wraps rather than on the property it exists to check.
        # Forwarding whatever it is handed makes that failure mode impossible,
        # and the guard is unchanged: the defect is still injected verbatim.
        def regressed(g, zone, ox, oy, s, logo_path, prefix="", **kwargs):
            children, *rest = real(g, zone, ox, oy, s, logo_path,
                                   prefix=prefix, **kwargs)
            for node in children:
                if getattr(node, "size_pt", None) is not None:
                    # WI-J's defect verbatim: a point size off a mm height.
                    node.size_pt = zone["height"] * s * 0.05
            return (children, *rest)

        monkeypatch.setattr(cd, "_front_typography", regressed)
        caught = sizes_that_move(dropper)
        assert caught, (
            "the guard did not notice a point size derived from a millimetre "
            "height in the live dropper composer — a clean register above "
            "would then mean nothing")
        assert "product-name-hero-0" in caught

    def test_the_fitted_flat_panel_is_a_blind_spot_and_here_is_the_number(
            self, monkeypatch):
        """A LIMIT OF THIS GUARD, measured and stated rather than trimmed.

        The sheet draws the front zone twice. The hero panel uses a FIXED
        scale s = 1.22, so a millimetre-derived size there moves with the
        product and is caught. The flat panel is FITTED to a fixed frame on
        the sheet, so `s` falls as the zone grows and the product
        `zone_height * s` is CONSERVED:

            product 1.0x -> zone 42.30 mm, s 1.545455 -> 65.37 mm
            product 1.5x -> zone 63.45 mm, s 1.030303 -> 65.37 mm

        A point size derived from that conserved quantity is invisible to a
        scale perturbation — not because the artwork is right but because
        this instrument cannot see it. So `compose_dropper_sheet: 0 of 61`
        means: every hero size verified, and flat sizes verified only
        against derivations that are not the fitted product.

        Recorded, not fixed: §AA4(c), and §AA4(d) puts the `flat-` panel
        out of sprint 12 by name.
        """
        import apps.ire.compose_dropper as cd

        real = cd._front_typography
        products: list[float] = []

        # §BB7(g)(a) — forwards rather than transcribes; see the sibling test.
        def regressed(g, zone, ox, oy, s, logo_path, prefix="", **kwargs):
            children, *rest = real(g, zone, ox, oy, s, logo_path,
                                   prefix=prefix, **kwargs)
            if prefix == "flat-":
                products.append(zone["height"] * s)
            for node in children:
                if getattr(node, "size_pt", None) is not None:
                    node.size_pt = zone["height"] * s * 0.05
            return (children, *rest)

        monkeypatch.setattr(cd, "_front_typography", regressed)
        caught = sizes_that_move(dropper)

        assert not any(n.startswith("flat-") for n in caught), (
            "the flat panel is now visible to the perturbation — if that is "
            "deliberate, this test is the one to update")
        assert len(products) == 2
        assert round(products[0], 6) == round(products[1], 6) == 65.372727


class TestHisCorrectionOf20261007ChoosesTheLabelsSizeByItsFit:
    """[His correction of 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a6b2092): "when the label doesn't fit,
    the text gets SMALLER ... Shrink the whole label evenly until everything fits ... Floor: 3 pt."] §Z1(b), LIVE in the
    brain at 2026-10-07T04:42Z: "No `size_pt` anywhere in this repo may be derived from a millimetre quantity. A type
    size is chosen as type." His rule for every design makes a back label's size depend on whether its copy fits its
    panel, so a larger product's larger panel holds it at a larger size. The executor's reading, his to veto: a size
    CHOSEN from the label's own quarter-point steps by a measured fit is type chosen as type, not a size derived from a
    millimetre length — and the collision with §Z1(b)'s words is recorded here, measured, and told him. The guard's
    dropper above measures the CONFIRMED hot stamp, whose 6 pt holds the label still; under the same stamp unconfirmed
    (every live method is: §AA3(c)) this is what moves, and nothing else does."""

    @staticmethod
    def _unconfirmed(scale):
        return dropper(scale, methods=_METHODS)

    def test_only_the_back_labels_runs_move_and_each_label_is_one_chosen_size(self):
        moved = sizes_that_move(self._unconfirmed)
        assert moved and all(name.startswith("back-panel-") for name in moved), moved
        sizes = []
        for scale in (1.0, PERTURB):
            label = {v for n, v in sized_nodes(self._unconfirmed(scale)).items() if n.startswith("back-panel-")}
            assert len(label) == 1, label                         # the whole label one size: evenly
            (size,) = label
            assert 3.0 <= size <= 6.0 and ((6.0 - size) / 0.25).is_integer(), size   # one of its steps
            sizes.append(size)
        assert sizes == [5.25, 6.0]       # 1.0: shrunk from the stamp's 6 pt until it stands; 1.5x: it stands at 6 pt


class TestTheNewDefectThisFoundAndDidNotFix:
    """§AA4(c): new defects are recorded, not fixed. Recorded here so the
    number is reproducible rather than an assertion in a report."""

    def test_the_container_back_panel_sets_copy_too_small_to_print(self):
        sizes = sized_nodes(container(1.0))
        assert round(sizes["back-section-0-copy"], 4) == 1.1579
        assert round(sizes["back-section-0-heading"], 4) == 1.3895

    def test_that_is_below_every_legibility_floor_in_the_repo(self):
        """5.0 pt and 6.0 pt are the floors WI-O reported against; 1.16 pt is
        not near them. FIXTURE bottle 110 x 40 mm — a different height gives
        a different number, and the dependence is the defect, not the value.
        """
        assert sized_nodes(container(1.0))["back-section-0-copy"] < 2.0
