"""Dieline generation agent — replaces the role Pacdora played after Gate 1.

Two-phase, matching the AI Dieline Contract (docs/ai_dieline_contract.md in the
dieline-generator project):

  Phase 1 (estimate):  run() produces a DimensionExtractionResult and a
                       DielineJob. Scenario A reads exact dimensions straight
                       from the Product (no AI). Scenario B asks Claude to
                       estimate, and never invents geometry.
  Phase 2 (generate):  after a human confirms the dimensions, generate() runs
                       the deterministic geometry engine + SVG/AI exporters.

Claude only ever estimates scalar dimensions; all geometry is produced by the
deterministic code in apps.dielines.geometry.
"""
from __future__ import annotations

from django.conf import settings

from apps.dielines.constants import (
    DEFAULT_BLEED_MM,
    DEFAULT_GLUE_TAB_MM,
    DEFAULT_SAFE_MARGIN_MM,
)
from apps.dielines.models import DielineJob, DielineTemplate
from apps.dielines.services.export_service import generate_exports
from apps.dielines.validators.schema import (
    DielineInputJSON,
    DimensionExtractionResult,
    FieldEstimate,
)

#: [His second goal of 2026-10-06 (transcribed at c34a518), item 2: "TOP-TIER DIELINES".] Every carton a design draws
#: is the reverse tuck end (ECMA A20.20.03.01: the top tuck on the back, the bottom tuck on the front) — the opposed
#: layout of the house's approved reference die (DECISION-003), which versions 1.0–1.3 drew under the straight tuck
#: end's name. A straight tuck end hangs both tucks from one panel (apps/dielines/docs/TRADE_RULES.md §1).
TEMPLATE_TYPE = "reverse_tuck_end_carton"

_BLOCKED_FIELD = FieldEstimate(value=None, confidence=0.0, source="manual", blocked=True)

_SYSTEM_PROMPT = """\
You are a packaging engineer AI. Your job is to estimate the physical dimensions
of a cosmetic product carton from the provided context.

Return ONLY valid JSON — no markdown, no preamble, no explanation.

The JSON must match this exact schema:
{
  "width_mm":       {"value": float|null, "confidence": float, "source": string},
  "depth_mm":       {"value": float|null, "confidence": float, "source": string},
  "height_mm":      {"value": float|null, "confidence": float, "source": string},
  "bleed_mm":       {"value": float|null, "confidence": float, "source": string},
  "safe_margin_mm": {"value": float|null, "confidence": float, "source": string},
  "glue_tab_mm":    {"value": float|null, "confidence": float, "source": string}
}

Rules:
- confidence is a float between 0.0 and 1.0
- If confidence < 0.85, value MUST be null
- Be conservative — null is safer than a wrong number
- source must be one of: "image", "text", "pdf", "db", "manual"

Cosmetic product reference ranges (mm):
  width_mm:        12–50  (slim cosmetics)
  depth_mm:        12–40
  height_mm:       60–180
  bleed_mm:        always 3.0, confidence 1.0, source "db"
  safe_margin_mm:  always 4.0, confidence 1.0, source "db"
  glue_tab_mm:     8–12, default 10.0
"""


#: §BH55 PHASE 1 — THE FIT BETWEEN A CONTAINER AND ITS CARTON, MEASURED ON THE OWNER'S OWN RECORD AND NOT TYPED: product 5
#: is the one product whose record carries BOTH a carton (40 × 40 × 110 mm) and a confirmed container (33 × 33 mm body,
#: drawn 96.306 mm tall with its closure): (40 − 33) / 2 = 3.5 mm a side, (110 − 96.306) / 2 = 6.847 mm an end. ONE
#: instance, said as one; the alternative rejected is the paid estimate this replaces, which never saw the bottle. The
#: result is a PROPOSAL: it is shown at the dimension gate with its source, and whoever confirms may change it.
CONTAINER_FIT_SIDE_MM = 3.5
CONTAINER_FIT_END_MM = 6.847


def carton_minimums() -> dict:
    """§BH71 PART 3: the smallest carton the carton template makes, side by side in millimetres — read from the
    dimension schema's own lower bounds (``apps.dielines.validators.schema._Dimensions``: "anything below the minima
    produces a physically unprintable carton"), never typed here."""
    from annotated_types import Ge

    from apps.dielines.validators.schema import _Dimensions
    return {name: next(float(m.ge) for m in _Dimensions.model_fields[name].metadata if isinstance(m, Ge))
            for name in ("width_mm", "depth_mm", "height_mm")}


def _db_field(value, confidence=1.0):
    return FieldEstimate(value=float(value), confidence=confidence, source="db", blocked=False)


def carton_input(confirmed_dims: dict, metadata: dict | None = None, template_version=None) -> DielineInputJSON:
    """The carton's die input for confirmed dimensions — one construction for its drawing (``DielineAgent.generate``)
    and for the check of its concepts at the size it will be drawn ([his second test blocker on design 123, 2026-10-09
    (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2)])."""
    metadata = metadata or {}
    return DielineInputJSON(
        template=TEMPLATE_TYPE,
        # [the owner's answer of 2026-09-27: a gift set's carton is drawn on the corrected flap — its target says
        # which version (`carton_template_version`); None is the current one, as before]
        template_version=template_version,
        unit="mm",
        dimensions={
            "width_mm": confirmed_dims["width_mm"],
            "depth_mm": confirmed_dims["depth_mm"],
            "height_mm": confirmed_dims["height_mm"],
        },
        print_settings={
            "bleed_mm": confirmed_dims.get("bleed_mm", DEFAULT_BLEED_MM),
            "safe_margin_mm": confirmed_dims.get("safe_margin_mm", DEFAULT_SAFE_MARGIN_MM),
        },
        construction={
            "glue_tab_mm": confirmed_dims.get("glue_tab_mm", DEFAULT_GLUE_TAB_MM),
            # Hardening 2026-07-04 (audit C5): the dimension gate confirms
            # board thickness + compensation; absent keys keep the legacy
            # (uncompensated) defaults so old callers are unchanged.
            "board_thickness_mm": confirmed_dims.get("board_thickness_mm", 0.35),
            "thickness_compensation": bool(
                confirmed_dims.get("thickness_compensation", False)
            ),
        },
        metadata={
            "product_name": metadata.get("product_name", ""),
            "product_type": metadata.get("product_type", ""),
            "notes": metadata.get("notes", ""),
        },
    )


#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (6): "Flag
#: impossible sizes at the size step (I typed 1123 mm for a 120 mm product; it accepted it)."] a side more than this many
#: times what its product needs is flagged as far larger than the product — a warning in words, never a refusal; a side
#: outside the die's own range, or smaller than the product, is impossible
FAR_LARGER = 2.0
SIDES = (("width_mm", "wide"), ("depth_mm", "deep"), ("height_mm", "tall"))


def size_flags(task, dims: dict) -> list:
    """[His test findings on design 123, (6).] Each side of ``dims`` the carton cannot be made at for its product —
    ``{"side", "level": "impossible" | "far", "words"}``, in his words: outside the range the carton's die is made in
    (``schema._Dimensions``), smaller than the product it holds (``DielineAgent.product_size``), or more than FAR_LARGER
    times the size the product needs (``proposed_without_ai``). Empty where nothing is known to flag."""
    from annotated_types import Ge, Le

    from apps.dielines.validators.schema import _Dimensions
    agent = DielineAgent(task)
    product, needs = agent.product_size(), agent.proposed_without_ai()
    out = []
    for side, way in SIDES:
        try:
            value = float(dims.get(side))
        except (TypeError, ValueError):
            continue
        meta = _Dimensions.model_fields[side].metadata
        least = next(float(m.ge) for m in meta if isinstance(m, Ge))
        most = next(float(m.le) for m in meta if isinstance(m, Le))
        held = (" — the product is %g mm %s" % (product[side], way)) if product else ""
        if value < least or value > most:
            out.append({"side": side, "level": "impossible",
                        "words": "%g mm %s is not a carton this die makes: it makes cartons %g to %g mm %s%s"
                                 % (value, way, least, most, way, held)})
        elif product and value < product[side]:
            out.append({"side": side, "level": "impossible",
                        "words": "%g mm %s is smaller than the product it holds (%g mm) — it would not go in"
                                 % (value, way, product[side])})
        elif needs and value > FAR_LARGER * needs[side]:
            out.append({"side": side, "level": "far",
                        "words": "%g mm %s is more than twice what the product needs (%g mm) — check it is the size "
                                 "you mean" % (value, way, needs[side])})
    return out


#: [His second test blocker on design 123, 2026-10-09, (2).] the size step's own proposal of board compensation: its
#: box is ticked unless he has entered otherwise (``static/js/gates.js``, ``compChecked``)
PROPOSED_COMPENSATION = True


class DielineAgent:
    def __init__(self, task, log_fn=None):
        self.task = task
        self.product = getattr(task, "product", None)
        self.log = log_fn or (lambda msg, data=None, level="info": None)

    # ------------------------------------------------------------------
    # Phase 1 — dimension estimation
    # ------------------------------------------------------------------

    def run(self):
        """Estimate dimensions and persist a DielineJob. Returns (result, job)."""
        scenario = self._determine_scenario()
        self.log(f"Dieline: scenario {scenario} determined")

        # §BH55 Phase 2: a GIFT SET's carton holds the set — sized from the set's own fit, never from one piece's record
        gift = self._gift_set_fit()
        container = None if (scenario == "A" or gift) else self._container_dimensions()
        if gift:
            scenario = "A"
            result = self._extract_from_gift_set(gift)
            a = gift["arrangement"]
            if a:
                self.log("Dieline: carton sized to hold the set — %d pieces, %d × %d on an insert (%s) — no AI needed" % (
                    gift["units"], a["columns"], a["rows"], gift["count_source"]))
            else:
                self.log("Dieline: %s — the dimension gate refuses every arrangement of the set; the carton is left "
                         "for a person to enter — no AI guess" % gift["code"])
        elif scenario == "A":
            result = self._extract_from_db()
            self.log("Dieline: dimensions read from product record (no AI needed)")
        elif container:
            # §BH55 Phase 1: one project — the carton is sized from the container stage, not guessed
            scenario = "A"
            result = self._extract_from_container(container)
            self.log("Dieline: carton sized from this project's container stage (task %s: %g × %g × %g mm, height = %s) "
                     "plus the fit measured on the owner's own record — no AI needed" % (
                         container["task"], container["width"], container["depth"], container["height"],
                         container["height_is"]))
        else:
            result = self._extract_from_context()
            self.log(
                "Dieline: dimensions estimated from context"
                if result.can_proceed
                else "Dieline: some dimensions need manual entry",
                level="info" if result.can_proceed else "warning",
            )

        job = DielineJob.objects.create(
            product=self.product,
            template_type=TEMPLATE_TYPE,
            scenario=scenario,
            input_json={},
            extraction_result=result.model_dump(),
            validation_status="pending",
        )
        self.log(f"Dieline: job {job.id} created, awaiting dimension confirmation")
        return result, job

    def proposed_without_ai(self) -> dict | None:
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2):
        "a concept shown as drawable must draw".] The dimensions the size step will propose where they come with no
        model call — a gift set's fit, the product's record, this project's container stage, as ``run`` reads them
        (no job made) — as confirmed dimensions, as the size step posts them untouched: its board thickness field
        blank, so the board the gate's own default gives it (``carton_input``, 0.35 mm), its compensation ticked; None
        where only an estimate could give them, or one is left for a person to enter."""
        gift = self._gift_set_fit()
        if gift:
            result = self._extract_from_gift_set(gift)
        elif self._determine_scenario() == "A":
            result = self._extract_from_db()
        else:
            container = self._container_dimensions()
            if not container:
                return None
            result = self._extract_from_container(container)
        keys = ("width_mm", "depth_mm", "height_mm", "bleed_mm", "safe_margin_mm", "glue_tab_mm")
        values = {key: getattr(result, key).value for key in keys}
        if any(value is None for value in values.values()):
            return None
        return dict({key: float(value) for key, value in values.items()}, thickness_compensation=PROPOSED_COMPENSATION)

    def product_size(self) -> dict | None:
        """[His test findings on design 123, (6).] The product the carton holds, in millimetres side by side — this
        project's container as its stage confirmed it (no fit added), else the product's record; None where neither
        gives it."""
        container = self._container_dimensions()
        if container:
            return {"width_mm": container["width"], "depth_mm": container["depth"], "height_mm": container["height"]}
        if self._determine_scenario() == "A":
            p = self.product
            return {"width_mm": float(p.width_mm), "depth_mm": float(p.depth_mm), "height_mm": float(p.height_mm)}
        return None

    def _determine_scenario(self):
        p = self.product
        if (
            p is not None
            and getattr(p, "width_mm", None)
            and getattr(p, "depth_mm", None)
            and getattr(p, "height_mm", None)
            and p.width_mm > 0
            and p.depth_mm > 0
            and p.height_mm > 0
        ):
            return "A"
        return "B"

    def _container_dimensions(self):
        """The container stage's own confirmed dimensions, when this task is the packaging stage of a project —
        read from that stage's governed record, never from the brief. The height is the DRAWN total where the
        record carries one (the closure stands above the body), else body + cap."""
        task = self.task
        if not getattr(task, "project_id", None) or getattr(task, "stage", "") != "packaging":
            return None
        source = task.project.tasks.filter(stage="container").order_by("-id").first()
        # [his goal of 2026-10-13, (2)] the container stage's accepted drawing, where he approved one — else its newest
        output = ((source.packaging_outputs.filter(is_final_approved=True).order_by("-id").first()
                   or source.packaging_outputs.order_by("-id").first()) if source else None)
        spec = (output.spec_sheet if output else None) or {}
        fields = (spec.get("container_profile/1.0") or {}).get("fields") or {}

        def val(name):
            return (fields.get(name) or {}).get("value")
        drawn = ((spec.get("container_drawing_source/1.0") or {}).get("geometry") or {}).get("total_height_mm")
        try:
            width = float(val("body_width_mm"))
            depth = float(val("body_depth_mm") or val("body_width_mm"))
            height = float(drawn) if drawn else float(val("body_height_mm")) + float(val("cap_height_mm") or 0)
        except (TypeError, ValueError):
            return None
        if min(width, depth, height) <= 0:
            return None
        # §BH70(1), items 8 and 16 of the list the owner was sent: A FORM DRAWN IN PLAN STANDS ON ITS EDGE IN ITS CARTON.
        # A compact's record holds its lid seen from above (its width and height) and its closed thickness (its
        # depth); read as a standing bottle's, its carton came out wider than tall — 117 x 25 x 108.7 mm for a 110 x 95
        # x 18 mm case — which the tuck-end carton it defaults to refuses, so a person had to retype it. Stood on its
        # edge, the lid's longer side is the carton's height: 102 x 25 x 123.7 mm. The fit margins are not touched —
        # measured on one dropper (§BH55 Phase 1) and frozen by §BH55(3); that they were measured on a dropper is on the
        # acceptance-time list.
        from apps.pipeline.targets.container import archetypes as _declared
        form = (spec.get("container_profile/1.0") or {}).get("archetype")
        if _declared.is_known(form) and _declared.drawn_as_of(form) == _declared.PLAN:
            # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front
            # is the lid's face (landscape). Use each container's real orientation for every form."] a face wider than
            # tall boxed lying flat — the same die, its front the lid's face seen as it is, landscape (``FLAT``); a face
            # taller than wide (a sachet) stands as its die does
            flat = width > height
            return {"task": source.id, "width": min(width, height), "depth": depth, "height": max(width, height),
                    "height_is": ("the longer side of its lid — its front, lying flat" if flat
                                  else "the longer side of its lid, the case standing on its edge"),
                    "on_edge": not flat, "flat": flat}
        return {"task": source.id, "width": width, "depth": depth, "height": height,
                "height_is": "the drawn total" if drawn else "body + cap"}

    def _extract_from_container(self, container):
        fit = {"width_mm": container["width"] + 2 * CONTAINER_FIT_SIDE_MM,
               "depth_mm": container["depth"] + 2 * CONTAINER_FIT_SIDE_MM,
               "height_mm": container["height"] + 2 * CONTAINER_FIT_END_MM}
        # §BH71 PART 3 (the owner's goal of 2026-09-28): a tin 42 mm across, stood on its edge, came to a carton 55.7 mm
        # tall and a sachet 3 mm thin to one 10 mm deep — under the template's own hard minimums, so the tuck-end
        # refused the carton it was proposed. A side under its minimum is raised to it, and the activity says which,
        # from what, to what; a carton over its minimums is exactly as it was.
        least = carton_minimums()
        raised = [(side, fit[side], least[side]) for side in ("width_mm", "depth_mm", "height_mm")
                  if fit[side] < least[side]]
        for side, _was, floor in raised:
            fit[side] = floor
        if raised:
            self.log("Dieline: the carton is raised to the smallest the carton template makes — %s; the product sits "
                     "in it with room to spare" % "; ".join("%s %.1f → %g mm" % (side[:-3], was, floor)
                                                             for side, was, floor in raised))
        return self._proposed_carton(fit["width_mm"], fit["depth_mm"], fit["height_mm"],
                                     "container lying flat" if container.get("flat") else
                                     "container on its edge" if container.get("on_edge") else "container",
                                     orientation="flat" if container.get("flat") else "standing")

    def _gift_set_fit(self):
        """§BH55 Phase 2: the set's fit when this task is a gift set (targets/gift_set.py), else None."""
        if getattr(self.task, "design_target", "") != "gift_set":
            return None
        from apps.pipeline.targets.gift_set import gift_set_fit
        return gift_set_fit(self.task)

    def _extract_from_gift_set(self, fit):
        c = fit["carton_inner"]
        if c is None:          # the gate refuses every arrangement: nothing is proposed, and nothing is guessed
            return self._proposed_carton(None, None, None, "gift set")
        return self._proposed_carton(c["w_mm"], c["d_mm"], c["h_mm"], "gift set")

    def _proposed_carton(self, width, depth, height, source, orientation="standing"):
        """A carton PROPOSED from what it must hold, with no model call, at the confidence the schema proposes and
        does not block at — the container stage's size (0496712) or a gift set's (§BH55 Phase 2), ONE helper for both
        (a copy is what the census found the first time); the template's print allowances beside it."""
        bleed, safe, glue = self._print_allowances()

        def proposed(value):
            if value is None:      # §BH55 Phase 2: nothing to propose — BLOCKED, for a person to enter
                return FieldEstimate(value=None, confidence=0.0, source=source, blocked=True)
            return FieldEstimate(value=round(value, 2), confidence=0.85, source=source, blocked=False)
        return DimensionExtractionResult(
            width_mm=proposed(width),
            depth_mm=proposed(depth),
            height_mm=proposed(height),
            bleed_mm=_db_field(bleed, confidence=0.90),
            safe_margin_mm=_db_field(safe, confidence=0.90),
            glue_tab_mm=_db_field(glue, confidence=0.90),
            scenario="A",
            can_proceed=height is not None,
            orientation=orientation,           # [his goal of 2026-10-13, (2)]
        )

    def _print_allowances(self):
        """(bleed, safe margin, glue tab) in mm — the carton template's own defaults, else this module's."""
        tpl = self._load_template()
        bleed = float(tpl.default_bleed_mm) if tpl else DEFAULT_BLEED_MM
        safe = float(tpl.default_safe_margin_mm) if tpl else DEFAULT_SAFE_MARGIN_MM
        glue = float(tpl.default_glue_tab_mm) if tpl else DEFAULT_GLUE_TAB_MM
        return bleed, safe, glue

    def _extract_from_db(self):
        p = self.product
        bleed, safe, glue = self._print_allowances()
        return DimensionExtractionResult(
            width_mm=_db_field(p.width_mm),
            depth_mm=_db_field(p.depth_mm),
            height_mm=_db_field(p.height_mm),
            bleed_mm=_db_field(bleed, confidence=0.90),
            safe_margin_mm=_db_field(safe, confidence=0.90),
            glue_tab_mm=_db_field(glue, confidence=0.90),
            scenario="A",
            can_proceed=True,
        )

    def _extract_from_context(self):
        try:
            raw = self._call_claude(self._build_context())
            return self._parse_claude_response(raw)
        except Exception as exc:
            self.log(f"Dieline: AI estimation failed — {exc}", level="warning")
            return self._blocked_result("B")

    def _blocked_result(self, scenario):
        b = _BLOCKED_FIELD
        return DimensionExtractionResult(
            width_mm=b, depth_mm=b, height_mm=b,
            bleed_mm=b, safe_margin_mm=b, glue_tab_mm=b,
            scenario=scenario, can_proceed=False,
        )

    def _build_context(self):
        parts = [
            f"Task ID: {self.task.pk}",
            f"Description: {getattr(self.task, 'task_text', '')}",
        ]
        p = self.product
        if p is not None:
            parts.append(f"Product: {p.name}")
            if getattr(p, "product_type", ""):
                parts.append(f"Product type: {p.product_type}")
            if getattr(p, "dimensions", ""):
                parts.append(f"Recorded dimensions (free text): {p.dimensions}")
        return "\n".join(parts)

    def _call_claude(self, context):
        # Route through the shared client so we get retry + prompt caching, and
        # the fast model since this is scalar estimation, not vision.
        from apps.pipeline.services.claude_service import call_claude, extract_text
        response = call_claude(
            _SYSTEM_PROMPT, context, max_tokens=1024,
            model=settings.CLAUDE_MODEL_FAST, operation="dieline_estimation",
        )
        return extract_text(response)

    def _parse_claude_response(self, raw):
        from apps.pipeline.services.claude_service import loads_tolerant
        data = loads_tolerant(raw)

        def _field(key):
            entry = data[key]
            confidence = float(entry["confidence"])
            value = entry.get("value")
            blocked = confidence < 0.85 or value is None
            return FieldEstimate(
                value=None if blocked else float(value),
                confidence=confidence,
                source=entry["source"],
                blocked=blocked,
            )

        fields = {
            k: _field(k)
            for k in ("width_mm", "depth_mm", "height_mm",
                      "bleed_mm", "safe_margin_mm", "glue_tab_mm")
        }
        return DimensionExtractionResult(
            **fields,
            scenario="B",
            can_proceed=not any(f.blocked for f in fields.values()),
        )

    def _load_template(self):
        return DielineTemplate.objects.filter(template_type=TEMPLATE_TYPE).first()

    # ------------------------------------------------------------------
    # Phase 2 — deterministic geometry + export
    # ------------------------------------------------------------------

    def generate(self, job, confirmed_dims, metadata=None, artwork_tint=None, panel_info=None,
                 template_version=None, map_front=None, inside=None):
        """Run geometry + exporters for confirmed dimensions.

        Delegates to the shared export service (Milestone 10.1, audit H4) so
        the agent path and the HTTP API path run the exact same pipeline:
        geometry engine → SVG → CMYK production PDF → .ai → spec JSON, all
        written to absolute paths under MEDIA_ROOT/dielines/<job_id>/ with
        no working-directory dependence.

        Returns a dict with the SVG string, the .ai path (or None), the
        geometry summary and any warnings. Raises ValueError on invalid
        input/geometry so the caller can surface it to the user.
        """
        params = carton_input(confirmed_dims, metadata, template_version)
        return generate_exports(job, params, log=self.log,
                                orientation=confirmed_dims.get("orientation"),   # [his goal of 2026-10-13, (2)]
                                artwork_tint=artwork_tint, panel_info=panel_info,
                                map_front=map_front,        # [his go of 2026-10-02] the front from its map
                                inside=inside)              # [his final goal, 2026-10-05, B1] the inside print
