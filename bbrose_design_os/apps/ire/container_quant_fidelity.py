"""Quantitative container fidelity (Phase 2B-3C, §2-§6).

Measures the EMITTED geometry, but gates an axis ONLY when the selected-concept
visual graph carries a RELIABLE target (§2). For a no-provider first-pass
concept the graph carries almost none, so most axes are UNMEASURED by
construction — never fabricated from INFERRED pixel noise. The axes that CAN
gate today:

* motif coverage — vs a VERIFIED ``decorative_coverage_pct`` target;
* logo zone      — vs a VERIFIED ``logo_zone`` string;
* product-name zone / scale — vs a VERIFIED ``product_name_zone`` string,
  measured against the confirmed PRINT ZONE (never the silhouette, §4).

A reliable MEASURED_FAIL is a PRODUCTION-READINESS finding (it blocks Gate-2
readiness) — it is NOT a reconstruction blocker, so a first-pass all-UNMEASURED
container still reaches Gate 2.

§BH50(f)(5), OWNER RULED 2026-09-13: an UNMEASURED axis here blocks ACCEPTANCE
too — Gate-2 approval, through container_production_readiness
.fidelity_unmeasured, one code per axis, derived at read time — and never the
reconstruction. "Reaches Gate 2" above means the task reaches the gate; it
does not clear it while any of these seventeen is unmeasured. Each stays
blocking as ruled, listed with what measuring it would take in the §BH50(f)
register block.

§BH65(a), OWNER RULED 2026-09-22 — AN AXIS READS ALWAYS AND MEASURES ONLY
AGAINST A VERIFIED TARGET. His words: "it is one that has never taken a
reading, and §BH55(3) does not protect a blank … No threshold is set from them
yet: report what they read."

Before this, every reading in this module was computed INSIDE the
verified-target branch, so an axis with no target reported neither a verdict
nor a number — the file conflated MEASURING with JUDGING. Each axis now carries
``reading`` (what the emitted document actually says) and ``reading_method``
(how it was taken and what it cannot tell you), taken whether or not a target
exists.

NOTHING ELSE MOVES, AND THAT IS THE POINT. ``state``, ``code``, ``counts``,
``overall`` and every existing ``measured``/``target`` are byte-for-byte what
they were: an axis with no VERIFIED target stays UNMEASURED and still blocks
acceptance through §BH50(f)(5). No reader branches on ``reading`` — measured
before this was written: every reader keys on ``state`` (``build_readiness``,
``FIDELITY_REPORTS``) or on ``counts`` (the board row at
``targets/container/__init__.py:729``). A reading is a number for him to rule
a bar from; it is not a bar.

TWO AXES TAKE NO READING AND SAY SO RATHER THAN REPORTING A ZERO.
``cap_orientation`` has no definition — "only the name and its code exist"
(§BH50(f), OWNER_BLOCKER_CLEARANCE.md:21458) — and a definition is his line,
not this module's. ``cap_artwork_zone`` needs a cap or collar artwork zone,
which his own confirmed decision excludes on the products drawn so far.
"""
from __future__ import annotations

import re

from apps.ire.container_fidelity import (MEASURED_FAIL, MEASURED_PASS,
                                         UNMEASURED, UNMEASURED_BLOCKING)
from apps.ire.container_motif_fidelity import _ALL_MOTIF_PREFIXES, _path_bbox

#: shape-aware ink-area factor per emitted mark (a bounding box overcounts an
#: ellipse ~27%, a star ~65%, a hairline tick ~80%) — mirrors geometry_report.
#: This is INK coverage, not the motif's bounding extent.
_INK_AREA_FACTOR = {"circle": 0.785, "ellipse": 0.785, "star": 0.35,
                    "tick": 0.22, "cross": 0.18}

# --- §3/§4/§5/§6 codes -------------------------------------------------------
MOTIF_DENSITY_FAILED = "CONTAINER_MOTIF_DENSITY_FAILED"
MOTIF_COVERAGE_FAILED = "CONTAINER_MOTIF_COVERAGE_FAILED"
MOTIF_POSITION_FAILED = "CONTAINER_MOTIF_POSITION_FAILED"
MOTIF_CONTINUATION_FAILED = "CONTAINER_MOTIF_CONTINUATION_FAILED"
MOTIF_COLOR_RELATIONSHIP_FAILED = "CONTAINER_MOTIF_COLOR_RELATIONSHIP_FAILED"
MOTIF_SCALE_DISTRIBUTION_FAILED = "CONTAINER_MOTIF_SCALE_DISTRIBUTION_FAILED"
MOTIF_ROTATION_DISTRIBUTION_FAILED = "CONTAINER_MOTIF_ROTATION_DISTRIBUTION_FAILED"
LOGO_ZONE_MISMATCH = "CONTAINER_LOGO_ZONE_MISMATCH"
LOGO_SCALE_MISMATCH = "CONTAINER_LOGO_SCALE_MISMATCH"
PRODUCT_NAME_TOO_SMALL = "CONTAINER_PRODUCT_NAME_TOO_SMALL"
PRODUCT_NAME_ZONE_MISMATCH = "CONTAINER_PRODUCT_NAME_ZONE_MISMATCH"
TYPOGRAPHY_HIERARCHY_FAILED = "CONTAINER_TYPOGRAPHY_HIERARCHY_FAILED"
LABEL_DENSITY_FAILED = "CONTAINER_LABEL_DENSITY_FAILED"
FRONT_BACK_RELATIONSHIP_FAILED = "CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED"
FRONT_DOMINANCE_FAILED = "CONTAINER_FRONT_DOMINANCE_FAILED"
CAP_ORIENTATION_FAILED = "CONTAINER_CAP_ORIENTATION_FAILED"
CAP_BODY_COORDINATION_FAILED = "CONTAINER_CAP_BODY_COORDINATION_FAILED"
CAP_ARTWORK_ZONE_MISMATCH = "CONTAINER_CAP_ARTWORK_ZONE_MISMATCH"

_PT_TO_MM = 1.0 / 2.835
_COVERAGE_TOL = 0.15          # wide — coverage is a bounding-box approximation


def _axis(state, *, code="", detail="", measured=None, target=None,
          reading=None, reading_method=""):
    """§BH65(a): ``reading``/``reading_method`` are what the document SAYS and
    how that was taken. They are additive and no reader branches on them; the
    verdict remains ``state`` and is unchanged by their presence."""
    return {"state": state, "code": code, "detail": detail,
            "measured": measured, "target": target,
            "reading": reading, "reading_method": reading_method}


def _field(vg, key):
    return ((vg or {}).get("fields") or {}).get(key) or {}


def _verified(f) -> bool:
    return f.get("verification") == "VERIFIED" and f.get("value") is not None


def _field_rect(doc, name):
    for node, _ in doc.walk():
        if node.type == "rect" and str(getattr(node, "name", "")) == name:
            return (node.x, node.y, node.w, node.h)
    return None


def _decoration_field(doc, zones=None):
    """The decoration field this document's readings are taken over, and WHERE
    it came from.

    §BH65(a) follow-up, found by taking the readings on a live compact rather
    than on a synthetic bottle: FOUR axes read nothing — motif_coverage,
    motif_density, label_density, product_name — for one reason. They all
    divide by a field, and `compose_container` emits the `decoration-field`
    rect only on its non-direct-print branch (`compose_container.py:524`); the
    branch a compact takes returns before it. The document names no field, so
    nothing could be divided.

    The CONFIRMED decoration zone is a better source than the composed rect in
    any case: it is the geometry a human confirmed, it is one source for the
    numbers (§BH64(b)), and reading it here adds no node to the document and
    moves no design-graph hash. The largest confirmed zone is the field, and
    the reading says which zone it was.
    """
    rect = _field_rect(doc, "decoration-field")
    if rect:
        return rect, "the document's own `decoration-field` rect"
    best = None
    for zone in (zones or []):
        w, h = float(zone.get("width") or 0), float(zone.get("height") or 0)
        if w * h <= 0:
            continue
        if best is None or w * h > best[0] * best[1]:
            best = (w, h, zone.get("zone_id"))
    if best is None:
        return None, "no decoration-field rect and no confirmed zone"
    return ((0.0, 0.0, best[0], best[1]),
            "the largest CONFIRMED decoration zone, %s (%.1f x %.1f mm) — this "
            "document names no `decoration-field` rect" % (best[2], best[0], best[1]))


def _name_runs(doc):
    return [n for n, _ in doc.walk()
            if n.type == "text" and str(n.name).startswith("product-name")]


def _ink_coverage(doc, field_area_mm2: float) -> float:
    """Shape-aware printed INK coverage of the motif marks as a fraction of the
    print zone — NOT the motif's bounding-box extent (which massively
    overcounts a sparse constellation). Sums per-mark bbox × shape factor."""
    if not field_area_mm2:
        return 0.0
    total = 0.0
    for node, _ in doc.walk():
        if node.type != "path":
            continue
        name = str(getattr(node, "name", ""))
        if not name.startswith(_ALL_MOTIF_PREFIXES):
            continue
        box = _path_bbox(node)
        if not box:
            continue
        kind = name.rsplit("-", 1)[-1]
        # filled marks default 0.5 of bbox; hairline strokes ~0.12
        factor = _INK_AREA_FACTOR.get(
            kind, 0.5 if getattr(node, "fill", None) else 0.12)
        total += factor * box[2] * box[3]
    return round(min(1.0, total / field_area_mm2), 4)


def _zone_label(value) -> str:
    return " ".join(str(value or "").lower().split())


def _product_text_runs(doc):
    """Text that PRINTS ON THE PRODUCT, by the composer's own declaration
    (§BH50(f)(1)): a sheet annotation is not product copy. An UNDECLARED run is
    COUNTED and the count is reported, because that ruling's own rule is that a
    forgotten declaration fails closed rather than vanishing."""
    runs, undeclared = [], 0
    for node, _ in doc.walk():
        if node.type != "text":
            continue
        scope = getattr(node, "print_scope", None)
        kind = getattr(scope, "kind", None) if scope is not None else None
        if kind == "SHEET_ANNOTATION":
            continue
        if kind is None:
            undeclared += 1
        runs.append(node)
    return runs, undeclared


def _spread(values):
    """Coefficient of variation — the spread of a set relative to its own mean.
    Undefined for fewer than two members, and says so rather than returning 0:
    "a definition for a one-mark motif" is named as missing in §BH50(f)'s cost
    list and a zero would answer a question nobody has asked yet."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    if not mean:
        return None
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return round((var ** 0.5) / mean, 4)


#: §Z4 / WI-L, recorded at container_motif_fidelity.py:63-76 and NOT fixed
#: here: `_path_bbox` ignores stroke width, so a hairline measures zero. That
#: note states fixing it MOVES gate axes, which §BH55(3) holds still and which
#: that ruling already left to the owner. Every reading built on a path box
#: carries this sentence rather than being quietly wrong.
_STROKE_CAVEAT = ("path boxes ignore stroke width, so a hairline reads zero "
                  "(§Z4/WI-L, container_motif_fidelity.py:63-76) — recorded, "
                  "not fixed here, because fixing it moves gate axes")


def take_readings(doc, field_rect, field_source="") -> dict:
    """§BH65(a): what every axis READS off this document, with no target and no
    verdict. Returns ``{axis: (reading, method)}``; a None reading with a
    method saying why is an answer, not a gap."""
    from apps.ire.container_motif_fidelity import measure_motif
    R: dict = {}
    fa = (field_rect[2] * field_rect[3]) if field_rect else None
    no_field = field_source or "no decoration field could be resolved"
    over = " over " + (field_source or "the decoration field")

    motif = measure_motif(doc)
    marks = motif.get("count") or 0
    boxes = [b for b in (_path_bbox(p) for p in _motif_marks(doc)) if b]

    R["motif_coverage"] = (
        (_ink_coverage(doc, fa), "shape-aware ink area" + over + "; " + _STROKE_CAVEAT) if fa
        else (None, no_field))
    R["motif_density"] = (
        (round(marks * 10000.0 / fa, 3), "emitted motif marks per 100 cm²" + over) if fa
        else (None, no_field))
    R["motif_position"] = (
        (motif.get("centroid"), "centroid of the emitted motif marks in "
                                "document mm (measure_motif); " + _STROKE_CAVEAT)
        if motif.get("centroid") else (None, "no motif mark is emitted"))
    R["motif_scale_distribution"] = (
        _spread([b[2] * b[3] for b in boxes]),
        "coefficient of variation of the %d emitted mark areas; %s"
        % (len(boxes), _STROKE_CAVEAT) if len(boxes) >= 2
        else "undefined for %d mark(s) — a one-mark definition is not this "
             "module's to invent (§BH50(f))" % len(boxes))
    R["motif_rotation_distribution"] = (
        _spread([abs(float(getattr(p, "rotation_deg", 0.0) or 0.0)) + 1.0
                 for p in _motif_marks(doc)]),
        "coefficient of variation of the emitted marks' rotations")
    R["motif_continuation"] = (
        marks, "motif marks emitted on this document in total; a front-to-back "
               "continuation reading needs both surfaces in one document and "
               "this path emits the front only")
    R["motif_color_relationship"] = (
        sorted({_fill_hex(p) for p in _motif_marks(doc) if _fill_hex(p)}),
        "the distinct fill colours the emitted motif marks use, unjudged")

    used = str(doc.metadata.get("logo_zone_used", "")) or None
    R["logo_zone"] = (used, "the placement the emitter recorded for the logo"
                            if used else "no logo placement is recorded")
    logo_box = _named_box(doc, "logo")
    R["logo_scale"] = (
        (round(logo_box[2], 3), "the logo's emitted width in document mm")
        if logo_box else (None, "no node named 'logo' is emitted"))

    runs, undeclared = _product_text_runs(doc)
    R["product_name"] = (
        (round(max((float(getattr(r, "size_pt", 0) or 0)
                    for r in _name_runs(doc)), default=0.0) * _PT_TO_MM
               / field_rect[3], 4),
         "the product name's cap height as a fraction of the print zone")
        if field_rect and _name_runs(doc)
        else (None, "no product-name run is emitted" if field_rect else no_field))
    R["label_density"] = (
        (round(sum(_run_area_mm2(r) for r in runs) / fa, 4),
         "product-copy text area over the decoration field, from %d run(s) "
         "(%d undeclared and counted, §BH50(f)(1) fails closed)"
         % (len(runs), undeclared)) if fa and runs
        else (None, no_field if not fa else "no product-copy run is emitted"))
    # §BH65(a) follow-up 2: THE LADDER IS BY TIER, NOT BY RUN. A name wrapped onto two lines is ONE tier set
    # at one size; read run by run it was "two runs tied at the top", and the executor reported that to the
    # owner as "task 89 has no typographic hierarchy" — which was false: it was "Focus Pressed" / "Powder",
    # one name on two lines. The composer names a wrapped tier's lines `product-name-hero-0`, `-1`, so the
    # tier is the run's name without its line suffix, and a tier counts once whatever its line count.
    tiers: dict = {}
    for run in runs:
        key = re.sub(r"-\d+$", "", str(getattr(run, "name", "") or "")) or id(run)
        size = float(getattr(run, "size_pt", 0) or 0)
        entry = tiers.setdefault(key, [size, 0])
        entry[0] = max(entry[0], size)
        entry[1] += 1
    ladder = sorted(tiers.values(), key=lambda t: -t[0])
    R["typography_hierarchy"] = (
        [round(t[0], 2) for t in ladder[:6]],
        "the product-copy size ladder in pt BY TIER, largest first — %d tier(s) from %d run(s); a tier wrapped "
        "onto several lines counts once (lines per tier: %s)"
        % (len(ladder), len(runs), [t[1] for t in ladder[:6]]))

    per_surface = _surface_ink(doc)
    total = sum(per_surface.values())
    surfaces = sorted(per_surface)
    one_surface = (
        "this document declares %d surface(s) — %s — and `PrintScope` is "
        "declared on text runs only, so no path, rect or image in it says "
        "which surface it is on: a front-to-back balance cannot be read here"
        % (len(surfaces), ", ".join(surfaces) or "none"))
    R["front_back_balance"] = (
        (per_surface, "product-copy area per declared surface in mm²")
        if len(surfaces) >= 2 else (None, one_surface))
    R["front_dominance"] = (
        (round(max(per_surface.values()) / total, 4),
         "the largest declared surface's share of the product-copy area")
        if len(surfaces) >= 2 and total else (None, one_surface))

    cap, body = _named_fill(doc, "cap"), _named_fill(doc, "body")
    R["cap_body_coordination"] = (
        ([cap, body], "the emitted cap and body fill colours, unjudged")
        if (cap or body) else (None, "no node named 'cap' or 'body' is emitted"))
    R["cap_orientation"] = (
        None, "NO DEFINITION EXISTS — only the axis name and its code "
              "(§BH50(f), OWNER_BLOCKER_CLEARANCE.md:21458). A definition is "
              "his line, not this module's, so nothing is invented here")
    R["cap_artwork_zone"] = (
        None, "needs a cap or collar artwork zone, which his confirmed "
              "decision excludes on the products drawn so far (§BH50(f))")
    return R


def _motif_marks(doc):
    return [n for n, _ in doc.walk()
            if n.type == "path" and str(getattr(n, "name", "")).startswith(
                _ALL_MOTIF_PREFIXES)]


def _fill_hex(node):
    """The node's fill as a hex string. `Color` carries floats and its repr is
    `r=0.71 g=0.43 b=0.47`, which is not a colour anybody can read — §BH60(d)
    asked for colours MEASURED, and a hex is the measured form."""
    fill = getattr(node, "fill", None)
    value = getattr(fill, "color", None) if fill is not None else None
    if value is None:
        return None
    to_hex = getattr(value, "to_hex", None)
    return to_hex() if callable(to_hex) else str(value)


def _named_box(doc, name):
    for node, _ in doc.walk():
        if str(getattr(node, "name", "")) == name:
            if node.type == "rect":
                return (node.x, node.y, node.w, node.h)
            if node.type in ("path", "image", "asset_ref"):
                return _path_bbox(node) if node.type == "path" else (
                    getattr(node, "x", 0), getattr(node, "y", 0),
                    getattr(node, "w", 0), getattr(node, "h", 0))
    return None


def _named_fill(doc, name):
    for node, _ in doc.walk():
        if str(getattr(node, "name", "")).startswith(name):
            hex_ = _fill_hex(node)
            if hex_:
                return hex_
    return None


def _run_area_mm2(run) -> float:
    """A text run's printed area, approximated as its cap height times its own
    advance estimate. It is an APPROXIMATION and the method string says so —
    no glyph metrics are read here."""
    h = float(getattr(run, "size_pt", 0) or 0) * _PT_TO_MM
    return h * h * 0.55 * max(1, len(str(getattr(run, "text", "") or "")))


def _surface_ink(doc):
    """Emitted area per SURFACE, by the composer's own `PrintScope.surface`
    declaration (§BH50(f)(1)) rather than by guessing a node-name prefix.

    Returns ``{surface: mm²}``. It is text-only, and that is the finding it
    reports rather than hides: `PrintScope` is declared on `TextRun` alone, so
    no path, rect or image in this document says which surface it is on. A
    front-to-back ink balance therefore cannot be read on this path, and the
    axis says that instead of returning a zero that would look like a measured
    absence of ink."""
    per: dict[str, float] = {}
    for node, _ in doc.walk():
        if node.type != "text":
            continue
        scope = getattr(node, "print_scope", None)
        surface = getattr(scope, "surface", None) if scope is not None else None
        if not surface:
            continue
        per[surface] = round(per.get(surface, 0.0) + _run_area_mm2(node), 3)
    return per


def measure_quantitative_fidelity(doc, visual_graph, motif_spec,
                                  zones=None) -> dict:
    """Per-axis three-state report. Gate-able axes fire only against a
    VERIFIED target; everything else is UNMEASURED (§2).

    ``zones`` is the CONFIRMED decoration zone set, optional and additive: it
    supplies the decoration field for a document that names no
    `decoration-field` rect (§BH65(a) follow-up). It changes no verdict — an
    axis that now has a field to divide by still needs a VERIFIED target to
    leave UNMEASURED.
    """
    axes: dict[str, dict] = {}
    field_rect, field_source = _decoration_field(doc, zones)
    fa = fw = fh = None
    if field_rect:
        _, _, fw, fh = field_rect
        fa = (fw or 0) * (fh or 0)

    # --- motif coverage (the one clean VERIFIED-target lever) --------------
    cov = _field(visual_graph, "decoration_coverage")
    motif_supported = (motif_spec or {}).get("reconstruction_capability") == "SUPPORTED"
    if motif_supported and _verified(cov) and fa:
        target = float(cov["value"]) / 100.0 if float(cov["value"]) > 1 else float(cov["value"])
        # shape-aware INK coverage (not the motif bounding-box extent)
        measured = _ink_coverage(doc, fa)
        if abs(measured - target) > _COVERAGE_TOL:
            axes["motif_coverage"] = _axis(
                MEASURED_FAIL, code=MOTIF_COVERAGE_FAILED,
                detail=f"emitted motif coverage {measured:.0%} vs target "
                       f"{target:.0%} (±{_COVERAGE_TOL:.0%})",
                measured=measured, target=round(target, 4))
        else:
            axes["motif_coverage"] = _axis(MEASURED_PASS, measured=measured,
                                           target=round(target, 4))
    else:
        axes["motif_coverage"] = _axis(UNMEASURED)

    # --- logo zone (VERIFIED string vs the emitter's centred placement) ----
    # §BH50(f)(5): a PASS needs a comparison. Before this ruling every target
    # but upper-left passed, with or without a logo emitted. Now: a concept
    # that wants it upper-left against anything else is the measured failure
    # it was; no recorded placement is UNMEASURED (rule 4's logo axis fails a
    # target with nothing emitted); a centred target against the emitter's
    # centred anchor is a compared PASS; any other token is UNMEASURED, named.
    lz = _field(visual_graph, "logo_zone")
    if _verified(lz):
        used = str(doc.metadata.get("logo_zone_used", "")).lower()
        label = _zone_label(lz["value"])
        wants_upper_left = "upper left" in label or "upper-left" in label
        # [the owner's second answer of 2026-09-25: the mark drawn from its approved vector master sits at the same
        # centred anchor as the raster (apps/ire/brand_mark.ZONE_USED)]
        from apps.ire.brand_mark import ZONE_USED as _MARK_ZONE_USED
        centred_anchor = used in ("front-controlled-fallback", "centred",
                                  "center", "centered", _MARK_ZONE_USED)
        wants_centre = any(t in label for t in ("centre", "center", "centred",
                                                 "centered", "middle"))
        # the container emitter places the logo at a centred anchor; a concept
        # that wants it upper-left is a real, measurable mismatch
        if wants_upper_left and "upper-left" not in used:
            axes["logo_zone"] = _axis(
                MEASURED_FAIL, code=LOGO_ZONE_MISMATCH,
                detail=f"concept places the logo {lz['value']!r}; emitted "
                       f"placement is {used or 'centred'}",
                measured=used or "centred", target=lz["value"])
        elif not used:
            axes["logo_zone"] = _axis(
                UNMEASURED, target=lz["value"],
                detail="no logo placement recorded by the emitter; the target "
                       "is not compared (rule 4's logo axis fails a target "
                       "with nothing emitted)")
        elif centred_anchor and wants_centre:
            axes["logo_zone"] = _axis(
                MEASURED_PASS, target=lz["value"], measured=used,
                detail=f"target {lz['value']!r} compared with the emitter's "
                       f"centred anchor ({used}): equal")
        else:
            axes["logo_zone"] = _axis(
                UNMEASURED, target=lz["value"], measured=used,
                detail=f"target {lz['value']!r} against the emitter's {used!r}: "
                       "no instrument compares this token")
    else:
        axes["logo_zone"] = _axis(UNMEASURED)

    # --- product-name zone / scale (measured vs the PRINT ZONE, §4) --------
    nz = _field(visual_graph, "product_name_zone")
    runs = _name_runs(doc)
    if _verified(nz) and fh:
        zone = _zone_label(nz["value"])
        max_pt = max((float(getattr(r, "size_pt", 0) or 0) for r in runs),
                     default=0.0)
        name_h_frac = (max_pt * _PT_TO_MM) / fh if fh else 0.0
        if not runs:
            axes["product_name"] = _axis(MEASURED_FAIL,
                                         code=PRODUCT_NAME_TOO_SMALL,
                                         detail="no product-name run emitted")
        elif name_h_frac < 0.06:
            axes["product_name"] = _axis(
                MEASURED_FAIL, code=PRODUCT_NAME_TOO_SMALL,
                detail=f"name cap-height is {name_h_frac:.0%} of the print "
                       "zone (min 6%)", measured=round(name_h_frac, 3))
        elif "left" in zone and runs and all(getattr(r, "align", "") == "center"
                                             for r in runs):
            axes["product_name"] = _axis(
                MEASURED_FAIL, code=PRODUCT_NAME_ZONE_MISMATCH,
                detail="concept left-aligns the name; emitted is centred",
                target=nz["value"])
        else:
            # §BH50(f)(5): a PASS needs a comparison — the target's horizontal
            # token against the one alignment the runs share. A definite
            # mismatch is a readiness finding here (never a reconstruction
            # blocker); a token no instrument compares is UNMEASURED, named.
            from apps.ire.container_fidelity import (_emitted_alignment,
                                                     _horizontal_token)
            target = _horizontal_token(zone)
            emitted = _emitted_alignment(runs)
            if target is not None and emitted is not None and target != emitted:
                axes["product_name"] = _axis(
                    MEASURED_FAIL, code=PRODUCT_NAME_ZONE_MISMATCH,
                    detail=f"concept places the name {nz['value']!r}; emitted "
                           f"alignment is {emitted}",
                    measured=emitted, target=nz["value"])
            elif target is not None and emitted is not None:
                axes["product_name"] = _axis(
                    MEASURED_PASS, target=nz["value"], measured=emitted,
                    detail=f"cap-height {name_h_frac:.0%} of the print zone "
                           f"(min 6%); target {nz['value']!r} compared with "
                           f"the emitted alignment {emitted!r}: equal")
            else:
                axes["product_name"] = _axis(
                    UNMEASURED, target=nz["value"],
                    measured=emitted or "none or mixed",
                    detail=f"cap-height {name_h_frac:.0%} of the print zone "
                           f"(min 6%) holds; target {nz['value']!r} against "
                           f"emitted alignment {emitted or 'none or mixed'}: "
                           "no instrument compares this token")
    else:
        axes["product_name"] = _axis(UNMEASURED)

    # --- axes with NO reliable target today → UNMEASURED (§2) --------------
    for axis in ("motif_density", "motif_position", "motif_scale_distribution",
                 "motif_rotation_distribution", "motif_continuation",
                 "motif_color_relationship", "logo_scale", "label_density",
                 "typography_hierarchy", "front_back_balance",
                 "front_dominance", "cap_body_coordination", "cap_orientation",
                 "cap_artwork_zone"):
        axes[axis] = _axis(UNMEASURED)

    # §BH65(a): EVERY AXIS CARRIES ITS READING. Attached here, after the
    # verdicts above are settled, so that not one `state`, `code`, `measured`
    # or `target` can be changed by taking a reading — the reading is written
    # into two keys that did not exist and that no reader branches on.
    for _axis_name, (_reading, _method) in take_readings(
            doc, field_rect, field_source).items():
        _entry = axes.get(_axis_name)
        if _entry is None:
            continue
        _entry["reading"] = _reading
        _entry["reading_method"] = _method

    failures = [a["code"] for a in axes.values()
                if a["state"] == MEASURED_FAIL and a["code"]]
    counts = {s: sum(1 for a in axes.values() if a["state"] == s)
              for s in (MEASURED_PASS, MEASURED_FAIL, UNMEASURED)}
    # §BH50(f)(5): a pass never outvotes an unmeasured axis. A report with a
    # measured pass beside an unmeasured axis reads UNMEASURED_BLOCKING (the
    # VQR-2A rule the base report already keeps); every axis unmeasured stays
    # UNMEASURED; the unmeasured axes block acceptance through readiness.
    overall = (MEASURED_FAIL if counts[MEASURED_FAIL]
               else UNMEASURED_BLOCKING
               if counts[MEASURED_PASS] and counts[UNMEASURED]
               else (MEASURED_PASS if counts[MEASURED_PASS] else UNMEASURED))
    # §BH65(a): the partition, on the record rather than in a report — how
    # many axes could say anything at all about this document, and how many
    # answered with a stated reason instead of a number.
    readings = {
        "taken": sum(1 for a in axes.values() if a.get("reading") is not None),
        "absent": sorted(k for k, a in axes.items() if a.get("reading") is None),
        "field_source": field_source,
        "scope": "READINGS ONLY — §BH65(a) sets no threshold; a reading is "
                 "never a verdict and never changes `state` (§BH55(3))"}
    return {"schema_version": "container_quantitative_fidelity/1.0",
            "axes": axes, "counts": counts, "overall": overall,
            "failures": failures, "readings": readings,
            "field_zone_mm": {"w": round(fw, 2), "h": round(fh, 2)}
            if field_rect else None}


__all__ = [
    "measure_quantitative_fidelity", "MOTIF_COVERAGE_FAILED",
    "MOTIF_DENSITY_FAILED", "MOTIF_POSITION_FAILED", "MOTIF_CONTINUATION_FAILED",
    "MOTIF_COLOR_RELATIONSHIP_FAILED", "MOTIF_SCALE_DISTRIBUTION_FAILED",
    "MOTIF_ROTATION_DISTRIBUTION_FAILED", "LOGO_ZONE_MISMATCH",
    "LOGO_SCALE_MISMATCH", "PRODUCT_NAME_TOO_SMALL",
    "PRODUCT_NAME_ZONE_MISMATCH", "TYPOGRAPHY_HIERARCHY_FAILED",
    "LABEL_DENSITY_FAILED", "FRONT_BACK_RELATIONSHIP_FAILED",
    "FRONT_DOMINANCE_FAILED", "CAP_ORIENTATION_FAILED",
    "CAP_BODY_COORDINATION_FAILED", "CAP_ARTWORK_ZONE_MISMATCH",
]
