"""Printed-data snapshot contract + regeneration integrity (Phase 2A-6B).

The task-#47 incident in one sentence: a regeneration rebuilt the panel
record from defaults and overwrote verified regulatory copy, and nothing
compared before with after. This module makes that comparison structural.

    packaging_print_data_snapshot/1.0

A snapshot is a deterministic, canonical description of the printed
information a generation consumed: normalized values, per-field verification
state, translation identities, the legal-role mapping, and one content hash
over all of it. A regeneration binds to the hash it consumed; afterwards the
output is re-snapshotted and the two are compared field by field.

Deliberately NOT in a snapshot: credentials, API keys, worker state, agent
rationale, the internal task brief, or a raw model serialization. It carries
product-facing print data and nothing else.

Comparison is fail-closed and never partially successful: any dropped,
changed, defaulted or placeholder-ised field, any lost translation, and any
legal-role reassignment is a failure with its own stable code.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from apps.pipeline.services.print_data import (
    MISSING,
    NOT_APPLICABLE,
    PLACEHOLDER,
    PRINT_FIELDS,
    UNVERIFIED,
    VERIFIED,
    PrintDataRecord,
    build_print_record,
)

SCHEMA_VERSION = "packaging_print_data_snapshot/1.0"

# --- failure codes -------------------------------------------------------------

VERIFIED_PRINT_DATA_WOULD_BE_LOST = "VERIFIED_PRINT_DATA_WOULD_BE_LOST"
PRINT_DATA_FIELD_CHANGED = "PRINT_DATA_FIELD_CHANGED"
PRINT_DATA_FIELD_DROPPED = "PRINT_DATA_FIELD_DROPPED"
PRINT_DATA_DEFAULT_SUBSTITUTED = "PRINT_DATA_DEFAULT_SUBSTITUTED"
TRANSLATION_DATA_LOST = "TRANSLATION_DATA_LOST"
LEGAL_ROLE_MAPPING_CHANGED = "LEGAL_ROLE_MAPPING_CHANGED"
PRINT_DATA_SNAPSHOT_MISMATCH = "PRINT_DATA_SNAPSHOT_MISMATCH"

#: States that mean "a human stands behind this value".
_TRUSTED = (VERIFIED, UNVERIFIED)

_WHITESPACE_RE = re.compile(r"[ \t ]+")
_NEWLINES_RE = re.compile(r"\r\n?| | ")


def normalize(value) -> str:
    """Canonical form of a printed string.

    Unicode NFC, CRLF/LS collapsed to \\n, runs of spaces and tabs collapsed,
    trailing space stripped per line, surrounding whitespace removed. This is
    the ONLY transformation a regeneration may apply without it counting as a
    change — and when it applies, the comparison says so explicitly.
    """
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = unicodedata.normalize("NFC", text)
    text = _NEWLINES_RE.sub("\n", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def translation_identities(translations) -> dict:
    """language -> field -> {sha256, chars}.

    Identities, not copies: enough to prove a translation survived unchanged
    without duplicating the corpus into every snapshot.
    """
    out: dict[str, dict] = {}
    if not isinstance(translations, dict):
        return out
    for lang in sorted(translations):
        block = translations[lang]
        if not isinstance(block, dict):
            continue
        fields = {}
        for key in sorted(block):
            text = normalize(block[key])
            if text:
                fields[key] = {"sha256": _digest(text), "chars": len(text)}
        if fields:
            out[str(lang)] = fields
    return out


def legal_role_mapping(record: PrintDataRecord) -> dict:
    """legal role -> the fields satisfying it, and with what state."""
    mapping: dict[str, dict] = {}
    for fld in PRINT_FIELDS:
        if not fld.legal_role:
            continue
        state = record.fields[fld.key].state if fld.key in record.fields else MISSING
        mapping.setdefault(fld.legal_role, {})[fld.key] = state
    return mapping


@dataclass
class PrintDataSnapshot:
    schema_version: str
    task_id: int
    source: str                       # where the record was read from
    created_at: str
    values: dict = field(default_factory=dict)         # normalized
    states: dict = field(default_factory=dict)
    translations: dict = field(default_factory=dict)   # identities
    legal_roles: dict = field(default_factory=dict)
    content_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def canonical(self) -> str:
        """The exact bytes the content hash is taken over. Excludes the
        timestamp and the hash itself, so two snapshots of the same data
        match regardless of when they were taken."""
        return json.dumps(
            {"schema_version": self.schema_version,
             "task_id": self.task_id,
             "values": self.values,
             "states": self.states,
             "translations": self.translations,
             "legal_roles": self.legal_roles},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_snapshot(task_id: int, record: PrintDataRecord, *,
                   translations=None, source: str = "") -> PrintDataSnapshot:
    """Deterministic snapshot of a printed-information record."""
    from django.utils import timezone

    values, states = {}, {}
    for fld in PRINT_FIELDS:
        state = record.fields.get(fld.key)
        if state is None:
            continue
        states[fld.key] = state.state
        text = normalize(state.value)
        if text:
            values[fld.key] = text
    snapshot = PrintDataSnapshot(
        schema_version=SCHEMA_VERSION,
        task_id=int(task_id),
        source=source or "stored_print_data_record",
        created_at=timezone.now().isoformat(),
        values=values,
        states=states,
        translations=translation_identities(translations),
        legal_roles=legal_role_mapping(record),
    )
    snapshot.content_hash = _digest(snapshot.canonical())
    return snapshot


def snapshot_from_panel_info(task_id: int, panel_info: dict, *,
                             verified_keys=None,
                             source: str = "") -> PrintDataSnapshot:
    """Convenience: snapshot straight from a panel_info mapping."""
    panel_info = panel_info or {}
    record = build_print_record(
        panel_info,
        verified_keys=(verified_keys if verified_keys is not None
                       else [k for k, v in panel_info.items()
                             if isinstance(v, str) and v.strip()]))
    return build_snapshot(task_id, record,
                          translations=panel_info.get("translations"),
                          source=source)


# --- comparison ------------------------------------------------------------------


@dataclass
class SnapshotComparison:
    before_hash: str
    after_hash: str
    identical: bool
    normalized_only: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    changed_fields: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def codes(self) -> set:
        return {f["code"] for f in self.failures}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["passed"] = self.passed
        return d


def compare_snapshots(before: PrintDataSnapshot, after: PrintDataSnapshot,
                      *, defaults: dict | None = None) -> SnapshotComparison:
    """Compare a consumed snapshot with the regenerated one.

    ``defaults`` (optional): the Product/Brand default values. When a field
    changed INTO its default it is reported as a substitution rather than a
    generic change, because that is the failure mode that caused the incident.
    """
    defaults = {k: normalize(v) for k, v in (defaults or {}).items()}
    comparison = SnapshotComparison(
        before_hash=before.content_hash, after_hash=after.content_hash,
        identical=before.content_hash == after.content_hash,
    )

    def fail(code, fld, detail, **extra):
        entry = {"code": code, "field": fld, "detail": detail}
        entry.update(extra)
        comparison.failures.append(entry)

    # --- field-by-field ---------------------------------------------------
    for key in sorted(set(before.values) | set(after.values)):
        old = before.values.get(key, "")
        new = after.values.get(key, "")
        old_state = before.states.get(key, MISSING)
        was_trusted = old_state in _TRUSTED

        if old and not new:
            comparison.changed_fields.append(key)
            fail(PRINT_DATA_FIELD_DROPPED, key,
                 f"{key!r} was present ({old_state}) and is now absent")
            if was_trusted:
                fail(VERIFIED_PRINT_DATA_WOULD_BE_LOST, key,
                     f"verified value for {key!r} would be lost")
            continue
        if not old:
            continue                       # newly supplied data is not a loss
        if old == new:
            continue

        comparison.changed_fields.append(key)
        if defaults.get(key) and new == defaults[key]:
            fail(PRINT_DATA_DEFAULT_SUBSTITUTED, key,
                 f"{key!r} was replaced by the Product/Brand default")
        else:
            fail(PRINT_DATA_FIELD_CHANGED, key,
                 f"{key!r} changed after regeneration")
        if was_trusted:
            fail(VERIFIED_PRINT_DATA_WOULD_BE_LOST, key,
                 f"verified value for {key!r} did not survive")

    # --- states: a trusted field must not decay --------------------------
    for key, old_state in before.states.items():
        new_state = after.states.get(key, MISSING)
        if old_state in _TRUSTED and new_state == PLACEHOLDER:
            fail(VERIFIED_PRINT_DATA_WOULD_BE_LOST, key,
                 f"{key!r} was {old_state} and is now placeholder text")
        elif old_state in _TRUSTED and new_state in (MISSING, NOT_APPLICABLE) \
                and key not in comparison.changed_fields:
            fail(VERIFIED_PRINT_DATA_WOULD_BE_LOST, key,
                 f"{key!r} lost its {old_state} state")

    # --- translations ------------------------------------------------------
    for lang, fields in before.translations.items():
        after_lang = after.translations.get(lang)
        if not after_lang:
            fail(TRANSLATION_DATA_LOST, f"translations.{lang}",
                 f"the {lang} translation block was lost")
            continue
        for key, identity in fields.items():
            other = after_lang.get(key)
            if other is None:
                fail(TRANSLATION_DATA_LOST, f"translations.{lang}.{key}",
                     f"{lang} translation of {key!r} was lost")
            elif other["sha256"] != identity["sha256"]:
                fail(TRANSLATION_DATA_LOST, f"translations.{lang}.{key}",
                     f"{lang} translation of {key!r} changed")

    # --- legal roles -------------------------------------------------------
    for role, fields in before.legal_roles.items():
        after_fields = after.legal_roles.get(role, {})
        satisfied_before = {k for k, s in fields.items() if s == VERIFIED}
        satisfied_after = {k for k, s in after_fields.items() if s == VERIFIED}
        if satisfied_before and not satisfied_before <= satisfied_after:
            fail(LEGAL_ROLE_MAPPING_CHANGED, role,
                 f"legal role {role!r} was satisfied by "
                 f"{sorted(satisfied_before)} and now by "
                 f"{sorted(satisfied_after)}")

    # --- formatting-only normalization, reported explicitly ---------------
    for key in sorted(set(before.values) & set(after.values)):
        raw_old, raw_new = before.values[key], after.values[key]
        if raw_old != raw_new and normalize(raw_old) == normalize(raw_new):
            comparison.normalized_only.append(key)

    return comparison


def assert_snapshot_binding(consumed_hash: str,
                            snapshot: PrintDataSnapshot) -> list[dict]:
    """A regeneration must bind to the snapshot it actually consumed."""
    if consumed_hash and consumed_hash != snapshot.content_hash:
        return [{
            "code": PRINT_DATA_SNAPSHOT_MISMATCH,
            "field": "",
            "detail": (f"regeneration bound to snapshot {consumed_hash[:12]}… "
                       f"but the record now hashes to "
                       f"{snapshot.content_hash[:12]}… — the printed data "
                       "changed underneath the run"),
        }]
    return []


__all__ = [
    "SCHEMA_VERSION",
    "PrintDataSnapshot",
    "SnapshotComparison",
    "build_snapshot",
    "snapshot_from_panel_info",
    "compare_snapshots",
    "assert_snapshot_binding",
    "normalize",
    "translation_identities",
    "legal_role_mapping",
    "VERIFIED_PRINT_DATA_WOULD_BE_LOST",
    "PRINT_DATA_FIELD_CHANGED",
    "PRINT_DATA_FIELD_DROPPED",
    "PRINT_DATA_DEFAULT_SUBSTITUTED",
    "TRANSLATION_DATA_LOST",
    "LEGAL_ROLE_MAPPING_CHANGED",
    "PRINT_DATA_SNAPSHOT_MISMATCH",
]
