"""His answer of 2026-09-29 to the §BH71 report (OWNER_BLOCKER_CLEARANCE.md, the block of that date), (3): "Yes, redraw
91 and 89 on their records" — A DESIGN WAITING AT ITS REVIEW HAS ITS SHAPE CONFIRMED AGAIN, BEFORE HIS ACCEPTANCE.

The confirm endpoint keeps a confirmation it holds immutable — a different profile is refused, PROFILE_ALREADY_CONFIRMED
(UI-2A, 9e20cdc) — so a design confirmed as one shape could never be drawn as the shape its concept shows: the §BH71
report told him confirming round at the shape step was his act, and no screen of his could have done it. This is the
one other door, and it is narrow:
- the design waits at its review (awaiting_gate_2) with a confirmation on its record, and no acceptance of his stands
  for the picture it shows — once he has accepted a drawing, its shape is settled by his act;
- the shape confirmed again is a variant the form draws; the rest of the record stays as confirmed, a round or square
  lid's height its own width;
- the confirmation it had is kept whole in the design's history (``HISTORY_KEY``), and the new one says who made it and
  on whose word — never as his;
- its zones are the proposal the shape step shows for the new shape, confirmed as proposed, every refusal of the
  confirm endpoint's contract applied the same way, before a byte is written;
- the design moves to reconstruction by the same transition, its gate decision recorded with no user and its reason in
  words, and it is drawn again by the worker's own job.
Anything else is refused by name, and nothing is written.
"""
from __future__ import annotations

import datetime

#: the design's confirmations before the one on its record, oldest first, each kept whole with who replaced it and why
HISTORY_KEY = "container_confirmation_history"

NOT_A_CONTAINER = "SHAPE_RECONFIRM_NOT_A_PRODUCT_CONTAINER"
NOT_AT_REVIEW = "SHAPE_RECONFIRM_NOT_WAITING_AT_ITS_REVIEW"
NOTHING_CONFIRMED = "SHAPE_RECONFIRM_NOTHING_CONFIRMED"
AFTER_HIS_ACCEPTANCE = "SHAPE_RECONFIRM_AFTER_HIS_ACCEPTANCE"
UNCHANGED = "SHAPE_RECONFIRM_THE_SAME_SHAPE"
VARIANT_NOT_DRAWN = "SHAPE_RECONFIRM_A_SHAPE_THE_FORM_DOES_NOT_DRAW"
REFUSED_BY_THE_CONTRACT = "SHAPE_RECONFIRM_REFUSED_BY_THE_CONTRACT"
CONFLICT = "SHAPE_RECONFIRM_CONFLICT"


class Refused(Exception):
    """A re-confirmation refused by name — nothing written."""

    def __init__(self, code, words):
        super().__init__("%s: %s" % (code, words))
        self.code, self.words = code, words


def _square_in_plan(archetype, variant) -> bool:
    """A lid seen from above as long as it is wide — a round or a square lid of a form drawn in plan."""
    from apps.pipeline.targets.container import archetypes as declared
    return declared.drawn_as_of(archetype) == declared.PLAN and variant in ("round", "square")


#: [B1, the clean-up of 2026-10-04] the kinds of confirmation a design's record can hold, as the badge on its
#: confirmed shape says them (``confirmation_provenance``) — it read "Confirmed by a person" whoever confirmed it
PROVENANCE_ON_A_WORD, PROVENANCE_THE_VIEWER, PROVENANCE_A_REVIEWER, PROVENANCE_NOBODY = (
    "on_a_word", "the_viewer", "a_reviewer", "nobody")


def confirmation_provenance(confirmation: dict | None, *, viewer: str, viewer_is_owner: bool) -> dict:
    """[B1 — the badge's words approved by the owner with the clean-up list, transcribed at b5892f9.] Who confirmed a
    design's shape, as its record (``spec_sheet["container_confirmation"]``) says it, in words for the person
    looking — ``{"kind", "by", "on_word_of", "words"}``:
    - confirmed again on someone's word (``reconfirm`` writes ``on_word_of``): "Confirmed again by the executor on
      your word — not by you", the word quoted after it; to anyone but the owner, "on the owner's word — not by the
      owner";
    - confirmed by the person looking (the confirm door writes their user name): "Confirmed by you";
    - confirmed by another reviewer: "Confirmed by {name}";
    - nothing on the record says who: "Not confirmed by a person".
    Each name is carried as the record holds it; the page escapes it."""
    record = confirmation if isinstance(confirmation, dict) else {}
    by = str(record["confirmed_by"]).strip() if record.get("confirmed_by") else ""
    word = str(record["on_word_of"]).strip() if record.get("on_word_of") else ""
    if word:
        whose, who = ("your", "you") if viewer_is_owner else ("the owner's", "the owner")
        kind = PROVENANCE_ON_A_WORD
        words = "%s on %s word — not by %s: “%s”" % ("Confirmed again by " + by if by else "Confirmed again",
                                                  whose, who, word)
    elif by and by == viewer:
        kind, words = PROVENANCE_THE_VIEWER, "Confirmed by you"
    elif by:
        kind, words = PROVENANCE_A_REVIEWER, "Confirmed by %s" % by
    else:
        kind, words = PROVENANCE_NOBODY, "Not confirmed by a person"
    return {"kind": kind, "by": by, "on_word_of": word, "words": words}


def reconfirm(task, *, variant: str, by: str, on_word_of: str, dispatch=None) -> dict:
    """The shape of ``task``'s design, waiting at its review, confirmed again as ``variant`` — ``by`` who made it and
    ``on_word_of`` whose word it rests on, both in words on the record; ``dispatch`` stands in for the worker job's
    ``delay`` (tests). Returns what was done; raises ``Refused`` with nothing written."""
    from django.db import transaction

    from apps.dashboard.exploration_render import confirmed_profile
    from apps.dashboard.owner_channel import preview_sha256
    from apps.ire.container_production_readiness import HDA_ACCEPTED, human_design_acceptance
    from apps.pipeline.models import GateDecision
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets.container import archetypes as declared
    from apps.pipeline.targets.container import name_fits_front
    from apps.pipeline.targets.container.silhouettes import ContainerProfile
    from apps.pipeline.targets.ui import PROFILE_AUTHORITY, validate_container_profile_payload
    from apps.pipeline.views import _transition

    if task.design_target != "product_container":
        raise Refused(NOT_A_CONTAINER, "only a Product Container design has a shape to confirm")
    if task.status != "awaiting_gate_2":
        raise Refused(NOT_AT_REVIEW, "the design is %s, not waiting at its review" % task.status)
    output = task.current_output()
    if output is None or not output.spec_sheet:
        raise Refused(NOTHING_CONFIRMED, "no confirmed shape is on its record")
    spec = dict(output.spec_sheet)
    before = spec.get("container_confirmation")
    old = spec.get(cc.PROFILE_SCHEMA)
    if not before or not old or old.get("confirmation_state") != "CONFIRMED":
        raise Refused(NOTHING_CONFIRMED, "no confirmed shape is on its record")
    if human_design_acceptance(spec, preview_sha256(output)[0]).get("state") == HDA_ACCEPTED:
        raise Refused(AFTER_HIS_ACCEPTANCE, "he has accepted the picture it shows: its shape is his act now")
    archetype = old.get("archetype")
    was = confirmed_profile(spec)
    if variant == was.get("variant"):
        raise Refused(UNCHANGED, "it is confirmed as %s already" % variant)
    drawn = [key for key, _label in declared.variants_of(archetype)]
    if variant not in drawn:
        raise Refused(VARIANT_NOT_DRAWN, "a %s is not drawn as %r — it draws %s" % (archetype, variant, ", ".join(drawn)))
    # a field the form does not have is left out of the check, as a confirmation made today never carries it: a record
    # confirmed before §BH70(1), item 17 still holds a bottle's neck ratio on a compact (89's, 0.42), and the editor's
    # own rules refuse to fill one — the value stays on the record, unread, as it always was
    not_applying = cc.fields_not_applying(archetype)
    payload = {k: v for k, v in dict(was, variant=variant).items() if k not in not_applying}
    if _square_in_plan(archetype, variant):
        payload["height_mm"] = payload["width_mm"]          # a round or square lid is as long as it is wide
    problems = validate_container_profile_payload(payload)
    if problems:
        raise Refused(REFUSED_BY_THE_CONTRACT, "; ".join(str(p) for p in problems))
    record = cc.merge_user_profile(old, {"variant": variant, "body_height_mm": payload["height_mm"]})
    zones = []
    for zone in cc.augment_code_zones(record, cc.propose_zones(record)):
        zone = dict(zone, user_confirmation_state=cc.ZONE_USER_CONFIRMED)
        zone["zone_hash"] = cc.zone_hash(zone)
        zones.append(zone)
    code = cc.evaluate_confirmation(record, zones)
    if code is not None:
        detail = cc.profile_is_confirmable(record) if code == cc.PROFILE_CONFIRMATION_REQUIRED else \
            cc.validate_zone_set(zones, record)
        raise Refused(REFUSED_BY_THE_CONTRACT, "%s — %s" % (code, "; ".join(str(d) for d in detail)))
    stop = name_fits_front(ContainerProfile(archetype=archetype, variant=variant, cap_style=payload.get("cap_style"),
                                            height_mm=float(payload["height_mm"]), width_mm=float(payload["width_mm"])),
                           spec["product_name"] if "product_name" in spec else "")
    if stop:
        raise Refused(REFUSED_BY_THE_CONTRACT, "%s — %s" % (stop["code"], stop["reason"]))

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record.update(confirmation_state="CONFIRMED", confirmed_at=now, confirmed_by=by,
                  not_applying=sorted(not_applying))         # said beside the fields, outside the hash (§BH70(1))
    history = list(spec[HISTORY_KEY]) if HISTORY_KEY in spec else []
    history.append({"replaced_at": now, "replaced_by": by, "on_word_of": on_word_of, "confirmation": before,
                    "profile": old, "zones": spec.get(cc.ZONES_SCHEMA)})
    combined = cc.combined_confirmation_hash(record, zones)
    zone_block = spec.get(cc.ZONES_SCHEMA)
    exclusions = zone_block.get("exclusions") if isinstance(zone_block, dict) else None
    spec[HISTORY_KEY] = history
    spec[cc.PROFILE_SCHEMA] = record
    spec[cc.ZONES_SCHEMA] = cc.zone_set_record(zones, record, confirmation_state="CONFIRMED", confirmed_by=by,
                                               confirmed_at=now, **({"exclusions": exclusions} if exclusions else {}))
    spec["container_confirmation"] = {"combined_hash": combined, "confirmed_at": now, "confirmed_by": by,
                                      "authority": PROFILE_AUTHORITY, "on_word_of": on_word_of,
                                      "replaces": before.get("combined_hash")}
    spec.pop("generation_error", None)
    notes = ("Confirmed again as %s by %s, on %s — the confirmation before it (%s, hash %s) kept in the design's "
             "history" % (variant, by, on_word_of, was.get("variant"), str(before.get("combined_hash"))[:12]))
    with transaction.atomic():
        output.spec_sheet = spec
        output.save(update_fields=["spec_sheet"])
        if not _transition(task.id, "awaiting_gate_2", status="generating_dieline"):
            raise Refused(CONFLICT, "the design left its review while this was being written")
        decision = GateDecision.objects.create(task=task, gate="container_profile", decision="approve", notes=notes,
                                               decided_by=None)

    from apps.pipeline.tasks import resume_aria_container_profile
    clean = confirmed_profile(spec)
    run = dispatch if dispatch is not None else resume_aria_container_profile.delay
    result = run(task.id, output.id, clean)
    output.refresh_from_db()
    spec = dict(output.spec_sheet)
    spec["container_resume"] = {"celery_task_id": str(result.id), "requested_at": now,
                                "requested_by": by, "kind": "RECONFIRMATION"}
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    return {"task_id": task.id, "variant": variant, "was": was.get("variant"), "combined_hash": combined,
            "gate_decision_id": decision.id, "history": len(history)}


def reopen(task, *, by: str, on_word_of: str) -> dict:
    """[His yes of 2026-09-30 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 5d23649): design 117's print area re-proposed
    from his concept, which prints edge to edge where his confirmed front was 35 x 99 mm in the middle; "You'd then
    re-confirm it at 117's shape step. I can't confirm it for you."] A design waiting at its review, its shape confirmed
    and no acceptance of his standing for the picture it shows, REOPENED at its shape step for HIM to confirm again —
    ``by`` who reopened it and ``on_word_of`` whose word it rests on, in words on the record:
    - its confirmation kept whole in its history (``HISTORY_KEY``), with the profile and the print areas it confirmed;
    - the confirmation lifted, so the shape step's confirm door takes his new one as a first;
    - the profile it had left as the step's starting point, marked unconfirmed;
    - its print areas proposed afresh — from the concept's map where one is on record for its approved picture
      (``targets.container.proposal_for``), else the contract's — every one PROPOSED, none confirmed;
    - the design moved back to its shape step.
    Nothing is confirmed for him and nothing is drawn. Refused by name, with nothing written, as ``reconfirm`` refuses:
    not a container, not at its review, nothing confirmed, or after his acceptance."""
    from django.db import transaction

    from apps.dashboard.owner_channel import preview_sha256
    from apps.ire.container_production_readiness import HDA_ACCEPTED, human_design_acceptance
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets.container import proposal_for
    from apps.pipeline.views import _transition

    if task.design_target != "product_container":
        raise Refused(NOT_A_CONTAINER, "only a Product Container design has a shape to confirm")
    if task.status != "awaiting_gate_2":
        raise Refused(NOT_AT_REVIEW, "the design is %s, not waiting at its review" % task.status)
    output = task.current_output()
    if output is None or not output.spec_sheet:
        raise Refused(NOTHING_CONFIRMED, "no confirmed shape is on its record")
    spec = dict(output.spec_sheet)
    before = spec.get("container_confirmation")
    old = spec.get(cc.PROFILE_SCHEMA)
    if not before or not old or old.get("confirmation_state") != "CONFIRMED":
        raise Refused(NOTHING_CONFIRMED, "no confirmed shape is on its record")
    if human_design_acceptance(spec, preview_sha256(output)[0]).get("state") == HDA_ACCEPTED:
        raise Refused(AFTER_HIS_ACCEPTANCE, "he has accepted the picture it shows: its shape is his act now")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    history = list(spec[HISTORY_KEY]) if HISTORY_KEY in spec else []
    history.append({"replaced_at": now, "replaced_by": by, "on_word_of": on_word_of, "confirmation": before,
                    "profile": old, "zones": spec.get(cc.ZONES_SCHEMA), "reopened": True})
    record = dict(old, confirmation_state="UNCONFIRMED", confirmed_at="", confirmed_by="")
    zone_block = spec.get(cc.ZONES_SCHEMA)
    exclusions = zone_block.get("exclusions") if isinstance(zone_block, dict) else None
    spec[HISTORY_KEY] = history
    spec[cc.PROFILE_SCHEMA] = record
    spec[cc.ZONES_SCHEMA] = cc.zone_set_record(proposal_for(record, spec, output), record,
                                               confirmation_state="PROPOSED",
                                               **({"exclusions": exclusions} if exclusions else {}))
    spec.pop("container_confirmation")
    spec.pop("generation_error", None)
    spec["container_reopened"] = {"reopened_at": now, "by": by, "on_word_of": on_word_of,
                                  "replaces": before.get("combined_hash")}
    with transaction.atomic():
        output.spec_sheet = spec
        output.save(update_fields=["spec_sheet"])
        if not _transition(task.id, "awaiting_gate_2", status="awaiting_container_profile"):
            raise Refused(CONFLICT, "the design left its review while this was being written")
    return {"task_id": task.id, "history": len(history), "replaces": before.get("combined_hash"),
            "front": next((z for z in spec[cc.ZONES_SCHEMA]["zones"] if z.get("zone_type") == "FRONT_PRINT_ZONE"),
                          None)}
