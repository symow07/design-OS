"""§BH71 PART 3, THE OWNER'S GOAL OF 2026-09-28 — "When a concept shows a shape the system doesn't know, it says so and
offers to learn it. It never squeezes a product into the wrong shape."

A LEARNED SHAPE: a lid shape no declared variant of a form drawn in plan draws, taught to the system at the shape step
by a person's one click — only from an approved concept whose OWN traced outline shows it (its proposal's
``unknown_shape`` said from "the approved concept", never a brief's words alone), and only of a kind whose geometry the
system draws from a trace (``LEARNABLE``: an oval — an ellipse in the width and length a person confirms). From then on
it is a variant of its form at every design's shape step (``variants_for``), accepted by the validation, proposed when
a concept or a brief shows it (``traced_variants``, ``variant_named``) and drawn from its geometry, which its variant
key itself names — the drawing and the zones read "learned_oval" with no lookup (``silhouettes``,
``container_contract``). Every other kind is said, not learned: its geometry is not one the system holds.
"""
from __future__ import annotations

import copy

#: kind -> the label its variant carries: the lid shapes the system draws from a trace
LEARNABLE = {"oval": "Oval"}
#: the variant key of a learned shape is this prefix and its kind — "learned_oval"
PREFIX = "learned_"
#: the stops, by name
NOT_LEARNABLE = "CONTAINER_SHAPE_NOT_LEARNABLE"
LEARNED_SHAPE_MISSING = "CONTAINER_LEARNED_SHAPE_MISSING"
#: the source an unknown shape must be said from to be learned (``targets.container._unknown_shape_on``)
FROM_THE_CONCEPT = "the approved concept"


class NotLearnable(ValueError):
    """A learn the task's own proposal does not support — its code and the reason in words; nothing is written."""

    def __init__(self, reason: str):
        super().__init__("%s: %s" % (NOT_LEARNABLE, reason))
        self.code = NOT_LEARNABLE
        self.reason = reason


def variant_key(kind: str) -> str:
    """The variant a learned kind is offered as — "learned_oval"."""
    return PREFIX + str(kind)


def kind_of(variant) -> str | None:
    """The learned kind a variant key names — "oval" for "learned_oval" — or None for any other key."""
    if variant is None:
        return None
    text = str(variant)
    if not text.startswith(PREFIX):
        return None
    return text[len(PREFIX):]


def _rows(form: str) -> list:
    from apps.pipeline.models import LearnedShape
    return list(LearnedShape.objects.filter(form=form).order_by("id"))


def variants_for(form: str) -> list:
    """``[(variant key, label)]`` — the lid shapes this form has learned, oldest first."""
    return [(variant_key(row.kind), "%s (learned)" % row.label) for row in _rows(form)]


def find(form: str, variant):
    """The LearnedShape row a variant key names for this form, or None."""
    kind = kind_of(variant)
    if kind is None:
        return None
    from apps.pipeline.models import LearnedShape
    return LearnedShape.objects.filter(form=form, kind=kind).first()


def traced_variants(form: str) -> dict:
    """``{trace kind: variant key}`` — the form's declared names for its traced lids, and its learned ones; nothing
    for a form the declaration does not know (a brief that names none)."""
    from apps.pipeline.targets.container import archetypes as _declared
    out = {}
    if not _declared.is_known(form):
        return out
    declared = _declared.traced_variants_of(form)
    if declared:
        out.update(declared)
    for row in _rows(form):
        out[row.kind] = variant_key(row.kind)
    return out


def variant_named(form: str, kind) -> str | None:
    """The learned variant a lid shape a brief names is, for this form — or None when the form has not learned it."""
    if kind is None:
        return None
    row = find(form, variant_key(kind))
    if row is None:
        return None
    return variant_key(row.kind)


def learnable(record) -> dict | None:
    """The shape a task's own proposal lets a person learn — its ``unknown_shape`` when the approved concept's own
    traced outline shows it and the system draws its kind — else None."""
    if not isinstance(record, dict):
        return None
    shape = record.get("unknown_shape")
    if not isinstance(shape, dict):
        return None
    if shape.get("source") != FROM_THE_CONCEPT or shape.get("kind") not in LEARNABLE:
        return None
    return shape


def learn(task, user) -> tuple:
    """(the LearnedShape, whether it is new) — the lid shape the task's own proposal shows, learned at a person's word,
    and the task's proposal re-proposed with it (``_repropose``). Refuses by name (``NotLearnable``), writing nothing,
    when the proposal shows no learnable shape: a shape only a brief's words name, one the system does not draw, or a
    proposal whose concept trace is not on its record."""
    from apps.pipeline.models import LearnedShape
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.services import container_contract as cc
    output = task.packaging_outputs.order_by("-id").first()
    if output is None or not isinstance(output.spec_sheet, dict):
        raise NotLearnable("the design has no shape proposal to learn from")
    spec = output.spec_sheet
    record = spec.get(cc.PROFILE_SCHEMA)
    shape = learnable(record)
    if shape is None and isinstance(record, dict) and kind_of(record.get("variant")) is not None:
        # a second click, or a replay: the proposal already carries the shape it learned — nothing more to do
        row = find(record["archetype"], record.get("variant"))
        if row is not None:
            return row, False
    if shape is None:
        raise NotLearnable("its proposal shows no lid the system can learn — it learns only a shape the approved "
                           "concept's own traced outline shows, of a kind it draws (an oval); a brief's words alone "
                           "never teach it one")
    trace = spec.get(co.SCHEMA)
    if not isinstance(trace, dict) or trace.get("kind") != shape["kind"] or not trace.get("source_sha256"):
        raise NotLearnable("the approved concept's trace is not on the design's record")
    row = LearnedShape.objects.filter(form=record["archetype"], kind=shape["kind"]).first()
    created = row is None
    if created:
        row = LearnedShape.objects.create(
            form=record["archetype"], kind=shape["kind"], label=LEARNABLE[shape["kind"]],
            geometry={"kind": shape["kind"], "aspect_seen": trace.get("aspect")}, source_task=task,
            source_sha256=trace["source_sha256"], learned_by=user)
    output.spec_sheet = _repropose(spec, row, trace)
    output.save(update_fields=["spec_sheet"])
    return row, created


def _repropose(spec: dict, row, trace: dict) -> dict:
    """The task's spec with the learned shape proposed: its variant; the lid's length from the picture's aspect AS
    SEEN — a tilted circle and an oval seen square-on read alike, so it is a proposal a person confirms; the shape no
    longer said unknown; its zones and its code place proposed for it, through the zone block's one writer."""
    from apps.pipeline.services import container_contract as cc
    out = copy.deepcopy(spec)
    record = out[cc.PROFILE_SCHEMA]
    record.pop("unknown_shape")
    record["variant"] = variant_key(row.kind)
    record["fields"]["variant"] = cc._field(record["variant"], source=cc.SRC_INFERRED, verification=cc.INFERRED)
    width = (record["fields"].get("body_width_mm") or {}).get("value")
    aspect = trace.get("aspect")
    if width is not None and aspect:
        record["fields"]["body_height_mm"] = cc._field(round(float(width) * float(aspect), 1), source=cc.SRC_INFERRED,
                                                       verification=cc.INFERRED)
    record["profile_hash"] = cc.profile_hash(record)
    legacy = out.get("container_profile")
    if isinstance(legacy, dict):
        legacy["variant"] = record["variant"]
    zones = cc.augment_code_zones(record, cc.propose_zones(record))
    out[cc.ZONES_SCHEMA] = cc.zone_set_record(zones, record, confirmation_state="PROPOSED")
    return out
