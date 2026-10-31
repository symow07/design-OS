"""Safe, deterministic display labels for evidence references — DIP-1C-5C-CORR-1.

The review forms labelled every checkbox with `evidence_kind + SourceArtifact.sha256`. That
hash is the hash of the *whole source file*, so all 11 page units extracted from one
Illustrator file rendered identical labels. Their `EvidenceReference` hashes and locators
were always distinct — only the presentation collapsed them — but a reviewer who cannot tell
two checkboxes apart cannot honestly claim to have inspected one of them.

**Presentation only.** Nothing here changes evidence identity, stored hashes, locators,
source artifacts, signed schemas or validation. The submitted checkbox value stays the
canonical `EvidenceReference` id; a label is never evidence identity.

**What may be shown.** Only bounded, non-path locator fields — `page`, `unit_key`,
`artboard`, `face_index`, `face_id`, `line`. Paths are never rendered: `source_file/1.0`,
`json_path/1.0`, `jsonl_record/1.0` and `archive_member/1.0` locators all carry real
repository or `materials/` paths, and the evidence boundary that keeps those out of semantic
documents applies just as much to a reviewer's screen.

**Fail closed.** A locator with no safe distinguishing value falls back to the evidence kind
plus a bounded reference id and evidence-hash prefix — never to the shared source-artifact
hash, which is exactly the collision this correction removes, and never to an invented page
or filename.
"""
from __future__ import annotations

HASH_PREFIX = 12
MAX_LABEL = 160
#: Locator fields that are bounded identifiers rather than paths. Anything not listed is
#: treated as unsafe to display, whether or not it looks like a path today.
SAFE_TEXT_FIELDS = ("unit_key", "face_id", "record_key")


def _safe_text(value):
    """Bounded locator text is displayable only if it cannot be read as a path."""
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if not text or len(text) > 80:
        return ""
    if "/" in text or "\\" in text or text.startswith("."):
        return ""
    return text


def _index(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _fallback(reference):
    """No safe distinguishing locator value: identify the reference itself. Distinct by
    construction, and it discloses nothing about where the evidence lives."""
    return (f"evidence reference {str(reference.pk)[:8]} · "
            f"hash {reference.evidence_hash[:HASH_PREFIX]}…")


def _detail(reference):
    schema = reference.locator_schema_version or ""
    locator = reference.locator if isinstance(reference.locator, dict) else {}

    if schema == "file_page/1.0":
        parts = []
        page = _index(locator.get("page"))
        if page is not None:
            parts.append(f"page {page}")
        unit = _safe_text(locator.get("unit_key"))
        if unit:
            parts.append(unit)
        return " · ".join(parts) if parts else _fallback(reference)

    if schema == "illustrator_artboard/1.0":
        parts = []
        artboard = _index(locator.get("artboard"))
        if artboard is not None:
            parts.append(f"artboard {artboard}")
        unit = _safe_text(locator.get("unit_key"))
        if unit:
            parts.append(unit)
        return " · ".join(parts) if parts else _fallback(reference)

    if schema == "font_face/1.0":
        parts = []
        face = _index(locator.get("face_index"))
        if face is not None:
            parts.append(f"face {face}")
        face_id = _safe_text(locator.get("face_id"))
        if face_id:
            parts.append(face_id)
        return " · ".join(parts) if parts else _fallback(reference)

    if schema == "source_file/1.0":
        # the locator holds a real path (`materials/…`), so it is never rendered; the
        # source hash IS the right identifier here because this reference *is* the file
        return f"complete source · SHA-256 {reference.source_artifact.sha256[:HASH_PREFIX]}…"

    if schema == "jsonl_record/1.0":
        line = _index(locator.get("line"))
        record = _safe_text(locator.get("record_key"))
        parts = ([f"line {line}"] if line is not None else []) + ([record] if record else [])
        return " · ".join(parts) if parts else _fallback(reference)

    # json_path/1.0 and archive_member/1.0 carry only paths; "1" is the legacy free-form
    # locator. All fail closed to the reference's own identity.
    return _fallback(reference)


def evidence_label(reference) -> str:
    """`FILE_PAGE_UNIT · page 0 · BL-2050 STAND-p0-u01`. Deterministic and bounded."""
    return f"{reference.evidence_kind} · {_detail(reference)}"[:MAX_LABEL]


def labelled_evidence(references):
    """`[(reference, label)]` in the given order — the one list every review form renders,
    so no screen can drift back to an ambiguous label."""
    return [(reference, evidence_label(reference)) for reference in references]
