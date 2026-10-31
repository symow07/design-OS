"""§AU3 / §AW3 — brand usage, judged (``container_brand_usage/1.0``).

WHAT THIS IS FOR, IN THE NODE'S OWN WORDS.
``brand_gov.minimum_component_library`` has sat at IMPLEMENTED 70/70 with a
``next_action`` naming two gaps, and this module closes the second one
verbatim: *"the library carries no USAGE rules (clear space, minimum size,
permitted backgrounds), which a brand component library normally holds and
which no committed owner record states today."* One does now — §AU3, committed
2026-08-21 — so the rules can stop being prose.

AU3's distinction, which the record should not blur: *"C2 was never the reason
the logo was unmeasured; it was the reason it was UNJUDGED."*
``container_logo_metrics/1.0`` already measures the emitted logo. This module
does not measure it again. It JUDGES it, against three ruled bars.

THIS GATE IS EXPECTED TO FAIL ON TODAY'S ARTWORK, and §AW2(e) already measured
that it does — the front's own copy sits 1.51 mm inside the logo's clear space.
§AU put it plainly: *"It is meant to be tight enough that the emitted logo
might fail it. If it does, that failure is the tranche's best output."* A
module written to pass the artwork that exists would be the bar moving to meet
the work, which §AU6(c) forbids in as many words: **never move a bar to make a
measurement pass**.

CAP HEIGHT IS MEASURED PER ASSET AND NEVER ASSUMED (§AW3). ``0.856667`` is
``media/brand/logo.png``'s number, not this module's. A mark with no flat
capitals has no cap band, and then the contract emits NO cap height and the
clear-space axis reports UNMEASURED — it does not substitute the placed height.
An UNMEASURED axis is blocking, which is the true state; a substituted number
would be a claim made from no measurement, which is the exact defect
``container_logo_metrics`` was written to avoid.

AND THE SPELLING IS DELIBERATE (§AW3 / §AK3). ``ContainerProfile.cap_height_mm``
already means the height of the bottle's CLOSURE. This contract never uses the
bare term: it emits ``logo_cap_height_mm``, so a reader cannot bind to the
wrong one of two ideas wearing one spelling.

Pure: no Django, no ORM, no network — WITH ONE NAMED EXCEPTION, DECLARED HERE
RATHER THAN DISCOVERED BY A READER. ``_delta_e_hex`` imports three colour
helpers from ``apps.pipeline.services.image_checks`` LAZILY, inside the
function. That module resolves Django settings at module scope, so a top-level
import would make this header false. The alternative — copying twenty lines of
sRGB-to-Lab arithmetic into this file — would give the repository TWO answers
to one question, which is worse than a lazy import. So the import is lazy, and
this paragraph is why the word "Pure" above now carries a qualifier.
"""
from __future__ import annotations

import os
from collections import Counter

SCHEMA = "container_brand_usage/1.0"

MM_TO_PT = 72.0 / 25.4
PT_TO_MM = 25.4 / 72.0

# ---------------------------------------------------------------- §AU3 bars
#: 1.0 x the logo's OWN cap height, on all four sides.
CLEAR_SPACE_CAP_HEIGHTS = 1.0
#: 12.0 mm reproduced WIDTH in print. "Reproduced width" is the x-extent, the
#: same axis ``container_logo_metrics.rendered_extent_pt`` already means.
MINIMUM_WIDTH_MM_PRINT = 12.0
#: 60 px reproduced width on screen.
MINIMUM_WIDTH_PX_SCREEN = 60.0

#: Grounds the mark may sit on in its POSITIVE form.
BACKGROUNDS_PERMITTED = ("brand_light_ground", "pure_white")
#: A ground permitted ONLY to the reversed lockup — AU3 says "and ONLY the
#: reversed lockup", so this is a pairing rule, not a fourth permitted ground.
BACKGROUND_REVERSED_ONLY = "brand_dark"

#: The grounds the owner has NAMED, by the hex the composer produces — §BB1
#: (C13, owner, 2026-08-25, committed 68eb962 BEFORE this code per §AE0(b)).
#:
#: TWO HEXES, NOT A CATEGORY OF PALE COLOURS. BB1(d) refuses "a tolerance, a
#: lightness threshold, or a rule of the form 'sufficiently pale tints count'",
#: so this is a LOOKUP and never a distance. A third colour under the mark is
#: C13's condition recurring: it comes back to the owner, which on this path
#: means CODE_GROUND_UNRECOGNISED and a False verdict, never a resemblance
#: match to whichever of these two it is nearest.
#:
#: NO BAR MOVED HERE AND BB1(a) IS THE SENTENCE TO CHECK THAT AGAINST.
#: ``BACKGROUNDS_PERMITTED`` is not edited and already contained
#: ``brand_light_ground``. What the owner supplied is the missing RECOGNITION
#: step — that these two specific tints are instances of a category the table
#: already permitted. The category list stays the owner's; this map is a
#: statement about what the composer produces.
GROUND_HEX_RULED = {
    "#F6EDEB": "brand_light_ground",   # _tint(body, 0.55) — decoration-field
    "#EAD7D2": "brand_light_ground",   # _DEFAULT_BODY — the container body
}

#: §BB2 (C12, owner, 2026-08-25, committed f009a83). A motif field IS a
#: permitted ground for the mark, on a condition carrying two numbers.
#:
#: CIE76 delta-E of a strand's fill against the field it sits on. A strand
#: BELOW this is not perceptibly there and is UNRESTRICTED — it may cross the
#: mark freely. That is what "tone-qualified" buys and it is the half of the
#: ruling an instrument is most likely to drop on the floor, because dropping
#: it makes the check stricter and stricter reads as safer.
#:
#: IT IS A LITERATURE CONSTANT, NOT A MEASUREMENT, and BB2(g) says so in those
#: words: the CIE76 just-noticeable difference commonly attributed to Mahy,
#: Van Eycken & Oosterlinck (1994). It was asserted from knowledge and was NOT
#: verified against the primary source; nothing in this repository measured it.
MOTIF_CONTRAST_DELTA_E = 2.3

#: ZERO. Not "few", not "a small share of the mark's box". One strand at or
#: above the threshold is enough to fail.
MOTIF_STRANDS_PERMITTED_OVER_MARK = 0

#: The ``Group.role`` a composer stamps to DECLARE a group a decoration ground
#: (§BA2(a), owner, 2026-08-22). The declaration is read off the role because
#: BA2(a) requires it to be carried AT COMPOSITION — a name matched here at
#: validation time would be "a list of node names in a hat", which is the
#: thing ``_clear_space_findings``' own docstring has always refused.
#: CORRECTED 2026-08-22 BY THE §AE6(a) AUDIT. This read "``compose_container.
#: py:186`` is THE SITE that sets it". The definite article was false and the
#: same file contradicts it 260 lines below, where ``_is_ground``'s docstring
#: names four more. ``role="decoration"`` is stamped at SEVEN sites in
#: compose_container.py alone — 186, 331, 379, 456, 559, 589, 590 — and 186 is
#: merely the first. Which matters: a reader who patched 186 believing it was
#: the only one would leave six grounds undeclared and would not find out from
#: this comment.
GROUND_ROLE = "decoration"

CODE_BELOW_MINIMUM_SIZE = "BRAND_LOGO_BELOW_MINIMUM_SIZE"
CODE_CLEAR_SPACE_VIOLATED = "BRAND_LOGO_CLEAR_SPACE_VIOLATED"
CODE_CAP_HEIGHT_UNMEASURED = "BRAND_LOGO_CAP_HEIGHT_UNMEASURED"
CODE_BACKGROUND_FORBIDDEN = "BRAND_LOGO_BACKGROUND_FORBIDDEN"
CODE_REVERSED_LOCKUP_REQUIRED = "BRAND_LOGO_REVERSED_LOCKUP_REQUIRED"
CODE_SCREEN_SIZE_UNMEASURED = "BRAND_LOGO_SCREEN_SIZE_UNMEASURED"
#: §BB1(d). The tone under the mark was measured and is not one the owner has
#: named. Fail-closed and blocking: the answer goes back to the owner, it is
#: never resolved to the nearest ruled tint.
CODE_GROUND_UNRECOGNISED = "BRAND_LOGO_GROUND_UNRECOGNISED"
#: Nothing OPAQUE contains the mark, so no ground could be read at all. Also
#: blocking, and distinct from UNRECOGNISED: one is a colour nobody ruled, the
#: other is no colour to rule.
CODE_GROUND_UNMEASURED = "BRAND_LOGO_GROUND_UNMEASURED"
#: §BB2. At least one strand at or above MOTIF_CONTRAST_DELTA_E crosses the
#: mark's ink box, against a permitted count of zero.
CODE_MOTIF_OVER_MARK = "BRAND_LOGO_MOTIF_OVER_MARK"
#: §BB2(d). A crossing strand whose contrast could not be measured on the
#: ruled terms — a stroke, a gradient, or a fill this module cannot reduce to
#: one value. Blocking, because an instrument that cannot see a strand does
#: not get to certify it.
CODE_MOTIF_UNMEASURED = "BRAND_LOGO_MOTIF_UNMEASURED"

# ------------------------------------------------------- cap-band detection
#: The share of inked columns that must agree on a top (or bottom) edge before
#: that edge is called a CAP LINE rather than the tallest thing in a crowd.
#:
#: MEASURED, not chosen to fit. On ``media/brand/logo.png`` the winning edges
#: carry 40.16% and 29.35% of inked columns; on the flat coloured mark that has
#: no cap band at all the best edges carry 4.51% and 4.01%. A 10% floor sits
#: 2.9x below the lowest pass and 2.2x above the highest fail, so it is not
#: tuned to either file — which is the property that matters, because a
#: threshold wedged between two samples describes the samples.
#:
#: A MODE MARGIN WAS TRIED FIRST AND REJECTED ON MEASUREMENT. "The winning
#: edge beats the runner-up by N x" rejects ``logo.png`` itself: its baseline
#: mode leads by only 1.82x because the runner-up is the round letters'
#: overshoot — the very feature the mode is supposed to be ignoring. A
#: x-uniform-null test was also tried and does not separate (20.4x vs 81.5x).
CAP_BAND_MIN_SHARE = 0.10

#: Alpha above which a pixel counts as ink, for assets that carry alpha.
_ALPHA_THRESHOLD = 128

_EPS_MM = 1e-6

#: The same idea for a CIE76 delta-E, WHICH IS DIMENSIONLESS AND IS NOT A
#: MILLIMETRE. It exists as its own name because the first draft of
#: ``motif_findings`` wrote ``de + _EPS_MM >= MOTIF_CONTRAST_DELTA_E``, adding
#: a millimetre to a colour distance — meaningless on its face, and the exact
#: shape ``test_wit_unit_analysis.py`` exists to catch ("a millimetre compared
#: against a point is a finding"). It only ever makes a strand at EXACTLY the
#: threshold count, so it can make the check fire more and never less; §AU6(c)
#: forbids moving a bar to make a measurement PASS, and this moves the other
#: way.
_EPS_DELTA_E = 1e-9

#: NotoSans / NotoSans-Bold, the faces ``emitters/pdf_ai.py`` registers:
#: ``OS/2.sCapHeight = 714`` per 1000 upm, confirmed against the ``H`` glyph's
#: own yMax. Used because ``TextRun.y`` is the BASELINE — ``_draw_text`` calls
#: ``drawCentredString(x, y, ...)`` — so a tier's ink starts ABOVE its ``y``
#: and a validator reading ``y`` as the top edge would under-report every
#: intrusion into the space above the text.
_FONT_CAP_RATIO = 0.714
#: Same face, ``OS/2.sTypoDescender``. Ink below the baseline is still ink.
_FONT_DESCENDER_RATIO = 0.271


def text_ink_top(baseline_mm: float, size_pt: float) -> float:
    """Where a text run's ink actually BEGINS, in document mm.

    PUBLIC because ``compose_container`` has to predict what this module will
    measure. A composer that laid text out against its own copy of the cap
    ratio would drift from this gate the moment either number moved, and the
    gate would then be measuring a layout built against a different model of
    itself (§AR2). ``_ink_box`` below calls this, so the composer and this
    gate share one definition.

    THAT SENTENCE ORIGINALLY READ "so there is exactly one definition of 'the
    top of the ink' in the repository", AND IT WAS FALSE. A fresh-agent audit
    found the second one: ``geometry_report.py:_text_bbox_mm`` computes
    ``run.y - cap_height`` from ``cap_height_em`` — measured per face, else
    ``0.72`` — against this module's fixed ``_FONT_CAP_RATIO`` of ``0.714``,
    and with no baseline-drop term at all. **A repository-wide absence claimed
    inside the docstring of the function written to END §AR2 violations**, and
    claimed without a search, which is AZ0(t)'s subject.

    The correction is deliberately narrow and the wider claim is NOT restored
    by unifying the two here. They may well be the same model and they are not
    obviously the same model: one is a measured per-face ratio and one is a
    constant, and deciding whether the constant is a legitimate fallback or a
    stale duplicate is a measurement nobody has taken. Reaching into
    ``geometry_report`` from this commit would be the chained fix §AC forbids.
    Carried, named, and left visible.

    ``baseline_mm`` is a BASELINE, not a cursor. The distinction is worth the
    sentence: ``compose_container``'s direct-print branch tracks a cursor and
    must add its own baseline drop before calling this, while its NOW branch
    already holds a baseline. Conflating them is a ``size x 0.74812`` error —
    5.99 mm at 8 pt — and it points the wrong way, so it looks like clearance.
    """
    return baseline_mm - size_pt * _FONT_CAP_RATIO * PT_TO_MM


def clear_space_mm(placed_h_mm: float, cap_ratio: float) -> float:
    """The ruled clear space around a mark of this placed height (§AU3/C2).

    PUBLIC for the same reason as ``text_ink_top``: the composer's keep-out and
    this module's verdict must be the same arithmetic or the front is laid out
    against one bar and judged against another.

    ``cap_ratio`` is the measured flat-capital share of the asset. Callers with
    an UNMEASURED band pass ``1.0``, which treats the entire mark as cap band.
    Since a real cap ratio is always <= 1.0, that fallback is STRICTER than any
    measurement it stands in for and can never be weaker (§AL4) — the safety
    argument is a property of the parameter's range, not a promise in a
    comment. NOTE that this module's own verdict does NOT take that fallback:
    ``evaluate_brand_usage`` reports UNMEASURED and declines to rule, because a
    gate that guesses is worse than a gate that abstains, while a LAYOUT still
    has to put the text somewhere. Same formula, deliberately different policy.
    """
    return placed_h_mm * cap_ratio * CLEAR_SPACE_CAP_HEIGHTS


def _ink_columns(path: str):
    """``(width_px, height_px, tops, bots)`` in pixels, or None.

    ``tops``/``bots`` hold one entry per INKED COLUMN. Two ways of being ink
    are supported because the two brand assets in this repository disagree:
    ``media/brand/logo.png`` carries alpha, and the approved mark in
    ``docs/visual_quality/vq2/`` has NO alpha channel at all and is a light
    coloured wordmark on white. Reading only alpha would have called every
    column of the second asset inked and returned a cap ratio of 1.000000 —
    a number that looks like a measurement and is an artefact of the reader.
    """
    try:
        from PIL import Image as _PILImage
        with _PILImage.open(path) as im:
            has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
            rgba = im.convert("RGBA")
            width, height = rgba.size
            px = rgba.load()
            corner = px[0, 0]
    except Exception:  # noqa: BLE001 — any decode failure is unmeasurable
        return None
    if not width or not height:
        return None

    if has_alpha and corner[3] <= _ALPHA_THRESHOLD:
        def inked(p):
            return p[3] > _ALPHA_THRESHOLD
    else:
        # Opaque asset: the ground is whatever the corner is, ink is whatever
        # differs from it. Stated as a limit rather than hidden — a mark that
        # bleeds to its own edge has no readable ground and will measure as
        # fully inked, which the share floor below then rejects rather than
        # dressing up as a cap band.
        def inked(p, _bg=corner):
            return p[:3] != _bg[:3]

    tops, bots = [], []
    for x in range(width):
        ys = [y for y in range(height) if inked(px[x, y])]
        if ys:
            tops.append(ys[0])
            bots.append(ys[-1])
    return width, height, tops, bots


def measure_cap_ratio(path: str) -> dict | None:
    """The flat-capital band of a wordmark, as a fraction of canvas height.

    Returns None when the asset has no cap band to find — §AW3's honest limit
    under §Y2(c). The caller must then report UNMEASURED, never substitute.

    THE FLAT CAPITALS ARE THE MODE, and nothing about any one asset is
    hard-coded. Round letters overshoot the baseline by a few pixels and a
    superscript sits far above the cap line, so both are minorities among
    inked columns; the most common top edge is therefore the cap line and the
    most common bottom edge is the baseline. ``CAP_BAND_MIN_SHARE`` is what
    stops that reasoning being applied to a mark where it does not hold.
    """
    measured = _ink_columns(path)
    if measured is None:
        return None
    width, height, tops, bots = measured
    if not tops:
        return None

    top_hist, bot_hist = Counter(tops), Counter(bots)
    cap_line, cap_n = top_hist.most_common(1)[0]
    baseline, base_n = bot_hist.most_common(1)[0]
    cap_share = cap_n / len(tops)
    base_share = base_n / len(bots)

    if cap_share < CAP_BAND_MIN_SHARE or base_share < CAP_BAND_MIN_SHARE:
        return None
    cap_px = baseline - cap_line + 1
    if cap_px <= 0 or cap_px > height:
        return None

    return {
        "canvas_px": [int(width), int(height)],
        "cap_line_px": int(cap_line),
        "baseline_px": int(baseline),
        "cap_band_px": int(cap_px),
        "cap_ratio": round(cap_px / height, 6),
        "cap_line_share": round(cap_share, 6),
        "baseline_share": round(base_share, 6),
        "inked_columns": len(tops),
        "min_share_required": CAP_BAND_MIN_SHARE,
    }


# ---------------------------------------------------------------- geometry
def _ink_box(node):
    """The mm box a node actually PUTS INK IN, or None when it inks nothing.

    Text is the case that matters and the case a naive reader gets wrong:
    ``TextRun.y`` is the baseline, so the box runs from ``y - cap`` to
    ``y + descender`` rather than from ``y`` downward.
    """
    kind = getattr(node, "type", "")
    if kind == "text":
        size = float(getattr(node, "size_pt", 0.0) or 0.0)
        text = str(getattr(node, "text", "") or "")
        if size <= 0 or not text.strip():
            return None
        desc_mm = size * _FONT_DESCENDER_RATIO * PT_TO_MM
        # x-extent of a centred run is not knowable without shaping the
        # string, so the run is treated as spanning the page horizontally.
        # That is deliberately CONSERVATIVE: it can over-report a horizontal
        # intrusion, never under-report one, and every intrusion this module
        # has actually found is vertical.
        return (float("-inf"), text_ink_top(node.y, size),
                float("inf"), node.y + desc_mm)
    for attrs in (("x", "y", "w", "h"),):
        if all(hasattr(node, a) for a in attrs):
            x, y, w, h = (float(getattr(node, a)) for a in attrs)
            if w <= 0 or h <= 0:
                return None
            return (x, y, x + w, y + h)
    segs = getattr(node, "segments", None)
    if segs:
        xs = [s.x for s in segs if hasattr(s, "x")]
        ys = [s.y for s in segs if hasattr(s, "y")]
        if xs and ys:
            return (min(xs), min(ys), max(xs), max(ys))
    return None


def _contains(outer, inner) -> bool:
    return (outer[0] <= inner[0] + _EPS_MM and outer[1] <= inner[1] + _EPS_MM
            and outer[2] >= inner[2] - _EPS_MM
            and outer[3] >= inner[3] - _EPS_MM)


def _overlap(a, b) -> bool:
    return (a[0] < b[2] - _EPS_MM and b[0] < a[2] - _EPS_MM
            and a[1] < b[3] - _EPS_MM and b[1] < a[3] - _EPS_MM)


def _leaves(node):
    """Every non-group descendant — i.e. everything that can carry ink."""
    if getattr(node, "type", "") == "group":
        for child in getattr(node, "children", None) or ():
            yield from _leaves(child)
    else:
        yield node


def _group_ink_box(group):
    """A group's box: the UNION of its leaves' ink boxes, or None when the
    group inks nothing.

    ``_ink_box`` returns None for a group, because a group has no geometry of
    its own, and that fact is the whole of BA2(c)'s degeneracy proof: a box
    computed this way contains every member by construction, so containment
    ALONE can never distinguish a ground from an ancestor.
    """
    boxes = [b for b in (_ink_box(n) for n in _leaves(group)) if b is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _is_ground(group, logo_box) -> bool:
    """Is this group the surface the mark is printed ON?

    THREE conditions. §BA2(a) gives two and they are NOT SUFFICIENT; the third
    is the executor's, it only ever makes this function return False more
    often, and the measurement that forced it is recorded below.

    1. **DECLARED.** ``role == GROUND_ROLE``, carried at composition.
    2. **CONTAINS.** The group's box contains the mark's box entirely.
    3. **INKS NO TEXT.** No leaf anywhere in the subtree is a text run.

    WHY (1) AND (2) ALONE REPRODUCE BA2(c)'s DEGENERACY THROUGH THE OTHER
    DOOR, MEASURED ON THE LIVE FRONT 2026-08-22 AND NOT REASONED ABOUT.
    ``role="decoration"`` is carried by 22 production sites, and most of them
    are LAYOUT CONTAINERS rather than rendered fields: ``compose_container``
    stamps it on ``Decoration`` (456), on ``FRONT_DIRECT_PRINT`` (379), on
    every ``Surface-*`` panel (589) and on ``Surfaces`` (590), which sits one
    level under ``Root``. On the front the composer emits today, conditions
    (1)+(2) alone silence **21 of 36 leaf nodes, including
    ``product-name-0``** — the very text node §AY2's keep-out exists to
    police. BA2(b) forbids exactly that outcome; it names coordinates as the
    route, and membership turns out to be a second route to the same place.

    AND IT IS NOT AN ARTEFACT OF ``_ink_box``'s CONSERVATIVE TEXT HANDLING,
    which was the first explanation offered and was wrong. ``Decoration``'s
    box is ``(-inf, 66.22, inf, 104.72)`` because a text run is treated as
    page-spanning — but with the text runs removed it is
    ``(55.6, 66.22, 84.4, 104.72)``, and the mark at
    ``(61.36, 70.579, 78.64, 74.182)`` is still inside it. The containment is
    real geometry. Removing the text would not have saved the rule.

    WHY CONDITION 3 IS THE RULING'S OWN LOGIC AND NOT A PATCH ON IT. BA1 ruled
    that a *rendered decoration field* is the ground. Text is not ground: it
    is the thing a ground is printed behind. BA2(b) says so in its own words —
    *"a text run drawn on top of a motif field is still a neighbour"* — and a
    group that inks text is therefore not a field, it is a container holding a
    neighbour. Note this subsumes the weaker rule "a text node never inherits
    the exclusion": if no ground can contain text, no text can be inside one.

    WHAT IT COSTS, STATED SO IT CAN BE LOST. If the motif engine ever emits a
    text glyph inside ``motif-front``, that group stops being a ground and all
    eighteen findings return at once. That is the safe direction — the
    instrument gets LOUDER, not quieter — but it is a real coupling and this
    is where a reader will find it.
    """
    if getattr(group, "role", "") != GROUND_ROLE:
        return False
    if any(getattr(n, "type", "") == "text" for n in _leaves(group)):
        return False
    box = _group_ink_box(group)
    return box is not None and _contains(box, logo_box)


def _ground_members(root, logo_box) -> set:
    """ids of the leaves that are INK IN A GROUND rather than neighbours of one.

    BA2(b): **MEMBERSHIP, NEVER COORDINATES.** A node inherits the exclusion
    because of where it sits in the TREE, never because of where it sits on
    the page. Sharing a bounding box with a ground does not make a node part
    of it, which is why §AY2's 1.5124 mm text collision stays measurable.
    """
    members: set = set()

    def visit(node, inside: bool) -> None:
        if getattr(node, "type", "") != "group":
            if inside:
                members.add(id(node))
            return
        here = inside or _is_ground(node, logo_box)
        for child in getattr(node, "children", None) or ():
            visit(child, here)

    visit(root, False)
    return members


def _clear_space_findings(doc, logo, cap_mm: float) -> list:
    """Every node whose ink enters the logo's clear-space margin.

    A node that CONTAINS the logo entirely is a GROUND, not a neighbour, and
    is judged by the backgrounds rule instead — a decoration field the mark is
    placed on top of has not intruded into its clear space, it is the surface
    the mark is sitting on. That exclusion is a rule about containment, not a
    list of node names, so it cannot quietly grow to cover an inconvenient
    finding.

    §BA (owner-ruled, 2026-08-22) WIDENED WHAT COUNTS AS THAT GROUND, AND THE
    WIDENING IS THE OWNER'S, NOT THIS MODULE'S. C11 asked whether a rendered
    motif field the mark is composed on top of is the mark's SURFACE or its
    NEIGHBOUR; the ruling is SURFACE. So a leaf is now also excluded when it
    is a MEMBER of a group ``_is_ground`` accepts. §AZ0(q) refused to make
    this edit unilaterally and §BA1(c) upholds that refusal as correct: the
    edit is legitimate only because the category was ruled first, in a commit
    that precedes this one (``c44c7d2``).

    **NO BAR MOVED.** Not the 1.0x cap height, not the 12.0 mm floor, not
    ``BACKGROUNDS_PERMITTED``. The ruling says the motif field was never
    inside the set of things the clear-space rule is about, and BA1(d) is the
    refutation of any report phrased as "the clear-space bar was relaxed".

    **AND IT DOES NOT CLEAR THE FRONT.** It moves the mark onto the BACKGROUND
    axis, where a motif field is a tinted ground not named in
    ``BACKGROUNDS_PERMITTED``. Eighteen clear-space findings become one
    ``CODE_BACKGROUND_FORBIDDEN``. That is owner row C12 and it is red on
    purpose.
    """
    lx0, ly0 = logo.x, logo.y
    lx1, ly1 = logo.x + logo.w, logo.y + logo.h
    margin = (lx0 - cap_mm, ly0 - cap_mm, lx1 + cap_mm, ly1 + cap_mm)
    logo_box = (lx0, ly0, lx1, ly1)

    ground_members = _ground_members(doc.root, logo_box)

    findings = []
    for node, _parent in doc.walk():
        if node is logo:
            continue
        if getattr(node, "type", "") == "group":
            continue
        if id(node) in ground_members:
            continue
        box = _ink_box(node)
        if box is None or not _overlap(box, margin):
            continue
        if _contains(box, logo_box):
            continue
        # which side, and by how much — a finding that cannot say where the
        # intrusion is cannot be acted on by whoever has to move something.
        sides = {}
        if box[3] > margin[1] and box[3] <= ly0 + _EPS_MM:
            sides["above"] = round(ly0 - box[3], 4)
        if box[1] < margin[3] and box[1] >= ly1 - _EPS_MM:
            sides["below"] = round(box[1] - ly1, 4)
        if box[2] > margin[0] and box[2] <= lx0 + _EPS_MM:
            sides["left"] = round(lx0 - box[2], 4)
        if box[0] < margin[2] and box[0] >= lx1 - _EPS_MM:
            sides["right"] = round(box[0] - lx1, 4)
        if not sides:
            sides = {"overlapping": 0.0}
        findings.append({
            "node_name": str(getattr(node, "name", "") or ""),
            "node_type": getattr(node, "type", ""),
            "gaps_mm": sides,
            "required_mm": round(cap_mm, 4),
            "shortfall_mm": round(cap_mm - min(sides.values()), 4),
        })
    return sorted(findings, key=lambda f: (-f["shortfall_mm"],
                                           f["node_name"]))


def _hex_of(node) -> str | None:
    """The single flat FILL hex a node paints with, or None when it has none.

    FILL ONLY, AND THAT IS A RULING RATHER THAN A LIMITATION. §BB2(d) sends
    strokes and gradients back to the owner, so this deliberately does not
    resolve a ``Stroke``'s colour: doing so would let the executor adjudicate
    what the owner reserved. ``_strand_unmeasured_reason`` records WHICH of the
    two a None means, so the record never implies blindness where the real
    state is "not ruled yet".

    None is NOT "white" and is not "skip me". A node that inks the mark's box
    and cannot state one fill colour is UNMEASURED and fails closed.
    """
    fill = getattr(node, "fill", None)
    color = getattr(fill, "color", None) if fill is not None else None
    if color is None:
        return None
    try:
        return "#%02X%02X%02X" % (round(color.r * 255), round(color.g * 255),
                                  round(color.b * 255))
    except (AttributeError, TypeError):       # pragma: no cover - defensive
        return None


def _strand_unmeasured_reason(node) -> str:
    """Why a crossing strand could not be measured on the ruled terms.

    MEASURED ON THE LIVE FRONT AND IT IS NOT WHAT THE FIRST DRAFT ASSUMED. Of
    the fourteen strands crossing the mark, eleven are ``flow-line-*`` paths
    that carry no fill at all — but they are not invisible. Each carries a
    0.312 mm ``Stroke`` at opacity 0.9 in #F7EFE4, **the same ink as the three
    ribbons, at the same 4.6305 delta-E**. Reporting them as though the
    instrument could not see them would be false; what is true is that the
    owner has not ruled whether a hairline stroke is a strand for a density
    rule, and BB2(d) says so.
    """
    if getattr(node, "stroke", None) is not None:
        return ("stroked — §BB2(d) reserves strokes to the owner; the ink is "
                "visible but whether a stroke is a strand is not ruled")
    return "no flat fill this module can reduce to one colour"


def _delta_e_hex(hex_a: str, hex_b: str) -> float | None:
    """CIE76 delta-E between two flat hexes, or None if either is unreadable.

    THE MATHS IS IMPORTED, NOT RE-IMPLEMENTED, and the import is lazy for the
    reason the module header now states: ``image_checks`` resolves Django
    settings at module scope.

    §BB2(e) BARS THE OTHER CONSTANT IN THAT MODULE BY NAME.
    ``image_checks.PALETTE_TOLERANCE_DE`` is 25.0, sits eight lines above the
    maths this uses, and exists for image-vs-brand-hex sampling — a different
    question. MEASURED: the live front's strands sit at 4.6305, so at 25.0 no
    strand would ever count and the entire tone-qualified rule would become a
    check that cannot fire. That is not a hypothetical margin; it is the one
    measured on the shipping artwork. It is WATCH backlog H002, and
    ``test_the_barred_constant_is_not_the_one_used`` is what keeps this
    paragraph from being the only thing standing between the two numbers.
    """
    from apps.pipeline.services.image_checks import (_delta_e, _hex_to_rgb,
                                                     _rgb_to_lab)
    rgb_a, rgb_b = _hex_to_rgb(hex_a), _hex_to_rgb(hex_b)
    if rgb_a is None or rgb_b is None:
        return None
    return _delta_e(_rgb_to_lab(rgb_a), _rgb_to_lab(rgb_b))


def measure_ground(doc, logo) -> dict | None:
    """The node whose ink the mark is REPRODUCED ON, read from the document.

    The last OPAQUE filled node, in paint order, painted before the mark and
    whose box CONTAINS the mark's. The pdf/.ai emitter is flat and paints in
    document order, so "last one before the mark that contains it" is the one
    whose colour survives underneath.

    THIS IS THE FUNCTION ``_ground_node``'s DOCSTRING SAID DID NOT EXIST.
    Its capitals, verbatim: *"NOTHING IN PRODUCTION COMPUTES THIS.
    ``evaluate_brand_usage`` takes ``background`` as an argument and believes
    whatever it is told — which is precisely how ``pure_white`` stood as a
    declaration on a front that has never been white, through every tranche
    that ran this gate green."* §BB1(e)(1) authorises the repair and the five
    ``TestTheGroundUnderTheMarkIsMeasuredNotDeclared`` tests are its spec.

    Returns None when nothing opaque contains the mark. That is UNMEASURED and
    it is not a pass: the caller emits a code for it.
    """
    logo_box = _ink_box(logo)
    if logo_box is None:
        return None
    under = None
    for node, _parent in doc.walk():
        if node is logo:
            break
        if getattr(node, "type", "") == "group":
            continue
        fill = getattr(node, "fill", None)
        if fill is None or float(getattr(fill, "opacity", 1.0) or 0.0) < 1.0:
            # A 40%-opaque panel does not determine the tone the mark
            # reproduces on — what shows through it does. Declaring its colour
            # would be a measurement of something invisible.
            continue
        box = _ink_box(node)
        if box is not None and _contains(box, logo_box):
            under = node
    if under is None:
        return None
    hexed = _hex_of(under)
    return {
        "node_name": str(getattr(under, "name", "") or ""),
        "hex": hexed,
        "resolved": GROUND_HEX_RULED.get(hexed or ""),
    }


def motif_findings(doc, logo, ground_hex: str | None) -> list:
    """§BB2 — the strands that CROSS the mark's own ink box, counted only when
    they are perceptibly there.

    WHICH NODES ARE STRANDS IS NOT A LIST OF NAMES. A strand is a leaf that
    §BA2 already ruled is INK IN A GROUND — a member of a group ``_is_ground``
    accepts — whose box OVERLAPS the mark's ink box without CONTAINING it.
    That definition dovetails with the clear-space axis instead of competing
    with it: §BA moved these leaves OFF the clear-space list by ruling them
    surface rather than neighbour, and this is the axis that catches them
    instead. A motif emitted outside such a group was never excluded and is
    still a clear-space finding, so there is no gap between the two rules.

    THE MARK'S OWN INK BOX, NOT ITS CLEAR-SPACE MARGIN. BB2 rules the density
    limit on "the mark's ink box", which is a strictly smaller region than the
    1.0x cap-height margin AY2 polices. A strand inside the margin but clear
    of the box is not a BB2 finding.

    CONTRAST DECIDES WHETHER A CROSSING COUNTS:

      * delta-E >= MOTIF_CONTRAST_DELTA_E  -> counts. Zero are permitted.
      * delta-E <  MOTIF_CONTRAST_DELTA_E  -> UNRESTRICTED. Reported for the
        record and NOT a violation, because the owner ruled the rule governs
        visible strands only.
      * unmeasurable (a stroke, a gradient, no flat fill either side)
        -> UNMEASURED and FAILS CLOSED, with the reason recorded.
    """
    logo_box = _ink_box(logo)
    if logo_box is None:
        return []
    members = _ground_members(doc.root, logo_box)
    out = []
    for node, _parent in doc.walk():
        if node is logo or getattr(node, "type", "") == "group":
            continue
        if id(node) not in members:
            continue
        box = _ink_box(node)
        if box is None or not _overlap(box, logo_box):
            continue
        if _contains(box, logo_box):
            # the field itself, not a strand on it
            continue
        strand_hex = _hex_of(node)
        de = (None if not strand_hex or not ground_hex
              else _delta_e_hex(strand_hex, ground_hex))
        out.append({
            "node_name": str(getattr(node, "name", "") or ""),
            "node_type": getattr(node, "type", ""),
            "strand_hex": strand_hex,
            "field_hex": ground_hex,
            "delta_e": None if de is None else round(de, 4),
            "threshold_delta_e": MOTIF_CONTRAST_DELTA_E,
            "contrast_measured": de is not None,
            "unmeasured_reason": (None if de is not None
                                  else _strand_unmeasured_reason(node)),
            # None = UNMEASURED, which fails closed at the caller. False =
            # measured and below the line, which the owner ruled unrestricted.
            "counts": (None if de is None
                       else de + _EPS_DELTA_E >= MOTIF_CONTRAST_DELTA_E),
        })
    return sorted(out, key=lambda f: (-(f["delta_e"] or 0.0), f["node_name"]))


def evaluate_brand_usage(doc, *, background: str | None = None,
                         media: str = "print",
                         reversed_lockup: bool = False,
                         dpi: float | None = None) -> dict | None:
    """``container_brand_usage/1.0`` for an emitted Document, or None when no
    logo was emitted.

    ``background`` names the ground the mark is placed on. Supplying None
    means NOBODY HAS SAID, and the axis reports UNMEASURED — it does not
    report a pass. AU3 permits three grounds by name and forbids "everything
    else"; a validator that read silence as one of the three would be
    inventing the answer most likely to be green.

    ``dpi`` IS REQUIRED FOR ``media="screen"`` AND THIS IS A DEFECT IN AU3
    THAT WRITING THE VALIDATOR EXPOSED. The ruling gives two floors — "12.0 mm
    reproduced width in print, 60 px reproduced width on screen" — but the
    Design Graph is millimetres throughout (``graph.Document.page_w``), and a
    millimetre document HAS NO PIXEL WIDTH until a rendering resolution is
    chosen. The first draft of this function compared a 17.28 mm placement
    against the number 60 and returned FAIL: a category error that reads as a
    measurement, which is precisely the §AK3 shape. So screen media converts
    through an explicit ``dpi`` or reports UNMEASURED. It never guesses one —
    a default of 72 or 96 would make the axis green or red by an assumption
    the owner never made.
    """
    # [THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The placed marks through the ONE helper every reader shares —
    # a mark drawn from its approved vector master among them, judged by the same bars on its box, its cap band
    # measured by this module's own ``measure_cap_ratio`` on the master rasterised (``brand_mark.cap_band``)]
    from apps.ire import brand_mark as _mark

    nodes = _mark.logo_nodes(doc)
    if not nodes:
        return None

    screen = media != "print"
    minimum = (MINIMUM_WIDTH_PX_SCREEN if screen else MINIMUM_WIDTH_MM_PRINT)
    placements, codes, assets = [], [], {}

    for node in nodes:
        src = _mark.source_of(node)
        if src not in assets:
            assets[src] = (_mark.band_of(node, src) if _mark.is_mark(node)
                           else measure_cap_ratio(src) if src else None)
        band = assets[src]
        placed_w = float(getattr(node, "w", 0.0) or 0.0)
        placed_h = float(getattr(node, "h", 0.0) or 0.0)

        # The reproduced width on the axis the ruling's floor is stated in.
        if screen:
            reproduced = (None if not dpi
                          else round(placed_w / 25.4 * float(dpi), 3))
        else:
            reproduced = round(placed_w, 3)
        meets_size = (None if reproduced is None
                      else reproduced + _EPS_MM >= minimum)

        record: dict = {
            "node_name": str(getattr(node, "name", "") or ""),
            "src": src,
            "placed_mm": [round(node.x, 3), round(node.y, 3),
                          round(placed_w, 3), round(placed_h, 3)],
            "reproduced_width_mm": round(placed_w, 3),
            "reproduced_width": reproduced,
            "reproduced_unit": "px" if screen else "mm",
            "minimum_width": minimum,
            "dpi": dpi,
            "meets_minimum_size": meets_size,
        }
        if meets_size is None:
            codes.append(CODE_SCREEN_SIZE_UNMEASURED)
        elif not meets_size:
            codes.append(CODE_BELOW_MINIMUM_SIZE)

        if band is None:
            # §AW3 / §Y2(c): no cap band, so no cap height, so no clear-space
            # verdict. UNMEASURED is blocking and is the true state.
            record.update({
                "cap_ratio": None,
                "logo_cap_height_mm": None,
                "clear_space_measured": False,
                "clear_space_findings": [],
                "meets_clear_space": None,
                "cap_height_unmeasured_reason":
                    "no flat-capital band above "
                    f"{CAP_BAND_MIN_SHARE:.0%} of inked columns",
            })
            codes.append(CODE_CAP_HEIGHT_UNMEASURED)
        else:
            cap_mm = clear_space_mm(placed_h, band["cap_ratio"])
            findings = _clear_space_findings(doc, node, cap_mm)
            record.update({
                "cap_ratio": band["cap_ratio"],
                "logo_cap_height_mm": round(cap_mm, 4),
                "clear_space_measured": True,
                "clear_space_findings": findings,
                "meets_clear_space": not findings,
            })
            if findings:
                codes.append(CODE_CLEAR_SPACE_VIOLATED)
        placements.append(record)

    # ------------------------------------------------------- backgrounds
    if background is None:
        background_verdict = None
    elif background == BACKGROUND_REVERSED_ONLY:
        background_verdict = bool(reversed_lockup)
        if not background_verdict:
            codes.append(CODE_REVERSED_LOCKUP_REQUIRED)
    elif background in BACKGROUNDS_PERMITTED:
        background_verdict = True
    else:
        background_verdict = False
        codes.append(CODE_BACKGROUND_FORBIDDEN)

    # --------------------------------------------- the MEASURED ground (§BB1)
    # TWO AXES, NEITHER OF WHICH CAN LIE FOR THE OTHER. The block above judges
    # what the caller DECLARED and is deliberately untouched; this one judges
    # what the document actually paints and cannot be argued with by a caller.
    #
    # THE OBVIOUS DESIGN WAS REJECTED ON EVIDENCE, NOT TASTE. "Measurement
    # replaces declaration" — compute the ground, ignore the argument — breaks
    # ``test_brand_dark_REQUIRES_the_reversed_lockup`` and
    # ``test_everything_else_is_forbidden``, which run on a REAL composed
    # document whose ground measures #F6EDEB and whose whole subject is the
    # declared value. BB1(e)(3) forbids exactly that outcome in its own words:
    # "churning them would destroy the axis they measure."
    ground = measure_ground(doc, nodes[0])
    if ground is None:
        ground_permitted = None
        codes.append(CODE_GROUND_UNMEASURED)
    elif ground["resolved"] in BACKGROUNDS_PERMITTED:
        ground_permitted = True
    else:
        # BB1(d): back to the owner, never resolved to the nearest ruled tint.
        # There is no reversed-lockup branch here because every value in
        # GROUND_HEX_RULED is a LIGHT ground; if the owner ever names a dark
        # hex, the pairing rule needs its own ruling and an unreachable branch
        # written today would be a guess standing in for it.
        ground_permitted = False
        codes.append(CODE_GROUND_UNRECOGNISED)

    # ------------------------------------------------ the motif field (§BB2)
    motifs = motif_findings(doc, nodes[0],
                            ground["hex"] if ground is not None else None)
    counted = [f for f in motifs if f["counts"] is True]
    unmeasured_strands = [f for f in motifs if f["counts"] is None]
    if len(counted) > MOTIF_STRANDS_PERMITTED_OVER_MARK:
        codes.append(CODE_MOTIF_OVER_MARK)
    if unmeasured_strands:
        codes.append(CODE_MOTIF_UNMEASURED)
    if counted:
        # A MEASURED VIOLATION OUTRANKS AN UNMEASURED ONE. Folding these to
        # None because something else could not be read would report a front
        # that definitely fails as one nobody could judge.
        motif_verdict = False
    elif unmeasured_strands:
        motif_verdict = None
    else:
        motif_verdict = True

    # Do the two axes agree? None whenever either side has nothing to say.
    if (background is None or ground is None
            or ground["resolved"] is None):
        declaration_true = None
    else:
        declaration_true = (background == ground["resolved"])

    clear_flags = [p["meets_clear_space"] for p in placements]
    size_flags = [p["meets_minimum_size"] for p in placements]
    return {
        "schema_version": SCHEMA,
        "media": media,
        "dpi": dpi,
        "ruled_by": "§AU3 (owner) / §AW3 (executor, cap-height semantics)",
        "clear_space_cap_heights": CLEAR_SPACE_CAP_HEIGHTS,
        "minimum_width_mm_print": MINIMUM_WIDTH_MM_PRINT,
        "minimum_width_px_screen": MINIMUM_WIDTH_PX_SCREEN,
        # UNMEASURED is preserved here for the same reason as clear space:
        # ``all([None])`` is False, so folding them would report a screen
        # placement nobody could measure as one that FAILED.
        "meets_minimum_size": (None if any(f is None for f in size_flags)
                               else all(size_flags)),
        # None (UNMEASURED) is NOT False and is not folded into one: an axis
        # nobody could measure and an axis that failed are different states.
        "meets_clear_space": (None if any(f is None for f in clear_flags)
                              else all(clear_flags)),
        "background": background,
        "background_permitted": background_verdict,
        # ---- the measured axis (§BB1). ``background_*`` above is the DECLARED
        # one and keeps its meaning exactly; nothing here can change it.
        "ground_node": None if ground is None else ground["node_name"],
        "ground_hex": None if ground is None else ground["hex"],
        "ground_resolved": None if ground is None else ground["resolved"],
        "ground_permitted": ground_permitted,
        "background_declaration_true": declaration_true,
        # ---- the motif axis (§BB2)
        "motif_contrast_delta_e": MOTIF_CONTRAST_DELTA_E,
        "motif_strands_permitted": MOTIF_STRANDS_PERMITTED_OVER_MARK,
        "motif_strands_over_mark": len(counted),
        "motif_strands_unmeasured": len(unmeasured_strands),
        "motif_findings": motifs,
        "meets_motif_density": motif_verdict,
        "reversed_lockup": reversed_lockup,
        "codes": sorted(set(codes)),
        # BOTH axes now, and UNMEASURED on either is not a pass. The added
        # conjuncts are belt-and-braces: every False or None state above also
        # appends a code, so ``not codes`` already covers them. They are
        # written out anyway because a future edit that appends no code for
        # some new state would otherwise make ``clean`` silently true again.
        "clean": (not codes and background_verdict is not None
                  and ground_permitted is True and motif_verdict is True),
        "placement_count": len(placements),
        "placements": placements,
        "assets": [{"path": k, "cap_band": assets[k],
                    "basename": os.path.basename(k)}
                   for k in sorted(assets)],
        "measured_by": "apps.ire.container_brand_usage.evaluate_brand_usage",
    }


__all__ = [
    "SCHEMA", "CLEAR_SPACE_CAP_HEIGHTS", "MINIMUM_WIDTH_MM_PRINT",
    "MINIMUM_WIDTH_PX_SCREEN", "BACKGROUNDS_PERMITTED",
    "BACKGROUND_REVERSED_ONLY", "CAP_BAND_MIN_SHARE",
    "CODE_BELOW_MINIMUM_SIZE", "CODE_CLEAR_SPACE_VIOLATED",
    "CODE_CAP_HEIGHT_UNMEASURED", "CODE_BACKGROUND_FORBIDDEN",
    "CODE_REVERSED_LOCKUP_REQUIRED", "CODE_SCREEN_SIZE_UNMEASURED",
    "CODE_GROUND_UNRECOGNISED", "CODE_GROUND_UNMEASURED",
    "CODE_MOTIF_OVER_MARK", "CODE_MOTIF_UNMEASURED",
    "GROUND_HEX_RULED", "MOTIF_CONTRAST_DELTA_E",
    "MOTIF_STRANDS_PERMITTED_OVER_MARK",
    "measure_cap_ratio", "evaluate_brand_usage",
    "measure_ground", "motif_findings",
    # exported so the COMPOSER can predict this gate instead of guessing it
    "text_ink_top", "clear_space_mm",
]
