"""The two-roots trap, bounded and demonstrated by execution rather than by a
comment that has already been written down and already been ignored.

THE MECHANISM

This working tree has two roots:

    /Users/symow/Desktop/bbrose-systemOS                 <- the GIT root
    /Users/symow/Desktop/bbrose-systemOS/bbrose_design_os <- Django, pytest,
                                                            venv, tools

Two tracked top-level directory names exist under BOTH of them -- ``docs`` and
``tools`` -- plus one tracked file, ``.gitignore``. So a relative path like
``tools/`` is SILENTLY VALID in both places and means different content in
each, and ``git show HEAD:<path>`` resolves from the git root regardless of
the cwd unless the path is written ``HEAD:./<path>``.

Neither form announces which root it used. That is the whole defect: the cwd
is invisible, persistent state, and the wrong root does not produce an error,
it produces a plausible answer.

WHY THIS IS A TEST AND NOT A NOTE

The gotcha was already written down in the operator's notes before any of this
was built, and it was hit nine times anyway. The ninth is the one that decided
the shape of this file: a ``grep -rln`` over ``tools/`` run from the git root
returned a hit from ``tools/dip0b/tests/conftest.py`` -- a real file, a
plausible answer, exit status 0 -- when the intended target was
``bbrose_design_os/tools/``. The same command from the inner root returns
nothing. Same text, two roots, two different answers, no error either way.

A note cannot catch that. A note is what failed nine times.

WHAT THIS GUARD DOES

Two things.

It PINS THE EXTENT of the collision. Today it is exactly three names. The trap
grows when a fourth is added, and adding one is easy and looks harmless, so the
addition is made to fail here with the new name printed.

And it DEMONSTRATES THE THREE SILENT MODES BY EXECUTION rather than describing
them, so that they cannot rot into a comment that is confidently wrong -- which
is the documented history of this particular knowledge in this repository:

  RevPathResolutionTests   ``HEAD:<path>`` is root-relative and fails from the
                           inner root; ``HEAD:./<path>`` is the safe form. The
                           failure is loud on stderr and silent through a pipe.
  PathLimitedStatusTests   ``git status --short <absent path>`` warns, prints
                           nothing, exits 0 -- and reads as "clean". The remedy
                           is ``git ls-files --error-unmatch``.
  WrongSuccessTests        ``.gitignore`` returns the WRONG FILE with no error
                           at all, because it is tracked under both roots.

Every assertion below has been run against a deliberately broken premise and
seen to fail. A guard that has never fired proves nothing.

WHAT THIS GUARD DOES NOT DO -- STATED, NOT IMPLIED

It does not stop anyone typing ``tools/`` from the wrong root. Nothing in this
repository can intercept an interactive shell command, and all nine occurrences
were interactive. This bounds the trap; it does not remove it.

The complete fix is to de-collide the two names, and it was measured rather
than hand-waved: 352 tracked files live under the git-root ``docs/`` and
``tools/``, and 83 tracked files reference those paths, including
``.github/workflows/ci.yml`` and ``bbrose_design_os/config/settings.py``. That
is a cross-cutting rename touching CI and Django settings for a workstream
(Design Intelligence) that is not this one's to restructure. It is the owner's
call, and it is recorded here so that the call is available rather than
forgotten.
"""

import os
import subprocess
import unittest


#: Derived from ``__file__``, never from the cwd -- which is the same
#: discipline whose ABSENCE is the bug under guard. ``record_integrity.py``
#: line 21 does this correctly and it is why redirecting a subprocess's cwd
#: could never have isolated the ledger.
DJANGO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
GIT_ROOT = os.path.dirname(DJANGO_ROOT)

#: Measured 2026-08-22, not remembered. Reproduce with::
#:
#:     git ls-files -z | ... split on the bbrose_design_os/ prefix,
#:     intersect the top-level name sets
#:
#: A fourth entry here is not a test that needs updating. It is a new way for
#: a relative path to mean two things, and it should be read that way before
#: the number is changed.
KNOWN_COLLIDING_TOP_LEVEL_NAMES = {"docs"}  # .gitignore and tools/ merged into one, 2026-10-04; docs/ waits (G6)

#: Full paths tracked under both roots. ``.gitignore`` is the only one, and it
#: is the sharpest case in the tree: ``git show HEAD:.gitignore`` succeeds from
#: either cwd and returns the GIT-ROOT file, never the inner one -- a wrong
#: SUCCESS rather than a loud failure. The inner ``.gitignore`` is where
#: ``.suite_gate_result`` and ``.tier2_gate_output`` are declared.
KNOWN_COLLIDING_FULL_PATHS = set()  # the one .gitignore since the clean-up of 2026-10-04


def _tracked(cwd):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=cwd,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


class TwoRootsLayoutTests(unittest.TestCase):
    """If the layout stops matching, every assertion below stops meaning what
    it says. A guard whose premise has quietly dissolved passes for the wrong
    reason, so the premise is checked first and by itself."""

    def test_there_really_are_two_roots_and_this_is_where_they_are(self):
        self.assertTrue(os.path.isdir(os.path.join(GIT_ROOT, ".git")),
                        f"no .git at the expected git root {GIT_ROOT}")
        self.assertFalse(os.path.isdir(os.path.join(DJANGO_ROOT, ".git")),
                         "a .git appeared inside the Django root -- the two "
                         "roots have become two repositories and the "
                         "collision analysis in this file no longer applies")
        self.assertEqual(os.path.basename(DJANGO_ROOT), "bbrose_design_os")
        self.assertTrue(os.path.isfile(os.path.join(DJANGO_ROOT, "manage.py")))


class TwoRootsCollisionExtentTests(unittest.TestCase):

    def setUp(self):
        tracked = _tracked(GIT_ROOT)
        pre = "bbrose_design_os/"
        self.inner = [p[len(pre):] for p in tracked if p.startswith(pre)]
        self.root = [p for p in tracked if not p.startswith(pre)]
        # -z above matters: git C-quotes paths containing non-ASCII, and the
        # em-dashes in docs/visual_quality/rbv/owner_inputs/ defeat a plain
        # prefix filter. Measured while writing this file: the unquoted read
        # reported 48 collisions, 47 of them that artefact. The real count is
        # one. The wrong number looked entirely reasonable.

    def test_the_colliding_top_level_names_are_exactly_the_known_three(self):
        top = lambda ps: {p.split("/")[0] for p in ps}
        found = top(self.root) & top(self.inner)
        self.assertEqual(
            found, KNOWN_COLLIDING_TOP_LEVEL_NAMES,
            "the set of top-level names that exist under BOTH roots changed.\n"
            f"  expected: {sorted(KNOWN_COLLIDING_TOP_LEVEL_NAMES)}\n"
            f"  found:    {sorted(found)}\n"
            f"  added:    {sorted(found - KNOWN_COLLIDING_TOP_LEVEL_NAMES)}\n"
            f"  removed:  {sorted(KNOWN_COLLIDING_TOP_LEVEL_NAMES - found)}\n"
            "Each added name is a new relative path that silently means two "
            "different things depending on a cwd nobody can see.")

    def test_the_colliding_full_paths_are_exactly_the_known_one(self):
        found = set(self.root) & set(self.inner)
        self.assertEqual(
            found, KNOWN_COLLIDING_FULL_PATHS,
            "the set of FULL paths tracked under both roots changed.\n"
            f"  expected: {sorted(KNOWN_COLLIDING_FULL_PATHS)}\n"
            f"  found:    {sorted(found)}\n"
            "These are the worst case: `git show HEAD:<path>` returns the "
            "git-root file with no error and no indication of which it read.")


class RevPathResolutionTests(unittest.TestCase):
    """``HEAD:<path>`` versus ``HEAD:./<path>``, executed rather than asserted.

    These are not tests of git. They are the demonstration that the safe form
    is the one with ``./``, kept executable so it cannot rot into a comment
    that is confidently wrong -- which is the documented history of this
    particular piece of knowledge in this repository."""

    #: Inner-only and tracked, so the bare form fails from BOTH cwds and the
    #: dotted form succeeds only from the inner root. The ledger would have
    #: worked too but its line count changes on every commit, and a guard
    #: that needs updating on every commit gets updated without being read.
    REL = "manage.py"

    def test_the_bare_form_ignores_the_cwd_and_fails_from_the_inner_root(self):
        r = subprocess.run(["git", "show", f"HEAD:{self.REL}"],
                           cwd=DJANGO_ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0,
                            "HEAD:manage.py resolved from inside "
                            "bbrose_design_os/ -- git's rev-path semantics "
                            "changed, or manage.py now exists at the git root")
        self.assertIn("fatal", r.stderr.lower())
        self.assertEqual(r.stdout, "", "the failing form still produced bytes")

    def test_the_dotted_form_honours_the_cwd_and_is_the_safe_one(self):
        r = subprocess.run(["git", "show", f"HEAD:./{self.REL}"],
                           cwd=DJANGO_ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DJANGO_SETTINGS_MODULE", r.stdout)

    def test_the_failure_is_loud_on_stderr_and_silent_through_a_pipe(self):
        """A137's shape, on this specific command.

        ``git show`` reports the error correctly. ``| wc -l`` then reports
        WC's exit code, not git's, and prints a number. The number is zero --
        a measurement-shaped value where an error belongs. This is the reason
        the mistake was survivable enough to make nine times: it never once
        looked like a mistake.
        """
        piped = subprocess.run(
            f"git show 'HEAD:{self.REL}' 2>/dev/null | wc -l",
            cwd=DJANGO_ROOT, shell=True, capture_output=True, text=True)
        self.assertEqual(piped.returncode, 0,
                         "the pipeline reported failure -- if pipefail became "
                         "the default this guard's premise is gone and the "
                         "silent-zero hazard it describes no longer exists")
        self.assertEqual(piped.stdout.strip(), "0")

        direct = subprocess.run(["git", "show", f"HEAD:{self.REL}"],
                                cwd=DJANGO_ROOT, capture_output=True,
                                text=True)
        self.assertNotEqual(direct.returncode, 0)
        # Same command, same instant: 0-and-success through the pipe,
        # non-zero-and-fatal without it.


class PathLimitedStatusTests(unittest.TestCase):
    """The instance that did real damage, kept executable.

    ``git status --short <path>`` against a path that does not exist under
    THIS root prints a *warning* to stderr, prints nothing to stdout, and
    exits 0. Empty output from a path-limited status reads as "that file is
    unmodified". It actually meant "that path is not here".

    This is not hypothetical. It is how the node-delta check was run:

        git status --short docs/roadmap/progress_tracker.json

    from the git root, where ``docs/roadmap/`` does not exist -- the tracker
    is at ``bbrose_design_os/docs/roadmap/progress_tracker.json``. The check
    returned empty and was reported as "ZERO, the tracker is not touched".
    Re-run afterwards against the real path, the conclusion held: the three
    commits concerned touched 3, 1 and 1 files and none was the tracker. The
    ANSWER was right and the EVIDENCE was void, which is the more dangerous
    pairing, because a void check that agrees with you is never revisited.

    THE REMEDY, and it is a real flag rather than an intention: name the path
    to ``git ls-files --error-unmatch`` first. It exits non-zero on a path git
    does not know, so the absent-path case becomes an error instead of a
    reassuring blank. The idiom is already in this tree at
    ``apps/pipeline/tests/test_wi0_evidence_is_committed.py``.
    """

    ABSENT = "docs/roadmap/progress_tracker.json"     # absent at the GIT root
    PRESENT = "bbrose_design_os/docs/roadmap/progress_tracker.json"

    def test_a_path_absent_from_this_root_looks_exactly_like_a_clean_one(self):
        r = subprocess.run(["git", "status", "--short", self.ABSENT],
                           cwd=GIT_ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         "path-limited status now FAILS on an absent path -- "
                         "good, and this guard's premise is gone")
        self.assertEqual(r.stdout, "", "stdout was not the reassuring blank")
        self.assertIn("could not open directory", r.stderr,
                      "the warning that is the only evidence of the mistake "
                      "is no longer emitted, which makes the shape worse, "
                      "not better")

    def test_error_unmatch_is_the_remedy_and_it_actually_fires(self):
        bad = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", self.ABSENT],
            cwd=GIT_ROOT, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0,
                            "--error-unmatch accepted a path git does not "
                            "track; the remedy recommended in this file's "
                            "docstring no longer works and the docstring is "
                            "now wrong")

        good = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", self.PRESENT],
            cwd=GIT_ROOT, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(good.stdout.strip(), self.PRESENT)


class WrongSuccessTests(unittest.TestCase):
    """The case with no failure signal at all — and, since the clean-up of 2026-10-04, the case that is gone.

    ``.gitignore`` WAS tracked under both roots, so the bare form ``HEAD:.gitignore`` succeeded from the inner root,
    printed a real file, exited 0 — and handed back the wrong one. The clean-up merged the app folder's 35 lines into
    the git root's file (each keeping its reach) and took the inner file out of the tree. There is one .gitignore now,
    so the two spellings cannot disagree. These two tests used to demonstrate the hazard; they now pin that it stays
    gone, and that the one file still declares the gate's own artifacts — the reason the inner file mattered.
    """

    def _blob(self, cwd, spec):
        return subprocess.run(["git", "show", spec], cwd=cwd,
                              capture_output=True, check=True).stdout

    def test_there_is_one_gitignore_so_the_bare_form_cannot_return_the_wrong_one(self):
        # read from the index and the working tree, never HEAD: a gate runs this BEFORE its own commit exists
        tracked = subprocess.run(["git", "ls-files", "--", "bbrose_design_os/.gitignore"],
                                 cwd=GIT_ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(tracked.stdout.strip(), "",
                         "an inner .gitignore is tracked again -- the wrong-success hazard is back; "
                         "merge it into the git root's file instead")
        self.assertFalse(os.path.exists(os.path.join(DJANGO_ROOT, ".gitignore")))
        bare = self._blob(DJANGO_ROOT, "HEAD:.gitignore")
        root = self._blob(GIT_ROOT, "HEAD:./.gitignore")
        self.assertEqual(bare, root,
                         "HEAD:.gitignore no longer resolves from the git "
                         "root; git's rev-path semantics changed")

    def test_the_one_gitignore_declares_the_gates_own_artifacts(self):
        """Not decoration. The gate writes its artifacts at the app folder's root; the one .gitignore must keep them
        out of `git status`, or a `git add -A` nobody meant commits them. Verified by content, not line number."""
        with open(os.path.join(GIT_ROOT, ".gitignore"), encoding="utf-8") as fh:   # the working tree, not HEAD
            root = fh.read()
        for name in (".suite_gate_result", ".tier2_gate_output"):
            self.assertIn("bbrose_design_os/**/" + name, root)
        for name in (".suite_gate_result", ".tier2_gate_output"):
            ignored = subprocess.run(["git", "check-ignore", "-q", "bbrose_design_os/" + name], cwd=GIT_ROOT)
            self.assertEqual(ignored.returncode, 0, name)


# ---------------------------------------------------------------------------
# §BH40(d) — THE BRAIN'S FRESHNESS GATE.
#
# The brain (bbrose_design_os/tools/brain/ — at the GIT root until the clean-up
# of 2026-10-04 moved it beside the gate) is a derived index
# over the register, the queue, the sitting reports, the WATCH notes, the
# launchers, the prompt files and the DIP-0A record. Its freshness record,
# var/brain/freshness.json, stores the sha256 of every source at build time.
# This test refuses the commit when that record disagrees with the sources on
# disk NOW: a source changed, a source appeared, a source vanished, or no
# record exists. guarded_commit.sh runs the rebuild before the suite, so a
# GREEN gate is evidence that the index a session consults was built from the
# sources the commit carries. Outside the gate the test fails until
# tools/brain/rebuild.py is run — by design: an index older than the register
# it was built from is refused, not tolerated.
#
# The module is loaded by FILE PATH from the app's tools/ (the same technique
# test_characterization_protocol.py uses for claim_scan.py), never imported
# as a package: the outer tools/ package chain must not be reached through
# sys.path from the apps leg. BRAIN_DIR relocates the record for the negative
# control below, so the real var/brain/ is never written by a test.
# ---------------------------------------------------------------------------

import collections as _collections
import hashlib as _hashlib
import importlib.util as _ilu
import json as _json
import os as _os
import pathlib as _pathlib
import tempfile as _tempfile

_GIT_ROOT = _pathlib.Path(GIT_ROOT)
_DJANGO_ROOT = _pathlib.Path(DJANGO_ROOT)
_BRAIN_SOURCES = _DJANGO_ROOT / "tools" / "brain" / "sources.py"


def _load_brain_sources(brain_dir=None):
    env = dict(_os.environ)
    if brain_dir is not None:
        _os.environ["BRAIN_DIR"] = str(brain_dir)
    else:
        _os.environ.pop("BRAIN_DIR", None)
    try:
        spec = _ilu.spec_from_file_location("brain_sources_under_test", _BRAIN_SOURCES)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        _os.environ.clear(); _os.environ.update(env)


class BrainFreshnessGateTests(unittest.TestCase):
    """§BH40(d): the on-disk index's freshness record must agree with the current source hashes."""

    def test_the_brain_lives_in_the_apps_tools_and_nowhere_else(self):
        self.assertTrue(_BRAIN_SOURCES.is_file(), "tools/brain/sources.py is missing under bbrose_design_os/tools/")
        self.assertFalse((_GIT_ROOT / "tools" / "brain").exists(),
                         "a second tools/brain at the git root would bring the two-roots trap back")

    def test_the_index_is_fresh_or_the_commit_is_refused(self):
        S = _load_brain_sources()
        record = S.read_freshness()
        fresh, findings = S.compare_freshness(record)
        self.assertTrue(fresh, "BRAIN_STALE — the freshness record at %s disagrees with the sources on disk; "
                               "run tools/brain/rebuild.py (guarded_commit.sh runs it before the suite):\n  %s"
                        % (S.FRESHNESS_PATH, "\n  ".join(findings[:12])))
        self.assertEqual(record["record_type"], S.FRESHNESS_RECORD_TYPE)
        self.assertGreater(record["source_count"], 300)
        self.assertLess(record["rebuild_seconds"], 300.0,
                        "§BH42(a) raised §BH40(d)'s two-minute bound to five minutes when the "
                        "semantic layer joined the rebuild; over it is a stop, not a gate step")

    def test_a_stale_record_is_refused_negative_control(self):
        """A record that names one source with a different hash, and one that names no source at all."""
        with _tempfile.TemporaryDirectory() as d:
            S = _load_brain_sources(d)
            fresh, findings = S.compare_freshness(None)
            self.assertFalse(fresh); self.assertTrue(findings[0].startswith("NO_FRESHNESS_RECORD"))
            current = S.current_source_hashes()
            k = sorted(current)[0]
            stale = {"record_type": S.FRESHNESS_RECORD_TYPE, "sources": dict(current)}
            stale["sources"][k] = "0" * 64
            fresh, findings = S.compare_freshness(stale, current)
            self.assertFalse(fresh); self.assertEqual(findings, ["SOURCE_CHANGED: %s" % k])
            gone = {"record_type": S.FRESHNESS_RECORD_TYPE, "sources": {kk: v for kk, v in current.items() if kk != k}}
            fresh, findings = S.compare_freshness(gone, current)
            self.assertFalse(fresh); self.assertEqual(findings, ["SOURCE_NEW: %s is enumerated and was not indexed" % k])

    def test_no_tracked_file_carries_a_hash_of_the_register(self):
        """§BH40(b): the register's hash lives in the untracked freshness record and nowhere tracked."""
        S = _load_brain_sources()
        reg_sha = S.sha256_file(S.REGISTER)
        tracked = subprocess.run(["git", "-C", str(_GIT_ROOT), "ls-files", "-z", "--", "bbrose_design_os/tools/brain", ".mcp.json", "CLAUDE.md",
                                  "bbrose_design_os/tools", "bbrose_design_os/apps/pipeline/tests"],
                                 capture_output=True, check=True).stdout.decode().split("\0")
        for rel in tracked:
            if rel and (_GIT_ROOT / rel).is_file():
                self.assertNotIn(reg_sha[:16], (_GIT_ROOT / rel).read_text(errors="replace"), rel)
        ignored = subprocess.run(["git", "-C", str(_GIT_ROOT), "check-ignore", "-q", "var/brain/freshness.json"]).returncode
        self.assertEqual(ignored, 0, "var/brain/freshness.json must be git-ignored")


# ---------------------------------------------------------------------------
# §BH42(i) — §BH24 IS RETIRED, unconditionally. The owner's sentence at
# OWNER_BLOCKER_CLEARANCE.md:20223 reads "The brain's status for §BH24 must
# measure SUPERSEDED-BY §BH41", and §BH41 is the front that established the
# flush deadlock's cause and fixed it. A flush deadlock, or any refusal of
# that shape, is now a defect to reproduce — never a re-run, never a widened
# id-list.
#
# The register had no grammar for this: the retiring verb typed is "IS
# RETIRED", the supersession idiom matched only "supersede" and its
# inflections, and even on a match the superseder would have been the block
# the sentence sits in (§BH42) rather than the §BH41 the owner named. So the
# chunker gained ONE idiom — a status the register DECLARES outright, naming
# both ends itself, is measured directly rather than inferred from verb
# grammar. Measured over the whole register and queue, the idiom moves
# exactly one status and adds exactly one note.
# ---------------------------------------------------------------------------

_BRAIN_CHUNKER = _DJANGO_ROOT / "tools" / "brain" / "chunker.py"


def _load_brain_chunker():
    spec = _ilu.spec_from_file_location("brain_chunker_under_test", _BRAIN_CHUNKER)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _measure_text(chunker, register_text, queue_text=""):
    texts = {"OWNER_BLOCKER_CLEARANCE.md": register_text, "OWNER_REVIEW_QUEUE.md": queue_text}
    chunks = (chunker.chunk_file(register_text, "OWNER_BLOCKER_CLEARANCE.md", "R")
              + chunker.chunk_file(queue_text, "OWNER_REVIEW_QUEUE.md", "Q"))
    return chunker.measure(chunks, texts)


class BrainSupersessionDeclarationTests(unittest.TestCase):
    """§BH42(i): a status the register declares outright is measured, not inferred."""

    def test_bh24_measures_superseded_by_bh41(self):
        chunker = _load_brain_chunker()
        register = (_GIT_ROOT / "OWNER_BLOCKER_CLEARANCE.md").read_text()
        queue = (_GIT_ROOT / "OWNER_REVIEW_QUEUE.md").read_text()
        chunks, _unresolved, _seen = _measure_text(chunker, register, queue)
        blocks = [c for c in chunks if c["id"] == "§BH24" and c["level"] == 2]
        self.assertEqual(len(blocks), 1, "§BH24 heads exactly one level-2 block")
        block = blocks[0]
        self.assertEqual(block["status"], "SUPERSEDED-BY §BH41",
                         "§BH42(i) retired §BH24 unconditionally; the brain must measure it")
        self.assertEqual(block["superseded_by"], "§BH41")
        self.assertTrue(block["superseded_at"].startswith("OWNER_BLOCKER_CLEARANCE.md:"),
                        block["superseded_at"])
        declared = [n for n in block["notes"] if n["kind"] == "DECLARED"]
        self.assertEqual(len(declared), 1, "one declaration, at the owner's own sentence")
        self.assertEqual(declared[0]["by"], "§BH41")

    def test_a_declaration_is_measured_and_its_negative_controls_are_not(self):
        """Declared plainly it lands; quoted or conditioned in its own clause it does not."""
        chunker = _load_brain_chunker()
        head = ("## 2026-01-01 — OWNER RULING §ZZ1: the target\n\nA target block.\n\n"
                "## 2026-01-02 — OWNER RULING §ZZ2: the authority\n\nAn authority block.\n\n"
                "## 2026-01-03 — OWNER RULING §ZZ3: the declaring block\n\n")
        plain = head + "The brain's status for §ZZ1 must measure SUPERSEDED-BY §ZZ2 after this lands.\n"
        chunks, _u, _s = _measure_text(chunker, plain)
        target = [c for c in chunks if c["id"] == "§ZZ1" and c["level"] == 2][0]
        self.assertEqual(target["status"], "SUPERSEDED-BY §ZZ2")
        self.assertIn("DECLARED", [n["kind"] for n in target["notes"]],
                      "the declaration is recorded as its own note beside any inferred one")

        quoted = head + 'The reading quoted it: "the status for §ZZ1 must measure SUPERSEDED-BY §ZZ2" and stopped.\n'
        chunks, _u, _s = _measure_text(chunker, quoted)
        target = [c for c in chunks if c["id"] == "§ZZ1" and c["level"] == 2][0]
        self.assertEqual(target["status"], "LIVE", "a quoted declaration reports one; it is not one")

        conditioned = head + "If the front lands, the status for §ZZ1 must measure SUPERSEDED-BY §ZZ2.\n"
        chunks, _u, _s = _measure_text(chunker, conditioned)
        target = [c for c in chunks if c["id"] == "§ZZ1" and c["level"] == 2][0]
        self.assertEqual(target["status"], "LIVE", "a condition in the declaration's own clause holds it")

        neighbour = head + ("The status for §ZZ1 must measure SUPERSEDED-BY §ZZ2 after this lands; "
                            "if it still measures LIVE, that is a finding to report.\n")
        chunks, _u, _s = _measure_text(chunker, neighbour)
        target = [c for c in chunks if c["id"] == "§ZZ1" and c["level"] == 2][0]
        self.assertEqual(target["status"], "SUPERSEDED-BY §ZZ2",
                         "a condition in a NEIGHBOURING clause does not veto the declaration")

    def test_the_idiom_moves_exactly_one_status_in_the_register(self):
        """The census that ruled the change: one status, one note, nothing else."""
        chunker = _load_brain_chunker()
        register = (_GIT_ROOT / "OWNER_BLOCKER_CLEARANCE.md").read_text()
        queue = (_GIT_ROOT / "OWNER_REVIEW_QUEUE.md").read_text()
        chunks, _unresolved, _seen = _measure_text(chunker, register, queue)
        declared = [(c["id"], c["status"]) for c in chunks
                    if any(n["kind"] == "DECLARED" for n in c["notes"])]
        self.assertEqual(declared, [("§BH24", "SUPERSEDED-BY §BH41")])
        superseded = sorted(c["status"] for c in chunks if c["status"].startswith("SUPERSEDED-BY"))
        self.assertEqual(superseded, ["SUPERSEDED-BY §AI", "SUPERSEDED-BY §BH41"])


# ---------------------------------------------------------------------------
# §BH42(a) — MEANING. v1 found words; v2 finds things. Every indexed text source
# carries a vector, and the semantic ranking is returned BESIDE the full-text one,
# never in place of it: each hit says which ranking reached it.
#
# The model is DATA under var/brain/ — a vocabulary and a matrix — so the suite's
# virtualenv gains no package. Inference is numpy and the standard library, and its
# agreement with the publishing library's own tokenizer was measured over the whole
# corpus rather than asserted: 99.370% exact token-id agreement, document cosine
# mean 0.999996 at the library's own window, worst case 0.995228.
# ---------------------------------------------------------------------------

import re
import sqlite3

_BRAIN_EMBED = _DJANGO_ROOT / "tools" / "brain" / "embed.py"


def _load_brain_embed():
    spec = _ilu.spec_from_file_location("brain_embed_under_test", _BRAIN_EMBED)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BrainSemanticLayerTests(unittest.TestCase):
    """§BH42(a): the vectors exist, they rank beside the words, and they are labelled."""

    def test_the_layer_is_built_over_the_text_sources(self):
        S = _load_brain_sources()
        record = S.read_freshness()
        embedding = (record.get("stats") or {}).get("embedding") or {}
        self.assertEqual(embedding.get("state"), "BUILT",
                         "§BH42(a): no semantic layer in the freshness record — run "
                         "tools/brain/export_embed_model.py, then tools/brain/rebuild.py")
        E = _load_brain_embed()
        vectors, ids = E.load_vectors(S.BRAIN_DIR)
        self.assertIsNotNone(vectors, "no vectors.npy under var/brain/")
        self.assertEqual(len(ids), embedding["vectors"])
        self.assertEqual(vectors.shape[1], embedding["dim"])
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            placeholders = ",".join("?" * len(E.TEXT_KINDS))
            n = con.execute("SELECT COUNT(*) FROM docs WHERE kind IN (%s)" % placeholders,
                            E.TEXT_KINDS).fetchone()[0]
        finally:
            con.close()
        self.assertEqual(len(ids), n, "every text document carries a vector")

    def test_the_rebuild_stays_within_the_ruled_bound(self):
        """§BH42(a) raised the bound from two minutes to five; over it is a stop."""
        S = _load_brain_sources()
        E = _load_brain_embed()
        self.assertEqual(E.REBUILD_BOUND_SECONDS, 300)
        self.assertLess(S.read_freshness()["rebuild_seconds"], float(E.REBUILD_BOUND_SECONDS))

    def test_meaning_reaches_a_source_that_shares_no_word_with_the_question(self):
        """The goal state's own test: every word of the query absent from what it cites.

        The property is the pin, not the rank. TWO assertions, and they are scoped differently on purpose:

        1. THE CLOSEST DOCUMENT OF THE PROBE'S OWN KIND shares NO word with the question — the goal state's
           property, proved on the corpus the probe was written for.
        2. THE SOURCE THE PROBE WAS CHOSEN FOR is among the three closest of that kind.

        §BH55(a)(b) MOVED THE SECOND ONE, and the reason is a live property of the system rather than a flaky
        test. Landing the REFERENCE captions put 4,431 `caption` documents beside 888 `register` ones, and
        "eyeballing discouraged instrumentation preferred" now reaches three pictures of eyes — lashes, eyeliner
        artwork — because "eyeballing" IS near eye imagery in meaning. The semantic layer is working; the anchor
        was measuring the corpus's composition. So the anchor now asks what `brain.search` asks: that tool takes a
        `kind` and filters its semantic half by it (`tools/brain/server.py:102`), and only the raw
        `embed.nearest()` probed here has no filter. Scoped that way the probe is immune to a picture corpus
        growing beside a text one, and it is not widened to green — the expected source must still be in the
        closest THREE of its own kind.

        BOTH assertions are scoped, and the second probe is why. Unfiltered, "pausing traffic before erasing
        tables" now lands on a caption of ROAD SIGNS — which contains the word "traffic", so the no-shared-word
        assertion was failing on a picture rather than on anything about meaning. Measuring the property against a
        union of text and image captions measures the corpus's composition; measuring it inside the kind measures
        the layer.

        WHAT THIS LEAVES TRUE AND WORTH KNOWING, and it is a live property of the system rather than a test
        detail: an UNSCOPED semantic question now competes with 4,431 image captions. "eyeballing discouraged
        instrumentation preferred" returns lashes and eyeliner artwork; "pausing traffic before erasing tables"
        returns road signs. A designer who asks without a kind can get pictures where they used to get the
        register, and `brain.search`'s `kind` is what avoids it.
        """
        S = _load_brain_sources()
        E = _load_brain_embed()
        probes = (("eyeballing discouraged instrumentation preferred", "OWNER_BLOCKER_CLEARANCE.md", "register"),
                  ("pausing traffic before erasing tables", "run_6.txt", "sitting"))
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            for query, expected_file, kind in probes:
                near = E.nearest(query, S.BRAIN_DIR, limit=200)
                self.assertTrue(near, "no semantic hit for %r" % query)
                rows = [con.execute("SELECT path, kind, COALESCE(title,'') || ' ' || COALESCE(text,'') "
                                    "FROM docs WHERE id = ?", (doc_id,)).fetchone()
                        for doc_id, _score in near]
                of_kind = [r for r in rows if r[1] == kind][:3]
                self.assertTrue(of_kind, "%r reaches no %s document at all" % (query, kind))
                body = of_kind[0][2].lower()
                for word in query.split():
                    self.assertNotRegex(body, r"\b%s\b" % re.escape(word),
                                        "%r shares the word %r with the source it cites" % (query, word))
                self.assertTrue(any(expected_file in r[0] for r in of_kind),
                                "%r no longer reaches %s among the closest %s documents: %r"
                                % (query, expected_file, kind, [r[0] for r in of_kind]))
        finally:
            con.close()

    def test_the_full_text_ranking_is_never_replaced_and_every_hit_is_labelled(self):
        S = _load_brain_sources()
        server = _ilu.module_from_spec(_ilu.spec_from_file_location(
            "brain_server_under_test", _DJANGO_ROOT / "tools" / "brain" / "server.py"))
        server.__spec__.loader.exec_module(server)
        words_only = server.tool_search({"query": "deadlock", "kind": "register",
                                         "limit": 5, "semantic": False})
        both = server.tool_search({"query": "deadlock", "kind": "register", "limit": 5})
        self.assertEqual(words_only["semantic"], "off")
        self.assertEqual(both["semantic"], "on")
        fts_cites = [h["cite"] for h in words_only["hits"]]
        kept = [h["cite"] for h in both["hits"] if h["found_by"].startswith("fts")]
        self.assertEqual(fts_cites, kept, "the full-text hits are kept, in their own order")
        for hit in both["hits"]:
            self.assertIn(hit["found_by"], ("fts", "semantic", "fts+semantic"))
            if hit["found_by"] == "semantic":
                self.assertIn("semantic_score", hit)
                self.assertNotIn("fts_score", hit)

    def test_the_ruled_probe_reaches_bh16_by_meaning(self):
        """(a)'s own sentence: the question about silence reaches §BH16."""
        S = _load_brain_sources()
        E = _load_brain_embed()
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            sections = []
            for doc_id, _ in E.nearest("what did we decide about silence in the record", S.BRAIN_DIR, limit=5):
                row = con.execute("SELECT section_id FROM docs WHERE id = ?", (doc_id,)).fetchone()
                sections.append(row[0])
        finally:
            con.close()
        self.assertIn("§BH16", sections, "the ruled probe must reach §BH16: %r" % sections)


# ---------------------------------------------------------------------------
# §BH42(b)+(c) — the captions' SCOPE and their SPEND, both checkable without
# spending anything.
#
# The scope is read from the records that define it, never re-derived: the 254
# design files listed by the §BH28 extraction and the PRODUCTION rows of the
# tier record. Re-deriving from the inventory returns 258 and sweeps in a
# licence agreement that is not a design.
#
# The cap is a decision, not a hope: a projection over it refuses, and only the
# owner's word lifts it, for that run alone.
# ---------------------------------------------------------------------------


class BrainCaptionScopeAndSpendTests(unittest.TestCase):
    """§BH42(b)+(c): the ruled scope, and the cap that refuses."""

    @staticmethod
    def _module():
        spec = _ilu.spec_from_file_location("brain_caption_scope", _DJANGO_ROOT / "tools" / "brain" / "caption_scope.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_the_scope_is_the_ruled_one_and_the_two_sets_are_disjoint(self):
        C = self._module()
        rows = C.scope()
        designs = [r for r in rows if r["set"] == "design_254"]
        production = [r for r in rows if r["set"] == "production_141"]
        self.assertEqual(len(designs), 254, "the §BH28 extraction's extent, as the register states it")
        self.assertEqual(len(production), 141, "the PRODUCTION rows of the tier record")
        self.assertEqual(len(rows), 395)
        self.assertEqual(len({r["sha256"] for r in designs} & {r["sha256"] for r in production}), 0)
        self.assertTrue(all(r["path"].startswith("materials/") for r in rows))
        for r in designs:
            self.assertIsNone(r["tier"], "a design file carries no tier row; it is not REFERENCE")
        for r in production:
            self.assertEqual(r["tier"], "PRODUCTION")

    def test_a_projection_over_the_cap_refuses_and_only_the_owners_word_lifts_it(self):
        C = self._module()
        self.assertEqual(C.DEFAULT_CAP_USD, 50.0, "§BH42(c) names the §AE cap")
        projected = C.project(0.0242, 10, 390)
        self.assertAlmostEqual(projected, 0.9438, places=3)
        self.assertFalse(C.refuses(projected, 50.0, False), "under the cap the run proceeds")
        self.assertTrue(C.refuses(projected, 0.10, False), "over the cap the run refuses")
        self.assertFalse(C.refuses(projected, 0.10, True), "the owner's word lifts it, for that run")
        self.assertTrue(C.refuses(60.0, 50.0, False))
        self.assertEqual(C.project(1.0, 0, 400), 0.0, "no sample, no projection")

    def test_the_palette_is_measured_from_pixels_not_asked_of_a_model(self):
        C = self._module()
        from PIL import Image
        frame = Image.new("RGB", (100, 100), (255, 197, 33))
        frame.paste(Image.new("RGB", (100, 25), (228, 0, 64)), (0, 0))
        measured = C.palette(frame)
        self.assertEqual(measured[0]["hex"], "#FFC521")
        self.assertGreater(measured[0]["share"], 0.7)
        self.assertEqual(measured[1]["hex"], "#E40040")
        self.assertEqual(sorted(measured[0].keys()), ["hex", "share"])


# ---------------------------------------------------------------------------
# §BH42(d) — brain.material answers by what an image SHOWS and by the colours
# measured in it, and brain.search ranks text and captions together.
#
# A caption is DERIVED and machine-written. It is evidence of nothing about
# rights: every row carries the tier record's verdict beside it and a placement
# verdict that refuses anything but a PRODUCTION row — the §BH37/§BH39 line,
# held inside the brain. No bytes; no locator beyond the repo-relative path.
# ---------------------------------------------------------------------------


class BrainCaptionSearchTests(unittest.TestCase):
    """§BH42(d): captions and palettes are searchable, and the tier travels with them."""

    @staticmethod
    def _server():
        spec = _ilu.spec_from_file_location("brain_server_captions", _DJANGO_ROOT / "tools" / "brain" / "server.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _captions_built(self):
        S = _load_brain_sources()
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            return con.execute("SELECT COUNT(*) FROM captions").fetchone()[0]
        finally:
            con.close()

    def test_the_captions_are_in_the_index_with_their_tier(self):
        S = _load_brain_sources()
        record = S.read_freshness()
        captions = (record.get("stats") or {}).get("captions") or {}
        self.assertEqual(captions.get("state"), "BUILT",
                         "§BH42(b): no captions in the index — run the caption pass, then rebuild")
        self.assertGreater(self._captions_built(), 300)
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            orphans = con.execute(
                "SELECT COUNT(*) FROM captions c LEFT JOIN materials m ON m.relative_path = c.relative_path "
                "WHERE m.relative_path IS NULL").fetchone()[0]
            self.assertEqual(orphans, 0, "every caption joins a row of the inventory")
            machine = con.execute("SELECT COUNT(*) FROM captions WHERE machine_written != 1").fetchone()[0]
            self.assertEqual(machine, 0, "every caption is marked machine-written")
        finally:
            con.close()

    def test_an_image_is_found_by_what_it_shows_and_by_its_colour(self):
        server = self._server()
        by_words = server.tool_material({"query": "flat vector pattern", "limit": 5})
        self.assertGreater(by_words["count"], 0)
        self.assertTrue(any("caption" in r for r in by_words["rows"]),
                        "a caption-matched row carries its caption")
        by_colour = server.tool_material({"query": "#FFC521", "limit": 5})
        self.assertGreater(by_colour["count"], 0, "a hex must reach the images that measured it")
        for row in by_colour["rows"]:
            matched = (row.get("caption") or {}).get("matched_by") or {}
            if "delta_e76" in matched:
                self.assertLessEqual(matched["delta_e76"], 12.0)

    def test_a_caption_carries_its_tier_and_the_refusal_to_place_it(self):
        """The §BH37/§BH39 line inside the brain: only PRODUCTION may be placed."""
        server = self._server()
        found = server.tool_material({"query": "flat vector", "limit": 40})
        self.assertGreater(found["count"], 0)
        for row in found["rows"]:
            self.assertIn("placement", row)
            self.assertIn("tier", row)
            if row["tier"] == "PRODUCTION":
                self.assertTrue(row["placement"]["may_place"])
            else:
                self.assertFalse(row["placement"]["may_place"],
                                 "%s is %s and its bytes may not be placed" % (row["relative_path"], row["tier"]))
            if "caption" in row:
                self.assertTrue(row["caption"]["machine_written"])
                self.assertIn("rights", row["caption"]["rights_note"].lower())

    def test_no_row_ever_carries_bytes_or_a_locator(self):
        server = self._server()
        for query in ("flat vector", "#FFC521", "materials/"):
            for row in server.tool_material({"query": query, "limit": 10})["rows"]:
                for forbidden in server.FORBIDDEN_FIELDS:
                    self.assertNotIn(forbidden, row, query)
                self.assertTrue(row["relative_path"].startswith("materials/"))

    def test_search_ranks_text_and_captions_together(self):
        server = self._server()
        out = server.tool_search({"query": "packaging", "limit": 20})
        kinds = {h["kind"] for h in out["hits"]}
        self.assertTrue(kinds & {"caption"}, "captions must be reachable from search: %r" % kinds)
        for hit in out["hits"]:
            self.assertIn(hit["found_by"], ("fts", "semantic", "fts+semantic"))


# ---------------------------------------------------------------------------
# §BH42(e) — the freshness gate reaches the captions and the vectors too.
#
# §BH40(d) refused a commit whose index disagreed with the sources on disk.
# That test knows nothing of captions: an image added to the ruled scope after
# the last caption run leaves the record fresh and the picture unread. So the
# gate now reads a COVERAGE state as well — a source in scope with no caption
# and no named reason is UNCAPTIONED, and the commit is refused rather than
# passing in silence. The same holds for the vectors: a text document with no
# vector is UNEMBEDDED and counted, never assumed away.
# ---------------------------------------------------------------------------


class BrainCoverageGateTests(unittest.TestCase):
    """§BH42(e): what the last derivation did not reach is REPORTED, never silent."""

    @staticmethod
    def _caption_scope():
        spec = _ilu.spec_from_file_location("brain_caption_scope_cov", _DJANGO_ROOT / "tools" / "brain" / "caption_scope.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_every_image_of_the_ruled_scope_is_captioned_or_named(self):
        C = self._caption_scope()
        cov = C.coverage()
        self.assertEqual(cov["state"], "COMPLETE",
                         "§BH42(e): %d images in scope are UNCAPTIONED: %s"
                         % (len(cov["uncaptioned"]), cov["uncaptioned"][:5]))
        self.assertEqual(cov["covered_paths"] + cov["uncaptionable_paths"], cov["scope_paths"],
                         "every path is either captioned or named uncaptionable")
        self.assertEqual(cov["uncaptioned"], [])

    def test_the_index_carries_the_coverage_it_was_built_with(self):
        S = _load_brain_sources()
        captions = (S.read_freshness().get("stats") or {}).get("captions") or {}
        self.assertEqual(captions.get("state"), "BUILT")
        self.assertEqual((captions.get("coverage") or {}).get("state"), "COMPLETE")

    def test_an_image_added_after_the_caption_run_is_reported_uncaptioned(self):
        """The negative control: a scope that grew since the run must not read COMPLETE.

        §BH55(a): THIS CONTROL HAD GONE VACUOUS and the repair is the point of the change. It dropped
        `record["captions"][0]` — the first row by sha256 — which worked only while the record and the measured
        scope were the same 396 contents. Since §BH43(b) landed the REFERENCE library the record holds 4,431 and
        the ruled scope is still 389, so the first row is almost certainly a REFERENCE file OUTSIDE the scope this
        measures: dropping it changed nothing, coverage read COMPLETE, and the control passed while testing
        nothing. It now drops a row that IS in the scope, which is what it always meant, and it stays true however
        far the record grows past the scope again.
        """
        C = self._caption_scope()
        record = C.read_tracked()          # §BH43(a): the record is tracked, not under var/
        in_scope = {r["path"] for r in C.scope()}
        dropped = next((c for c in record["captions"]
                        if in_scope.intersection(c.get("paths") or [c["path"]])), None)
        self.assertIsNotNone(dropped, "no captioned content is inside the measured scope — the control is vacuous")
        thinned = dict(record)
        thinned["captions"] = [c for c in record["captions"] if c["sha256"] != dropped["sha256"]]
        with _tempfile.TemporaryDirectory() as d:
            path = _pathlib.Path(d) / "captions.json"
            path.write_text(_json.dumps(thinned))
            cov = C.coverage(path)
        self.assertEqual(cov["state"], "UNCAPTIONED")
        for p in (dropped.get("paths") or [dropped["path"]]):
            self.assertIn(p, cov["uncaptioned"])
        self.assertLess(cov["covered_paths"], cov["scope_paths"])

    def test_no_caption_record_at_all_is_reported_not_assumed(self):
        C = self._caption_scope()
        with _tempfile.TemporaryDirectory() as d:
            cov = C.coverage(_pathlib.Path(d) / "absent.json")
        self.assertEqual(cov["state"], "NO_CAPTIONS")
        self.assertEqual(cov["captioned"], 0)
        self.assertGreater(len(cov["uncaptioned"]), 300)

    def test_every_text_document_carries_a_vector_and_the_shortfall_is_counted(self):
        S = _load_brain_sources()
        E = _load_brain_embed()
        embedding = (S.read_freshness().get("stats") or {}).get("embedding") or {}
        self.assertEqual(embedding.get("state"), "BUILT")
        self.assertIn("unembedded", embedding, "a document without a vector is counted, not assumed away")
        _vectors, ids = E.load_vectors(S.BRAIN_DIR)
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            n = con.execute("SELECT COUNT(*) FROM docs WHERE kind IN (%s)"
                            % ",".join("?" * len(E.TEXT_KINDS)), E.TEXT_KINDS).fetchone()[0]
        finally:
            con.close()
        self.assertEqual(len(ids) + embedding["unembedded"], n,
                         "every text document is either embedded or counted as unembedded")


# ---------------------------------------------------------------------------
# §BH43(a) — THE CAPTION RECORD IS TRACKED.
#
# The captions cost dollars to make. The renders, the vectors, the model export
# and the SQLite index are derived and stay ignored, because a machine can remake
# them for nothing. Remaking the RECORD costs dollars again, so it is tracked:
# keyed by content sha256, carrying every path that content lies at, marked
# machine-written, and evidence of NOTHING about rights. A rebuild reads it and
# re-captions only what it does not hold — so the dollar is paid once.
# ---------------------------------------------------------------------------


class BrainTrackedCaptionRecordTests(unittest.TestCase):
    """§BH43(a): the record is tracked evidence, deterministic, and it is not var/."""

    @staticmethod
    def _caption_scope():
        spec = _ilu.spec_from_file_location("brain_caption_scope_tracked",
                                            _DJANGO_ROOT / "tools" / "brain" / "caption_scope.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_the_record_is_tracked_by_git_and_var_is_not_where_it_lives(self):
        C = self._caption_scope()
        for path in (C.TRACKED_JSONL, C.TRACKED_INDEX):
            self.assertTrue(path.is_file(), "§BH43(a): the tracked record is missing at %s" % path)
            rel = str(path.relative_to(_GIT_ROOT))
            tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                                     cwd=_GIT_ROOT, capture_output=True, text=True)
            self.assertEqual(tracked.returncode, 0, "%s is not tracked by git" % rel)
            self.assertFalse(rel.startswith("var/"), "the record must not live under the ignored var/")

    def test_a_write_that_would_drop_captions_is_refused(self):
        """§BH55 Phase 4 — the floor. A caption is money already spent; this writer rewrites the pair whole.

        Found by running §BH43(b)'s own first step: `caption_scope.py --probe` printed "Nothing was spent" and
        left the 396-row tracked record at ZERO BYTES, because it captioned nothing and had loaded no prior.
        Everything here happens in a temporary directory; the real record is never the subject.
        """
        C = self._caption_scope()
        with _tempfile.TemporaryDirectory() as d:
            here = _pathlib.Path(d)
            full = {"captions": [{"path": "a/%d.jpg" % i, "paths": ["a/%d.jpg" % i],
                                  "sha256": "%064x" % i, "caption": {"subject": "x"}} for i in range(5)]}
            C.write_tracked(full, here)
            self.assertEqual(len(C.read_tracked(here)["captions"]), 5)
            with self.assertRaises(C.RecordWouldShrink) as caught:
                C.write_tracked({"captions": []}, here)
            self.assertIn("5", str(caught.exception))
            self.assertEqual(len(C.read_tracked(here)["captions"]), 5, "the refusal wrote nothing")
            C.write_tracked({"captions": full["captions"][:2]}, here, allow_shrink=True)
            self.assertEqual(len(C.read_tracked(here)["captions"]), 2, "a caller that MEANS it still can")

    def test_the_tracked_record_is_read_without_being_asked_for(self):
        """§BH43(a): 'the rebuild reads the tracked record … so the dollar is paid once' — by default, not by flag.

        The prior was loaded only under --resume, which is what let a run that bought nothing overwrite it. This
        asserts the default read itself; that the run USES it is enforced from the other side, by the floor above —
        a run that failed to load the prior would carry fewer captions than the file holds and be refused.
        """
        C = self._caption_scope()
        record = C._read_record()
        self.assertIsNotNone(record, "the default read must find the tracked pair with no path and no flag")
        self.assertGreater(len(record["captions"]), 0)

    def test_the_record_is_keyed_by_content_and_carries_every_path(self):
        C = self._caption_scope()
        record = C.read_tracked()
        self.assertIsNotNone(record)
        rows = record["captions"]
        shas = [c["sha256"] for c in rows]
        self.assertEqual(len(shas), len(set(shas)), "one line per CONTENT, never one per path")
        self.assertEqual(shas, sorted(shas), "the lines are sorted by sha256 so a diff reads as changes")
        # The record may describe anything the audit covers; what the CURRENT scope demands is
        # coverage()'s question, not this one. Stated against the audited universe so it holds
        # whether or not the §BH43(b) REFERENCE arm is switched on.
        prev = C.REFERENCE_IN_SCOPE          # read at import, so the module attribute is the switch
        C.REFERENCE_IN_SCOPE = True
        try:
            audited = {r["path"] for r in C.scope()}
        finally:
            C.REFERENCE_IN_SCOPE = prev
        recorded = {p for c in rows for p in c["paths"]}
        self.assertTrue(recorded <= audited,
                        "a recorded path outside the audited material: %s" % sorted(recorded - audited)[:3])
        self.assertGreater(len(recorded), len(rows), "the duplicate paths are recorded, not collapsed away")
        for c in rows[:50]:
            self.assertEqual(c["path"], c["paths"][0], "path is derived from paths, never stored twice")

    def test_the_record_says_it_is_machine_written_and_proves_nothing_about_rights(self):
        C = self._caption_scope()
        record = C.read_tracked()
        self.assertEqual(record["record_type"], C.TRACKED_RECORD_TYPE)
        self.assertIn("MACHINE-WRITTEN", record["tracked_note"])
        self.assertIn("rights", record["tracked_note"].lower())
        for c in record["captions"]:
            self.assertTrue(c.get("machine_written"), "every row is marked machine-written")
            self.assertTrue(c.get("rights_note"), "every row carries its rights note")
        # the tier travels from the tier record, never from the caption
        tiers = {c.get("tier") for c in record["captions"]}
        self.assertTrue(tiers <= {"PRODUCTION", "REFERENCE", "NOT_IN_TIER_RECORD", None},
                        "an unexpected tier in the record: %s" % tiers)

    def test_writing_what_was_read_reproduces_the_same_bytes(self):
        """Deterministic: the record is a function of its content, not of when it was written."""
        C = self._caption_scope()
        before = (C.TRACKED_JSONL.read_bytes(), C.TRACKED_INDEX.read_bytes())
        with _tempfile.TemporaryDirectory() as d:
            out = _pathlib.Path(d)
            C.write_tracked(C.read_tracked(), out)
            after = ((out / C.TRACKED_JSONL.name).read_bytes(), (out / C.TRACKED_INDEX.name).read_bytes())
        self.assertEqual(before, after, "a re-write of the same record must produce the same bytes")

    def test_the_record_carries_no_hash_of_the_register(self):
        """§BH40(b): no tracked file may carry a hash of the register."""
        register = (_GIT_ROOT / "OWNER_BLOCKER_CLEARANCE.md").read_bytes()
        digest = _hashlib.sha256(register).hexdigest()
        C = self._caption_scope()
        for path in (C.TRACKED_JSONL, C.TRACKED_INDEX):
            body = path.read_text(encoding="utf-8")
            # 64/32/16 only: 12 and 8 hex characters are not a hash of the register, and
            # the record carries thousands of image digests — a chance hit would read as a
            # governance violation and cost a gate cycle.
            for n in (64, 32, 16):
                self.assertNotIn(digest[:n], body, "%s carries a hash of the register" % path.name)

    def test_a_resumed_run_against_the_tracked_record_would_pay_for_nothing(self):
        """The ZERO-dollar claim as a pure set question, asked without spending a cent."""
        C = self._caption_scope()
        record = C.read_tracked()
        held = {c["sha256"] for c in record["captions"]}
        named = {u["sha256"] for u in record["scope"]["uncaptionable"]}
        in_scope = {r["sha256"] for r in C.scope()}
        self.assertEqual(sorted(in_scope - held - named), [],
                         "a resumed run would have to pay for these contents")
        self.assertGreater(record["spend_usd"], 0.0, "the record states the dollars already spent")

    def test_the_rebuild_read_the_tracked_record_and_spent_nothing(self):
        S = _load_brain_sources()
        captions = (S.read_freshness().get("stats") or {}).get("captions") or {}
        self.assertEqual(captions.get("state"), "BUILT")
        self.assertTrue(captions.get("tracked"), "§BH43(a): the index was built from the tracked record")
        self.assertEqual(captions.get("record"), "docs/design_intelligence/captions")
        self.assertEqual(captions.get("spent_this_rebuild_usd"), 0.0,
                         "a rebuild reads the record and spends no dollar")


# ---------------------------------------------------------------------------
# §BH43(b), before it spends — THE SAMPLE IS PAID FOR, SO THE SAMPLE IS KEPT.
#
# caption_scope.main() bought its sample and then discarded it at both early
# returns: the cap refusal and the sample-only exit. §BH42 paid $1.0059 and
# recorded $0.9816; the difference bought ten captions that were thrown away.
# (b) is where it would have bitten, because the owner's $15 stop is MEANT to
# fire — and stopping would have burned the sample, so the authorised re-run
# paid for the same images twice. That is the opposite of §BH43(a)'s sentence,
# "so the dollar is paid once". These tests drive the real main() with a fake
# renderer and a fake model, so they cost nothing to run.
# ---------------------------------------------------------------------------


class BrainSampleIsKeptTests(unittest.TestCase):
    """A refusal must refuse. It must not also burn what it already bought."""

    @staticmethod
    def _caption_scope():
        spec = _ilu.spec_from_file_location("brain_caption_scope_keep",
                                            _DJANGO_ROOT / "tools" / "brain" / "caption_scope.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    class _Usage:
        input_tokens, output_tokens = 1500, 200

    def _rig(self, C, tmp, contents=6):
        """Point the module at a scratch scope of tiny images and a model that never runs."""
        from PIL import Image
        rows = [{"path": "materials/fake/%d.png" % i, "sha256": "%064x" % i,
                 "set": "design_254", "tier": "REFERENCE", "tier_source": "test",
                 "grant_terms_class": None} for i in range(contents)]
        C.scope = lambda: rows
        C.render = lambda rel: (Image.new("RGB", (24, 24), (200, 40, 40)), "fake", None)
        C.api_key = lambda: "not-a-real-key"
        calls = []

        def fake_caption_one(client, jpeg):
            calls.append(1)
            return {"subject": "a fake swatch", "text_seen": []}, None, self._Usage()

        C.caption_one = fake_caption_one
        C.RENDERS = _pathlib.Path(tmp) / "renders"
        C.RENDERS.mkdir(parents=True, exist_ok=True)
        return rows, calls

    def test_a_refused_projection_keeps_the_captions_it_already_paid_for(self):
        C = self._caption_scope()
        with _tempfile.TemporaryDirectory() as tmp:
            rec = _pathlib.Path(tmp) / "record"
            rec.mkdir()
            _rows, calls = self._rig(C, tmp)
            # a cap far below what six images project to: the run must REFUSE
            rc = C.main(["--sample", "2", "--run", "--cap", "0.0000001", "--record", str(rec)])
            record = C.read_tracked(rec)          # read INSIDE: the temp dir dies with the block
        self.assertEqual(rc, 2, "a projection over the cap must still refuse")
        self.assertEqual(len(calls), 2, "only the sample was paid for; the full run did not begin")
        self.assertIsNotNone(record, "§BH43(b): the refusal discarded the captions it had paid for")
        self.assertEqual(len(record["captions"]), 2, "both sampled captions were kept")
        self.assertGreater(record["spend_usd"], 0.0, "the dollars paid are recorded, not lost")

    def test_a_sample_only_run_keeps_what_it_bought(self):
        C = self._caption_scope()
        with _tempfile.TemporaryDirectory() as tmp:
            rec = _pathlib.Path(tmp) / "record"
            rec.mkdir()
            _rows, calls = self._rig(C, tmp)
            rc = C.main(["--sample", "3", "--record", str(rec)])       # no --run
            record = C.read_tracked(rec)
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)
        self.assertIsNotNone(record, "a sample-only run must keep the captions it paid for")
        self.assertEqual(len(record["captions"]), 3)

    def test_a_crash_mid_run_keeps_every_caption_already_paid_for(self):
        """The third exit. §BH43(b)'s first REFERENCE run died on a 400 — the API balance ran
        out — after roughly $0.15 of captions, and every one of them was lost, because the
        exception went straight past the write. A refusal and a sample-only exit were covered;
        a crash was not, and a crash is the one that actually took dollars with it."""
        C = self._caption_scope()

        class Broke(RuntimeError):
            pass

        with _tempfile.TemporaryDirectory() as tmp:
            rec = _pathlib.Path(tmp) / "record"
            rec.mkdir()
            _rows, calls = self._rig(C, tmp, contents=9)
            good = C.caption_one

            def dies_on_the_seventh(client, jpeg):
                if len(calls) >= 6:
                    raise Broke("your credit balance is too low")
                return good(client, jpeg)

            C.caption_one = dies_on_the_seventh
            with self.assertRaises(Broke):
                C.main(["--sample", "2", "--run", "--cap", "50", "--record", str(rec)])
            record = C.read_tracked(rec)
        self.assertIsNotNone(record, "the crash discarded captions that had been paid for")
        self.assertEqual(len(record["captions"]), 6,
                         "every caption bought before the crash is kept, and no more")
        self.assertGreater(record["spend_usd"], 0.0, "the dollars paid are recorded, not lost")

    def test_the_kept_sample_is_not_paid_for_again_on_the_authorised_re_run(self):
        """The whole point: after a refusal, the owner's word must not cost the sample twice."""
        C = self._caption_scope()
        with _tempfile.TemporaryDirectory() as tmp:
            rec = _pathlib.Path(tmp) / "record"
            rec.mkdir()
            _rows, calls = self._rig(C, tmp, contents=6)
            self.assertEqual(C.main(["--sample", "2", "--run", "--cap", "0.0000001",
                                     "--record", str(rec)]), 2)
            paid_before = len(calls)
            rc = C.main(["--sample", "2", "--run", "--resume", "--cap", "50",
                         "--over-cap-authorised", "--record", str(rec)])
            record = C.read_tracked(rec)
        self.assertEqual(rc, 0)
        self.assertEqual(paid_before, 2)
        self.assertEqual(len(calls), 6, "six contents cost six calls in total, not eight")
        self.assertEqual(len(record["captions"]), 6)


class BrainProbeAndNamedPathsTests(unittest.TestCase):
    """§BH43(b): the half of the work that costs nothing, and the duplicate it stopped losing."""

    @staticmethod
    def _caption_scope():
        spec = _ilu.spec_from_file_location("brain_caption_scope_probe",
                                            _DJANGO_ROOT / "tools" / "brain" / "caption_scope.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_an_uncaptionable_content_carries_every_path_that_holds_those_bytes(self):
        """A content named once must account for BOTH copies. Counting only the first left the
        second reading UNCAPTIONED — the same collapse the caption rows were fixed for in §BH42,
        which the uncaptionable list never got. 32 named contents lie at more than one path."""
        C = self._caption_scope()
        named = C.read_tracked()["scope"]["uncaptionable"]
        self.assertTrue(named, "the record names what no renderer opened")
        multi = [u for u in named if len(u.get("paths") or []) > 1]
        self.assertTrue(multi, "duplicates exist in the corpus and must be recorded as such")
        for u in named:
            self.assertIn("paths", u, "every named content lists its paths")
            self.assertIn(u["path"], u["paths"], "the headline path is one of them")
            self.assertEqual(u["paths"], sorted(u["paths"]))
            self.assertTrue(u.get("note"), "named WITH ITS REASON, never merely omitted")

    def test_every_named_reason_says_which_class_it_belongs_to(self):
        C = self._caption_scope()
        named = C.read_tracked()["scope"]["uncaptionable"]
        classes = {u["note"].split(":")[0] for u in named}
        self.assertTrue(classes <= {"UNCAPTIONABLE", "NOT_AN_IMAGE_FORMAT",
                                    "POSTSCRIPT_NEEDS_GHOSTSCRIPT", "MOVING_IMAGE"},
                        "an unclassified reason: %s" % (classes,))
        # §BH55(a): this asserted MORE THAN 1000 POSTSCRIPT_NEEDS_GHOSTSCRIPT reasons, and that was a true
        # diagnosis of a machine WITHOUT Ghostscript — 648 .eps and 671 .ai refused for one cause. `gs 10.08.0` is
        # installed now and renders all 1,319 of them, so the count is ZERO and the remaining reasons are the
        # formats no renderer opens. The old claim is kept here because it is why the number moved, and the new
        # assertion is what is true: a PostScript reason on a machine that HAS Ghostscript would be a defect.
        ps = [u for u in named if u["note"].startswith("POSTSCRIPT_NEEDS_GHOSTSCRIPT")]
        import shutil as _shutil
        if _shutil.which("gs"):
            self.assertEqual(ps, [], "Ghostscript is installed, so no file may be refused for wanting it")
        self.assertTrue(any(u["note"].startswith("NOT_AN_IMAGE_FORMAT") for u in named),
                        "the fonts, archives and text files are still named with their reason")

    def test_the_probe_makes_no_api_call_and_still_writes_the_record(self):
        """--probe renders, names and records while spending nothing, so a census survives a
        later failure to buy captions. It runs with no key and no balance."""
        C = self._caption_scope()
        with _tempfile.TemporaryDirectory() as tmp:
            from PIL import Image
            rec = _pathlib.Path(tmp) / "record"
            rec.mkdir()
            rows = [{"path": "materials/fake/%d.png" % i, "sha256": "%064x" % i, "set": "reference",
                     "tier": "REFERENCE", "tier_source": "test", "grant_terms_class": None}
                    for i in range(4)]
            C.scope = lambda: rows
            C.render = lambda rel: (Image.new("RGB", (16, 16), (10, 90, 200)), "fake", None)
            C.RENDERS = _pathlib.Path(tmp) / "renders"
            C.RENDERS.mkdir()
            called = []
            C.caption_one = lambda *a, **k: called.append(1)
            C.api_key = lambda: (_ for _ in ()).throw(AssertionError("--probe must not need a key"))
            rc = C.main(["--probe", "--record", str(rec)])
            wrote = (rec / "INDEX.json").is_file()
        self.assertEqual(rc, 0)
        self.assertEqual(called, [], "the probe made an API call")
        self.assertTrue(wrote, "the probe wrote no record")


# ---------------------------------------------------------------------------
# §BH43(c) — THE VAULT. Generated markdown, Obsidian-ready, DERIVED AND
# DISPOSABLE: a rebuild step emits it, nothing in it is hand-edited, and a
# regeneration from scratch reproduces it byte-for-byte. The freshness gate
# covers it, so a note that has drifted from its sources refuses the commit.
#
# It is IGNORED, by §BH43(a)'s own principle: track what costs dollars to
# remake, ignore what a machine remakes for nothing. Tracking ~7,300 derived
# notes would also put hundreds of file changes into every register append and
# make §AC's one-concern-per-commit unreadable.
# ---------------------------------------------------------------------------


class BrainVaultTests(unittest.TestCase):
    """§BH43(c): the vault is generated, deterministic, and it holds the placement line."""

    @staticmethod
    def _vault():
        spec = _ilu.spec_from_file_location("brain_vault", _DJANGO_ROOT / "tools" / "brain" / "vault.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_the_vault_exists_and_is_ignored_rather_than_tracked(self):
        V = self._vault()
        self.assertTrue(V.VAULT.is_dir(), "§BH43(c): no brain_vault/ — run tools/brain/rebuild.py")
        ignored = subprocess.run(["git", "check-ignore", "-q", "brain_vault/index.md"],
                                 cwd=_GIT_ROOT, capture_output=True)
        self.assertEqual(ignored.returncode, 0, "brain_vault/ must be git-ignored")
        tracked = subprocess.run(["git", "ls-files", "--", "brain_vault"],
                                 cwd=_GIT_ROOT, capture_output=True, text=True)
        self.assertEqual(tracked.stdout.strip(), "", "no vault note may be tracked")

    def test_every_note_declares_where_it_was_generated_from(self):
        V = self._vault()
        notes = sorted(V.VAULT.rglob("*.md"))
        self.assertGreater(len(notes), 1000)
        for p in notes[::37]:                       # a deterministic stride, not a random sample
            head = p.read_text(encoding="utf-8")[:1200]
            self.assertTrue(head.startswith("---\n"), "%s has no frontmatter" % p.name)
            self.assertIn("generated_from:", head)
            self.assertIn("generated_at_commit:", head)
            self.assertIn("hand_edited: false", head)
            self.assertIn("generator: tools/brain/vault.py", head)

    def test_no_note_stamps_a_wall_clock_and_every_commit_is_resolvable(self):
        """A value that moves on its own defeats byte-identical regeneration. The commit must be
        a real sha, or an honest statement that the source is not tracked — never blank."""
        V = self._vault()
        stamps = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        commit = re.compile(r"^generated_at_commit: (.+)$", re.M)
        seen = 0
        for p in sorted(V.VAULT.rglob("*.md"))[::53]:
            frontmatter = p.read_text(encoding="utf-8").split("\n---\n", 1)[0]
            self.assertIsNone(stamps.search(frontmatter),
                              "%s stamps a wall clock into its header" % p.name)
            m = commit.search(frontmatter)
            self.assertIsNotNone(m, "%s has no generated_at_commit" % p.name)
            value = m.group(1).strip()
            self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", value)
                            or value.startswith("untracked:sha256:") or value == "absent",
                            "%s cites an unresolvable commit %r" % (p.name, value))
            seen += 1
        self.assertGreater(seen, 20)

    def test_the_freshness_record_agrees_with_the_vault_on_disk(self):
        """The gate: notes that have drifted from their sources refuse the commit."""
        S = _load_brain_sources()
        V = self._vault()
        recorded = ((S.read_freshness() or {}).get("stats") or {}).get("vault") or {}
        self.assertEqual(recorded.get("record_type"), V.VAULT_RECORD_TYPE,
                         "§BH43(c): the freshness record carries no vault — rebuild")
        on_disk = V.digest()
        self.assertIsNotNone(on_disk)
        self.assertEqual(on_disk["sha256"], recorded["sha256"],
                         "VAULT_STALE — brain_vault/ disagrees with the record it was built with; "
                         "a note was hand-edited, or the sources moved. Run tools/brain/rebuild.py")
        self.assertEqual(on_disk["notes"], recorded["notes"])

    def test_a_hand_edited_note_is_refused_negative_control(self):
        """The control the ruling asks for: edit one note, and the digest must move."""
        V = self._vault()
        before = V.digest()["sha256"]
        with _tempfile.TemporaryDirectory() as d:
            copy = _pathlib.Path(d) / "vault"
            copy.mkdir()
            victim = sorted(V.VAULT.rglob("*.md"))[0]
            (copy / "a.md").write_text(victim.read_text(encoding="utf-8"), encoding="utf-8")
            clean = V.digest(copy)["sha256"]
            (copy / "a.md").write_text(victim.read_text(encoding="utf-8") + "\nhand edit\n",
                                       encoding="utf-8")
            edited = V.digest(copy)["sha256"]
        self.assertNotEqual(clean, edited, "a hand-edited note must move the digest")
        self.assertEqual(V.digest()["sha256"], before, "the real vault was not disturbed")

    def test_a_missing_note_is_refused_negative_control(self):
        V = self._vault()
        with _tempfile.TemporaryDirectory() as d:
            copy = _pathlib.Path(d) / "vault"
            copy.mkdir()
            for i, src in enumerate(sorted(V.VAULT.rglob("*.md"))[:4]):
                (copy / ("n%d.md" % i)).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            full = V.digest(copy)["sha256"]
            (copy / "n0.md").unlink()
            short = V.digest(copy)["sha256"]
        self.assertNotEqual(full, short, "a deleted note must move the digest")

    def test_two_regenerations_from_scratch_reproduce_each_other_byte_for_byte(self):
        """The ruled proof: 'a regeneration from scratch reproduces it byte-identically'.

        Both runs are SEPARATE PROCESSES with DIFFERENT PYTHONHASHSEEDs, because CPython
        randomises string hashing per process: a set that reaches the output passes a
        regeneration inside one process and fails across two.

        The comparison is between the two fresh trees, NOT against vault/ on disk. The vault
        carries each front's commits, so it is a function of the repository state it was built
        at — and the gate rebuilds BEFORE it commits, which means vault/ on disk is one commit
        behind the moment its own commit lands. That staleness is expected and is covered by
        the freshness test above, which compares vault/ against the record it was built with.
        Asserting a fresh regeneration equals a tree built at a different HEAD would assert
        that HEAD never moves, which is not the ruling and is not true.
        """
        def regenerate(seed, dest):
            script = (
                "import sys, sqlite3, json\n"
                "sys.path.insert(0, %r)\n"
                "import vault\n"
                "con = sqlite3.connect('file:%s?mode=ro', uri=True)\n"
                "r = vault.emit(con, %r)\n"
                "print(json.dumps([r['sha256'], r['notes']]))\n"
                % (str(_DJANGO_ROOT / "tools" / "brain"),
                   str(_load_brain_sources().DB_PATH), str(dest))
            )
            env = dict(_os.environ, PYTHONHASHSEED=seed)
            r = subprocess.run([str(_GIT_ROOT / "bbrose_design_os" / "venv" / "bin" / "python"),
                                "-c", script], capture_output=True, text=True, env=env,
                               cwd=str(_GIT_ROOT))
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            return _json.loads(r.stdout.strip().splitlines()[-1])

        with _tempfile.TemporaryDirectory() as d:
            a_dir, b_dir = _pathlib.Path(d) / "a", _pathlib.Path(d) / "b"
            a_sha, a_n = regenerate("1", a_dir)
            b_sha, b_n = regenerate("424242", b_dir)
            self.assertEqual(a_sha, b_sha,
                             "§BH43(c): two regenerations from scratch did not agree")
            self.assertEqual(a_n, b_n)
            self.assertGreater(a_n, 1000)
            diff = subprocess.run(["diff", "-r", str(a_dir), str(b_dir)],
                                  capture_output=True, text=True)
            self.assertEqual(diff.returncode, 0,
                             "diff -r found differences:\n%s" % diff.stdout[:2000])

    def test_every_slug_is_unique_so_no_two_things_share_a_note(self):
        """60 real group names collide once unsafe characters are folded — one of them 20 ways.
        The slug carries a digest of its full key, so uniqueness is a property of the key."""
        V = self._vault()
        names = [p.name for p in V.VAULT.rglob("*.md")]
        self.assertEqual(len(names), len(set(names)),
                         "two notes share a filename: %s"
                         % [n for n, c in _collections.Counter(names).items() if c > 1][:5])

    def test_the_line_holds_no_reference_byte_is_placed_in_a_note(self):
        """THE LINE: a thumbnail is a rendered byte. Only PRODUCTION may carry one; every other
        tier is NAMED as withheld rather than quietly omitted."""
        S = _load_brain_sources()
        V = self._vault()
        recorded = ((S.read_freshness() or {}).get("stats") or {}).get("vault") or {}
        self.assertGreater(recorded.get("thumbnails_withheld", 0), 0,
                           "no withholding recorded — the rule was not exercised")
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            production = {r[0] for r in con.execute(
                "SELECT sha256 FROM materials WHERE tier = 'PRODUCTION' AND sha256 IS NOT NULL")}
        finally:
            con.close()
        embed_re = re.compile(r"!\[\[([0-9a-f]{16})\.jpg\]\]")
        drawn = set()
        for p in sorted((V.VAULT / "materials").rglob("*.md")):
            for m in embed_re.finditer(p.read_text(encoding="utf-8")):
                drawn.add(m.group(1))
        self.assertTrue(drawn, "no thumbnail was drawn at all — the rule is untested")
        prefixes = {s[:16] for s in production}
        self.assertTrue(drawn <= prefixes,
                        "a NON-PRODUCTION render was placed in a note: %s" % sorted(drawn - prefixes)[:5])

    def test_no_front_tagged_commit_is_skipped_by_the_pattern_that_files_it(self):
        """§BH55 Phase 4 — a commit is filed under its front, whatever its id's parts.

        §BH45(e)(3) queued this as the vault-note pattern skip and quoted ONE commit. Measured against the log, the
        pattern skipped 21 of the 180 front-tagged subjects — every id with a second part or a compound — and every
        §BH44 commit was among them, so the vault carried no §BH44 note at all.

        The pattern is the module's own (`_vault()` loads the file that runs): a test that restated the expression
        would pass while the generator went on skipping.
        """
        V = self._vault()
        log = subprocess.run(["git", "log", "--format=%s", "--no-merges"],
                             cwd=_GIT_ROOT, capture_output=True, text=True)
        self.assertEqual(log.returncode, 0, log.stderr)
        tagged = [s for s in log.stdout.splitlines() if re.match(r"^\s*\w+\(§", s)]
        self.assertGreater(len(tagged), 150, "the log must carry the programme's own commits")
        skipped = [s for s in tagged if not V._FRONT_RE.match(s)]
        self.assertEqual(skipped, [], "%d of %d front-tagged commits reach no note; first: %s"
                         % (len(skipped), len(tagged), skipped[:3]))

    def test_the_front_id_is_read_without_its_parts(self):
        """What group 1 must be for front_notes() to file the commit under the right front."""
        V = self._vault()
        for subject, front in (("feat(§BH50(f)(8) line 6): X", "§BH50"),
                               ("feat(§BH44(c)+(d)): X", "§BH44"),
                               ("test(§BH52(b)(d) slice 1): X", "§BH52"),
                               ("fix(§BH48(b)(i)): X", "§BH48"),
                               ("feat(§BH30(h)(i)(j)): X", "§BH30"),
                               ("feat(§BH55 p4-vault): X", "§BH55"),
                               # §BH69: a tag that quotes his words, parentheses and all (606b54f)
                               ('feat(§BH69(2), his words "in words (layout, colours, mood)"): X', "§BH69")):
            m = V._FRONT_RE.match(subject)
            self.assertIsNotNone(m, subject)
            self.assertEqual(m.group(1), front, subject)

    def test_the_front_the_queue_named_has_a_note(self):
        """§BH44's every front-tagged commit was skipped, so the front the queue named was the absent one."""
        V = self._vault()
        fronts = {p.name.split("-")[0] for p in (V.VAULT / "fronts").glob("*.md")}
        self.assertIn("§BH44", fronts, "§BH44 has no note — the skip is back, or the vault is stale")


# ---------------------------------------------------------------------------
# brain.ruling — THE REGISTER RULES, THE QUEUE QUEUES.
#
# server.py selected a section by id with no path filter. `sections` holds both
# OWNER_BLOCKER_CLEARANCE.md (838 rows) and OWNER_REVIEW_QUEUE.md (556), and 65
# ids head a block in BOTH; the tiebreak `ORDER BY level, line_start` chose
# between two documents by something that encodes nothing about authority and
# returned the QUEUE for 23 of them. It had no harmless case: chunker gates
# `measurable` on the register (chunker.py:92) and a non-measurable row is
# forced to UNCLASSIFIED (chunker.py:163), so every one of the 23 reported a
# LIVE ruling as UNCLASSIFIED. §BC (the transcription discipline) and §AD0(a)
# (the 8-leg prediction discipline) were two of them — CLAUDE.md's standing
# line says to cite brain.ruling's measured status, so this arc's own two
# governing rules answered UNCLASSIFIED.
# ---------------------------------------------------------------------------


class BrainRulingDocumentTests(unittest.TestCase):

    @staticmethod
    def _server():
        spec = _ilu.spec_from_file_location("brain_server_ruling",
                                            _DJANGO_ROOT / "tools" / "brain" / "server.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def _dual_ids():
        S = _load_brain_sources()
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            return [r[0] for r in con.execute(
                "SELECT id FROM sections GROUP BY id HAVING COUNT(DISTINCT path) > 1 ORDER BY id")]
        finally:
            con.close()

    def test_an_id_headed_in_both_documents_is_answered_by_the_register(self):
        server = self._server()
        dual = self._dual_ids()
        self.assertGreater(len(dual), 20, "the case this pins must exist to be pinned")
        for sid in dual:
            r = server.tool_ruling({"section": sid, "text": False})
            self.assertEqual(r["file"], "OWNER_BLOCKER_CLEARANCE.md",
                             "brain.ruling(%s) answered from %s — the register rules" % (sid, r["file"]))

    def test_the_status_returned_is_the_registers_measured_status(self):
        """The defect's real cost: it reported LIVE rulings as UNCLASSIFIED."""
        S = _load_brain_sources()
        server = self._server()
        con = sqlite3.connect("file:%s?mode=ro" % S.DB_PATH, uri=True)
        try:
            for sid in self._dual_ids():
                want = con.execute(
                    "SELECT status FROM sections WHERE id = ? AND path = 'OWNER_BLOCKER_CLEARANCE.md' "
                    "ORDER BY level, line_start LIMIT 1", (sid,)).fetchone()
                got = server.tool_ruling({"section": sid, "text": False})
                self.assertEqual(got["status"], want[0],
                                 "brain.ruling(%s) said %r; the register measures %r"
                                 % (sid, got["status"], want[0]))
        finally:
            con.close()

    def test_the_two_disciplines_this_arc_runs_on_answer_live(self):
        """The named regression. Both were UNCLASSIFIED before the fix."""
        server = self._server()
        for sid in ("§BC", "§AD0(a)"):
            r = server.tool_ruling({"section": sid, "text": False})
            self.assertEqual(r["status"], "LIVE", "%s must answer LIVE" % sid)
            self.assertEqual(r["file"], "OWNER_BLOCKER_CLEARANCE.md")

    def test_the_other_document_is_named_and_not_silently_discarded(self):
        server = self._server()
        for sid in self._dual_ids():
            r = server.tool_ruling({"section": sid, "text": False})
            self.assertIn("also_headed_in", r,
                          "brain.ruling(%s) dropped the queue's block instead of naming it" % sid)
            self.assertTrue(r["also_headed_in"])
            for a in r["also_headed_in"]:
                self.assertNotIn("OWNER_BLOCKER_CLEARANCE.md", a["cite"])
            self.assertIn("register rules", r["ruling_document"])

    def test_an_id_in_one_document_only_gains_no_spurious_second_block(self):
        server = self._server()
        for sid in ("§BH43", "§BH42", "§AC"):
            r = server.tool_ruling({"section": sid, "text": False})
            self.assertNotIn("also_headed_in", r,
                             "%s heads a block in one document only" % sid)


# --- archive/ is never imported (the owner's goal of 2026-10-29, §0: "After the switch, a check fails the build if any
# live code imports from archive/") -----------------------------------------------------------------------------------
#
# archive/ sits at the GIT root, beside the Django root: a sys.path entry or a relative import that reaches it would
# load an archived engine as plausibly as a live one, and nothing would say so. The check is behavioural, not a
# source-string guard: a fresh interpreter imports every module the site and the worker can load (as
# docs/consolidation/import_check.py does) and then asks every loaded module where its file is.

_ARCHIVE_SWEEP = r'''
import importlib, json, os, sys
from pathlib import Path
app, archive, extra_path, mode = Path(sys.argv[1]), Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4]
extra = sys.argv[5:]
sys.path.insert(0, str(app))
if extra_path:
    sys.path.insert(0, extra_path)
os.chdir(app)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
names = []
if mode == 'all':
    for base in ('apps', 'config'):
        for path in sorted((app / base).rglob('*.py')):
            rel = path.relative_to(app)
            if any(p in ('tests', 'migrations', '__pycache__') for p in rel.parts) or rel.name.startswith('test'):
                continue
            name = '.'.join(rel.with_suffix('').parts)
            names.append(name[:-9] if name.endswith('.__init__') else name)
failed = {}
for name in names + extra:
    try:
        importlib.import_module(name)
    except BaseException as error:
        failed[name] = '%s: %s' % (type(error).__name__, str(error)[:120])
loaded = sorted(n for n, m in list(sys.modules.items())
                if getattr(m, '__file__', None) and Path(m.__file__).resolve().is_relative_to(archive))
print(json.dumps({'imported': len(names) + len(extra) - len(failed), 'failed': failed, 'from_archive': loaded}))
'''


def _archive_sweep(archive, mode='all', extra_path='', extra=()):
    import json
    import sys
    out = subprocess.run([sys.executable, '-c', _ARCHIVE_SWEEP, DJANGO_ROOT, archive, extra_path, mode, *extra],
                         capture_output=True, text=True, cwd=DJANGO_ROOT, timeout=900)
    if out.returncode != 0:
        raise AssertionError('the sweep itself failed: ' + out.stderr[-2000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


class ArchiveIsNeverImportedTests(unittest.TestCase):
    def test_no_live_module_loads_anything_from_archive(self):
        result = _archive_sweep(os.path.join(GIT_ROOT, 'archive'))
        self.assertGreater(result['imported'], 500, 'the sweep imported too little to mean anything')
        # the only modules that cannot import are the Blender scripts, which need Blender's own bpy
        self.assertEqual({name for name, error in result['failed'].items()
                          if not (name.startswith('apps.pipeline.services.blender_scripts.') and "'bpy'" in error)},
                         set(), result['failed'])
        self.assertEqual(result['from_archive'], [],
                         'live code loaded archived modules — switch them to the chain engine, never the reverse')

    def test_the_sweep_sees_a_module_loaded_from_an_archive(self):
        """The negative control: a module under an archive/ folder that something imports is named."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, 'archive', 'consolidation', 'retire', 'services')
            os.makedirs(folder)
            with open(os.path.join(folder, 'retired_engine_fixture.py'), 'w') as f:
                f.write('VALUE = 1\n')
            result = _archive_sweep(os.path.join(tmp, 'archive'), mode='extra', extra_path=folder,
                                    extra=('retired_engine_fixture',))
        self.assertEqual(result['from_archive'], ['retired_engine_fixture'])


# ---------------------------------------------------------------------------
# The engine map names only live files (the owner's goal of 2026-10-29, "Execution", §5)
# ---------------------------------------------------------------------------

#: The sections of docs/ENGINE_MAP.md that name live code; "Archived" and "How it is checked" are not among them.
ENGINE_MAP_LIVE_SECTIONS = ('## The ten engines of the chain', '## Held')


def _engine_map_faults(text):
    """Every backticked path in the map's live sections, with what is wrong with it. A path is a token holding a / or
    ending in .py; apps/…, pipeline/… and tools/… resolve under the Django root, a bare name beside the last apps/ path
    of its line resolves in that path's folder. A path into archive/, or one that is not on disk, is a fault."""
    faults, live = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            live = line.startswith(ENGINE_MAP_LIVE_SECTIONS)
            continue
        if not live:
            continue
        folder = None
        for token in re.findall(r'`([^`]+)`', line):
            if token == 'archive/' or not ('/' in token or token.endswith('.py')):
                continue
            if token.startswith('archive/') or '/archive/' in token:
                faults.append((token, 'names an archived file as live'))
                continue
            if token.startswith('apps/'):
                path = os.path.join(DJANGO_ROOT, token)
                folder = os.path.dirname(path)
            elif token.startswith(('pipeline/', 'dielines/', 'dashboard/', 'ire/')):
                path = os.path.join(DJANGO_ROOT, 'apps', token)
            elif token.startswith('tools/'):
                path = os.path.join(DJANGO_ROOT, token)
                if not os.path.exists(path):
                    path += '.py'
            elif folder is None:
                faults.append((token, 'a bare name with no apps/ path before it on its line'))
                continue
            else:
                path = os.path.join(folder, token)
            if not os.path.exists(path):
                faults.append((token, 'not on disk'))
            elif '%sarchive%s' % (os.sep, os.sep) in os.path.realpath(path):
                faults.append((token, 'names an archived file as live'))
    return faults


class EngineMapNamesOnlyLiveFilesTests(unittest.TestCase):
    def test_every_file_the_map_names_as_live_is_live(self):
        with open(os.path.join(GIT_ROOT, 'docs', 'ENGINE_MAP.md')) as f:
            text = f.read()
        self.assertGreaterEqual(len(re.findall(r'`apps/[^`]+\.py`', text)), 10, 'the map names too few engines to mean anything')
        self.assertEqual(_engine_map_faults(text), [])

    def test_a_map_naming_an_archived_or_missing_file_fails(self):
        """The negative control: an archived donor, a moved file and a missing one are each named."""
        text = ('## The ten engines of the chain\n'
                '| x | `archive/consolidation/boards/merged/round_ideas_brief.py` |\n'
                '| y | `apps/pipeline/services/round_ideas.py` |\n'
                '| z | `apps/dielines/geometry/engine.py`, `no_such_part.py` |\n'
                '## Archived\n'
                '| w | `apps/pipeline/services/round_ideas.py` |\n')
        self.assertEqual(_engine_map_faults(text), [
            ('archive/consolidation/boards/merged/round_ideas_brief.py', 'names an archived file as live'),
            ('apps/pipeline/services/round_ideas.py', 'not on disk'),
            ('no_such_part.py', 'not on disk')])
