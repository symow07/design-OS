"""§AA1 — compressed on-pack copy, every cut carrying the source that permits it.

§X2(d) fired with real numbers and §AA1 is it returning: **the copy changes.**
No carton, no leaflet, no wrap, no new zone. This module is the compression,
and it is built the way §AA1(c) requires rather than the way that would have
been quicker — each proposed cut is a record, the record names the permission
and where the permission comes from, and **a cut whose permission cannot be
sourced is not made.** It is recorded ``SOURCE_REQUIRED`` and its section stays
whole. A shorter panel bought by deleting something mandatory is the same
defect as a lower floor wearing different clothes, so the deleting is what has
to be justified, not the keeping.

ITS EFFECT ON EMITTED OUTPUT IS ZERO, AND THE REASON IS WORTH MORE THAN THE
MODULE
------------------------------------------------------------------------------
§AA's rule — when a fix's effect on production output is zero that sentence
goes next to the fix, not in a footnote. Here it is, and it is not incidental:
**there is no back-panel copy in production to compress.**
``apps/pipeline/targets/container/_back_sections_from_record`` supplies real
text for exactly two of its seven sections, ``PRODUCT`` (the product name) and
``NET CONTENT``; ``DESCRIPTION``, ``INGREDIENTS``, ``DIRECTIONS``, ``WARNINGS``
and ``MANUFACTURER`` are all emitted as the placeholder
``CONTENT_VERIFICATION_REQUIRED``. There is no INCI list on a live sheet. There
is nothing to shorten. Compressing copy into that path would mean **writing the
copy first**, which is precisely what §AA1(d) forbids for the two sections it
names and what §AA1(c) forbids in general.

So this module does not touch the composer, does not register a string table
and changes no emitted byte. It measures a document. The only document that
exists is the reconstruction in ``test_wik_back_panel_floor``, and §AA1(d) says
so in the same breath as it makes the reconstruction the authority: 608
characters, the five-character gap to §X2's headline 613 still open and still
stated.

WHAT THE MEASUREMENT SAYS, WHICH IS NOT WHAT §AA1(a) EXPECTED
------------------------------------------------------------------------------
§AA1(a) sets the target as a panel that **fits at its own resolved floor with
every mandatory declaration present**. That target is not reachable on this
panel, and the reason is arithmetic rather than editorial. On the confirmed
``BACK_PRINT_ZONE`` — 22.0 × 42.3 mm, a 19.0 mm column, 39.3 mm of height once
§W1's margins are taken — the panel holds 16 lines at 5.0 pt and 13 at 6.0 pt
once six section gaps are paid for. The five sections that are **not** the
ingredient list, plus the word INGREDIENTS itself, already cost 20 lines at
5.0 pt and 23 at 6.0. The panel is over budget before a single ingredient is
printed, and the ingredient list is the one section no reading of any
regulation lets you shorten to nothing.

``ingredient_ceiling`` states the same thing in the form that closes the
question. Delete every other section outright — PRODUCT, DIRECTIONS, WARNINGS,
MANUFACTURER, NET CONTENT, all of it, an unlawful panel by anyone's reading —
and give the whole surface to the ingredient list. It holds 17 of the 20
ingredients at 5.0 pt and 11 of 20 at 6.0. **There is no on-pack copy that
fits**, because the mandatory part alone does not fit. Compression was worth
measuring and it was not the answer, and knowing which of those two is true is
the only reason to do the measuring.

That is what ``back_panel``'s own docstring anticipated in sprint 8 — *a 30 ml
dropper's back panel that cannot hold a full INCI list at a legible size is a
finding about the product, and the finding is the deliverable* — and §AA1(b)
had already ruled what follows from it: the panel keeps blocking.
``CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL`` is correct and stays. Nothing here
shrinks type, truncates a character, drops a floor or reorders a section past a
cut line.

Pure: no Django, no ORM, no network. Takes the document as an argument, because
a measurement tool that knows one document is a document wearing a tool.
"""
from __future__ import annotations

from apps.ire import back_panel as bp

SCHEMA = "container_on_pack_copy/1.0"

RULE = ("OWNER_BLOCKER_CLEARANCE.md §AA1 — compressed on-pack copy; every cut "
        "records the source that permits it and an unsourced cut is not made")

# --- the four states a proposed cut can be in --------------------------------
#
# §AA1(c) asks for "the reason it is permissible" and rules that an unsourced
# permission means the cut is not made. Splitting the sourced case in two is
# the part that is not in the ruling and is the part that makes the ruling
# answerable: a permission written in a document committed to this repository
# and a permission cited to a regulation that is NOT in this repository are
# both "sourced", and only one of them can be checked by anyone reading this.
# No regulatory text exists anywhere in this repo — that was grepped, not
# assumed — so every regulatory citation below is in the second class.

#: the permission is written in a document committed to this repository, and
#: the record names the file and the clause. Checkable by the owner in one
#: click, and by a future executor with no memory of this sprint.
OWNER_RULING_IN_REPO = "OWNER_RULING_IN_REPO"

#: the permission is cited to a regulation that is NOT in this repository. The
#: citation may well be right. **This executor cannot verify it**, has no copy
#: of the text, and is not qualified to read it if it had one. Recorded as a
#: citation and marked unverified, so that a cut resting on it is visibly
#: resting on it.
CITED_EXTERNAL_UNVERIFIED = "CITED_EXTERNAL_UNVERIFIED"

#: the marker every external citation carries verbatim, as a constant rather
#: than a spelling. Written as prose it drifted on the first draft — one
#: citation said "NEITHER IS IN THIS REPOSITORY", which means the same thing to
#: a reader and a different thing to the test that checks the class is honestly
#: populated. A claim a test depends on should not be a turn of phrase.
NOT_IN_THIS_REPO = "NOT IN THIS REPOSITORY"

#: §AA1(c) by name — no permission was found. The cut is NOT made and the
#: section stays whole. This is the state the ruling exists to produce, and a
#: run of this module that produced none of them would mean the executor had
#: found a source for everything it wanted to delete, which is the failure
#: mode §AA1(c) is written against.
SOURCE_REQUIRED = "SOURCE_REQUIRED"

#: measured and refused. The thing it deletes is mandatory, so the cut is a
#: defect however much height it buys — and it is kept in the table WITH its
#: measured saving, because a refusal is only worth something if you know what
#: was refused. This is the state that stops the table being a list of things
#: that happened to be easy.
REFUSED_MANDATORY = "REFUSED_MANDATORY"

#: the states a cut may be applied in, per candidate. Nothing else is ever
#: applied: SOURCE_REQUIRED and REFUSED_MANDATORY appear in no candidate at all.
STRICT = "STRICT"
CITED = "CITED"
CANDIDATES = {
    STRICT: (OWNER_RULING_IN_REPO,),
    CITED: (OWNER_RULING_IN_REPO, CITED_EXTERNAL_UNVERIFIED),
}

#: a cut whose text is not present in the document it was applied to. Recorded
#: rather than ignored: a cut that silently does nothing is how a compression
#: report comes to overstate itself, and the overstatement is invisible because
#: the number it produces is a real number from a real layout.
TARGET_NOT_PRESENT = "CONTAINER_ON_PACK_CUT_TARGET_NOT_PRESENT"

#: the finding. Not a layout parameter and not a copy problem: the mandatory
#: section alone exceeds the panel, so no arrangement of the rest fits.
CANNOT_HOLD_INCI = "CONTAINER_BACK_PANEL_CANNOT_HOLD_INGREDIENT_LIST"

#: §AA1(e)'s two floors. 5.0 is what ships today — §W2(b)'s disclosed fallback,
#: and also, as WI-K measured, SCREEN_PRINT's capability-table number, which is
#: why the live sheet cannot tell the two apart. 6.0 is what a hot stamp would
#: impose, and it reaches this document only through a hand-written fixture in
#: `test_back_panel.py`. Naming that every time the number is quoted is §AA's
#: standing rule, so it is named here, where the numbers are produced.
FLOOR_LIVE_PT = 5.0
FLOOR_HOT_STAMP_PT = 6.0
FLOORS = (FLOOR_LIVE_PT, FLOOR_HOT_STAMP_PT)

FLOOR_PROVENANCE = {
    FLOOR_LIVE_PT: "what ships today — §W2(b)'s disclosed fallback, and "
                   "identically SCREEN_PRINT's capability-table minimum, which "
                   "is why no live sheet distinguishes them (WI-K)",
    FLOOR_HOT_STAMP_PT: "FIXTURE — reaches this document only through the "
                        "hand-written HOT_STAMP methods record in "
                        "apps/ire/tests/test_back_panel.py, not from any "
                        "confirmed manufacturing capability (§AA precedent)",
}


# --- the cuts ----------------------------------------------------------------
#
# One mechanism for all of them: an exact substring of one section's text,
# replaced by an exact string. Expressed that way a cut is auditable by
# reading it — there is no rule to run in your head to know what comes off —
# and a cut that no longer matches its document announces itself instead of
# quietly saving nothing.

CUTS = (
    {
        "cut_id": "DIRECTIONS_SHORTENED",
        "section": "DIRECTIONS",
        "removes": " to cleansed skin",
        "replacement": "",
        "what": "the phrase 'to cleansed skin' from the directions of use",
        "permission": "§AA1(a) licenses 'DIRECTIONS shortened' by name. The "
                      "shortened form is still an instruction on use; what "
                      "comes off is the preparatory step, not the dose or the "
                      "frequency.",
        "source": "OWNER_BLOCKER_CLEARANCE.md §AA1(a)",
        "source_state": OWNER_RULING_IN_REPO,
        "residual_risk": "the owner licensed shortening, not this wording. If "
                         "'to cleansed skin' is load-bearing for the product's "
                         "safety assessment it is not the executor's to remove "
                         "and this cut should be reclassified SOURCE_REQUIRED.",
    },
    {
        "cut_id": "INCI_AQUA_GLOSS",
        "section": "INGREDIENTS",
        "removes": "AQUA (WATER)",
        "replacement": "AQUA",
        "what": "the English gloss on the first INCI name",
        "permission": "AQUA is the INCI name; '(WATER)' is a common-name gloss "
                      "alongside it. An ingredient list stated in INCI is "
                      "stated in INCI with or without the gloss.",
        "source": "cited to Regulation (EC) No 1223/2009 Art. 19(1)(g) and "
                  "Art. 33 (the common ingredient nomenclature glossary). "
                  + NOT_IN_THIS_REPO + " — neither article, nor the glossary.",
        "source_state": CITED_EXTERNAL_UNVERIFIED,
        "residual_risk": "measured saving is zero lines at both floors, so "
                         "this cut costs a verification and buys nothing. It "
                         "is kept in the table because that is the finding.",
    },
    {
        "cut_id": "NET_CONTENT_METRIC_ONLY",
        "section": "NET CONTENT",
        "removes": "30 ml / 1.01 fl. oz.",
        "replacement": "30 ml",
        "what": "the US customary declaration beside the metric one",
        "permission": "the metric declaration is the one an EU/UK panel must "
                      "carry; 'fl. oz.' is there for a market this container "
                      "has no confirmed distribution into (§AA's B1/B2 "
                      "distributor question is still open).",
        "source": "cited to Regulation (EC) No 1223/2009 Art. 19(1)(c). "
                  + NOT_IN_THIS_REPO + ". The distribution premise is not "
                  "sourced at all — no confirmed market list exists here "
                  "either.",
        "source_state": CITED_EXTERNAL_UNVERIFIED,
        "residual_risk": "if the product ships to the US this cut is a "
                         "labelling defect in the other direction, and the "
                         "repo cannot say whether it does.",
    },
    {
        "cut_id": "PRODUCT_NAME_ONCE_PER_CONTAINER",
        "section": "PRODUCT",
        "removes": "Rose Damascena Serum",
        "replacement": "",
        "what": "the whole PRODUCT section, on the ground that the front "
                "already carries the name",
        "permission": "NOT ESTABLISHED. That a declaration may appear once per "
                      "container rather than once per panel is an inference "
                      "this executor made and could not source. It is exactly "
                      "the kind of inference §AA1(c) is written against.",
        "source": None,
        "source_state": SOURCE_REQUIRED,
        "residual_risk": "not applied; the section stays whole and costs its "
                         "3 lines at 5.0 pt.",
    },
    {
        "cut_id": "WARNINGS_TO_MANDATORY_MINIMUM",
        "section": "WARNINGS",
        "removes": " Discontinue use if irritation occurs.",
        "replacement": "",
        "what": "the sentence that reads as advisory rather than as a "
                "required precaution",
        "permission": "NOT ESTABLISHED, and doubly so. Which of these four "
                      "sentences is a required precaution is a regulatory "
                      "question with no source in this repo — and §AA1(d) "
                      "rules that WARNINGS is an OWNER-SUPPLIED string that "
                      "has not been supplied. The text being cut here is the "
                      "sprint-8 probe's reconstruction, not the owner's copy. "
                      "Editing a reconstruction and reporting the saving as a "
                      "copy decision would be inventing twice.",
        "source": None,
        "source_state": SOURCE_REQUIRED,
        "residual_risk": "not applied; the section stays whole and costs its "
                         "7 lines at 5.0 pt.",
    },
    {
        "cut_id": "MANUFACTURER_ADDRESS_ABBREVIATED",
        "section": "MANUFACTURER",
        "removes": ", Great Britain",
        "replacement": "",
        "what": "the country from the responsible person's address",
        "permission": "NOT ESTABLISHED. The responsible person's name and "
                      "address is mandatory and what constitutes a sufficient "
                      "address is not sourceable here. §AA1(d) again: this is "
                      "an owner-supplied string that is still owed.",
        "source": None,
        "source_state": SOURCE_REQUIRED,
        "residual_risk": "not applied; the section stays whole.",
    },
    {
        "cut_id": "INCI_DROP_FRAGRANCE_ALLERGENS",
        "section": "INGREDIENTS",
        "removes": ", CITRONELLOL, GERANIOL, LINALOOL, FARNESOL",
        "replacement": "",
        "what": "the four named fragrance allergens at the end of the list",
        "permission": "REFUSED. This is the largest single saving available "
                      "anywhere in the document and it deletes the one part of "
                      "an ingredient list that exists specifically to be read "
                      "by someone it can harm. Named fragrance allergens are "
                      "declared BECAUSE they are allergens.",
        "source": "cited to Regulation (EC) No 1223/2009 Annex III. "
                  + NOT_IN_THIS_REPO + " — and it does not matter that it is "
                  "not, because the citation is being used to refuse a cut "
                  "rather than to permit one, and a refusal does not need a "
                  "source the way a deletion does.",
        "source_state": REFUSED_MANDATORY,
        "residual_risk": "kept in the table WITH its measured saving. Someone "
                         "will propose this cut; the answer should be a number "
                         "and a refusal, not a silence.",
    },
)


def cuts_by_state(state: str) -> tuple[dict, ...]:
    return tuple(c for c in CUTS if c["source_state"] == state)


# --- applying them -----------------------------------------------------------


def apply_cuts(sections, cut_ids) -> tuple[list[dict], list[dict]]:
    """Apply the named cuts to a copy of ``sections``.

    Returns the new sections and one record per cut, each saying whether it
    actually matched. A cut that did not match is not an error and is not
    silence: ``applied`` is False and the code says why.
    """
    wanted = {c["cut_id"]: c for c in CUTS if c["cut_id"] in set(cut_ids or ())}
    out = [dict(s or {}) for s in sections or []]
    records = []
    for cut_id, cut in ((c["cut_id"], c) for c in CUTS if c["cut_id"] in wanted):
        hit = False
        for section in out:
            if str(section.get("heading", "")) != cut["section"]:
                continue
            text = str(section.get("text", "") or "")
            if cut["removes"] in text:
                section["text"] = text.replace(cut["removes"],
                                               cut["replacement"], 1)
                hit = True
        records.append({
            "cut_id": cut_id,
            "section": cut["section"],
            "source_state": cut["source_state"],
            "applied": hit,
            "codes": [] if hit else [TARGET_NOT_PRESENT],
            "characters_removed": (len(cut["removes"]) - len(cut["replacement"])
                                   if hit else 0),
        })
    return out, records


def candidate(sections, name: str) -> tuple[list[dict], list[dict]]:
    """The document as a named candidate leaves it.

    STRICT applies only permissions written in this repository. CITED also
    applies permissions cited to regulations that are not. Both are measured
    and reported; picking between them is the owner's, and the point of
    reporting both is that the choice is worth a stated number of millimetres
    rather than an argument.
    """
    states = CANDIDATES[name]
    ids = [c["cut_id"] for c in CUTS if c["source_state"] in states]
    return apply_cuts(sections, ids)


# --- measuring ---------------------------------------------------------------


def measure(sections, panel_mm, size_pt: float, *, regular, bold) -> dict:
    """One document, one panel, one floor — ``bp.layout`` plus what §AA1(e)
    asks to be reported in the same breath as the millimetres."""
    width, height = float(panel_mm[0]), float(panel_mm[1])
    record = bp.layout(sections, width, height, size_pt=size_pt,
                       regular=regular, bold=bold)

    # a line budget quoted without the section gaps is a budget nobody can
    # spend. `layout` charges SECTION_GAP_MM between sections, so a six-section
    # document pays five gaps before its first line — 4.0 mm, which at 5.0 pt
    # is very nearly two lines of the sixteen. Both numbers are reported and
    # both are named for what they are: the ungapped one is reachable only by a
    # document with ONE section, which is the construction `ingredient_ceiling`
    # deliberately builds and nothing lawful ever is.
    line_h = record["line_height_mm"]
    count = len(sections or [])
    gapped = record["height_available_mm"] - max(0, count - 1) * bp.SECTION_GAP_MM
    return {
        "size_pt": size_pt,
        "size_provenance": FLOOR_PROVENANCE.get(size_pt),
        "fits": record["fits"],
        "height_required_mm": record["height_required_mm"],
        "height_available_mm": record["height_available_mm"],
        "overflow_mm": record["overflow_mm"],
        "panel_height_that_would_fit_mm": round(
            record["height_required_mm"] + 2 * bp.MARGIN_MM, 3),
        "lines_required": record["lines_required"],
        "sections_supplied": count,
        "section_gaps_paid_mm": round(max(0, count - 1) * bp.SECTION_GAP_MM, 3),
        "lines_the_panel_holds": (int(gapped // line_h + 1e-9)
                                  if line_h else 0),
        "lines_the_panel_holds_in_one_section": (
            int(record["height_available_mm"] // line_h + 1e-9)
            if line_h else 0),
        "characters_supplied": record["characters_supplied"],
        "characters_emitted": record["characters_emitted"],
        "characters_not_emitted": record["characters_not_emitted"],
        "sections": [{"heading": s["heading"],
                      "lines_required": s["lines_required"],
                      "characters_supplied": s["characters_supplied"]}
                     for s in record["sections"]],
        "codes": list(record["codes"]),
    }


def cut_saving(sections, cut, panel_mm, size_pt: float, *, regular,
               bold) -> dict:
    """What ONE cut is worth, measured against the document it is cut from.

    Measured for every cut including the refused one. A refusal whose price
    nobody measured is a preference.
    """
    before = measure(sections, panel_mm, size_pt, regular=regular, bold=bold)
    after_sections, applied = apply_cuts(sections, [cut["cut_id"]])
    after = measure(after_sections, panel_mm, size_pt, regular=regular,
                    bold=bold)
    return {
        "cut_id": cut["cut_id"],
        "section": cut["section"],
        "source_state": cut["source_state"],
        "applied_in_any_candidate": any(
            cut["source_state"] in states for states in CANDIDATES.values()),
        "matched": applied[0]["applied"] if applied else False,
        "lines_saved": before["lines_required"] - after["lines_required"],
        "mm_saved": round(before["height_required_mm"]
                          - after["height_required_mm"], 3),
        "characters_saved": (before["characters_supplied"]
                             - after["characters_supplied"]),
    }


def ingredient_ceiling(inci: str, panel_mm, size_pt: float, *, regular,
                       bold) -> dict:
    """How much of the ingredient list the panel holds with NOTHING else on it.

    The whole surface given over to INGREDIENTS: no product name, no
    directions, no warnings, no responsible person, no net content. An
    unlawful panel by any reading, constructed deliberately, because it is the
    only construction that answers the question §AA1(a) actually asks. If the
    list does not fit even here, no compression of anything else can make the
    document fit, and the target §AA1(a) sets is not reachable by writing.
    """
    parts = [p for p in str(inci).split(", ") if p]
    held = 0
    for count in range(len(parts), 0, -1):
        trial = [{"heading": "INGREDIENTS", "text": ", ".join(parts[:count])}]
        if measure(trial, panel_mm, size_pt, regular=regular,
                   bold=bold)["fits"]:
            held = count
            break
    return {
        "size_pt": size_pt,
        "size_provenance": FLOOR_PROVENANCE.get(size_pt),
        "ingredients_supplied": len(parts),
        "ingredients_held": held,
        "ingredients_that_do_not_fit": len(parts) - held,
        "everything_else_deleted": True,
        "codes": [] if held >= len(parts) else [CANNOT_HOLD_INCI],
    }


def report(sections, panel_mm, *, regular, bold, inci: str | None = None,
           floors=FLOORS) -> dict:
    """§AA1(e) — the fit at BOTH floors, in mm and in characters, against the
    same document, for both candidates, with every cut's source beside it."""
    built = {}
    for name in (STRICT, CITED):
        cut_sections, applied = candidate(sections, name)
        built[name] = {
            "cuts_applied": [r for r in applied if r["applied"]],
            "cuts_that_did_not_match": [r for r in applied if not r["applied"]],
            "fit": {str(f): measure(cut_sections, panel_mm, f, regular=regular,
                                    bold=bold) for f in floors},
        }

    supplied_fit = {str(f): measure(sections, panel_mm, f, regular=regular,
                                    bold=bold) for f in floors}
    ceiling = ({str(f): ingredient_ceiling(inci, panel_mm, f, regular=regular,
                                           bold=bold) for f in floors}
               if inci else {})

    # every cut in the table applied at once, INCLUDING the three that have no
    # source and the one that is refused. Not a candidate, never emitted, and
    # unlawful on its face — measured for one reason: it is the arithmetic
    # ceiling of compression itself. If the document still does not fit when
    # every rule in §AA1(c) has been broken, then no sourcing question and no
    # editorial judgement changes the answer, and the owner is looking at a
    # container decision rather than a copy decision.
    broken, _ = apply_cuts(sections, [c["cut_id"] for c in CUTS])
    no_holds_barred = {
        "what_this_is": "ALL cuts applied — the unsourced ones and the "
                        "refused one too. Never emitted, not a candidate, and "
                        "not lawful. It bounds the question: this is the "
                        "smallest this document gets by cutting.",
        "fit": {str(f): measure(broken, panel_mm, f, regular=regular,
                                bold=bold) for f in floors},
    }

    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "surface": bp.SURFACE,
        "panel_mm": [round(float(panel_mm[0]), 3), round(float(panel_mm[1]), 3)],
        "floors_pt": list(floors),
        "floor_provenance": dict(FLOOR_PROVENANCE),
        "as_supplied": supplied_fit,
        "candidates": built,
        "cuts": [dict(c) for c in CUTS],
        "cut_savings": {str(f): [cut_saving(sections, c, panel_mm, f,
                                            regular=regular, bold=bold)
                                 for c in CUTS] for f in floors},
        "cuts_not_made_for_want_of_a_source": [
            c["cut_id"] for c in cuts_by_state(SOURCE_REQUIRED)],
        "cuts_refused_as_mandatory": [
            c["cut_id"] for c in cuts_by_state(REFUSED_MANDATORY)],
        "every_cut_regardless_of_source": no_holds_barred,
        "ingredient_ceiling": ceiling,
        "finding": FINDING,
    }


FINDING = (
    "Compression was measured, not estimated, and it is not the answer. The "
    "sections that are NOT the ingredient list already exceed the panel on "
    "their own at both floors, and the panel does not hold the full ingredient "
    "list even with every other section deleted. No on-pack copy fits this "
    "surface, so §AA1(a)'s target is not reachable by writing and "
    "CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL stays correct — which is what "
    "§AA1(b) already ruled would happen if a real attempt was made.")
