"""WI-2A / §AC3 — sections may split across a fold, under four conditions.

§AB1(e)'s ledger priced WHOLE sections against ONE surface and found that
INGREDIENTS appears in none of the 30 subsets that fit at 5.0 pt. That is not a
copy problem; it is the arithmetic of a document that is taller than the thing
it is printed on. §AC3 supplies the missing rule — a section may continue onto
the next surface — and attaches four conditions to it. This module is those
four conditions, and each one is a mechanism here rather than a comment:

  (a) **A break only at a modelled line boundary.** *"Never mid-word, never
      mid-token, never at a position the line-counter cannot name. If the
      ledger cannot point at the break, the break did not happen in the
      model."* A break here is an INDEX into the line sequence `bp.layout`
      already emits, and `describe_cut` turns any index back into the
      `(section, order)` pair that names it. Mid-word is not forbidden by a
      check; it is unrepresentable, because the only positions this module can
      express are the boundaries between lines the layout engine produced.

  (b) **A continuation costs a line, debited from the RECEIVING surface.**
      *"If a split is free, the arithmetic lies — you can manufacture capacity
      by splitting, and the minimum surface count becomes a number the model
      invented rather than measured."* `_charge` adds 1 to the cost of any
      surface whose first line is mid-section. It is charged to the receiving
      surface and not the sending one because that is where the marker is
      printed. The measurement that makes this necessary rather than decorative
      is in `test_wi2a_split_packer.py`: an empty heading emits NO line, so a
      continuation is genuinely free unless something charges for it.

  (c) **Reading order is DECLARED before the split is computed.** *"The order
      is an input to the packer, not an output of it."* `reading_order` is a
      REQUIRED argument with no default. There is no ordering heuristic in this
      file. The order fixes the line sequence, and the line sequence is fixed
      before a single cut position is considered.

  (d) **Split only where NECESSARY, never for balance.** *"Permitting it would
      let the packer split things to make a tight fit look comfortable — which
      is exactly how an overflow becomes invisible."* This is the condition
      that shaped the algorithm. A greedy fill-then-spill packer splits
      whenever a section overhangs, which is splitting for packing convenience
      and would satisfy (d) only by assertion. Instead `pack` minimises
      lexicographically on `(surfaces, splits)`: among every allocation that
      achieves the minimum surface count, it returns one with the FEWEST
      breaks. Each surviving break is then necessary by construction — the
      search proved that no allocation with fewer breaks reaches that surface
      count. Necessity is a result here, not a promise.

WHAT THIS MODULE COMPUTES AND WHAT IT REFUSES TO RULE
-----------------------------------------------------
§AC3(e): *"WI-2A computes it. WI-2A does not rule it. The number returns as an
owner question in §AD, because AB1(f) reserved the layer count to me and AC3
does not transfer it."* So `pack` reports `surfaces_required` and every record
carries `layer_count_authority: None`. The number is a measurement of what the
copy needs; it is not a decision that the object has that many layers. Those
are different claims and this module only makes the first.

The continuation MARKER is the same distinction one level down. §AC3(b) rules
what a continuation COSTS — one line. Nothing rules what it SAYS. So the cost
is charged and the wording is left at `continuation_marker_text: None` with
`CONTINUATION_MARKER_TEXT_NOT_RULED`, on the same principle that makes
`back_panel_ledger.mandatory_state` refuse to invent a mandatory list: an
executor's guess printed as a fact is worse than a recorded absence.

WHY AN EXACT SEARCH RATHER THAN A GREEDY ONE
---------------------------------------------
Because (d) needs the minimum to be a fact and not an artefact. Reading order
is declared, so an allocation is fully described by where the cuts fall in one
linear sequence of lines — which makes the space small enough to search
exhaustively by dynamic programming over cut positions. `pack` therefore
returns THE minimum, not a bound on it, and `lower_bound_surfaces` is carried
alongside as an independent arithmetic cross-check computed from the ungapped
capacity: if the two agree, the answer is confirmed by a second method that
shares no code with the first.

THE ASSUMPTION THIS MODULE MAKES, STATED SO IT CAN BE FALSIFIED
----------------------------------------------------------------
Every surface is assumed to have the SAME width, and therefore the same column
and the same wrap. §AC2(b)'s `(N, B)` gives one budget B for all N surfaces, so
this is that form's assumption and not a new one — but it is load-bearing here
in a way it is not there, because a break is only meaningful if the tail wraps
on the receiving surface exactly as it wrapped on the sending one. That
identity is not assumed: `test_wi2a_split_packer.py` re-wraps every suffix of
every section at both floors and requires the lines to come back identical.
"""
from __future__ import annotations

import math

from apps.ire import back_panel as bp
from apps.ire import surface_plan as sp

SCHEMA = "container_back_panel_split_packer/1.0"

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §AC3 — a section may continue onto the next "
    "surface, breaking only at a line boundary the ledger models, paying one "
    "line for the continuation on the receiving surface, in a reading order "
    "the caller declared, and only where a break is necessary to reach the "
    "minimum surface count. No layer count is ruled and no marker text is "
    "invented."
)

#: §AC3(c). Required, never defaulted: a default reading order would be this
#: module choosing the order, which is the exact thing (c) forbids.
READING_ORDER_REQUIRED = "SPLIT_PACKER_READING_ORDER_REQUIRED"
READING_ORDER_NOT_A_PERMUTATION = "SPLIT_PACKER_READING_ORDER_NOT_A_PERMUTATION"

#: §AC3 rules that sections MAY split. Whether they do on a given call is still
#: the caller's to state, because the negative control depends on being able to
#: turn it off and reproduce §AB1(e)'s whole-section result exactly.
SPLIT_POLICY_REQUIRED = "SPLIT_PACKER_SPLIT_POLICY_REQUIRED"

#: no allocation exists at any surface count — reachable only when a single
#: line cannot be placed on an empty surface, or when splitting is off and one
#: section is taller than a whole surface.
DOES_NOT_FIT = "SPLIT_PACKER_DOES_NOT_FIT"

#: `bp.layout` could not measure, because a face was not registered. WI-K's
#: lesson, restated: an unregistered face silently degrades to one line per
#: field, which reads as the panel getting ROOMIER. A packer that ran on that
#: would report a smaller minimum than the truth.
UNMEASURED = "SPLIT_PACKER_FIT_UNMEASURED"

#: §AC3(b) rules the COST of a continuation, not its wording.
CONTINUATION_MARKER_TEXT_NOT_RULED = \
    "SPLIT_PACKER_CONTINUATION_MARKER_TEXT_NOT_RULED"

#: §AC3(e) / §AB1(f). The minimum is computed; the layer count is not ruled.
LAYER_COUNT_NOT_RULED = "SPLIT_PACKER_LAYER_COUNT_NOT_RULED"

#: §AC3(b)'s charge, as a number in one place. One line per continuation.
CONTINUATION_LINE_COST = 1

#: how many distinct optimal allocations to count before giving up and saying
#: "at least this many". Counting is cheap but the number can be large, and an
#: exact count is not worth a big integer when the only thing it is used for is
#: to establish that the answer is not unique.
WITNESS_COUNT_CAP = 10000

#: more than one allocation reaches the minimum, and NOTHING RANKS THEM. See
#: `pack`: the module reports one and refuses to prefer it.
ALLOCATION_NOT_UNIQUE = "SPLIT_PACKER_ALLOCATION_NOT_UNIQUE"


def _faces_measured(record: dict) -> bool:
    return bool(record.get("fit_measured"))


def line_model(sections, *, width_mm: float, size_pt: float, regular, bold,
               reading_order) -> dict:
    """The document as ONE sequence of modelled lines, in the declared order.

    This is the object §AC3(a) requires to exist before a break can be spoken
    about. Each entry carries the section it came from and its ordinal WITHIN
    that section, so any cut position can be named as a `(section, order)` pair
    rather than as an offset into a string.

    Each section is measured ALONE on the column with unbounded height, for the
    same reason `back_panel_ledger.section_costs` does: a section's wrap depends
    on the column width and its own text and nothing else, so measuring it in
    isolation yields lines that are the section's own rather than an artefact of
    what happened to precede it.
    """
    if reading_order is None:
        raise ValueError(READING_ORDER_REQUIRED)
    supplied = list(sections or [])
    order = [int(i) for i in reading_order]
    if sorted(order) != list(range(len(supplied))):
        raise ValueError(
            f"{READING_ORDER_NOT_A_PERMUTATION}: {order!r} is not a "
            f"permutation of the {len(supplied)} sections supplied")

    lines: list[dict] = []
    measured = True
    per_section: dict[int, int] = {}
    for index in order:
        section = supplied[index]
        record = bp.layout([section], float(width_mm), 1.0e6,
                           size_pt=float(size_pt), regular=regular, bold=bold)
        if not _faces_measured(record):
            measured = False
        heading = str((section or {}).get("heading", ""))
        own = record["lines"]
        per_section[index] = len(own)
        for entry in own:
            lines.append({
                "position": len(lines),
                "section": index,
                "heading": heading,
                "role": entry["role"],
                "order": entry["order"],
                "text": entry["text"],
            })
    return {
        "schema_version": SCHEMA,
        "reading_order": order,
        "reading_order_provenance": "declared by the caller; §AC3(c)",
        "lines": lines,
        "total_lines": len(lines),
        "lines_per_section": per_section,
        "measured": measured,
        "size_pt": float(size_pt),
        "width_mm": float(width_mm),
    }


def is_split_position(lines, index: int) -> bool:
    """Whether a cut BEFORE ``index`` breaks a section rather than following one.

    The whole of §AC3(a)'s distinction, in two comparisons: a cut is a SPLIT
    when the line before it and the line at it belong to the same section, and
    is an ordinary surface boundary otherwise. The document's start and end are
    never splits.
    """
    i = int(index)
    if i <= 0 or i >= len(lines):
        return False
    return lines[i - 1]["section"] == lines[i]["section"]


def describe_cut(lines, index: int) -> dict:
    """Name a cut position the way §AC3(a) requires it to be nameable."""
    i = int(index)
    if i <= 0 or i >= len(lines):
        return {"position": i, "split": False, "section": None, "order": None,
                "heading": None, "role": None, "resumes_at_text": None}
    at = lines[i]
    return {
        "position": i,
        "split": is_split_position(lines, i),
        "section": at["section"],
        "heading": at["heading"],
        "order": at["order"],
        "role": at["role"],
        # what the receiving surface starts with, quoted from the model rather
        # than re-derived, so the break can be checked by eye against a proof.
        "resumes_at_text": at["text"],
    }


def _pieces_in(lines, start: int, end: int) -> int:
    """How many section-pieces the run ``lines[start:end]`` contains.

    A surface pays `SECTION_GAP_MM` between pieces, so this number is what sets
    the surface's capacity. Reading order is fixed, so a section's lines are
    contiguous and the count is one more than the number of changes.
    """
    if end <= start:
        return 0
    pieces = 1
    for i in range(start + 1, end):
        if lines[i]["section"] != lines[i - 1]["section"]:
            pieces += 1
    return pieces


def capacity_for_pieces(*, width_mm: float, height_mm: float, size_pt: float,
                        pieces: int, regular, bold) -> int:
    """Lines one surface holds when it carries ``pieces`` section-pieces.

    Delegates the geometry to `back_panel_ledger.capacity` rather than
    recomputing it. Two modules that each derive the gap charge from the panel
    dimensions are two modules that can come to disagree about it after one of
    them is edited.
    """
    from apps.ire import back_panel_ledger as led
    if int(pieces) <= 0:
        return 0
    record = led.capacity(width_mm=width_mm, height_mm=height_mm,
                          size_pt=size_pt, sections=int(pieces),
                          regular=regular, bold=bold)
    return int(record["lines_held_for_this_many_sections"])


def _charge(lines, start: int, end: int) -> int:
    """What the run ``lines[start:end]`` costs the surface that receives it.

    §AC3(b): the lines themselves, plus ONE line if this surface is receiving
    the tail of a section that began on an earlier one. The charge lands here,
    on the receiving surface, because that is where the marker prints.
    """
    cost = end - start
    if is_split_position(lines, start):
        cost += CONTINUATION_LINE_COST
    return cost


def pack(sections, *, width_mm: float, height_mm: float, size_pt: float,
         regular, bold, reading_order, allow_split) -> dict:
    """The minimum number of surfaces the copy needs, and where it breaks.

    ONE floor per call. This originally took a `floors=FLOORS` argument copied
    from the ledger's shape, never read it, and imported `back_panel_copy` to
    supply the default — which lengthened the import chain
    `test_wio_on_pack_copy.py` watches, for a parameter that did nothing. The
    guard caught it. A packer prices ONE size, because the line model, the
    capacity and the cut positions are all functions of that size; a `floors`
    argument would have implied it priced several.

    Exact, not greedy — see the module docstring for why §AC3(d) forces that.
    The search is a dynamic programme over cut positions in the declared line
    sequence, minimising `(surfaces, splits)` lexicographically: the primary key
    gives the minimum surface count, and the secondary key is §AC3(d) itself,
    since it returns the allocation that reaches that count with the fewest
    breaks and therefore leaves no break that could have been avoided.

    Returns a record. It does not raise on infeasibility — a document that does
    not fit is a MEASUREMENT, and the codes carry it.

    THE ALLOCATION IS A WITNESS, NOT A CHOICE. Several allocations usually
    reach the minimum with the same number of breaks, and §AC3 ranks them
    against each other nowhere. So the record reports how many there are and
    presents the one the search reached as EVIDENCE that the minimum is
    achievable, not as a recommended layout. `back_panel_ledger.subsets` set
    this precedent for the same reason: choosing among equals here would be
    this module making the layout decision it was built to price. A reader who
    finds `surface[0]` holding six lines of an eighteen-line budget is looking
    at that refusal, not at a bug.
    """
    if allow_split is None:
        raise ValueError(SPLIT_POLICY_REQUIRED)
    model = line_model(sections, width_mm=width_mm, size_pt=size_pt,
                       regular=regular, bold=bold, reading_order=reading_order)
    lines = model["lines"]
    total = len(lines)
    codes: list[str] = []
    if not model["measured"]:
        codes.append(UNMEASURED)

    ungapped = capacity_for_pieces(width_mm=width_mm, height_mm=height_mm,
                                   size_pt=size_pt, pieces=1, regular=regular,
                                   bold=bold)
    #: The most generous arithmetic that could possibly be true: every surface
    #: carries one piece, so it pays no gap, and no continuation is ever
    #: charged. Nothing can beat it. It shares no code with the search below,
    #: which is the point of computing it — see `TestTheMinimumIsConfirmedTwice`.
    lower_bound = (int(math.ceil(total / ungapped)) if ungapped and total
                   else (0 if not total else None))

    #: `best[i]` = the lexicographically smallest `(surfaces, splits)` that
    #: covers `lines[:i]`, or None when no allocation reaches that prefix.
    best: list[tuple | None] = [None] * (total + 1)
    parent: list[int | None] = [None] * (total + 1)
    best[0] = (0, 0)

    cap_cache: dict[int, int] = {}

    def cap(pieces: int) -> int:
        if pieces not in cap_cache:
            cap_cache[pieces] = capacity_for_pieces(
                width_mm=width_mm, height_mm=height_mm, size_pt=size_pt,
                pieces=pieces, regular=regular, bold=bold)
        return cap_cache[pieces]

    edges: list[tuple[int, int, tuple]] = []
    for start in range(total):
        if best[start] is None:
            continue
        if not allow_split and is_split_position(lines, start):
            # With splitting off a surface may only begin where a section
            # begins. The state is reachable but not extendable, which is how
            # "no split" is enforced without a separate code path.
            continue
        surfaces_so_far, splits_so_far = best[start]
        opens_a_split = is_split_position(lines, start)
        delta = (1, 1 if opens_a_split else 0)
        for end in range(start + 1, total + 1):
            pieces = _pieces_in(lines, start, end)
            if _charge(lines, start, end) > cap(pieces):
                # costs only grow with `end`, so nothing further can fit either
                break
            if not allow_split and is_split_position(lines, end):
                continue
            edges.append((start, end, delta))
            candidate = (surfaces_so_far + delta[0], splits_so_far + delta[1])
            if best[end] is None or candidate < best[end]:
                best[end] = candidate
                parent[end] = start

    if best[total] is None:
        codes.append(DOES_NOT_FIT)
        return _record(model, None, [], codes, lower_bound, ungapped,
                       allow_split, height_mm, 0, False)

    #: How many allocations reach the optimum. Valid because adding an edge cost
    #: preserves the lexicographic order on `(surfaces, splits)`, so an optimal
    #: path is optimal on every prefix and paths can be counted state by state.
    ways = [0] * (total + 1)
    ways[0] = 1
    capped = False
    for start, end, delta in edges:
        if best[start] is None or best[end] is None or not ways[start]:
            continue
        if (best[start][0] + delta[0], best[start][1] + delta[1]) == best[end]:
            ways[end] += ways[start]
            if ways[end] > WITNESS_COUNT_CAP:
                ways[end] = WITNESS_COUNT_CAP
                capped = True
    witnesses = ways[total]
    if witnesses > 1:
        codes.append(ALLOCATION_NOT_UNIQUE)

    cuts: list[int] = []
    at = total
    while at is not None and at > 0:
        cuts.append(at)
        at = parent[at]
    boundaries = sorted(cuts + [0])

    surfaces = []
    for index in range(len(boundaries) - 1):
        start, end = boundaries[index], boundaries[index + 1]
        pieces = _pieces_in(lines, start, end)
        continuation = is_split_position(lines, start)
        run = lines[start:end]
        surfaces.append({
            "surface": sp.address(index),
            "index": index,
            "first_line": start,
            "last_line": end - 1,
            "lines_of_copy": end - start,
            "continuation_line_charged": (CONTINUATION_LINE_COST
                                          if continuation else 0),
            "lines_charged": _charge(lines, start, end),
            "capacity_lines": cap(pieces),
            "pieces": pieces,
            "receives_continuation": continuation,
            "opens_at": describe_cut(lines, start),
            "headings": _headings_of(run),
            # A heading left with no copy beneath it on the same surface. It is
            # RECORDED and not prevented: forbidding it is a typographic
            # preference, and §AC3 supplied four conditions, not five.
            "heading_alone": _heading_alone(run),
            "continuation_marker_text": None,
        })

    if any(s["continuation_line_charged"] for s in surfaces):
        codes.append(CONTINUATION_MARKER_TEXT_NOT_RULED)
    codes.append(LAYER_COUNT_NOT_RULED)
    return _record(model, best[total], surfaces, codes, lower_bound, ungapped,
                   allow_split, height_mm, witnesses, capped)


def _headings_of(run) -> list[dict]:
    out: list[dict] = []
    for entry in run:
        if not out or out[-1]["section"] != entry["section"]:
            out.append({"section": entry["section"],
                        "heading": entry["heading"],
                        "starts_at_order": entry["order"],
                        "whole": entry["order"] == 0,
                        "lines_here": 0})
        out[-1]["lines_here"] += 1
    return out


def _heading_alone(run) -> list[str]:
    out = []
    for piece in _headings_of(run):
        rows = [e for e in run if e["section"] == piece["section"]]
        if rows and all(e["role"] == "heading" for e in rows):
            out.append(piece["heading"])
    return out


def _record(model, answer, surfaces, codes, lower_bound, ungapped, allow_split,
            height_mm, witnesses, capped) -> dict:
    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "size_pt": model["size_pt"],
        "width_mm": model["width_mm"],
        "height_mm": float(height_mm),
        "reading_order": model["reading_order"],
        "reading_order_provenance": model["reading_order_provenance"],
        "splitting_allowed": bool(allow_split),
        "total_lines": model["total_lines"],
        "lines_per_section": model["lines_per_section"],
        "surfaces_required": (answer[0] if answer else None),
        "splits_used": (answer[1] if answer else None),
        "lower_bound_surfaces": lower_bound,
        "lower_bound_basis": (
            "ceil(total_lines / ungapped capacity of one surface) — assumes "
            "every surface carries one piece and pays no gap and no "
            "continuation, which nothing can beat"),
        "ungapped_capacity_lines": ungapped,
        "minimum_confirmed_by_lower_bound": (
            answer is not None and lower_bound is not None
            and answer[0] == lower_bound),
        "surfaces": surfaces,
        #: The allocation above is ONE of this many that reach the same
        #: `(surfaces, splits)`. Reported so that nobody reads a witness as a
        #: recommendation — see `pack`'s docstring.
        "optimal_allocations": witnesses,
        "optimal_allocations_capped_at": (WITNESS_COUNT_CAP if capped else None),
        "allocation_is_a_witness": True,
        "measured": model["measured"],
        #: §AC3(e) / §AB1(f). The count above is what the COPY needs. It is not
        #: a ruling that the object has that many layers, and this key stays
        #: None until §AD says otherwise.
        "layer_count_authority": None,
        "codes": codes,
    }


__all__ = ["CONTINUATION_LINE_COST", "CONTINUATION_MARKER_TEXT_NOT_RULED",
           "DOES_NOT_FIT", "LAYER_COUNT_NOT_RULED",
           "READING_ORDER_NOT_A_PERMUTATION", "READING_ORDER_REQUIRED", "RULE",
           "SCHEMA", "SPLIT_POLICY_REQUIRED", "UNMEASURED",
           "capacity_for_pieces", "describe_cut", "is_split_position",
           "line_model", "pack"]
