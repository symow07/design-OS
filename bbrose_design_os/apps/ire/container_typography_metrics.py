"""VQR-4 — emitted typography metrics (``container_typography_metrics/1.0``).

The last contract ``visual_quality_gate`` reads with nothing producing it.
Until this module the typography axis could not be measured at all — and
worse, a record supplying only ``min_text_pt`` PASSED it, because the three
defect flags were read with ``.get()`` and an absent flag is False. The axis
was asserting "not clipped, not overlapping, no placeholder" about three
things nobody had looked at. That defect is fixed in the gate; this module
supplies the half of the contract that can honestly be measured.

WHAT IS BEING MEASURED IS THE CONTAINER, NOT THE SHEET. The emitted document
is a presentation sheet: a container view at container scale, plus a SURFACE
STRIP that draws the other surfaces as a schematic map. Everything the
emitter wraps in a ``Surface-*`` group is in that strip — ``_surface_panels``
skips ``HERO_SURFACE``, so a wrapper IS the strip — and the strip's type is
sized for the diagram (``panel-{surf}-label`` is the surface's own NAME at
``3.0 * k``, reaching 1.5 pt at the emitted scale factor). The gate's floor
is a PRINT legibility floor, the same concern the dieline validators enforce
at 4.5 pt. Measuring a schematic caption against a print floor would fail
the container for a property of the thumbnail — the mirror of the false PASS
this module exists to remove. So the strip is out of scope and the record
SAYS it is out of scope, with the runs counted, because the back panel's
copy lives only there and its absence from the measurement must be visible
rather than silent.

The gate reads five fields, and every one of them is now measured — three of
them only because an owner ruled, never because a session wanted a green axis:

* ``min_text_pt`` — MEASURED. The smallest ``size_pt`` among container-view
  artwork runs. Sheet furniture is excluded by the same prefix set
  ``validate_typography_hierarchy`` and ``front_hierarchy_runs`` use. It
  stays a bare NUMBER: the four disagreeing minimum-size constants were
  ruled by §W2, and the verdict they now produce is a separate field.
* ``below_size_floor`` — MEASURED SINCE §W2, by ``container_text_floor``. The
  floor is no longer one flat number the gate owned; it is the
  ``container_production_method`` capability table, read per RUN through the
  print method recorded for that run's SURFACE, with a disclosed 5.0 pt
  fallback where no method is recorded. A single ``min_text_pt`` scalar
  cannot decide a per-run floor, which is why the comparison left the gate.
* ``clipped`` — MEASURED, and complete for text. Two mechanisms can cut a
  run off: the page edge, and a clip path on an ANCESTOR — ``graph.Group``
  and ``graph.Image`` carry ``clip``, ``graph.TextRun`` does not, so a run
  is clipped by the groups above it or not at all. Both predicates are
  imported (``container_composition_metrics._outside_artboard``,
  ``container_logo_metrics._clip_bbox``) rather than restated, so the three
  records cannot drift about where the edge is.
* ``materially_overlapping`` — MEASURED SINCE §W3. It was absent for the same
  reason ``blocking_overlaps`` was, because it was THE SAME QUESTION asked
  about a second axis: type set over a rule is the front composition working
  as drawn. §W3 ruled both at once — type over type blocks at any opacity,
  type over artwork does not — so the rule lives in ``container_overlap`` and
  both axes read it there. The flag goes absent, and the axis stays
  UNMEASURED, where the rule cannot be applied to a run (§W3(d)).
* ``placeholder_text_present`` — MEASURED SINCE §W5, and the reason it
  changed matters. It was absent because a boolean failing on ANY
  placeholder would have contradicted §B1/§B2, which rule the back-label
  EAN and the distributor identity legitimate and non-gating. §W5 supplied
  the missing half: an ALLOW-LIST of exactly those two, everything else a
  finding naming the run and the text. It did not become measurable because
  a later session got tired of an UNMEASURED axis. §W5(c) forbids reusing
  either ``_PLACEHOLDER_RE`` in this repo — both were written for SPEC
  FIELD VALUES, where "" and "—" are placeholders, and on a container an
  empty run is never drawn and a dash is a RULE.
  §BH50(f)(2), OWNER RULED 2026-09-13 (annotation, §AZ0(u)): the finding
  moved. Placeholder copy is its own blocker — ``container_placeholder_copy``
  builds one record per piece of copy nobody has written and readiness
  carries its codes at acceptance — and this record publishes no placeholder
  field, so the same six pieces are no longer counted a second time as a
  typography failure. The detector below (``measure_placeholder_text``,
  ``copy_bearing_runs``, the allow-list) is unchanged and is that record's
  instrument.

So the record is still deliberately incomplete and the axis stays
UNMEASURED — blocking, which is the honest state — while the facts that ARE
measurable stop being invisible.

EXTENT PROVENANCE TRAVELS WITH THE VERDICT (WI-F). A clipping verdict from
a guessed text box is a guessed verdict, so each reported run states how its
box was obtained and the record republishes the per-role font provenance.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_typography_metrics/1.0"

#: float noise in mm-space geometry, not a placement allowance — matches
#: ``container_logo_metrics`` and ``container_composition_metrics``.
_EPS_MM = 1e-6

#: nothing is permanently unmeasured here any more. §W3 and §W5 supplied the
#: two rulings this record was waiting on; what remains is per-document.

#: §W5(a) — the ONLY placeholders permitted on a container, matched on the
#: RUN NAME because what the owner permitted is a ROLE, not a form of words.
#: Neither is drawn by ``compose_container`` today; keying the list to the
#: ruling rather than to the current emitter means drawing one later does not
#: silently fail the axis, and a run named anything else still fails loudly.
#:
#: §W5(d): ADDING TO THIS LIST IS AN OWNER RULING THROUGH THE CLEARANCE
#: SHEET. AN EXECUTOR MAY NOT EXTEND IT.
PERMITTED_PLACEHOLDER_RUNS = {
    "back-label-ean":
        "OWNER_BLOCKER_CLEARANCE.md §B1 — EAN ownership is unconfirmed, so "
        "the back-label draft carries a clearly-marked placeholder EAN; "
        "ruled explicitly NOT to gate artwork.",
    "distributor-identity":
        "OWNER_BLOCKER_CLEARANCE.md §B2 — no responsible person/distributor "
        "yet; the field renders as a marked placeholder and the owner "
        "supplies the identity later.",
}

#: what makes drawn text a PLACEHOLDER on a container. §W5(c) forbids reusing
#: ``print_data._PLACEHOLDER_RE`` or ``production_readiness._PLACEHOLDER_RE``
#: and forbids answering this with a better regex. Both were written for spec
#: FIELD VALUES, where an empty string and a lone dash ARE placeholders — on a
#: container an empty run is never drawn and a dash is a RULE, so either regex
#: would fail every container carrying a divider. This is instead a short list
#: of tokens that are never product copy.
_PLACEHOLDER_MARKERS = (
    "placeholder", "lorem ipsum", "tbd", "todo", "to be confirmed",
    "to be determined", "to be advised", "coming soon", "sample text",
    "xxx", "content_verification_required",
)

#: the one token the repo's two definitions DISAGREE about — matched by
#: ``print_data`` and not by ``production_readiness`` — and which §W5 rules
#: nothing about: it ruled which placeholders are PERMITTED, not what counts
#: as one at the margin. A run whose only placeholder evidence is this token
#: therefore leaves ``placeholder_text_present`` ABSENT, which keeps the axis
#: UNMEASURED and blocking, and the reason names the run. Picking a side
#: between two committed definitions by coin-flip is not a measurement.
_CONTESTED_PLACEHOLDER_MARKERS = ("n/a",)

#: the surface strip's own furniture — ``panel-BODY_BACK-label`` is the
#: surface's NAME, ``panel-{surf}-code-batch`` is the diagram's caption for a
#: code area. The emitter authored these words about the diagram; they are not
#: copy from the product record and are not drawn on the container.
_STRIP_FURNITURE_PREFIX = "panel-"

_PLACEHOLDER_POLICY = (
    "OWNER_BLOCKER_CLEARANCE.md §W5 — permitted placeholders are EXACTLY the "
    "back-label EAN (§B1) and the distributor identity (§B2), matched on the "
    "run name because what was permitted is a ROLE. Any other placeholder "
    "text drawn on the container fails the axis, naming the run and the "
    "text. Scope is the copy, not the container view: the strip's own "
    "furniture is excluded, but back-panel copy emitted into the strip is "
    "still container copy. Extending the permitted list is an owner ruling "
    "(§W5(d)); an executor may not."
)

_SURFACE_STRIP_EXCLUSION = (
    "the emitter draws every non-hero surface as a schematic panel in the "
    "surface strip, at a diagram scale — panel-{surface}-label is the "
    "surface's own name, not container copy. The gate's floor is a print "
    "legibility floor, so measuring the strip against it would fail the "
    "container for a property of the thumbnail. §BH50(f)(1): the back "
    "panel's copy is measured on the true-scale panel where one exists "
    "(§W1(a)); a surface whose product copy is drawn only as a depiction is "
    "named NOT MEASURED in the size-floor record and blocks."
)


def container_view_text_runs(doc) -> tuple[list, list]:
    """``(container_view, surface_strip)`` — live text runs paired with the
    surface the emitter placed each on.

    The strip half is returned rather than discarded so the record can COUNT
    what it excluded: a limit nobody can see is indistinguishable from a
    limit nobody has.

    Two exclusions, neither invented here:

    * SHEET FURNITURE — a spec label, a swatch caption, an SKU — by
      ``NON_ARTWORK_TEXT_PREFIXES``, the set two other readers already use,
      so three of them cannot disagree about what counts as type;
    * THE SURFACE STRIP — any run the emitter wrapped in a ``Surface-*``
      group. ``_surface_panels`` builds those wrappers and skips
      ``HERO_SURFACE``, so the wrapper is the emitter saying "this is the
      schematic, not the container view".

    §W1's full-scale panel is wrapped in a ``TrueScaleSurface-*`` group and is
    NOT excluded: it is the printed surface, so it is container view and it
    carries its own surface name rather than falling through to the hero. That
    pairing is what makes §W2's per-surface floor reach it — a true-scale run
    returned with surface None would be judged against the FRONT's print
    method, which is a different physical process.
    """
    from apps.ire.container_composition_metrics import _emitted_surface
    from apps.ire.container_motif_fidelity import NON_ARTWORK_TEXT_PREFIXES

    parents = {id(node): parent for node, parent in doc.walk()}
    runs, strip = [], []
    for node, _ in doc.walk():
        if getattr(node, "type", "") != "text":
            continue
        if str(getattr(node, "name", "") or "").startswith(
                NON_ARTWORK_TEXT_PREFIXES):
            continue
        surface, true_scale = _emitted_surface(node, parents)
        schematic = surface is not None and not true_scale
        (strip if schematic else runs).append((node, surface))
    return runs, strip


def copy_bearing_runs(doc) -> list:
    """Every run drawn from the PRODUCT RECORD — container view and strip.

    Deliberately a DIFFERENT scope from ``container_view_text_runs``, and the
    record says so rather than leaving two scopes to be discovered. The size
    floor is a PRINT legibility floor, so measuring the strip's diagram scale
    against it fails the container for a property of its own thumbnail — the
    sprint-7 finding that read ``min_text_pt: 1.5`` off a panel caption. A
    placeholder is not a scale property: "TBD" is TBD at any size, and the
    back panel's copy is real product copy that today is drawn ONLY in the
    strip. So the placeholder check follows the copy and excludes only the
    strip's own furniture.
    """
    from apps.ire.container_motif_fidelity import NON_ARTWORK_TEXT_PREFIXES

    runs = []
    for node, _ in doc.walk():
        if getattr(node, "type", "") != "text":
            continue
        name = str(getattr(node, "name", "") or "")
        if name.startswith(NON_ARTWORK_TEXT_PREFIXES):
            continue
        if name.startswith(_STRIP_FURNITURE_PREFIX):
            continue
        runs.append(node)
    return runs


def _marker_in(text: str, markers) -> str | None:
    low = text.lower()
    return next((m for m in markers if m in low), None)


def measure_placeholder_text(doc) -> dict:
    """§W5 — placeholder text drawn on the container.

    Three outcomes, not two. ``present`` is None when the only placeholder
    evidence found is the CONTESTED token, because §W5 ruled which
    placeholders are permitted and did not rule that margin; the caller then
    leaves the gate field absent and the axis stays UNMEASURED and blocking.
    A definite finding beside a contested run still reports True — an absent
    measurement does not un-see a defect found next to it.
    """
    findings, permitted, contested = [], [], []
    runs = copy_bearing_runs(doc)
    for node in runs:
        name = str(getattr(node, "name", "") or "")
        text = str(getattr(node, "text", "") or "")
        marker = _marker_in(text, _PLACEHOLDER_MARKERS)
        entry = {"node_name": name, "text": text, "marker": marker}
        if marker is not None:
            ruling = next((r for run, r in PERMITTED_PLACEHOLDER_RUNS.items()
                           if name.startswith(run)), None)
            if ruling is not None:
                permitted.append({**entry, "permitted_by": ruling})
            else:
                findings.append(entry)
            continue
        disputed = _marker_in(text, _CONTESTED_PLACEHOLDER_MARKERS)
        if disputed is not None:
            contested.append({**entry, "marker": disputed})
    return {
        "present": True if findings else None if contested else False,
        "findings": findings,
        "permitted": permitted,
        "contested": contested,
        "runs_examined": len(runs),
    }


def _contested_reason(contested) -> str:
    return (
        "placeholder text was found, and this repo's two committed "
        "definitions DISAGREE about it: print_data._PLACEHOLDER_RE matches "
        "'N/A' and production_readiness._PLACEHOLDER_RE does not. §W5 ruled "
        "which placeholders are PERMITTED (the back-label EAN, the "
        "distributor identity) — it did not rule this margin, and choosing "
        "between two committed definitions by coin-flip is not a "
        "measurement. Runs affected: "
        + ", ".join(f"{c['node_name']} ({c['text']!r})" for c in contested)
        + ". An owner ruling through OWNER_BLOCKER_CLEARANCE.md settles it.")


def _clipping_ancestor(node, parents, box) -> str | None:
    """The name of the nearest ancestor whose clip path cuts ``box``, or None.

    ``graph.TextRun`` has no ``clip`` of its own — only ``Group`` and
    ``Image`` carry one — so for text the ancestors ARE the clip test, and
    a producer that checked page bounds alone would miss the emitter's own
    ``BACK_DIRECT_PRINT`` clip entirely.
    """
    from apps.ire.container_logo_metrics import _clip_bbox

    x0, y0, x1, y1 = box[0], box[1], box[0] + box[2], box[1] + box[3]
    cur = parents.get(id(node))
    while cur is not None:
        clip = getattr(cur, "clip", None)
        rect = _clip_bbox(clip) if clip else None
        if rect and (x0 < rect[0] - _EPS_MM or y0 < rect[1] - _EPS_MM
                     or x1 > rect[2] + _EPS_MM or y1 > rect[3] + _EPS_MM):
            return str(getattr(cur, "name", "") or "")
        cur = parents.get(id(cur))
    return None


def measure_typography_metrics(doc, methods_record=None) -> dict | None:
    """``container_typography_metrics/1.0`` for an emitted Document, or None
    when it carries no container-view artwork text.

    None rather than a record of zeros, as in the logo and composition
    producers: ``min_text_pt`` over nothing has no value, and a record
    asserting nothing is clipped when nothing was drawn is a measurement of
    nothing. A container with no type is a composition finding, not a
    typography one.

    ``methods_record`` is ``container_production_method/1.0``, which §W2 made
    the authority on the size floor. Omitting it is not an error and not an
    unmeasured state — §W2(b) ruled what happens when no print method is
    recorded, and every run then carries the 5.0 pt fallback WITH its source.
    """
    from apps.ire.container_composition_metrics import (_bbox,
                                                        _outside_artboard)
    from apps.ire.container_overlap import (blocking_overlap_count,
                                            measure_text_overlaps,
                                            unmeasurable_reason)
    from apps.ire.container_text_floor import (below_floor, measure_text_floor,
                                               unresolved_reason)
    from apps.ire.text_metrics import (metrics_provenance,
                                       resolve_metric_faces,
                                       resolve_role_metrics)

    runs, strip = container_view_text_runs(doc)
    if not runs:
        return None

    parents = {id(node): parent for node, parent in doc.walk()}
    role_metrics = resolve_role_metrics(resolve_metric_faces(doc.metadata))
    measured, clipped = [], []
    for node, _ in runs:
        box = _bbox(node, role_metrics)
        entry = {
            "node_name": str(getattr(node, "name", "") or ""),
            "size_pt": round(float(node.size_pt), 3),
            "font_role": node.font,
            "extent_source": box[4] if box else "unmeasured",
        }
        if box is not None:
            reasons = []
            if _outside_artboard(box, doc.page_w, doc.page_h):
                reasons.append("page_bounds")
            ancestor = _clipping_ancestor(node, parents, box)
            if ancestor is not None:
                reasons.append(f"clip_path:{ancestor}")
            if reasons:
                entry["box_mm"] = [round(v, 3) for v in box[:4]]
                entry["clip_findings"] = reasons
                clipped.append(entry)
        measured.append(entry)

    smallest_view = min(e["size_pt"] for e in measured)
    # §BH50(f)(2): placeholder copy is its own blocker (container_placeholder_copy/1.0);
    # no placeholder field is read or published by this record
    overlaps = measure_text_overlaps(doc)
    blocking = blocking_overlap_count(overlaps)
    floor = measure_text_floor(doc, methods_record)
    under = below_floor(floor)
    # §BH50(f)(1): the smallest type is read over the runs the floor JUDGES —
    # the copy printed on the product — with the sheet's annotation minimum
    # published beside it under its own name, so the number his page prints
    # next to rule 2 is the product's and says so. On an undeclared document
    # the judged set is the container view, as before.
    judged_sizes = [r["size_pt"] for r in floor["runs"]]
    judged_names = {r["node_name"] for r in floor["runs"]}
    smallest = min(judged_sizes) if judged_sizes else smallest_view
    annotation_sizes = [a["size_pt"] for a in
                        floor.get("out_of_scope_annotations") or []]
    unmeasured, reasons = [], {}
    if blocking is None:
        unmeasured.append("materially_overlapping")
        reasons["materially_overlapping"] = unmeasurable_reason(overlaps)
    if under is None:
        unmeasured.append("below_size_floor")
        reasons["below_size_floor"] = unresolved_reason(floor)
    return {
        "schema_version": SCHEMA,
        "min_text_pt": smallest,
        # §BH50(f)(1): the smallest sheet annotation, out of §W2's scope
        "min_annotation_pt": (min(annotation_sizes) if annotation_sizes
                              else None),
        "clipped": bool(clipped),
        **({"materially_overlapping": blocking > 0}
           if blocking is not None else {}),
        **({"below_size_floor": under} if under is not None else {}),
        "size_floor_rule": floor["rule"],
        "size_floor_status": floor["status"],
        "size_floor_runs": floor["runs"],
        "runs_below_size_floor": floor["below_floor"],
        "size_floor_is_a_fallback": floor["any_floor_is_a_fallback"],
        "size_floor_by_surface": floor["surface_floors"],
        "size_floor_unresolved_surfaces": floor["ambiguous_surfaces"],
        # §BH50(f)(1): the scope, stated on the record
        "size_floor_scope": floor["scope"],
        "size_floor_declared_runs": floor["scope_declared_runs"],
        "size_floor_scope_undeclared_runs": floor["scope_undeclared_runs"],
        "size_floor_out_of_scope_annotations": floor["out_of_scope_annotations"],
        "size_floor_depicted_by_surface": floor["depicted_product_copy_by_surface"],
        "size_floor_surfaces_not_measured": floor["surfaces_not_measured"],
        # §AA3(a)/(c) — the axis reports which surfaces are being judged
        # against a floor nobody confirmed, and which stage supplied each
        # method. A floor is not made authoritative by being applied.
        "size_floor_unconfirmed_method_surfaces": floor[
            "unconfirmed_method_surfaces"],
        "method_provenance_by_surface": floor["method_provenance_by_surface"],
        "overlap_rule": overlaps["rule"],
        "blocking_overlap_pairs": overlaps["blocking"],
        "overlaps_over_artwork_not_blocking": overlaps[
            "non_blocking_over_artwork"],
        "overlap_unmeasurable_runs": overlaps["unmeasurable_runs"],
        # §BH50(f)(2): the placeholder fields live in container_placeholder_copy/1.0
        "unmeasured": unmeasured,
        "unmeasured_reasons": reasons,
        "container_view_text_runs": len(measured),
        "smallest_runs": [e for e in measured if e["size_pt"] == smallest
                          and (not judged_names or e["node_name"] in judged_names)],
        "clipped_runs": clipped,
        "clip_definition": "page bounds and any ancestor clip path — a "
                           "TextRun carries no clip of its own",
        "surface_strip_runs_excluded": len(strip),
        "surface_strip_exclusion_reason": _SURFACE_STRIP_EXCLUSION,
        "artboard_mm": [round(doc.page_w, 3), round(doc.page_h, 3)],
        "text_metrics_provenance": metrics_provenance(role_metrics),
        "measured_by": "apps.ire.container_typography_metrics"
                       ".measure_typography_metrics",
    }


__all__ = ["SCHEMA", "container_view_text_runs", "measure_typography_metrics"]
