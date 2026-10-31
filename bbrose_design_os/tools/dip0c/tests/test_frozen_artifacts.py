"""Frozen milestone artifacts stay immutable under normal test runs (hygiene fix).

The DIP-0C3 milestone records under `docs/design_intelligence/dip0c/` are immutable inputs
to later tests. Ordinary tests must read them and never overwrite them; regeneration is
explicit and opt-in. These tests defend that contract; a CI step additionally runs the C3
suite and asserts `git diff --exit-code` on the tracked tree.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

from tools.dip0 import provenance as PROV
from tools.dip0c import config as C


def test_milestone_writes_are_redirected_off_the_frozen_tree_under_test():
    # the conftest points the write root at a temp dir, distinct from the frozen tree
    out = C.MILESTONE_OUTPUT_ROOT.resolve()
    frozen = C.DOCS_ROOT.resolve()
    assert out != frozen
    assert frozen not in out.parents and out != frozen


def test_guard_refuses_a_frozen_write_without_explicit_opt_in():
    with pytest.raises(C.FrozenMilestoneWrite):
        C.assert_not_frozen_milestone(C.DOCS_ROOT / "c3b2_reconciliation.json")
    with pytest.raises(C.FrozenMilestoneWrite):
        C.assert_not_frozen_milestone(C.DOCS_ROOT / "decisions" / "index.json")


def test_guard_allows_a_temp_write():
    # no raise for a path outside the frozen tree
    C.assert_not_frozen_milestone(C.MILESTONE_OUTPUT_ROOT / "c3b2_reconciliation.json")


def test_guard_allows_a_frozen_write_only_with_explicit_regeneration(monkeypatch):
    monkeypatch.setattr(C, "ALLOW_MILESTONE_WRITE", True)
    C.assert_not_frozen_milestone(C.DOCS_ROOT / "c3b2_reconciliation.json")  # no raise


def test_ledger_root_lives_under_the_injectable_output_root():
    from tools.dip0c import ledger as L
    assert str(L.LEDGER_ROOT).startswith(str(C.MILESTONE_OUTPUT_ROOT))


def test_frozen_reconciliations_are_readable_without_regeneration():
    # consolidation READS the committed milestone reconciliations; it must never write them
    from tools.dip0c import consolidate
    arts = consolidate.milestone_artifacts()
    assert isinstance(arts, dict)
    # at least the committed c3b2 reconciliation is present and readable
    assert (C.DOCS_ROOT / "c3b2_reconciliation.json").exists()


# --------------------------------------------------------------------------------------
# §BH55 Phase 4 — "the wall-clock fixtures". c3b3_known_limitations.md L8 recorded that
# re-running a pilot re-touches the committed examples' `recorded_at` / `generated_at`,
# and deferred the remedy it named: "a frozen clock in the runner". The clock is
# freezable now, and these prove it end to end — the second one by running a real pilot
# twice, into a temp root, and demanding the bytes agree.
# --------------------------------------------------------------------------------------


def test_the_record_clock_is_frozen_by_its_env_and_normalised(monkeypatch):
    monkeypatch.setenv(PROV.CLOCK_ENV, "2026-07-13T06:28:52+00:00")
    assert PROV.now_iso() == "2026-07-13T06:28:52+00:00"
    # a naive instant is read as UTC, and an offset is normalised to it, so one clock means one stamp
    monkeypatch.setenv(PROV.CLOCK_ENV, "2026-07-13T06:28:52")
    assert PROV.now_iso() == "2026-07-13T06:28:52+00:00"
    monkeypatch.setenv(PROV.CLOCK_ENV, "2026-07-13T08:28:52+02:00")
    assert PROV.now_iso() == "2026-07-13T06:28:52+00:00"


def test_an_unreadable_frozen_clock_refuses_rather_than_falling_back(monkeypatch):
    """A frozen clock that silently reverts to the wall clock makes a run LOOK reproducible."""
    monkeypatch.setenv(PROV.CLOCK_ENV, "yesterday")
    with pytest.raises(ValueError):
        PROV.now_iso()
    monkeypatch.delenv(PROV.CLOCK_ENV)
    assert PROV.now_iso().endswith("+00:00")          # unset, the wall clock, unchanged


def test_two_pilot_runs_under_one_frozen_clock_are_byte_identical():
    """L8's remedy, exercised: the same pilot, twice, into two temp roots — the same bytes.

    This is what "byte-stable" has to mean. It runs the REAL runner in a subprocess, because the write root and
    the clock are both read from the environment at import, and it writes only under a temp root: the guard in
    test_milestone_writes_are_redirected_off_the_frozen_tree_under_test above is the contract it relies on.
    """
    git_root = pathlib.Path(__file__).resolve().parents[3]  # the root holding the `tools` package (the app folder since 2026-10-04)
    digests = []
    with tempfile.TemporaryDirectory() as d:
        for run in ("a", "b"):
            root = pathlib.Path(d) / run
            env = dict(os.environ,
                       DIP0C_MILESTONE_OUTPUT=str(root),
                       DIP0C_ALLOW_MILESTONE_WRITE="1",
                       **{PROV.CLOCK_ENV: "2026-07-13T06:28:52+00:00"})
            r = subprocess.run([sys.executable, "-m", "tools.dip0c.run_c3b3"],
                               cwd=str(git_root), env=env, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr[-2000:]
            examples = root / "decisions" / "examples_TEST_ONLY"
            files = sorted(p for p in examples.rglob("*.json"))
            assert files, "the pilot wrote no example records at all"
            digests.append([(p.relative_to(examples).as_posix(), p.read_bytes()) for p in files])
    assert [n for n, _ in digests[0]] == [n for n, _ in digests[1]], "the two runs wrote different files"
    for (name, first), (_, second) in zip(digests[0], digests[1]):
        assert first == second, "%s differs between two runs under one frozen clock" % name


def test_a_frozen_clock_is_what_the_pilot_stamps_its_records_with():
    """Not only stable run to run — stable at the instant the clock names."""
    git_root = pathlib.Path(__file__).resolve().parents[3]  # the root holding the `tools` package (the app folder since 2026-10-04)
    stamp = "2026-07-13T06:28:52+00:00"
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, DIP0C_MILESTONE_OUTPUT=d,
                   DIP0C_ALLOW_MILESTONE_WRITE="1", **{PROV.CLOCK_ENV: stamp})
        r = subprocess.run([sys.executable, "-m", "tools.dip0c.run_c3b3"],
                           cwd=str(git_root), env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        events = sorted((pathlib.Path(d) / "decisions" / "examples_TEST_ONLY" / "events").glob("*.json"))
        assert events, "the pilot wrote no events"
        for p in events:
            assert json.loads(p.read_text())["recorded_at"] == stamp
