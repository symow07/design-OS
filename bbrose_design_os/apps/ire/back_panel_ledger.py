"""WI-W / §AB1(e) — what each back-panel section costs, and what a budget buys.

§AB1(e) asks for "the per-section line ledger for the back panel: every
mandatory section, its cost in lines at 5.0 and at 6.0 pt, and the subsets that
fit a given surface budget, which is a parameter", with three prohibitions --
"Do not invent cuts. Do not compress. Do not assume a layer count." -- and one
purpose: "a measuring instrument built so that an owner can cut with numbers in
front of him".

So this module prices. It does not choose.

HOW IT DIFFERS FROM §AA1, WHICH ALREADY MEASURED SOMETHING ADJACENT
-------------------------------------------------------------------
`back_panel_copy` prices CUTS -- edits inside a section's text, each carrying
the source that permits it. Its finding was that compression is not the answer.
This module never edits a character. Its unit is the WHOLE SECTION, its
question is which combinations of whole sections fit a surface, and its answer
is a table. That is the difference between "what if we reword this" and "what
if we do not print this", and only the second one is WI-W's.

THE THREE PROHIBITIONS, EACH AS STRUCTURE RATHER THAN AS A PROMISE
-------------------------------------------------------------------
* **No invented cuts.** Section text is never read for editing and never
  written. A subset is a selection over the supplied sections; the sections
  that survive it are the ones that were handed in, unchanged.
* **No compression.** Type size is never chosen by this module. Both floors are
  reported side by side and neither is preferred, because picking one is the
  decision the ledger exists to inform.
* **No assumed layer count.** The budget is ONE SURFACE. Nothing here
  multiplies it, and there is no `layers` parameter to pass. §AB1(f) says the
  layer count is not yet a number, and `container_label_construction
  .require_layer_count` raises rather than returning one; a ledger that
  silently doubled a budget would be answering that question in arithmetic
  while the module next door refuses to answer it in words.

WHAT THIS MODULE WILL NOT TELL YOU, AND WHY THAT IS THE HONEST SHAPE
-------------------------------------------------------------------
**It does not rule which sections are mandatory.** §AA1 established -- by
grepping, not by assuming -- that no regulatory text exists anywhere in this
repository. An executor who hard-coded a mandatory set here would be doing
exactly what §AA1(c) forbids one file further along: sourcing a decision to his
own judgement and printing it as a fact.

`mandatory_claims` is therefore a PARAMETER whose default is empty, and every
section not claimed in it reports `SOURCE_REQUIRED` -- the §AA1 state meaning
"no permission was found". The subsets carry what they DROP and the state of
each dropped section's claim, so an owner reading the table sees which of his
options are priced-and-lawful, which are priced-and-unsourced, and which he
would be deciding on his own authority. That is what "cut with numbers in front
of him" has to mean when the numbers are real and the regulations are absent.

Pure: no Django, no ORM, no network. Takes the document, the surface and the
claims as arguments -- a measurement tool that knows one document is a document
wearing a tool.
"""
from __future__ import annotations

import itertools

from apps.ire import back_panel as bp
from apps.ire import surface_plan as sp
from apps.ire.back_panel_copy import (CITED_EXTERNAL_UNVERIFIED, FLOOR_PROVENANCE,
                                      FLOORS, OWNER_RULING_IN_REPO,
                                      SOURCE_REQUIRED)

SCHEMA = "container_back_panel_line_ledger/1.0"

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §AB1(e) — the per-section line ledger: every "
    "section's cost in lines at 5.0 and at 6.0 pt, and the subsets of WHOLE "
    "sections that fit a surface budget supplied by the caller. No cut is "
    "invented, no copy is compressed, no type size is chosen and no layer "
    "count is assumed."
)

#: §AA1's states, re-exported rather than restated. A second vocabulary for the
#: same idea is how two files come to disagree about what "sourced" means.
MANDATORY_STATES = (OWNER_RULING_IN_REPO, CITED_EXTERNAL_UNVERIFIED,
                    SOURCE_REQUIRED)

#: exhaustive enumeration is 2**n - 1. Twelve sections is 4095 subsets, which
#: is a table; twenty is a million, which is a hang. Refused with a code rather
#: than silently sampled — a ledger that quietly stopped being exhaustive would
#: still look like a ledger.
MAX_SECTIONS_FOR_EXHAUSTIVE = 12

TOO_MANY_SECTIONS = "CONTAINER_BACK_PANEL_LEDGER_TOO_MANY_SECTIONS"

#: no subset of the supplied sections fits the supplied budget — not even one
#: section on its own. Distinct from "the whole document does not fit", which is
#: ordinary and already known.
NOTHING_FITS = "CONTAINER_BACK_PANEL_LEDGER_NOTHING_FITS"

#: the fit could not be measured because a face was not registered. `bp.layout`
#: reports `fits: None` in that case and this module refuses to read None as a
#: fit either way. WI-K's lesson: an unregistered face silently turns a fit
#: measurement into one line per field, which reads as the panel getting roomier.
UNMEASURED = "CONTAINER_BACK_PANEL_LEDGER_FIT_UNMEASURED"

BUDGET_NOTE = (
    "the budget is ONE SURFACE, width × height in mm, and it is the caller's "
    "to supply. Width is not incidental: it sets the column and therefore the "
    "wrap, so a line cost measured at one width does not transfer to another. "
    "Nothing here multiplies the budget by a layer count — §AB1(f) leaves that "
    "count unruled, and doubling a surface in arithmetic would rule it."
)

MANDATORY_NOTE = (
    "this ledger does not decide which sections are mandatory and does not "
    "have a default set. No regulatory text exists in this repository (§AA1 "
    "grepped for it), so a hard-coded mandatory list would be an executor's "
    "judgement printed as a fact. Claims are supplied by the caller with a "
    "source; anything unclaimed reports SOURCE_REQUIRED, which is §AA1(c)'s "
    "state for a permission that was looked for and not found."
)


def mandatory_state(heading: str, mandatory_claims=None) -> str:
    """The claim recorded for ``heading``, or ``SOURCE_REQUIRED``.

    Unclaimed is not "optional". It is "nobody sourced an answer", which is a
    different and weaker statement, and collapsing the two is how an unsourced
    deletion acquires the look of a permitted one.
    """
    claim = (mandatory_claims or {}).get(heading)
    if isinstance(claim, dict):
        state = claim.get("state")
        if state in MANDATORY_STATES:
            return str(state)
    return SOURCE_REQUIRED


def _layout(sections, width_mm, height_mm, size_pt, regular, bold):
    return bp.layout(list(sections), float(width_mm), float(height_mm),
                     size_pt=float(size_pt), regular=regular, bold=bold)


def section_costs(sections, *, width_mm: float, regular, bold,
                  floors=FLOORS, mandatory_claims=None) -> list[dict]:
    """Each section's cost in lines and mm, at each floor.

    Measured ALONE on the column, with height enough that nothing is clipped:
    a section's line count depends on the column width and its own text, and
    nothing else, so measuring it in isolation gives a cost that is the
    section's own rather than an artefact of where it happened to sit. That
    independence is not assumed — `TestTheCostsCompose` requires the isolated
    costs to reconstruct `bp.layout`'s total for whole documents.
    """
    out = []
    for index, section in enumerate(sections or []):
        heading = str((section or {}).get("heading", ""))
        entry = {
            "index": index,
            "heading": heading,
            "mandatory_state": mandatory_state(heading, mandatory_claims),
            "characters_supplied": None,
            "cost": {},
        }
        for floor in floors:
            record = _layout([section], width_mm, 1.0e6, floor, regular, bold)
            per = (record["sections"] or [{}])[0]
            entry["characters_supplied"] = per.get("characters_supplied")
            entry["cost"][str(floor)] = {
                "lines": per.get("lines_required"),
                "mm": record["height_required_mm"],
                "line_height_mm": record["line_height_mm"],
                "measured": record["fit_measured"],
            }
        out.append(entry)
    return out


def capacity(*, width_mm: float, height_mm: float, size_pt: float, sections: int,
             regular, bold) -> dict:
    """How many lines the budget holds for a document of ``sections`` sections.

    Capacity is not one number. `bp.layout` charges `SECTION_GAP_MM` between
    sections, so a six-section document pays five gaps before its first line
    and holds fewer lines than a one-section document on the same surface. Both
    are reported and both are labelled, because quoting the ungapped figure as
    "the panel holds N lines" overstates every real document.
    """
    probe = _layout([{"heading": "", "text": "x"}], width_mm, height_mm,
                    size_pt, regular, bold)
    line_h = probe["line_height_mm"]
    available = probe["height_available_mm"]
    gaps = max(0, int(sections) - 1) * bp.SECTION_GAP_MM
    return {
        "size_pt": size_pt,
        "size_provenance": FLOOR_PROVENANCE.get(size_pt),
        "line_height_mm": line_h,
        "height_available_mm": available,
        "section_gaps_paid_mm": round(gaps, 3),
        "lines_held_for_this_many_sections": (
            int((available - gaps) // line_h + 1e-9) if line_h else 0),
        "lines_held_in_one_section": (int(available // line_h + 1e-9)
                                      if line_h else 0),
        "sections_assumed": int(sections),
    }


def surface_budget(*, n, width_mm: float, height_mm: float, size_pt: float,
                   sections_per_surface: int, regular, bold) -> dict:
    """§AC2(b)'s ``(N, B)``, with B MEASURED and N taken from the caller.

    *"The ledger and the construction model take `(N, B)` — N surfaces, budget
    B per surface — with N unbound."* This is the ledger's half. It measures B
    on one surface of the given geometry and hands `(N, B)` to
    `surface_plan.plan`, which knows nothing about panels; the two halves are
    separate so that the thing which counts lines and the thing which counts
    surfaces cannot start agreeing with each other by accident.

    `n` is passed straight through and NOT defaulted here either — see
    `surface_plan.plan`. A default in this wrapper would reintroduce §AB1(f)'s
    forbidden assumption one import further out, which is exactly how a
    guessed number survives a rule against guessing.

    WHAT B IS AND WHERE IT IS OPTIMISTIC, stated because a budget quoted
    without its assumption is the thing §AB1(e) was written against. B is
    `lines_held_for_this_many_sections` — the GAPPED figure, which charges
    `SECTION_GAP_MM` between sections and is the smaller of the two capacity
    reports. It is therefore honest about gaps and dishonest about
    UNIFORMITY: §AC2(b)'s form gives every surface the same B, but the real
    capacity of a surface depends on how many sections actually land on it,
    and a surface holding one section pays no gap at all. So B here is
    correct for a surface carrying exactly `sections_per_surface` sections
    and CONSERVATIVE for one carrying fewer.

    That is deliberate and it is not a rounding choice. The allocator is
    §AC3's, it does not exist yet, and it is the only thing that will know the
    per-surface section count. Until it does, a uniform B that understates is
    the direction that cannot cause a document to be declared to fit when it
    does not. Both capacity figures are returned under `budget_provenance` so
    the allocator can recompute rather than inherit this assumption.
    """
    measured = capacity(width_mm=width_mm, height_mm=height_mm,
                        size_pt=size_pt, sections=sections_per_surface,
                        regular=regular, bold=bold)
    record = sp.plan(n, measured["lines_held_for_this_many_sections"])
    record["budget_provenance"] = measured
    record["budget_basis"] = "lines_held_for_this_many_sections"
    #: The other reading, carried rather than discarded: a caller that puts one
    #: section on a surface is entitled to the ungapped number, and having to
    #: re-derive it would mean re-deriving the layout.
    record["budget_lines_if_one_section"] = \
        measured["lines_held_in_one_section"]
    return record


def _subset_record(sections, indices, *, width_mm, height_mm, floors, regular,
                   bold, mandatory_claims):
    kept = [sections[i] for i in indices]
    kept_headings = [str((s or {}).get("heading", "")) for s in kept]
    dropped = [(i, str((sections[i] or {}).get("heading", "")))
               for i in range(len(sections)) if i not in set(indices)]
    fit = {}
    for floor in floors:
        record = _layout(kept, width_mm, height_mm, floor, regular, bold)
        fit[str(floor)] = {
            "fits": record["fits"],
            "lines_required": record["lines_required"],
            "height_required_mm": record["height_required_mm"],
            "height_available_mm": record["height_available_mm"],
            "overflow_mm": record["overflow_mm"],
            "measured": record["fit_measured"],
        }
    return {
        "indices": list(indices),
        "kept": kept_headings,
        "dropped": [h for _, h in dropped],
        "dropped_states": {h: mandatory_state(h, mandatory_claims)
                           for _, h in dropped},
        "drops_something_unsourced": any(
            mandatory_state(h, mandatory_claims) == SOURCE_REQUIRED
            for _, h in dropped),
        "fit": fit,
    }


def subsets(sections, *, width_mm: float, height_mm: float, regular, bold,
            floors=FLOORS, mandatory_claims=None) -> dict:
    """Every non-empty subset of ``sections``, priced against the budget.

    Exhaustive on purpose. A greedy "best subset" would need a preference
    ordering over which sections matter, and that ordering is precisely the
    owner's decision — supplying one here would be the ledger making the cut it
    was built to price.
    """
    supplied = list(sections or [])
    codes = []
    if len(supplied) > MAX_SECTIONS_FOR_EXHAUSTIVE:
        return {"codes": [TOO_MANY_SECTIONS], "subsets": [],
                "sections_supplied": len(supplied),
                "limit": MAX_SECTIONS_FOR_EXHAUSTIVE}

    records = []
    for size in range(1, len(supplied) + 1):
        for combo in itertools.combinations(range(len(supplied)), size):
            records.append(_subset_record(
                supplied, combo, width_mm=width_mm, height_mm=height_mm,
                floors=floors, regular=regular, bold=bold,
                mandatory_claims=mandatory_claims))

    fitting = {str(f): [r for r in records if r["fit"][str(f)]["fits"] is True]
               for f in floors}
    unmeasured = any(r["fit"][str(f)]["measured"] is False
                     for r in records for f in floors)
    if unmeasured:
        codes.append(UNMEASURED)
    if records and not any(fitting[str(f)] for f in floors):
        codes.append(NOTHING_FITS)

    # a subset is MAXIMAL when no further section can be added and still fit.
    # That is the row an owner actually wants: the most he can print, rather
    # than any of the smaller sets that trivially also fit.
    maximal = {}
    for floor in floors:
        key = str(floor)
        sets_ = [frozenset(r["indices"]) for r in fitting[key]]
        maximal[key] = [r for r in fitting[key]
                        if not any(frozenset(r["indices"]) < other
                                   for other in sets_)]
    return {
        "codes": codes,
        "sections_supplied": len(supplied),
        "subsets_examined": len(records),
        "subsets": records,
        "fitting": {k: [r["kept"] for r in v] for k, v in fitting.items()},
        "maximal_fitting": {k: [r["kept"] for r in v]
                            for k, v in maximal.items()},
        "maximal_fitting_records": maximal,
    }


def ledger(sections, *, width_mm: float, height_mm: float, regular, bold,
           floors=FLOORS, mandatory_claims=None) -> dict:
    """``container_back_panel_line_ledger/1.0`` — §AB1(e) in one record."""
    supplied = list(sections or [])
    costs = section_costs(supplied, width_mm=width_mm, regular=regular,
                          bold=bold, floors=floors,
                          mandatory_claims=mandatory_claims)
    enumerated = subsets(supplied, width_mm=width_mm, height_mm=height_mm,
                         regular=regular, bold=bold, floors=floors,
                         mandatory_claims=mandatory_claims)
    whole = {str(f): _layout(supplied, width_mm, height_mm, f, regular, bold)
             for f in floors}
    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "surface": bp.SURFACE,
        "budget_mm": [round(float(width_mm), 3), round(float(height_mm), 3)],
        "budget_note": BUDGET_NOTE,
        "mandatory_note": MANDATORY_NOTE,
        "floors_pt": list(floors),
        "floor_provenance": {str(f): FLOOR_PROVENANCE.get(f) for f in floors},
        "capacity": {str(f): capacity(width_mm=width_mm, height_mm=height_mm,
                                      size_pt=f, sections=len(supplied),
                                      regular=regular, bold=bold)
                     for f in floors},
        "sections": costs,
        "as_supplied": {str(f): {
            "fits": whole[str(f)]["fits"],
            "lines_required": whole[str(f)]["lines_required"],
            "height_required_mm": whole[str(f)]["height_required_mm"],
            "overflow_mm": whole[str(f)]["overflow_mm"],
        } for f in floors},
        "subsets": enumerated,
        "codes": list(enumerated["codes"]),
        "measured_by": "apps.ire.back_panel_ledger.ledger",
    }


__all__ = ["BUDGET_NOTE", "MANDATORY_NOTE", "MANDATORY_STATES",
           "MAX_SECTIONS_FOR_EXHAUSTIVE", "NOTHING_FITS", "RULE", "SCHEMA",
           "TOO_MANY_SECTIONS", "UNMEASURED", "capacity", "ledger",
           "mandatory_state", "section_costs", "subsets"]
