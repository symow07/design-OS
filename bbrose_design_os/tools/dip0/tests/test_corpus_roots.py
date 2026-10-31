"""§BH18(c) Option B — the additive second corpus root and its two guards.

§BH18(c) attached two conditions to the widening, and both are here as
behavioural tests rather than as existence checks:

  (1) the integrity snapshot root widens IN THE SAME CHANGE — the
      reconciliation may never report unchanged while silent about the new root;
  (2) write protection extends over static/fonts in the same change.

The condition-(1) test is written as a SIDE-BY-SIDE on a single mutation: the
narrow scope reports `unchanged: True` about the very same edit that the widened
default reports as modified. An assertion that the new behaviour works proves
much less than a demonstration that the old behaviour was wrong about a real
change, so both halves are measured on one mutation rather than asserted apart.
"""
from __future__ import annotations

import pytest

from tools.dip0 import config as C
from tools.dip0 import integrity
from tools.dip0.classify import classify
from tools.dip0.walk import walk_corpus, walk_source


def _face(tree, name: str = "NotoSans-Regular.ttf", body: bytes = b"\x00\x01\x00\x00ttf") -> object:
    """Create a file under the ADDITIVE root, wherever the fixture put it."""
    root = C.corpus_roots()[1]
    root.mkdir(parents=True, exist_ok=True)
    p = root / name
    p.write_bytes(body)
    return p


class TestCorpusRootsResolution:
    def test_corpus_roots_is_dynamic_not_frozen_at_import(self, tree):
        """The reason it is a function and not a module-level tuple.

        The fixtures monkeypatch SOURCE_ROOT and REPO_ROOT. A tuple built at
        import time would still name the real 28GB library here, and the whole
        test suite would walk the live corpus without saying so.
        """
        roots = C.corpus_roots()
        assert roots[0] == C.SOURCE_ROOT
        assert roots[1] == C.REPO_ROOT / C.CONTAINER_FONT_DIR
        # every root sits under the patched repo, not the real one
        for r in roots:
            assert str(r).startswith(str(C.REPO_ROOT))

    def test_source_root_keeps_its_meaning(self, tree):
        """Option B, not Option A: SOURCE_ROOT is not redefined."""
        assert C.SOURCE_ROOT.name == "materials"
        assert C.corpus_roots()[0] is C.SOURCE_ROOT
        assert C.SOURCE_ROOT != C.corpus_roots()[1]

    def test_second_root_is_the_container_font_dir(self, tree):
        assert C.CONTAINER_FONT_DIR == "bbrose_design_os/static/fonts"


class TestWalkReachesTheNewRoot:
    def test_walk_source_alone_never_sees_the_new_root(self, tree):
        """The measured Q1 finding, pinned: the single-root walk cannot reach it."""
        _face(tree)
        rels = {r["relative_path"] for r in walk_source().files}
        assert not any(C.CONTAINER_FONT_DIR in r for r in rels)

    def test_walk_corpus_reaches_the_new_root(self, tree):
        _face(tree)
        rels = {r["relative_path"] for r in walk_corpus().files}
        assert f"{C.CONTAINER_FONT_DIR}/NotoSans-Regular.ttf" in rels

    def test_walk_corpus_is_additive_not_a_replacement(self, tree):
        """Every materials/ row survives; the new rows are added to them."""
        _face(tree)
        base = {r["relative_path"] for r in walk_source().files}
        wide = {r["relative_path"] for r in walk_corpus().files}
        assert base and base < wide
        assert wide - base == {f"{C.CONTAINER_FONT_DIR}/NotoSans-Regular.ttf"}

    def test_row_schema_needs_no_change_to_express_the_new_root(self, tree):
        """relpath() is REPO_ROOT-relative in code, so both roots fit as-is."""
        _face(tree)
        rec = next(r for r in walk_corpus().files
                   if r["relative_path"].startswith(C.CONTAINER_FONT_DIR))
        assert set(rec) >= {"relative_path", "filename", "extension",
                            "size_bytes", "sha256"}
        assert rec["extension"] == ".ttf"

    def test_absent_new_root_contributes_nothing_and_does_not_raise(self, tree):
        """No file is created here on purpose: the root does not exist."""
        assert not C.corpus_roots()[1].exists()
        assert walk_corpus().files == walk_source().files

    def test_font_extension_rule_classifies_the_new_root(self, tree):
        """No classify rule changes, MEASURED side-by-side rather than claimed.

        The reason the taxonomy needed no widening is that the font branch keys
        on the extension and not on the path. That is only worth asserting if
        the two roots are shown to land on the SAME rule, so a `materials/` face
        and a container face are classified here and compared, rather than the
        new root being checked alone against a remembered expectation.
        """
        _face(tree)
        files = walk_corpus().files
        new = next(r for r in files
                   if r["relative_path"].startswith(C.CONTAINER_FONT_DIR))
        old = next(r for r in files
                   if r["relative_path"] == "materials/Fonts/Brand.otf")

        assert classify(new)["value"] == "FONT"
        assert classify(new)["value"] == classify(old)["value"]
        # the same RULE fired, not merely the same answer by two routes
        assert classify(new)["source"] == classify(old)["source"] \
            == "extension_rule"


class TestConditionTwoWriteProtection:
    """§BH18(c)(2) — live tracked application assets must not sit unguarded."""

    def test_assert_output_safe_refuses_the_new_root(self, tree):
        with pytest.raises(RuntimeError):
            C.assert_output_safe(C.corpus_roots()[1])

    def test_assert_output_safe_refuses_beneath_the_new_root(self, tree):
        with pytest.raises(RuntimeError):
            C.assert_output_safe(C.corpus_roots()[1] / "NotoSans-Regular.ttf")

    def test_the_refusal_names_the_root_it_refused_for(self, tree):
        with pytest.raises(RuntimeError) as e:
            C.assert_output_safe(C.corpus_roots()[1] / "x.ttf")
        assert C.CONTAINER_FONT_DIR.split("/")[-1] in str(e.value)

    def test_the_original_source_root_refusal_is_unchanged(self, tree):
        with pytest.raises(RuntimeError):
            C.assert_output_safe(C.SOURCE_ROOT / "inventory")

    def test_legitimate_output_paths_still_pass(self, tree):
        C.assert_output_safe(C.OUT_REPORTS)      # must not raise
        C.assert_output_safe(C.OUTPUT_ROOT)      # must not raise

    def test_a_sibling_of_the_new_root_is_not_refused(self, tree):
        """The guard is scoped to the fonts dir, not to static/ or the app."""
        C.assert_output_safe(C.REPO_ROOT / "bbrose_design_os" / "static" / "css")


class TestConditionOneIntegritySnapshot:
    """§BH18(c)(1) — the reconciliation may never be silent about the new root."""

    def test_snapshot_covers_both_roots_by_default(self, tree):
        _face(tree)
        snap = integrity.snapshot()
        assert any(p.startswith("materials/") for p in snap)
        assert f"{C.CONTAINER_FONT_DIR}/NotoSans-Regular.ttf" in snap

    def test_explicit_root_still_snapshots_exactly_that_tree(self, tree):
        _face(tree)
        snap = integrity.snapshot(C.SOURCE_ROOT)
        assert not any(p.startswith(C.CONTAINER_FONT_DIR) for p in snap)

    def test_a_mutation_under_the_new_root_was_invisible_and_now_is_not(self, tree):
        """THE Q3(4) DEFECT, DEMONSTRATED ON ONE MUTATION.

        Both scopes are snapshotted before the SAME edit. The narrow scope —
        which is exactly what `snapshot()` did before this change — reports
        `unchanged: True` about a file that demonstrably changed. That is the
        silent false assurance produced by the machinery that exists to prevent
        one, and it is asserted here rather than described.
        """
        p = _face(tree)
        before_narrow = integrity.snapshot(C.SOURCE_ROOT)
        before_wide = integrity.snapshot()

        p.write_bytes(p.read_bytes() + b"MUTATED")     # one edit, both scopes

        narrow = integrity.compare(before_narrow,
                                   integrity.snapshot(C.SOURCE_ROOT),
                                   roots=[C.SOURCE_ROOT])
        wide = integrity.compare(before_wide, integrity.snapshot())

        assert narrow["unchanged"] is True             # the old, wrong answer
        assert wide["unchanged"] is False              # the widened, true one
        assert any(C.CONTAINER_FONT_DIR in m for m in wide["modified"])

    def test_a_mutation_under_materials_is_still_caught(self, tree):
        """The widening must not cost the guarantee it already had."""
        before = integrity.snapshot()
        p = C.SOURCE_ROOT / "Fonts" / "Brand.otf"
        p.write_bytes(p.read_bytes() + b"x")
        cmp = integrity.compare(before, integrity.snapshot())
        assert cmp["unchanged"] is False
        assert any("Brand.otf" in m for m in cmp["modified"])

    def test_unchanged_can_never_be_read_without_its_scope(self, tree):
        """`roots_covered` is the point: a verdict now carries its extent."""
        cmp = integrity.compare(integrity.snapshot(), integrity.snapshot())
        assert cmp["unchanged"] is True
        assert cmp["roots_covered"] == ["materials", C.CONTAINER_FONT_DIR]

    def test_a_file_appearing_under_the_new_root_is_detected(self, tree):
        before = integrity.snapshot()
        _face(tree, name="Interloper.ttf")
        cmp = integrity.compare(before, integrity.snapshot())
        assert cmp["unchanged"] is False
        assert any("Interloper.ttf" in a for a in cmp["added"])


class TestOutputRootCheckWidened:
    def test_output_root_is_outside_every_corpus_root(self, tree):
        chk = integrity.no_output_under_source()
        assert chk["ok"] is True
        assert chk["output_inside_root"] == []

    def test_the_check_now_names_every_root_it_cleared(self, tree):
        chk = integrity.no_output_under_source()
        assert len(chk["corpus_roots"]) == 2
        assert str(C.SOURCE_ROOT.resolve()) in chk["corpus_roots"]

    def test_source_root_key_is_preserved_for_existing_readers(self, tree):
        assert integrity.no_output_under_source()["source_root"] \
            == str(C.SOURCE_ROOT.resolve())


# ---------------------------------------------------------------------------
# §BH30(h)(2) — THE RULED EXCLUSION LIST. Five entries as typed on disk, no
# globs, additive to the existing skip rules, reversible only by ruling.
# ---------------------------------------------------------------------------

RULED_TWO = (
    "materials/Fonts/FONTS 2026",
    "materials/FONTS 2026",
)
#: §BH37(2): the three folders that left the list — ADMITTED, walked like any sibling
ADMITTED_AT_BH37 = ("materials/17-10-2024", "materials/ALL..MOCKUP", "materials/ADOBE STOCK")


def _plant_excluded_entries(tree):
    """The two ruled entries, the three admitted folders and a sixth sibling, under the fixture's materials/."""
    src = tree / "materials"
    (src / "Fonts" / "FONTS 2026").mkdir(parents=True)
    (src / "Fonts" / "FONTS 2026" / "Dropped.ttf").write_bytes(b"\x00\x01\x00\x00drop")
    (src / "FONTS 2026").write_bytes(b"book" + b"mark" * 8)          # the alias is a FILE
    for d in ("17-10-2024", "ALL..MOCKUP", "ADOBE STOCK"):
        (src / d).mkdir()
        (src / d / "asset.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
    (src / "SIXTH SIBLING").mkdir()
    sixth = src / "SIXTH SIBLING" / "walked.ttf"
    sixth.write_bytes(b"\x00\x01\x00\x00walked")
    return sixth


class TestRuledExclusionList:
    def test_the_list_is_exactly_the_two_the_ruling_left(self):
        assert C.EXCLUDED_PATHS == RULED_TWO           # a change here is a ruling (§BH30(h)(2), §BH37(2))

    def test_each_of_the_two_is_skipped_and_the_admitted_three_and_the_sixth_sibling_are_walked(self, tree):
        sixth = _plant_excluded_entries(tree)
        res = walk_corpus(hash_files=False)
        paths = [r["relative_path"] for r in res.files]
        for entry in RULED_TWO:
            assert not any(p == entry or p.startswith(entry + "/") for p in paths), entry
        for entry in ADMITTED_AT_BH37:                 # §BH37(2): the three enter the walk
            assert f"{entry}/asset.jpg" in paths, entry
        assert C.relpath(str(sixth)) in paths
        recorded = {(e["relative_path"], e["kind"]) for e in res.excluded}
        assert recorded == {
            ("materials/Fonts/FONTS 2026", "dir"), ("materials/FONTS 2026", "file"),
        }

    def test_the_match_is_exact_not_a_prefix_or_a_glob(self):
        assert C.is_excluded_path("materials/Fonts/FONTS 2026")
        assert C.is_excluded_path("materials/Fonts/FONTS 2026/Any.ttf")
        assert not C.is_excluded_path("materials/Fonts")                  # the parent is walked
        assert not C.is_excluded_path("materials/Fonts/FONTS 2026x")     # a longer name is not the entry
        assert not C.is_excluded_path("materials/FONTS 2026 copy")
        assert not C.is_excluded_path("bbrose_design_os/static/fonts/brand2026/Poppins/OFL.txt")

    def test_existing_skip_rules_still_apply_beside_the_list(self, tree):
        _plant_excluded_entries(tree)
        res = walk_corpus(hash_files=False)
        assert any(s.endswith("__MACOSX") for s in res.skipped_dirs)
        assert any(j["filename"] == "Thumbs.db" for j in res.junk)

    def test_the_snapshot_report_names_each_entry_with_its_bytes(self, tree):
        _plant_excluded_entries(tree)
        rep = {e["entry"]: e for e in C.excluded_entries_on_disk()}
        assert set(rep) == set(RULED_TWO)
        assert rep["materials/FONTS 2026"]["kind"] == "file" and rep["materials/FONTS 2026"]["bytes"] == 36
        assert rep["materials/Fonts/FONTS 2026"]["kind"] == "dir" and rep["materials/Fonts/FONTS 2026"]["files"] == 1
        assert "materials/17-10-2024" not in rep         # admitted: no longer reported as excluded

    def test_an_absent_entry_is_reported_absent_not_invented(self, tree):
        rep = {e["entry"]: e for e in C.excluded_entries_on_disk()}
        assert rep["materials/Fonts/FONTS 2026"]["kind"] == "absent"
