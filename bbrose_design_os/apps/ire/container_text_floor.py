"""§W2 — the minimum-text-size rule for a container (``container_text_floor/1.0``).

Four constants disagreed about the smallest type a container may carry, and
the gate was deciding containers with the flat one:

* 5.0 pt — ``visual_quality_gate.THRESHOLDS["typography_min_text_pt"]``, which
  decided the container axis and is now this module's FALLBACK;
* 5.5 pt — ``compose_vector_art._MIN_TEXT_PT``, vector artwork composition;
* 4.5 pt — the two dieline validators;
* the ``container_production_method`` capability table, applied only to
  ``product-name*`` runs.

**The table is right and the flat number is wrong, and the repo already knew
it** (§W2). Minimum legible size is a physical property of how the type is put
onto the substrate: you cannot emboss at 5 pt, and forbidding a 2.0 pt bottom
inkjet code that is standard practice is a FALSE FAIL. §W2 keeps the other
three constants alive in their own domains, and each now names its domain in
its own file — a constant that does not name its domain is a conflation
waiting to happen.

THE RULE:

* (a) THE CAPABILITY TABLE GOVERNS, for ALL runs, not just ``product-name*``,
  matched by the print method recorded for THE SURFACE THE RUN SITS ON. Not
  one global minimum checked against every method: that is what made the 2.0 pt
  inkjet code fail the embossed panel's 8.0 pt limit.
* (b) WHERE THE PRINT METHOD IS UNRECORDED, the flat 5.0 pt applies AS A
  FALLBACK, and the record SAYS it is a fallback. A fallback reported as a
  measurement is the defect class this programme keeps catching, so the source
  is carried on every single run rather than summarised.
* (d) this is a POLICY CHOICE, not a measurement: ``OWNER_CALIBRATED``.

SCOPE IS THE CONTAINER VIEW. §W2(a) extends the rule from ``product-name*``
runs to all runs — it widens which NAMES are read, not which SURFACES. The
floor is a PRINT legibility floor and the surface strip is a schematic drawn
at diagram scale, so measuring the strip against it fails the container for a
property of its own thumbnail: the sprint-7 finding that read 1.5 pt off a
panel caption. §W1(c) — the strip is a map, do not measure it harder — settles
it. The strip runs are COUNTED here so the exclusion is visible.

Consequence, recorded because it is a real limit and not an achievement: the
back panel's copy is drawn ONLY in the strip today, so ITS legibility is not
measured by this record. §W1 (WI-E) is the work that changes that, and when a
full-scale back panel exists its runs will resolve through BODY_BACK's own
method rather than the hero's.

§BH50(f)(1), OWNER RULED 2026-09-13 (annotation, §AZ0(u) — the paragraphs
above are history; the true-scale panel exists since §W1(a)): THE FLOOR IS
PRODUCT COPY ONLY, SCOPED BY SURFACE. The rule covers the text PRINTED ON THE
PRODUCT, by the surface the composer DECLARES on each run
(``TextRun.print_scope``): the sheet's annotations are out of its scope and
listed with their sizes; schematic depictions of product copy are counted per
surface and never judged (§W1(c)); a surface whose product copy is drawn only
as a depiction is named NOT MEASURED with its floor, and the verdict is None
there — never a pass (§AC6(c), §W1(b), §BH50(f)(5)); an undeclared run is
judged by the inference this record used before (the container view, then the
hero fall-through) and disclosed as such, so a forgotten declaration fails
closed. Before this ruling every run outside a surface group was judged as
BODY_FRONT type, which is how twelve of the sheet's own labels blocked task 52.
The acceptance-side instrument (container_production_method) reads the same
declaration, so one rule has one scope (§BD(c)).

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_text_floor/1.0"

#: §W2(d) — the table is a policy choice about what is manufacturable, not a
#: measurement of this document. The gate must not read a PASS here as
#: manufacturer authority; only VERIFIED_MANUFACTURER_CAPABILITY is that.
STATUS = "OWNER_CALIBRATED"

#: DOMAIN: a container run whose surface has NO print method recorded. §W2(b).
#: It is the old flat gate threshold, kept at its own number and demoted to a
#: fallback — every run carrying it says so in ``floor_source``.
FALLBACK_FLOOR_PT = 5.0

SOURCE_TABLE = "container_production_method/1.0 capability table"
SOURCE_FALLBACK = "FALLBACK — no print method recorded for this surface"
#: [his correction of 2026-10-07, which replaced his final goal's C5 4 pt for the ingredients and warnings alone] the
#: floor of a label's every run where no confirmed print method holds it higher
SOURCE_FINE = "his correction of 2026-10-07: a label shrinks evenly to 3 pt"
#: §Y1(d) — a floor the ZONE raised above what the table requires. It is still
#: table-derived in the sense that the table set the minimum the zone had to
#: beat, but it is NOT the table's number, and `floor_source` must be able to
#: say so. A zone may only ever move a floor UP (§Y1(a)); a zone value below
#: the table is refused and recorded, and a run governed by that refusal
#: reports SOURCE_TABLE, because the table value is what is actually in force.
SOURCE_ZONE_TIGHTENED = (
    "container_production_method/1.0 capability table, TIGHTENED by the zone")

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §W2 — the container_production_method "
    "capability table governs minimum text size, on ALL runs and not only "
    "product-name*, matched by the print method recorded for the surface the "
    "run sits on. Where the method is unrecorded the flat 5.0 pt applies AS A "
    "FALLBACK and the record says so. Status OWNER_CALIBRATED: this is a "
    "policy choice, not a measurement, and a PASS here is not manufacturer "
    "authority. §BH50(f)(1): the rule covers the text PRINTED ON THE PRODUCT, "
    "by the surface the composer declares on each run; the sheet's "
    "annotations are out of its scope and listed; schematic depictions of "
    "product copy are counted and not judged; a surface whose product copy "
    "is drawn only as a depiction is not measured and blocks; an undeclared "
    "run is judged by name and structure as before and disclosed."
)

#: §BH50(f)(1) — how a judged run came into scope
SCOPE_DECLARED = "DECLARED"
SCOPE_INFERRED = "INFERRED_FROM_NAME_AND_STRUCTURE"
SCOPE = ("§BH50(f)(1): text printed on the product, by the surface the "
         "composer declares; annotations out of scope and listed; depictions "
         "counted, not judged; a surface with depicted copy and no printed run "
         "not measured; undeclared runs judged by inference and disclosed")

_NOT_MEASURED_REASON = (
    "§BH50(f)(1) — product copy on these surfaces is drawn only as a "
    "schematic depiction on this document, so its printed size is not "
    "measured here and the surface blocks until a print-size drawing of it "
    "exists (§AC6(c), §W1(b)): "
)

_STRIP_EXCLUSION = (
    "the surface strip is a schematic at diagram scale; a print legibility "
    "floor applied to it fails the container for a property of its own "
    "thumbnail (§W1(c))"
)

_AMBIGUOUS_REASON = (
    "a surface carries print methods with DIFFERENT minimum text sizes, and "
    "§W2(a) matches a run to its SURFACE rather than to its zone, so this "
    "record cannot say which floor governs a given run on it. Taking the "
    "larger would invent the false FAIL §W2 was written to stop; taking the "
    "smaller would pass type that one of the recorded methods cannot hold. "
    "No floor is supplied, the axis stays UNMEASURED and blocking, and the "
    "case goes to the owner. Surfaces affected: "
)


def surface_floors(methods_record) -> dict:
    """surface → the floor its recorded print methods impose.

    ``{"floor_pt": float|None, "methods": [...], "ambiguous": bool}``. A
    surface with several methods that AGREE is not ambiguous; only distinct
    floors are, because only then does it matter which zone a run sits in.

    §AA3(a) — each method also carries the STAGE that supplied it, and the
    surface carries whether every one of them was confirmed. This function used
    to copy four keys out of each method and drop the rest, which meant the
    authority the builder had already recorded was discarded at exactly the
    boundary where the floor is decided: everything downstream was then
    structurally unable to tell a `propose_zones` proposal from a
    confirmation. The information was never missing; it was being thrown away.
    """
    from apps.ire.container_method_provenance import is_confirmed, method_stage
    from apps.ire.container_production_method import ORIGIN_ZONE_TIGHTENED

    by_surface: dict[str, list[dict]] = {}
    for method in (methods_record or {}).get("methods") or []:
        floor = method.get("minimum_text_size_pt")
        if floor is None:
            continue
        stage = method_stage(method)
        for surface in method.get("target_surfaces") or []:
            if surface is None:
                continue
            by_surface.setdefault(str(surface), []).append({
                "method_id": method.get("method_id"),
                "method_type": method.get("method_type"),
                "floor_pt": float(floor),
                # §Y1(d) — carried per method so the run-level floor_source can
                # distinguish a table floor from one a zone raised.
                "floor_origin": method.get("minimum_text_size_source"),
                # §AA3(a) — and WHO supplied the method the row was read from.
                # `floor_origin` says which value won between zone and table;
                # `method_stage` says whether the table was consulted about a
                # method anybody confirmed. Two different questions that read
                # as one when only the first is recorded.
                "method_stage": stage,
                "method_confirmed": is_confirmed(stage),
            })

    resolved = {}
    for surface, methods in by_surface.items():
        distinct = sorted({m["floor_pt"] for m in methods})
        resolved[surface] = {
            "floor_pt": distinct[0] if len(distinct) == 1 else None,
            "ambiguous": len(distinct) > 1,
            # True when AT LEAST ONE method's floor on this surface was raised
            # by its zone. Where methods agree on the number this is still the
            # honest label: some of that agreement was bought by a tightening.
            "zone_tightened": any(m.get("floor_origin") == ORIGIN_ZONE_TIGHTENED
                                  for m in methods),
            # §AA3 — one unconfirmed method is enough. The floor is resolved
            # across all of them, so a surface is only as confirmed as its
            # least confirmed method.
            "method_confirmed": all(m["method_confirmed"] for m in methods),
            "method_stages": sorted({m["method_stage"] for m in methods}),
            "methods": sorted(methods, key=lambda m: str(m["method_id"])),
        }
    return resolved


def measure_text_floor(doc, methods_record=None) -> dict:
    """§W2 applied to an emitted Document's container view.

    ``methods_record`` absent, empty, or silent about a surface all mean the
    same thing under §W2(b) — no print method is recorded — and all take the
    disclosed fallback. There is no third state to invent: the owner ruled
    what happens when the method is unknown.
    """
    from apps.ire.compose_container import HERO_SURFACE
    from apps.ire.container_typography_metrics import container_view_text_runs

    from apps.ire.graph import (DEPICTION_OF_PRODUCT_COPY, PRINTED_ON_PRODUCT)

    floors = surface_floors(methods_record)
    runs, strip = container_view_text_runs(doc)
    # [his correction of 2026-10-07: "Shrink the whole label evenly ... Floor: 3 pt."] the back panel's label runs, by
    # the names its own record gives them — every one, its copy, headings and fine print (his final goal's 4 pt was for
    # the fine print alone)
    from apps.ire import back_panel as _bp
    fine_runs = {"back-panel-%s-%s-%s" % (e["section"], e["role"], e["order"])
                 for e in ((doc.metadata or {}).get(_bp.SCHEMA) or {}).get("lines") or []}

    # §BH50(f)(1): the composer's declaration decides scope. A declared
    # printed run is judged at its DECLARED surface whatever its name or
    # position; a declared annotation leaves scope and is listed; a declared
    # depiction is counted per surface and never judged. An undeclared run
    # keeps the inference below (the container view, then the hero
    # fall-through) and is disclosed as such.
    judged: list = []
    annotations: list = []
    depicted: dict = {}
    undeclared: list = []
    declared_runs = 0
    for node, _ in doc.walk():
        if getattr(node, "type", "") != "text":
            continue
        scope = getattr(node, "print_scope", None)
        name = str(getattr(node, "name", "") or "")
        if scope is None:
            undeclared.append(name)
            continue
        declared_runs += 1
        if scope.kind == PRINTED_ON_PRODUCT:
            judged.append((node, scope.surface, SCOPE_DECLARED, scope.zone_id))
        elif scope.kind == DEPICTION_OF_PRODUCT_COPY:
            depicted[scope.surface] = depicted.get(scope.surface, 0) + 1
        else:
            annotations.append({"node_name": name,
                                "size_pt": float(node.size_pt)})
    for node, emitted_surface in runs:
        if getattr(node, "print_scope", None) is not None:
            continue
        # a container-view run is one the emitter did NOT wrap in a Surface-*
        # group, which is the emitter saying it is on the hero surface.
        judged.append((node,
                       emitted_surface if emitted_surface is not None
                       else HERO_SURFACE, SCOPE_INFERRED, None))
    strip_undeclared = sum(1 for n, _ in strip
                           if getattr(n, "print_scope", None) is None)

    measured, ambiguous_surfaces = [], []
    for node, surface, scope_source, zone_id in judged:
        resolved = floors.get(surface)
        if resolved is not None and resolved["ambiguous"]:
            if surface not in ambiguous_surfaces:
                ambiguous_surfaces.append(surface)
            continue
        if resolved is None:
            floor, source, methods = FALLBACK_FLOOR_PT, SOURCE_FALLBACK, []
        else:
            floor = resolved["floor_pt"]
            # §Y1(d) — three-way, not two. A zone that TIGHTENED this floor is
            # neither the table's number nor a fallback, and a record that
            # called it SOURCE_TABLE would be attributing the zone's decision
            # to the capability table.
            source = (SOURCE_ZONE_TIGHTENED if resolved.get("zone_tightened")
                      else SOURCE_TABLE)
            methods = [m["method_type"] for m in resolved["methods"]]
        size = float(node.size_pt)
        if str(getattr(node, "name", "") or "") in fine_runs:
            # [his correction of 2026-10-07] a label's run is measured against the floor its panel shrank to: his 3 pt,
            # unless a confirmed print method holds it higher (``back_panel.label_floor_pt`` — one answer for both)
            label = _bp.label_floor_pt(None if resolved is None else resolved["floor_pt"],
                                       None if resolved is None else resolved.get("method_confirmed"))
            if label < floor:
                floor, source = label, SOURCE_FINE
        measured.append({
            "node_name": str(getattr(node, "name", "") or ""),
            "surface": surface,
            "size_pt": size,
            "floor_pt": floor,
            "floor_source": source,
            "method_types": methods,
            # §AA3(c) — carried on every run, beside the floor it qualifies,
            # for the same reason §W2(b) carries `floor_source` per run rather
            # than summarising it: a reader looking at one run must not have to
            # go elsewhere to learn that its floor is an assumption.
            #
            # None, NOT False, on a fallback run. There is no method on that
            # surface to be unconfirmed — `floor_source` already says FALLBACK
            # and that is the whole disclosure §W2(b) ruled. False would assert
            # that a method exists and nobody confirmed it, which is a claim
            # about a method that is not there. Presence before value, the same
            # rule the typography axis learned about its own absent flags.
            "method_confirmed": (None if resolved is None
                                 else bool(resolved.get("method_confirmed"))),
            "method_stages": ([] if resolved is None
                              else resolved.get("method_stages") or []),
            "below": size < floor - 1e-9,
            # §BH50(f)(1): how the run came into scope, and the zone the
            # composer placed it in when it said so
            "scope_source": scope_source,
            "zone_id": zone_id,
            # §BH50(f)(2): a placeholder run is judged for its SIZE only; the
            # copy is unwritten and blocks under its own code — never read as
            # printed copy that passes
            "placeholder": "CONTENT_VERIFICATION_REQUIRED" in str(
                getattr(node, "text", "") or ""),
        })

    judged_surfaces = {r["surface"] for r in measured}
    not_measured = []
    for surface, count in sorted(depicted.items()):
        if surface in judged_surfaces:
            continue
        resolved = floors.get(surface)
        not_measured.append({
            "surface": surface,
            "depicted_runs": count,
            "floor_pt": (FALLBACK_FLOOR_PT if resolved is None
                         else resolved["floor_pt"]),
            "floor_source": (SOURCE_FALLBACK if resolved is None
                             else SOURCE_TABLE),
            "reason": "product copy drawn only as a schematic depiction on "
                      "this document; no print-size drawing to measure",
        })

    return {
        "schema_version": SCHEMA,
        "status": STATUS,
        "rule": RULE,
        "runs": measured,
        "below_floor": [r for r in measured if r["below"]],
        # §BH50(f)(1)
        "scope": SCOPE,
        "scope_declared_runs": declared_runs,
        "scope_undeclared_runs": undeclared,
        "out_of_scope_annotations": annotations,
        "depicted_product_copy_by_surface": depicted,
        "surfaces_not_measured": not_measured,
        "fallback_floor_pt": FALLBACK_FLOOR_PT,
        "any_floor_is_a_fallback": any(r["floor_source"] == SOURCE_FALLBACK
                                       for r in measured),
        "surface_floors": floors,
        "ambiguous_surfaces": ambiguous_surfaces,
        # §AA3(a)/(b) — the surfaces whose recorded method no stage confirmed.
        # Only surfaces a RUN was actually resolved against are listed: a
        # surface recorded in the methods record but carrying no type on this
        # document is not a finding about this document.
        "unconfirmed_method_surfaces": sorted(
            {r["surface"] for r in measured if r["method_confirmed"] is False}),
        "method_provenance_by_surface": {
            s: {"confirmed": f.get("method_confirmed"),
                "stages": f.get("method_stages") or []}
            for s, f in floors.items()},
        "runs_examined": len(measured) + sum(
            1 for _n, s, _src, _z in judged
            if (floors.get(s) or {}).get("ambiguous")),
        # depictions declared by the composer and strip runs it did not
        # declare: counted, never judged (§W1(c))
        "surface_strip_runs_excluded": strip_undeclared + sum(depicted.values()),
        "surface_strip_exclusion": _STRIP_EXCLUSION,
        "measured_by": "apps.ire.container_text_floor.measure_text_floor",
    }


def below_floor(record) -> bool | None:
    """Whether any run is under its own floor, or None where §W2(a)'s
    surface-level match could not resolve one, or where the method the floor
    came from is unconfirmed (§AA3(b)).

    Same asymmetry the overlap rule uses: a run found below its floor is a
    positive finding about THAT run and is reported even beside a surface the
    rule could not resolve. False is a universal claim over every run.

    §AA3(b) DOES NOT ADD A THIRD BRANCH HERE, AND THE REASON IS THE FINDING
    ----------------------------------------------------------------------
    An unconfirmed method makes this verdict's FALSE a universal claim of
    legibility resting on a technique that entered the system as a default
    argument value in `make_zone`'s signature, so returning None for it looks
    like the natural reading of §AA3(b). It was built, run, and REVERTED,
    because measuring it showed what it costs: nine §W2 tests flip, and among
    them is `test_the_two_pt_bottom_code_is_not_a_defect` — §W2's own headline
    example, the 2.0 pt bottom inkjet code that is standard practice and whose
    rejection §W2 names as a FALSE FAIL. `OWNER_CONFIRMED` is unreachable by
    construction (`container_method_provenance`, "two constraints live output
    never reaches"), so the branch would make FALSE unreachable for every
    container forever. That is not a small structural change to a record; it
    is a repeal of §W2's PASS branch, and §Q–§AA are closed.

    WHAT THAT LEAVES, STATED RATHER THAN LEFT TO BE NOTICED: the axis blocks
    today, and it blocks for a reason that has nothing to do with the method.
    Measured on the emitted sheet against the LIVE methods record, 34 runs are
    examined and 13 sit under their 5.0 floors. Only FOUR of the 13 are
    artwork: `front-support` 3.4 and `front-net-content` 3.0, which §AA2(b)
    rules stay failing, and their `flat-` twins, which §AA4 puts out of sprint
    12 by name. The other NINE are the review sheet's own annotations — seven
    `panel-label-*` at 2.7, `confirmed-dims` at 2.3, `census-line` at 2.3 —
    measured as printed type because `NON_ARTWORK_TEXT_PREFIXES` covers
    `sheet-`, `swatch-`, `sku`, `reference-`, `spec-` and none of those three.
    Recorded, NOT fixed: §AA4 forbids chained fixes, and widening that tuple
    changes which runs the gate sees, which is a gate change and not WI-N's.
    §BH50(b) (2026-09-13): the owner ruled the floor stands and the design
    moves, so the two product runs are set at 5.0 pt and leave the list with
    their twins; on the emitted sheet the block now rests on the nine
    annotations alone.

    So the coincidence is worse than "an unrelated failure holds the blocker
    up": the load-bearing part of the block is a caption under a diagram. §AA's
    own WI-K precedent one level out — a constraint the pipeline never reaches
    is a constraint nobody has tested, and a blocker held up by sheet furniture
    has not been tested either.

    `TestTheBlockIsCoincidental` in `tests/test_win_method_provenance.py` pins
    that behaviour as it stands, so the open question has an artefact rather
    than a paragraph, and so the day it is ruled on the test says so out loud.

    §BH50(f)(1), 2026-09-16 (annotation, §AZ0(u) — the paragraphs above are
    history): the day came. The owner ruled the annotations out of §W2's
    scope, so the block no longer rests on them, and read with §AC6(c),
    §W1(b) and his (5) the verdict gained the third branch this docstring
    refused: a surface whose product copy is drawn only as a depiction is NOT
    MEASURED, and the verdict is None there. That does not repeal the PASS
    branch — a document whose every surface with product copy carries a
    printed run still reads False, and the 2.0 pt bottom-code test above
    still reads False — and it is not §AA3(b)'s branch, which stays where
    this docstring left it. On task 52 the verdict reads None, because the
    bottom code is drawn only in the bottom diagram.
    """
    if record["below_floor"]:
        return True
    if record["ambiguous_surfaces"] or record.get("surfaces_not_measured"):
        return None
    return False


def unresolved_reason(record) -> str:
    """Why ``below_floor`` came back None, and what else is wrong with the
    floors while the reader is here.

    The cause of None is ambiguity and ONLY ambiguity — `below_floor` has two
    branches, not three, and its docstring says at length why §AA3(b) did not
    become the third. So the second clause here is not a second cause. It is a
    disclosure riding along: when the axis is already unmeasured, the reader is
    being handed a sentence about these floors, and a sentence about floors
    that omitted "and nobody confirmed the method three of them came from"
    would be true and incomplete in the way this programme keeps catching.

    It is joined with "ALSO:" rather than "and" so the two never read as one
    finding, and it is emitted after the cause so the cause is never displaced
    by it. When ambiguity is absent this function is not called at all (see
    `container_typography_metrics`, which asks only when the verdict is None) —
    the unconfirmed surfaces are still reported there, on the record, under
    `size_floor_unconfirmed_method_surfaces`.
    """
    from apps.ire.container_method_provenance import UNCONFIRMED_NOTE

    reasons = []
    for nm in record.get("surfaces_not_measured") or []:
        reasons.append(_NOT_MEASURED_REASON + f"{nm['surface']} (floor "
                       f"{nm['floor_pt']} pt, {nm['depicted_runs']} depicted "
                       f"run{'s' if nm['depicted_runs'] != 1 else ''})")
    if record["ambiguous_surfaces"]:
        reasons.append(_AMBIGUOUS_REASON + ", ".join(
            f"{s} ({'/'.join(str(m['method_type']) for m in record['surface_floors'][s]['methods'])}"
            f" → {'/'.join(str(m['floor_pt']) for m in record['surface_floors'][s]['methods'])} pt)"
            for s in record["ambiguous_surfaces"]))
    unconfirmed = record.get("unconfirmed_method_surfaces") or []
    if unconfirmed:
        reasons.append(UNCONFIRMED_NOTE + ", ".join(
            f"{s} ("
            f"{'/'.join(str(m['method_type']) for m in record['surface_floors'][s]['methods'])}"
            f" — {'/'.join(record['surface_floors'][s].get('method_stages') or [])})"
            for s in unconfirmed))
    return "  ALSO: ".join(reasons)


__all__ = ["FALLBACK_FLOOR_PT", "RULE", "SCHEMA", "SOURCE_FALLBACK",
           "SOURCE_TABLE", "SOURCE_ZONE_TIGHTENED", "STATUS", "below_floor",
           "measure_text_floor", "surface_floors", "unresolved_reason"]
