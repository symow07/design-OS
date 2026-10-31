"""WI-0 / §AF4(b) — the rescued evidence is actually IN the repository.

Why this file exists, stated plainly because the lesson cost a commit:

`d4f93e0` is titled "twelve suite records rescued". It rescued **ten**.
`.gitignore:13` carries a bare `*.log` rule, `git add <directory>` applies it
without a word, and `git status --short` then reports the directory clean —
so two of the twelve records were copied onto disk, verified with `cmp`
against their origins, and silently left out of the commit that claimed to
contain them.

The verification in that commit was real and it was aimed at the wrong
boundary. It compared *copy on disk* to *origin on disk*. The claim being made
was about *content in git*. A rescue is only a rescue at the boundary you are
claiming about, and `/tmp` not surviving a reboot is exactly as fatal to an
untracked file inside the repository as it is to the original.

These assertions therefore run against `git ls-files`, not against `os.listdir`.
"""

import gzip
import hashlib
import json
import os
import subprocess
import unittest

INDEX_RELATIVE = "docs/roadmap/palt_m6/suite_records/INDEX.json"

#: The two ids registered as §AC4 flakes in
#: docs/roadmap/palt_m6/flake_register.json. Written out in full rather than
#: matched on the class name, because ten methods share that class and only
#: these two are registered -- a distinction §AF3 collapsed and §AG4 restored.
FLAKE_IDS = (
    "apps/pipeline/tests/test_browser_profile_editor.py::"
    "ConfirmationDialogBrowserTests::"
    "test_confirm_sends_one_request_and_freezes_into_confirmed_state",
    "apps/pipeline/tests/test_browser_profile_editor.py::"
    "ConfirmationDialogBrowserTests::test_dialog_traps_focus",
)


def _repo_root():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _tracked_files(root, subdir):
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "--", subdir],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        return None
    return {line for line in out.stdout.splitlines() if line}


def _sha256(path, opener=open):
    h = hashlib.sha256()
    with opener(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class SuiteRecordRescueIsTrackedTests(unittest.TestCase):
    """The rescue is measured where the claim is made: in git, not on disk."""

    @classmethod
    def setUpClass(cls):
        cls.root = _repo_root()
        if cls.root is None:
            raise unittest.SkipTest(
                "git is not available or this is not a work tree; the tracking "
                "assertions cannot be evaluated and are skipped rather than "
                "reported as passing")
        cls.pytest_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        cls.index_path = os.path.join(cls.pytest_root, INDEX_RELATIVE)
        cls.record_dir = os.path.dirname(cls.index_path)
        # path of the record directory relative to the GIT root, which is the
        # parent of the pytest root -- the two-root layout is load-bearing here
        cls.subdir = os.path.relpath(cls.record_dir, cls.root)

    def test_the_index_itself_exists_and_parses(self):
        self.assertTrue(os.path.exists(self.index_path), self.index_path)
        with open(self.index_path) as fh:
            data = json.load(fh)
        self.assertTrue(
            data["record_type"].startswith("suite_record_rescue_index/"),
            data["record_type"])
        self.assertIn("records", data)
        self.assertGreater(len(data["records"]), 0)

    def test_every_file_on_disk_in_the_record_directory_is_tracked_by_git(self):
        tracked = _tracked_files(self.root, self.subdir)
        self.assertIsNotNone(tracked, "git ls-files failed")
        tracked_names = {os.path.basename(p) for p in tracked}
        on_disk = {
            name for name in os.listdir(self.record_dir)
            if os.path.isfile(os.path.join(self.record_dir, name))
        }
        missing = sorted(on_disk - tracked_names)
        self.assertEqual(
            missing, [],
            "rescued evidence present on disk but NOT committed -- this is the "
            "exact failure d4f93e0 shipped, and .gitignore is the usual "
            "reason: " + ", ".join(missing))

    def test_every_record_the_index_names_is_tracked_by_git(self):
        with open(self.index_path) as fh:
            records = json.load(fh)["records"]
        untracked = []
        for record in records:
            rel_to_pytest_root = record["committed_path"]
            abs_path = os.path.join(self.pytest_root, rel_to_pytest_root)
            rel_to_git_root = os.path.relpath(abs_path, self.root)
            probe = subprocess.run(
                ["git", "-C", self.root, "ls-files", "--error-unmatch", "--",
                 rel_to_git_root],
                capture_output=True, text=True, timeout=30)
            if probe.returncode != 0:
                untracked.append(rel_to_git_root)
        self.assertEqual(
            untracked, [],
            "the index names records that are not in the repository: "
            + ", ".join(untracked))

    def test_the_compressed_record_still_decompresses_to_its_recorded_hash(self):
        """A compressed evidence file nobody can verify is a hope, not evidence."""
        with open(self.index_path) as fh:
            records = json.load(fh)["records"]
        compressed = [r for r in records if r.get("compressed")]
        self.assertEqual(
            len(compressed), 1,
            "exactly one record is expected to be compressed; if that changes, "
            "this assertion is the place to say so deliberately")
        record = compressed[0]
        path = os.path.join(self.pytest_root, record["committed_path"])
        self.assertEqual(
            _sha256(path, opener=gzip.open),
            record["sha256_of_uncompressed_content"],
            "the gz no longer decompresses to the content that was rescued")

    def test_the_index_records_the_measured_flake_failures_not_a_conclusion(self):
        """§AG5(d). The previous version of this test asserted §AF3's claim.

        §AF3 said no rescued record showed the two §AC4 flakes on a `FAILED`
        line. This test ran, went red, and the claim was withdrawn. What
        replaced it is not a better claim — it is the measurement. The index
        must carry the per-record counts, and those counts must match a fresh
        recount of the committed bytes, so that a change in the *evidence* is a
        red and a change in anybody's *opinion* is not.
        """
        with open(self.index_path) as fh:
            data = json.load(fh)
        for record in data["records"]:
            path = os.path.join(self.pytest_root, record["committed_path"])
            with open(path, "rb") as fh:
                raw = fh.read()
            if record.get("compressed"):
                raw = gzip.decompress(raw)
            failed = [line for line in raw.decode("utf-8", "replace").splitlines()
                      if line.startswith("FAILED")]
            self.assertEqual(
                len(failed), record["failed_line_count"],
                "FAILED-line count drifted from the index for "
                + record["committed_path"])
            recounted = sorted({
                flake_id for flake_id in FLAKE_IDS
                for line in failed if flake_id in line})
            self.assertEqual(
                recounted, record["registered_ac4_flake_ids_on_failed_lines"],
                "the index's flake-failure record no longer matches the bytes "
                "for " + record["committed_path"])

    def test_the_withdrawn_claim_is_not_still_sitting_in_the_index(self):
        """§AG5(a) struck a sentence. A struck sentence that is still shipped
        is not struck, and this repository has been caught once already
        believing a correction had propagated when it had not."""
        with open(self.index_path) as fh:
            data = json.load(fh)
        self.assertEqual(data["record_type"], "suite_record_rescue_index/1.1")
        self.assertIn("correction_at_v1_1", data)
        blob = json.dumps(data, ensure_ascii=False).lower()
        self.assertNotIn("occurrence, not failure", blob)
        self.assertNotIn("names_a_confirmation_dialog_flake", blob)

    def test_the_two_filtered_extracts_are_not_promoted_to_run_records(self):
        """A file with no summary line is an extract of a run, not a run.

        Two of the thirteen have no summary line: they are `FAILED` lines with
        the run they came from deleted. They are kept because they are evidence
        of something, and labelled because they are not evidence of a board.
        """
        with open(self.index_path) as fh:
            records = json.load(fh)["records"]
        extracts = [r for r in records if not r["is_a_run_record"]]
        self.assertEqual(
            len(extracts), 2,
            "expected exactly two filtered extracts; if this moves, say so "
            "deliberately rather than letting the label drift")
        for record in extracts:
            self.assertIsNone(record["summary_line"])
            self.assertGreater(record["failed_line_count"], 0)
