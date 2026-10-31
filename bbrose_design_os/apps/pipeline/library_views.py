"""The finished-design helpers the dashboard's Library reads (apps/dashboard/views.py: the finished designs'
list, each one's card and its own page) — a design's picture, its name, its size and its approvals in words,
and the filters that find it (Postgres full-text over the brief and product name where available,
``icontains`` elsewhere).

[Milestone 12.3 built this module as the /api/library/ list, detail and "start from existing" doors with their
serializers. The clean-up of 2026-10-04 (E10b, on the owner's approved list) removed those doors, which no page
called; git history keeps them. The helpers the Library's pages read stay here.]
"""
from __future__ import annotations

from django.db import connection
from django.db.models import Q


def _picture(output):
    """§BH55 Phase 3: a finished design's own picture — the design on its dieline, or its page — before the concept it
    was made from, which the Library showed in its place. Returns (file, "design" | "concept") or (None, None)."""
    if output.design_preview:
        return output.design_preview, "design"
    img = output.approved_image
    if img and img.image_file:
        return img.image_file, "concept"
    return None, None


def _title(task):
    """The design's name as the list shows it: the first line of what was asked (a project's name, when one was given,
    is that first line)."""
    lines = (task.task_text or "").strip().splitlines()
    first = lines[0].strip() if lines else ""
    return (first[:79] + "…") if len(first) > 80 else (first or "A finished design")


def _size_words(spec):
    """§BH55 Phase 3: the size a design was made at, in words. The Library read "dimensions" or "manufacture", which no
    finished design's record here carries (both printed "{}"); the size step saves the confirmed size."""
    d = spec.get("confirmed_dimensions") or spec.get("dimensions") or {}
    whd = [d.get(k) for k in ("width_mm", "depth_mm", "height_mm")]
    words = []
    if all(isinstance(v, (int, float)) for v in whd):
        words.append("%s × %s × %s mm (width × depth × height)" % tuple(f"{v:g}" for v in whd))
    if spec.get("template"):
        words.append(str(spec["template"]).replace("_", " ").capitalize())
    return " · ".join(words)


# §BH55 Phase 3: a gate decision in the words a designer reads — the Library printed the decisions as raw JSON
_DECISION_WORDS = {
    ("gate_1", "approve"): "Concept chosen", ("gate_1", "reject"): "Changes asked for the concepts",
    ("dimension", "approve"): "Size confirmed", ("dimension", "reject"): "Size sent back",
    ("container_profile", "approve"): "Shape confirmed", ("container_profile", "reject"): "Shape sent back",
    ("design_intent", "approve"): "Design intent confirmed", ("design_intent", "reject"): "Design intent sent back",
    ("gate_2", "approve"): "Design approved", ("gate_2", "reject"): "Changes asked for the design",
}


def _approvals(task):
    return [{"words": _DECISION_WORDS.get((g.gate, g.decision), f"{g.gate} — {g.decision}".replace("_", " ")),
             "by": g.decided_by.username if g.decided_by else None,
             "at": g.decided_at.isoformat() if g.decided_at else None, "notes": g.notes}
            for g in task.gate_decisions.select_related("decided_by").order_by("decided_at")]


def _apply_filters(qs, params):
    brand = params.get("brand")
    if brand:
        qs = qs.filter(task__brand_id=brand)
    category = params.get("category")
    if category:
        qs = qs.filter(task__product__category=category)
    date_from = params.get("date_from")
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    date_to = params.get("date_to")
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    q = (params.get("q") or "").strip()
    if q:
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import SearchQuery, SearchVector
            qs = qs.annotate(
                _sv=SearchVector("task__task_text", "task__product__name"),
            ).filter(_sv=SearchQuery(q))
        else:
            qs = qs.filter(
                Q(task__task_text__icontains=q)
                | Q(task__product__name__icontains=q)
            )
    return qs
