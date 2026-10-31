"""§W1 — the container's back panel, drawn at the size it is printed at.

Until now the back panel existed only inside the presentation sheet's 92×46 mm
schematic strip: body copy at ``2.0 * k`` pt with ``k`` floored at 0.5, so the
ingredient list rendered at 1.0 pt, truncated to 70 characters and headings to
40. §W1 ruled that a product gap, not a measurement gap — the panel a printer
and a regulator read first cannot be a 1 pt diagram — and this module is the
panel itself: the confirmed ``BACK_PRINT_ZONE``'s own width and height in
document mm, with the whole of the supplied copy laid into it.

**The strip stays.** §W1(a) keeps it and §W1(c) forbids measuring it harder;
``compose_dropper._back_panel`` is untouched. This is a second, full-scale
drawing of the same surface, and the two are told apart by the group prefix so
that no reader has to guess which one it is looking at.

What this module refuses to do is the point of it. §W1(d) ruled the strip's
70/40-character limits out of the full-scale copy, so no character limit is
applied here at all: the layout is computed from EVERY supplied character, and
the only thing that bounds the panel is the panel's own measured edge. Copy
that edge excludes is not cut to a constant and not quietly dropped — it is
counted, named by the section it came from, measured in millimetres, and
reported as ``CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL``, which blocks. A 30 ml
dropper's back panel that cannot hold a full INCI list at a legible size is a
finding about the product, and the finding is the deliverable.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_back_panel/1.0"

#: §W1(d) — the supplied copy does not fit the panel it is printed on. A
#: finding about the product, not a layout parameter to tune.
COPY_EXCEEDS_PANEL = "CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL"

#: no confirmed BACK_PRINT_ZONE, so there are no true dimensions to draw at
#: and no panel is emitted. §W1(b): the axis stays UNMEASURED on that surface.
NO_CONFIRMED_ZONE = "CONTAINER_BACK_PANEL_NO_CONFIRMED_ZONE"

#: the face the copy is set in could not be measured, so the line breaks the
#: emitted document will have are not known — and a panel whose line breaks
#: are guesses cannot be allowed to decide which copy the edge excludes. No
#: panel is emitted, exactly as when there is no zone: an unmeasured fit is
#: not a fit that happens to be tight.
FIT_UNMEASURED = "CONTAINER_BACK_PANEL_FIT_UNMEASURED"

SURFACE = "BODY_BACK"
ZONE_TYPE = "BACK_PRINT_ZONE"

MM_PER_PT = 25.4 / 72.0

# --- §Z3: what size the copy is set at, and who decided ----------------------
#
# The 15 `back-panel-*` runs sat at 5.0 pt against a 6.0 pt floor because the
# COMPOSER and the AXIS were reading different sources: the composer had no
# production-method record and took §W2(b)'s disclosed fallback, while the axis
# resolved BODY_BACK's own method and got the capability table's number. §Z3(a)
# ruled that disagreement — **a floor from an actual capability table outranks
# a fallback** — so the record the axis reads is now threaded to the composer
# and one object decides both. The two can no longer disagree, which is a
# stronger property than getting today's number right.

#: BODY_BACK has a print method recorded and the copy is set at its floor.
SIZE_TABLE = "container_production_method/1.0 capability table for " + SURFACE

#: §W2(b) — nothing is recorded for this surface, so the disclosed fallback is
#: what the panel is set at, and the record says the word FALLBACK.
SIZE_FALLBACK = "FALLBACK — §W2(b), no print method recorded for " + SURFACE

#: an explicit `size_pt` from the caller. Kept so a test can set the panel at a
#: size deliberately, and named so a record can never present a caller's choice
#: as something the capability table said.
SIZE_CALLER = "supplied by the caller, not resolved from a methods record"

SIZE_AMBIGUOUS = (
    "FALLBACK — " + SURFACE + " carries print methods with DIFFERENT minimum "
    "text sizes. §W2 reserves that case for the owner and the typography axis "
    "stays UNMEASURED and blocking on this surface; the composer takes the "
    "disclosed fallback rather than settling the ambiguity by choosing a size.")

#: §X2(b) — the one direction this resolution may NOT travel. A table floor
#: BELOW 5.0 (an ADHESIVE_LABEL's 4.0, say) is a legitimate floor for the axis
#: to judge against, but setting the copy AT it would shrink the type and buy
#: panel height, which is the thing §X2(b) forbids by name: "buying 47 mm by
#: dropping type size is the purest form of moving a bar to make something
#: pass". So the size only ever moves UP from the fallback. The AXIS still
#: measures against the table's own lower number — floor and size are two
#: different quantities with two different jobs, and this field exists so the
#: record can never blur them.
SIZE_HELD_UP_BY_FALLBACK = (
    "the capability table's floor for " + SURFACE + " is BELOW the 5.0 pt "
    "fallback. The copy is NOT set down to it: §X2(b) forbids buying panel "
    "height by dropping type size. The typography axis still judges these runs "
    "against the table's own lower floor; this is the size, not the floor.")


def size_for_surface(methods_record, size_pt: float | None = None, surface: str | None = None):
    """``(size_pt, source_record)`` — what this panel's copy is set at.

    §Z3(a). An explicit ``size_pt`` wins, because a caller that names a size
    has already decided. Otherwise ``BODY_BACK``'s own recorded print method
    decides, never going below §W2(b)'s fallback (see
    ``SIZE_HELD_UP_BY_FALLBACK``).

    §AA3(c) — and the record now says whether any stage CONFIRMED that method.
    On live output nothing ever has: the technique is `make_zone`'s default
    argument, so `method_confirmed` is False and `size_is_an_assumption` is
    True. The panel still draws at that size; it no longer presents the size
    as a fact.
    """
    # §AA3(c) — ASSUMPTION is imported rather than restated here so the panel
    # and the axis cannot drift into two wordings of the same disclosure.
    from apps.ire.container_method_provenance import ASSUMPTION
    from apps.ire.container_text_floor import FALLBACK_FLOOR_PT, surface_floors

    resolved = None
    if size_pt is not None:
        source, floor = SIZE_CALLER, float(size_pt)
    else:
        resolved = (surface_floors(methods_record) or {}).get(surface or SURFACE)
        if resolved is None:
            source, floor = SIZE_FALLBACK, None
        elif resolved["ambiguous"]:
            source, floor = SIZE_AMBIGUOUS, None
        else:
            source, floor = SIZE_TABLE, float(resolved["floor_pt"])

    if source == SIZE_CALLER:
        size = floor
    else:
        size = FALLBACK_FLOOR_PT if floor is None else max(floor,
                                                           FALLBACK_FLOOR_PT)
    held_up = floor is not None and source != SIZE_CALLER \
        and floor < FALLBACK_FLOOR_PT
    # §AA3(c) — the number this panel is set at is an ASSUMPTION unless some
    # stage confirmed the method it came from. `source` above answers "which
    # table was read"; these answer "did anyone confirm the row". Before §AA3
    # this record was byte-identical for a machine default and a hand-written
    # fixture, which is how a proposal came to be read as a confirmation.
    confirmed = None if resolved is None else bool(
        resolved.get("method_confirmed"))
    return size, {
        "size_pt": size,
        "source": source,
        "surface": SURFACE,
        "surface_floor_pt": floor if source != SIZE_CALLER else None,
        "fallback_floor_pt": FALLBACK_FLOOR_PT,
        "held_up_by_fallback": held_up,
        "held_up_reason": SIZE_HELD_UP_BY_FALLBACK if held_up else None,
        "method_types": sorted(str(m["method_type"])
                               for m in (resolved or {}).get("methods") or []),
        "zone_tightened": bool((resolved or {}).get("zone_tightened")),
        # None where no method was resolved at all: there is nothing to be
        # unconfirmed, and `source` already says FALLBACK or CALLER.
        "method_confirmed": confirmed,
        "method_stages": (resolved or {}).get("method_stages") or [],
        "size_is_an_assumption": confirmed is False,
        "assumption_reason": ASSUMPTION if confirmed is False else None,
        "measured_by": "apps.ire.back_panel.size_for_surface",
    }

#: the printed margin inside the zone. The zone is already the safe printable
#: area, so this is the panel's own typographic inset, not a second safety
#: allowance — it is recorded in the fit record so the fit can be recomputed.
#: [§BH54(b) (n), OWNER RULED 2026-09-19: "THE BACK CARRIES A SAFE MARGIN on the same principle as the front: derive it
#: from the back zone the way 16.0 was derived from the front, state the derivation, and apply it. Do not type 3.0
#: because it is a round number." The sentence above is what stood and is no longer the rule: the zone is the printable
#: AREA, and the copy keeps the zone record's own `safe_margin_mm` inside it, on the back as on the front. This 1.5 is
#: now only the LEGACY inset of a zone whose record carries no usable margin — see `zone_margin`.]
MARGIN_MM = 1.5

#: §BH54(b) (n) — where the inset came from, said on every fit record
MARGIN_FROM_ZONE = ("the zone record's own safe_margin_mm — §BH54(b) (n): the back's margin derived from the back zone the "
                    "way the front's safe area is derived from the front zone (width − 2 × safe_margin_mm)")
MARGIN_LEGACY = ("LEGACY 1.5 mm typographic inset — this zone's record carries no usable safe_margin_mm, so there is "
                 "nothing to derive a margin from")


def zone_margin(zone) -> tuple[float, str]:
    """``(margin_mm, source)`` — the inset the back panel's copy keeps from its zone's edge.

    THE DERIVATION, stated as he asked. The front's 16.0 mm is its zone's width less twice that zone record's own
    ``safe_margin_mm`` (22.0 − 2 × 3.0; ``compose_dropper.front_copy_fit``). The back is derived the same way from
    ITS zone's record: the column is the back zone's width less twice the back zone's ``safe_margin_mm``, and the
    copy height its height less the same. The number is READ from the record and never typed here. Said plainly,
    because he warned against a round number: on task 52 both zones' records carry 3.0, and on both it is
    ``container_contract.make_zone``'s default argument, carried on a zone he confirmed — nobody measured a print
    process to get it, on either face. A margin that is missing, not a number, not positive, or too large to leave
    any column is not usable, and the legacy inset stands with its source saying so."""
    try:
        margin = float((zone or {}).get("safe_margin_mm"))
        room = min(float(zone["width"]), float(zone["height"]))
    except (TypeError, ValueError, KeyError):
        return MARGIN_MM, MARGIN_LEGACY
    if margin > 0 and 2 * margin < room:
        return margin, MARGIN_FROM_ZONE
    return MARGIN_MM, MARGIN_LEGACY

#: line pitch as a multiple of the em, and the space between sections.
LEADING_EM = 1.2
SECTION_GAP_MM = 0.8
#: [His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), C: "Back
#: label laid out like packaging, using the whole area: clear hierarchy, the three languages as balanced blocks; never
#: cramped at the bottom with empty space below."] a product's back grows from its print size, a quarter point at a time,
#: while the whole copy still stands in the panel, to this — then the height left is shared between its language blocks
GROW_MAX_PT = 8.0
#: … the least room between two language blocks as it grows, the most once the height left is shared, and a little
#: height kept back so the spread lies inside its foot
BLOCK_GAP_MIN_MM = 3.0
BLOCK_GAP_MAX_MM = 8.0
BLOCK_RESERVE_MM = 0.2
#: … as it grows, every line wrapped to this share of its column (MEASURED while building it: a single word wider than
#: its column — "INGREDIENTES" on an ampoule's back — grew into the margin, the height alone being checked) — and room
#: kept under its last baseline for that line's descent, this share of its size (MEASURED: a back grown to its foot hung
#: its last line's descenders 0.1–0.5 mm into the margin, the fit counting to its baseline)
GROW_WIDTH_SHARE = 0.97
DESCENT_EM = 0.3
#: [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] … and an Arabic last line's: the Naskh face hangs deeper
#: (MEASURED: its lowest glyph 0.59 em under the baseline, Poppins' 0.35 — a back whose Arabic block came last, grown to
#: its foot with the full set, hung its last line 0.2 mm into the margin at 0.3)
DESCENT_AR_EM = 0.6


def _room_under(record: dict) -> float:
    """The height a laid label leaves under its last line's descent (DESCENT_EM of its size; an Arabic line's
    DESCENT_AR_EM), in millimetres."""
    tail = record["lines"][-1:]
    last = max((float(e.get("size_pt", record["size_pt"])) for e in tail), default=0.0)
    descent = DESCENT_AR_EM if any(e.get("lang") == "ar" for e in tail) else DESCENT_EM
    return record["height_available_mm"] - record["height_required_mm"] - descent * last * MM_PER_PT


def lines_within(record: dict, faces_of: dict) -> bool:
    """Every line of ``record`` — wrapped at GROW_WIDTH_SHARE of its column — no wider than the whole column as drawn in
    its own face (``faces_of``: ``{(language — "ar" or else "en", role): face}``), measured by its glyphs' outlines: a
    single word wider than the column (it cannot break) stops the label growing. The Arabic, shaped as it is wrapped,
    keeps the share's room; a Latin line no face measures is never taken as within."""
    from apps.ire.text_metrics import drawn_width_mm
    column = float(record["column_mm"]) / GROW_WIDTH_SHARE
    for entry in record["lines"]:
        if entry.get("lang") == "ar":
            continue
        role = "heading" if entry["role"] == "heading" else "copy"
        em_mm = float(entry.get("size_pt", record["size_pt"])) * MM_PER_PT
        width = drawn_width_mm(entry["text"], em_mm, faces_of[("en", role)])
        if width is None or width > column:
            return False
    return True

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §W1 — the back panel is emitted at the "
    "confirmed BACK_PRINT_ZONE's true dimensions with untruncated copy. The "
    "schematic strip stays as a map (§W1(a)) and is not measured harder "
    "(§W1(c)); this panel is measured like any other surface (§W1(b)). The "
    "strip's 70/40-character limits do not follow the copy here (§W1(d))."
)

NO_TRUNCATION = (
    "no character limit is applied to this panel. The layout is computed from "
    "every supplied character and the panel's own measured edge is the only "
    "bound on it. Copy the edge excludes is not cut to a constant: it is "
    "counted, named by section, measured in mm, and reported as "
    + COPY_EXCEEDS_PANEL + ", which blocks. Fitting the copy is the owner's "
    "ruling to make — a larger panel, a wrap label, an insert — and shrinking "
    "it here would answer it by making the answer invisible."
)


def back_zone(zones) -> dict | None:
    """The confirmed ``BACK_PRINT_ZONE``, or None when there is not one."""
    return next((z for z in zones or []
                 if z.get("zone_type") == ZONE_TYPE), None)


def wrap_lines(text: str, size_pt: float, width_mm: float,
               font_name: str | None) -> list[str] | None:
    """``text`` broken to ``width_mm`` at the EMITTED advance widths, or None
    when the face is not registered and no width was measured at all.

    Strict on purpose. ``text_metrics.text_width_mm`` would hand back a
    char-count estimate, and a fit computed from an estimate reports a panel
    as full or as roomy on the strength of a guess — the defect class this
    programme keeps catching. A word longer than the column is left on its own
    line rather than broken: hyphenating an INCI name invents a word.
    """
    from apps.ire.text_metrics import drawn_width_mm

    words = str(text or "").split()
    if not words:
        return []
    em_mm = size_pt * MM_PER_PT
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        # [his goal of 2026-10-06, item 8] the width the line's ink covers, by its glyphs' outlines
        width = drawn_width_mm(trial, em_mm, font_name)
        if width is None:
            return None
        if width <= width_mm or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def wrap_arabic(text: str, size_pt: float, width_mm: float, latin_font: str | None,
                arabic_font: str | None = None) -> list[str] | None:
    """[His final goal, 2026-10-05, A.] Arabic ``text`` broken to ``width_mm`` on its LOGICAL words, each line measured
    shaped in the Arabic face it is drawn in (``arabic_font`` — [his goal of 2026-10-06, item 8] a heading's is the
    Bold — else the label's), its Latin runs in ``latin_font``; None where no Arabic face can measure it."""
    from apps.dielines.exporters.info_panel import _resolve_arabic_font_for_label
    from apps.dielines.exporters.text_intl import wrap_ar_logical
    if not str(text or "").strip():
        return []
    face = arabic_font or _resolve_arabic_font_for_label()
    if not face:
        return None
    return wrap_ar_logical(text, face, size_pt, width_mm / MM_PER_PT, latin_font=latin_font, keep_harakat=True)


#: [His correction of 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a6b2092): "Shrink the whole label
#: evenly until everything fits, keeping its layout, spacing and order. Floor: 3 pt."] the floor a design's label shrinks
#: to — his final goal's 4 pt for the fine print alone gives way to it
LABEL_FLOOR_PT = 3.0


def label_floor_pt(method_floor_pt=None, method_confirmed=None) -> float:
    """[His correction of 2026-10-07] the size a label may shrink to on a surface: his 3 pt, unless a print method
    someone CONFIRMED records a larger minimum — what that method can print — which is then its floor (the executor's
    reading, his to veto). A method the machine proposed and nobody confirmed (on live output every one is:
    ``make_zone``'s default technique, §AA3(c)) is an assumption, and an assumption never holds his label above his
    floor. One answer, read by the panel that shrinks (``compose_back_panel``) and the axis that measures it
    (``container_text_floor``)."""
    if method_confirmed and method_floor_pt is not None:
        return max(float(method_floor_pt), LABEL_FLOOR_PT)
    return LABEL_FLOOR_PT


def label_floor_of(size_source: dict) -> float:
    """``label_floor_pt`` for ``size_for_surface``'s record. A size the caller named is the size it decided: never
    shrunk."""
    if size_source.get("source") == SIZE_CALLER:
        return float(size_source["size_pt"])
    return label_floor_pt(size_source.get("surface_floor_pt"), size_source.get("method_confirmed"))


def layout(sections, width_mm: float, height_mm: float, *, size_pt: float,
           regular: str | None, bold: str | None,
           margin_mm: float = MARGIN_MM, first_section: int = 0, fine_size_pt: float | None = None,
           arabic_regular: str | None = None, arabic_bold: str | None = None, block_gap_mm: float = 0.0,
           column_share: float = 1.0) -> dict:
    """Where every line of the supplied copy falls on a panel this size.

    Pure geometry over the WHOLE of the copy. ``lines`` carries a ``fits``
    flag per line rather than being pre-filtered, so the caller draws the
    panel and the record counts the shortfall off the same list — two passes
    over the same copy is how a record comes to describe a document that was
    never drawn.
    """
    column = (width_mm - 2 * margin_mm) * column_share   # §BH54(b) (n): the caller's margin — the zone's own
    available = height_mm - 2 * margin_mm
    line_h = size_pt * MM_PER_PT * LEADING_EM

    measured = True
    preserved = True
    lines: list[dict] = []
    per_section: list[dict] = []
    y = 0.0
    lang = None
    for index, section in enumerate(sections or [], start=first_section):
        supplied_text, wrapped = {}, []
        # [his test finding on design 122's drawing, C] each language a block: the room shared between them before each
        # block after the first
        here = (section or {}).get("lang")
        if lang is not None and here != lang:
            y += block_gap_mm
        lang = here
        # [his final goal, 2026-10-05, A] an Arabic section wrapped on its own words, in the Arabic face, set right
        arabic = (section or {}).get("lang") == "ar"
        # [his final goal, C5] the ingredients and the warnings, in every language, at the fine print's size
        fine = bool((section or {}).get("fine")) and fine_size_pt is not None
        size = fine_size_pt if fine else size_pt
        step = size * MM_PER_PT * LEADING_EM
        for role, key, font, ar_font in (("heading", "heading", bold, arabic_bold),
                                         ("copy", "text", regular, arabic_regular)):
            # whitespace is normalised before anything counts it, so that a
            # line break — which consumes the space it breaks at — cannot be
            # mistaken for a character the panel dropped.
            text = " ".join(str((section or {}).get(key, "") or "").split())
            supplied_text[role] = text
            broken = (wrap_arabic(text, size, column, font, ar_font) if arabic
                      else wrap_lines(text, size, column, font))
            if broken is None:
                measured = False
                broken = [text] if text else []
            if " ".join(broken) != text:
                preserved = False
            wrapped.extend((role, line) for line in broken)

        section_lines = []
        for order, (role, text) in enumerate(wrapped):
            y += step
            entry = {"section": index, "role": role, "order": order,
                     "text": text, "baseline_mm": round(y, 4),
                     "fits": y <= available + 1e-9}
            if arabic:
                entry["lang"] = "ar"
            if fine:
                entry["fine"], entry["size_pt"] = True, size
            lines.append(entry)
            section_lines.append(entry)
        y += SECTION_GAP_MM

        # baselines only increase, so the ``fits`` filter can remove a SUFFIX
        # and nothing else — what the panel holds is a prefix of what it was
        # given by construction, and the claim worth checking is the one above:
        # that the wrap itself reconstructs the supplied copy.
        emitted_text = {role: " ".join(e["text"] for e in section_lines
                                       if e["role"] == role and e["fits"])
                        for role in ("heading", "copy")}
        per_section.append({
            "heading": supplied_text["heading"],
            "lines_required": len(section_lines),
            "lines_emitted": sum(1 for e in section_lines if e["fits"]),
            "characters_supplied": sum(len(t) for t in supplied_text.values()),
            "characters_emitted": sum(len(t) for t in emitted_text.values()),
        })

    required = max(0.0, y - SECTION_GAP_MM) if lines else 0.0
    supplied = sum(s["characters_supplied"] for s in per_section)
    emitted = sum(s["characters_emitted"] for s in per_section)
    fits = None if not measured else required <= available + 1e-9

    codes = []
    if fits is False:
        codes.append(COPY_EXCEEDS_PANEL)
    if not measured:
        codes.append(FIT_UNMEASURED)

    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "truncation": NO_TRUNCATION,
        "surface": SURFACE,
        "panel_mm": [round(width_mm, 3), round(height_mm, 3)],
        "column_mm": round(column, 3),
        "margin_mm": margin_mm,
        "size_pt": size_pt,
        "fine_size_pt": fine_size_pt,
        "leading_em": LEADING_EM,
        "block_gap_mm": round(block_gap_mm, 3),
        "line_height_mm": round(line_h, 4),
        "fit_measured": measured,
        "fits": fits,
        "copy_preserved": preserved,
        "whitespace": "runs of whitespace are collapsed to one space before "
                      "anything is counted, so a character count here is a "
                      "count of NORMALISED characters; copy_preserved is the "
                      "stronger claim, and it reconstructs the supplied text "
                      "from the emitted lines rather than counting them.",
        "height_required_mm": round(required, 3),
        "height_available_mm": round(available, 3),
        "overflow_mm": round(max(0.0, required - available), 3),
        "lines_required": len(lines),
        "lines_emitted": sum(1 for e in lines if e["fits"]),
        "characters_supplied": supplied,
        "characters_emitted": emitted,
        "characters_not_emitted": supplied - emitted,
        "sections": per_section,
        "lines": lines,
        "codes": codes,
        "measured_by": "apps.ire.back_panel.layout",
    }


# --- [his goal of 2026-10-12, (14): "BACK LABEL (for every palette and compact): Laid out like packaging, using the
# --- whole panel: clear hierarchy, the three languages as balanced blocks, never a squeezed list with empty space
# --- below."]
#: a palette's or compact's back as packaging: its languages side by side, PACK_GUTTER_MM apart — where each column
#: keeps at least PACK_MIN_COLUMN_MM, else stacked as before — each heading in bold capitals over its copy; the largest
#: size up to PACK_MAX_PT at which every column stands (never under the label's floor); each column's sections spread
#: down to the panel's foot, every column top to foot alike (PACK_SECTION_GAP_MAX_MM: no cap)
PACK_GUTTER_MM = 5.0
PACK_MIN_COLUMN_MM = 42.0
PACK_MAX_PT = 9.0
PACK_SECTION_GAP_MAX_MM = float("inf")
PACKAGING = "packaging — its languages side by side, balanced, each column spread to the panel's foot"


def packaging_layout(sections, width_mm: float, height_mm: float, *, size_pt: float, lowest_pt: float,
                     regular: str | None, bold: str | None, margin_mm: float, first_section: int = 0,
                     arabic_regular: str | None = None, arabic_bold: str | None = None) -> dict | None:
    """Every line of the copy laid as packaging (PACKAGING), or None where its languages are not side by side —
    one language only, or a column narrower than PACK_MIN_COLUMN_MM, or a copy no size from ``lowest_pt`` stands in:
    the caller lays it stacked, as before. The record is ``layout``'s, its lines each with their column's ``x_mm`` (from
    the panel's left) and ``column_mm``."""
    secs = list(sections or [])
    order, spans = [], {}
    for i, sec in enumerate(secs):
        lang = (sec or {}).get("lang")
        if lang not in spans:
            order.append(lang)
            spans[lang] = [i, i]
        spans[lang][1] = i
    n = len(order)
    if n < 2 or any(spans[a][0] > spans[b][0] for a, b in zip(order, order[1:])):
        return None
    if any(spans[lang][1] - spans[lang][0] + 1 != sum(1 for s in secs if (s or {}).get("lang") == lang)
           for lang in order):
        return None                                    # a language whose sections are not one run: stacked
    column = (width_mm - 2.0 * margin_mm - (n - 1) * PACK_GUTTER_MM) / n
    if column < PACK_MIN_COLUMN_MM:
        return None

    def headed(sec):
        # bold capitals over the copy — an Arabic heading as it is written
        sec = dict(sec or {})
        if sec.get("lang") != "ar" and sec.get("heading"):
            sec["heading"] = str(sec["heading"]).upper()
        return sec

    def lay(pt):
        cols = []
        for k, lang in enumerate(order):
            a, b = spans[lang]
            cols.append(layout([headed(s) for s in secs[a:b + 1]], column + 2.0 * margin_mm, height_mm, size_pt=pt,
                               regular=regular, bold=bold, margin_mm=margin_mm, first_section=first_section + a,
                               arabic_regular=arabic_regular, arabic_bold=arabic_bold))
        return cols

    pt = size_pt
    cols = lay(pt)
    while not all(c["fits"] is True for c in cols) and pt - 0.25 >= lowest_pt - 1e-9:
        pt = round(pt - 0.25, 2)
        cols = lay(pt)
    if not all(c["fits"] is True for c in cols):
        return None
    while pt + 0.25 <= PACK_MAX_PT + 1e-9:
        trial = lay(round(pt + 0.25, 2))
        if not all(c["fits"] is True for c in trial):
            break
        pt, cols = round(pt + 0.25, 2), trial
    lines, per_section = [], []
    for k, rec in enumerate(cols):
        slack = _room_under(rec) - BLOCK_RESERVE_MM          # never past the foot: its last line's descent kept in
        gaps = len(rec["sections"]) - 1
        extra = min(PACK_SECTION_GAP_MAX_MM, slack / gaps) if gaps > 0 and slack > 0 else 0.0
        first = min((e["section"] for e in rec["lines"]), default=0)
        x_mm = margin_mm + k * (column + PACK_GUTTER_MM)
        for e in rec["lines"]:
            lines.append(dict(e, baseline_mm=round(e["baseline_mm"] + extra * (e["section"] - first), 4),
                              x_mm=round(x_mm, 4), column_mm=round(column, 4), column=k))
        per_section += rec["sections"]
    out = dict(cols[0])
    supplied = sum(s["characters_supplied"] for s in per_section)
    emitted = sum(s["characters_emitted"] for s in per_section)
    out.update({"panel_mm": [round(width_mm, 3), round(height_mm, 3)], "column_mm": round(column, 3),
                "size_pt": pt, "lines": lines, "sections": per_section,
                "lines_required": len(lines), "lines_emitted": sum(1 for e in lines if e["fits"]),
                "characters_supplied": supplied, "characters_emitted": emitted,
                "characters_not_emitted": supplied - emitted, "fits": True, "codes": [],
                "copy_preserved": all(c["copy_preserved"] for c in cols),
                "fit_measured": all(c["fit_measured"] for c in cols),
                "height_required_mm": round(max(c["height_required_mm"] for c in cols), 3),
                "overflow_mm": 0.0, "layout": PACKAGING, "columns": n, "gutter_mm": PACK_GUTTER_MM,
                "languages": order, "measured_by": "apps.ire.back_panel.packaging_layout"})
    return out


def compose_back_panel(sections, zone, x: float, y: float, *,
                       size_pt: float | None = None,
                       methods_record: dict | None = None,
                       doc_metadata: dict | None = None,
                       ink=None,
                       # §BH49(c): the roles the panel's headings and copy carry. The defaults are the
                       # legacy words, so every exempt evidence surface that draws this panel is
                       # byte-identical; the product composer names heading/body, which the layer
                       # resolves to the theme faces and their pinned instances.
                       heading_role: str = "bold", copy_role: str = "regular",
                       first_section: int = 0, surface: str | None = None,
                       label_pt: float | None = None, fill_area: bool = False, packaging: bool = False,
                       qr_url: str | None = None):
    """``(Group|None, record)`` — the full-scale panel at ``(x, y)``.

    [His review of 127, 130, 131 and 132, 2026-10-15, C (7): "Every back label carries the full set (... QR)."]
    ``qr_url`` — the address the label's QR code carries: drawn as vector modules in the panel's foot, its right corner,
    the copy laid and fitted in the height above it (so the fit measures it); none drawn where the column is too narrow
    for a QR that scans (QR_MIN_MM), said in the record. Without it the panel is the panel it was.

    [His correction of 2026-10-07] copy that does not stand at its size shrinks whole, evenly, to ``label_floor_of``.
    ``label_pt`` — the size a caller's flow across several panels chose for the whole label (a jar's wrap label's two
    ends, ``compose_information_panels``): this panel is set at it and does not shrink on its own.

    [His answer of 2026-10-05, W10.] ``surface`` — the surface the panel prints on, BODY_BACK unless a caller names
    another (the back of a jar's wrap label is BODY_WRAP): its group carries that name and its copy that surface's own
    print floor. ``first_section`` — a later panel of one flow numbers its sections on from the panel before it.

    The group is None exactly when there is no zone to take true dimensions
    from; the record then carries ``NO_CONFIRMED_ZONE`` and says so, because a
    panel silently absent and a panel that fits are the same document to a
    reader who only counts what is drawn.

    The size the copy is set at is ``size_for_surface(methods_record,
    size_pt)`` and every returned record carries its ``size_source``, so a
    reader is never left to infer whether 5.0 pt was ``BODY_BACK``'s own
    capability-table floor or §W2(b)'s fallback standing in for one. §Z3(a):
    a table floor outranks a fallback, and the record that says which is the
    same one the typography axis reads.
    """
    from apps.ire.compose_container import TRUE_SCALE_SURFACE_PREFIX
    from apps.ire.graph import (Color, Group, LineTo, MoveTo, Path, Rect,
                                Stroke, TextRun)
    from apps.ire.text_metrics import resolve_metric_faces

    ink = ink if ink is not None else Color.from_hex("#2A2426")
    surface = surface or SURFACE
    size_pt, size_source = size_for_surface(methods_record, size_pt, surface)
    # [His correction of 2026-10-07: "when the label doesn't fit, the text gets SMALLER ... Shrink the whole label
    # evenly until everything fits, keeping its layout, spacing and order. Floor: 3 pt."] a back that does not stand at
    # its size shrinks whole — its copy, its headings, its ingredients and warnings together, a quarter point at a time
    # — to 3 pt, or to a confirmed print method's larger minimum (``label_floor_pt``: what that method can print, never
    # undercut — the executor's reading, his to veto); a size its caller named stays as named. The fine print stepped
    # down alone and then the narrower face was tried (his final goal, his second goal of 2026-10-06); both are gone.
    # MEASURED while building it: the step before this compared the whole size record to SIZE_FALLBACK, a dict to a
    # string, so it never ran — since b8f5a98 no container back ever stepped its fine print down — and where it would
    # have run, the machine's own proposed print method (5 pt, never confirmed) would have held every live back at its
    # size; ``label_floor_of`` reads the record's source and whether its method was confirmed.
    lowest = label_floor_of(size_source)
    if label_pt is not None:
        size_pt = lowest = float(label_pt)
    faces = resolve_metric_faces(doc_metadata)
    regular = (faces.get("regular") or (None, None))[0]
    bold = (faces.get("bold") or (None, None))[0]
    arabic_regular = arabic_bold = None
    # [his goal of 2026-10-06, item 8: "Fix the container back-label 1 mm safe-margin overrun: measure with the real font
    # outlines so it never crosses."] MEASURED: the container composer asked with no document, which the font layer reads
    # as the legacy surface — every line was measured in Noto Sans and drawn in the theme's faces (its copy in Poppins
    # Regular, its headings in Montserrat Bold, both wider). A document that adopts the theme measures each line in the
    # face of the role it is drawn in, and its Arabic in that role's Arabic face; an exempt one as before.
    from apps.ire.font_roles import ARABIC_ROLE_FOR, base_role, is_exempt, resolve_roles
    if not is_exempt(doc_metadata):
        roles = {"copy": base_role(copy_role), "heading": base_role(heading_role)}
        wanted = set(roles.values()) | {ARABIC_ROLE_FOR.get(r, "arabic-body") for r in roles.values()}
        drawn = resolve_roles(tuple(sorted(wanted)))["faces"]
        regular = (drawn.get(roles["copy"]) or faces.get("regular") or (None, None))[0]
        bold = (drawn.get(roles["heading"]) or faces.get("bold") or (None, None))[0]
        arabic_regular = (drawn.get(ARABIC_ROLE_FOR.get(roles["copy"], "arabic-body")) or (None, None))[0]
        arabic_bold = (drawn.get(ARABIC_ROLE_FOR.get(roles["heading"], "arabic-body")) or (None, None))[0]

    if zone is None:
        return None, {
            "schema_version": SCHEMA,
            "rule": RULE,
            "surface": SURFACE,
            "emitted": False,
            "size_source": size_source,
            "codes": [NO_CONFIRMED_ZONE],
            "reason": "no confirmed " + ZONE_TYPE + " — the panel has no true "
                      "dimensions to be drawn at, so none was drawn. §W1(b): "
                      "the typography axis stays UNMEASURED and blocking on "
                      + SURFACE + " until it exists.",
            "measured_by": "apps.ire.back_panel.compose_back_panel",
        }

    width, height = float(zone["width"]), float(zone["height"])
    margin, margin_source = zone_margin(zone)          # §BH54(b) (n): read from the zone's record, never typed
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] the QR's square in the foot, the copy above it
    qr_side = min(QR_MAX_MM, (width - 2 * margin) * QR_SHARE) if qr_url else None
    if qr_side is not None and qr_side < QR_MIN_MM:
        qr_side = None
    full_height = height
    if qr_side is not None:
        height = height - qr_side - QR_GAP_MM
    record = layout(sections, width, height, size_pt=size_pt,
                    regular=regular, bold=bold, margin_mm=margin, first_section=first_section,
                    arabic_regular=arabic_regular, arabic_bold=arabic_bold)
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] … and a product's back (``fill_area``) whose last line's
    # descent would hang into the safe margin (the fit counts to the baseline: MEASURED on a back carrying the full set,
    # its last line set at the foot stood 0.2 mm in the margin) steps down too — never under its floor
    while (record["fits"] is False or (fill_area and label_pt is None and record["fits"] is True and record["lines"]
                                       and _room_under(record) < 0)) \
            and size_pt - 0.25 >= lowest - 1e-9:
        size_pt = round(size_pt - 0.25, 2)
        record = layout(sections, width, height, size_pt=size_pt, regular=regular, bold=bold, margin_mm=margin,
                        first_section=first_section, arabic_regular=arabic_regular, arabic_bold=arabic_bold)
    # [his test finding on design 122's drawing, 2026-10-08, C: "using the whole area ... the three languages as balanced
    # blocks; never cramped at the bottom with empty space below"] a container's back (``fill_area``: the container
    # composer's information panels — never an evidence sheet's, nor a label a caller sized across panels; the dropper's
    # sheet holds every size still under its type-scale rule) grows while its whole copy stands, to GROW_MAX_PT, and the
    # height left is shared between its language blocks — the label filling its panel top to foot
    grew_from = size_pt
    # [his goal of 2026-10-12, (14)] a palette's or compact's back (``packaging``) as packaging, where its languages
    # stand side by side; else as below
    packed = (packaging_layout(sections, width, height, size_pt=grew_from, lowest_pt=lowest, regular=regular,
                               bold=bold, margin_mm=margin, first_section=first_section,
                               arabic_regular=arabic_regular, arabic_bold=arabic_bold)
              if packaging and label_pt is None and not is_exempt(doc_metadata) else None)
    if packed is not None:
        record, size_pt = packed, packed["size_pt"]
    elif fill_area and label_pt is None and not is_exempt(doc_metadata) and record["fits"] is True:
        langs = [(sec or {}).get("lang") for sec in sections or []]
        blocks = sum(1 for a, b in zip(langs, langs[1:]) if a != b)
        base_gap = BLOCK_GAP_MIN_MM if blocks else 0.0

        def lay(pt, gap):
            return layout(sections, width, height, size_pt=pt, regular=regular, bold=bold, margin_mm=margin,
                          first_section=first_section, arabic_regular=arabic_regular, arabic_bold=arabic_bold,
                          block_gap_mm=gap, column_share=GROW_WIDTH_SHARE)
        faces_of = {("en", "heading"): bold, ("en", "copy"): regular, ("ar", "heading"): arabic_bold or bold,
                    ("ar", "copy"): arabic_regular or regular}
        start = lay(size_pt, base_gap)
        if start["fits"] is True and lines_within(start, faces_of):
            record = start
            while size_pt + 0.25 <= GROW_MAX_PT + 1e-9:
                trial = lay(round(size_pt + 0.25, 2), base_gap)
                if trial["fits"] is not True or not lines_within(trial, faces_of) or _room_under(trial) < 0.0:
                    break
                size_pt, record = round(size_pt + 0.25, 2), trial
            slack = _room_under(record)
            if blocks and slack > BLOCK_RESERVE_MM:
                spread = lay(size_pt, min(BLOCK_GAP_MAX_MM, base_gap + (slack - BLOCK_RESERVE_MM) / blocks))
                if spread["fits"] is True:             # kept only where it still stands — never laid past its foot
                    record = spread
    record = {**record, "grown_from_pt": grew_from} if size_pt != grew_from else record
    if qr_url:
        # the panel is its zone's whole height; the copy's height is what is left above the QR
        record = {**record, "panel_mm": [round(width, 3), round(full_height, 3)],
                  "qr": {"url": qr_url, "drawn": qr_side is not None,
                         **({"side_mm": round(qr_side, 3)} if qr_side is not None else
                            {"why": "the column is narrower than a QR that scans needs (%g mm)" % QR_MIN_MM})}}
    record = {**record, "surface": surface, "size_source": size_source, "margin_source": margin_source,
              # [his goal of 2026-10-06, item 8] the faces each line was measured in — the ones it is drawn in
              "measured_in": {"copy": regular, "heading": bold, "arabic_copy": arabic_regular,
                              "arabic_heading": arabic_bold}}
    if not record["fit_measured"]:
        return None, {**record, "emitted": False,
                      "zone_id": zone.get("zone_id"),
                      "reason": "the face this copy is set in could not be "
                                "measured, so the line breaks the emitted "
                                "document will have are not known. Drawing "
                                "the panel anyway would let a guessed layout "
                                "decide which copy the panel's edge excludes."}

    kids: list = [Rect(name="back-panel-boundary", x=x, y=y, w=width,
                       h=full_height,
                       stroke=Stroke(color=ink, width_mm=0.2, opacity=0.55))]
    seen_section = seen_column = None
    for entry in record["lines"]:
        if not entry["fits"]:
            continue
        # [his goal of 2026-10-12, (14)] a packaging back's line in its own column; else across the panel
        left = x + entry.get("x_mm", margin)
        right = left + entry["column_mm"] if "column_mm" in entry else x + width - margin
        if seen_section is not None and entry["section"] != seen_section and entry.get("column") == seen_column:
            ry = y + margin + entry["baseline_mm"] \
                - entry.get("size_pt", size_pt) * MM_PER_PT * LEADING_EM - SECTION_GAP_MM * 0.55
            kids.append(Path(
                name=f"back-panel-{entry['section']}-rule",
                segments=[MoveTo(x=left, y=ry),
                          LineTo(x=right, y=ry)],
                stroke=Stroke(color=ink, width_mm=0.08, opacity=0.35)))
        seen_section, seen_column = entry["section"], entry.get("column")
        arabic = entry.get("lang") == "ar"      # [his final goal, A] set from the column's right edge
        role = heading_role if entry["role"] == "heading" else copy_role
        kids.append(TextRun(
            name=f"back-panel-{entry['section']}-{entry['role']}"
                 f"-{entry['order']}",
            text=entry["text"], x=right if arabic else left,
            y=y + margin + entry["baseline_mm"], size_pt=entry.get("size_pt", size_pt),
            color=ink, font=role,
            align="right" if arabic else "left"))

    if qr_side is not None:
        from apps.ire.graph import Barcode
        kids.append(Barcode(name="back-panel-qr", symbology="qr", value=qr_url, x=x + width - margin - qr_side,
                            y=y + full_height - margin - qr_side, w=qr_side, h=qr_side))
    # deliberately NO clip. Only lines the panel holds are drawn, so a clip
    # would cut nothing — and a clip path over live type is what
    # ``container_typography_metrics`` clip findings exist to catch.
    group = Group(name=f"{TRUE_SCALE_SURFACE_PREFIX}{surface}",
                  role="decoration", children=kids)
    return group, {**record, "emitted": True, "zone_id": zone.get("zone_id"),
                   "origin_mm": [round(x, 3), round(y, 3)]}


#: [his answer of 2026-10-05, W10: "a jar's back copy goes on the back of its wrap label; with no wrap, on the base
#: label. Never nowhere."] where a design's back copy prints, in his order
WHERE_BACK_ZONE = "the back print zone"
WHERE_WRAP_BACK = "the back of the wrap label"
WHERE_BASE_LABEL = "the base label"
#: no back print zone, no wrap label reaching the back, no base label: refused by name, never drawn nowhere
NO_SURFACE = "CONTAINER_BACK_COPY_HAS_NO_SURFACE"
#: CHOSEN: a wrap label's end narrower than this behind the body holds no column of copy, and is not used
WRAP_END_MIN_MM = 10.0
#: CHOSEN: the gap between the two ends' panels as the sheet shows them side by side
PANEL_GAP_MM = 6.0
_BASE_SURFACES = ("BOTTOM", "BASE_BOTTOM")
#: [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] CHOSEN: the back's QR — a share of its column, no larger than
#: the carton sticker's own, no smaller than a phone reads at arm's length; the gap between it and the copy above
QR_SHARE = 0.5
QR_MAX_MM = 12.0
QR_MIN_MM = 7.0
QR_GAP_MM = 1.0


__all__ = ["SCHEMA", "COPY_EXCEEDS_PANEL", "NO_CONFIRMED_ZONE",
           "FIT_UNMEASURED", "SURFACE", "ZONE_TYPE", "RULE", "NO_TRUNCATION",
           "SIZE_TABLE", "SIZE_FALLBACK", "SIZE_CALLER", "SIZE_AMBIGUOUS",
           "SIZE_HELD_UP_BY_FALLBACK", "size_for_surface",
           "LABEL_FLOOR_PT", "label_floor_pt", "label_floor_of",
           "MARGIN_FROM_ZONE", "MARGIN_LEGACY", "zone_margin",
           "back_zone", "wrap_lines", "layout", "compose_back_panel"]
