#!/bin/zsh
# A137 — the commit path cannot swallow an exit code.
#
# The 1q shape at the shell layer: a pipeline that, given a failure it
# could not represent, produced a plausible success instead of raising
# (a716c30 briefly existed with a red suite because `pytest | tail`
# reported tail's exit code). This script is the only sanctioned commit
# path for suite-gated commits: the suite's TRUE exit code is written
# to an artifact and the commit decision reads the artifact — never a
# pipeline's tail.
#
# Usage: tools/guarded_commit.sh [--dry-run] -m <msg> [paths...]
#   SUITE_CMD overrides the suite command (tests use it to force red).
set -e -u -o pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    shift
fi

SUITE_CMD_DEFAULT="venv/bin/python -m pytest apps/pipeline/tests/test_palette_statistics.py apps/pipeline/tests/test_characterization_protocol.py -q"
SUITE_CMD_OVERRIDDEN=0
if [[ -n "${SUITE_CMD:-}" ]]; then
    SUITE_CMD_OVERRIDDEN=1
fi
SUITE_CMD="${SUITE_CMD:-${SUITE_CMD_DEFAULT}}"
# Redirectable so the script's OWN tests stop clobbering the artifact a
# concurrently running real gate is about to read at line 133 — the same
# A137 shape this script exists to close, reintroduced by the tests that
# check it. The default is unchanged, so every real commit still writes
# and reads .suite_gate_result.
ARTIFACT="${SUITE_GATE_ARTIFACT:-.suite_gate_result}"

# §BB7(g)(c) — the same treatment for the two OUTPUT files, which the fix
# above did not cover. Measured at 8e47f6f while a real gate was mid-flight:
# the nested --dry-run in GuardedCommitTests truncated .suite_gate_output
# from 198 bytes to 0 and replaced .record_integrity_output's 74 bytes with
# 250 bytes reporting a /var/folders temp ledger. The running gate's own
# evidence, destroyed by a test inside that gate's own suite.
#
# .reserved_copy_output and .brand_strings_output were written by the nested
# run too and were measured byte-IDENTICAL, so they lost nothing THEN — a
# property of those two tools' output being run-independent, not a property of
# this script. §BH55 Phase 4 closes the class rather than the instance: all
# FOUR output files are redirectable now, by the same pattern, so no nested run
# can overwrite a live gate's evidence even if a tool's output starts to vary.
SUITE_OUTPUT="${SUITE_GATE_OUTPUT:-.suite_gate_output}"
INTEGRITY_OUTPUT="${RECORD_INTEGRITY_OUTPUT:-.record_integrity_output}"
RESERVED_OUTPUT="${RESERVED_COPY_OUTPUT:-.reserved_copy_output}"
STRINGS_OUTPUT="${BRAND_STRINGS_OUTPUT:-.brand_strings_output}"

# A315/3l — DECLARED EXTENT, asserted before the exit code is honoured.
#
# The defect this closes (SILENT_EXTENT_LOSS, A316): a check whose
# failure mode is collecting nothing, read through a channel that
# cannot represent the difference between "ran and passed" and "did
# not run". test_characterization_protocol.py was zero bytes for the
# 3h, 3i and 3j nodes; pytest collects nothing from an empty file and
# exits 0, so this gate reported success over part of its declared
# coverage. The header above was right about the danger
# and wrong about where it lived: it guarded against the suite lying,
# not against the suite being absent.
#
# A count alone will not do it (2p: a count without an enumeration is
# not a declaration). "At least N" is satisfied by N tests from the
# wrong targets — the surviving target alone
# would have cleared any plausible floor.
#
# WI-3G/§AJ — the floors are the MEASURED extents, not historical ones.
# test_characterization_protocol.py declared 28 and collected 53: the
# gate that exists because this file once went to ZERO BYTES would have
# tolerated losing 25 of its 53 tests without a word. A stale floor is
# SILENT_EXTENT_LOSS one notch down — it does not fail to count, it
# counts against a number that stopped being true. Measured 2026-08-20:
# 49 and 59 (59 = 53 + the six §AJ3 compressed-record tests).
#
# §AR2/WI-3J — THIS IS THE SECOND OF TWO COPIES OF THESE NUMBERS. The
# other lives in suite_file_manifest.json's tier1_floors and is the one
# TIER_2 reads. §AJ above repaired this copy at WI-3G and left the JSON
# saying 28 against a measured 59, for eight days, in the gate that
# exists because this very file once went to zero bytes.
#
# The duplication is NOT eliminated here, deliberately. TIER_1 runs
# BEFORE tier2_gate's A352-repair-3 digest check, so a TIER_1 that read
# the manifest directly would trust an unverified file and an edited
# manifest could lower this floor. Two copies with an enforced agreement
# is the smaller risk; one copy read from an unverified source is a
# bypass. What closes §AR2 is therefore a test rather than a refactor:
# ExtentFloorsAreMonotonic::test_the_two_copies_of_the_tier1_floors_agree
# fails if this array ever falls below the manifest again.
# 49 -> 50: dab25db added test_the_real_ledger_and_artifact_are_left_alone to
# GuardedCommitTests and did not raise this copy. The guard on line 72 did not
# fire, because the manifest was stale at 49 as well -- two copies agreeing on
# the same wrong number is exactly the failure §AR2 describes, and it stayed
# invisible for two commits until a manifest regeneration recounted from disk.
# Both are now 50, and 50 is what pytest --collect-only reports for that file.
#
# 50 -> 51: 4cda10f (the C4 ledger repair) added a test and DID raise this
# copy -- the maintenance the docstring describes, working as designed. THE
# SENTENCE DIRECTLY ABOVE IS LEFT STANDING AND IS NOW FALSE IN BOTH HALVES:
# this array says 51, and pytest --collect-only reports 51 for that file
# (measured 2026-08-24, 51 + 66 = 117 for the pair). The MANIFEST copy still
# says 50 and will until the next regeneration. Nothing fired, correctly: the
# §AR2 assertion is one-directional on purpose, and shell-above-manifest is
# the safe direction -- it refuses earlier rather than losing coverage.
#
# WHAT THAT COST, RECORDED WHERE THE NUMBER LIVES RATHER THAN ONLY IN PROSE
# TWO DIRECTORIES UP. f1b9247's message says "tier1 floors 50 and 66" without
# naming a copy, and the prediction it was checked against said the same. 50
# is the manifest's, 51 is this one's, THIS ONE IS WHAT GATES, and 51 is what
# pytest counts. Both numbers are real, which is the whole trap -- the same
# shape as protocol_identity's two correct answers: a lookup that returns a
# plausible value of the right type does not announce that it read the wrong
# copy. A prediction naming one of two copies must say WHICH.
#
# 2026-08-27, §BC(h)/C10: THE PREDICTION ABOVE CLOSED AND THIS ARRAY DID NOT
# MOVE. "The MANIFEST copy still says 50 and will until the next regeneration"
# was written on 2026-08-24; adding test_c10_mark_width.py forced a
# regeneration, the recount from disk read 51 for this file, and the manifest
# now says 51 too. Both copies agree for the first time since 4cda10f. The
# sentence above is left standing rather than corrected in place: it was a
# falsifiable prediction about a future event, and editing it now would leave a
# later reader nothing to score it against. Nothing fired in the interval,
# which is the one-directional guard behaving as line 87 says it should.
#
# A365 CAUGHT THE FIRST DRAFT OF THIS VERY NOTE. It closed on an absolute about
# future behaviour — one of the seven phrases in claim_scan.py's FORBIDDEN
# tuple, sitting in instrument prose, inside the paragraph congratulating
# itself on falsifiability. The gate refused and the sentence above is the
# rewrite. Recorded rather than quietly reworded, because the guard found it in
# the one place its author was least likely to look.
#
# THE SECOND REFUSAL IS THE MORE USEFUL ONE AND IS WHY THIS NOTE PARAPHRASES.
# The first attempt to record the finding QUOTED the offending phrase, and the
# scanner refused again — twice, once for the quotation and once for naming the
# pattern it matched. The scan joins prose and matches substrings; it has no
# notion of quotation, so a note about a refusal may not contain the text that
# was refused. That is a real limit of this instrument, it is stated here as a
# condition rather than as a complaint, and the cost is one paraphrase.
#
# 51 -> 52: the §BB7(g)(c) output-redirect guard
# (test_the_real_output_files_are_left_alone) is added to GuardedCommitTests,
# and THIS COPY IS RAISED IN THE SAME COMMIT — which is precisely what
# dab25db did not do on line 88 for the sibling guard. Measured, not assumed:
# `pytest --collect-only -q` reports 52 for this file and 66 for the other.
# The MANIFEST copy stays 51 until a regeneration, and nothing fires, because
# --check --commit does not regenerate (tier2_gate.py:267 gates that on
# --regenerate-manifest alone) and shell-above-manifest is the safe direction
# per line 101. The pinned protocol_identity does not move either: it hashes
# the EXTENT_DIGESTS literal in palette_powder_protocol.py:2065, not the
# manifest file.
EXPECTED_TARGETS=(
    "apps/pipeline/tests/test_palette_statistics.py:52"
    "apps/pipeline/tests/test_characterization_protocol.py:66"
)

assert_declared_extent() {
    # The four clauses live in tools/extent_gate.py: the shell this gate
    # runs under does not reliably have grep/sed/sort on PATH, and an
    # extent check that silently fails to count is the defect it exists
    # to close. Discovered by making this gate refuse (A319), not by
    # reading it.
    venv/bin/python tools/extent_gate.py --suite "${SUITE_CMD}" -- "${EXPECTED_TARGETS[@]}"
}

# The script's own tests force a red suite through SUITE_CMD, and the
# declared extent belongs to the DEFAULT command. But overriding
# SUITE_CMD must NOT by itself turn the assertion into an echo: A315
# says REFUSE is non-zero exit and no commit, not a warning, and one
# environment variable that downgrades a refusal to a stderr line is
# the same defect one level up. The opt-out must be NAMED, separately
# and deliberately.
EXTENT_ASSERTED="NO"
if (( SUITE_CMD_OVERRIDDEN )); then
    if [[ "${EXTENT_ASSERTION_OPT_OUT:-}" == "1" ]]; then
        # A328 — the opt-out is COUNTED, not merely recorded, and every
        # use names its reason. An opt-out exercised routinely is an
        # unproven gate wearing a proven gate's record. Expected count
        # per node is ZERO; nonzero is a finding, not a footnote.
        if [[ -z "${EXTENT_ASSERTION_OPT_OUT_REASON:-}" ]]; then
            echo "GUARDED_COMMIT_REFUSED: the opt-out requires a named " \
                 "reason (EXTENT_ASSERTION_OPT_OUT_REASON)" >&2
            exit 1
        fi
        EXTENT_ASSERTED="SKIPPED_BY_NAMED_OPT_OUT"
        venv/bin/python tools/opt_out_log.py \
            "${EXTENT_ASSERTION_OPT_OUT_REASON}" "${DRY_RUN}"
        echo "EXTENT_ASSERTION_SKIPPED_BY_NAMED_OPT_OUT" >&2
    else
        echo "GUARDED_COMMIT_REFUSED: SUITE_CMD is overridden but " \
             "EXTENT_ASSERTION_OPT_OUT is not set. Overriding the suite " \
             "does not waive the declared extent (A315/3l)." >&2
        exit 1
    fi
else
    assert_declared_extent
    EXTENT_ASSERTED="YES"
fi

# §BH40(d) — THE BRAIN'S REBUILD, before the suite, in the ledger-append
# idiom: its own output artifact, its TRUE exit code honoured, a failing
# rebuild refuses the commit. tools/brain sits beside this script (moved from
# the GIT root by the clean-up of 2026-10-04, ending that two-roots trap); it
# regenerates the git-ignored var/brain/ at the GIT root,
# index and the freshness record the apps-leg gate test compares against
# the sources on disk. Run ONLY when SUITE_CMD is not overridden — the same
# condition TIER_2 runs under — so the nested --dry-run inside this script's
# own tests never rebuilds var/brain/ underneath a running gate (the
# §BB7(g)(c) output-clobber class, one level up). Diagnostic runs that
# override SUITE_CMD skip the rebuild and the freshness test alike.
BRAIN_OUTPUT="${BRAIN_REBUILD_OUTPUT:-.brain_rebuild_output}"
BRAIN_REBUILT="NOT_RUN_SUITE_CMD_OVERRIDDEN"
if (( ! SUITE_CMD_OVERRIDDEN )); then
    set +e
    venv/bin/python "${0:A:h}/brain/rebuild.py" > "${BRAIN_OUTPUT}" 2>&1
    BRAIN_RC=$?
    set -e
    if [[ "${BRAIN_RC}" != "0" ]]; then
        echo "GUARDED_COMMIT_REFUSED: brain rebuild failed (§BH40(d)); output ${BRAIN_OUTPUT} tail:" >&2
        tail -5 "${BRAIN_OUTPUT}" >&2
        exit 1
    fi
    BRAIN_REBUILT=$(tail -1 "${BRAIN_OUTPUT}")
    echo "${BRAIN_REBUILT}"
fi

# run the suite with NO pipe on its exit path; capture the true code
set +e
${=SUITE_CMD} > "${SUITE_OUTPUT}" 2>&1
SUITE_EXIT=$?
set -e
# A316 one level up: an artifact that records only the exit code cannot
# distinguish a commit whose extent was asserted from one whose extent
# was skipped. extent_asserted is part of the record, not a log line.
print -r -- "{\"suite_exit\": ${SUITE_EXIT}, \"extent_asserted\": \"${EXTENT_ASSERTED}\", \"utc\": \"$(date -u +%FT%TZ)\", \"cmd\": \"${SUITE_CMD}\"}" > "${ARTIFACT}"

# the commit decision reads the ARTIFACT, not the pipeline
GATE=$(sed -n 's/.*"suite_exit": \([0-9][0-9]*\).*/\1/p' "${ARTIFACT}")
if [[ "${GATE}" != "0" ]]; then
    echo "GUARDED_COMMIT_REFUSED: suite_exit=${GATE} (artifact ${ARTIFACT}; output ${SUITE_OUTPUT} tail:)" >&2
    tail -3 "${SUITE_OUTPUT}" >&2
    # A188 — the one-invocation condition, bound mechanically rather
    # than by memory: a registered flake permits exactly one
    # pre-committed re-run, consumed in the register; a second
    # occurrence stops the node.
    set +e
    venv/bin/python tools/flake_gate.py "${SUITE_OUTPUT}"
    FLAKE_RC=$?
    set -e
    exit "${FLAKE_RC}"
fi
# A373/3q — record integrity. The commit path now reads the record set
# it never read, which is why 1636 findings records sat unprotected
# while eight hashed blocks and fourteen defect classes accumulated
# around the code. Protection follows stakes, not execution.
set +e
venv/bin/python tools/record_integrity.py > "${INTEGRITY_OUTPUT}" 2>&1
RECORD_RC=$?
set -e
if [[ "${RECORD_RC}" != "0" ]]; then
    echo "GUARDED_COMMIT_REFUSED: record integrity (A373/3q)" >&2
    head -12 "${INTEGRITY_OUTPUT}" >&2
    exit 1
fi

# §AK/WI-3H — reserved copy, on the same A373/3q principle: protection
# follows STAKES, not execution. §AE2(b) is the highest-stakes category
# the charter names, and its reason is that fabricated regulated copy
# "passes review precisely because it looks like copy" — which is to say
# the failure mode is a HUMAN reading it and seeing nothing wrong. A
# reviewer asked to be the backstop here is being asked to spot a defect
# whose defining property is that it looks correct, so this check runs on
# the commit path and not only in the suite.
set +e
venv/bin/python tools/reserved_copy.py > "$RESERVED_OUTPUT" 2>&1
RESERVED_RC=$?
set -e
if [[ "${RESERVED_RC}" != "0" ]]; then
    echo "GUARDED_COMMIT_REFUSED: reserved copy (§AK/WI-3H)" >&2
    head -12 "$RESERVED_OUTPUT" >&2
    exit 1
fi

# §AV2/§AU5 — brand strings, the §AE2(c) half of the same argument. The
# block above says protection follows STAKES and then protects exactly
# one reserved category. §AU5's clause is not about §AE2(b) at all: "no
# emission carrying a ⟪PROVISIONAL⟫ descriptor reaches print, a proof, or
# any owner-facing artefact." The guard for that was built at 84e0018 and
# wired to nothing — it ran in the suite and on no commit path, which is
# the §AA shape with a green test suite standing in front of it.
#
# The refusal is asymmetric on purpose and that asymmetry is the point: a
# descriptor carrying the ⟪PROVISIONAL⟫ marker PASSES here, because
# ``scan`` drops marked sites before ``check`` ever sees them. What is
# refused is an unmarked fabricated descriptor — a string that looks like
# brand copy, was invented by an executor, and carries nothing to say so.
# That is the same failure mode the block above names: it passes review
# because it looks correct.
set +e
venv/bin/python tools/brand_strings.py > "$STRINGS_OUTPUT" 2>&1
BRAND_RC=$?
set -e
if [[ "${BRAND_RC}" != "0" ]]; then
    echo "GUARDED_COMMIT_REFUSED: brand strings (§AV2/§AU5)" >&2
    head -12 "$STRINGS_OUTPUT" >&2
    exit 1
fi

# A326/3m — TIER_2: the full suite as DECLARED extent. TIER_1's pass is
# the TIER_1 files only; without this, the artifact cannot stop that
# narrow pass being read as the whole suite. AMBER is a distinct value and is NOT a pass: a commit may
# proceed on AMBER, a result may not be cited as full-suite-green on it.
TIER2="NOT_RUN_SUITE_CMD_OVERRIDDEN"
if (( ! SUITE_CMD_OVERRIDDEN )); then
    set +e
    venv/bin/python tools/tier2_gate.py --check --commit > .tier2_gate_output 2>&1
    TIER2_RC=$?
    set -e
    TIER2=$(venv/bin/python -c "import re,sys; t=open('.tier2_gate_output').read(); m=re.search(r'TIER_2=(\w+)',t); print(m.group(1) if m else 'UNREADABLE')")
    cat .tier2_gate_output
    if [[ "${TIER2_RC}" != "0" ]]; then
        echo "GUARDED_COMMIT_REFUSED: TIER_2=${TIER2} (A326/3m)" >&2
        exit 1
    fi
fi

# 3m — the pass carries its EXTENT. A reader who has only the artifact
# must not be able to mistake a narrow pass for a wide one.
print -r -- "{\"suite_exit\": ${SUITE_EXIT}, \"extent_asserted\": \"${EXTENT_ASSERTED}\", \"tier1_extent\": \"${EXPECTED_TARGETS[*]}\", \"tier2\": \"${TIER2}\", \"utc\": \"$(date -u +%FT%TZ)\", \"cmd\": \"${SUITE_CMD}\"}" > "${ARTIFACT}"

# A352 repair 2: overriding SUITE_CMD is a DIAGNOSTIC act. Diagnostic
# runs stay unrestricted; a COMMIT requires the declared suite. This
# removes the bypass without removing the legitimate use, and makes the
# A328 opt-out count structurally zero on the committing path.
if [[ "${EXTENT_ASSERTED}" == "SKIPPED_BY_NAMED_OPT_OUT" && "${DRY_RUN}" != "1" ]]; then
    echo "GUARDED_COMMIT_REFUSED: the extent opt-out is diagnostic only " \
         "and may not commit. Run the declared suite to commit (A352)." >&2
    exit 1
fi
if [[ "${DRY_RUN}" == "1" ]]; then
    echo "GUARDED_COMMIT_DRY_RUN_OK: tier1 green, tier2=${TIER2}, commit not performed"
    exit 0
fi

# THE LEDGER LINE THIS RUN JUST WROTE BELONGS IN THIS RUN'S COMMIT.
# `tools/record_integrity.py`, invoked above, APPENDS to the tracked gate
# ledger — and it runs long after the caller staged, because staging is
# the caller's act and this script only ever ran `git commit` on an index
# it did not build. So every commit through the sanctioned path carried
# the PREVIOUS run's verdict and left its own behind as a working-tree
# modification. The ledger was permanently one run behind, and a clean
# tree was unreachable through this path BY CONSTRUCTION.
#
# Measured, not inferred: 9456e7d contains the 2026-08-22T11:24:55Z line
# while its own 2026-08-24T01:28:50Z line was still unstaged after it.
#
# PLACED HERE ON PURPOSE — after the --dry-run exit, before the commit.
# A dry run must not touch the index. What a dry run appended is not lost
# by that: `git add` stages the whole file, so the next real commit picks
# it up along with its own.
GC_LEDGER="${0:A:h:h}/docs/roadmap/palt_m6/record_gate_ledger.jsonl"
if [[ -n "${RECORD_INTEGRITY_LEDGER:-}" ]]; then
    # This run's append was redirected, so the real file holds nothing
    # from it. Staging it here would commit whatever an unrelated earlier
    # run happened to leave behind, under this commit's message.
    echo "GUARDED_COMMIT_LEDGER_NOT_STAGED: RECORD_INTEGRITY_LEDGER is set, so this run appended nothing to ${GC_LEDGER}"
elif git diff --quiet -- "${GC_LEDGER}"; then
    echo "GUARDED_COMMIT_LEDGER_UNCHANGED: ${GC_LEDGER}"
else
    git add -- "${GC_LEDGER}"
    echo "GUARDED_COMMIT_LEDGER_STAGED: ${GC_LEDGER}"
fi
git commit "$@"
