"""§BH66(a) — ON A FACE, THE CONCEPT'S OWN ARRANGEMENT GOVERNS: where its words put each element, read and laid out.

OWNER RULED 2026-09-23 (§BH66(a), ``OWNER_BLOCKER_CLEARANCE.md:23254``, LIVE): "§AU1 governs bottle, jar and tube
fronts as it always has. It does NOT govern a compact lid, and it does not govern any future form whose primary
surface is its face — a palette, a case, a box lid. On such a surface the concept's own arrangement governs, inside
two limits that stand: the mark's clear space on every side (§AY2), and no motif field as a ground behind the mark
(§BA / C12). Draw the window, the ring, the Arabic line and their finishes where the concept puts them, and refuse by
name only what those two limits actually forbid."

WHICH FORMS HAVE A FACE is declared on each form (``archetypes.primary_surface_of``), never inferred here.

THE READER WAS MEASURED BEFORE IT WAS WRITTEN. Every face-form concept on record — tasks 84, 88 and 89, nine
variations in three families: a petal WINDOW, a full-face VEIL field, an EDGE-led constellation — was read for the
words it uses to say where the mark, the name, the Arabic line and the motif sit. Those words are the tables below.
A position word belongs to the nearest thing named BEFORE it in its clause (the window, the motif and a claim line
count as things, so "category copy lower-right" never moves the name); the typography sentence is read first. Every
element's place is recorded with the words that decided it, and an element the words do not place is DEFAULTED and
says so.

  THE SLOTS, top to bottom:   top · upper · above the window · middle · below the window · lower · bottom
  THE ALIGNMENTS:             left · centre · right

  A pair told "above and below the window" in one breath ("EN + AR, both … stacked above and below the petal
  window") stays together ABOVE it: the reading the owner saw drawn as the concept's own arrangement in the §BH65(c)
  report and ruled on. The name above and the Arabic below is taken only where the words give each its own place
  (88A: "left-aligned above window" … "left-aligned below window").

THE TWO LIMITS, AND THE ONLY REFUSALS.
  1. The mark's clear space — 1.0x its measured cap height (§AU3, the ordering §AY2) — holds on EVERY side: no other
     element's ink, the ring included, enters it. The layout keeps it by construction and records the margins.
  2. No motif field as a ground behind the mark — §BH66(a)'s own words, stricter than §BA's heading and §BB2's
     condition and applied by his principle that the later governs (recorded at §BH66). A motif element whose box
     meets the mark's clear space is REFUSED, counted and named.

WHAT IS NOT A REFUSAL. Room: an element the zone cannot hold is NOT_PLACED with its millimetres. Rotation: type the
words turn ("rotated 90°", "vertical spine") is set LEVEL at the edge the words name and recorded APPROXIMATED. The
emitter can turn a run, but the brand-usage instrument reads every run as a level band across the whole page
(``container_brand_usage._ink_box``), so a turned run beside the mark would be measured crossing a clear space it
never enters.

THE LAYOUT'S NUMBERS, EACH THE EXECUTOR'S AND EACH RECORDED WITH WHAT IT REPLACED.
  GAP     one em of the name's size between stacked elements, and between the type and the ring.
  THIRD   the mark's block — the mark with its clear space above and below — takes at most a third of the face's
          height: 84A's own words, "a vertically stacked three-zone lid". A larger mark SHRINKS toward the 12.0 mm
          print floor (§AY2's step 2), never below it. Rejected: the mark at the composer's 0.6 of the backbone's
          label zone — 50.16 mm on task 89's lid, its block 28.4 mm of 62.1 — a width derived for a bottle's narrow
          label and quietly governing a lid, the class of error §BH66(a) names.
  WINDOW  takes the height the two stacks leave, never under ``WINDOW_MIN_MM`` and never wider than
          ``WINDOW_ASPECT_MAX`` times its height: a centrepiece, not the strip §BH65(c)3 fitted above a mark.
  REGION  a motif with no window sits where its words put it — the whole face, a vertical band, or the corner it
          is led from (``REGION_SHARE`` of the face each way).

Pure: no Django, no ORM, no drawing. The composer draws what this returns.
"""
from __future__ import annotations

import re

from apps.ire import composer_vocabulary as V

SCHEMA = "container_concept_face/1.0"
GOVERNED_BY = "§BH66(a)"

TOP, UPPER, ABOVE_WINDOW, MIDDLE, BELOW_WINDOW, LOWER, BOTTOM = (
    "top", "upper", "above_window", "middle", "below_window", "lower", "bottom")
SLOT_ORDER = (TOP, UPPER, ABOVE_WINDOW, MIDDLE, BELOW_WINDOW, LOWER, BOTTOM)
LEFT, CENTRE, RIGHT = "left", "centre", "right"
MARK, NAME, NAME_AR = "mark", "name", "name_ar"
#: [his answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks for"] the
#: record's shade on the face — its English and its Arabic side by side on one line at the face's foot, where the
#: concept's picture shows a shade line of its own the place it takes and the size it is set at, never its words
SHADE = "shade"
#: the kinds of line the vision step reads that are not the face's own elements: the lowest of them on the face is the
#: concept's shade line (91's "03 Medium Beige", read other_text; 110's "02 BEIGE | PRESSED POWDER", read descriptor)
SHADE_LINE_KINDS = ("other_text", "descriptor")
#: a shade line keeps one em of ITS OWN size from its neighbour — the name's em is a headline's air, not a small
#: line's (the executor's number, new)
SHADE_GAP_EM = 1.0

GAP_EM = 1.0
THIRD = 1.0 / 3.0
WINDOW_MIN_MM = 8.0            # the floor §BH65(c)3 set for a window
WINDOW_ASPECT_MAX = 1.7
WINDOW_WIDTH_SHARE = 0.62      # §BH65(c)3's own share of the region's width, unchanged
REGION_SHARE = 0.62
MARK_FLOOR_MM = 12.0           # container_brand_usage.MINIMUM_WIDTH_MM_PRINT, the §AU3 print floor
#: a point in millimetres — the name the unit analyser reads as the conversion it is (§Z1(a))
MM_PER_PT = 25.4 / 72.0
#: a run's ink from its baseline, in ems: the ruled front's own model (compose_container._ink_extent)
INK_ABOVE_EM, INK_BELOW_EM = 0.75, 0.25
#: Naskh reaches further below its baseline than a Latin capital — the Arabic line's ink below, in ems
AR_INK_BELOW_EM = 0.45

_AR_CHARS = "[%s-%s]" % (chr(0x0600), chr(0x06FF))
_FIELDS = ("typography_signature", "composition_signature", "decoration_zone_signature")
_MENTIONS = (
    (MARK, r"bbrose|wordmark|lockup|\blogo\b|\bseal\b|hallmark|brand mark"),
    ("other", r"category (copy|word)|claims?|\bcopy\b|descriptor|side band|'[^']*/[^']*'|'palette'"),
    (NAME_AR, r"arabic (product )?names?|naskh names?|arabic|naskh|kufi|\(ar\)|" + _AR_CHARS + "+"),
    (NAME, r"product names?|\bnames?\b|name tiers?|display type|type block|type column|headline|\(en\)|english|"
           r"\btypography\b|\btype\b|'[a-z][a-z ]+'"),
    ("window", r"window|cartouche|medallion"),
    ("motif", r"veil|motif|constellation|strands|petals?|droplets?|dewdrops?|bloom|\bfield\b"),
)
_RELATIVE = (
    (ABOVE_WINDOW, r"above and below (the |its )?([\w-]+ )?(window|cartouche|medallion)|"
                   r"above (the |its )?([\w-]+ )?(window|cartouche|medallion)"),
    (BELOW_WINDOW, r"(below|beneath|under) (the |its )?([\w-]+ )?(window|cartouche|medallion)|below cent(re|er)"),
)
_VERTICAL = (
    (TOP, r"top rim|pins the top|crowns?|top[- ](left|right|centre|center)|at the top|\btop\b|upper quarter|"
          r"upper third|head of"),
    (UPPER, r"upper[- ](centre|center|right|left)|upper half|\bupper\b"),
    (LOWER, r"lower third|lower[- ](centre|center|left|right)|lower half|\blower\b"),
    (BOTTOM, r"anchors? (the )?base|\bbase\b|bottom[- ](centre|center|left|right)|\bbottom\b|\bfoot\b"),
    (MIDDLE, r"mid[- ](right|left)|\bmid\b|\bmiddle\b"),
)
_HORIZONTAL = (
    (LEFT, r"left[- ]aligned|flush[- ]left|left[- ](edge|column|rim)|\bleft\b"),
    (RIGHT, r"right[- ]aligned|flush[- ]right|right[- ](edge|column|rim)|\bright\b"),
    (CENTRE, r"centred|centered|\bcentre\b|\bcenter\b|\bacross\b"),
)
#: a product name is matched as its LEADING PHRASE ("rose glow", "focus") — a lone first word that is also a colour
#: ("rose" in "deep rose") is never taken for the name
_COLOUR_WORDS = frozenset(("rose", "gold", "pink", "blush", "nude", "cream", "pearl", "coral", "peach", "ivory",
                           "plum", "berry", "bronze", "champagne", "copper", "silver", "white", "black", "red"))
_PAIR_RE = re.compile(r"(?<![a-z])(both|pair)(?![a-z])")
_BOTH_WAYS_RE = re.compile(r"above and below")
_ROTATED_RE = re.compile(r"(?<![a-z])(rotated|vertical (type )?spine|type spine|vertical type)(?![a-z])")
_SCALE_RE = re.compile(r"at (\d{2,3})\s?% (cap height|scale|size)")
_CLAUSE_SPLIT = re.compile(r"\s*(?:;|\s/\s(?!" + _AR_CHARS + r")|\s—\s|:\s)\s*")
_REGION = (
    ("full", r"full[- ]bleed|full[- ]face|entire lid face|entire lid|across the (whole|entire) (lid|face)|"
             r"fill(s)? the entire|all[- ]over|ambient field"),
    ("band_left", r"(centre|center)[- ]left vertical band|left vertical band"),
    ("band_right", r"(centre|center)[- ]right vertical band|right vertical band"),
    ("band_centre", r"full[- ]height central|central vertical|vertical band"),
    ("corner_lower_left", r"lower[- ]left"),
    ("corner_lower_right", r"lower[- ]right"),
    ("corner_upper_left", r"upper[- ]left"),
    ("corner_upper_right", r"upper[- ]right"),
)


def _clauses(structured: dict) -> list[tuple[str, str]]:
    out = []
    for field in _FIELDS:
        text = V.normalise(str(structured.get(field) or ""))
        for clause in _CLAUSE_SPLIT.split(text):
            if clause.strip():
                out.append((field, clause.strip()))
    return out


def _mask(text: str, spans) -> str:
    chars = list(text)
    for a, b in spans:
        for i in range(a, b):
            chars[i] = " "
    return "".join(chars)


def _parse(clause: str, name_words: tuple[str, ...]) -> list[dict]:
    """Each thing this clause names, with the position words that belong to it: a word belongs to the nearest thing
    named BEFORE it, or to the nearest after it when nothing precedes. A compound ("top-left", "bottom-center")
    carries both of its axes."""
    words, spans = [], []
    for slot, rx in _RELATIVE:
        for m in re.finditer(rx, clause):
            if not any(a <= m.start() < b for a, b in spans):
                words.append((m.start(), "v", slot, m.group(0)))
                spans.append(m.span())
    for slot, rx in _VERTICAL:
        for m in re.finditer(rx, clause):
            if any(a <= m.start() < b for a, b in spans):
                continue
            words.append((m.start(), "v", slot, m.group(0)))
            side = re.search(r"(left|right|centre|center)$", m.group(0))
            if side:
                words.append((m.start(), "h", {"left": LEFT, "right": RIGHT}.get(side.group(1), CENTRE),
                              m.group(0)))
            spans.append(m.span())
    for align, rx in _HORIZONTAL:
        for m in re.finditer(rx, _mask(clause, spans)):
            words.append((m.start(), "h", align, m.group(0)))
            spans.append(m.span())
    for m in _ROTATED_RE.finditer(clause):
        words.append((m.start(), "r", True, m.group(0)))
    for m in _SCALE_RE.finditer(clause):
        words.append((m.start(), "s", round(int(m.group(1)) / 100.0, 2), m.group(0)))
    taken = _mask(clause, spans)
    mentions = []
    patterns = list(_MENTIONS)
    if name_words:
        patterns.insert(3, (NAME, "|".join(r"\b%s\b" % r"[\s-]+".join(map(re.escape, p.split()))
                                           for p in name_words)))
    for kind, rx in patterns:
        for m in re.finditer(rx, taken):
            if not any(a <= m.start() < b for a, b, _k in mentions):
                mentions.append((m.start(), m.end(), kind))
    mentions.sort()
    if not mentions:
        return []
    placed = {}
    for pos, axis, value, text in sorted(words, key=lambda w: w[0]):
        before = [mm for mm in mentions if mm[0] <= pos]
        target = before[-1] if before else min(mentions, key=lambda mm: abs(mm[0] - pos))
        row = placed.setdefault(target, {"v": [], "h": [], "r": [], "s": []})
        row[axis].append((value, text))
    out = [{"kind": k[2], "at": k[0], **r} for k, r in placed.items()]
    for a, _b, kind in mentions:
        if kind in (NAME, NAME_AR) and not any(r["at"] == a for r in out):
            out.append({"kind": kind, "at": a, "v": [], "h": [], "r": [], "s": []})
    return sorted(out, key=lambda r: r["at"])


def _default_slot(key, layout):
    if key == MARK:
        return BELOW_WINDOW if layout == "window" else BOTTOM
    return ABOVE_WINDOW if layout == "window" else UPPER


def read(structured: dict | None, *, layout: str | None, has_arabic: bool, product_name: str = "",
         has_shade: bool = False) -> dict:
    """``container_concept_face/1.0``'s reading: where the concept's own words put the mark, the name and the Arabic
    line on a face, and where its motif sits. ``layout`` is the §BH65(c)3 plan's (window / field / edge / None);
    ``has_arabic`` says whether the product record holds an Arabic name to set; the product name's own words count
    as the name ("FOCUS in tall classical serif ... across upper third"). ``has_shade`` says whether the record holds
    the one shade a lid draws: it is set at the face's foot, the last of the stack [his answer of 2026-09-29, (4)]."""
    keys = [MARK, NAME] + ([NAME_AR] if has_arabic else [])
    out = {"schema_version": SCHEMA, "governed_by": GOVERNED_BY, "layout": layout, "region": None,
           "elements": {}, "order": [], "approximated": [], "state": "NO_STRUCTURED_RECORD"}
    if not structured:
        return out
    out["state"] = "READ"
    words = re.findall(r"[a-z]{2,}", (product_name or "").lower())
    name_words = tuple(" ".join(words[:n]) for n in range(len(words), 0, -1)
                       if not (n == 1 and words[0] in _COLOUR_WORDS))
    found = {k: {"v": None, "h": None, "r": None, "scale": None, "from": [], "clause": None} for k in keys}
    first_seen = {}
    for ci, (field, clause) in enumerate(_clauses(structured)):
        rows = _parse(clause, name_words)
        texts = [r for r in rows if r["kind"] in (NAME, NAME_AR)]
        pair = len({r["kind"] for r in texts}) == 2 and bool(_PAIR_RE.search(clause))
        shared = {axis: next((w for r in texts for w in r[axis]), None) for axis in ("v", "h")} if pair else {}
        for r in rows:
            k = r["kind"]
            if k not in found:
                continue
            first_seen.setdefault(k, (ci, r["at"]))
            f = found[k]
            # a list of places for one mention ("type elements occupy edge zones (left spine, lower centre, upper
            # band)") places nothing: several different slots, or several different sides, are not a placement
            own_v = r["v"] if len({w[0] for w in r["v"]}) == 1 else []
            own_h = r["h"] if len({w[0] for w in r["h"]}) == 1 else []
            v = own_v[0] if own_v else shared.get("v")
            h = own_h[0] if own_h else shared.get("h")
            if f["v"] is None and v is not None:
                if v[0] == ABOVE_WINDOW and _BOTH_WAYS_RE.search(v[1]):
                    v = (ABOVE_WINDOW, v[1] + " (a pair told this in one breath stays together above it)"
                         if pair else v[1] + " (read: above it)")
                f["v"] = v
                f["from"].append(field)
                f["clause"] = f["clause"] or clause[:160]
            if f["h"] is None and h is not None:
                f["h"] = h
                f["from"].append(field)
            if f["r"] is None and r["r"] and k in (NAME, NAME_AR):
                f["r"] = r["r"][0][1]
            if k == NAME_AR and f["scale"] is None and r["s"]:
                f["scale"] = r["s"][0]
    elements = {}
    for k in keys:
        f = found[k]
        why = [w[1] for w in (f["v"], f["h"]) if w]
        slot = f["v"][0] if f["v"] else None
        if f["r"]:
            out["approximated"].append({"element": k, "words": f["r"],
                                        "drawn_as": "set level at the edge the words name — the brand-usage "
                                                    "instrument reads every run as a level band"})
            if slot is None:
                slot, why = MIDDLE, why + ["rotated type runs the face's height: middle"]
        row = {"slot": slot, "align": f["h"][0] if f["h"] else CENTRE, "why": why,
               "from": sorted(set(f["from"])), "clause": f["clause"]}
        if f["scale"]:
            row["scale"], row["why"] = f["scale"][0], row["why"] + [f["scale"][1]]
        if slot is None:
            row["slot"] = _default_slot(k, layout)
            row["why"].append("no vertical word — DEFAULTED")
        elements[k] = row
    if NAME_AR in elements and not found[NAME_AR]["v"] and not found[NAME_AR]["r"]:
        # the Arabic line is the name in its other language: with no height word of its own it shares the name's
        # slot, keeping its own side when the words give one
        own_side = found[NAME_AR]["h"]
        elements[NAME_AR] = dict(elements[NAME], why=(["no height word of its own — the name's slot"]
                                                       + ([own_side[1]] if own_side else [])))
        elements[NAME_AR]["align"] = own_side[0] if own_side else elements[NAME]["align"]
        elements[NAME_AR].pop("scale", None)
        if found[NAME_AR]["scale"]:
            elements[NAME_AR]["scale"] = found[NAME_AR]["scale"][0]
    for k, row in elements.items():
        if layout != "window" and row["slot"] in (ABOVE_WINDOW, BELOW_WINDOW):
            row["why"] = row["why"] + ["no window is drawn — read as %s"
                                       % (UPPER if row["slot"] == ABOVE_WINDOW else LOWER)]
            row["slot"] = UPPER if row["slot"] == ABOVE_WINDOW else LOWER
        if layout == "window" and row["slot"] == MIDDLE:
            row["why"] = row["why"] + ["the window holds the middle — read as above it"]
            row["slot"] = ABOVE_WINDOW
    out["order"] = sorted(keys, key=lambda k: first_seen.get(k, (9999, 9999)))
    out["elements"] = elements
    if has_shade:
        # [his answer of 2026-09-29, (4)] the record's shade: the face's foot, the last of its stack; the concept's
        # own shade line, where its picture shows one, moves it (``follow_concept_layout``) — its words never
        elements[SHADE] = {"slot": BOTTOM, "align": CENTRE, "why": ["the record's shade — the face's foot"],
                           "from": [], "clause": None}
        out["order"].append(SHADE)
    from apps.pipeline.direction_signature import strip_negated_spans
    text = strip_negated_spans(" . ".join(V.normalise(str(structured.get(f) or ""))
                                          for f in ("decoration_zone_signature", "composition_signature")))
    if layout == "window":
        out["region"] = {"kind": "window", "why": ["the plan's window"]}
    elif layout:
        for kind, rx in _REGION:
            m = re.search(rx, text)
            if m:
                out["region"] = {"kind": kind, "why": [m.group(0)]}
                break
        if out["region"] is None:
            out["region"] = {"kind": "full" if layout == "field" else "corner_lower_left",
                             "why": ["no region words — the plan's %s" % layout]}
    return out


def mark_width(content_h: float, composer_w: float, aspect: float, cap_ratio: float) -> tuple[float, str]:
    """THIRD: the mark's block takes at most a third of the face; the composer's mark shrinks toward the §AU3 print
    floor to meet it (§AY2's step 2), never below the floor. Returns (width mm, the reason)."""
    block_ratio = aspect * (1.0 + 2.0 * cap_ratio)      # the block's height per mm of width
    cap = content_h * THIRD / block_ratio
    if composer_w <= cap:
        return composer_w, "the composer's mark, %.2f mm: its block fits a third of the face" % composer_w
    if cap < MARK_FLOOR_MM:
        return MARK_FLOOR_MM, "a third of the face is under the 12.0 mm print floor: held at the floor"
    return cap, ("shrunk from the composer's %.2f mm so its block is a third of the face (§AY2 step 2; floor "
                 "12.0 mm)" % composer_w)


def _text_block(lines: int, size_pt: float, step_mm: float, below_em: float) -> tuple[float, float]:
    """(ink height, the first baseline's drop from the ink top) of ``lines`` lines at ``size_pt``."""
    em = size_pt * MM_PER_PT
    return (INK_ABOVE_EM * em + (lines - 1) * step_mm + below_em * em), INK_ABOVE_EM * em


def layout(reading: dict, *, box: tuple, ring_mm: float | None, name_lines: list, name_size_pt: float,
           name_step_mm: float, ar_text: str | None, ar_size_pt: float, mark_aspect: float | None,
           mark_cap_ratio: float, composer_mark_w: float, shade_size_pt: float | None = None,
           shade_has_arabic: bool = False) -> dict:
    """The face laid out inside ``box`` = (x, y, w, h): the confirmed zone less its safe margin. ``ring_mm`` is the
    ring's stroke when the concept asks for one (None otherwise): its PATH is inset one stroke so its ink stays inside
    the safe area, the mark's clear space stays inside its inner edge, and the type keeps one GAP from it. Returns
    every element's geometry and the record of what could not be placed and why. The composer draws exactly this."""
    x0, y0, w, h = box
    em = name_size_pt * MM_PER_PT
    gap = GAP_EM * em
    rec = {"box": [round(v, 3) for v in box], "ring": None, "gap_mm": round(gap, 3), "placed": {},
           "not_placed": [], "collisions": [], "rules": {"gap": "one em of the name, %.3f mm" % gap}}
    if ring_mm:
        # the ring's PATH sits one stroke inside the safe line, so its ink's outer edge is half a stroke clear of it
        # and no rounding of a placement record can carry it over; the mark's clear space starts one stroke inside
        # the path, half a stroke clear of the ring's inner edge
        rec["ring"] = [round(v, 3) for v in (x0 + ring_mm, y0 + ring_mm, w - 2 * ring_mm, h - 2 * ring_mm)]
        mark_reg = (x0 + 2 * ring_mm, y0 + 2 * ring_mm, w - 4 * ring_mm, h - 4 * ring_mm)
        text_reg = (mark_reg[0] + gap, mark_reg[1] + gap, mark_reg[2] - 2 * gap, mark_reg[3] - 2 * gap)
    else:
        mark_reg = text_reg = (x0, y0, w, h)
    rec["regions"] = {"text": [round(v, 3) for v in text_reg], "mark": [round(v, 3) for v in mark_reg]}
    els = reading["elements"]
    blocks = {}
    if name_lines:
        hgt, drop = _text_block(len(name_lines), name_size_pt, name_step_mm, INK_BELOW_EM)
        blocks[NAME] = {"h": hgt, "drop": drop}
    if ar_text and NAME_AR in els:
        hgt, drop = _text_block(1, ar_size_pt, 0.0, AR_INK_BELOW_EM)
        blocks[NAME_AR] = {"h": hgt, "drop": drop}
    shade_gap = None
    if shade_size_pt and SHADE in els:
        # [his answer of 2026-09-29, (4)] the record's shade: one line, its Arabic reaching as far below as the
        # Arabic name does
        hgt, drop = _text_block(1, shade_size_pt, 0.0, AR_INK_BELOW_EM if shade_has_arabic else INK_BELOW_EM)
        blocks[SHADE] = {"h": hgt, "drop": drop}
        shade_gap = SHADE_GAP_EM * shade_size_pt * MM_PER_PT
        rec["shade_gap_mm"] = round(shade_gap, 3)
        rec["rules"]["shade_gap"] = "one em of the shade line's own size, %.3f mm" % shade_gap
    mark = None
    if mark_aspect:
        mw, why = mark_width(mark_reg[3], composer_mark_w, mark_aspect, mark_cap_ratio)
        mh = mw * mark_aspect
        clear = mh * mark_cap_ratio
        mark = {"w": mw, "h": mh, "clear": clear}
        blocks[MARK] = {"h": mh + 2 * clear, "drop": clear}
        rec["rules"]["mark"] = why
    clear = mark["clear"] if mark else 0.0

    def reg(k):
        return mark_reg if k == MARK else text_reg

    def sep(a, b):
        """Ink-to-ink air between two neighbours: one GAP, of which the mark's own clear space counts — beside the
        shade line, one em of its own size."""
        room = shade_gap if SHADE in (a, b) and shade_gap is not None else gap
        return max(0.0, room - clear) if MARK in (a, b) else room

    order = [k for k in reading["order"] if k in blocks]
    by_slot = {s: [k for k in order if els[k]["slot"] == s] for s in SLOT_ORDER}
    tops = {}
    if reading.get("layout") == "window":
        above = by_slot[TOP] + by_slot[UPPER] + by_slot[ABOVE_WINDOW]
        below = by_slot[BELOW_WINDOW] + by_slot[LOWER] + by_slot[BOTTOM]
        end, prev = None, None
        for k in above:
            top = reg(k)[1] if prev is None else max(end + sep(prev, k), reg(k)[1])
            tops[k], end, prev = top, top + blocks[k]["h"], k
        above_end, above_last = (end if end is not None else text_reg[1]), prev
        start, prev = None, None
        for k in reversed(below):
            bottom = reg(k)[1] + reg(k)[3]
            if prev is not None:
                bottom = min(start - sep(k, prev), bottom)
            tops[k], start, prev = bottom - blocks[k]["h"], bottom - blocks[k]["h"], k
        below_start, below_first = (start if start is not None else text_reg[1] + text_reg[3]), prev
        wy = above_end + (sep(above_last, "window") if above_last else 0.0)
        wh = below_start - (sep("window", below_first) if below_first else 0.0) - wy
        if wh >= WINDOW_MIN_MM:
            ww = min(text_reg[2] * WINDOW_WIDTH_SHARE, wh * WINDOW_ASPECT_MAX)
            rec["placed"]["window"] = [round(text_reg[0] + (text_reg[2] - ww) / 2.0, 3), round(wy, 3),
                                       round(ww, 3), round(wh, 3)]
            rec["rules"]["window"] = ("the %.2f mm the stacks leave; %.2f mm wide — at most %.2f of the face's width "
                                      "and %.1fx its height" % (wh, ww, WINDOW_WIDTH_SHARE, WINDOW_ASPECT_MAX))
        else:
            rec["not_placed"].append({"element": "window", "room_mm": round(wh, 3),
                                      "reason": "the stacks above and below leave %.3f mm, under the %.1f mm window "
                                                "floor" % (wh, WINDOW_MIN_MM)})
    else:
        # bands: the top and the bottom slots hold the edges, the others their quarter lines, never overlapping
        quarter = {TOP: 0.0, UPPER: 0.25, MIDDLE: 0.5, LOWER: 0.75, BOTTOM: 1.0}
        end, prev = None, None
        for s in (TOP, UPPER, MIDDLE):
            for k in by_slot[s]:
                rx, ry, rw, rh = reg(k)
                want = ry + quarter[s] * rh - (0.0 if s == TOP else blocks[k]["h"] / 2.0)
                floor_ = ry if prev is None else end + sep(prev, k)
                tops[k] = max(want, floor_)
                end, prev = tops[k] + blocks[k]["h"], k
        start, prev = None, None
        for s in (BOTTOM, LOWER):
            for k in reversed(by_slot[s]):
                rx, ry, rw, rh = reg(k)
                want = ry + quarter[s] * rh - (blocks[k]["h"] if s == BOTTOM else blocks[k]["h"] / 2.0)
                ceiling = ry + rh - blocks[k]["h"] if prev is None else start - sep(k, prev) - blocks[k]["h"]
                tops[k] = min(want, ceiling)
                start, prev = tops[k], k
        region = (reading.get("region") or {}).get("kind")
        if region:
            rx, ry, rw, rh = text_reg
            if region == "full":
                box_ = (rx, ry, rw, rh)
            elif region.startswith("band_"):
                bw = rw * REGION_SHARE
                bx = rx if region == "band_left" else (rx + rw - bw if region == "band_right"
                                                       else rx + (rw - bw) / 2.0)
                box_ = (bx, ry, bw, rh)
            else:
                cw, ch = rw * REGION_SHARE, rh * REGION_SHARE
                box_ = (rx if region.endswith("left") else rx + rw - cw,
                        ry + rh - ch if "lower" in region else ry, cw, ch)
            rec["placed"]["motif_region"] = [round(v, 3) for v in box_]
            rec["rules"]["motif_region"] = "%s — %s" % (region, ", ".join(reading["region"]["why"]))
    spans = []
    for k, top in tops.items():
        rx, _ry, rw, _rh = reg(k)
        align = els[k]["align"]
        if k == MARK:
            mw = mark["w"]
            mx = (rx + clear if align == LEFT else rx + rw - clear - mw if align == RIGHT else rx + (rw - mw) / 2.0)
            my = top + clear
            rec["placed"][MARK] = {"box": [round(mx, 3), round(my, 3), round(mw, 3), round(mark["h"], 3)],
                                   "clear_mm": round(clear, 3),
                                   "clear_box": [round(mx - clear, 3), round(my - clear, 3),
                                                 round(mw + 2 * clear, 3), round(mark["h"] + 2 * clear, 3)],
                                   "slot": els[k]["slot"], "align": align}
            spans.append((top, top + blocks[k]["h"], k))
        else:
            anchor = rx if align == LEFT else (rx + rw if align == RIGHT else rx + rw / 2.0)
            rec["placed"][k] = {"baseline": round(top + blocks[k]["drop"], 3), "x": round(anchor, 3),
                                "align": align, "slot": els[k]["slot"], "ink_top": round(top, 3),
                                "ink_bottom": round(top + blocks[k]["h"], 3)}
            spans.append((top, top + blocks[k]["h"], k))
    spans.sort()
    for (t1, b1, k1), (t2, b2, k2) in zip(spans, spans[1:]):
        if t2 < b1 - 1e-6:
            rec["collisions"].append({"elements": [k1, k2], "overlap_mm": round(b1 - t2, 3),
                                      "reason": "their places, as the words give them, overlap by %.3f mm" % (b1 - t2)})
    return rec


#: §BH67(d)2 — the element kinds the vision step reads that the face draws, and the one each is drawn as here
FOLLOWED_KINDS = {"mark": MARK, "name": NAME, "name_ar": NAME_AR, "window": "window", "motif": "motif_region"}


def follow_concept_layout(rec: dict, vision: dict | None, *, zone: tuple, mark_aspect: float | None,
                          mark_cap_ratio: float, measured: dict | None = None) -> dict:
    """§BH67(d)2, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "The composer draws from that layout
    instead of its fixed slots, scaled to the real surface. Every standing rule still applies — clear space, type
    floors, §AU1 on bottle fronts, the granted faces, the tier line. Where the concept's layout breaks a rule, the
    rule wins and the element is moved the least distance that satisfies it, recorded by name. … Where the vision step
    cannot read an element, it says so and the fixed slot is used — reported, never silent."

    ``rec`` is ``layout``'s record (the fixed slots); ``vision`` the ``container_concept_layout/1.0`` record; ``zone``
    the confirmed zone in drawing mm (x, y, w, h) — the lid face since §BH67(c)3, the surface the concept's fractions
    are of. Each element the vision step READ is moved to where the concept puts it: its centre at the concept's
    centre, scaled to the real surface. A mark keeps its own width, which the rules size (the §AU3 floor, a third of
    the face); the window takes the concept's box; TYPE KEEPS ITS SIZE — sizing type from the surface is §BH67(b)4,
    waiting on §Z1(b) [§BH68(b), 2026-09-24: reconciled — the composer chooses the name's size BEFORE this pass, the
    largest step of the typographic scale the lid holds for the concept's layout; this pass still never resizes
    type]. Then the rules, in order, each move the least distance that satisfies it, by name: every
    element inside its region (the safe area, the ring's inside); one GAP between neighbours, the mark's own clear
    space counting (§AY2); nothing of the motif behind the mark's clear space (§BA / C12). Returns the follow
    record; ``rec`` is changed in place and the composer draws it as always."""
    out = {"state": (vision or {}).get("state") or "NO_VISION_RECORD", "followed": [], "fixed_slot": [],
           "moves": [], "surface_mm": [round(v, 3) for v in zone]}
    placed = rec.get("placed") or {}
    targets = {}
    if (vision or {}).get("state") == "READ":
        zx, zy, zw, zh = zone
        for e in vision.get("elements") or []:
            k = FOLLOWED_KINDS.get(e["kind"])
            if k and k not in targets:
                x0, y0, x1, y1 = e["box"]
                targets[k] = (zx + x0 * zw, zy + y0 * zh, (x1 - x0) * zw, (y1 - y0) * zh)
        if SHADE in placed:
            # [his answer of 2026-09-29, (4)] the concept's own shade line — the lowest line on the face that is not
            # one of its elements — gives the record's shade its place; its words stay the picture's
            box_ = shade_line_box(vision, zone)
            if box_ is not None:
                targets[SHADE] = box_
    # §BH71 PART 1: an element MEASURED on the concept picture itself — the hero's window, its place on the lid rectified
    # by the lid's own rim (`concept_outline.hero_window_box`) — takes that place, and says so; the read's own box
    # for it is an axis-aligned fraction of a lid it may have seen tilted
    zx, zy, zw, zh = zone
    for k, (x0, y0, x1, y1) in (measured or {}).items():
        targets[k] = (zx + x0 * zw, zy + y0 * zh, (x1 - x0) * zw, (y1 - y0) * zh)
        out.setdefault("measured", []).append({"element": k, "source": "the concept picture, measured on its "
                                                                   "rectified lid (§BH71 PART 1)"})
    why_unread = ("the vision step read no layout (%s)" % out["state"] if out["state"] != "READ"
                  else "the vision step did not read it in the concept")
    for k in (MARK, NAME, NAME_AR, "window", "motif_region", SHADE):
        if k in placed and k not in targets:
            out["fixed_slot"].append({"element": k, "reason": (why_unread if k != SHADE else
                                                               "the concept shows no shade line of its own — the "
                                                               "face's foot")})
    if not targets:
        return out
    mark_reg = tuple(rec["regions"]["mark"])
    text_reg = tuple(rec["regions"]["text"])
    gap = float(rec.get("gap_mm") or 0.0)

    def span(k):                        # (top, bottom) of the element's ink, the mark's clear space included
        p = placed[k]
        if k == MARK:
            return p["clear_box"][1], p["clear_box"][1] + p["clear_box"][3]
        if isinstance(p, dict):
            return p["ink_top"], p["ink_bottom"]
        return p[1], p[1] + p[3]

    def shift(k, dy, dx=0.0):
        p = placed[k]
        if k == MARK:
            p["box"][0] = round(p["box"][0] + dx, 3)
            p["box"][1] = round(p["box"][1] + dy, 3)
            p["clear_box"][0] = round(p["clear_box"][0] + dx, 3)
            p["clear_box"][1] = round(p["clear_box"][1] + dy, 3)
        elif isinstance(p, dict):
            for key in ("baseline", "ink_top", "ink_bottom"):
                p[key] = round(p[key] + dy, 3)
            p["x"] = round(p["x"] + dx, 3)
        else:
            p[0], p[1] = round(p[0] + dx, 3), round(p[1] + dy, 3)

    def region(k):
        return mark_reg if k == MARK else text_reg

    # 1. TO THE CONCEPT'S PLACE: each read element's centre on the concept's centre, scaled to the real surface
    for k, (tx, ty, tw, th) in targets.items():
        if k == "motif_region" and "window" in placed:
            # a windowed face draws its motif INSIDE the window: the window's own place carries it
            out["followed"].append({"element": "motif", "inside": "window",
                                    "concept_mm": [round(v, 3) for v in (tx, ty, tw, th)]})
            continue
        if k not in placed:
            out["fixed_slot"].append({"element": k, "reason": "the concept shows it; the face's own reading draws "
                                                              "none — nothing to place"})
            continue
        if k in ("window", "motif_region"):
            placed[k] = [round(tx, 3), round(ty, 3), round(tw, 3), round(th, 3)]
        elif k == MARK and mark_aspect:
            # the mark is ARTWORK, not type: it takes the concept's width, held by the rules that size it — the §AU3
            # print floor and a third of the face (§AY2 step 2) — and its clear space follows its height
            block_ratio = mark_aspect * (1.0 + 2.0 * mark_cap_ratio)
            cap = mark_reg[3] * THIRD / block_ratio
            mw = max(MARK_FLOOR_MM, min(tw, cap))
            mh, clear = mw * mark_aspect, mw * mark_aspect * mark_cap_ratio
            mx, my = tx + tw / 2.0 - mw / 2.0, ty + th / 2.0 - mh / 2.0
            placed[k].update(box=[round(mx, 3), round(my, 3), round(mw, 3), round(mh, 3)], clear_mm=round(clear, 3),
                             clear_box=[round(mx - clear, 3), round(my - clear, 3), round(mw + 2 * clear, 3),
                                        round(mh + 2 * clear, 3)])
            if abs(mw - tw) > 1e-6:
                out["moves"].append({"element": k, "rule": ("the §AU3 print floor, 12.0 mm" if mw > tw else
                                                             "a third of the face (§AY2 step 2)"),
                                     "width_mm": round(mw, 3), "concept_width_mm": round(tw, 3)})
        else:
            top, bottom = span(k)
            cx_now = (placed[k]["box"][0] + placed[k]["box"][2] / 2.0 if k == MARK else placed[k]["x"])
            want_cx = tx + tw / 2.0
            if k != MARK and placed[k].get("align") == LEFT:
                want_cx = tx
            elif k != MARK and placed[k].get("align") == RIGHT:
                want_cx = tx + tw
            shift(k, (ty + th / 2.0) - (top + bottom) / 2.0, want_cx - cx_now)
        out["followed"].append({"element": k, "concept_mm": [round(v, 3) for v in (tx, ty, tw, th)]})

    def move(k, dy, dx, rule):
        if abs(dy) < 1e-6 and abs(dx) < 1e-6:
            return
        shift(k, dy, dx)
        out["moves"].append({"element": k, "rule": rule, "dy_mm": round(dy, 3), "dx_mm": round(dx, 3),
                             "moved_mm": round((dy * dy + dx * dx) ** 0.5, 3)})

    # 2. ACROSS: every element's centre inside its region — the least move sideways; a window wider than its region is
    #    held to the region's width
    for k in [k for k in (MARK, NAME, NAME_AR, "window", SHADE) if k in placed]:
        rx, ry, rw, rh = region(k)
        if k == "window" and placed[k][2] > rw:
            placed[k][2] = round(rw, 3)
            out["moves"].append({"element": k, "rule": "inside its region — held to the region's width",
                                 "width_mm": placed[k][2]})
        if k == MARK:
            x0, w = placed[k]["clear_box"][0], placed[k]["clear_box"][2]
        elif isinstance(placed[k], dict):
            x0, w = placed[k]["x"], 0.0
        else:
            x0, w = placed[k][0], placed[k][2]
        dx = (rx - x0) if x0 < rx else ((rx + rw) - (x0 + w) if x0 + w > rx + rw else 0.0)
        move(k, 0.0, dx, "inside its region, across")

    # 3. DOWN THE FACE, as ONE problem: the elements keep the concept's order; each stays inside its region (the zone's
    #    safe area, the ring's inside); neighbours keep one GAP, the mark's own clear space counting (§AY2) — which also
    #    keeps every motif out from behind the mark (§BA / C12); and, among the placements that satisfy all of that,
    #    the one that moves the elements the LEAST (least squares: an isotonic fit of the concept's own tops). A window
    #    the rules leave no room for is held to the room there is, never under the 8.0 mm window floor.
    stack = sorted([k for k in (MARK, NAME, NAME_AR, "window", SHADE) if k in placed],
                   key=lambda k: sum(span(k)) / 2.0)
    shade_gap = float(rec.get("shade_gap_mm") or gap)
    before = {k: span(k)[0] for k in stack}

    def solve():
        hs = [span(k)[1] - span(k)[0] for k in stack]
        seps = [0.0 if MARK in (a, b) else (shade_gap if SHADE in (a, b) else gap)
                for a, b in zip(stack, stack[1:])]
        offs = [0.0]
        for i in range(1, len(stack)):
            offs.append(offs[-1] + hs[i - 1] + seps[i - 1])
        want = [before[k] - offs[i] for i, k in enumerate(stack)]
        blocks = []
        for v in want:                                     # pool adjacent violators: the least-squares monotone fit
            blocks.append([v, 1])
            while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
                s_, c_ = blocks.pop()
                blocks[-1][0] += s_
                blocks[-1][1] += c_
        u = [s_ / c_ for s_, c_ in blocks for _ in range(c_)]
        lo = [region(k)[1] - offs[i] for i, k in enumerate(stack)]
        hi = [region(k)[1] + region(k)[3] - hs[i] - offs[i] for i, k in enumerate(stack)]
        low_env = [max(lo[:i + 1]) for i in range(len(stack))]
        high_env = [min(hi[i:]) for i in range(len(stack))]
        room = min(top - bot for bot, top in zip(low_env, high_env))
        return [min(max(v, bot), top) + offs[i] for i, (v, bot, top) in enumerate(zip(u, low_env, high_env))], room
    tops, room = solve()
    if room < -1e-6 and "window" in stack:
        wh = placed["window"][3]
        held = max(WINDOW_MIN_MM, wh + room)
        placed["window"][3] = round(held, 3)
        out["moves"].append({"element": "window", "rule": "held to the room the rules leave — its region less the "
                                                          "stack above and below it, the %.1f mm floor kept" % WINDOW_MIN_MM,
                             "height_mm": round(held, 3), "concept_height_mm": round(wh, 3)})
        tops, room = solve()
    for k, top in zip(stack, tops):
        move(k, top - span(k)[0], 0.0, "the stack's rules — inside its region, one GAP from its neighbours (the "
                                       "mark's clear space counting); the least movement that satisfies them")
    rec["collisions"] = []
    order = sorted(stack, key=lambda k: span(k)[0])
    for a, b in zip(order, order[1:]):
        if span(b)[0] < span(a)[1] - 1e-6:
            rec["collisions"].append({"elements": [a, b], "overlap_mm": round(span(a)[1] - span(b)[0], 3),
                                      "reason": "the concept's layout does not fit the rules on this surface: no "
                                                "placement keeps both inside the region at one GAP"})
    rec["followed_concept"] = True
    return out


#: [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines."] the rule's width where the concept's picture gives
#: none — the ruled front's own share of its zone (``compose_container._native_decoration``: ``rule_w = zw * 0.5``),
#: of the face's text region; where the vision step read the rule, its own width is drawn
RULE_WIDTH_SHARE = 0.5


def shade_line_box(vision: dict | None, zone: tuple) -> tuple | None:
    """[his answer of 2026-09-29, (4)] the concept's own shade line in drawing mm, (x, y, w, h): the lowest line the
    vision step READ on the face that is not one of the face's elements (``SHADE_LINE_KINDS``) — its place and its
    height, never its words — or None where it read none."""
    if (vision or {}).get("state") != "READ":
        return None
    lines = [e for e in vision.get("elements") or [] if e.get("kind") in SHADE_LINE_KINDS and e.get("box")]
    if not lines:
        return None
    x0, y0, x1, y1 = max(lines, key=lambda e: e["box"][3])["box"]
    zx, zy, zw, zh = zone
    return zx + x0 * zw, zy + y0 * zh, (x1 - x0) * zw, (y1 - y0) * zh


def concept_box(vision: dict | None, kind: str, zone: tuple) -> tuple | None:
    """The first element of ``kind`` the vision step READ, scaled to the real surface ``zone`` = (x, y, w, h) — the
    scaling ``follow_concept_layout`` gives every element it follows — or None."""
    if vision is None or vision.get("state") != "READ" or vision.get("elements") is None:
        return None
    zx, zy, zw, zh = zone
    for e in vision["elements"]:
        if e.get("kind") == kind:
            x0, y0, x1, y1 = e["box"]
            return (zx + x0 * zw, zy + y0 * zh, (x1 - x0) * zw, (y1 - y0) * zh)
    return None


def place_rule(rec: dict, *, rule_mm: float, concept: tuple | None = None) -> None:
    """[the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."] THE
    CONCEPT'S RULE, between the name and the Arabic line — task 110's "hairline rule", which its picture draws under
    "Focus" and over "فوكس". Placed on ``rec`` (``layout``'s record, after ``follow_concept_layout``) as
    ``placed["rule"]`` = (x, y, w, h), its ink strip:
      WHERE   midway in the gap between the two lines' ink, as the ruled front sets its rule midway between its two
              tiers (§BH66(b), ``compose_container._native_decoration``); the concept's own place for it, where the
              vision step read one, is recorded beside it, never drawn over the rules.
      WIDTH   the concept's own (``concept`` — the vision read's box on the real surface), else ``RULE_WIDTH_SHARE``
              of the text region; never wider than the text region.
      ACROSS  on the name's own axis (its alignment), held inside the text region by the least move.
    It is NOT an element of the stack: it keeps no GAP of its own and sits in the one the stack already keeps between
    the two lines, so it costs the name no step (§BH68(b)). Where the face sets no Arabic line, or anything the face
    places sits between the two, it is NOT_PLACED with the reason — room, never a refusal."""
    placed = rec["placed"]
    if NAME not in placed or NAME_AR not in placed:
        rec["not_placed"].append({"element": "rule", "reason": "the concept's rule sits between the name and the "
                                                              "Arabic line, and this face sets %s"
                                                              % ("no Arabic line" if NAME in placed else "no name")})
        return
    upper, lower = sorted((placed[NAME], placed[NAME_AR]), key=lambda p: p["ink_top"])
    top, bottom = upper["ink_bottom"], lower["ink_top"]

    def span(p):
        if isinstance(p, dict):
            return (p["clear_box"][1], p["clear_box"][1] + p["clear_box"][3]) if "clear_box" in p else (
                p["ink_top"], p["ink_bottom"])
        return p[1], p[1] + p[3]
    between = sorted(k for k, p in placed.items() if k not in (NAME, NAME_AR, "motif_region")
                     and span(p)[0] < bottom and top < span(p)[1])
    if between or bottom - top <= rule_mm:
        rec["not_placed"].append({"element": "rule", "reason": (
            "the %s sits between the name and the Arabic line" % " and ".join(between) if between else
            "the name and the Arabic line leave %.3f mm between their ink, no more than the rule's own %.2f mm"
            % (bottom - top, rule_mm))})
        return
    tx, _ty, tw, _th = rec["regions"]["text"]
    width = min(concept[2], tw) if concept is not None else tw * RULE_WIDTH_SHARE
    anchor, align = placed[NAME]["x"], placed[NAME]["align"]
    x = anchor if align == LEFT else (anchor - width if align == RIGHT else anchor - width / 2.0)
    x = min(max(x, tx), tx + tw - width)
    y = (top + bottom) / 2.0
    placed["rule"] = [round(x, 3), round(y - rule_mm / 2.0, 3), round(width, 3), round(rule_mm, 3)]
    rec["rules"]["rule"] = (
        "midway in the %.3f mm between the name's ink and the Arabic line's, as the ruled front sets its rule "
        "(§BH66(b)); %.2f mm wide — %s" % (
            bottom - top, width, "the concept's own width" if concept is not None and concept[2] <= tw else
            "the concept's own width, held to the text region" if concept is not None else
            "%.2f of the text region, the ruled front's own share (the concept's picture gives none)"
            % RULE_WIDTH_SHARE))
    if concept is not None:
        rec["rules"]["rule"] += "; the concept's own read centres it at %.3f mm, %.3f mm from where it is drawn" % (
            concept[1] + concept[3] / 2.0, abs(concept[1] + concept[3] / 2.0 - y))


def refuse_behind_mark(leaves, mark_clear_box) -> list:
    """Limit 2: every motif element whose box meets the mark's clear space — the names of the ones refused."""
    if mark_clear_box is None:
        return []
    mx, my, mw, mh = mark_clear_box
    out = []
    for name, (x, y, w, h) in leaves:
        if x < mx + mw and mx < x + w and y < my + mh and my < y + h:
            out.append(name)
    return out


__all__ = ["SCHEMA", "GOVERNED_BY", "SLOT_ORDER", "TOP", "UPPER", "ABOVE_WINDOW", "MIDDLE", "BELOW_WINDOW",
           "LOWER", "BOTTOM", "LEFT", "CENTRE", "RIGHT", "MARK", "NAME", "NAME_AR", "GAP_EM", "THIRD",
           "WINDOW_MIN_MM", "WINDOW_ASPECT_MAX", "WINDOW_WIDTH_SHARE", "REGION_SHARE", "MARK_FLOOR_MM",
           "read", "mark_width", "layout", "refuse_behind_mark", "FOLLOWED_KINDS", "follow_concept_layout",
           "RULE_WIDTH_SHARE", "concept_box", "place_rule"]
