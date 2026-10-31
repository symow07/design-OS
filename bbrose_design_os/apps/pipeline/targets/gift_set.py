"""Gift Set (§BH55 Phase 2, 2026-09-19): N of the product in ONE carton, side by side on an insert.

OWNER STANDING ORDER §BH55, PHASE 2: "EVERY REMAINING TARGET … No target reads COMING SOON when this phase ends." The
roadmap's own scope: "tray/insert geometry over Container+Packaging" (docs/roadmap/master_roadmap_v3.md:200-205). The
carton is NOT reinvented: a gift set IS the packaging target — the dieline registry's own cartons, the dimension gate a
person confirms, the carton's artwork composed like any carton's — sized by the set's fit (`apps/ire/fit_grid.py
::insert_for`): the pieces on an insert, the carton's inner space around them. The insert's arrangement and each
piece's cut-out are on the design's record beside the carton; the insert's own die is not drawn — named.

THE CARTON IS ONE THE DIMENSION GATE ACCEPTS, and the gate is ASKED, never restated (`gate_refusal`): every carton its
chooser recommends for new work is taller than it is wide (`apps/dielines/validators/schema.py`, `_STRUCTURAL_RULES`),
and a row of three pieces is often wider than they stand — measured on the pilot's own product: three 30 ml pieces in a
row, 111 mm across and 104 mm tall with their headroom, were refused. So the arrangement is the SMALLEST carton the gate
accepts: the row, made the least whole millimetre taller the gate accepts, its insert raising the pieces by that much —
or a square of four when a row of four would stand taller than it needs. Rejected: the wide row as it stands (refused by
the rule, which is listed on the acceptance-time list, untouched — clause 3); the tuck-top auto-bottom carton, whose
rules accept a carton wider than tall, because the registry holds it production-ineligible (MEASURED_REFERENCE_REQUIRED,
its crash-lock "NOT a finished auto-bottom production die") and draws its top tuck from the width — 136.2 mm for the
row's 111, taller than the carton (`geometry.engine.calculate_dieline`, measured); a square with one place empty, which
is the larger carton.

THE PIECE is the product itself — a set replaces each piece's own carton: the product record's own size when the record
describes the product; a record of the product's CARTON is not a piece, so the piece is then sized as the container
stage sizes it, from the capacity the brief names or the record's own net content (3938d81). THE COUNT from the brief's
own words ("a set of three", "a trio", "3 serums"), else PROPOSED at three and said as proposed. With no size for the
piece, the carton is sized the packaging target's own way.

THE DIE IS QUALIFIED, AND HELD AT GATE 2 BY ITS OWN DOMAIN (`die_qualification`, `gate2_hold`): this deployment draws
the straight tuck end at its current version, 1.1 (the standard vector path, where a person picks the corrected 1.2, is
off — a local validation exercise, `apps/dielines/checks.py`), and 1.1 takes its tuck from the carton's WIDTH. The
qualification layer's own domain for that die (`apps/dielines/qualification`, which governs "every path that creates NEW
dies") refuses a row's carton — measured at 111 × 39 × 112 mm: "TUCK_LIP_VS_HEIGHT: lip = 97.20 mm must be < H/2 = 56
mm" — and the corrected 1.2 D-derived closure qualifies it. So the design is composed and shown, and held at Gate 2 with
the qualification layer's own code, DIMENSION_COMBINATION_UNSUPPORTED, the domain's own words and what it needs. One of
the domain's constraints is NOT applied (`NOT_APPLIED`): the dust-pair clearance, which every square carton this system
has drawn fails — the product's own (40 × 40 × 110 mm, -10.48 mm) and the measured reference die (28 × 28 × 120, overlap
7.3 mm); it is on the acceptance-time list, untouched. Rejected: a square of four places with one empty (its tuck keeps
the rule; a set of three shown with a hole), and the row made 195 mm tall, the least height at which 1.1's tuck keeps
the rule (the pieces raised 91 mm, the carton more than half empty).

[THE OWNER'S ANSWER OF 2026-09-27 TO THE §BH70 REPORT'S SECOND QUESTION: "Yes, switch the Gift Set carton to the
corrected flap." A set's carton is drawn at 1.2 (`GiftSetTarget.carton_template_version`), the flap cut from the
carton's depth; the qualification reads the version drawn, and the row of three it held at 1.1 is accepted. A die
saved at 1.1 before is still read at 1.1, and held as it was. A colleague test-fits the first sample (§BH70(3)).]

THE SET'S OWN WORDS on the carton (`panel_defaults`, `design_metadata`): its content is n × the piece's own net content;
the piece's own item number and barcode are not the set's — a set has no record of its own, and one piece's barcode on
it would ring up one piece — so neither is printed; the front says "Gift set of n" under the name where a carton says
its type. A person still edits every panel field at the dimension gate.
"""
from __future__ import annotations

import re

from apps.pipeline.targets.base import DesignTarget
from apps.pipeline.targets.packaging import PackagingTarget

FIT_KEY = "gift_set_fit/1.0"
#: CHOSEN, and said as chosen: the count a set is proposed at when the brief names none
DEFAULT_SET = 3
_SET_WORDS = (r"\bset of (\d{1,2})\b", r"\b(\d{1,2})[- ]?pieces?\b",
              r"\b(\d{1,2})\s+(?:mini\s+)?(?:serums?|creams?|oils?|lotions?|balms?|masks?|toners?|cleansers?|"
              r"lipsticks?|glosses|mascaras?|bottles?|jars?|tubes?|products?|items?)\b")
_NAMED_SETS = (("duo", 2), ("pair", 2), ("trio", 3), ("quartet", 4))
_NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

DIRECTIVE = (
    "This design target is a GIFT SET: several of the product presented together in ONE carton — the pieces standing "
    "side by side on an insert inside it. Render the carton itself, closed, its front and one side visible, the front "
    "carrying the design: it is the packaging a customer is given. Do NOT render the pieces loose, a basket, a bag, a "
    "hamper, ribbons or a flat dieline; no words other than the product's name.")


def set_count(task) -> tuple[int, str]:
    """The count the brief names for the set, or the proposal when it names none."""
    from apps.pipeline.targets.artwork import _UNIT_COUNT_WORDS
    text = (getattr(task, "task_text", "") or "").lower()
    for words in (*_SET_WORDS, _UNIT_COUNT_WORDS):
        m = re.search(words, text)
        if m and 1 <= int(m.group(1)) <= 24:
            return int(m.group(1)), "the brief's own words"
    m = re.search(r"\bset of (" + "|".join(_NUMBER_WORDS) + r")\b", text)
    if m:
        return _NUMBER_WORDS[m.group(1)], "the brief's own words"
    for word, n in _NAMED_SETS:
        if re.search(rf"\b{word}\b", text):
            return n, "the brief's own words"
    return DEFAULT_SET, f"PROPOSED — the brief names no count ({DEFAULT_SET}, chosen)"


def set_piece(task):
    """One piece as it stands on the insert: the product record's own size when the record describes the product; a
    record of the product's CARTON is not a piece — the set replaces it — so the piece is then sized as the container
    stage sizes it, from the capacity the brief names or the record's own net content (3938d81); else nothing."""
    from apps.ire.fit_grid import Unit
    from apps.pipeline.targets.container import _bottle_size_for, _capacity_ml, _record_describes_carton
    product = getattr(task, "product", None)
    boxed = product is not None and _record_describes_carton(product)
    if product is not None and not boxed and all(getattr(product, k, None) for k in ("width_mm", "depth_mm", "height_mm")):
        return Unit(float(product.width_mm), float(product.depth_mm), float(product.height_mm), "the product record")
    size = _bottle_size_for(_capacity_ml((getattr(task, "task_text", "") or "").lower(), product))
    if not size:
        return None
    return Unit(size["width_mm"], size["width_mm"], size["height_mm"],
                ("the record is the product's carton, which a set replaces — " if boxed else "")
                + "sized from its capacity, the container's own proposal (3938d81)")


def gate_refusal(w_mm: float, d_mm: float, h_mm: float) -> str:
    """The dimension gate's own answer for a carton: its words when it refuses, else empty — the validator its
    confirmation runs (`views.py`, confirm_dimensions → `DielineInputJSON`), for the carton it falls back to when none
    is chosen and for every carton its chooser recommends for new work (the rules are a carton's, whatever its
    version)."""
    from pydantic import ValidationError

    from apps.dielines import registry
    from apps.dielines.validators.schema import DielineInputJSON
    templates = ["straight_tuck_end_carton"] + sorted(
        {c["template_id"] for c in registry.new_selection_templates()
         if c["new_selection_class"] == registry.NEW_SELECTION_RECOMMENDED} - {"straight_tuck_end_carton"})
    for template in templates:
        try:
            DielineInputJSON(template=template, unit="mm",
                             dimensions={"width_mm": w_mm, "depth_mm": d_mm, "height_mm": h_mm},
                             print_settings={}, construction={},
                             metadata={"product_name": "gift set", "product_type": "carton"})
        except ValidationError as exc:
            return "; ".join(e["msg"] for e in exc.errors())
    return ""


#: the one constraint of the die's own domain NOT applied: every square carton this system has drawn fails it
NOT_APPLIED = ("DUST_PAIR_CLEARANCE",)


def die_qualification(output) -> dict | None:
    """The die drawn for the set's carton — its confirmed sizes and the version actually drawn — against its own
    template's published domain, less ``NOT_APPLIED``; and whether the corrected version the registry recommends for
    new work qualifies the same carton. None when no die is on record, or its template has no qualification."""
    from apps.dielines import registry
    from apps.dielines.qualification.domain import evaluate_domain
    from apps.dielines.qualification.runner import adapter_for
    job = getattr(output, "dieline_job", None)
    params = (getattr(job, "input_json", None) or {}) if job is not None else {}
    dims = params.get("dimensions") or {}
    if not dims:
        return None
    defn = registry.resolve(params.get("template") or "straight_tuck_end_carton", params.get("template_version"))
    current = registry.resolve(defn.template_id).version
    qualified = registry.QUALIFIED_AS.get(defn.version, defn.version)     # [his final goal, B2] 1.3 over 1.2's domain
    adapter = adapter_for(defn.template_id if qualified == current else f"{defn.template_id}@{qualified}")
    if adapter is None:
        return None
    construction, printing = params.get("construction") or {}, params.get("print_settings") or {}
    user = {**{k: float(dims[k]) for k in ("width_mm", "depth_mm", "height_mm")},
            "board_thickness_mm": float(construction.get("board_thickness_mm", 0.35)),
            "glue_tab_mm": float(construction.get("glue_tab_mm", 10.0)),
            "bleed_mm": float(printing.get("bleed_mm", 3.0)), "safe_margin_mm": float(printing.get("safe_margin_mm", 4.0))}
    applied = tuple(c for c in adapter.domain_constraints if c.name not in NOT_APPLIED)
    corrected = registry.recommended_corrected_version(defn.template_id)
    fixed = adapter_for(f"{defn.template_id}@{registry.QUALIFIED_AS.get(corrected, corrected)}") \
        if corrected and corrected != qualified else None
    return {"template_key": f"{defn.template_id}/{defn.version}", "violations": evaluate_domain(user, applied),
            "not_applied": list(NOT_APPLIED),
            "corrected": ({"template_key": f"{defn.template_id}/{corrected}",
                           "violations": evaluate_domain(user, tuple(c for c in fixed.domain_constraints
                                                                     if c.name not in NOT_APPLIED))}
                          if fixed is not None else None)}


def gift_set_fit(task) -> dict | None:
    """The set's fit — the insert, the pieces' cut-outs and the carton's inner space, or the gate's refusals — or None
    when the piece has no size to fit from (the carton is then sized the packaging target's own way)."""
    from apps.ire import fit_grid
    unit = set_piece(task)
    if unit is None:
        return None
    n, source = set_count(task)
    fit = fit_grid.insert_for(n, unit, gate_refusal)
    fit["count_source"] = source
    return fit


class GiftSetTarget(PackagingTarget):
    """The packaging target, for a set: the same carton, the same gates, sized by the set's fit."""

    name = DesignTarget.GIFT_SET.value

    def concept_prompt_profile(self, aria) -> str:
        """[The owner's finding on design 119, 2026-10-03: "ONE ENGINE ... Concept pictures for drawing show the
        product alone ... straight-on".] A set's carton is drawn from its concept's map as every carton is: the set's
        own words, and the carton pictured to be traced (``CARTON_MAP_DIRECTIVE``) — it read "its front and one side
        visible", a picture no map reads square."""
        from apps.pipeline.targets.packaging import CARTON_MAP_DIRECTIVE
        return DIRECTIVE.replace("closed, its front and one side visible, the front carrying the design",
                                 "closed, the front carrying the design") + " " + CARTON_MAP_DIRECTIVE

    def begin_output(self, aria, approved_image):
        super().begin_output(aria, approved_image)          # the dieline estimate: sized from the set's fit
        if aria.task.status == "awaiting_gate_1":
            return          # [the owner's finding on design 119, 2026-10-03] stopped at Gate 1: no output was made for it
        fit = gift_set_fit(aria.task)
        output = aria.task.packaging_outputs.order_by("-id").first()
        if fit is not None and output is not None:
            spec = dict(output.spec_sheet or {})
            spec[FIT_KEY] = fit
            output.spec_sheet = spec
            output.save(update_fields=["spec_sheet"])

    def panel_defaults(self, task, info: dict) -> dict:
        n, _source = set_count(task)
        # [the owner's finding on design 119, 2026-10-03] a set's carton is a carton: his brief's back copy, and never
        # another product's supplier text (``PackagingTarget.panel_defaults``), before the set's own words
        out = PackagingTarget.panel_defaults(self, task, info)
        if out.get("net_weight"):
            out["net_weight"] = f"{n} × {out['net_weight']}"
        out["item_no"], out["barcode_ean"] = "", ""          # one piece's would ring up one piece; the set has none
        return out

    def design_metadata(self, task, metadata: dict) -> dict:
        n, _source = set_count(task)
        return {**metadata, "product_type": f"Gift set of {n}"}

    def carton_template_version(self, task) -> str | None:
        """[The owner's answer of 2026-09-27 to the §BH70 report's second question: "Yes, switch the Gift Set carton
        to the corrected flap."] The set's carton is drawn at the straight tuck end's corrected closure — the version
        the registry recommends for new work, 1.2, whose top flap is cut from the carton's depth — so a row of pieces
        wider than it stands closes. A colleague test-fits the first sample (§BH70(3))."""
        from apps.dielines import registry
        from apps.pipeline.agents.dieline_agent import TEMPLATE_TYPE
        # [his final goal, 2026-10-05, B2] the corrected flap, print-ready: 1.3 is 1.2's closure with its tuck folds
        # creased, their lock slits and the thumb notch
        return registry.print_ready_version(TEMPLATE_TYPE)

    def gate2_hold(self, task, output) -> dict | None:
        held = super().gate2_hold(task, output)        # the carton's front copy, held as any carton's is
        if held:
            return held
        q = die_qualification(output)
        if not q or not q["violations"]:
            return None
        return {"error": "DIMENSION_COMBINATION_UNSUPPORTED", "template_key": q["template_key"],
                "violations": q["violations"], "not_applied": q["not_applied"], "needs": _die_needs(q)}

    def review_sections(self, task) -> list[dict]:
        rows = super().review_sections(task)
        output = task.packaging_outputs.order_by("-id").first()
        fit = ((output.spec_sheet or {}).get(FIT_KEY) if output else None) or {}
        if fit.get("arrangement"):
            a, c = fit["arrangement"], fit["carton_inner"]
            rows.append({"label": "The set",
                         "value": f'{fit["units"]} pieces, {a["columns"]} × {a["rows"]} on an insert '
                                  f'({fit["count_source"]}) · the carton\'s inner space {c["w_mm"]:g} × {c["d_mm"]:g} × '
                                  f'{c["h_mm"]:g} mm'})
            raised = (f'the pieces raised {fit["insert_raised_mm"]:g} mm on it — the dimension gate\'s cartons are '
                      'taller than wide; ' if fit["insert_raised_mm"] else "")
            rows.append({"label": "The insert",
                         "value": f"each piece's cut-out on the record; {raised}its own die is not drawn"})
            q = die_qualification(output)
            if q and q["violations"]:
                rows.append({"label": "The die",
                             "value": f'HELD at Gate 2 — DIMENSION_COMBINATION_UNSUPPORTED ({q["template_key"]}): '
                                      + "; ".join(q["violations"]) + f" — needs {_die_needs(q)}"})
            rows.append({"label": "The panel",
                         "value": f'the content printed is the set\'s, {fit["units"]} × the piece\'s own; the piece\'s '
                                  "item number and barcode are not printed — a set has none on record, and one "
                                  "piece's would ring up one piece"})
        elif fit:
            u = fit["unit"]
            rows.append({"label": "The set",
                         "value": f'HELD — {fit["code"]}: the dimension gate refuses every arrangement of '
                                  f'{fit["units"]} pieces {u["width_mm"]:g} × {u["depth_mm"]:g} × {u["height_mm"]:g} mm '
                                  "— the carton is left for a person to enter"})
        return rows


def _die_needs(q: dict) -> str:
    c = q.get("corrected")
    if c and not c["violations"]:
        return (f'the corrected closure, {c["template_key"]}, which qualifies this carton — drawn only on the standard '
                "vector path, which this deployment does not run")
    return "a carton structure whose own domain holds this carton; none the registry offers for new work does"
