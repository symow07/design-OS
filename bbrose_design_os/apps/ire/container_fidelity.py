"""Selected-concept fidelity for the NATIVE container reconstruction
(Phase 2B-2, slice 4).

Measures the ACTUAL emitted Document against
container_selected_concept_visual_graph/1.0 — structural relationships, never
pixel similarity. Three-state per axis (the no-provider consequence, §10):

* MEASURED_PASS  — the target is known and the emitted artwork satisfies it
* MEASURED_FAIL  — the target is known and the emitted artwork violates it
* UNMEASURED     — the target field is MISSING (needs vision / a structured
                   record); surfaced for a human, NEVER an auto-pass

"Element exists" is not a pass. When any axis is MEASURED_FAIL the overall
verdict is SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED and reconstruction fails
closed (CONTAINER_NATIVE_RECONSTRUCTION_FAILED) — the task stays at the
reconstruction gate with the report preserved; it never reverts to the raster
fallback and never globally fails the task.

§BH50(f)(4)/(5), OWNER RULED 2026-09-13 — WHAT UNMEASURED_BLOCKING BLOCKS.
Measured before the ruling, the overall UNMEASURED_BLOCKING had no gating
reader: the board printed it and nothing enforced it, a label that said it
blocked and blocked nothing. It is kept, and made true, with one scope: an
UNMEASURED required axis blocks ACCEPTANCE of production artwork — Gate-2
approval, through container_production_readiness.fidelity_unmeasured, which
derives one code per unmeasured axis at read time — and never the
reconstruction, so a design can be tried while its axes are unmeasured. The
report says so in ``blocking_scope``. An axis that does not describe the
product is NOT_APPLICABLE with its reason (the seam check on a product with
no wrapped surface, §BH50(f)(6)), never a pass and never a silent drop.
"""
from __future__ import annotations

from apps.pipeline.services.container_contract import MISSING

MEASURED_PASS = "MEASURED_PASS"
MEASURED_FAIL = "MEASURED_FAIL"
UNMEASURED = "UNMEASURED"
# VQR-2A §6: overall verdict when nothing failed outright but a REQUIRED
# axis has no valid measurement — absence of evidence is never a pass.
UNMEASURED_BLOCKING = "UNMEASURED_BLOCKING"
# §BH50(f)(6): an axis whose rule does not describe this product — recorded
# with its reason, counted apart, never blocking and never a pass
NOT_APPLICABLE = "NOT_APPLICABLE"
#: §BH50(f)(5): the act an unmeasured required axis blocks
BLOCKING_SCOPE = "ACCEPTANCE"

# --- §10 stable failure codes -----------------------------------------------
LOGO_ZONE_MISMATCH = "CONTAINER_LOGO_ZONE_MISMATCH"
LOGO_SCALE_MISMATCH = "CONTAINER_LOGO_SCALE_MISMATCH"
PRODUCT_NAME_TOO_SMALL = "CONTAINER_PRODUCT_NAME_TOO_SMALL"
PRODUCT_NAME_ZONE_MISMATCH = "CONTAINER_PRODUCT_NAME_ZONE_MISMATCH"
MOTIF_FAMILY_MISMATCH = "CONTAINER_MOTIF_FAMILY_MISMATCH"
MOTIF_DENSITY_FAILED = "CONTAINER_MOTIF_DENSITY_FAILED"
MOTIF_POSITION_FAILED = "CONTAINER_MOTIF_POSITION_FAILED"
CAP_BODY_COORDINATION_FAILED = "CONTAINER_CAP_BODY_COORDINATION_FAILED"
FRONT_BACK_RELATIONSHIP_FAILED = "CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED"
WRAP_ALIGNMENT_FAILED = "CONTAINER_WRAP_ALIGNMENT_FAILED"
FIDELITY_FAILED = "SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED"
NATIVE_RECONSTRUCTION_FAILED = "CONTAINER_NATIVE_RECONSTRUCTION_FAILED"

_MIN_NAME_PT = 8.0


def name_floor_pt(doc) -> float:
    """[His test blocker on design 122 at reconstruction, 2026-10-08: "The picture's layout wins (my rule): draw the name
    at the size the concept shows, as long as it's readable and above the print floor. Tell me which old rule refused it
    and retire it for fronts drawn from their concept."] The least size a front's product name may stand at: on a front
    drawn from its concept picture's map, the print floor every line of it is set on (``compose_container``'s
    MAP_TYPE_FLOOR_PT), the concept's own size above it; on every other front the ruled block's ``_MIN_NAME_PT`` — the
    8 pt VQR-2A set for a name the drawing lays out itself, retired for fronts drawn from their concept."""
    if ((getattr(doc, "metadata", None) or {}).get("map_front")) is None:
        return _MIN_NAME_PT
    from apps.ire.compose_container import MAP_TYPE_FLOOR_PT
    return float(MAP_TYPE_FLOOR_PT)


def _present(field: dict) -> bool:
    return bool(field) and field.get("verification") != MISSING \
        and field.get("value") is not None


def _axis(state: str, *, code: str = "", detail: str = "") -> dict:
    # VQR-2A §6: every axis declares that it is required — the overall
    # verdict may only pass when every required axis was measured and passed
    return {"state": state, "code": code, "detail": detail, "required": True}


def spells_the_name(words, product_name) -> bool:
    """[His test blocker on design 124, 2026-10-11, with his rule on 122 at reconstruction (2026-10-08): "draw the name at
    the size the concept shows".] ``words`` are the product's name as a front sets it: the record's name, or its first
    words — two at least — the one line a concept sets the start of its name on, as the composer takes it
    (``compose_container._name_start``): 124's lid sets "Enchanted Rose" of "Enchanted Rose Palette", 122's 149 "Rose
    Blossom" of "Rose Blossom Hand Cream"."""
    def tokens(text):
        return [w for w in str(text).casefold().split() if any(ch.isalnum() for ch in w)]
    mine, name = tokens(words), tokens(product_name)
    if not mine or not name:
        return False
    return mine == name or (len(mine) >= 2 and name[:len(mine)] == mine)


def traced_name(doc) -> dict | None:
    """[His answer after test day finding 3, (3).] The name a front drew as its concept picture's traced lettering
    (``compose_container._map_type_group``): ``{"words", "size_pt"}`` when its path is drawn and the record says so,
    else None."""
    rec = ((getattr(doc, "metadata", None) or {}).get("map_front") or {}).get("name_traced")
    if not rec:
        return None
    drawn = any(n.type == "path" and str(getattr(n, "name", "")).startswith("product-name-traced") for n, _ in doc.walk())
    return dict(rec) if drawn else None


def measure_front_back(doc) -> dict:
    """§6 emitted-role check (structural, not the concept's vision-only
    INTENT which stays UNMEASURED): the roles COLLAPSE when the back surface
    carries the hero motif, or when the front carries no hero content — either
    is a real, measurable failure of the emitted document."""
    group_names = [str(getattr(n, "name", "")) for n, _ in doc.walk()
                   if n.type == "group"]
    text_names = [str(getattr(n, "name", "")) for n, _ in doc.walk()
                  if n.type == "text"]
    back_has_hero_motif = "motif-BODY_BACK" in group_names
    # [his test blocker on design 122 at reconstruction, 2026-10-08: "find what this check wants ... Make the check and
    # the new back area agree, for every form"] it wants the hero on the front and never the hero motif on the back; a
    # front drawn from its concept carries its motif under the map's own names (122's "lineart-map-0 …"), never
    # "motif-front" — the concept's motif on the front is the hero as the ruled block's is
    from apps.ire.compose_container import LID_ART_GROUP, MAP_MOTIF_PREFIXES
    front_is_hero = ("motif-front" in group_names
                     or any(g.startswith(MAP_MOTIF_PREFIXES) for g in group_names)
                     or LID_ART_GROUP in group_names       # [his test blocker on design 124, (3)] a lid drawn from its art
                     or any(t.startswith("product-name") for t in text_names)
                     or traced_name(doc) is not None)          # [his answer after finding 3, (3): the traced name]
    return {"roles_distinct": (not back_has_hero_motif) and front_is_hero,
            "back_has_hero_motif": back_has_hero_motif,
            "front_is_hero": front_is_hero, "measured": True}


def _horizontal_token(zone_label: str):
    """The horizontal placement a concept's zone label names, or None."""
    if any(t in zone_label for t in ("center", "centre", "centred", "centered")):
        return "center"
    if "left" in zone_label:
        return "left"
    if "right" in zone_label:
        return "right"
    return None


def _emitted_alignment(runs):
    """The one alignment every emitted name run shares, or None (no run, or
    mixed alignments) — a comparison needs one value on each side."""
    aligns = {str(getattr(r, "align", "") or "") for r in runs}
    return aligns.pop() if len(aligns) == 1 and "" not in aligns else None


def _wrap_axis(zones) -> dict:
    """§BH50(f)(6): the wrap axis takes the seam check's own applicability
    when the zone record is given — NOT_APPLICABLE with its reason on a
    product with no wrapped surface, UNMEASURED (blocking at acceptance)
    otherwise. With no zone record it stays UNMEASURED, as before."""
    if zones is None:
        return _axis(UNMEASURED)
    from apps.ire import container_wrap_geometry as cwg
    app = cwg.seam_applicability(zones)
    if app["state"] == cwg.NOT_APPLICABLE:
        return _axis(NOT_APPLICABLE, detail=app["reason"])
    return _axis(UNMEASURED,
                 detail=app["reason"] if app["state"] != cwg.APPLICABLE else "")


def measure_fidelity(doc, visual_graph: dict, *, name_lines,
                     census: dict | None = None, zones=None) -> dict:
    """Per-axis three-state report of the emitted ``doc`` vs the visual graph.
    Deterministic; no pixels, no provider. ``zones`` (§BH50(f)(6)) is the
    confirmed zone record the wrap axis reads its applicability from."""
    fields = (visual_graph or {}).get("fields") or {}
    census = census or {}
    axes: dict[str, dict] = {}

    name_runs = [n for n, _ in doc.walk()
                 if n.type == "text" and str(n.name).startswith("product-name")]
    # [his answer after test day finding 3, (3): "the script lettering also traced from the picture"] a name drawn as
    # the picture's traced lettering is the name, at the size a typed name filling its place takes
    traced = traced_name(doc)

    # 1. product-name presence + scale — measurable whenever a name is emitted
    floor_pt = name_floor_pt(doc)              # [his test blocker on design 122 at reconstruction] the concept's size
    if name_lines and traced is not None and not name_runs:
        axes["product_name_presence"] = (_axis(MEASURED_PASS) if traced["size_pt"] >= floor_pt else _axis(
            MEASURED_FAIL, code=PRODUCT_NAME_TOO_SMALL,
            detail=f"the traced name stands at {traced['size_pt']:.1f}pt"))
    elif name_lines:
        if not name_runs:
            axes["product_name_presence"] = _axis(
                MEASURED_FAIL, code=PRODUCT_NAME_TOO_SMALL,
                detail="no product-name run was emitted")
        elif max((r.size_pt for r in name_runs), default=0) < floor_pt:
            axes["product_name_presence"] = _axis(
                MEASURED_FAIL, code=PRODUCT_NAME_TOO_SMALL,
                detail=f"largest name run is "
                       f"{max(r.size_pt for r in name_runs):.1f}pt")
        else:
            axes["product_name_presence"] = _axis(MEASURED_PASS)
    else:
        axes["product_name_presence"] = _axis(UNMEASURED)

    # 2. product-name zone — measured only when the record carries the zone.
    #    §BH50(f)(5): a PASS needs a COMPARISON — the target's horizontal
    #    token against the one alignment the emitted runs share. Before this
    #    ruling every target but "left"-against-centred passed, including a
    #    "left" target with NO name run at all (an empty list is falsy).
    #    Rule-4 failures block the reconstruction, so no NEW failure is
    #    added here: a mismatch this report does not compare is UNMEASURED,
    #    naming the token, and the quant product_name axis fails it at
    #    acceptance.
    nz = fields.get("product_name_zone", {})
    if _present(nz):
        zone = str(nz.get("value", "")).lower()
        target = _horizontal_token(zone)
        emitted = _emitted_alignment(name_runs)
        if target == "left" and emitted == "center":
            axes["product_name_zone"] = _axis(
                MEASURED_FAIL, code=PRODUCT_NAME_ZONE_MISMATCH,
                detail="concept left-aligns the name; emitted is centered")
        elif target is not None and emitted is not None and target == emitted:
            axes["product_name_zone"] = _axis(
                MEASURED_PASS,
                detail=f"target {zone!r} compared with the emitted alignment "
                       f"{emitted!r}: equal")
        else:
            axes["product_name_zone"] = _axis(
                UNMEASURED,
                detail=f"target {zone!r} against emitted alignment "
                       f"{emitted or 'none or mixed'}: not compared by this "
                       "report (its failures block the reconstruction); the "
                       "quant product_name axis compares it at acceptance")
    else:
        axes["product_name_zone"] = _axis(UNMEASURED)

    # 3. logo — measured only when the record carries a logo zone.
    #    §BH50(f)(5): "element exists" is not a pass, the docstring's own
    #    sentence. An emitted logo against a target ZONE is UNMEASURED here —
    #    this report compares no position; the quant logo_zone axis does, at
    #    acceptance. A target with nothing emitted stays a measured failure.
    lz = fields.get("logo_zone", {})
    if _present(lz):
        if census.get("logo_rasters", 0) >= 1 or doc.metadata.get("logo_zone_used"):
            axes["logo"] = _axis(
                UNMEASURED,
                detail=f"a logo is emitted; its zone is not compared with the "
                       f"target {str(lz.get('value'))!r} by this report — the "
                       "quant logo_zone axis compares position at acceptance")
        else:
            axes["logo"] = _axis(
                MEASURED_FAIL, code=LOGO_ZONE_MISMATCH,
                detail="the concept places a logo but none was emitted")
    else:
        axes["logo"] = _axis(UNMEASURED)

    # 4. motif family — measured by the dedicated geometry engine
    #    (container_motif_fidelity, 2B-2A); deferred here so it is not
    #    double-counted against the base fidelity report.
    axes["motif_family"] = _axis(UNMEASURED)

    # 5. relationships that need vision / an unrendered motif — UNMEASURED
    #    (surfaced for a human; never an auto-pass, never a silent fail).
    #    §BH50(f)(5): they block acceptance, through readiness, and never the
    #    reconstruction. front_back_relationship stays here in full: its
    #    sibling record measures emitted-role collapse, not the concept's
    #    intent, and a sibling that measures a different quantity does not
    #    discharge an axis.
    for axis in ("cap_body_coordination", "front_back_relationship",
                 "motif_position"):
        axes[axis] = _axis(UNMEASURED)
    axes["wrap_alignment"] = _wrap_axis(zones)

    failures = [a["code"] for a in axes.values()
                if a["state"] == MEASURED_FAIL and a["code"]]
    counts = {
        "measured_pass": sum(1 for a in axes.values() if a["state"] == MEASURED_PASS),
        "measured_fail": sum(1 for a in axes.values() if a["state"] == MEASURED_FAIL),
        "unmeasured": sum(1 for a in axes.values() if a["state"] == UNMEASURED),
        "not_applicable": sum(1 for a in axes.values() if a["state"] == NOT_APPLICABLE),
    }
    # VQR-2A §6 fail-closed overall: MEASURED_PASS requires EVERY required
    # axis to be MEASURED_PASS. Unmeasured required axes are BLOCKING — the
    # old rule (one pass outvoting seven unmeasured axes) let task 53 report
    # MEASURED_PASS while visually unusable. Historical persisted reports
    # are audit evidence and are never rewritten; this shapes new
    # evaluations only.
    blocking_unmeasured = [name for name, a in axes.items()
                           if a.get("required", True)
                           and a["state"] == UNMEASURED]
    if counts["measured_fail"]:
        overall = MEASURED_FAIL
    elif blocking_unmeasured:
        overall = UNMEASURED_BLOCKING
    else:
        overall = MEASURED_PASS if counts["measured_pass"] else \
            UNMEASURED_BLOCKING
    return {"axes": axes, "counts": counts, "overall": overall,
            "failures": failures,
            "blocking_unmeasured": blocking_unmeasured,
            # §BH50(f)(5): what the unmeasured axes block, stated on the record
            "blocking_scope": BLOCKING_SCOPE,
            "fidelity_code": FIDELITY_FAILED if failures else ""}


__all__ = [
    "measure_fidelity", "MEASURED_PASS", "MEASURED_FAIL", "UNMEASURED",
    "UNMEASURED_BLOCKING", "NOT_APPLICABLE", "BLOCKING_SCOPE",
    "FIDELITY_FAILED", "NATIVE_RECONSTRUCTION_FAILED",
    "PRODUCT_NAME_TOO_SMALL", "PRODUCT_NAME_ZONE_MISMATCH",
    "LOGO_ZONE_MISMATCH", "LOGO_SCALE_MISMATCH", "MOTIF_FAMILY_MISMATCH",
    "MOTIF_DENSITY_FAILED", "MOTIF_POSITION_FAILED",
    "CAP_BODY_COORDINATION_FAILED", "FRONT_BACK_RELATIONSHIP_FAILED",
    "WRAP_ALIGNMENT_FAILED",
]
