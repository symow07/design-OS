"""Print-data entry/review screen + incident recovery report (2A-6B §1, §5).

Two bounded, read-mostly services:

``entry_screen(task)``
    Everything the reviewer needs to enter or confirm the printed
    information for one task: every field in the contract, its current value,
    its verification state, its legal role, and whether it is required for
    production. Missing legal or formula data is NEVER prefilled with
    generated text, and values that exist only inside a rendered artifact are
    NEVER presented as verified structured data.

``recovery_report(task)``
    The bounded operational history of a print-data incident: what was lost,
    what it was restored from, the snapshot hashes before and after a replay,
    the differences found, and the result. It is history, not authority — no
    DecisionEvent is created (the project contract does not require one for
    production-data entry).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from apps.pipeline.services.print_data import (
    MISSING,
    NOT_APPLICABLE,
    PRINT_FIELDS,
    build_print_record,
)
from apps.pipeline.services.print_data_snapshot import (
    build_snapshot,
    compare_snapshots,
    snapshot_from_panel_info,
)

#: Languages the sticker renderer supports today.
SUPPORTED_TRANSLATION_LANGUAGES = ("es", "ar")


@dataclass
class FieldEntry:
    key: str
    label: str
    value: str
    state: str
    required: bool
    legal_role: str
    detail: str = ""
    #: True when the value came from a Product/Brand default rather than
    #: from a human — shown so a reviewer never mistakes it for confirmed.
    from_default: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EntryScreen:
    task_id: int
    fields: list = field(default_factory=list)
    translations: dict = field(default_factory=dict)
    incident: dict = field(default_factory=dict)
    snapshot_hash: str = ""
    production_failures: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fields"] = [f.to_dict() if isinstance(f, FieldEntry) else f
                       for f in self.fields]
        d["complete"] = self.complete
        d["outstanding"] = self.outstanding
        return d

    @property
    def outstanding(self) -> list:
        """Required fields a human still has to supply."""
        return [f.key for f in self.fields
                if f.required and f.state in (MISSING, NOT_APPLICABLE,
                                              "PLACEHOLDER")]

    @property
    def complete(self) -> bool:
        return not self.outstanding


def entry_screen(task, *, output=None) -> EntryScreen:
    """Bounded entry/review data for the task's printed information."""
    output = output or (task.packaging_outputs
                        .order_by("-created_at").first())
    spec = (getattr(output, "spec_sheet", None) or {}) if output else {}
    stored = dict(spec.get("panel_info") or {})

    # Product/Brand defaults are shown as SUGGESTIONS only, and only for
    # fields the stored record does not already answer. Nothing legal or
    # formula-shaped is ever generated.
    from apps.pipeline.services.panel_info import merge_panel_info
    defaults = merge_panel_info(task, None)

    record = build_print_record(stored, verified_keys=[
        k for k, v in stored.items() if isinstance(v, str) and v.strip()])

    entries = []
    for fld in PRINT_FIELDS:
        state = record.fields[fld.key]
        value = state.value
        from_default = False
        if not value:
            suggestion = str(defaults.get(fld.key) or "").strip()
            # Never suggest a value for a legal/formula field: those must be
            # supplied by the customer, not inherited from another record.
            if suggestion and not fld.legal_role:
                value, from_default = suggestion, True
        entries.append(FieldEntry(
            key=fld.key, label=fld.label, value=value, state=state.state,
            required=fld.required, legal_role=fld.legal_role,
            detail=state.detail, from_default=from_default))

    translations = {
        lang: sorted((stored.get("translations") or {}).get(lang, {}))
        for lang in SUPPORTED_TRANSLATION_LANGUAGES
        if isinstance((stored.get("translations") or {}).get(lang), dict)
    }
    snapshot = snapshot_from_panel_info(task.pk, stored,
                                        source="entry_screen")
    return EntryScreen(
        task_id=task.pk,
        fields=entries,
        translations=translations,
        incident=dict(spec.get("panel_info_incident") or {}),
        snapshot_hash=snapshot.content_hash,
        production_failures=record.production_failures(),
    )


def save_print_data(task, values: dict, *, verified_keys=None,
                    translations=None, output=None) -> dict:
    """Persist an entered printed-information record and snapshot it.

    Only declared contract fields are stored — the whitelist is the same one
    production artwork reads, so nothing else can enter by this door.
    Returns the normalized record plus its snapshot hash for confirmation.
    """
    output = output or (task.packaging_outputs
                        .order_by("-created_at").first())
    if output is None:
        raise ValueError("no packaging output to attach printed data to")

    allowed = {f.key for f in PRINT_FIELDS}
    cleaned = {k: v.strip() for k, v in (values or {}).items()
               if k in allowed and isinstance(v, str) and v.strip()}
    record = build_print_record(
        cleaned, verified_keys=verified_keys or cleaned.keys())
    stored = dict(cleaned)
    if translations:
        stored["translations"] = translations

    spec = dict(output.spec_sheet or {})
    spec["panel_info"] = stored
    snapshot = build_snapshot(task.pk, record, translations=translations,
                              source="human_entry")
    spec["print_data_snapshot"] = {
        "schema_version": snapshot.schema_version,
        "entered_hash": snapshot.content_hash,
    }
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    return {"record": record.to_dict(), "snapshot": snapshot.to_dict(),
            "snapshot_hash": snapshot.content_hash}


def recovery_report(task, *, output=None, before=None, after=None) -> dict:
    """Bounded incident + recovery history for one task.

    ``before``/``after``: optional snapshots from a replay, so the report can
    state exactly what a regeneration changed.
    """
    output = output or (task.packaging_outputs
                        .order_by("-created_at").first())
    spec = (getattr(output, "spec_sheet", None) or {}) if output else {}
    incident = dict(spec.get("panel_info_incident") or {})
    stored = dict(spec.get("panel_info") or {})

    report = {
        "incident_id": incident.get("incident_id",
                                    f"PRINT-DATA-{task.pk}-2026-07-20"),
        "task_id": task.pk,
        "fields_lost": list(incident.get("fields_lost") or ()),
        "restoration_source": incident.get("restoration_source",
                                           "AWAITING_USER_ENTRY"),
        "restored_snapshot_hash": "",
        "replay_snapshot_hash": "",
        "differences": [],
        "result": "AWAITING_USER_ENTRY",
        "incident": incident,
    }
    if stored:
        report["restored_snapshot_hash"] = snapshot_from_panel_info(
            task.pk, stored, source="restored_record").content_hash
    if before is not None and after is not None:
        comparison = compare_snapshots(before, after)
        report["restored_snapshot_hash"] = before.content_hash
        report["replay_snapshot_hash"] = after.content_hash
        report["differences"] = comparison.failures
        report["result"] = ("REPLAY_IDENTICAL" if comparison.passed
                            else "REPLAY_DIFFERENCES_FOUND")
    elif stored:
        report["result"] = "RECORD_PRESENT_REPLAY_PENDING"
    return report


__all__ = [
    "EntryScreen",
    "FieldEntry",
    "entry_screen",
    "save_print_data",
    "recovery_report",
    "SUPPORTED_TRANSLATION_LANGUAGES",
]
