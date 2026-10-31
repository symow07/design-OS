"""§AU3 / §AW3 — the brand-usage gate, and the failure it is supposed to find.

THIS FILE'S HEADLINE ASSERTION IS A FAILURE, ON PURPOSE.
``test_the_front_the_repository_emits_today_FAILS_this_gate`` is the point of
the tranche, not an accident in it. §AU asked for an instrument "tight enough
that the emitted logo might fail it. If it does, that failure is the tranche's
best output." It does. A version of this file whose assertions were all green
would mean the bar had been lowered to meet the artwork, and §AU6(c) forbids
that in as many words: **never move a bar to make a measurement pass**.

WHY THE GATE IS JUDGED AGAINST A REAL COMPOSED CONTAINER AND NOT A FIXTURE.
§AA: a guard nobody has seen fire is not evidence. Hand-built documents appear
below ONLY where the question is about the instrument's own logic — the
containment rule, the UNMEASURED axes — and never where the question is
"does the gate fire on the artwork this repository ships".
"""
from __future__ import annotations

import os

import pytest
from django.conf import settings

from apps.ire.compose_container import compose_container_graph
from apps.ire.container_brand_usage import (
    BACKGROUND_REVERSED_ONLY,
    CAP_BAND_MIN_SHARE,
    CODE_BACKGROUND_FORBIDDEN,
    CODE_BELOW_MINIMUM_SIZE,
    CODE_CAP_HEIGHT_UNMEASURED,
    CODE_CLEAR_SPACE_VIOLATED,
    CODE_GROUND_UNMEASURED,
    CODE_GROUND_UNRECOGNISED,
    CODE_MOTIF_OVER_MARK,
    CODE_MOTIF_UNMEASURED,
    CODE_REVERSED_LOCKUP_REQUIRED,
    CODE_SCREEN_SIZE_UNMEASURED,
    GROUND_HEX_RULED,
    MOTIF_CONTRAST_DELTA_E,
    MOTIF_STRANDS_PERMITTED_OVER_MARK,
    MINIMUM_WIDTH_MM_PRINT,
    MINIMUM_WIDTH_PX_SCREEN,
    SCHEMA,
    _contains,
    _delta_e_hex,
    _ink_box,
    evaluate_brand_usage,
    measure_cap_ratio,
    measure_ground,
    motif_findings,
)
from apps.ire.container_logo_metrics import logo_image_nodes
# [the owner's second answer of 2026-09-25: the placed marks as production reads them — apps/ire/brand_mark.py]
from apps.ire.brand_mark import logo_nodes as _mark_nodes
from apps.ire.graph import (
    Color, Document, Group, Image, Rect, SolidFill, Stroke, TextRun,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_projection as cp
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile, build_backbone,
)

_APPROVED = os.path.join(
    settings.BASE_DIR, "docs", "visual_quality", "vq2", "brand",
    "bbrose_logo_approved.png")


@pytest.fixture(scope="module")
def emitted_front():
    """The container the repository actually composes, on the live profile.

    NOT QUITE — and §AY2 measured the difference. This omits ``zones`` and
    ``motif_spec``; both production call sites supply both. ``_live_front`` is
    the composition with them, and it does not reach the same verdict. The
    fixture is kept as-is because several tests below are about the
    instrument's own axes (screen dpi, backgrounds) where the difference is
    irrelevant, and because renaming it would rewrite history that AY0(b)
    pinned."""
    return compose_container_graph(
        build_backbone(ContainerProfile(archetype="bottle", )),
        logo_path=settings.BRAND_LOGO_PATH, product_name="Liquid Veil",
        sku="LV-01", native=True)


#: the CONTRACT's zones, not a hand-written stub — the containment validator
#: reads ``width``/``height``/``safe_margin_mm`` off them, and a stub with
#: those keys missing would make ZONE_SAFE_MARGIN_VIOLATION unreachable and
#: the containment assertions below vacuous (§AA).
_PROFILE = cc.build_inferred_profile("bottle", estimates={
    "body_width_mm": 40.0, "body_height_mm": 110.0})
_ZONES = cc.propose_zones(_PROFILE)


def _motif_spec():
    from apps.ire import container_motif as cm
    return cm.build_motif_spec(
        {"motif_signature": "a ribbon motif", "title": "PLACEHOLDER-TITLE",
         "variation_id": "v"}, {}, _ZONES, _PROFILE)


def _live_front(hierarchy=None, motif=True):
    """The composition the live targets actually call for, with the arguments
    they actually pass: a mark AND a motif spec AND no ``hierarchy_lines``.

    IT WAS SINGULAR HERE UNTIL THE CALL SITES WERE COUNTED, AND THE COUNT WAS
    STILL WRONG TWICE. Both errors are recorded at AZ0(t), and the corrected
    numbers are stated with the search that produced them (§AY0(d)):

    ``grep -rln 'compose_container_graph(' --include='*.py' apps tools config``
    returns **28** files — not 27; the definition site in
    ``compose_container.py`` is a call-shaped match and was uncounted — and
    all 28 are under ``apps/``. **None are under ``tools/`` or ``config/``**,
    which the previous sentence named anyway. Of the 28, 24 are tests, one is
    a prose string in ``container_line_weight.py``, one is the definition, and
    two are production:

      * ``apps/pipeline/targets/container/__init__.py:1081``
      * ``apps/pipeline/services/native_handoff.py:249``

    Both pass ``motif_spec`` with no hierarchy; the second passes the mark
    conditionally on ``BRAND_LOGO_PATH`` being set and existing, which it is.

    **THAT IS STILL NOT "THE ONLY STATE PRODUCTION COMPOSES", AND THE GREP
    ABOVE COULD NEVER HAVE SAID SO.** A search for one function's name can
    only return that function's call sites; it is structurally incapable of
    returning a DIFFERENT composer. Scoped by the question instead —
    ``grep -rn '^def compose_' --include='*.py' apps tools config`` — there
    are nine composers, four of which take a ``logo_path`` and therefore place
    the mark. One of them outranks this one:
    ``targets/container/__init__.py:1050`` reads ``if geometry is not None:``
    and routes to ``compose_dropper_sheet``; the call at 1081 is the
    ``else``. **So whenever a confirmed dropper geometry exists — the product
    this programme is building — production does not reach this composer at
    all**, and ``compose_dropper.py:_front_typography`` places the same mark
    from its own ``intrinsic_aspect`` call with no keep-out of any kind. That
    is C10, and it is not this file's to fix (§AC).

    What this fixture is, accurately: the arguments production passes on the
    NON-dropper branch, which is the branch this composer owns.

    Strings are visibly synthetic per AZ5(e). Measuring the geometry a real
    front will occupy is not emitting one, and §AU5's bar is untouched."""
    return compose_container_graph(
        build_backbone(ContainerProfile(archetype="bottle", )),
        logo_path=settings.BRAND_LOGO_PATH,
        product_name="PLACEHOLDER-BRAND", sku="PB-01", native=True,
        zones=_ZONES, hierarchy_lines=hierarchy,
        motif_spec=_motif_spec() if motif else None)


#: The four front states, declared ONCE. Written out per test they were four
#: copies of one list, which is the §AR2 shape this tranche is about — a state
#: added to three of them and forgotten in the fourth is exactly the hole that
#: let the motif front go unmeasured in the first place.
#:
#: ``descriptor`` is the ONLY declared brand tier (AU1, and ``BRAND_KINDS``
#: refuses anything else). The first draft of this file wrote ``"support"``
#: and §AX's own guard refused the commit — a tier invented by an executor is
#: §AE2(c) work under §AE1 cover, which is the thing the charter reserves.
#: The ⟪PROVISIONAL⟫ marker is what makes the placeholder legible to the
#: runtime guard as well as to a reader; nothing here is emitted.
_SUPPORT_TIER = {"text": "⟪PROVISIONAL⟫ PLACEHOLDER-SUPPORT",
                 "rel": 0.7, "kind": "descriptor"}
_NAME_TIER = {"text": "PLACEHOLDER-BRAND", "rel": 1.0, "kind": "product_name"}

_STATES = [
    (None, False, "NOW — no hierarchy, no motif (the fixture's state)"),
    (None, True, "NOW — motif field, no hierarchy (the LIVE call site)"),
    ([_NAME_TIER, _SUPPORT_TIER], True,
     "FUTURE — hierarchy + motif, all three divider gates open"),
    ([_NAME_TIER], False, "FUTURE — hierarchy, motif absent"),
]

#: the three states §AY2 could and did clear — every state but the live one,
#: which is what TestTheStateTheLiveComposerActuallyEmits is about.
_CLEARED = [s for s in _STATES if s[:2] != (None, True)]


#: The ground the live front's mark is ACTUALLY printed on, and the reason
#: every assertion below that used to read ``background="pure_white"`` now
#: reads this instead.
#:
#: §BA ruled the motif field a SURFACE. A surface is a GROUND. So on any state
#: carrying a motif, ``pure_white`` stopped being a conservative simplification
#: and became a FALSE statement about what was measured — and a load-bearing
#: one: with §BA's exclusion in and ``pure_white`` still declared, the live
#: front reports ``clean=True, codes=[]``. Eighteen findings would have become
#: a clean bill of health rather than the one honest red BA3(b) predicted.
#:
#: THE SPELLING CARRIES NO BEHAVIOUR AND IS NOT A NEW TAXONOMY TERM.
#: ``evaluate_brand_usage`` treats every string outside
#: ``BACKGROUNDS_PERMITTED`` + ``BACKGROUND_REVERSED_ONLY`` identically, so
#: this could be any honest description of the ground and the code emitted
#: would be the same. Adding it to ``BACKGROUNDS_PERMITTED`` is what
#: BA3(d) forbids in as many words; so is switching it to something that
#: passes, and so is switching it to ``None`` to get UNMEASURED instead of a
#: red. It is owner row **C12** and it is not this file's to make green.
#:
#: **THIS CONSTANT READ ``"motif_field"`` WHEN FIRST WRITTEN, AND THAT WAS
#: WRONG — CAUGHT BY GOING TO RENDER THE PICTURE, NOT BY REREADING.** The
#: motif is never underneath the mark. Its strands are drawn *into* the same
#: field and pass *behind* and *around* the mark; the thing the ink actually
#: lands on is a ``decoration-field`` rect filled ``_tint(body, 0.55)`` =
#: **#F6EDEB** (``compose_container.py:383``), opaque (``SolidFill.opacity``
#: defaults to 1.0), painted after ``body`` and containing the mark's box —
#: so it occludes ``body`` completely under the mark. I had conflated §BA's
#: sense of "ground" (a group whose extent ENCLOSES the mark — which
#: ``motif-front`` genuinely is) with the sense ``background=`` declares (the
#: TONE the mark is reproduced on). §BA's rule is unaffected; only my name for
#: the result was. The measurement now comes from ``_ground_of``, which reads
#: the document instead of trusting either name.
LIVE_FRONT_GROUND = "decoration_field_tint"

#: The ground on the states that emit NO decoration field — and a finding §BA
#: did not commission, filed as owner row **C13** and NOT fixed here.
#:
#: BA-4 says to declare the truthful ground and commit what the instrument
#: says. Deciding what is truthful required looking, so I looked: for each of
#: the four states, every OPAQUE filled node, in paint order, whose ink box
#: CONTAINS the mark's box. The answer is not one colour, it is two, and which
#: one applies is decided by a branch:
#:
#: * ``_native_decoration`` (``compose_container.py:241`` is the ``def``; the
#:   branch is sixteen lines further down at **:257**) branches on
#:   ``if direct_print and hierarchy:`` and returns a ``FRONT_DIRECT_PRINT``
#:   group that emits **no field rect at all** — the type prints straight on
#:   the material. Both FUTURE states take it, and their mark lands on
#:   ``body`` at **#EAD7D2** (``_DEFAULT_BODY``, ``compose_container.py:114``).
#: * Otherwise a ``decoration-field`` rect is emitted at
#:   ``_tint(body_c, 0.55)`` = **#F6EDEB**. Both NOW states take this branch —
#:   **including the live call site** — and their mark lands on that.
#:
#: **The motif does not change the answer.** Panels 2 and 3 of the rendered
#: comparison in ``docs/visual_quality/ba4_grounds/`` are the same tint; the
#: motif adds strands behind and beside the mark, not underneath it.
#:
#: **So ``pure_white`` was not merely made false by §BA. It was already false,
#: on every state, before §BA was written.** C12 says "the mark is printed on
#: motif, not on white"; the measurement says that on a front with no motif at
#: all it is still not on white, and that even WITH a motif the tone under the
#: mark is a flat tint rather than the motif. That widens C12 rather than
#: answering it, so it is C13's row.
#:
#: Declaring ``pure_white`` here would assert ``background_permitted is True``
#: for a ground measured at #F6EDEB or #EAD7D2, which is the same move BA3(d)
#: forbids one level down — choosing the declaration most likely to be green.
BARE_FRONT_GROUND = "container_body_tint"

#: The two measured grounds, by the hex the composer actually produces. A
#: colour that is not in here is not silently declared as something else: it
#: raises, because an unnamed ground is exactly the condition C13 exists to
#: stop being invisible.
_GROUND_BY_HEX = {"#F6EDEB": LIVE_FRONT_GROUND,
                  "#EAD7D2": BARE_FRONT_GROUND}


def _ground_node(doc):
    """The node whose ink the mark is reproduced ON, read from the DOCUMENT.

    The last OPAQUE filled node, in document order, painted before the mark
    and whose box contains the mark's. The pdf/.ai emitter is flat and paints
    in document order, so "last one before the mark that contains it" is the
    one whose colour survives underneath it.

    **NOTHING IN PRODUCTION COMPUTES THIS.** ``evaluate_brand_usage`` takes
    ``background`` as an argument and believes whatever it is told — which is
    precisely how ``pure_white`` stood as a declaration on a front that has
    never been white, through every tranche that ran this gate green."""
    order = [n for n, _ in doc.walk()]
    logo = next(n for n in order if str(getattr(n, "name", "")) == "logo")
    logo_box = _ink_box(logo)
    under = None
    for node in order:
        if node is logo:
            break
        fill = getattr(node, "fill", None)
        if fill is None or getattr(fill, "opacity", 1.0) < 1.0:
            continue
        box = _ink_box(node)
        if box is not None and _contains(box, logo_box):
            under = node
    return under


def _ground_of(doc) -> str:
    """The truthful declaration for a composed state — MEASURED, not assumed.

    Keyed on the document rather than on ``motif``, which is what the first
    version of this function used and which was simply the wrong variable: the
    branch that decides the ground is ``direct_print and hierarchy``, and the
    motif does not appear in it. Reading the document means a future change to
    that branch cannot leave a stale declaration behind — it either produces a
    hex this file has named, or it raises."""
    node = _ground_node(doc)
    assert node is not None, "no opaque ground under the mark"
    color = node.fill.color
    hexed = "#%02X%02X%02X" % (round(color.r * 255), round(color.g * 255),
                               round(color.b * 255))
    assert hexed in _GROUND_BY_HEX, (
        f"unnamed ground {hexed} under the mark, from node "
        f"{getattr(node, 'name', '?')!r} — name it and say so in C13 rather "
        f"than declaring it as something already in the table")
    return _GROUND_BY_HEX[hexed]


def _intruders(doc, ground: str = LIVE_FRONT_GROUND) -> list:
    """The clear-space findings by name.

    ``ground`` is an argument with a default rather than a fixed constant so
    that the claim "the background declaration cannot move this list" is a
    thing a caller can try rather than a thing this docstring asserts —
    ``test_the_clear_space_axis_does_not_depend_on_the_BACKGROUND_declaration``
    below tries it, on every state, across the whole declaration table."""
    rec = evaluate_brand_usage(doc, background=ground)
    return sorted(f["node_name"]
                  for f in rec["placements"][0]["clear_space_findings"])


def _motif_leaves(doc) -> list:
    """The motif field's own ink, read from the DOCUMENT.

    Every test in this file that wanted "the strands" used to get them from
    ``_intruders``, i.e. from the detector's output. §BA takes that output to
    zero, which would have left three tests asserting things about an empty
    list and passing vacuously — green for the reason a test is supposed to go
    red. A property of the artwork is read off the artwork."""
    group = next((n for n, _p in doc.walk()
                  if getattr(n, "name", "") == "motif-front"), None)
    assert group is not None, "the live front stopped composing a motif field"
    out: list = []
    stack = [group]
    while stack:
        node = stack.pop()
        if getattr(node, "type", "") == "group":
            stack.extend(node.children)
        else:
            out.append(node)
    return out


def _containment(doc) -> list:
    return cp.validate_zone_containment(
        doc.metadata.get("placements") or [], _ZONES, _PROFILE)


class TestCapHeightIsMeasuredPerAssetAndNeverAssumed:
    """§AW3 — ``0.856667`` is one file's number, not the module's."""

    def test_it_reproduces_the_hand_measurement_in_aw2(self):
        """§AW2(c) measured the flat-capital band of ``media/brand/logo.png``
        by hand at 257 px of a 300 px canvas. The instrument must agree, or
        one of the two is wrong and the section is unsafe to build on."""
        band = measure_cap_ratio(settings.BRAND_LOGO_PATH)
        assert band is not None
        assert band["canvas_px"] == [1439, 300]
        assert band["cap_band_px"] == 257
        assert band["cap_ratio"] == 0.856667

    def test_the_mark_with_no_cap_band_measures_as_UNMEASURED(self):
        """THE CASE THAT FORCED THE SHARE FLOOR TO EXIST.
        ``bbrose_logo_approved.png`` has NO alpha channel and is a light
        coloured mark on white. An alpha-only reader called every column
        inked and returned a cap ratio of 1.000000 — which would then have
        demanded clear space equal to the mark's FULL placed height, a gate
        made stricter by a bug and looking exactly like a measurement."""
        assert os.path.exists(_APPROVED), "the second brand asset moved"
        assert measure_cap_ratio(_APPROVED) is None

    def test_the_floor_is_not_wedged_between_the_two_samples(self):
        """A threshold tuned to the files it was tested on describes those
        files. The passing asset's winning edges carry 40.16% and 29.35% of
        inked columns; the failing one's carry 4.51% and 4.01%. The 10% floor
        sits BELOW the lowest pass and ABOVE the highest fail by wide margins,
        and this test pins those margins so that shrinking the gap to admit
        some future asset is a visible act."""
        band = measure_cap_ratio(settings.BRAND_LOGO_PATH)
        assert band["cap_line_share"] > CAP_BAND_MIN_SHARE * 2.5
        assert band["baseline_share"] > CAP_BAND_MIN_SHARE * 2.0
        assert CAP_BAND_MIN_SHARE == 0.10

    def test_an_unreadable_asset_is_UNMEASURED_not_zero(self, tmp_path):
        junk = tmp_path / "not-an-image.png"
        junk.write_bytes(b"this is not a PNG")
        assert measure_cap_ratio(str(junk)) is None
        assert measure_cap_ratio("/no/such/file.png") is None


class TestTheGateFiresOnTheArtworkTheRepositoryShips:
    """§AA — watch it refuse a REAL violation, not a constructed one."""

    def test_the_front_the_repository_emits_today_FAILS_this_gate(
            self, emitted_front):
        """THE TRANCHE'S BEST OUTPUT, and it is a failure.

        The front's own product name sits inside the logo's clear space. This
        is a defect in the LAYOUT — §AE1's and mine to fix — measured against
        a RULE that is §AE2(c)'s and the owner's to keep. The rule does not
        move. Per §AW5(c) the correction is a separate tranche and this
        failing measurement is committed first, so this assertion is expected
        to be INVERTED by a later tranche and must not be deleted by one.

        INVERTED 2026-08-21 BY §AY2 / AZ5, AND THE NAME IS NOW WRONG IN A WAY
        WORTH KEEPING. What inverted it: ``compose_container`` now derives a
        keep-out from the mark's own placed box and drops the front stack
        below it, so ``product-name-0``'s ink top clears 77.2674 mm and the
        superseded shortfall of 1.5124 mm is gone. The mark did NOT move and
        did not shrink — AY2 step 1, not step 2, on the vertical budget AZ5(c)
        measured.

        THE NAME IS WRONG BECAUSE THIS FIXTURE IS NOT WHAT THE REPOSITORY
        EMITS. It composes with no ``motif_spec``; BOTH production call sites
        pass one (``_live_front`` counts them). That state is
        measured by ``TestTheStateTheLiveComposerActuallyEmits`` below and it
        STILL FAILS, with eighteen intruders no vertical move can clear. The
        name is left standing rather than quietly corrected so that the gap
        between "the fixture" and "the front" stays legible (§AY0(d): a
        quantity carries the state it was measured in).

        RE-INVERTED 2026-08-22 BY BA-4, AND THE NAME IS RIGHT AGAIN. This read
        ``assert rec["clean"] is True`` from §AY2 until this line was written.
        It is now False, and NOTHING ABOUT THE LAYOUT CHANGED to make it so —
        the clear-space axis below is untouched and still passes. What changed
        is that the call stopped declaring ``background="pure_white"`` about a
        document whose mark is printed on **#F6EDEB**.

        THIS SITE WAS FOUND LATE AND IT MATTERS THAT IT WAS. BA-4's correction
        was applied to the two ``_live_front`` call sites first, and this file
        then contained both "the ground is measured, never declared" and a
        ``pure_white`` declaration over the same #F6EDEB ground, three hundred
        lines apart. Four other ``emitted_front`` sites were declaring it too;
        those four are on the size and screen axes and the truthful ground
        changed nothing there, which is the point — the value was incidental at
        four sites and LOAD-BEARING at this one. A green that only one of five
        identical declarations was holding up is the green worth finding.

        So ``clean`` was True here on a false declaration, and the honest
        verdict is red on ONE code. Per BA-4 the red is committed, not
        negotiated: "if the truthful declaration produces
        CODE_BACKGROUND_FORBIDDEN, commit the red." Whether #F6EDEB is a
        permitted ground is §AE2(c) and is owner row C13. This assertion
        inverts again when C13 is answered, and not before."""
        rec = evaluate_brand_usage(emitted_front,
                                   background=_ground_of(emitted_front))
        assert rec["schema_version"] == SCHEMA
        assert rec["clean"] is False
        assert CODE_BACKGROUND_FORBIDDEN in rec["codes"]
        # the axis that was ever in question here is UNMOVED and still green
        assert CODE_CLEAR_SPACE_VIOLATED not in rec["codes"]
        assert rec["meets_clear_space"] is True
        assert rec["codes"] == [CODE_BACKGROUND_FORBIDDEN], (
            "the truthful declaration must cost exactly ONE code; a second "
            "would mean this edit changed something other than the ground")

    def test_it_names_which_element_intrudes_and_by_how_much(self):
        """A gate that says only "clear space violated" cannot be acted on by
        whoever has to move something. §AW2(e) measured the shortfall at
        1.5127 mm from the ROUNDED placement; the instrument works from the
        unrounded geometry and gets 1.5124 mm. Both are pinned loosely enough
        that the 0.0003 mm difference is not mistaken for a contract.

        RETARGETED 2026-08-21. Those two numbers described ``product-name-0``
        on the fixture front, and §AY2 moved that text out of the margin, so
        there is no longer a finding there to name. They are kept in this
        docstring because AY0(b) pinned them as the measurement of a state
        that existed — not deleted, superseded.

        THE NAMING BEHAVIOUR IS STILL MEASURED AGAINST A REAL VIOLATION AND
        NOT A CONSTRUCTED ONE, which was this class's whole reason for
        existing (§AA). The violation it uses is the one the live composer
        actually emits, so this test got MORE honest by being retargeted, not
        less.

        RE-TARGETED AGAIN 2026-08-22 BY §BA, AND THE NUMBERS ABOVE COME BACK.
        §BA ruled the motif field a SURFACE, so the eighteen strand findings
        this test was pointed at in August are gone — not fixed, reclassified,
        and the front now reports ZERO clear-space findings. A test needs a
        violation to name.

        The one it now names is the SAME ONE the paragraph above called
        superseded: forcing ``_front_keepout_y`` to return None reproduces the
        composer's own pre-§AY2 output exactly, and ``product-name-0`` returns
        at a shortfall of **1.5124 mm** — §AY0(b)'s pinned number, recovered as
        a live assertion instead of a docstring memory. That is a REAL state
        the repository emitted for weeks, reached by removing one call, not a
        Document built by hand to have a violation in it.

        AND IT IS THE THIRD WITNESS §BA2(e) DEMANDS, on the live front rather
        than a fixture: this finding is a TEXT node, inside the motif field's
        vertical span, and the ground exclusion does not silence it. If a
        future edit ever lets membership propagate to text, this goes green and
        says so."""
        import apps.ire.compose_container as ccx
        real = ccx._front_keepout_y
        try:
            ccx._front_keepout_y = lambda *a, **k: None
            rec = evaluate_brand_usage(_live_front(),
                                       background=LIVE_FRONT_GROUND)
        finally:
            ccx._front_keepout_y = real
        findings = rec["placements"][0]["clear_space_findings"]
        assert findings, rec["placements"][0]
        worst = findings[0]
        assert worst["node_type"] == "text"
        assert worst["node_name"] == "product-name-0"
        assert worst["gaps_mm"] == {"below": 1.5737}
        assert worst["required_mm"] == 3.0861
        assert worst["shortfall_mm"] == 1.5124, worst

    def test_the_size_floor_PASSES_and_the_two_axes_are_independent(
            self, emitted_front):
        """AU6(c) bet that the 12.0 mm floor would not fit. It fits with room
        — §AW2(d) — and the gate still fails, on a different axis. Recording
        both keeps the section honest about WHICH bet was lost."""
        rec = evaluate_brand_usage(emitted_front,
                                   background=_ground_of(emitted_front))
        assert rec["meets_minimum_size"] is True
        assert CODE_BELOW_MINIMUM_SIZE not in rec["codes"]
        placement = rec["placements"][0]
        assert placement["reproduced_width_mm"] > MINIMUM_WIDTH_MM_PRINT

    def test_a_document_with_no_logo_produces_no_record(self):
        doc = Document(page_w=50.0, page_h=30.0, title="none",
                       root=Group(name="Root", role="artwork", children=[]))
        assert evaluate_brand_usage(doc, background="pure_white") is None


class TestTheStateTheLiveComposerActuallyEmits:
    """INVERTED 2026-08-22 BY §BA (OWNER-RULED). THE HEADLINE IS STILL A
    FAILURE — ON A DIFFERENT AXIS, WHICH IS THE ONLY HONEST WAY TO READ IT.

    Everything from "THIS CLASS'S HEADLINE ASSERTION" down is the pre-ruling
    record and is kept verbatim, per BA2(d), because it is the measurement of
    a state that existed. What changed is not the artwork and not a bar. §BA
    ruled that a rendered decoration field the mark is composed on top of is
    the GROUND the mark is printed on rather than eighteen neighbours crowding
    it, so the eighteen findings below are not fixed — they are RECLASSIFIED,
    and they leave the clear-space axis entirely.

    **NO BAR MOVED** (BA1(d)): not the 1.0x cap height, not the 12.0 mm floor,
    not ``BACKGROUNDS_PERMITTED``. The mark is still 17.28 mm at
    ``[61.36, 70.579, 17.28, 3.603]`` and every strand is still exactly where
    it was; the last paragraph below — "the obvious way to make this green is
    to widen the instrument's GROUND exclusion" — describes precisely the edit
    that has now been made, and the reason it was refused there and is
    permitted here is the ONLY thing that changed: the owner ruled the
    category first, in commit ``c44c7d2``, before a line of it was written
    (§AE0(b), BA1(c)).

    **AND IT DID NOT CLEAR THE FRONT.** The mark moved onto the BACKGROUND
    axis, where a motif field is a tinted ground `BACKGROUNDS_PERMITTED` does
    not name. Eighteen clear-space findings became ONE
    ``BRAND_LOGO_BACKGROUND_FORBIDDEN``. Reporting C11 as having cleared the
    front is the false claim this docstring exists to pre-empt; it cleared the
    axis it was asked about, and the new axis is owner row **C12**.

    ---- the pre-ruling record, unedited ----

    THIS CLASS'S HEADLINE ASSERTION IS A FAILURE, ON PURPOSE, AND IT IS THE
    SECOND TIME THIS FILE HAS HELD ONE.

    §AY2 cleared the front of TEXT intruders. It did not clear the front. The
    fixture the original headline measured omits ``motif_spec``; both
    production call sites (counted in ``_live_front``) pass
    ``logo_path`` AND ``motif_spec`` AND no ``hierarchy_lines``, so whenever a
    concept carries a motif signal the mark is placed on a rendered motif
    FIELD — and every element of that field runs from 68.5240 mm to
    102.4160 mm, entering the mark's clear band at 67.4929..77.2674 from
    inside it and continuing past the mark to the bottom of the zone.

    AY2's ordering was written for exactly this and its step 1 does not apply.
    "MOVE THE INTRUDER if the vertical budget exists" presumes the intruder
    HAS a vertical position; a strand spanning the zone has none, and there is
    no budget because there is no degree of freedom. Step 2 does not apply
    either, and for a stronger reason than AZ5's 62.3% arithmetic: fourteen of
    the eighteen findings report ``{"overlapping": 0.0}``, meaning the strand
    crosses the mark's own box rather than merely its margin, so no reduction
    of the mark's SIZE removes them. What is left is step 3 — "the front
    cannot carry the logo at ruled clear space" — which AY2 rules is referred
    back and not the executor's to execute.

    WHAT IS NOT DONE HERE, DELIBERATELY. The obvious way to make this green is
    to widen the instrument's GROUND exclusion so that a field of strands
    counts as the surface the mark sits on rather than as eighteen neighbours.
    That may well be the right rule — it is a real question and this file does
    not answer it — but ``_clear_space_findings``' own docstring says the
    exclusion "is a rule about containment, not a list of node names, so it
    cannot quietly grow to cover an inconvenient finding", and widening it
    here would be weakening a detector to fit the artwork (§AL4 / §Y2, and
    §AU6(c) in as many words). The question goes to the owner; the failure
    stays visible until it is answered.
    """

    def test_the_live_front_STILL_FAILS_but_now_on_the_BACKGROUND_axis(self):
        """INVERTED BY §BA. Was
        ``test_the_live_front_STILL_FAILS_and_no_vertical_move_can_fix_it``,
        asserting ``CODE_CLEAR_SPACE_VIOLATED``.

        THE HEADLINE — ``clean is False`` — IS UNCHANGED AND THAT IS THE
        POINT. The front the composer emits is still refused. What the ruling
        changed is WHICH axis refuses it and how many findings it takes to say
        so: eighteen became one, and the one is honest where the eighteen were
        arguably a category error.

        The old name is recorded here rather than kept, because "no vertical
        move can fix it" is still TRUE and is now beside the point — nothing
        about the geometry was ever the problem."""
        rec = evaluate_brand_usage(_live_front(),
                                   background=LIVE_FRONT_GROUND)
        assert rec["clean"] is False
        assert CODE_CLEAR_SPACE_VIOLATED not in rec["codes"]
        assert rec["meets_clear_space"] is True
        assert CODE_BACKGROUND_FORBIDDEN in rec["codes"]
        assert rec["background_permitted"] is False

    def test_declaring_pure_white_here_NO_LONGER_buys_a_CLEAN_FRONT(self):
        """§AE0(e), §BB1(e)(1). The assertion this replaces is QUOTED rather
        than deleted, because the whole value of the old test was what it
        caught and a reader needs to see it to know what moved.

        UNTIL §BB1 THIS TEST READ, VERBATIM:

            false_ = evaluate_brand_usage(_live_front(),
                                          background="pure_white")
            assert false_["clean"] is True and false_["codes"] == []

        AND IT PASSED. That was the near-miss made permanent: §BA's exclusion
        and the old ``background="pure_white"`` declaration, together, took
        this front from eighteen findings to ``clean=True, codes=[]``. Landing
        the exclusion without BA-4 would not have under-reported the front, it
        would have CERTIFIED it — on a front that has never been white.

        WHAT CHANGED IS THE INSTRUMENT, NOT THE DECLARATION. §BB1(e)(1)
        authorised production to COMPUTE the ground, so the caller's word is
        no longer the only evidence the gate has. A false declaration now buys
        nothing: the measured axes refuse this front on their own evidence,
        and they refuse it for a reason the caller cannot reach.

        THE DECLARED AXIS IS STILL LIVE AND STILL DOES ITS JOB. That is the
        second half. Both declarations produce a red; they differ by exactly
        the one code the declaration is responsible for, and NEITHER can
        produce a clean. That is the two-axis property stated as a behaviour:
        neither axis can lie for the other."""
        false_ = evaluate_brand_usage(_live_front(), background="pure_white")
        # the declaration is ACCEPTED on its own axis — "pure_white" really is
        # a permitted ground — and it no longer decides the verdict.
        assert false_["background_permitted"] is True
        assert false_["clean"] is False
        assert false_["codes"] == [CODE_MOTIF_OVER_MARK,
                                   CODE_MOTIF_UNMEASURED]

        true_ = evaluate_brand_usage(_live_front(),
                                     background=LIVE_FRONT_GROUND)
        assert true_["clean"] is False
        assert true_["codes"] == [CODE_BACKGROUND_FORBIDDEN,
                                  CODE_MOTIF_OVER_MARK,
                                  CODE_MOTIF_UNMEASURED]

        # The ONLY difference the declaration makes is its own code. The
        # measured axes are byte-identical across the two calls, which is what
        # "cannot be argued with by a caller" means operationally.
        assert (set(true_["codes"]) - set(false_["codes"])
                == {CODE_BACKGROUND_FORBIDDEN})
        for key in ("ground_node", "ground_hex", "ground_resolved",
                    "ground_permitted", "motif_strands_over_mark",
                    "meets_motif_density"):
            assert false_[key] == true_[key], key
        # and the ground it measured is the one the document actually paints
        assert false_["ground_node"] == "decoration-field"
        assert false_["ground_hex"] == "#F6EDEB"
        assert false_["ground_resolved"] == "brand_light_ground"
        # the axis that was never in question here is still untouched
        assert (false_["placements"][0]["clear_space_findings"]
                == true_["placements"][0]["clear_space_findings"] == [])

    def test_no_strand_is_an_intruder_any_more_and_none_was_moved(self):
        """INVERTED BY §BA. Was
        ``test_every_intruder_is_a_motif_strand_and_none_is_text``, which
        asserted ``names`` was non-empty and every name a strand.

        Its docstring said: "If a text node ever reappears here the keep-out
        has regressed, and that is a different failure from the motif one this
        class is about." **That property is the one thing here that must NOT
        weaken**, so it is asserted in the stronger direction now — the whole
        finding list is empty, so a text node reappearing fails this test by
        arithmetic rather than by a ``startswith`` that no longer runs.

        AND THE SECOND HALF IS THE ANTI-TUNING CHECK. The eighteen strands are
        read from the DOCUMENT, not from the detector's output, and asserted
        still present and still in the mark's clear band. "Zero findings"
        because the artwork was silently changed and "zero findings" because
        the ruling reclassified it are indistinguishable from the finding list
        alone; they are not indistinguishable from here."""
        assert _intruders(_live_front()) == []

        doc = _live_front()
        rec = evaluate_brand_usage(doc, background=LIVE_FRONT_GROUND)
        p = rec["placements"][0]
        _lx, ly, _lw, lh = p["placed_mm"]
        band = (ly - p["logo_cap_height_mm"], ly + lh + p["logo_cap_height_mm"])
        strands = _motif_leaves(doc)
        assert len(strands) == 18, sorted(str(n.name) for n in strands)
        assert all(str(n.name).startswith(("flow-line", "ribbon"))
                   for n in strands)
        crossing = [str(n.name) for n in strands
                    if (b := _ink_box(n)) and b[1] < band[1] and b[3] > band[0]]
        assert len(crossing) == 18, crossing

    def test_moving_any_strand_clear_runs_it_off_the_bottom_of_the_zone(self):
        """§AY0(d): "there is no vertical budget" is a MEASUREMENT, so it is
        measured rather than asserted in a docstring.

        THE FIRST DRAFT OF THIS TEST MEASURED THE WRONG PROPERTY AND FAILED,
        WHICH IS WHY THIS ONE EXISTS. It asserted each strand's ink box sits
        ABOVE the mark's band and BELOW it — "spans the band" — and
        ``flow-line-0`` refuted it: the strands begin at 68.5240, which is
        INSIDE the band (67.4929..77.2674), not above it. The claim was close
        enough to true to have been believed if it had been left in prose.

        What is actually true is the statement AY2 step 1 turns on: applying
        the SAME keep-out that moved the type — drop the element until its ink
        top reaches ``keepout_y`` — drives every strand's bottom edge past the
        floor of the zone it is drawn in. The zone is read off the emitted
        ``decoration-field`` rather than recomputed from the backbone, so this
        does not keep a second copy of the composer's geometry (§AR2).

        RE-SOURCED 2026-08-22, AND IT WOULD HAVE GONE SILENTLY GREEN OTHERWISE.
        ``wanted`` was ``set(_intruders(doc))`` — the DETECTOR's output. §BA
        takes that to zero, so the loop would have run no iterations and
        ``assert seen == len(wanted)`` would have compared 0 to 0 and passed.
        A test measuring nothing, reporting success, in the tranche whose whole
        risk is an exclusion that silences too much. BA2(d) named the two tests
        that would FAIL; this is the one that would not, which is why it needed
        looking for rather than waiting for.

        The strands now come from the motif group in the document, so this
        keeps measuring the same property — "the AY2 keep-out cannot be applied
        to a strand without pushing it off the floor" — whether or not those
        strands are reported by anything."""
        doc = _live_front()
        rec = evaluate_brand_usage(doc, background=LIVE_FRONT_GROUND)
        p = rec["placements"][0]
        _lx, ly, _lw, lh = p["placed_mm"]
        keepout_y = ly + lh + p["logo_cap_height_mm"]

        field = next(_ink_box(n) for n, _ in doc.walk()
                     if str(getattr(n, "name", "") or "") == "decoration-field")
        floor = field[3]
        strands = _motif_leaves(doc)
        assert len(strands) == 18, len(strands)
        seen = 0
        for node in strands:
            box = _ink_box(node)
            assert box is not None
            shift = keepout_y - box[1]
            assert shift > 0, (node.name, box)
            assert box[3] + shift > floor, (node.name, box, shift, floor)
            seen += 1
        assert seen == len(strands), (seen, len(strands))


class TestProductionsOwnLayoutMoved:
    """THE COMMIT MESSAGE THAT SHIPPED THIS KEEP-OUT SAID THIS DID NOT HAPPEN.

    ``02ff1c9``, under WHAT THIS DOES NOT CLAIM, in the section whose whole
    job is to stop false sentences: *"Production supplies no
    ``hierarchy_lines``, so the shift is computed and applied only in states a
    test composes. What production gets today is the ``is not None`` guard and
    an unchanged layout."* **Every clause of that is false except the first**,
    and a fresh-agent audit found it in the landed commit (AZ0(t)).

    There are TWO shift sites. The direct-print one is reached only under
    ``if direct_print and hierarchy:``. The other — the one production takes —
    is guarded by ``if keepout_y is not None:`` and **no hierarchy condition
    whatsoever**, so it fires whenever a mark is placed. That is every
    non-dropper front the repository composes.

    This test exists because prose was where the error lived. A sentence in a
    commit message cannot be re-run; this can. It is deliberately written as a
    BEHAVIOURAL check on production's own arguments rather than a grep for the
    guard's text, because the false sentence was itself produced by reading
    code and reasoning about it (§AA).

    NOTE THE DIRECTION OF THE ERROR, because it is the one worth guarding.
    Nothing was overclaimed: a LIMITATION was overclaimed. The instinct — be
    conservative, assume the change reached less than it did — is the right
    instinct, and it is exactly what made the sentence feel safe enough to
    skip checking. §AE0(e) has to cover understatement too: an unverified
    claim that something did NOT happen is not the cautious version of a
    claim, it is a claim.
    """

    def _name_baselines(self, doc) -> list:
        return sorted((str(n.name), round(float(n.y), 4))
                      for n, _p in doc.walk()
                      if isinstance(n, TextRun)
                      and str(getattr(n, "name", "") or "").startswith(
                          "product-name"))

    def test_the_front_production_composes_today_MOVED_by_1_5125_mm(self):
        """The before column is the pre-tranche composer reproduced exactly:
        forcing ``_front_keepout_y`` to None makes both sites take
        ``shift = 0``, which is the arithmetic that stood before ``02ff1c9``.
        Arguments are ``_live_front()``'s — ``motif_spec``, live
        ``BRAND_LOGO_PATH``, **no ``hierarchy_lines``** — i.e. exactly what
        ``targets/container/__init__.py:1081`` passes."""
        import apps.ire.compose_container as ccx
        after = self._name_baselines(_live_front())
        real = ccx._front_keepout_y
        try:
            ccx._front_keepout_y = lambda *a, **k: None
            before = self._name_baselines(_live_front())
        finally:
            ccx._front_keepout_y = real

        assert [n for n, _ in before] == [n for n, _ in after]
        assert before == [("product-name-0", 77.7700)], before
        assert after == [("product-name-0", 79.2825)], after
        assert after[0][1] - before[0][1] == pytest.approx(1.5125, abs=1e-4)

    def test_the_moved_node_belongs_to_the_branch_WITHOUT_a_hierarchy_guard(
            self):
        """Which of the two shift sites moved it, established by discriminating
        the branches rather than by asserting the input.

        THE FIRST VERSION OF THIS TEST COULD NOT FAIL, which is the same
        defect the audit that prompted this class had just found elsewhere in
        this file. It read ``doc.metadata.get("hierarchy_lines") in (None, [],
        ())`` — and ``hierarchy_lines`` is not a metadata key at all, so
        ``.get`` returned None unconditionally and the assertion was true for
        every possible document. Writing an unfalsifiable assertion INTO the
        commit that fixes unfalsifiable assertions is the §AR2 shape one level
        up, and it is recorded rather than quietly deleted.

        The branches are told apart by what they EMIT: direct print composes
        ``product-name-hero`` and ``front-descriptor``; the ``else`` composes
        ``product-name-0``. The moved node is ``product-name-0``, so the shift
        that moved it is the one guarded by ``if keepout_y is not None:`` with
        no hierarchy condition — production's path."""
        live = {str(n.name) for n, _ in _live_front().walk()
                if getattr(n, "name", None)}
        hier = {str(n.name) for n, _ in
                _live_front(hierarchy=_STATES[2][0]).walk()
                if getattr(n, "name", None)}
        assert "product-name-0" in live and "product-name-0" not in hier
        assert {"product-name-hero", "front-descriptor"} <= hier
        assert not {"product-name-hero", "front-descriptor"} & live

    def test_the_move_is_what_cleared_the_text_and_the_message_said_so(self):
        """``02ff1c9``'s own four-state table records the LIVE row going
        ``19 -> 18  product-name-0``. A finding cannot clear without something
        moving. The refutation of the false sentence was two screens above it
        in the same document; both facts were in hand and their contradiction
        was asserted anyway.

        COUNTS UPDATED 2026-08-22 BY §BA: ``19 -> 1`` and ``18 -> 0``, because
        the eighteen strands left the clear-space axis. **The assertion that
        carries the meaning is untouched** — ``before - after`` is still
        exactly ``{"product-name-0"}`` — and the ruling made this test SHARPER
        rather than weaker: ``before`` is now that one TEXT finding and nothing
        else, which is §BA2(e)'s third witness stated on the live front. If the
        ground exclusion ever propagated to text, ``before`` would be empty and
        this fails on the first assertion, not the counts."""
        import apps.ire.compose_container as ccx
        after = set(_intruders(_live_front()))
        real = ccx._front_keepout_y
        try:
            ccx._front_keepout_y = lambda *a, **k: None
            before = set(_intruders(_live_front()))
        finally:
            ccx._front_keepout_y = real
        assert before - after == {"product-name-0"}, (before, after)
        assert len(before) == 1 and len(after) == 0


class TestTheKeepOutClearsTheStatesWhereABudgetExists:
    """§AY2 step 1 measured on BOTH states the owner named, plus the third.

    AZ5(c) ruled the vertical budget exists and step 1 is the branch. It does,
    and it is: the mark stays at its ruled 17.28 mm in every state below —
    step 2 is never reached and the 12.0 mm floor is never approached, let
    alone moved.
    """

    @pytest.mark.parametrize("hierarchy,motif,label", _CLEARED)
    def test_the_front_is_clear_of_the_mark(self, hierarchy, motif, label):
        """RE-SCOPED BY BA-4 FROM ``rec["clean"]`` TO THE CLEAR-SPACE AXIS,
        which is the axis this class is named for and the only one the
        keep-out ever bought.

        ``clean`` is the whole-record verdict — size, background AND clear
        space. Asserting it here was always wider than the claim: it passed
        only because ``background="pure_white"`` was declared, and BA-4
        establishes that declaration was false. With the truthful one it goes
        red on the BACKGROUND axis, which says nothing about whether §AY2's
        keep-out worked. **The two lines below are what "the front is clear of
        the mark" actually means**, they are unchanged in substance, and they
        are still green under a declaration that fails the record."""
        doc = _live_front(hierarchy=hierarchy, motif=motif)
        rec = evaluate_brand_usage(doc, background=_ground_of(doc))
        assert rec["placements"][0]["meets_clear_space"] is True, label
        assert rec["placements"][0]["clear_space_findings"] == [], label
        # and the red it now carries is the BACKGROUND one, not a clear-space
        # one wearing a different name (§AE0(e): the failure is reported, not
        # routed around)
        assert rec["clean"] is False, label
        assert CODE_BACKGROUND_FORBIDDEN in rec["codes"], label
        assert CODE_CLEAR_SPACE_VIOLATED not in rec["codes"], label

    @pytest.mark.parametrize("hierarchy,motif,label", _STATES)
    def test_the_mark_never_moves_and_never_shrinks(self, hierarchy, motif,
                                                    label):
        """AY2 step 1 keeps the logo at ruled size. If a future edit ever
        bought clearance by shrinking the mark instead of moving the type,
        this fires before the size gate does.

        Asserted on ALL FOUR states including the one that still fails: the
        mark's placement is not what is wrong there, and a remedy that moved
        or shrank it would be step 2 or step 3 taken without a ruling."""
        doc = _live_front(hierarchy=hierarchy, motif=motif)
        rec = evaluate_brand_usage(doc, background=_ground_of(doc))
        p = rec["placements"][0]
        assert p["placed_mm"] == [61.36, 70.579, 17.28, 3.603], label
        assert p["reproduced_width_mm"] == 17.28
        assert p["reproduced_width_mm"] > MINIMUM_WIDTH_MM_PRINT
        assert p["logo_cap_height_mm"] == 3.0861

    @pytest.mark.parametrize("hierarchy,motif,label", _STATES)
    def test_containment_is_still_empty_which_is_AZ5_f_s_falsifier(
            self, hierarchy, motif, label):
        """AZ5(f): "wrong if the move re-fails containment ... falsified by
        any suite failure naming a containment or placement code on the front
        zone after the move."

        The list is asserted EMPTY rather than "free of the code I thought
        of", and the two codes are named so that a reader can see which bound
        was at risk. ``validate_zone_containment`` applies the safe-margin
        inset BEFORE the 0..1 bound, so a shift that overspent the budget
        surfaces as ZONE_SAFE_MARGIN_VIOLATION well before
        DECORATION_OUTSIDE_ZONE would ever fire.

        THE TWO CODE ASSERTIONS USED TO SIT AFTER THE EMPTINESS ASSERTION AND
        THEREFORE COULD NOT FAIL. ``joined`` was built from a list already
        asserted empty, so it was always ``""`` and ``not in ""`` is true for
        every string. A fresh-agent audit found it (AZ0(t)). The docstring
        above was honest — it claims only that a reader can SEE the bounds —
        but `02ff1c9`'s commit message claimed more than the docstring did,
        saying the codes were named "so a silently empty list cannot pass for
        a clean one". They gave no such property. They give it now: the named
        codes are checked FIRST, while ``problems`` can still be non-empty, so
        a regression that raises either one fails on the specific code and
        says which bound broke, and only then does the catch-all fire."""
        problems = _containment(_live_front(hierarchy=hierarchy, motif=motif))
        joined = " ".join(problems)
        assert cp.ZONE_SAFE_MARGIN_VIOLATION not in joined, (label, problems)
        assert cp.DECORATION_OUTSIDE_ZONE not in joined, (label, problems)
        assert problems == [], (label, problems)

    def test_the_keep_out_can_only_REMOVE_findings_never_add_one(self):
        """§AL4 as a property of the change rather than a claim about it.

        The pre-tranche composer is reproduced exactly by forcing the keep-out
        to be absent — both branches then take ``shift = 0``, which is the
        arithmetic that stood before this tranche. Every state's finding set
        after the change must be a SUBSET of the set before it. That is a
        stronger statement than "three states went green", and it is the one
        that stays true if someone adds a fourth state."""
        import apps.ire.compose_container as ccx
        real = ccx._front_keepout_y
        try:
            for hierarchy, motif, _label in _STATES:
                after = set(_intruders(_live_front(hierarchy, motif)))
                ccx._front_keepout_y = lambda *a, **k: None
                before = set(_intruders(_live_front(hierarchy, motif)))
                ccx._front_keepout_y = real
                assert after <= before, (hierarchy, motif, after - before)
                assert _containment(_live_front(hierarchy, motif)) == []
        finally:
            ccx._front_keepout_y = real


class TestTheUnmeasuredFallbackIsStricterAndIsNotJustSaidToBe:
    """AZ5(d) / §AL4, and §AA: the branch is FORCED, not described.

    ``_front_keepout_y`` needs a cap band to size the clear space. When
    ``measure_cap_ratio`` returns None it falls back to a ratio of 1.0, which
    treats the mark's FULL PLACED HEIGHT as its cap band. The safety argument
    is a property of the parameter's range rather than a promise in a comment:
    a real cap ratio cannot exceed 1.0, so the fallback can only ever demand
    MORE clearance than the measurement it stands in for.

    On the live asset the branch is not taken — ``media/brand/logo.png``
    measures at 0.856667 — so a comment claiming it is safe would be a
    sentence nobody had ever watched run (§AA, and AZ0(k) is what happened the
    last time such a sentence was trusted). This forces it.

    NOTE the deliberate asymmetry with the GATE, which is in the same
    repository and does the opposite: ``evaluate_brand_usage`` reports
    CAP_HEIGHT_UNMEASURED and declines to rule. Same formula, different
    policy, and both are right — a composer that cannot measure should reserve
    more room, and a validator that cannot measure should not issue a verdict.
    """

    def _forced(self, monkeypatch):
        import apps.ire.compose_container as ccx
        monkeypatch.setattr(ccx, "measure_cap_ratio", lambda _p: None)
        return ccx

    def test_the_fallback_demands_strictly_more_room_than_the_measurement(
            self, monkeypatch):
        """The box is DERIVED from the emitted document, not written down.

        It used to read ``box = (61.36, 70.5787491313412, 17.28,
        3.6025017373175814)`` — a verbatim copy of ``_logo_box``'s output,
        pasted into the very file whose commit message reports collapsing four
        duplicated state lists because "that is the two-copies-of-a-number
        shape, written by me, in the file arguing against it." There was a
        FIFTH copy four hundred lines further down and I did not see it; a
        fresh-agent audit did (AZ0(t)).

        It is not a harmless literal. Those seventeen digits are the composer's
        answer as of one particular commit, so if ``_logo_box`` ever moves the
        mark this test keeps asserting against where the mark USED to be, and
        the keep-out it validates would be measured from a stale box — which
        is §AR2 in its purest form, inside the test defending against §AR2."""
        import apps.ire.compose_container as ccx
        # Captured from the composer's OWN call, not rebuilt and not read off
        # the report: `placed_mm` is rounded to three decimals for the record,
        # and the cap-band identity asserted at the bottom of this test is an
        # exact one, so a rounded height would make it a near-identity that
        # passes on a tolerance. Wrapping the real function gets the argument
        # the composer actually passed, at full precision, and additionally
        # pins that the keep-out is reached at all.
        seen: list = []
        real = ccx._front_keepout_y

        def _spy(box, logo_path):
            seen.append(box)
            return real(box, logo_path)

        try:
            ccx._front_keepout_y = _spy
            _live_front()
        finally:
            ccx._front_keepout_y = real
        assert len(seen) == 1, seen
        box = seen[0]
        assert box is not None
        measured = ccx._front_keepout_y(box, settings.BRAND_LOGO_PATH)
        self._forced(monkeypatch)
        forced = ccx._front_keepout_y(box, settings.BRAND_LOGO_PATH)
        assert measured == pytest.approx(77.2674, abs=1e-4)
        assert forced == pytest.approx(77.7838, abs=1e-4)
        assert forced > measured
        # and the gap is exactly the cap band the measurement would have saved
        cap_ratio = measure_cap_ratio(settings.BRAND_LOGO_PATH)["cap_ratio"]
        assert forced - measured == pytest.approx(
            box[3] * (1.0 - cap_ratio), abs=1e-6)

    def test_a_front_composed_under_the_fallback_is_still_clean_and_contained(
            self, monkeypatch):
        """Stricter must not mean broken: the extra reservation still fits the
        zone, so §AL4's "never weaker" is bought without spending AZ5(f)'s
        containment budget."""
        self._forced(monkeypatch)
        for hier, motif, label in _CLEARED:
            doc = _live_front(hierarchy=hier, motif=motif)
            assert _intruders(doc) == [], label
            assert _containment(doc) == [], label

    def test_the_box_is_None_when_the_mark_is_not_emitted_and_nothing_shifts(
            self):
        """The two conditions that suppress the logo node must suppress the
        keep-out with it, or the front drops for a mark that is not there."""
        import apps.ire.compose_container as ccx
        assert ccx._front_keepout_y(None, settings.BRAND_LOGO_PATH) is None
        backbone = build_backbone(ContainerProfile(archetype="bottle", ))
        assert ccx._logo_box(backbone, None, 1.0, 1.0,
                             lambda v: v, lambda v: v) is None


class TestUnmeasuredIsNotAPassAndIsNotAFailure:
    """``container_logo_metrics``' discipline, inherited deliberately: "An
    absent record leaves the axis UNMEASURED, which is the true state."""

    def test_a_background_nobody_named_is_UNMEASURED(self, emitted_front):
        """Silence is not consent. A validator that read "no background was
        supplied" as one of AU3's three permitted grounds would be inventing
        the answer most likely to be green."""
        rec = evaluate_brand_usage(emitted_front, background=None)
        assert rec["background_permitted"] is None
        assert rec["clean"] is False
        assert CODE_BACKGROUND_FORBIDDEN not in rec["codes"]

    def test_screen_without_a_resolution_is_UNMEASURED_not_FAILED(
            self, emitted_front):
        """THE DEFECT IN AU3 THAT WRITING THIS FOUND. The ruling states the
        screen floor in PIXELS and the Design Graph is millimetres, so the
        axis does not exist until a resolution is chosen. The first draft
        compared 17.28 mm against the number 60 and returned FAIL."""
        rec = evaluate_brand_usage(emitted_front,
                                   background=_ground_of(emitted_front),
                                   media="screen")
        assert rec["meets_minimum_size"] is None
        assert CODE_SCREEN_SIZE_UNMEASURED in rec["codes"]
        assert CODE_BELOW_MINIMUM_SIZE not in rec["codes"]

    def test_the_resolution_genuinely_changes_the_verdict(self, emitted_front):
        """Which is why guessing a default of 72 or 96 was refused: the same
        placement is BELOW the 60 px floor at 72 dpi and above it at 300."""
        low = evaluate_brand_usage(emitted_front,
                                   background=_ground_of(emitted_front),
                                   media="screen", dpi=72)
        high = evaluate_brand_usage(emitted_front,
                                    background=_ground_of(emitted_front),
                                    media="screen", dpi=300)
        assert low["meets_minimum_size"] is False
        assert CODE_BELOW_MINIMUM_SIZE in low["codes"]
        assert high["meets_minimum_size"] is True
        assert low["placements"][0]["reproduced_unit"] == "px"
        assert low["placements"][0]["reproduced_width"] < MINIMUM_WIDTH_PX_SCREEN
        assert high["placements"][0]["reproduced_width"] > MINIMUM_WIDTH_PX_SCREEN

    def test_a_mark_with_no_cap_band_leaves_clear_space_UNMEASURED(self):
        """§AW3's honest limit under §Y2(c): the contract emits no cap height
        and the clear-space check reports UNMEASURED rather than substituting
        the placed height. A substituted number would be a claim made from no
        measurement."""
        doc = Document(page_w=80.0, page_h=40.0, title="unmeasurable",
                       root=Group(name="Root", role="artwork", children=[
                           Image(name="logo", src=_APPROVED,
                                 x=10.0, y=10.0, w=30.0, h=8.0)]))
        rec = evaluate_brand_usage(doc, background="pure_white")
        placement = rec["placements"][0]
        assert placement["logo_cap_height_mm"] is None
        assert placement["meets_clear_space"] is None
        assert rec["meets_clear_space"] is None
        assert CODE_CAP_HEIGHT_UNMEASURED in rec["codes"]


class TestTheBackgroundRuleIsAPairingNotAList:
    """AU3: "permitted — the reversed lockup on brand dark, and ONLY the
    reversed lockup". That is a pairing rule; flattening it into a fourth
    permitted ground would licence the positive mark on dark."""

    def test_the_two_positive_grounds_pass(self, emitted_front):
        for ground in ("brand_light_ground", "pure_white"):
            rec = evaluate_brand_usage(emitted_front, background=ground)
            assert rec["background_permitted"] is True, ground

    def test_brand_dark_REQUIRES_the_reversed_lockup(self, emitted_front):
        positive = evaluate_brand_usage(emitted_front,
                                        background=BACKGROUND_REVERSED_ONLY)
        assert positive["background_permitted"] is False
        assert CODE_REVERSED_LOCKUP_REQUIRED in positive["codes"]

        reversed_ = evaluate_brand_usage(
            emitted_front, background=BACKGROUND_REVERSED_ONLY,
            reversed_lockup=True)
        assert reversed_["background_permitted"] is True
        assert CODE_REVERSED_LOCKUP_REQUIRED not in reversed_["codes"]

    def test_everything_else_is_forbidden(self, emitted_front):
        for ground in ("a photograph", "photographic", "tinted_field",
                       "brand_light", ""):
            rec = evaluate_brand_usage(emitted_front, background=ground)
            assert rec["background_permitted"] is False, ground
            assert CODE_BACKGROUND_FORBIDDEN in rec["codes"], ground

    @pytest.mark.parametrize("hierarchy,motif,label", _STATES)
    def test_the_clear_space_axis_does_not_depend_on_the_BACKGROUND_declaration(
            self, hierarchy, motif, label):
        """The property that lets BA-4 change every declaration in this file
        without touching a single clear-space number.

        ``_intruders`` takes ``ground`` as a defaulted argument, and the
        default has to be harmless. That is easy to assert in a comment and
        this asserts it instead, over the WHOLE declaration table — the two
        permitted grounds, the reversed-only one, both §BA spellings, and
        UNMEASURED — on all four composer states. If a future edit ever routed
        a background verdict into the clear-space list, every caller of
        ``_intruders`` in this file would start depending on an argument
        nobody passes, and this fires first and says so."""
        doc = _live_front(hierarchy=hierarchy, motif=motif)
        baseline = _intruders(doc, ground="pure_white")
        for ground in ("brand_light_ground", BACKGROUND_REVERSED_ONLY,
                       LIVE_FRONT_GROUND, BARE_FRONT_GROUND, None):
            assert _intruders(doc, ground=ground) == baseline, (label, ground)


class TestTheGroundUnderTheMarkIsMeasuredNotDeclared:
    """C13's table, as an assertion instead of prose in a manifest.

    THE ROW WAS FILED WITH THE WRONG COLOUR IN IT. It said the mark is printed
    over ``body`` at #EAD7D2 on all four states. That is true only of the two
    states that take the direct-print branch; on the other two — including the
    live call site — an opaque ``decoration-field`` rect at #F6EDEB is painted
    over ``body`` and is what the ink actually lands on. The row's own table
    listed the rect and still drew the wrong conclusion from it, because it
    recorded WHICH nodes are under the mark without recording WHICH ONE WINS.

    A manifest row cannot fail. This can, which is the point of moving the
    claim here: if a composer change ever alters the tone under the mark, the
    owner question C13 asks stops matching the artefact, and one of these
    fires rather than the row quietly going stale."""

    _EXPECTED = {
        "NOW — no hierarchy, no motif (the fixture's state)":
            ("decoration-field", "#F6EDEB"),
        "NOW — motif field, no hierarchy (the LIVE call site)":
            ("decoration-field", "#F6EDEB"),
        "FUTURE — hierarchy + motif, all three divider gates open":
            ("body", "#EAD7D2"),
        "FUTURE — hierarchy, motif absent":
            ("body", "#EAD7D2"),
    }

    @pytest.mark.parametrize("hierarchy,motif,label", _STATES)
    def test_the_ground_is_the_one_measured_and_never_white(
            self, hierarchy, motif, label):
        doc = _live_front(hierarchy=hierarchy, motif=motif)
        node = _ground_node(doc)
        color = node.fill.color
        hexed = "#%02X%02X%02X" % (round(color.r * 255), round(color.g * 255),
                                   round(color.b * 255))
        assert (str(node.name), hexed) == self._EXPECTED[label], label
        assert hexed != "#FFFFFF", label

    def test_the_motif_changes_the_SURROUNDINGS_and_not_the_GROUND(self):
        """§BA's exclusion and the ``background=`` declaration are two
        different senses of the word "ground", and conflating them is what put
        ``motif_field`` in this file as a declaration. ``motif-front``'s extent
        does enclose the mark — that is §BA's sense and it is correct. But no
        motif ink is UNDERNEATH the mark: adding the motif leaves the tone the
        mark reproduces on completely unchanged."""
        with_motif = _ground_node(_live_front(motif=True))
        without = _ground_node(_live_front(motif=False))
        assert str(with_motif.name) == str(without.name) == "decoration-field"
        assert with_motif.fill.color == without.fill.color

    def _stack(self, *extra, translucent=False):
        """A hand-built stack — the instrument's own logic, per this file's
        header rule about when a synthetic document is allowed."""
        children = [
            Rect(name="under", x=0.0, y=0.0, w=100.0, h=60.0,
                 fill=SolidFill(color=Color(r=0.5, g=0.5, b=0.5),
                                **({"opacity": 0.4} if translucent else {}))),
            Image(name="logo", src=settings.BRAND_LOGO_PATH,
                  x=40.0, y=25.0, w=20.0, h=4.171),
        ]
        return Document(page_w=100.0, page_h=60.0, title="stack",
                        root=Group(name="Root", role="artwork",
                                   children=[*children, *extra]))

    def test_a_node_painted_AFTER_the_mark_is_not_the_ground_under_it(self):
        """FOUND BY §AA, NOT BY READING. ``_ground_node`` stops at the mark,
        and on all four composer states nothing opaque is painted after it —
        so deleting the stop changed no assertion at all. A composer that ever
        lays an opaque panel OVER the mark would have been measured as
        reproducing on it."""
        over = Rect(name="over", x=0.0, y=0.0, w=100.0, h=60.0,
                    fill=SolidFill(color=Color(r=0.1, g=0.1, b=0.1)))
        assert str(_ground_node(self._stack(over)).name) == "under"

    def test_a_TRANSLUCENT_node_is_not_the_ground_under_the_mark(self):
        """Also §AA. Every fill on every composer state is opacity 1.0, so the
        opacity condition could be deleted with the suite still green. What it
        is for: a 40%-opaque panel does not determine the tone the mark
        reproduces on — what shows through it does — and declaring its colour
        as the ground would be a measurement of something invisible."""
        assert _ground_node(self._stack(translucent=True)) is None

    def test_the_direct_print_branch_is_what_moves_the_ground(self):
        """Named so the reason is greppable: the deciding condition is
        ``if direct_print and hierarchy:`` in ``_native_decoration``, not the
        motif. Keyed on ``motif``, the first version of ``_ground_of`` declared
        #EAD7D2 for a front reproducing on #F6EDEB and called it truthful."""
        assert _ground_of(_live_front(motif=False)) == LIVE_FRONT_GROUND
        assert _ground_of(_live_front(hierarchy=[_NAME_TIER],
                                      motif=False)) == BARE_FRONT_GROUND


def _hexcolor(hexed: str) -> Color:
    """A ``Color`` from a hex, round-tripping exactly through ``_hex_of``."""
    return Color(r=int(hexed[1:3], 16) / 255.0,
                 g=int(hexed[3:5], 16) / 255.0,
                 b=int(hexed[5:7], 16) / 255.0)


class TestTheMotifRuleIsToneQualifiedAndZeroTolerance:
    """§BB2 (C12, owner, 2026-08-25, committed f009a83 BEFORE this code).

    The ruling has TWO halves and they pull in opposite directions, which is
    why each gets its own watched document here:

      * ZERO strands at or above the threshold may cross the mark's ink box.
      * A strand BELOW the threshold is UNRESTRICTED and may cross freely.

    The second half is the one an instrument silently drops, because dropping
    it makes the check stricter and stricter reads as safer. §AU6(c) is about
    bars moved to make a measurement PASS; this is the mirror image, and it is
    just as much a misreport of what the owner ruled."""

    _GROUND = "#F6EDEB"          # a ruled tint — the live front's own ground

    def _doc(self, strand_fill=None, strand_stroke=None):
        strand = Rect(name="strand", x=0.0, y=0.0, w=45.0, h=60.0,
                      fill=(None if strand_fill is None
                            else SolidFill(color=_hexcolor(strand_fill))),
                      stroke=(None if strand_stroke is None
                              else Stroke(color=_hexcolor(strand_stroke),
                                          width_mm=0.312, opacity=0.9)))
        return Document(page_w=100.0, page_h=60.0, title="motif",
                        root=Group(name="Root", role="artwork", children=[
                            Group(name="motif", role="decoration", children=[
                                Rect(name="plate", x=0.0, y=0.0,
                                     w=100.0, h=60.0,
                                     fill=SolidFill(
                                         color=_hexcolor(self._GROUND))),
                                strand]),
                            Image(name="logo", src=settings.BRAND_LOGO_PATH,
                                  x=40.0, y=25.0, w=20.0, h=4.171)]))

    def test_a_strand_BELOW_the_threshold_is_UNRESTRICTED(self):
        """THE HALF MOST LIKELY TO BE DROPPED. #F3EDEB against #F6EDEB
        measures 1.1022, below the ruled 2.3, so it is reported for the record
        and is NOT a violation. If this ever goes red, the tone-qualification
        has been quietly discarded and the rule has become "no strand may
        cross", which is not what was ruled."""
        rec = evaluate_brand_usage(self._doc(strand_fill="#F3EDEB"),
                                   background="brand_light_ground")
        (finding,) = [f for f in rec["motif_findings"]
                      if f["node_name"] == "strand"]
        assert finding["delta_e"] == 1.1022
        assert finding["delta_e"] < MOTIF_CONTRAST_DELTA_E
        assert finding["contrast_measured"] is True
        assert finding["counts"] is False        # reported, NOT a violation
        assert rec["motif_strands_over_mark"] == 0
        assert rec["meets_motif_density"] is True
        assert CODE_MOTIF_OVER_MARK not in rec["codes"]
        assert rec["clean"] is True

    def test_a_strand_AT_OR_ABOVE_the_threshold_is_a_violation(self):
        """And ZERO are permitted, so ONE is enough. #F7EFE4 measures 4.6305,
        which is the live front's own number."""
        rec = evaluate_brand_usage(self._doc(strand_fill="#F7EFE4"),
                                   background="brand_light_ground")
        (finding,) = [f for f in rec["motif_findings"]
                      if f["node_name"] == "strand"]
        assert finding["delta_e"] == 4.6305
        assert finding["counts"] is True
        assert MOTIF_STRANDS_PERMITTED_OVER_MARK == 0
        assert rec["motif_strands_over_mark"] == 1
        assert rec["meets_motif_density"] is False
        assert CODE_MOTIF_OVER_MARK in rec["codes"]
        assert rec["clean"] is False

    def test_a_STROKED_strand_is_UNMEASURED_and_records_WHY(self):
        """§BB2(d) sends strokes back to the owner, so the executor may not
        adjudicate them — but the record must not imply the instrument is
        BLIND to them, because it is not. Measured on the live front, all
        eleven ``flow-line-*`` strands carry a 0.312 mm stroke in #F7EFE4:
        the same ink as the ribbons, at the same 4.6305. What is unruled is
        whether a hairline stroke is a strand for a density rule, not what
        colour it is."""
        rec = evaluate_brand_usage(self._doc(strand_stroke="#F7EFE4"),
                                   background="brand_light_ground")
        (finding,) = [f for f in rec["motif_findings"]
                      if f["node_name"] == "strand"]
        assert finding["strand_hex"] is None
        assert finding["delta_e"] is None
        assert finding["contrast_measured"] is False
        assert finding["counts"] is None                 # UNMEASURED
        assert "stroke" in finding["unmeasured_reason"]
        assert "BB2(d)" in finding["unmeasured_reason"]
        # fails closed: unmeasured is not a pass
        assert rec["meets_motif_density"] is None
        assert CODE_MOTIF_UNMEASURED in rec["codes"]
        assert rec["clean"] is False

    def test_a_MEASURED_violation_outranks_an_unmeasured_one(self):
        """Both at once. Folding the verdict to None because something else
        could not be read would report a front that DEFINITELY fails as one
        nobody could judge — the A137 shape, in the direction that flatters."""
        doc = self._doc(strand_fill="#F7EFE4")
        doc.root.children[0].children.append(
            Rect(name="hairline", x=0.0, y=0.0, w=45.0, h=60.0,
                 stroke=Stroke(color=_hexcolor("#F7EFE4"), width_mm=0.312,
                               opacity=0.9)))
        rec = evaluate_brand_usage(doc, background="brand_light_ground")
        assert rec["motif_strands_over_mark"] == 1
        assert rec["motif_strands_unmeasured"] == 1
        assert rec["meets_motif_density"] is False       # not None
        assert CODE_MOTIF_OVER_MARK in rec["codes"]
        assert CODE_MOTIF_UNMEASURED in rec["codes"]

    def test_the_barred_constant_is_not_the_one_used(self):
        """§BB2(e), and WATCH backlog H002. This is the test the production
        docstring names as the only thing standing between two numbers eight
        lines apart in ``image_checks``.

        ``PALETTE_TOLERANCE_DE`` is 25.0 and exists for image-vs-brand-hex
        sampling — a different question. Wired here it would not merely be
        wrong, it would make the entire tone-qualified rule A CHECK THAT
        CANNOT FIRE: the live front's strands measure 4.6305, so at 25.0 every
        strand on the shipping artwork falls below the line and zero ever
        count. That is the defect 44e222d fixed on the morning of the day this
        was ruled, asserted here instead of described."""
        from apps.pipeline.services.image_checks import PALETTE_TOLERANCE_DE
        assert PALETTE_TOLERANCE_DE == 25.0
        assert MOTIF_CONTRAST_DELTA_E == 2.3
        assert MOTIF_CONTRAST_DELTA_E != PALETTE_TOLERANCE_DE

        # the margin is not academic: measured on the live front's own ink
        live = _delta_e_hex("#F7EFE4", "#F6EDEB")
        assert round(live, 4) == 4.6305
        assert live >= MOTIF_CONTRAST_DELTA_E     # fires on the ruled number
        assert live < PALETTE_TOLERANCE_DE        # silent on the barred one

    def test_the_live_front_FAILS_this_rule_on_three_measured_strands(self):
        """§BB2(f): the violation must be visible AS A FAILURE. Three ribbons
        at 4.6305 cross the mark's ink box against a permitted count of zero.

        The eleven stroked flow-lines are reported separately and the red does
        NOT depend on them — which is the position worth having, because it
        cannot be argued away whichever way the owner rules on strokes."""
        rec = evaluate_brand_usage(_live_front(),
                                   background="brand_light_ground")
        counted = [f for f in rec["motif_findings"] if f["counts"] is True]
        assert [f["node_name"] for f in counted] == ["ribbon-0", "ribbon-1",
                                                     "ribbon-2"]
        assert {f["delta_e"] for f in counted} == {4.6305}
        assert rec["motif_strands_over_mark"] == 3
        assert rec["motif_strands_unmeasured"] == 11
        assert rec["meets_motif_density"] is False
        assert rec["clean"] is False
        # the red stands on the ruled three ALONE
        assert len(counted) > MOTIF_STRANDS_PERMITTED_OVER_MARK


class TestProductionComputesTheGroundTheHelperOnlyMeasured:
    """§BB1(e)(1). ``_ground_node``'s docstring said, in capitals, *"NOTHING
    IN PRODUCTION COMPUTES THIS."* Something does now, and these pin that the
    two agree — which is what makes the five
    ``TestTheGroundUnderTheMarkIsMeasuredNotDeclared`` tests binding on
    production rather than on a test helper only."""

    @pytest.mark.parametrize("hierarchy,motif,label", _STATES)
    def test_production_measures_what_the_helper_measures(
            self, hierarchy, motif, label):
        doc = _live_front(hierarchy=hierarchy, motif=motif)
        helper = _ground_node(doc)
        # [the owner's second answer of 2026-09-25: production (evaluate_brand_usage) reads the mark through
        # brand_mark.logo_nodes and no longer calls logo_image_nodes; on this raster front the two are the same node
        # list — held here, so neither can drift — and the measurement is taken on the node production reads]
        assert _mark_nodes(doc) == logo_image_nodes(doc), label
        production = measure_ground(doc, _mark_nodes(doc)[0])
        assert production is not None, label
        assert production["node_name"] == str(helper.name), label
        assert production["resolved"] == "brand_light_ground", label
        assert production["hex"] in GROUND_HEX_RULED, label

    def test_an_unrecognised_tint_is_never_resolved_to_the_NEAREST_ruled_one(
            self):
        """BB1(d) in one assertion. #E6E6E6 measures 4.5698 from #F6EDEB —
        closer to a ruled tint than many things, and nearer than the 25.0 the
        barred constant would have allowed. It resolves to NOTHING. There is
        no tolerance, no lightness threshold, and no "sufficiently pale tints
        count": the map is a lookup and a miss goes back to the owner."""
        assert _delta_e_hex("#E6E6E6", "#F6EDEB") < 25.0
        assert "#E6E6E6" not in GROUND_HEX_RULED
        doc = Document(page_w=100.0, page_h=60.0, title="grey",
                       root=Group(name="Root", role="artwork", children=[
                           Rect(name="plate", x=0.0, y=0.0, w=100.0, h=60.0,
                                fill=SolidFill(color=_hexcolor("#E6E6E6"))),
                           Image(name="logo", src=settings.BRAND_LOGO_PATH,
                                 x=40.0, y=25.0, w=20.0, h=4.171)]))
        rec = evaluate_brand_usage(doc, background="brand_light_ground")
        assert rec["ground_hex"] == "#E6E6E6"
        assert rec["ground_resolved"] is None
        assert rec["ground_permitted"] is False
        assert CODE_GROUND_UNRECOGNISED in rec["codes"]
        assert rec["clean"] is False

    def test_nothing_opaque_under_the_mark_is_UNMEASURED_not_a_pass(self):
        """Distinct from UNRECOGNISED: one is a colour nobody ruled, the other
        is no colour to rule. A translucent panel does not determine the tone
        the mark reproduces on, so it is not the ground — and there being no
        ground at all is blocking, never a silent green."""
        doc = Document(page_w=100.0, page_h=60.0, title="sheer",
                       root=Group(name="Root", role="artwork", children=[
                           Rect(name="sheer", x=0.0, y=0.0, w=100.0, h=60.0,
                                fill=SolidFill(color=_hexcolor("#F6EDEB"),
                                               opacity=0.4)),
                           Image(name="logo", src=settings.BRAND_LOGO_PATH,
                                 x=40.0, y=25.0, w=20.0, h=4.171)]))
        assert _mark_nodes(doc) == logo_image_nodes(doc)      # [2026-09-25: the node production reads — see above]
        assert measure_ground(doc, _mark_nodes(doc)[0]) is None
        rec = evaluate_brand_usage(doc, background="brand_light_ground")
        assert rec["ground_permitted"] is None           # UNMEASURED
        assert rec["ground_node"] is None
        assert CODE_GROUND_UNMEASURED in rec["codes"]
        assert rec["clean"] is False

    def test_the_caller_cannot_argue_with_the_measured_axis(self):
        """The two-axis property, stated as a behaviour. Every declaration a
        caller can make leaves the measured ground identical — including the
        one that used to buy a clean bill of health."""
        doc = _live_front(motif=False)
        seen = []
        for declared in ("pure_white", "brand_light_ground", "brand_dark",
                         "a photograph", None):
            rec = evaluate_brand_usage(doc, background=declared)
            seen.append((rec["ground_node"], rec["ground_hex"],
                         rec["ground_resolved"], rec["ground_permitted"]))
        assert len(set(seen)) == 1
        assert seen[0] == ("decoration-field", "#F6EDEB",
                           "brand_light_ground", True)


class TestAGroundIsNotANeighbour:
    """The exclusion that keeps the clear-space check from reporting the
    surface the mark is PLACED ON as an intrusion into its own clear space."""

    def _doc(self, ground_box):
        gx, gy, gw, gh = ground_box
        return Document(page_w=100.0, page_h=60.0, title="ground",
                        root=Group(name="Root", role="artwork", children=[
                            Rect(name="decoration-field", x=gx, y=gy,
                                 w=gw, h=gh,
                                 fill=SolidFill(color=Color(r=0.9, g=0.9,
                                                            b=0.9))),
                            Image(name="logo",
                                  src=settings.BRAND_LOGO_PATH,
                                  x=40.0, y=25.0, w=20.0, h=4.171)]))

    def test_a_field_containing_the_logo_is_not_an_intrusion(self):
        """RE-SCOPED BY §BB1 FROM ``codes == []`` TO THE CLEAR-SPACE AXIS.
        Until the ground was computed this read:

            assert rec["codes"] == []
            assert rec["clean"] is True

        Both were PROXIES for "the exclusion fired and nothing was reported",
        and they stopped being safe proxies the moment a second axis could
        report something. This fixture's field is ``Color(0.9, 0.9, 0.9)`` —
        #E6E6E6, an arbitrary grey — and it CONTAINS the mark, so it is now
        measured as the ground and is correctly refused: the owner named two
        tints at §BB1 and this is not one of them.

        THE COLOUR WAS DELIBERATELY NOT CHANGED, and the prediction written
        before this code said it would be. That prediction (G4) argued a ruled
        brand tint would make the fixture "MORE like the product". It would,
        and it would also have thrown away the only document in this suite
        where **BB1(d) can be watched firing on an unrecognised tint**. §AA is
        explicit that a guard nobody has seen fire is not evidence, so the
        grey stays and earns its keep as the negative case.

        It also avoids touching ``_doc``, which is SHARED with
        ``test_a_field_that_only_OVERLAPS_the_logo_still_is_one`` — the test
        §BA2 names as its tripwire and forbids editing, relaxing or
        parametrising. Adding a colour parameter for this test's benefit would
        have edited that helper. Nothing here does."""
        rec = evaluate_brand_usage(self._doc((0.0, 0.0, 100.0, 60.0)),
                                   background="brand_light_ground")
        # THE SUBJECT OF THIS TEST, unchanged and still the whole point:
        # a field that CONTAINS the mark is its ground, not an intrusion.
        assert rec["meets_clear_space"] is True
        assert CODE_CLEAR_SPACE_VIOLATED not in rec["codes"]
        assert rec["placements"][0]["clear_space_findings"] == []

        # and the one code that IS reported belongs to the other axis
        assert rec["codes"] == [CODE_GROUND_UNRECOGNISED]
        assert rec["ground_node"] == "decoration-field"
        assert rec["ground_hex"] == "#E6E6E6"
        assert rec["ground_resolved"] is None
        assert rec["ground_permitted"] is False
        # BB1(d): fail-closed, and NOT resolved to whichever ruled tint it is
        # nearest. #E6E6E6 is a pale grey; nothing here lets it become one.
        assert rec["clean"] is False

    def test_a_field_that_only_OVERLAPS_the_logo_still_is_one(self):
        """The exclusion is a rule about CONTAINMENT, not a list of node
        names, so a field that merely crowds the mark is still reported.

        §BA2 NAMES THIS TEST AS THE TRIPWIRE AND FORBIDS TOUCHING IT: *"It may
        not be edited, relaxed or parametrised to fit this ruling."* Its
        ``decoration-field`` is a direct child of ``Root``, which is exactly
        why it goes green under the naive widening BA2(c) proves degenerate.
        It was not edited. It passed unchanged, first run, and this docstring
        is the only thing about it that moved."""
        rec = evaluate_brand_usage(self._doc((0.0, 0.0, 45.0, 60.0)),
                                   background="brand_light_ground")
        assert rec["meets_clear_space"] is False
        assert CODE_CLEAR_SPACE_VIOLATED in rec["codes"]


class TestTheGroundExclusionIsNotUniversal:
    """§BA2's three bars, composed and WATCHED rather than reasoned about (§AA).

    §BA's whole risk is that widening the ground exclusion silences everything
    instead of eighteen things, and that the difference is invisible from the
    finding list — which is empty either way. Every test here is a document in
    which the exclusion MUST NOT fire, plus the one control in which it must.

    Each pair differs by ONE property, so a failure names the condition that
    broke rather than "something changed".
    """

    def _doc(self, *nodes):
        return Document(page_w=100.0, page_h=60.0, title="ground",
                        root=Group(name="Root", role="artwork", children=[
                            *nodes,
                            Image(name="logo", src=settings.BRAND_LOGO_PATH,
                                  x=40.0, y=25.0, w=20.0, h=4.171)]))

    @staticmethod
    def _plate():
        """Covers the page, so any group holding it has a box that CONTAINS
        the mark — condition (2) satisfied without relying on a text run's
        page-spanning ink box."""
        return Rect(name="plate", x=0.0, y=0.0, w=100.0, h=60.0,
                    fill=SolidFill(color=Color(r=0.9, g=0.9, b=0.9)))

    @staticmethod
    def _strand():
        """Crowds the mark from the left and does NOT contain it, so it is a
        finding unless something excludes it. The subject of every assertion
        below."""
        return Rect(name="strand", x=0.0, y=0.0, w=45.0, h=60.0,
                    fill=SolidFill(color=Color(r=0.5, g=0.5, b=0.5)))

    @staticmethod
    def _caption(name="caption", y=40.0):
        """The mark's margin runs 21.4268..32.7442, so the default baseline of
        40.0 puts this text CLEAR of it — deliberately. Where it is used to
        disqualify a group, the group must be disqualified by the text
        existing, not by the text also being a finding, or the test would be
        measuring two things at once. ``y=34.0`` is the intruding form (ink top
        31.7331, inside the margin by 1.0111)."""
        return TextRun(name=name, text="INGREDIENTS", x=50.0, y=y,
                       size_pt=9.0, align="center",
                       color=Color(r=0.1, g=0.1, b=0.1))

    def _names(self, doc):
        rec = evaluate_brand_usage(doc, background="brand_light_ground")
        return sorted(f["node_name"]
                      for f in rec["placements"][0]["clear_space_findings"])

    # ------------------------------------------------ the control: it fires
    def test_a_declared_ground_silences_the_ink_that_is_PART_OF_it(self):
        """§BA's ruling, in one document. Without this the other tests here
        would all pass on an exclusion that never fires at all."""
        doc = self._doc(Group(name="motif", role="decoration",
                              children=[self._plate(), self._strand()]))
        assert self._names(doc) == []

    # ------------------------------------------ BA2(c): the degeneracy proof
    def test_containment_ALONE_does_not_silence_anything(self):
        """BA2(c). ``Root``'s box contains the mark unconditionally, because a
        group's box is the union of its descendants' and a union contains
        every member. If containment alone were the rule, this document — and
        every document — would report nothing, forever.

        The group here is ``role="panel"``: same shape, same geometry, same
        containment as the control above. Only the declaration differs."""
        doc = self._doc(Group(name="panel", role="panel",
                              children=[self._plate(), self._strand()]))
        assert self._names(doc) == ["strand"]

    def test_the_marks_own_ancestors_are_not_grounds(self):
        """The same proof one level up: ``Root`` itself contains the mark, so
        an encoding that inherited from ANY containing ancestor would silence
        the strand even with no group around it at all."""
        doc = self._doc(self._plate(), self._strand())
        assert self._names(doc) == ["strand"]

    def test_a_DECLARED_group_that_does_not_CONTAIN_the_mark_is_not_a_ground(
            self):
        """BA2(a)'s SECOND condition, which nothing in this file could falsify
        until a mutant said so.

        FOUND BY §AA, NOT BY READING. The witness set as first written passed
        with the containment test deleted from ``_is_ground`` — a mutant
        returning ``box is not None`` and ignoring ``logo_box`` entirely scored
        53/53. Every document here either failed the DECLARED bar or contained
        the mark anyway, so "declared" was doing all the work and the owner's
        second condition was decorative. It is load-bearing again below.

        The group is declared, inks no text, and its box ``(0, 0, 45, 60)``
        stops 15 mm short of the mark's right edge at 60. A field the mark is
        not ON is not the field the mark is printed on, however it is labelled
        — which is the difference between a ground and a big neighbour."""
        doc = self._doc(Group(name="sidebar", role="decoration",
                              children=[self._strand()]))
        assert self._names(doc) == ["strand"]

    # ---------------------------------- DEPTH: both bars read the whole tree
    #
    # ALSO FOUND BY §AA. A mutant that stopped ``_leaves`` at DIRECT children
    # scored 54/54: every group in this file, and the live front's own
    # ``motif-front``, holds its ink one level down, so recursion was never
    # exercised. The two tests below are the two directions that mutant broke
    # — one silences too much, one too little — and they are separate because
    # a single test could pass by getting one of them right.

    def test_a_grounds_text_is_found_at_ANY_depth(self):
        """Condition (3) must see a text run wherever it is nested, or the
        cheapest way to defeat it is to put the type in a sub-group.

        The dangerous direction: a flat reading finds no text on ``motif``,
        promotes it to a ground, and silences the strand — the over-silencing
        §BA's whole risk is about, reached by nesting rather than by role."""
        doc = self._doc(Group(name="motif", role="decoration", children=[
            self._plate(), self._strand(),
            Group(name="legal", role="decoration",
                  children=[self._caption()])]))
        assert self._names(doc) == ["strand"]

    def test_a_grounds_BOX_is_the_union_at_ANY_depth(self):
        """And condition (2) must see the ink at depth too — the same bug in
        the safe direction. Here the plate that makes ``motif`` contain the
        mark is one level down; a flat reading sees only the strand, computes
        a box 15 mm short of the mark, and reports ink that is genuinely part
        of the ground. Louder is not the same as right."""
        doc = self._doc(Group(name="motif", role="decoration", children=[
            Group(name="inner", role="artwork", children=[self._plate()]),
            self._strand()]))
        assert self._names(doc) == []

    # ------------- the third condition, and the measurement that forced it
    def test_a_declared_group_that_INKS_TEXT_is_a_container_not_a_ground(self):
        """THE EXECUTOR'S THIRD CONDITION, AND THE ONLY PART OF THIS ENCODING
        §BA DOES NOT SPECIFY. It is here because BA2(a)'s two conditions were
        MEASURED INSUFFICIENT on the live front, not because a third felt
        safer.

        ``role="decoration"`` is carried by 22 production sites and most are
        layout containers: ``compose_container`` stamps it on ``Decoration``,
        on ``FRONT_DIRECT_PRINT``, on every ``Surface-*`` panel and on
        ``Surfaces``, one level under ``Root``. With two conditions only, the
        live front loses **21 of 36 leaves including ``product-name-0``** —
        §AY2's keep-out, unmeasurable, which is the precise outcome BA2(b)
        forbids. BA2(b) names coordinates as the route; membership is a second
        route to the same place.

        The condition follows BA1's own words rather than patching them: a
        GROUND is a rendered field, text is what a ground is printed BEHIND,
        so a group that inks text is a container holding a neighbour. It can
        only ever make the instrument report MORE.

        This document is the control above plus one text run. Nothing else."""
        doc = self._doc(Group(name="Decoration", role="decoration",
                              children=[self._plate(), self._strand(),
                                        self._caption()]))
        assert self._names(doc) == ["strand"]

    def test_a_ground_that_GAINS_text_stops_being_one_loudly(self):
        """The coupling named in ``_is_ground``'s docstring, pinned so it is
        discovered by a test rather than by a silent change in a report: if
        the motif engine ever emits a glyph, the field stops being a ground
        and every strand returns at once.

        That is the safe direction — louder, not quieter — and it is asserted
        here so that "safe direction" is a measurement and not a hope."""
        ground = Group(name="motif", role="decoration",
                       children=[self._plate(), self._strand()])
        assert self._names(self._doc(ground)) == []
        ground.children.append(self._caption("motif-glyph"))
        assert self._names(self._doc(ground)) == ["strand"]

    # --------------------------- BA2(b): membership, never coordinates
    def test_sharing_a_grounds_BOX_does_not_make_a_node_part_of_it(self):
        """BA2(b), the clause §BA said would bite. The strand sits INSIDE the
        ground's box — identical coordinates to the control, where it is
        silenced — but hangs off ``Root`` instead of off the ground. A rule
        that propagated by geometry cannot tell these two documents apart."""
        doc = self._doc(Group(name="motif", role="decoration",
                              children=[self._plate()]),
                        self._strand())
        assert self._names(doc) == ["strand"]

    def test_a_text_run_over_a_ground_is_still_a_neighbour(self):
        """BA2(b) stated on the node type that matters, because this is the
        one §AY2's 1.5124 mm collision depends on. Text drawn on top of a
        motif field is crowding the mark, not supporting it."""
        doc = self._doc(Group(name="motif", role="decoration",
                              children=[self._plate()]),
                        self._caption("product-name-0", y=34.0))
        assert self._names(doc) == ["product-name-0"]

    def test_an_empty_declared_group_is_not_a_ground_and_does_not_crash(self):
        """A group that inks nothing has no box. ``None`` is not a container
        of anything, and the arithmetic that would ask must not be reached."""
        doc = self._doc(Group(name="empty", role="decoration", children=[]),
                        self._strand())
        assert self._names(doc) == ["strand"]


class TestTextIsMeasuredFromItsBaselineNotItsY:
    """``TextRun.y`` is the BASELINE — ``pdf_ai._draw_text`` calls
    ``drawCentredString(x, y, …)``. A validator reading ``y`` as the top edge
    under-reports every intrusion from below by a whole cap height."""

    def test_ink_is_reported_above_the_baseline(self):
        """A run whose BASELINE sits just clear of the margin still intrudes,
        because its ink starts a cap height higher. If this passes, the
        module is reading ``y`` as a top edge and the gate is blind."""
        logo_bottom = 20.0 + 4.171
        run_y = logo_bottom + 3.0            # baseline is inside the margin
        doc = Document(page_w=100.0, page_h=60.0, title="baseline",
                       root=Group(name="Root", role="artwork", children=[
                           Image(name="logo", src=settings.BRAND_LOGO_PATH,
                                 x=40.0, y=20.0, w=20.0, h=4.171),
                           TextRun(name="product-name-0", text="Liquid Veil",
                                   x=50.0, y=run_y, size_pt=9.0,
                                   align="center",
                                   color=Color(r=0.1, g=0.1, b=0.1))]))
        rec = evaluate_brand_usage(doc, background="pure_white")
        finding = rec["placements"][0]["clear_space_findings"]
        assert finding, "the run's ink was not seen above its baseline"
        assert finding[0]["gaps_mm"]["below"] < 3.0

    def test_an_empty_run_inks_nothing(self):
        doc = Document(page_w=100.0, page_h=60.0, title="empty",
                       root=Group(name="Root", role="artwork", children=[
                           Image(name="logo", src=settings.BRAND_LOGO_PATH,
                                 x=40.0, y=20.0, w=20.0, h=4.171),
                           TextRun(name="blank", text="   ", x=50.0, y=25.5,
                                   size_pt=9.0, align="center",
                                   color=Color(r=0.1, g=0.1, b=0.1))]))
        rec = evaluate_brand_usage(doc, background="pure_white")
        assert rec["meets_clear_space"] is True


class TestTheMarkFromItsApprovedMasterIsJudgedByTheSameBars:
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." A mark drawn from its approved vector master — a SYNTHETIC fixture
    here (apps/ire/tests/brand_mark_fixtures.py) — is judged by §AU3's bars exactly as the raster is: its box, its OWN
    cap band (the master rasterised, measured by ``measure_cap_ratio``), and the neighbours in its clear space. Its
    own outlines are drawn only at emit, so they can never stand in its own clear space."""

    def _master(self):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        return B.read_master(FX.REG_STYLE, path="/fixture/bbrose-logo.svg")

    def test_the_live_front_is_judged_with_the_masters_own_band_and_nothing_is_unmeasured(self):
        from apps.ire import brand_mark as B
        master = self._master()
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", )), logo_path=settings.BRAND_LOGO_PATH,
            product_name="PLACEHOLDER-BRAND", sku="PB-01", native=True, zones=_ZONES,
            hierarchy_lines=[_NAME_TIER], motif_spec=_motif_spec(), logo_master=master)
        rec = evaluate_brand_usage(doc)
        band = B.cap_band(master)
        assert band is not None and band["cap_ratio"] != 0.856667             # the master's, not logo.png's
        placement = rec["placements"][0]
        assert (placement["src"], placement["cap_ratio"], placement["clear_space_measured"]) == (
            master.path, band["cap_ratio"], True)
        assert CODE_CAP_HEIGHT_UNMEASURED not in rec["codes"]
        assert [a["path"] for a in rec["assets"]] == [master.path]

    def test_a_neighbour_in_the_marks_clear_space_is_found_and_its_own_outlines_never_are(self):
        from apps.ire import brand_mark as B
        master = self._master()
        mark = B.mark_node("logo", master, 20.0, 20.0, 40.0, 40.0 * master.aspect)
        cap = 40.0 * master.aspect * B.cap_band(master)["cap_ratio"]
        near = Rect(name="rule-in-the-clear-space", x=20.0, y=20.0 + mark.h + cap / 2.0, w=40.0, h=0.3,
                    fill=SolidFill(color=Color.from_hex("#8B2E3C")))
        doc = Document(page_w=100, page_h=100, root=Group(name="Root", children=[mark, near]))
        rec = evaluate_brand_usage(doc)
        found = [f["node_name"] for f in rec["placements"][0]["clear_space_findings"]]
        assert found == ["rule-in-the-clear-space"] and CODE_CLEAR_SPACE_VIOLATED in rec["codes"]
        alone = evaluate_brand_usage(Document(page_w=100, page_h=100, root=Group(name="Root", children=[mark])))
        assert alone["placements"][0]["clear_space_findings"] == []
