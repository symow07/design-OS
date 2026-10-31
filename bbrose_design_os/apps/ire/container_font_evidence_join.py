"""§BH12(a) Option B — the ``confirmed_fonts`` producer.

A JOIN over the dip0c face evidence by ``file_sha256``, per §BH12(a): *"The
confirmed_fonts producer is a join over dip0c evidence by file_sha256, ceiling
LICENCE_REVIEW_REQUIRED — machine-writable states only... It must be
structurally incapable of emitting VERIFIED_FOR_PRODUCTION or any HUMAN_ONLY
state: cap enforced in code, not convention."*

The cap lives in ``container_font_authority``'s public guards and this module
calls them on every value it emits, so the ceiling is enforced ACROSS A MODULE
BOUNDARY rather than by a private agreement with itself. §BH13(a) then fixed the
vocabulary: the cap is *"enforced in code against the app-side enum"*, not
against dip0c's ``MACHINE_ALLOWED`` — that phrase was the owner's own mis-cite
and is superseded. What survives from dip0c is the PRINCIPLE.

THIS PRODUCER YIELDS BOTH CONTAINER FACES. The paragraph that stood here
("yields nothing today": 3,966 rows, all under ``materials/``, NO MATCH) was true
when written and was superseded by measurement at §BH20(b)/(c), which
regenerated the c4c evidence over the app's own ``static/fonts`` root; §BH26(b)
then wired the producer live (``join_document_fonts`` below, at the production
call site). Measured 2026-09-03 at HEAD: 3,969 rows; the container's two faces
(``478c558e…`` → ``face-327979ef355ce8ccd570``, ``1df075a3…`` →
``face-ac29d83abf6138679264``) JOIN, each yielding a MACHINE_DERIVED /
LICENCE_REVIEW_REQUIRED confirmation — the ceiling, never more. §BH15(b) still
governs a face that does not join — *"No per-face claim is made while the joined
set is empty — not UNVERIFIED-dressed-as-progress, nothing"* — so such a face is
ABSENT from the returned mapping rather than present with a hedged state; and the
evidence file is untracked and git-ignored, so in a clean clone the join reads
EVIDENCE_ABSENT, yields nothing, and the default column stands beneath the grant.

WHY IT CARRIES NO LICENCE FIELD. §BH12(a): *"No licence is granted because none
exists to grant — zero of the 6921 proposed decisions are taken, and reading the
OFL is my act, not code's."* That is borne out by the evidence rather than
merely honoured: all 3,966 rows carry exactly ONE distinct ``permissions``
combination and every flag in it is false, and every one of the 13 ``human``
decision fields is null in every row. The row has no licence-IDENTIFYING field
at all — only ``license_evidence``, a list of PATHS — so there is nothing here a
machine could put in ``licence_id`` even if it were permitted to.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.ire.container_font_authority import (
    LICENCE_REVIEW_REQUIRED,
    SOURCE_MACHINE_DERIVED,
    extract_identity,
    machine_writable_source,
    machine_writable_verification,
)

SCHEMA = "container_font_evidence_join/1.0"

#: The dip0c artifact. Untracked AND git-ignored (measured: ``ls-files
#: --error-unmatch`` rc=1, ``check-ignore`` rc=0), so it is ABSENT in a clean
#: clone. Absence is a first-class outcome below, never a silent empty result.
DEFAULT_EVIDENCE_PATH = (Path(__file__).resolve().parents[3]
                         / "var/design_intelligence/audits/dip0c/c4c"
                         / "face_manifest.json")

#: The two states this producer declares. Both sit AT OR BELOW the app ceiling,
#: and both are pushed through the guards at emission time so that changing
#: either constant to a forbidden state RAISES instead of widening the licence.
JOIN_VERIFICATION = LICENCE_REVIEW_REQUIRED
JOIN_SOURCE = SOURCE_MACHINE_DERIVED

# Evidence-side outcomes. EVIDENCE_ABSENT exists so that "I could not look"
# never reads as "I looked and found nothing" — returning {} for both is the
# measurement-shaped-value-where-an-error-belongs defect this house keeps
# hitting, and the join is absent-by-default on any clean clone.
EVIDENCE_READ = "EVIDENCE_READ"
EVIDENCE_ABSENT = "EVIDENCE_ABSENT"
EVIDENCE_UNREADABLE = "EVIDENCE_UNREADABLE"

# Face-side outcomes.
FACE_JOINED = "JOINED"
FACE_NO_MATCH = "NO_MATCH"
FACE_NO_FILE_IDENTITY = "NO_FILE_IDENTITY"


def _load_rows(evidence_path) -> tuple[str, list]:
    path = Path(evidence_path) if evidence_path else DEFAULT_EVIDENCE_PATH
    if not path.exists():
        return EVIDENCE_ABSENT, []
    try:
        rows = json.loads(path.read_text())
    except (OSError, ValueError):
        return EVIDENCE_UNREADABLE, []
    if not isinstance(rows, list):
        return EVIDENCE_UNREADABLE, []
    return EVIDENCE_READ, rows


def _confirmation(row, *, verification=JOIN_VERIFICATION,
                  source=JOIN_SOURCE) -> dict:
    """One confirmation for a JOINED face, capped at the point of emission.

    ``verification``/``source`` are parameters so the cap can be proven by
    ENUMERATION against the app enum, as §BH13(a) requires — *"The cap test must
    prove the producer cannot emit any state above the ceiling, by enumeration
    against the app enum, not by convention."* Driving the producer with a
    forbidden state must RAISE; a test that only called the guards directly
    would prove the guards work, not that the producer uses them.

    ``provenance`` is stamped EXPLICITLY. Since §BH16(a) a confirmation with no
    ``provenance`` key reads as UNDECLARED, and UNDECLARED clears
    ``is_fallback`` — which is §BH16(g)(1)'s open residual, where silence still
    deletes CONTAINER_FONT_FALLBACK_DETECTED. Declaring MACHINE_DERIVED keeps
    this producer out of that hole rather than relying on it.

    No ``licence_id``, ``approved_by`` or ``approved_at``: see the module
    docstring. The seam's own conservative defaults stand for everything absent
    here, so silence at this seam withholds rather than grants.

    The two constants are the literal defaults rather than ``None`` sentinels,
    so an explicit ``None`` reaches the guard and is REFUSED. A sentinel would
    have quietly substituted the permitted default for a value the caller asked
    to emit — a silent widening at the exact seam that exists to prevent one,
    and it was a real defect here until the enumeration test caught it.
    """
    machine = row.get("machine") or {}
    return {
        "provenance": machine_writable_source(source),
        "verification": machine_writable_verification(verification),
        # The join key IS the file's sha256, so this is the joined row's claim
        # about the very file the resolver already picked. Passing it lets the
        # seam's identity check fire if the evidence disagrees with the file.
        "postscript_name": machine.get("postscript_name") or "",
        "evidence_face_id": machine.get("face_id") or "",
    }


def join_font_evidence(faces, *, evidence_path=None) -> dict:
    """Join resolved container faces against the dip0c evidence by sha256.

    ``faces`` is an iterable of ``(role, path)``. Returns the whole join RESULT,
    not just its yield: ``confirmed_fonts`` is the mapping
    ``build_font_authority`` consumes, and the sibling fields record what was
    looked at, so an empty yield is never ambiguous about its cause.
    """
    status, rows = _load_rows(evidence_path)
    by_sha: dict[str, dict] = {}
    for row in rows:
        sha = ((row.get("machine") or {}).get("file_sha256") or "")
        if sha:
            by_sha.setdefault(sha, row)

    confirmed: dict[str, dict] = {}
    reports = []
    for role, path in faces:
        sha = extract_identity(path)["sha256"]
        if not sha:
            outcome = FACE_NO_FILE_IDENTITY
        elif sha in by_sha:
            outcome = FACE_JOINED
            confirmed[role] = _confirmation(by_sha[sha])
        else:
            outcome = FACE_NO_MATCH
        reports.append({"role": role, "sha256": sha, "outcome": outcome})

    return {
        "schema_version": SCHEMA,
        "evidence_status": status,
        "evidence_path": str(Path(evidence_path) if evidence_path
                             else DEFAULT_EVIDENCE_PATH),
        "rows_considered": len(rows),
        "faces": reports,
        "confirmed_fonts": confirmed,
    }


def join_document_fonts(doc, *, evidence_path=None) -> dict:
    """§BH26(b) — the PRODUCTION entry: join the faces the emitter will actually
    use for ``doc``, resolved by the seam's own helper so the mapping is keyed by
    the roles ``build_font_authority`` will record and no other. Returns the whole
    join result (see ``join_font_evidence``); the call site passes
    ``["confirmed_fonts"]`` to the seam. Same ceiling, same yield discipline.
    """
    from apps.ire.container_font_authority import _resolved_faces
    faces, _outlined = _resolved_faces(doc)
    return join_font_evidence([(role, path) for role, _name, path in faces],
                              evidence_path=evidence_path)


__all__ = [
    "SCHEMA", "DEFAULT_EVIDENCE_PATH",
    "JOIN_VERIFICATION", "JOIN_SOURCE",
    "EVIDENCE_READ", "EVIDENCE_ABSENT", "EVIDENCE_UNREADABLE",
    "FACE_JOINED", "FACE_NO_MATCH", "FACE_NO_FILE_IDENTITY",
    "join_font_evidence", "join_document_fonts",
]
