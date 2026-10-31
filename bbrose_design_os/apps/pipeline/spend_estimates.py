"""§BH54(k) 1 — WHAT A CLICK WILL COST, SAID BEFORE THE CLICK.

"Start a design from the dashboard — target, brief, brand — and watch it run, with what it is doing visible rather than a
spinner." (OWNER RULING §BH54(k) 1.) Starting a design, regenerating its images and retrying it are SPENDS; until this
module no page stated a cost before a click, and the task badge never showed what a run had spent. The figures here are
MEASURED on this system's own cost ledger (`ApiCallRecord`, one row per external AI call) — what past clicks cost, with
the number of tasks each figure rests on — and are never a quote or a promise. Reads rows; writes nothing; calls nobody.
"""
from __future__ import annotations

from statistics import median

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Sum

_CACHE_KEY = "pipeline:spend_estimates/2"      # §BH55 Phase 3: the payload carries each paid step now
_TTL_SECONDS = 60
BASIS = "measured on this system's own cost ledger — what past clicks cost, never a quote"


#: a drawn set is three concepts — the count the rerun has always used, one picture per prompt (image_producer.py)
SET_SIZE = 3


def _usd(value) -> float:
    return round(float(value or 0), 2)


def measured_costs() -> dict:
    """Per design target: how many tasks spent, and their least, median and greatest spend; the measured price of one
    image and of one QA read; and from those, the three images a rerun draws. Cached for a minute: the status payload
    is polled."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached
    from apps.pipeline.models import ApiCallRecord

    per_target: dict = {}
    rows = (ApiCallRecord.objects.exclude(task=None).values("task_id", "task__design_target")
            .annotate(spent=Sum("cost_usd")))
    for row in rows:
        per_target.setdefault(row["task__design_target"] or "unknown", []).append(float(row["spent"] or 0))
    # §BH55 Phase 3: each PAID STEP of the path, measured the same way — on the operations the step itself records.
    # [E3, the clean-up of 2026-10-04] no carton has made a flat-artwork or background edit since the owner's finding
    # on design 119 (cd52e1f): their old `image:flat_artwork` rows stay on the ledger, as history, and are priced no more
    def _each(**flt):
        row = ApiCallRecord.objects.filter(**flt).aggregate(each=Avg("cost_usd"), rows=Count("id"))
        return float(row["each"] or 0), row["rows"]

    directions_usd, directions_rows = _each(operation="creative_directions")
    prompts_usd, prompts_rows = _each(operation="image_prompts")
    estimate_usd, estimate_rows = _each(operation="dieline_estimation")
    translate_usd, translate_rows = _each(operation="panel_translation")
    read_usd, read_rows = _each(operation="inspiration_read")         # §BH69(2): one inspiration picture read
    # [his go of 2026-10-02] the design map's read, once per approved concept of a container design
    map_usd, map_rows = _each(operation="container_design_map_parts")
    translated = bool(settings.PANEL_TRANSLATE_ENABLED and settings.ANTHROPIC_API_KEY)
    image = ApiCallRecord.objects.filter(image_count__gt=0).aggregate(each=Avg("cost_usd"), rows=Count("id"))
    review = ApiCallRecord.objects.filter(operation="qa_vision_review").aggregate(each=Avg("cost_usd"), rows=Count("id"))
    image_usd, review_usd = float(image["each"] or 0), float(review["each"] or 0)
    costs = {
        "basis": BASIS,
        "ledger_rows": ApiCallRecord.objects.count(),
        "start_design": [{"target": target, "tasks": len(spent), "min_usd": _usd(min(spent)),
                          "median_usd": _usd(median(spent)), "max_usd": _usd(max(spent))}
                         for target, spent in sorted(per_target.items()) if spent],
        "image_usd": round(image_usd, 4), "image_rows": image["rows"],
        "qa_per_image_usd": round(review_usd, 4), "qa_rows": review["rows"],
        "rerun_images": {"images": SET_SIZE, "usd": _usd(SET_SIZE * (image_usd + review_usd))},
        # what a click on each paid step of the path costs — the parts each one runs, measured
        "steps": {
            "choose_direction": {"usd": _usd(prompts_usd + SET_SIZE * (image_usd + review_usd)), "images": SET_SIZE,
                                 "rows": min(prompts_rows, image["rows"], review["rows"])},
            "ask_for_changes": {"usd": _usd(directions_usd), "rows": directions_rows},
            "size_estimate": {"usd": _usd(estimate_usd), "rows": estimate_rows},
            # a read costs about a cent: to the tenth of a cent, measured once there are reads on the ledger
            "inspiration_read": {"usd": round(read_usd, 3), "rows": read_rows},
            "design_map_read": {"usd": _usd(map_usd), "rows": map_rows},
            # [E3] making the design spends on the label copy's translation only, where it is switched on — no
            # picture is made or edited for a carton (aria.py, resume_after_dimensions)
            "make_the_design": {"usd": _usd(translate_usd if translated else 0),
                                "rows": translate_rows if translated else 0, "translated": translated},
        },
        # what the paid steps use, from the settings the code reads before it spends
        "machine": {"image_model": settings.IMAGE_MODEL, "image_size": settings.IMAGE_SIZE, "set_size": SET_SIZE,
                    "redraws": int(settings.MAX_REVISION_PASSES), "translated": translated},
    }
    cache.set(_CACHE_KEY, costs, _TTL_SECONDS)
    return costs
