"""Phase 2B-3A §1/§2 — container font authority + confirmation gate.

Records every emitted face's identity and a conservative authority state; the
defaulted placeholder is UNVERIFIED + CONTAINER_FONT_FALLBACK_DETECTED (never
an unearned approval). licence is never inferred from the family name; fsType
is embedding evidence, not permission. The gate codes are production-readiness
codes — they do NOT block reconstruction.

§BH14 adds the CEILING below — which of the six verification states a MACHINE
may write. That is a different question from the gate codes above, and the two
partitions deliberately disagree on one state.
"""
from __future__ import annotations

import json

import pytest

from apps.ire import container_font_authority as cfa
from apps.ire import container_font_evidence_join as cfj
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _doc():
    bb = build_backbone(ContainerProfile(archetype="bottle", height_mm=110,
                                         width_mm=40))
    zones = cc.propose_zones(cc.build_inferred_profile("bottle"))
    return compose_container_graph(bb, product_name="Rose Nectar",
                                   name_lines=["Rose Nectar"], zones=zones,
                                   native=True)


def test_authority_records_every_emitted_face():
    auth = cfa.build_font_authority(_doc())
    assert auth["schema_version"] == "container_font_authority/1.0"
    assert auth["faces"]
    for f in auth["faces"]:
        # full §1 field list present
        assert set(f) >= {"font_family", "font_style", "postscript_name",
                          "file_identity", "sha256", "fs_type",
                          "embedding_status", "redistribution_status",
                          "production_use_status", "source", "licence_id",
                          "licence_evidence", "verification", "approved_by",
                          "approved_at"}


def test_placeholder_is_unverified_not_an_unearned_approval():
    auth = cfa.build_font_authority(_doc())
    for f in auth["faces"]:
        assert f["verification"] == cfa.UNVERIFIED
        assert f["is_fallback"] is True
        assert f["production_use_status"] == "UNVERIFIED"    # never auto-granted
        assert f["source"] == "PLACEHOLDER_FALLBACK"
    assert auth["all_production_verified"] is False


def test_gate_returns_confirmation_and_fallback_not_mismatch():
    auth = cfa.build_font_authority(_doc())
    codes = cfa.font_confirmation_gate(auth)
    assert cfa.FONT_CONFIRMATION_REQUIRED in codes
    assert cfa.FONT_FALLBACK_DETECTED in codes
    # with no REQUIRED identity specified, the mismatch code must NOT misfire
    assert cfa.FONT_IDENTITY_MISMATCH_CODE not in codes
    assert cfa.FONT_MISSING not in codes


def test_extract_identity_reads_file_not_name():
    # the resolved placeholder face has a real file → identity + sha extracted
    _, path = cfa._regular_face()
    if path:
        ident = cfa.extract_identity(path)
        assert ident["file_present"] is True
        assert ident["sha256"]
        # fsType recorded as evidence (may be 0 = installable) but never a right
        assert "family" in ident
    # a missing path degrades cleanly
    miss = cfa.extract_identity("/no/such/font.ttf")
    assert miss["file_present"] is False and miss["sha256"] == ""


def test_a_typed_in_production_claim_is_refused_at_the_seam():
    # THE INVERSION §BH13(c) ORDERS, and this is the register's "revived test":
    # it was named `test_confirmed_production_face_can_verify` there and at
    # §BH15's :15250, so the old name is kept greppable here rather than lost.
    # "the revived test is INVERTED at commit (3), not deleted: its assertion
    # flips to expect refusal, and its red-to-green transition is the guard's
    # ordered proof." The name moves with the assertion on the precedent of
    # `test_an_undeclared_confirmation_still_reads_as_human`, renamed when the
    # commit above inverted it — a name that keeps asserting the old contract
    # is a stale claim, not a stable identifier.
    #
    # The BODY is unchanged: same confirmation, same call. Measured before the
    # guard, this exact dict produced `is_fallback` clear on every face and
    # `font_confirmation_gate(auth) == []` — a gate silenced completely by a
    # licence string somebody typed into a test. That is what is refused now.
    doc = _doc()
    ps = None
    _, path = cfa._regular_face()
    if path:
        ps = cfa.extract_identity(path)["postscript_name"]
    if not path:
        return                          # no local font file to confirm against
    conf = {"verification": cfa.VERIFIED_FOR_PRODUCTION, "licence_id": "OFL-1.1",
            "production_use_status": "GRANTED", "postscript_name": ps,
            "path": path}
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa.build_font_authority(doc, confirmed_fonts={"bold": conf,
                                                       "regular": conf})


# --- §BH14 — the ceiling on what a MACHINE may write into ``verification`` ---
# Partition by SUBSTANCE, not list position (§BH14(a)): a state is above the
# ceiling if it GRANTS. §BH14(d) places UNVERIFIED at or below it, fixing the
# partition at 2 forbidden / 4 permitted. Written against the MEASURED strings,
# never guessed (§BH13(d)).
#
# SCOPE: no producer exists yet, so these prove the ENUM, not the cap. The cap
# test §BH14(a) orders — enumerating the forbidden side and proving each state
# unreachable — belongs to the producer commit, which is what §BH14(b) means by
# the producer's cap enforcing "against infrastructure that already exists".

# the six, written out literally rather than read back from the module, so a
# change there fails here instead of silently redefining the assertion
SIX_STATES = {
    "VERIFIED_FOR_PRODUCTION", "APPROVED_FOR_CONCEPT_ONLY",
    "LICENCE_REVIEW_REQUIRED", "FONT_FILE_MISSING", "FONT_IDENTITY_MISMATCH",
    "UNVERIFIED",
}


def test_ceiling_covers_exactly_the_six_states():
    assert set(cfa.VERIFICATION_CEILING) == SIX_STATES
    assert set(cfa.VERIFICATION_CEILING.values()) <= set(cfa.CEILING_SIDES)


def test_partition_is_two_forbidden_four_permitted():
    forbidden = set(cfa.MACHINE_FORBIDDEN_VERIFICATIONS)
    writable = set(cfa.MACHINE_WRITABLE_VERIFICATIONS)
    assert forbidden == {cfa.VERIFIED_FOR_PRODUCTION,
                         cfa.APPROVED_FOR_CONCEPT_ONLY}
    assert writable == {cfa.LICENCE_REVIEW_REQUIRED, cfa.FONT_FILE_MISSING,
                        cfa.FONT_IDENTITY_MISMATCH, cfa.UNVERIFIED}
    assert not forbidden & writable
    assert forbidden | writable == SIX_STATES


def test_unverified_sits_at_or_below_per_owner_confirmation():
    # §BH14(d). Asserted apart from the partition above because this is the one
    # state the ruling's own gloss did not name, and the answer is owner text.
    assert cfa.VERIFICATION_CEILING[cfa.UNVERIFIED] == cfa.AT_OR_BELOW_CEILING
    assert cfa.machine_writable_verification(cfa.UNVERIFIED) == cfa.UNVERIFIED


def test_every_forbidden_state_is_refused():
    assert cfa.MACHINE_FORBIDDEN_VERIFICATIONS
    for state in cfa.MACHINE_FORBIDDEN_VERIFICATIONS:
        with pytest.raises(cfa.FontStateAboveCeiling):
            cfa.machine_writable_verification(state)


def test_every_permitted_state_passes_through_unchanged():
    assert cfa.MACHINE_WRITABLE_VERIFICATIONS
    for state in cfa.MACHINE_WRITABLE_VERIFICATIONS:
        assert cfa.machine_writable_verification(state) == state


def test_the_two_refusals_are_distinguishable():
    # disjoint types, so the producer's cap test can prove WHICH refusal fired
    assert not issubclass(cfa.FontStateAboveCeiling, ValueError)
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa.machine_writable_verification(cfa.VERIFIED_FOR_PRODUCTION)
    for unknown in ("INVENTED_STATE", "LICENSE_APPROVED",
                    "licence_review_required", "", None):
        with pytest.raises(ValueError):
            cfa.machine_writable_verification(unknown)


def test_a_seventh_state_cannot_be_added_without_placing_it():
    # HEURISTIC drift guard, with its blind spot stated: the six states are
    # self-naming (NAME == "NAME"); the five gate codes are not (they carry a
    # CONTAINER_ prefix), and SCHEMA is not. A seventh self-naming state
    # constant is caught here; a state whose value differed from its name would
    # NOT be, and nothing here claims otherwise.
    self_named = {n for n in dir(cfa)
                  if n.isupper() and isinstance(getattr(cfa, n), str)
                  and getattr(cfa, n) == n}
    assert self_named - set(cfa.CEILING_SIDES) == SIX_STATES


def test_the_gates_own_grouping_is_untouched():
    # §BH14(d): "The gate's :220 grouping answers a different question and stays
    # untouched." The ceiling puts these two states on OPPOSITE sides; the gate
    # still emits ONE code for both, and that disagreement is intended.
    for state in (cfa.UNVERIFIED, cfa.APPROVED_FOR_CONCEPT_ONLY):
        auth = {"faces": [{"verification": state, "is_fallback": False}]}
        assert cfa.font_confirmation_gate(auth) == [
            cfa.FONT_CONFIRMATION_REQUIRED]
    assert (cfa.VERIFICATION_CEILING[cfa.UNVERIFIED]
            != cfa.VERIFICATION_CEILING[cfa.APPROVED_FOR_CONCEPT_ONLY])


# --- §BH15(a) — the ceiling over `source`, and is_fallback's honesty --------
# §BH14's ceiling governed `verification` only. §BH15(a) found that a producer
# perfectly capped there could still confer authority through `source` and
# silence a finding through `is_fallback`, and extended the principle to every
# authority-bearing field. These test THE LEAK, on the same file the resolver
# already picked — which is exactly the machine join's own case, since the join
# is over the ALREADY-RESOLVED face's sha256.

KNOWN_SOURCES = {"PLACEHOLDER_FALLBACK", "USER_CONFIRMED", "MACHINE_DERIVED",
                 "UNATTRIBUTED", "UNDECLARED"}


def _machine_conf():
    """A machine-declared confirmation for the resolved placeholder face.

    Its `verification` sits AT OR BELOW the §BH14 ceiling, so this confirmation
    is fully §BH14-compliant. Everything it is refused below is refused by
    §BH15(a) alone.

    It USED to carry `licence_id: "DIP0C-JOIN"`, and the §BH12(b) guard now
    refuses that: a licence claim with no `licence_evidence` behind it. The key
    is DELETED rather than given fabricated evidence, and the deletion makes the
    helper more faithful rather than less — the real producer that landed one
    commit ago emits no `licence_id` at all, which its own test below pins by
    asserting the field is absent. Measured across the four tests this helper
    feeds: every assertion holds either way and the gate codes are identical, so
    nothing here was relaxed to get past the guard.
    """
    _, path = cfa._regular_face()
    if not path:
        return None
    return {"provenance": "MACHINE_DERIVED", "path": path,
            "verification": "LICENCE_REVIEW_REQUIRED"}


def test_source_ceiling_forbids_only_the_claim_that_a_human_acted():
    # Renamed from `..._is_one_forbidden_three_writable`. The old name carried a
    # COUNT, which §BH16(a)'s fifth value made stale; the ceiling's own ground is
    # SUBSTANCE (§BH14(a)), so the name now states the substance and survives the
    # next addition. The counts are still pinned — by the set literals below.
    assert set(cfa.SOURCE_CEILING) == KNOWN_SOURCES
    forbidden = set(cfa.MACHINE_FORBIDDEN_SOURCES)
    writable = set(cfa.MACHINE_WRITABLE_SOURCES)
    assert forbidden == {cfa.SOURCE_USER_CONFIRMED}
    assert writable == {cfa.SOURCE_PLACEHOLDER_FALLBACK,
                        cfa.SOURCE_MACHINE_DERIVED, cfa.SOURCE_UNATTRIBUTED,
                        cfa.SOURCE_UNDECLARED}
    assert not forbidden & writable
    assert forbidden | writable == KNOWN_SOURCES


def test_clearing_the_fallback_flag_is_no_longer_the_ceiling():
    # §BH15(a) derived is_fallback FROM the ceiling: "only a source above it may
    # clear the flag". §BH16(a) breaks that — silence sits below the ceiling yet
    # "does not flip" the flag. Pinned so the break stays deliberate and visible
    # rather than looking like a set someone forgot to re-derive.
    clearing = set(cfa.SOURCES_CLEARING_FALLBACK)
    assert clearing == {cfa.SOURCE_USER_CONFIRMED, cfa.SOURCE_UNDECLARED}
    assert clearing <= KNOWN_SOURCES
    assert clearing != set(cfa.MACHINE_FORBIDDEN_SOURCES)
    # and the members are here for different reasons: one is above the ceiling,
    # the other is not
    assert cfa.SOURCE_CEILING[cfa.SOURCE_USER_CONFIRMED] == cfa.ABOVE_CEILING
    assert cfa.SOURCE_CEILING[cfa.SOURCE_UNDECLARED] == cfa.AT_OR_BELOW_CEILING


def test_machine_writable_source_keeps_the_two_refusals_disjoint():
    for src in cfa.MACHINE_WRITABLE_SOURCES:
        assert cfa.machine_writable_source(src) == src
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa.machine_writable_source(cfa.SOURCE_USER_CONFIRMED)
    for unknown in ("MACHINE_JOINED", "user_confirmed", "", None):
        with pytest.raises(ValueError):
            cfa.machine_writable_source(unknown)


def test_a_machine_declared_confirmation_cannot_claim_a_human_confirmed_it():
    conf = _machine_conf()
    if conf is None:
        return                          # no local font file to join against
    auth = cfa.build_font_authority(_doc(), confirmed_fonts={"regular": conf,
                                                             "bold": conf})
    assert auth["faces"]
    for f in auth["faces"]:
        assert f["source"] == cfa.SOURCE_MACHINE_DERIVED
        assert f["source"] != cfa.SOURCE_USER_CONFIRMED
        assert f["approved_by"] == ""


def test_a_machine_declared_confirmation_cannot_suppress_the_fallback_finding():
    conf = _machine_conf()
    if conf is None:
        return
    auth = cfa.build_font_authority(_doc(), confirmed_fonts={"regular": conf,
                                                             "bold": conf})
    codes = cfa.font_confirmation_gate(auth)
    assert all(f["is_fallback"] is True for f in auth["faces"])
    assert cfa.FONT_FALLBACK_DETECTED in codes
    # the ceiling-compliant verification it DID supply is still honoured, so
    # this proves the fallback finding survives rather than that the
    # confirmation was ignored wholesale
    assert cfa.FONT_LICENSE_REVIEW_REQUIRED in codes


def test_an_unrecognised_provenance_is_not_rounded_to_a_confirmation():
    conf = _machine_conf()
    if conf is None:
        return
    conf = dict(conf, provenance="SOME_FUTURE_PRODUCER")
    auth = cfa.build_font_authority(_doc(), confirmed_fonts={"regular": conf,
                                                             "bold": conf})
    for f in auth["faces"]:
        assert f["source"] == cfa.SOURCE_UNATTRIBUTED
        assert f["is_fallback"] is True


def test_an_undeclared_confirmation_no_longer_reads_as_human():
    # THE INVERSION, ruled §BH16(a): "a confirmation carrying no provenance key
    # may no longer read as a human claim... silence grants nothing." This test
    # is the one the ruling names, and this is its §BH13(c) moment — the old
    # assertion below it recorded a RESIDUAL reported to the owner, and the owner
    # closed it the other way. Nothing was relaxed to make it pass.
    #
    # The second assertion is UNCHANGED, and that is also the ruling's: "is_fallback
    # stays truthful under an undeclared confirmation — it does not flip on
    # silence." So only `source` moves. Compare the unrecognised-declaration test
    # above, which keeps is_fallback True: a declared-but-unknown origin IS a
    # fallback while a declared-NOTHING one is not. That asymmetry follows from the
    # ruling's own sentence and is reported, not smoothed over.
    conf = _machine_conf()
    if conf is None:
        return
    conf = {k: v for k, v in conf.items() if k != "provenance"}
    auth = cfa.build_font_authority(_doc(), confirmed_fonts={"regular": conf,
                                                             "bold": conf})
    assert auth["faces"]
    for f in auth["faces"]:
        assert f["source"] == cfa.SOURCE_UNDECLARED
        assert f["source"] != cfa.SOURCE_USER_CONFIRMED
        assert f["is_fallback"] is False


# --- §BH12(a) Option B — the confirmed_fonts PRODUCER -----------------------
# The join is capped against the APP enum per §BH13(a), and is fixture-tested
# per §BH15(b) because the real artifact is git-ignored (absent in a clean
# clone) AND contains zero static/fonts rows, so a test joining against the
# real thing would pass while asserting nothing.

FIXTURE_SHA = "f" * 64


def _evidence_row(sha, *, ps="Fixture-Regular"):
    """One row in the MEASURED shape of the real artifact.

    Faithful to the schema, not invented: two blocks under `machine`/`human`
    with `schema_version` and `machine_inference_immutable` alongside, all
    nine permissions false and every human decision null — which is what all
    3,966 live rows carry.
    """
    return {
        "schema_version": "font_face_manifest/1.0",
        "machine_inference_immutable": True,
        "machine": {
            "source_path": f"materials/fixture/{ps}.ttf",
            "file_sha256": sha,
            "face_id": "face-fixture0000000000",
            "postscript_name": ps,
            "preferred_family": "Fixture",
            "license_evidence": [],
            "permissions": {k: False for k in (
                "retrieval_allowed", "automatic_use_allowed",
                "production_use_allowed", "modification_allowed",
                "embedding_allowed", "redistribution_allowed",
                "public_export_allowed", "approved_for_bbrose",
                "approved_for_other_brands")},
        },
        "human": {k: None for k in (
            "reviewer", "reviewed_at", "family_confirmation",
            "source_package_confirmation", "provenance_confirmation",
            "license_decision", "ownership_decision", "quarantine_decision",
            "style_tags_confirmation", "notes", "correction_reason")},
    }


def _evidence_file(tmp_path, rows):
    p = tmp_path / "face_manifest.json"
    p.write_text(json.dumps(rows))
    return p


def _real_face():
    """A real resolved face, so the join runs on a genuine sha256."""
    _, path = cfa._regular_face()
    return path


def test_the_producer_cap_is_enforced_by_enumeration_over_the_app_enum():
    # §BH13(a): "The cap test must prove the producer cannot emit any state
    # above the ceiling, by enumeration against the app enum, not by
    # convention." So this drives THE PRODUCER with every member of the app
    # enum rather than calling the guards directly — which would only prove the
    # guards work, not that the producer routes through them.
    row = _evidence_row(FIXTURE_SHA)
    assert set(cfa.VERIFICATION_CEILING) == SIX_STATES     # enum is the app's
    for state in SIX_STATES:
        if cfa.VERIFICATION_CEILING[state] == cfa.ABOVE_CEILING:
            with pytest.raises(cfa.FontStateAboveCeiling):
                cfj._confirmation(row, verification=state)
        else:
            assert cfj._confirmation(row, verification=state)["verification"] \
                == state
    for src in cfa.SOURCE_CEILING:
        if cfa.SOURCE_CEILING[src] == cfa.ABOVE_CEILING:
            with pytest.raises(cfa.FontStateAboveCeiling):
                cfj._confirmation(row, source=src)
        else:
            assert cfj._confirmation(row, source=src)["provenance"] == src
    # a state outside the enum is a DIFFERENT refusal, so the test above proves
    # which one fired rather than merely that something was raised
    for unknown in ("INVENTED_STATE", "VERIFIED", "", None):
        with pytest.raises(ValueError):
            cfj._confirmation(row, verification=unknown)
        with pytest.raises(ValueError):
            cfj._confirmation(row, source=unknown)


def test_the_producers_declared_states_sit_at_or_below_both_ceilings():
    assert cfj.JOIN_VERIFICATION == cfa.LICENCE_REVIEW_REQUIRED   # §BH12(a)
    assert cfa.VERIFICATION_CEILING[cfj.JOIN_VERIFICATION] \
        == cfa.AT_OR_BELOW_CEILING
    assert cfa.SOURCE_CEILING[cfj.JOIN_SOURCE] == cfa.AT_OR_BELOW_CEILING
    assert cfj.JOIN_VERIFICATION not in cfa.MACHINE_FORBIDDEN_VERIFICATIONS
    assert cfj.JOIN_SOURCE not in cfa.MACHINE_FORBIDDEN_SOURCES


def test_a_face_that_joins_yields_a_capped_confirmation(tmp_path):
    path = _real_face()
    if not path:
        return
    sha = cfa.extract_identity(path)["sha256"]
    ev = _evidence_file(tmp_path, [_evidence_row(sha, ps="Joined-Regular")])
    out = cfj.join_font_evidence([("regular", path)], evidence_path=ev)
    assert out["evidence_status"] == cfj.EVIDENCE_READ
    assert out["faces"][0]["outcome"] == cfj.FACE_JOINED
    conf = out["confirmed_fonts"]["regular"]
    assert conf["verification"] == cfa.LICENCE_REVIEW_REQUIRED
    assert conf["provenance"] == cfa.SOURCE_MACHINE_DERIVED


def test_a_face_that_does_not_join_yields_NOTHING(tmp_path):
    # §BH15(b): "No per-face claim is made while the joined set is empty — not
    # UNVERIFIED-dressed-as-progress, nothing." So the role is ABSENT from the
    # mapping, not present carrying a hedged state.
    path = _real_face()
    if not path:
        return
    ev = _evidence_file(tmp_path, [_evidence_row(FIXTURE_SHA)])
    out = cfj.join_font_evidence([("regular", path)], evidence_path=ev)
    assert out["faces"][0]["outcome"] == cfj.FACE_NO_MATCH
    assert out["confirmed_fonts"] == {}
    assert "regular" not in out["confirmed_fonts"]
    # NEGATIVE CONTROL — the same call with a MATCHING row does yield, so the
    # empty mapping above is a measurement and not a producer that never emits
    sha = cfa.extract_identity(path)["sha256"]
    matching = tmp_path / "matching"
    matching.mkdir()
    ev2 = _evidence_file(matching, [_evidence_row(sha)])
    assert cfj.join_font_evidence([("regular", path)],
                                  evidence_path=ev2)["confirmed_fonts"]


def test_absent_evidence_is_distinguishable_from_a_real_no_match(tmp_path):
    # Both yield {}. If that were the only signal, "I could not look" would be
    # indistinguishable from "I looked and found nothing" — and the artifact is
    # absent by default in any clean clone, so this is the DEFAULT case.
    path = _real_face()
    if not path:
        return
    missing = tmp_path / "nope" / "face_manifest.json"
    absent = cfj.join_font_evidence([("regular", path)], evidence_path=missing)
    present = cfj.join_font_evidence(
        [("regular", path)],
        evidence_path=_evidence_file(tmp_path, [_evidence_row(FIXTURE_SHA)]))
    assert absent["confirmed_fonts"] == present["confirmed_fonts"] == {}
    assert absent["evidence_status"] == cfj.EVIDENCE_ABSENT
    assert present["evidence_status"] == cfj.EVIDENCE_READ
    assert absent["rows_considered"] == 0 and present["rows_considered"] == 1


def test_the_producer_grants_no_licence_and_names_no_human(tmp_path):
    # §BH12(a): "No licence is granted because none exists to grant... reading
    # the OFL is my act, not code's."
    path = _real_face()
    if not path:
        return
    sha = cfa.extract_identity(path)["sha256"]
    ev = _evidence_file(tmp_path, [_evidence_row(sha)])
    conf = cfj.join_font_evidence(
        [("regular", path)], evidence_path=ev)["confirmed_fonts"]["regular"]
    for field in ("licence_id", "licence_evidence", "approved_by",
                  "approved_at", "redistribution_status",
                  "production_use_status"):
        assert field not in conf
    # and the seam's conservative defaults therefore stand
    auth = cfa.build_font_authority(_doc(), confirmed_fonts={"regular": conf})
    face = next(f for f in auth["faces"] if f["role"] == "regular")
    assert face["licence_id"] == "" and face["approved_by"] == ""
    assert face["redistribution_status"] == "UNVERIFIED"
    assert face["production_use_status"] == "UNVERIFIED"


def test_the_producer_cannot_silence_any_gate_code(tmp_path):
    # The safety property that matters: feeding the join's own output through
    # the seam must never REDUCE the gate codes. A machine join declares
    # MACHINE_DERIVED, which is below the ceiling and so outside
    # SOURCES_CLEARING_FALLBACK — the fallback finding survives the join.
    path = _real_face()
    if not path:
        return
    sha = cfa.extract_identity(path)["sha256"]
    ev = _evidence_file(tmp_path, [_evidence_row(sha)])
    produced = cfj.join_font_evidence([("regular", path)],
                                      evidence_path=ev)["confirmed_fonts"]
    assert produced                                   # the join really fired
    doc = _doc()
    before = set(cfa.font_confirmation_gate(cfa.build_font_authority(doc)))
    after = set(cfa.font_confirmation_gate(
        cfa.build_font_authority(doc, confirmed_fonts=produced)))
    assert before <= after
    assert cfa.FONT_FALLBACK_DETECTED in after
    assert all(f["source"] == cfa.SOURCE_MACHINE_DERIVED
               and f["is_fallback"] is True
               for f in cfa.build_font_authority(
                   doc, confirmed_fonts=produced)["faces"]
               if f["role"] == "regular")


# --- §BH12(b) BUILD D — the seam's guard ------------------------------------
# "The four-case probe becomes its tests — the bare-claim case must go red
# before the guard and green after refusing it." The probe is §BH13(g)'s, and
# its SHAPE is load-bearing: a REAL font file present and no `postscript_name`,
# so neither of `_face_record`'s downgrades can fire. §BH13(g) records that the
# first probe of this question asked with `path=None`, the file_present
# downgrade rewrote every bad value to FONT_FILE_MISSING, and the result read as
# "the seam checks its input" — the opposite of the truth. These tests inherit
# the corrected shape, and `_guarded_face()` below is where it is fixed once.


def _guarded_face():
    """The probe's shape: a real file, so no downgrade can mask the answer."""
    _, path = cfa._regular_face()
    return path


def test_the_seam_refuses_a_state_from_outside_its_own_vocabulary():
    path = _guarded_face()
    if not path:
        return
    # the four bad values §BH13(g) measured stored VERBATIM before this guard
    for bad in ("TOTALLY_INVENTED_STATE",      # never in any vocabulary
                "LICENSE_APPROVED",            # dip0c HUMAN_ONLY, borrowed
                "licence_review_required",     # the ceiling in lower case
                ""):                           # a declared nothing
        with pytest.raises(ValueError):
            cfa._face_record(role="regular", name="NotoSans", path=path,
                             confirmed={"verification": bad})


def test_an_absent_verification_key_is_not_a_refusal():
    # the control that keeps the test above honest: the guard must refuse a
    # DECLARED bad state, not the mere act of confirming. An omitted key keeps
    # its conservative default, which grants nothing and so needs no refusal.
    path = _guarded_face()
    if not path:
        return
    rec = cfa._face_record(role="regular", name="NotoSans", path=path,
                           confirmed={"path": path})
    assert rec["verification"] == cfa.LICENCE_REVIEW_REQUIRED


def test_the_seam_refuses_verified_for_production_outright():
    # §BH13(b): "the guard refuses VERIFIED_FOR_PRODUCTION OUTRIGHT. No
    # owner-confirmation exception branch is built until Option C lands...
    # refusal is total for now." OUTRIGHT is the word under test: the second
    # case declares the strongest provenance the vocabulary has and is refused
    # just the same, so this proves total refusal rather than a machine-only cap.
    path = _guarded_face()
    if not path:
        return
    for conf in ({"verification": cfa.VERIFIED_FOR_PRODUCTION},
                 {"verification": cfa.VERIFIED_FOR_PRODUCTION,
                  "provenance": cfa.SOURCE_USER_CONFIRMED}):
        with pytest.raises(cfa.FontStateAboveCeiling):
            cfa._face_record(role="regular", name="NotoSans", path=path,
                             confirmed=conf)
    # and the state one below it is NOT refused here. §BH12(b)/§BH13(b) name
    # only VERIFIED_FOR_PRODUCTION, and APPROVED_FOR_CONCEPT_ONLY is measured
    # not to clear the gate anyway, so refusing it too would go wider than the
    # sentence. It is above the ceiling for a MACHINE and admissible at the
    # seam, which is the two questions staying distinct rather than an oversight.
    rec = cfa._face_record(role="regular", name="NotoSans", path=path,
                           confirmed={"verification":
                                      cfa.APPROVED_FOR_CONCEPT_ONLY})
    assert rec["verification"] == cfa.APPROVED_FOR_CONCEPT_ONLY
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa.machine_writable_verification(cfa.APPROVED_FOR_CONCEPT_ONLY)


def test_the_seam_refuses_a_licence_claim_carrying_no_evidence():
    # THE BARE-CLAIM CASE §BH12(b) names: "a licence claim arriving without
    # evidence is refused", red before this guard and green after. Every one of
    # the five claim-bearing fields was measured stored verbatim beforehand.
    path = _guarded_face()
    if not path:
        return
    for field, claim in (("licence_id", "OFL-1.1"),
                         ("redistribution_status", "GRANTED"),
                         ("production_use_status", "GRANTED"),
                         ("approved_by", "somebody"),
                         ("approved_at", "2026-08-31")):
        with pytest.raises(cfa.UnfoundedLicenceClaim):
            cfa._face_record(role="regular", name="NotoSans", path=path,
                             confirmed={field: claim})
    # the census is asserted rather than assumed, so a sixth claim-bearing field
    # added later cannot join the record without joining this test
    assert set(cfa.LICENCE_CLAIM_DEFAULTS) == {
        "licence_id", "redistribution_status", "production_use_status",
        "approved_by", "approved_at"}


def test_evidence_admits_the_very_claim_that_was_refused_without_it():
    # The negative control that gives the test above its power. Without this,
    # "refused" would be consistent with a guard that simply bans the field —
    # and a guard that never admits anything proves nothing about EVIDENCE.
    # Same field, same value, one difference.
    path = _guarded_face()
    if not path:
        return
    for field, claim in (("licence_id", "OFL-1.1"),
                         ("production_use_status", "GRANTED")):
        with pytest.raises(cfa.UnfoundedLicenceClaim):
            cfa._face_record(role="regular", name="NotoSans", path=path,
                             confirmed={field: claim})
        rec = cfa._face_record(
            role="regular", name="NotoSans", path=path,
            confirmed={field: claim, "licence_evidence": "docs/OFL.txt"})
        assert rec[field] == claim
        assert rec["licence_evidence"] == "docs/OFL.txt"
    # and a field sitting AT its conservative default is not a claim at all,
    # so it needs no evidence — the guard reads what is asserted, not what is
    # present. Evidence is still not approval: the face stays a fallback and
    # the gate still speaks.
    rec = cfa._face_record(role="regular", name="NotoSans", path=path,
                           confirmed={"licence_id": "",
                                      "production_use_status": "UNVERIFIED"})
    assert rec["licence_id"] == ""


def test_the_three_refusals_stay_disjoint_so_a_test_can_prove_which_fired():
    # The module states this discipline for its own two guards; the third
    # refusal joins it rather than collapsing into ValueError, which would make
    # "unknown state" and "unfounded claim" indistinguishable to any caller.
    assert not issubclass(cfa.UnfoundedLicenceClaim, ValueError)
    assert not issubclass(cfa.UnfoundedLicenceClaim, cfa.FontStateAboveCeiling)
    assert not issubclass(cfa.FontStateAboveCeiling, cfa.UnfoundedLicenceClaim)
    path = _guarded_face()
    if not path:
        return
    with pytest.raises(cfa.UnfoundedLicenceClaim):
        cfa._face_record(role="regular", name="NotoSans", path=path,
                         confirmed={"licence_id": "OFL-1.1"})
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa._face_record(role="regular", name="NotoSans", path=path,
                         confirmed={"verification": cfa.VERIFIED_FOR_PRODUCTION})


def test_the_producer_still_passes_the_guard_it_now_has_to_pass(tmp_path):
    # The guard lands one commit after the producer, so the producer's output is
    # its first real subject. It claims no licence and declares a state at the
    # ceiling, so it passes — and if a future change made it claim one, this
    # goes red rather than the claim going quietly into a record.
    _, path = cfa._regular_face()
    if not path:
        return
    sha = cfa.extract_identity(path)["sha256"]
    ev = _evidence_file(tmp_path, [_evidence_row(sha)])
    produced = cfj.join_font_evidence([("regular", path)],
                                      evidence_path=ev)["confirmed_fonts"]
    assert produced
    for conf in produced.values():
        assert cfa.guarded_confirmation(conf) is conf


# ---- §BH32(d)(ii): the Arabic face is routed through the confirmed-font seam.

def _arabic_doc():
    bb = build_backbone(ContainerProfile(archetype="bottle", height_mm=110,
                                         width_mm=40))
    zones = cc.propose_zones(cc.build_inferred_profile("bottle"))
    return compose_container_graph(bb, product_name="رحيق الورد",
                                   name_lines=["رحيق الورد", "ROSE NECTAR"],
                                   zones=zones, native=True)


def _legacy_arabic_doc():
    """§BH48(a): the untagged copy — the composition is lifted, so only an untagged document still
    resolves as at 41604ac; the legacy expectations below hold on it, the live ones on the tagged."""
    from apps.ire.font_roles import SURFACE_KEY
    doc = _arabic_doc()
    doc.metadata = {k: v for k, v in (doc.metadata or {}).items() if k != SURFACE_KEY}
    return doc


def test_an_rtl_run_puts_the_arabic_face_into_the_record():
    faces, _ = cfa._resolved_faces(_legacy_arabic_doc())
    roles = [r for r, _, _ in faces]
    assert roles == ["bold", "regular", "arabic"]
    name, path = next((n, p) for r, n, p in faces if r == "arabic")
    assert name == "NotoNaskhArabic"
    assert path and path.endswith("static/fonts/NotoNaskhArabic-Regular.ttf")
    auth = cfa.build_font_authority(_legacy_arabic_doc())
    ar = next(f for f in auth["faces"] if f["role"] == "arabic")
    assert ar["postscript_name"] == "NotoNaskhArabic-Regular"
    assert ar["sha256"] == "6f0a92031367b2f5a2078fe9d24f3433122b61a0bad57c423aad8f3c39aa2e6e"
    assert ar["file_identity"]
    # §BH48(a): the LIVE composition resolves through the theme — the Arabic role is the layer's
    # arabic-display (Naskh, the §BH33(1) chain), the Latin roles the theme's Poppins
    live = {f["role"]: f["postscript_name"] for f in cfa.build_font_authority(_arabic_doc())["faces"]}
    assert list(live) == ["bold", "regular", "arabic-display"]
    assert live["bold"] == "Poppins-Light" and live["regular"] == "Poppins-Regular"
    assert live["arabic-display"] == "NotoNaskhArabic-Regular"


def test_the_arabic_face_verifies_through_the_channel_on_the_seam():
    from apps.ire.container_font_owner_grant import apply_owner_grant
    auth = apply_owner_grant(cfa.build_font_authority(_legacy_arabic_doc()))
    by_role = {f["role"]: f for f in auth["faces"]}
    assert by_role["arabic"]["verification"] == cfa.VERIFIED_FOR_PRODUCTION
    assert by_role["arabic"]["source"] == cfa.SOURCE_USER_CONFIRMED
    assert by_role["arabic"]["is_fallback"] is False
    assert auth["all_production_verified"] is True
    assert cfa.font_confirmation_gate(auth) == []


def test_a_latin_only_document_records_exactly_the_two_roles_as_before():
    faces, _ = cfa._resolved_faces(_doc())
    assert [r for r, _, _ in faces] == ["bold", "regular"]
    assert [f["role"] for f in cfa.build_font_authority(_doc())["faces"]] == ["bold", "regular"]


def test_the_join_keys_the_arabic_role_when_the_document_has_one():
    from apps.ire.container_font_evidence_join import join_document_fonts
    result = join_document_fonts(_legacy_arabic_doc())
    assert [r["role"] for r in result["faces"]] == ["bold", "regular", "arabic"]
    # §BH48(a): on the lifted surface the join keys the layer's role
    assert [r["role"] for r in join_document_fonts(_arabic_doc())["faces"]] == ["bold", "regular", "arabic-display"]


# ---- §BH32(e)/(h): on a NON-exempt surface the record is what the layer resolved; (h)(3) skipped candidates.

def _themed_arabic_doc():
    from apps.ire.font_roles import NON_EXEMPT_EXERCISE, SURFACE_KEY
    doc = _arabic_doc()
    doc.metadata = dict(doc.metadata, **{SURFACE_KEY: NON_EXEMPT_EXERCISE})
    return doc


def test_a_non_exempt_record_carries_the_theme_faces_the_layer_resolved():
    from apps.ire.container_font_owner_grant import apply_owner_grant
    auth = apply_owner_grant(cfa.build_font_authority(_themed_arabic_doc()))
    by_role = {f["role"]: f["postscript_name"] for f in auth["faces"]}
    assert list(by_role) == ["bold", "regular", "arabic-display"]
    assert by_role["bold"] == "Poppins-Light"           # display default (bold alias)
    assert by_role["regular"] == "Poppins-Regular"      # body default (regular alias)
    assert by_role["arabic-display"] == "NotoNaskhArabic-Regular"   # the §BH33(1) default, first try
    assert all(f["verification"] == cfa.VERIFIED_FOR_PRODUCTION for f in auth["faces"])
    assert auth["all_production_verified"] is True and cfa.font_confirmation_gate(auth) == []
    # §BH33(1): nothing is skipped ahead of Naskh — Cairo-Bold left every
    # Arabic chain; the skipped-candidate contract is proved on the void grant below
    assert auth["skipped_candidates"] == []
    # §BH48(a): the UNTAGGED composition beside it records exactly as at 41604ac (the tagged one is lifted)
    legacy = cfa.build_font_authority(_legacy_arabic_doc())
    assert [f["role"] for f in legacy["faces"]] == ["bold", "regular", "arabic"]
    assert legacy["skipped_candidates"] == []


def test_a_refused_role_on_a_non_exempt_surface_is_recorded_with_no_file_and_the_gate_fires(monkeypatch):
    from apps.ire import font_roles as FR
    monkeypatch.setitem(FR.CHAINS, "arabic-display", ())
    FR.reset_cache()
    try:
        auth = cfa.build_font_authority(_themed_arabic_doc())
        ar = next(f for f in auth["faces"] if f["role"] == "arabic-display")
        assert ar["file_identity"] == "" and ar["sha256"] == ""
        assert ar["verification"] != cfa.VERIFIED_FOR_PRODUCTION
        assert auth["all_production_verified"] is False
        assert cfa.font_confirmation_gate(auth)          # the gate fires on the refusal
    finally:
        FR.reset_cache()


def test_a_skipped_candidate_is_carried_in_the_record_at_its_honest_state(monkeypatch):
    """§BH32(h)(3): a void candidate is SKIPPED by the chain — the render falls
    back to the next verified face — and the record carries the skipped one
    at its honest state with the named code. The channel's own tests are
    untouched; this is the production record's contract."""
    from apps.ire import font_roles as FR
    from apps.ire.container_font_owner_grant import apply_owner_grant
    import apps.ire.container_font_owner_grant as cfg
    poppins_light = FR.catalogue()["Poppins-Light"]["sha256"]
    voided = tuple(dict(g, licence_evidence_sha256="0" * 64) if poppins_light in g["face_sha256s"] else g
                   for g in cfg.OWNER_GRANTS)
    monkeypatch.setattr(cfg, "OWNER_GRANTS", voided)
    FR.reset_cache()
    try:
        auth = apply_owner_grant(cfa.build_font_authority(_themed_arabic_doc()))
        bold = next(f for f in auth["faces"] if f["role"] == "bold")
        assert bold["postscript_name"] == "Poppins-Regular"          # the render fell back
        assert bold["verification"] == cfa.VERIFIED_FOR_PRODUCTION
        skipped = [s for s in auth["skipped_candidates"] if s["role"] == "display"]
        assert skipped and skipped[0]["stem"] == "Poppins-Light"
        assert skipped[0]["verification"] == cfa.LICENCE_REVIEW_REQUIRED   # its honest state: the void path
        assert skipped[0]["skipped_code"] == FR.SKIPPED_CODE
        assert skipped[0]["sha256"] == poppins_light
        assert cfa.font_confirmation_gate(auth) == []                 # what rendered verified
    finally:
        FR.reset_cache()


# ---- §BH33(2): a variable face's row names the pinned instance; the granted file verifies.

def test_a_variable_face_row_names_the_pinned_instance_and_hashes_the_granted_file():
    from apps.ire import font_roles as FR
    from apps.ire.container_font_owner_grant import apply_owner_grant
    from apps.ire.graph import Color, TextRun
    doc = _doc()
    doc.metadata = dict(doc.metadata, **{FR.SURFACE_KEY: FR.NON_EXEMPT_EXERCISE})
    doc.root.children.append(TextRun(name="h", text="HYDRATING", x=10, y=80, font="heading",
                                     size_pt=9, color=Color(r=0.2, g=0.1, b=0.15)))
    auth = apply_owner_grant(cfa.build_font_authority(doc))
    row = next(f for f in auth["faces"] if f["role"] == "heading")
    granted = FR.catalogue()["Montserrat[wght]"]
    assert row["postscript_name"] == "Montserrat-Bold"                 # what the artefact embeds
    assert row["font_style"] == "Bold"
    assert row["sha256"] == granted["sha256"]                          # what the owner granted
    assert row["file_identity"] == granted["path"]
    assert row["verification"] == cfa.VERIFIED_FOR_PRODUCTION and row["source"] == cfa.SOURCE_USER_CONFIRMED
    inst = row["instance"]
    assert inst["postscript_name"] == "Montserrat-Bold" and inst["axes"] == {"wght": 700.0}
    assert inst["derived_from"] == "Montserrat[wght]" and inst["derived_from_sha256"] == granted["sha256"]
    assert inst["source_default_instance"] == "Montserrat-Thin"
    assert inst["sha256"] != granted["sha256"] and inst["path"] != granted["path"]
    assert auth["all_production_verified"] is True and cfa.font_confirmation_gate(auth) == []
    # rows of static faces carry no instance; an exempt record is exactly as at 41604ac
    assert all("instance" not in f for f in auth["faces"] if f["role"] != "heading")
    assert all("instance" not in f for f in cfa.build_font_authority(_doc())["faces"])
    # the seam's (role, name, path) hands the GRANTED path to the record builder
    faces, _ = cfa._resolved_faces(doc)
    assert next(p for r, n, p in faces if r == "heading") == granted["path"]


# ---- §BH33(4): the record carries the three Arabic rows distinct, never collapsed.

def _themed_trilingual_doc():
    from apps.ire.graph import Color, TextRun
    rose = Color(r=0.2, g=0.1, b=0.15)
    doc = _themed_arabic_doc()
    doc.root.children.append(TextRun(name="ar-h", text="سيروم مرطب للوجه", x=20, y=70,
                                     font="heading", size_pt=8, color=rose))
    doc.root.children.append(TextRun(name="ar-b", text="يوضع قطرتان صباحاً ومساءً", x=20, y=78,
                                     font="body", size_pt=5, color=rose))
    return doc


def test_the_record_carries_the_three_arabic_rows_distinct_never_collapsed(monkeypatch):
    from apps.ire import font_roles as FR
    from apps.ire.container_font_owner_grant import apply_owner_grant
    auth = apply_owner_grant(cfa.build_font_authority(_themed_trilingual_doc()))
    roles = [f["role"] for f in auth["faces"]]
    assert [r for r in roles if r.startswith("arabic")] == ["arabic-display", "arabic-heading", "arabic-body"]
    assert "arabic" not in roles                                   # the collapsed row of (d)(ii) is gone
    by_role = {f["role"]: f for f in auth["faces"]}
    for r in ("arabic-display", "arabic-heading", "arabic-body"):
        # [his goal of 2026-10-06, item 6: "Approve Noto Naskh Arabic Bold ... for Arabic headings"] the heading's row is
        # the granted Bold; the display's and the body's the Regular
        assert by_role[r]["postscript_name"] == ("NotoNaskhArabic-Bold" if r == "arabic-heading"
                                                 else "NotoNaskhArabic-Regular")
        assert by_role[r]["verification"] == cfa.VERIFIED_FOR_PRODUCTION
    assert auth["all_production_verified"] is True and cfa.font_confirmation_gate(auth) == []
    # a future re-ranking to different faces leaves no drawn face off the record:
    # refuse arabic-heading alone — its own row shows the refusal, the other two still name Naskh
    monkeypatch.setitem(FR.CHAINS, "arabic-heading", ())
    FR.reset_cache()
    try:
        auth = apply_owner_grant(cfa.build_font_authority(_themed_trilingual_doc()))
        by_role = {f["role"]: f for f in auth["faces"]}
        assert by_role["arabic-heading"]["sha256"] == "" and by_role["arabic-heading"]["verification"] != cfa.VERIFIED_FOR_PRODUCTION
        assert by_role["arabic-display"]["postscript_name"] == "NotoNaskhArabic-Regular"
        assert by_role["arabic-body"]["postscript_name"] == "NotoNaskhArabic-Regular"
        assert cfa.font_confirmation_gate(auth)                       # the gate fires on the refused row
    finally:
        FR.reset_cache()
    # §BH48(a): the UNTAGGED composition beside it records exactly as at 41604ac (the tagged one is lifted)
    assert [f["role"] for f in cfa.build_font_authority(_legacy_arabic_doc())["faces"]] == ["bold", "regular", "arabic"]
