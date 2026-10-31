"""PALT-M4C M4C-4 — human confirmation contract for palette design intent.

§G says only ``HUMAN_CONFIRMED_DESIGN_INTENT`` is design authority. This
module is the durable record of what the owner did to each drafted field,
so a confirmation survives a rebuild and is never inferred.

The owner may confirm, correct, delete, add, reclassify the constraint
level, mark a field unresolved, and attach a note. Every action is
recorded with what it changed, so a later reader can see the AI draft and
the owner's decision separately rather than a merged result.

Nothing here promotes an "approximately" reading into an exact fact. The
ES3083 draft carries pan_count ~12 and a ~4x3 layout as PROVISIONAL; only
an explicit owner CORRECT or CONFIRM can make either authoritative.
"""
from __future__ import annotations

import collections
import hashlib
from dataclasses import asdict, dataclass, field

from apps.pipeline.services import palette_design_intent as di

SCHEMA = "palette_intent_confirmation/1.0"

CONFIRM = "CONFIRM"
CORRECT = "CORRECT"
DELETE = "DELETE"
ADD = "ADD"
RECLASSIFY = "RECLASSIFY"
MARK_UNRESOLVED = "MARK_UNRESOLVED"
NOTE = "NOTE"
ACTIONS = (CONFIRM, CORRECT, DELETE, ADD, RECLASSIFY, MARK_UNRESOLVED, NOTE)

UNRESOLVED = "UNRESOLVED"

# §3 — fields the confirmation page must present for a palette concept.
REQUIRED_PANEL_ROWS = (
    "selected_source_image", "silhouette", "opening_direction",
    "pan_shapes", "pan_count", "rows", "columns", "relative_pan_sizes",
    "spacing_rhythm", "margins", "hinge_location", "clasp_location",
    "mirror_presence", "colour_zones", "artwork_zones", "logo_position",
    "typography_zones",
    # 3t/A437 — shade_names was decided in the ES3083 baseline and had no
    # panel row, so the owner confirmed sixteen fields while the record
    # attributed seventeen. The intent carried it in full the whole time
    # (SHADE_LABEL_STRIP_SHEET_PRESENT, 0.85, HARD_VISIBLE_CONSTRAINT);
    # only this tuple omitted it. Added so the field can be reviewed and
    # revised like any other. Version 1 is NOT edited — it is the honest
    # record of what was confirmed blind.
    "shade_names",
    # 3u/A446 — regulatory_zones is a HARD_VISIBLE_CONSTRAINT read at 0.9
    # from the back panel. No honest withholding reason exists for it:
    # it is visible, it is composition, and it is exactly what
    # VISIBLE_COMPOSITION_ONLY covers. Surfaced rather than withheld.
    # This is an executor judgement and is reversible by the owner.
    "regulatory_zones",
)

#: 3u — A SURFACE IS A DECLARED SELECTION. Every intent field is either
#: SURFACED (a panel row) or DECLARED_WITHHELD with a reason from this
#: CLOSED vocabulary. "Not needed" and "internal" are refused: they name
#: nothing, and an omission that states no reason is indistinguishable
#: from someone forgetting to type it.
WITHHELD_REASONS = {
    "OUTSIDE_OWNER_SCOPE": (
        "the field is not part of VISIBLE_COMPOSITION_ONLY — material, "
        "formulation, or dimensional impression, each of which has its "
        "own authority track and its own gate"),
    "NOT_READABLE_FROM_THIS_RENDER": (
        "the field exists in the schema but this render does not show "
        "it, so any reading would be invention"),
    "DERIVED_NOT_OBSERVED": (
        "the value is inferred character rather than measured from the "
        "image; confirming it would attribute an observation to a "
        "reading that made none"),
    "SUPERSEDED_BY_ANOTHER_FIELD": (
        "the property is already ruled through a surfaced field, so a "
        "second row would let the owner rule the same thing twice and "
        "disagree with themselves"),
}

#: The declared complement. Assignment is per field and stated.
NOT_SURFACED = {
    "apparent_material": ("OUTSIDE_OWNER_SCOPE",
                          "material identity, not visible composition"),
    "powder_finish_intent": ("OUTSIDE_OWNER_SCOPE",
                             "formulation, not visible composition"),
    "perceived_thickness": ("OUTSIDE_OWNER_SCOPE",
                            "dimensional impression; PALT_P1_FINAL_"
                            "DIMENSIONS is NOT_APPROVED and rules it"),
    "playful": ("DERIVED_NOT_OBSERVED", "character inferred from motif"),
    "youthful": ("DERIVED_NOT_OBSERVED", "character inferred from palette"),
    "alignment": ("SUPERSEDED_BY_ANOTHER_FIELD",
                  "the grid is ruled through rows, columns and "
                  "spacing_rhythm"),
    "corner_radius_impression": ("SUPERSEDED_BY_ANOTHER_FIELD",
                                 "ruled through silhouette"),
    "ornament": ("SUPERSEDED_BY_ANOTHER_FIELD",
                 "ruled through artwork_zones"),
    "pattern": ("SUPERSEDED_BY_ANOTHER_FIELD",
                "ruled through artwork_zones"),
}


class UndeclaredField(RuntimeError):
    """3u / class eighteen — present, unshown, and unexplained."""


def assert_surface_partition(intent, panel_rows):
    """INTENT == SURFACED u DECLARED_WITHHELD, or refuse.

    Class seventeen compares RECORD to PANEL and is blind to this by
    construction: a field in neither population is invisible to it.
    """
    populated = {f.name for f in intent.fields}
    surfaced = {r["field"] for r in panel_rows}
    undeclared = sorted(populated - surfaced - set(NOT_SURFACED))
    if undeclared:
        raise UndeclaredField(
            f"{undeclared} exist in the intent, appear on no surface, and "
            "carry no NOT_SURFACED reason — an omission that states no "
            "reason is indistinguishable from a lapse (3u)")
    bad = [f for f, (r, _) in NOT_SURFACED.items()
           if r not in WITHHELD_REASONS]
    if bad:
        raise UndeclaredField(f"{bad} carry a reason outside the closed "
                              f"vocabulary {sorted(WITHHELD_REASONS)}")
    return {"SURFACED": sorted(surfaced), "DECLARED_WITHHELD": sorted(NOT_SURFACED)}

PROVISIONAL = "PROVISIONAL_PENDING_CONFIRMATION"
PROVISIONAL_VISIBLE = "PROVISIONAL_VISIBLE_CONSTRAINT"


class ConfirmationError(ValueError):
    """Raised when a confirmation action is malformed."""


#: 3w — AN ACT CARRIES ITS ROUTE. Closed, and exhaustive against the
#: code: ConfirmationAction is constructed in exactly two places —
#: palette_es3083_owner_confirmation (the replayed baseline) and
#: dashboard/views (the panel). No third route exists, so none is
#: invented and there is no catch-all.
ROUTES = {
    "BASELINE_REPLAY": ("replayed from the recorded ES3083 owner "
                        "confirmation on every version"),
    "PANEL_ACTION": "entered by the owner on the confirmation panel",
}

#: The attribute each act is ABOUT. state is co-written by CONFIRM,
#: CORRECT, RECLASSIFY and MARK_UNRESOLVED, so keying on the full write
#: set would flag every ordinary pair; keying on the primary attribute
#: asks the question actually worth asking — did the same route decide
#: the same thing twice.
PRIMARY_ATTRIBUTE = {
    "CONFIRM": "state", "MARK_UNRESOLVED": "state",
    "CORRECT": "value", "ADD": "value",
    "RECLASSIFY": "level", "NOTE": "note", "DELETE": "existence",
}
#: Every attribute an act writes. Reported alongside, never merged: an
#: expected multiplicity that is hidden is the defect one layer up.
WRITES = {
    "CONFIRM": ("state",), "MARK_UNRESOLVED": ("state", "note"),
    "CORRECT": ("value", "state"), "RECLASSIFY": ("level", "state"),
    "ADD": ("value",), "NOTE": ("note",), "DELETE": ("existence",),
}


class MissingRoute(ValueError):
    """3w — an act with no route is refused at construction, never
    defaulted. A default route is a default reason (A446) wearing a
    different name."""


@dataclass
class ConfirmationAction:
    field_name: str
    action: str
    route: str = ""
    actor: str = "OWNER"
    new_value: object = None
    new_level: str = ""
    note: str = ""

    def __post_init__(self):
        # 3w — route first. A second __post_init__ silently overrides the
        # first in a dataclass, which is how the first version of this
        # guard was defined and never ran. Merged rather than added.
        if not self.route:
            raise MissingRoute(
                f"{self.field_name!r}/{self.action}: an act carries its "
                f"route; declare one of {sorted(ROUTES)}")
        if self.route not in ROUTES:
            raise MissingRoute(
                f"{self.route!r} is not a declared route; "
                f"expected one of {sorted(ROUTES)}")
        if self.action not in ACTIONS:
            raise ConfirmationError(f"unknown action {self.action!r}")
        if self.action == RECLASSIFY and self.new_level not in \
                di.CONSTRAINT_LEVELS:
            raise ConfirmationError(
                f"RECLASSIFY needs a constraint level, got "
                f"{self.new_level!r}")
        if self.action == ADD and self.field_name not in di.ALL_FIELDS:
            raise ConfirmationError(
                f"cannot ADD unknown field {self.field_name!r}")


@dataclass
class ConfirmationRecord:
    """Durable record of the owner's decisions on one drafted intent."""

    concept_reference: str
    draft_identity: str
    actions: list = field(default_factory=list)
    schema: str = SCHEMA

    def apply(self, action: ConfirmationAction):
        self.actions.append(action)
        return self

    def identity(self) -> str:
        payload = repr([(a.field_name, a.action, repr(a.new_value),
                         a.new_level, a.note) for a in self.actions])
        return hashlib.sha256(
            (payload + self.draft_identity).encode()).hexdigest()[:16]

    def to_dict(self):
        return {"schema": self.schema,
                "concept_reference": self.concept_reference,
                "draft_identity": self.draft_identity,
                "confirmation_identity": self.identity(),
                "actions": [asdict(a) for a in self.actions]}


#: 3t / class seventeen — DECISION_WITHOUT_A_REVIEW_SURFACE.
#: A record carried a decision attributed to an actor while no surface
#: available to that actor could have displayed it. First observed at
#: shade_names on task 9: a baseline CONFIRM with no panel row, so the
#: owner confirmed sixteen rows and the record attributed seventeen.
#:
#: This takes a RECORD and a PANEL, never a task id — a check bound to
#: one task is not a control (A440).
def reconcile_decision_surface(record_actions, panel_rows):
    """Both differences, named and in one direction each.

    UNSURFACED = decided but never shown -> the 3t violation.
    UNDECIDED  = shown but never decided -> not a violation; a field
                 the owner was offered and left alone.
    """
    decided = {a["field_name"] if isinstance(a, dict) else a.field_name
               for a in record_actions}
    shown = {r["field"] for r in panel_rows}
    # 3v / class nineteen — MULTIPLICITY_ERASED_BY_A_SET_COMPARISON.
    # The two differences above are SET operations: a field appearing
    # three times and once are identical to them. Two acts are legal
    # (A450); two acts nobody can see are not. DOUBLED reports, it does
    # not refuse.
    def _f(a, k):
        # Versions 1-4 on task 9 were written BEFORE 3w and carry no
        # route. A stored record predating a field is not a defect in
        # the record; it is history. Missing route reads as UNROUTED and
        # is excluded from the routed decomposition rather than crashing
        # it or being silently counted as some default.
        if isinstance(a, dict):
            if k in a:
                return a[k]
        elif hasattr(a, k):
            return getattr(a, k)
        if k == "route":
            return ""
        raise KeyError(k)

    # 3w/A467 — decomposed. SAME field, SAME route, SAME primary
    # attribute, more than once is the signal. Cross-route and
    # cross-attribute multiplicity is EXPECTED and is shown separately
    # rather than folded in.
    def _primary(action):
        # No default: an action the table does not name would key on
        # itself and quietly form its own bucket, so a new action type
        # could never collide with an existing one and would read clean
        # forever. Refuse instead.
        if action not in PRIMARY_ATTRIBUTE:
            raise ConfirmationError(
                f"{action!r} has no declared primary attribute; add it to "
                "PRIMARY_ATTRIBUTE rather than letting it key on itself")
        return PRIMARY_ATTRIBUTE[action]

    keyed = collections.Counter(
        (_f(a, "field_name"), _f(a, "route"), _primary(_f(a, "action")))
        for a in record_actions if _f(a, "route"))
    flagged = {f"{k[0]}|{k[1]}|{k[2]}": n for k, n in sorted(keyed.items())
               if n > 1}
    cross = collections.defaultdict(list)
    for a in record_actions:
        cross[_f(a, "field_name")].append(
            (_f(a, "route"), _f(a, "action"),
             _primary(_f(a, "action"))))
    expected = {f: v for f, v in sorted(cross.items()) if len(v) > 1}
    counts = collections.Counter(
        a["field_name"] if isinstance(a, dict) else a.field_name
        for a in record_actions)
    doubled = {}
    for name, n in sorted(counts.items()):
        if n > 1:
            doubled[name] = [
                (a["action"] if isinstance(a, dict) else a.action)
                for a in record_actions
                if (a["field_name"] if isinstance(a, dict)
                    else a.field_name) == name]
    return {"UNSURFACED": sorted(decided - shown),
            "UNDECIDED": sorted(shown - decided),
            "DOUBLED": doubled,
            "FLAGGED_SAME_ROUTE_SAME_ATTRIBUTE": flagged,
            "EXPECTED_MULTIPLICITY": expected}


def panel(intent) -> dict:
    """§3 — 'WHAT THE ENGINE UNDERSTOOD FROM ES3083', as data.

    Presented per field with confidence and provenance so the owner sees
    the reading AND how sure the engine is, never a bare assertion.
    """
    rows = []
    for name in REQUIRED_PANEL_ROWS:
        if name == "selected_source_image":
            rows.append({"field": "selected_source_image",
                         "understood": intent.concept_reference,
                         "confidence": None, "level": None,
                         "state": "SOURCE", "actionable": False})
            continue
        f = intent.get(name)
        if f is None:
            rows.append({"field": name, "understood": None,
                         "confidence": 0.0, "level": None,
                         "state": UNRESOLVED, "actionable": True,
                         "why": "not detected in the source"})
            continue
        provisional = (f.constraint_level == di.HARD and PROVISIONAL_VISIBLE
                       or PROVISIONAL)
        rows.append({
            "field": name, "understood": f.value,
            "confidence": round(float(f.confidence), 3),
            "level": f.constraint_level,
            "state": provisional if f.confirmation_state == di.PENDING
            else f.confirmation_state,
            "source_region": f.source_region,
            "extraction_method": f.extraction_method,
            "note": f.note, "actionable": True})
    return {
        "record_type": "palette_intent_panel/1.0",
        "title": "WHAT THE ENGINE UNDERSTOOD FROM THE SELECTED DESIGN",
        "concept_reference": intent.concept_reference,
        "draft_identity": intent.identity(),
        "rows": rows,
        "unresolved": list(intent.unresolved_regions),
        "occluded": intent.view.get("hidden_faces", []),
        "available_actions": list(ACTIONS),
        "available_levels": list(di.CONSTRAINT_LEVELS),
        "owner_approved": False,
        "state": intent.state,
        "warning": "values shown as approximate remain approximate; only "
                   "an explicit owner CONFIRM or CORRECT makes one exact",
    }


#: 3v / class ten EXHIBITED — WHICH ACT GOVERNS, stated rather than
#: inferred from order. Determined EMPIRICALLY from the function below,
#: not read off it: the resolution is NOT "panel supersedes baseline".
#:
#:   1. DELETE DOMINATES REGARDLESS OF POSITION. `any(... DELETE ...)`
#:      short-circuits, so DELETE->CONFIRM and CONFIRM->DELETE both
#:      yield OWNER_REMOVED.
#:   2. OTHERWISE ACTS COMPOSE PER ATTRIBUTE. CORRECT writes value and
#:      state; RECLASSIFY writes level and state; CONFIRM writes state;
#:      MARK_UNRESOLVED writes state and note. CORRECT then RECLASSIFY
#:      leaves BOTH value and level standing — they do not supersede.
#:   3. WHERE TWO ACTS WRITE THE SAME ATTRIBUTE, THE LAST IN RECORD
#:      ORDER WINS. CORRECT 7 then CORRECT 8 gives 8; reversed gives 7.
#:      CORRECT then CONFIRM gives HUMAN_CONFIRMED_DESIGN_INTENT;
#:      CONFIRM then CORRECT gives OWNER_CORRECTED. Same two acts,
#:      different outcome, decided by nothing but loop order.
#:
#: The behaviour is NOT changed here (A459). It is named, and
#: ResolutionOrderStandingControl fails if the order changes.
RESOLUTION_RULE = "LAST_WRITE_PER_ATTRIBUTE_WINS_EXCEPT_DELETE_WHICH_DOMINATES"


def apply_confirmations(intent, record) -> di.PaletteDesignIntent:
    """Produce a NEW intent carrying the owner's decisions.

    Resolution follows RESOLUTION_RULE above.

    The draft is not mutated: the AI reading and the owner's decision stay
    separately auditable.
    """
    out = di.PaletteDesignIntent(concept_reference=intent.concept_reference)
    out.decomposition = dict(intent.decomposition)
    out.view = dict(intent.view)
    out.unresolved_regions = list(intent.unresolved_regions)

    by_field = {}
    for a in record.actions:
        by_field.setdefault(a.field_name, []).append(a)

    for f in intent.fields:
        acts = by_field.get(f.name, [])
        if any(a.action == DELETE for a in acts):
            out.add(**{**asdict(f), "confirmation_state": di.REMOVED})
            continue
        value, level, state, note = (f.value, f.constraint_level,
                                     f.confirmation_state, f.note)
        for a in acts:
            if a.action == CONFIRM:
                state = di.CONFIRMED
            elif a.action == CORRECT:
                value, state = a.new_value, di.CORRECTED
            elif a.action == RECLASSIFY:
                level, state = a.new_level, di.CORRECTED
            elif a.action == MARK_UNRESOLVED:
                state = di.PENDING
                note = (note + " | owner marked UNRESOLVED").strip(" |")
            if a.note:
                note = (note + f" | owner: {a.note}").strip(" |")
        out.add(**{**asdict(f), "value": value, "constraint_level": level,
                   "confirmation_state": state, "note": note})

    known = {f.name for f in intent.fields}
    for name, acts in by_field.items():
        for a in acts:
            if a.action == ADD and name not in known:
                out.add(name=name, value=a.new_value,
                        source_reference=intent.concept_reference,
                        source_region="owner supplied",
                        confidence=1.0, extraction_method="OWNER_STATED",
                        confirmation_state=di.CONFIRMED,
                        constraint_level=a.new_level or di.HARD,
                        geometry_relevance=False, material_relevance=False,
                        artwork_relevance=False, note=a.note)
    return out


def confirmation_status(intent) -> dict:
    live = [f for f in intent.fields
            if f.confirmation_state != di.REMOVED]
    confirmed = [f for f in live if f.is_design_authority]
    return {
        "record_type": "palette_confirmation_status/1.0",
        "total_fields": len(live),
        "confirmed": len(confirmed),
        "pending": [f.name for f in live
                    if f.confirmation_state == di.PENDING],
        "fully_confirmed": len(confirmed) == len(live) and bool(live),
        "state": intent.state,
        "design_authority": (di.CONFIRMED if len(confirmed) == len(live)
                             and live else di.DRAFT),
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
