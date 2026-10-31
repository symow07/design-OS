"""Font authority + confirmation gate for the native container (Phase 2B-3A,
§1/§2).

Records the identity of every live-text face the emitter actually uses and the
authority state that governs whether it may reach PRODUCTION. This is a
PRODUCTION-READINESS concern, not a reconstruction blocker: concept review
continues on the fallback face, and it is Gate-2 approval (wired in 2B-3D) that
refuses until production font authority passes — the codes here never enter the
reconstruction ``blockers`` list.

Discipline (matches the DIP rules):
* licence authority is NEVER inferred from the font family name;
* ``fsType`` bits are embedding EVIDENCE, never licence permission — they do
  not set ``production_use_status`` (that stays human-verified);
* font binaries are never distributed — only identity + SHA-256 are recorded;
* a defaulted substitution is ``UNVERIFIED`` + ``CONTAINER_FONT_FALLBACK_
  DETECTED`` — never an unearned ``APPROVED_FOR_CONCEPT_ONLY``.
"""
from __future__ import annotations

import hashlib
import os

SCHEMA = "container_font_authority/1.0"

# --- verification states (§1) -----------------------------------------------
VERIFIED_FOR_PRODUCTION = "VERIFIED_FOR_PRODUCTION"
APPROVED_FOR_CONCEPT_ONLY = "APPROVED_FOR_CONCEPT_ONLY"
LICENCE_REVIEW_REQUIRED = "LICENCE_REVIEW_REQUIRED"
FONT_FILE_MISSING = "FONT_FILE_MISSING"
FONT_IDENTITY_MISMATCH = "FONT_IDENTITY_MISMATCH"
UNVERIFIED = "UNVERIFIED"

# --- §BH14 the ceiling: which of those six a MACHINE may write --------------
# Defined by SUBSTANCE, not by list position (§BH14(a)): a state is ABOVE the
# ceiling if it GRANTS. Reordering the six constants above therefore cannot
# move the partition, which is what lets the cap test assert a reason rather
# than an index.
ABOVE_CEILING = "ABOVE_CEILING"
AT_OR_BELOW_CEILING = "AT_OR_BELOW_CEILING"
CEILING_SIDES = (ABOVE_CEILING, AT_OR_BELOW_CEILING)

# Every state carries its side: 2 forbidden / 4 permitted, per §BH14(a) and the
# owner's confirmation at §BH14(d). This is NOT the grouping
# ``font_confirmation_gate`` uses below — that one answers production
# readiness, emits ONE code for both UNVERIFIED and APPROVED_FOR_CONCEPT_ONLY,
# and §BH14(d) leaves it untouched. The two partitions disagree on exactly one
# state and are both correct, because they answer different questions.
VERIFICATION_CEILING = {
    # ABOVE — approval-shaped. A machine writing these confers authority.
    VERIFIED_FOR_PRODUCTION: ABOVE_CEILING,
    APPROVED_FOR_CONCEPT_ONLY: ABOVE_CEILING,
    # AT OR BELOW — they grant nothing.
    LICENCE_REVIEW_REQUIRED: AT_OR_BELOW_CEILING,
    FONT_FILE_MISSING: AT_OR_BELOW_CEILING,
    FONT_IDENTITY_MISMATCH: AT_OR_BELOW_CEILING,
    UNVERIFIED: AT_OR_BELOW_CEILING,        # §BH14(d), the owner's typed words
}
MACHINE_FORBIDDEN_VERIFICATIONS = tuple(
    s for s, side in VERIFICATION_CEILING.items() if side == ABOVE_CEILING)
MACHINE_WRITABLE_VERIFICATIONS = tuple(
    s for s, side in VERIFICATION_CEILING.items() if side == AT_OR_BELOW_CEILING)


class FontStateAboveCeiling(RuntimeError):
    """A machine tried to write a font state that GRANTS.

    Deliberately NOT a ``ValueError``: an unrecognised state raises ``ValueError``
    instead, and the cap test must be able to prove WHICH of the two refusals
    fired. ``tools/dip0c/font_rights.py`` keeps its own two refusals disjoint for
    the same reason.
    """


def machine_writable_verification(value: str) -> str:
    """Guard. Returns ``value`` only if it sits at or below the ceiling.

    A machine may record what it has found about a font; it may never record a
    state that grants. Anything outside the six is refused outright, and there
    is no pass-through for ``None`` — this module's own answer to "no state
    yet" is ``UNVERIFIED``, not absence.
    """
    if value not in VERIFICATION_CEILING:
        raise ValueError(
            f"{value!r} is not a container font verification state. "
            f"Known: {sorted(VERIFICATION_CEILING)}")
    if VERIFICATION_CEILING[value] == ABOVE_CEILING:
        raise FontStateAboveCeiling(
            f"{value!r} is above the ceiling: a machine writing it would confer "
            f"authority only a human may confer. Writable: "
            f"{list(MACHINE_WRITABLE_VERIFICATIONS)}")
    return value


# --- §BH15(a) the record's ORIGIN, under the same ceiling -------------------
# §BH15(a) extends §BH14(a) from ``verification`` to every authority-bearing
# field: a machine "may never write a human-confirmation claim, and may never
# suppress a truthful finding". ``source`` is such a field, and ``is_fallback``
# is derived from it below because clearing that flag DELETES a gate code.
#
# The SOURCE_ prefix on these names is load-bearing, not decoration: the drift
# guard in ``test_container_font_authority`` asserts that the only SELF-NAMING
# uppercase strings here are the six verification states, so a bare
# ``MACHINE_DERIVED = "MACHINE_DERIVED"`` would read as a seventh state.
SOURCE_PLACEHOLDER_FALLBACK = "PLACEHOLDER_FALLBACK"
SOURCE_USER_CONFIRMED = "USER_CONFIRMED"

#: Measured, not invented. §BH15(a) left the exact string to "measurement
#: against the house idiom" and offered MACHINE_JOINED as an example; that
#: string appears nowhere in the repo, while ``design_context.PROVENANCES`` and
#: ``design_intent.REFERENCE_SOURCES`` are both ("MACHINE_DERIVED",
#: "HUMAN_VERIFIED") and MACHINE_DERIVED is the only MACHINE_* literal the repo
#: already uses in a ``source`` field.
SOURCE_MACHINE_DERIVED = "MACHINE_DERIVED"

#: a confirmation declaring an origin this module does not know. Deliberately
#: NOT rounded to the nearest known origin — ``container_method_provenance.
#: method_stage`` refuses the same rounding for the same reason: "a stage
#: nobody recognises is unattributed, which is the honest answer and the
#: blocking one".
SOURCE_UNATTRIBUTED = "UNATTRIBUTED"

#: §BH16(a): a confirmation that declares NO origin at all. Distinct from
#: UNATTRIBUTED above, and the distinctness is FORCED rather than stylistic —
#: measured, not argued. `test_an_unrecognised_provenance_is_not_rounded_to_a_
#: confirmation` requires UNATTRIBUTED to carry ``is_fallback is True``, while
#: §BH16(a) requires silence to leave that flag alone. Collapsing the two was
#: BUILT AND RUN both ways: sharing the string with the ceiling-based flag rule
#: reddens the protected `test_confirmed_production_face_can_verify`, and
#: sharing it with the flag rule below reddens the unrecognised-provenance test.
#: One string cannot carry both flag values.
#:
#: The spelling is MEASURED against the house idiom per §BH16(a), and the owner's
#: own example WINS here where his MACHINE_JOINED lost at §BH15(a). The WEAK leg
#: is stated first, because it is the leg that decided the earlier contest: as a
#: bare QUOTED LITERAL, "UNDECLARED" had ZERO prior uses, and its four
#: pre-existing uppercase appearances in tracked .py are all PROSE, none a value.
#: That is precisely MACHINE_JOINED's disqualifying position. The difference is
#: that MACHINE_JOINED lost TO SOMETHING — a live incumbent, MACHINE_DERIVED,
#: already paired with HUMAN_VERIFIED — whereas nothing occupies this slot.
#:
#: What it wins on. The WORD is thoroughly house vocabulary — 372 case-insensitive
#: occurrences across the tracked tree at HEAD, 134 of them in .py across 31 files
#: — and the house builds it as a COMPOUND: `UNDECLARED_READINESS_SECTION` in this
#: very package, plus `UNDECLARED_TIER_PREFIX`, `AUTHORED_COLOUR_SPACE_UNDECLARED`,
#: `PICK_DECISION_UNDECLARED`, `RECORD_UNDECLARED`. That is the shape the CONSTANT
#: takes here, while the VALUE stays a bare participle like its three neighbours.
#: It is also the morphological twin of UNVERIFIED, the analogy §BH16(a) draws by
#: name, and the word this repository already used for this exact state: the test
#: inverted in this commit was called
#: `test_an_undeclared_confirmation_still_reads_as_human`.
#:
#: Runner-up UNSTATED lost on MEANING first — it glosses as a value nobody stated,
#: not an ORIGIN nobody declared — and on footprint second: 22 case-insensitive
#: occurrences to UNDECLARED's 372, its three `apps/ire` hits all prose about
#: unstated predicates and estimates, never an enum.
SOURCE_UNDECLARED = "UNDECLARED"

#: Partitioned by SUBSTANCE per §BH14(a): a source is ABOVE the ceiling if it
#: claims A HUMAN ACTED. Exactly one does. UNDECLARED is AT OR BELOW: silence
#: grants nothing, which is §BH16(a)'s whole point.
SOURCE_CEILING = {
    SOURCE_USER_CONFIRMED: ABOVE_CEILING,
    SOURCE_PLACEHOLDER_FALLBACK: AT_OR_BELOW_CEILING,
    SOURCE_MACHINE_DERIVED: AT_OR_BELOW_CEILING,
    SOURCE_UNATTRIBUTED: AT_OR_BELOW_CEILING,
    SOURCE_UNDECLARED: AT_OR_BELOW_CEILING,
}
MACHINE_FORBIDDEN_SOURCES = tuple(
    s for s, side in SOURCE_CEILING.items() if side == ABOVE_CEILING)
MACHINE_WRITABLE_SOURCES = tuple(
    s for s, side in SOURCE_CEILING.items() if side == AT_OR_BELOW_CEILING)

#: Which sources leave ``is_fallback`` CLEAR. §BH15(a) derived this from the
#: ceiling — "only a source ABOVE the ceiling may clear it" — and §BH16(a)
#: BREAKS that derivation, so it is written out rather than computed, and the
#: break is named instead of hidden. The two members are here for DIFFERENT
#: reasons. USER_CONFIRMED clears the flag because a human CHOSE this face.
#: UNDECLARED clears it because §BH16(a) says in terms that "is_fallback stays
#: truthful under an undeclared confirmation — it does not flip on silence",
#: NOT because silence means anything was chosen.
#:
#: The consequence is that a declared-but-unrecognised origin IS a fallback
#: while a declared-NOTHING origin is not, i.e. silence is treated more
#: leniently than an unrecognised declaration. That asymmetry is a measured
#: consequence of the ruling's own sentence, is reported to the owner rather
#: than smoothed away, and is why this set is not `== ABOVE_CEILING`.
SOURCES_CLEARING_FALLBACK = frozenset({SOURCE_USER_CONFIRMED,
                                       SOURCE_UNDECLARED})


def machine_writable_source(value: str) -> str:
    """Guard. The ``source`` twin of ``machine_writable_verification``.

    Keeps the same two DISJOINT refusals, so a cap test can prove which fired:
    an unrecognised origin raises ``ValueError``, and a human-confirmation
    claim raises ``FontStateAboveCeiling``.
    """
    if value not in SOURCE_CEILING:
        raise ValueError(
            f"{value!r} is not a container font record source. "
            f"Known: {sorted(SOURCE_CEILING)}")
    if SOURCE_CEILING[value] == ABOVE_CEILING:
        raise FontStateAboveCeiling(
            f"{value!r} claims a human confirmed this face; a machine may "
            f"never write it. Writable: {list(MACHINE_WRITABLE_SOURCES)}")
    return value


# --- §BH12(b) BUILD D — the seam's guard ------------------------------------
# The ceiling above governs what a MACHINE may WRITE. This guard governs what
# may ARRIVE, which is a different question: §BH13(g) measured that the seam
# refuses NOTHING today — an invented state, a dip0c HUMAN_ONLY state, the
# ceiling in lower case and the empty string are all stored verbatim, and a
# licence claim with no evidence behind it is copied straight into the record.


class UnfoundedLicenceClaim(RuntimeError):
    """A licence-bearing field arrived carrying a claim with no evidence.

    Deliberately NOT a ``ValueError`` and not a ``FontStateAboveCeiling``: the
    three refusals stay DISJOINT so a test can prove which one fired, the same
    discipline ``machine_writable_source`` states for its own two.
    """


#: §BH13(b): *"the guard refuses VERIFIED_FOR_PRODUCTION OUTRIGHT. No
#: owner-confirmation exception branch is built until Option C lands... refusal
#: is total for now, and that narrowing loses nothing because no such record
#: exists to arrive."* Written as a set rather than a bare comparison so that
#: Option C has one obvious place to narrow, and so the refusal is stated by
#: SUBSTANCE. It is deliberately NOT ``MACHINE_FORBIDDEN_VERIFICATIONS``:
#: that tuple also holds APPROVED_FOR_CONCEPT_ONLY, which neither §BH12(b) nor
#: §BH13(b) names and which is measured not to clear the gate anyway. Refusing
#: it too would be going wider than the sentence, against §BH13(d)'s *"if I
#: meant something narrower, my sentence governs."*
SEAM_REFUSED_VERIFICATIONS = frozenset({VERIFIED_FOR_PRODUCTION})

#: The claim-bearing fields, each mapped to the value it carries when NOTHING
#: is claimed. A field departing from its default is a CLAIM and needs
#: evidence; a field at its default asserts nothing and needs none.
LICENCE_CLAIM_DEFAULTS = {
    "licence_id": "",
    "redistribution_status": "UNVERIFIED",
    "production_use_status": "UNVERIFIED",
    "approved_by": "",
    "approved_at": "",
}


def guarded_confirmation(confirmed: dict | None) -> dict | None:
    """Guard. The app-side equivalent §BH12(b) calls for, at the seam.

    §BH12(b): *"The app-side seam gets a machine_font_state-equivalent: a
    licence claim arriving without evidence is refused, and
    VERIFIED_FOR_PRODUCTION arriving from anything but an owner-confirmation
    record is refused."* §BH13(b) then narrowed the second half to outright
    refusal, so no exception branch is built here.

    THREE DISJOINT REFUSALS, mirroring ``tools/dip0c/font_rights.
    machine_font_state`` — which raises ``ValueError`` for an unknown state and
    ``HumanOnlyStateViolation`` for a human-only one — plus the licence
    question, which that function does not have to ask.

    ONE READING IS FORCED RATHER THAN CHOSEN. A ``licence_id`` is refused
    whenever it is non-empty and unevidenced, WITHOUT regard to what it says.
    The alternative — treat a placeholder like ``PENDING-OWNER-REVIEW`` as no
    claim while refusing ``OFL-1.1`` — requires code that can tell a licence
    name from a placeholder, which is precisely the reading §BH12(a) reserves:
    *"reading the OFL is my act, not code's."* A machine that cannot read
    licences cannot grade them either, so it refuses on the SHAPE.

    An ABSENT ``verification`` key is left alone: ``_face_record`` already
    defaults it to ``LICENCE_REVIEW_REQUIRED``, which grants nothing. An
    explicitly supplied ``""`` is NOT the same thing and does reach the refusal
    — the lesson the producer's own sentinel defect taught one commit ago, where
    substituting a permitted default for a value the caller asked to emit was a
    silent widening at the one seam that exists to prevent one.
    """
    if not confirmed:
        return confirmed

    if "verification" in confirmed:
        value = confirmed["verification"]
        if value not in VERIFICATION_CEILING:
            raise ValueError(
                f"{value!r} is not a container font verification state. "
                f"Known: {sorted(VERIFICATION_CEILING)}")
        if value in SEAM_REFUSED_VERIFICATIONS:
            raise FontStateAboveCeiling(
                f"{value!r} may not arrive at this seam. It is refused "
                f"outright per §BH13(b): the only thing that could confer it "
                f"is an owner-confirmation record, and none exists to arrive "
                f"from.")

    if not str(confirmed.get("licence_evidence") or "").strip():
        claimed = sorted(f for f, nothing in LICENCE_CLAIM_DEFAULTS.items()
                         if f in confirmed and confirmed[f] != nothing)
        if claimed:
            raise UnfoundedLicenceClaim(
                f"{claimed} claim a licence position with no `licence_evidence` "
                f"behind it. Possession is not permission: evidence is not "
                f"approval either, but a claim without even evidence is nothing "
                f"at all.")

    return confirmed


# --- §2 gate codes ----------------------------------------------------------
FONT_CONFIRMATION_REQUIRED = "CONTAINER_FONT_CONFIRMATION_REQUIRED"
FONT_MISSING = "CONTAINER_FONT_MISSING"
FONT_IDENTITY_MISMATCH_CODE = "CONTAINER_FONT_IDENTITY_MISMATCH"
FONT_LICENSE_REVIEW_REQUIRED = "CONTAINER_FONT_LICENSE_REVIEW_REQUIRED"
FONT_FALLBACK_DETECTED = "CONTAINER_FONT_FALLBACK_DETECTED"


def _sha256_file(path: str) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def extract_identity(path: str | None) -> dict:
    """Font identity from the FILE via fontTools — family / style / PostScript
    name / fsType (embedding evidence) / SHA-256. Never reads licence from the
    name. Degrades to empty fields (file_present False) on any failure."""
    out = {"family": "", "style": "", "postscript_name": "", "fs_type": None,
           "embedding_evidence": "", "sha256": "", "file_present": False}
    if not path or not os.path.exists(path):
        return out
    out["file_present"] = True
    out["sha256"] = _sha256_file(path)
    try:
        from fontTools.ttLib import TTFont
        with TTFont(path, lazy=True, fontNumber=0) as font:
            name = font["name"]

            def _n(*ids):
                for i in ids:
                    rec = name.getDebugName(i)
                    if rec:
                        return rec
                return ""
            out["family"] = _n(16, 1)
            out["style"] = _n(17, 2)
            out["postscript_name"] = _n(6)
            os2 = font.get("OS/2")
            if os2 is not None and hasattr(os2, "fsType"):
                fs = int(os2.fsType)
                out["fs_type"] = fs
                # bit 1 = restricted; bits 8/9 = no-subset / bitmap-only.
                # Recorded as EVIDENCE for a human licence review — not a right.
                out["embedding_evidence"] = (
                    "installable" if fs == 0 else f"restricted_bits={fs}")
    except Exception:  # noqa: BLE001 — identity degrades, never fatal
        pass
    return out


def _confirmation_source(confirmed) -> str:
    """Which origin a confirmation DECLARES, per §BH15(a).

    An absent declaration reads as ``UNDECLARED``, per §BH16(a): "a confirmation
    carrying no provenance key may no longer read as a human claim. No
    declaration => a conservative non-human source... This is the same principle
    as UNVERIFIED: silence grants nothing."

    This INVERTS the seam's former default, which returned ``USER_CONFIRMED``
    here and made the §BH15(a) cap structural only against a producer that
    declared itself. The two live assertions that pinned that contract are
    inverted in the same commit, which is their §BH13(c) moment and not a bar
    lowered. ``is_fallback`` is deliberately NOT carried along — see
    ``SOURCES_CLEARING_FALLBACK``.
    """
    if not confirmed:
        return SOURCE_PLACEHOLDER_FALLBACK
    declared = str(confirmed.get("provenance") or "").strip()
    if not declared:
        return SOURCE_UNDECLARED
    if declared in SOURCE_CEILING:
        return declared
    return SOURCE_UNATTRIBUTED


def _face_record(*, role, name, path, confirmed) -> dict:
    """One §1 face record with honest conservative defaults.

    The guard runs FIRST, so a refused confirmation never reaches a record at
    all. Placing it here rather than in ``build_font_authority`` covers both
    entry points with one check.
    """
    confirmed = guarded_confirmation(confirmed)
    ident = extract_identity(path)
    src = _confirmation_source(confirmed)
    rec = {
        "role": role,
        "font_family": ident["family"] or (name or ""),
        "font_style": ident["style"] or role,
        "postscript_name": ident["postscript_name"],
        "file_identity": path or "",
        "sha256": ident["sha256"],
        "fs_type": ident["fs_type"],
        "embedding_status": ident["embedding_evidence"],   # EVIDENCE only
        "redistribution_status": "UNVERIFIED",
        "production_use_status": "UNVERIFIED",              # human-verified only
        "source": src,
        "licence_id": "",
        "licence_evidence": "",
        "approved_by": "",
        "approved_at": "",
        # §BH15(a): truthful REGARDLESS of confirmation state. Clearing this
        # flag deletes CONTAINER_FONT_FALLBACK_DETECTED at the gate below, so
        # clearing it is itself an authority-bearing act. §BH16(a) then withheld
        # silence from the inversion, so the set is now explicit rather than
        # derived from the ceiling.
        "is_fallback": src not in SOURCES_CLEARING_FALLBACK,
        "verification": UNVERIFIED,
    }
    if confirmed:
        # a production confirmation for this role. `source`/`is_fallback` are
        # NOT set here: they follow the declared origin above, so a machine
        # feeding this seam cannot acquire them by the act of confirming.
        rec.update({
            "licence_id": confirmed.get("licence_id", ""),
            "licence_evidence": confirmed.get("licence_evidence", ""),
            "redistribution_status": confirmed.get("redistribution_status",
                                                    "UNVERIFIED"),
            "production_use_status": confirmed.get("production_use_status",
                                                   "UNVERIFIED"),
            "approved_by": confirmed.get("approved_by", ""),
            "approved_at": confirmed.get("approved_at", ""),
            "verification": confirmed.get("verification", LICENCE_REVIEW_REQUIRED),
        })
        req_ps = confirmed.get("postscript_name")
        if not ident["file_present"]:
            rec["verification"] = FONT_FILE_MISSING
        elif req_ps and ident["postscript_name"] and req_ps != ident["postscript_name"]:
            rec["verification"] = FONT_IDENTITY_MISMATCH
    return rec


def _resolved_faces(doc):
    """(role, name, path) for every face the emitter will actually use, plus
    whether any text run was outlined (§2: outlined text is reported).

    §BH32(e) W4: resolved by the role-based selection layer
    (``apps.ire.font_roles.record_faces``) — every role the document's runs
    need, walked through the ruled chains and verified through this seam's own
    record builder and the owner-grant channel; recorded under the document's
    own role names (``bold``/``regular`` stay as declared; Arabic runs add
    arabic-display / arabic-heading / arabic-body as DISTINCT rows — §BH33(4)); a
    refused role is recorded with no file so the record shows the refusal and the gate
    fires. The layer never calls ``build_font_authority``, so there is no
    recursion through this function.

    The rewrite keeps this file's line count: the protected gate grouping
    below is pinned at lines [514:541] and stays byte-identical.
    """
    from apps.ire.font_roles import record_faces
    return record_faces(doc)





def _regular_face():
    """The regular face's registration label and the file reportlab holds for it.

    ``_resolve_fonts()`` returns REGISTRATION LABELS, not filenames. The regular
    label is ``NotoSans``, which is neither the family (``Noto Sans``), nor the
    postscript name (``NotoSans-Regular``), nor the file stem — it is a fourth,
    caller-chosen string. Deriving the path as ``f"{label}.ttf"`` therefore found
    a file for the bold face only, by the coincidence that ``NotoSans-Bold`` is
    both its label and its stem, and reported the regular face as fileless: no
    identity, no sha256, nothing to join evidence against.

    Asked of reportlab instead, per ``registered_font_path``: the face that
    answered for the widths is the face whose file this is. That also keeps the
    two lower fallback tiers honest — DejaVu resolves outside ``static/fonts``,
    and Helvetica is a built-in with no file at all, where None is the true answer.
    """
    try:
        from apps.dielines.exporters.counter_display_files import _resolve_fonts
        reg, _ = _resolve_fonts()
    except Exception:  # noqa: BLE001
        reg = None
    from apps.ire.text_metrics import registered_font_path
    return reg, registered_font_path(reg)


def build_font_authority(doc, *, confirmed_fonts: dict | None = None) -> dict:
    """container_font_authority/1.0 for the emitted document."""
    confirmed_fonts = confirmed_fonts or {}
    faces, outlined = _resolved_faces(doc)
    records = []
    for role, name, path in faces:
        conf = confirmed_fonts.get(role)
        # a confirmed production font supplies its OWN file/name; otherwise we
        # record the resolved placeholder (a fallback).
        use_name = (conf.get("name") if conf and conf.get("name") else name)
        use_path = (conf.get("path") if conf and conf.get("path") else path)
        records.append(_with_instance(_face_record(role=role, name=use_name, path=use_path,
                                                   confirmed=conf), doc, role))
    return {"schema_version": SCHEMA, "faces": records, "outlined_text_present": outlined,
            "skipped_candidates": _skipped_candidates(doc),        # §BH32(h)(3)
            "all_production_verified": bool(records) and all(
                r["verification"] == VERIFIED_FOR_PRODUCTION for r in records)}


def font_confirmation_gate(authority: dict) -> list[str]:
    """§2 production-font gate codes for the authority record. Empty when every
    face is VERIFIED_FOR_PRODUCTION. These are PRODUCTION-READINESS codes — a
    caller must NOT add them to the reconstruction blockers (concept review
    continues; Gate-2 approval enforces them)."""
    codes: list[str] = []
    for r in authority.get("faces") or []:
        v = r.get("verification")
        if v == VERIFIED_FOR_PRODUCTION:
            continue
        if v == FONT_FILE_MISSING:
            codes.append(FONT_MISSING)
        elif v == FONT_IDENTITY_MISMATCH:
            codes.append(FONT_IDENTITY_MISMATCH_CODE)
        elif v == LICENCE_REVIEW_REQUIRED:
            codes.append(FONT_LICENSE_REVIEW_REQUIRED)
        else:                            # UNVERIFIED / concept-only
            codes.append(FONT_CONFIRMATION_REQUIRED)
        if r.get("is_fallback"):
            codes.append(FONT_FALLBACK_DETECTED)
    # stable, de-duplicated order
    seen, ordered = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


__all__ = [
    "SCHEMA", "extract_identity", "build_font_authority",
    "font_confirmation_gate",
    "VERIFIED_FOR_PRODUCTION", "APPROVED_FOR_CONCEPT_ONLY",
    "LICENCE_REVIEW_REQUIRED", "FONT_FILE_MISSING", "FONT_IDENTITY_MISMATCH",
    "UNVERIFIED", "FONT_CONFIRMATION_REQUIRED", "FONT_MISSING",
    "FONT_IDENTITY_MISMATCH_CODE", "FONT_LICENSE_REVIEW_REQUIRED",
    "FONT_FALLBACK_DETECTED",
    "ABOVE_CEILING", "AT_OR_BELOW_CEILING", "CEILING_SIDES",
    "VERIFICATION_CEILING", "MACHINE_FORBIDDEN_VERIFICATIONS",
    "MACHINE_WRITABLE_VERIFICATIONS", "FontStateAboveCeiling",
    "machine_writable_verification",
    "SOURCE_PLACEHOLDER_FALLBACK", "SOURCE_USER_CONFIRMED",
    "SOURCE_MACHINE_DERIVED", "SOURCE_UNATTRIBUTED", "SOURCE_UNDECLARED",
    "SOURCE_CEILING", "SOURCES_CLEARING_FALLBACK",
    "MACHINE_FORBIDDEN_SOURCES", "MACHINE_WRITABLE_SOURCES",
    "machine_writable_source",
    "UnfoundedLicenceClaim", "SEAM_REFUSED_VERIFICATIONS",
    "LICENCE_CLAIM_DEFAULTS", "guarded_confirmation",
]


def _skipped_candidates(doc) -> list[dict]:
    """§BH32(h)(3): the candidates the layer's chains skipped as void or
    unverified before the face that rendered, at their honest states with the
    named code — the render falls back, the record never hides it. Defined
    BELOW the protected gate grouping so its lines stay where they are pinned."""
    from apps.ire.font_roles import skipped_candidates
    return skipped_candidates(doc)


def _with_instance(rec: dict, doc, role: str) -> dict:
    """§BH33(2): a variable face's row names the pinned instance the artefact
    embeds — ``postscript_name`` / ``font_style`` = the instance, ``sha256`` /
    ``file_identity`` = the GRANTED file (the verification subject the channel
    and the join key on), ``instance`` = the axes, the derived bytes' sha256
    and path, the source face and its default-instance name. Rows of static
    faces and of exempt documents are returned untouched. Defined BELOW the
    protected gate grouping so its lines stay where they are pinned."""
    from apps.ire.font_roles import instance_for_record
    inst = instance_for_record(doc, role)
    if not inst:
        return rec
    return dict(rec, postscript_name=inst["postscript"], font_style=inst["style"] or rec["font_style"],
                instance={"postscript_name": inst["postscript"], "axes": dict(inst["axes"]),
                          "sha256": inst["sha256"], "path": inst["path"],
                          "derived_from": inst["derived_from"],
                          "derived_from_sha256": inst["derived_from_sha256"],
                          "source_default_instance": inst["source_default_instance"]})
