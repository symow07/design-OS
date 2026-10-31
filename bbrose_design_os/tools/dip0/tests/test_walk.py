"""Slice 1 — walk, exclusions, symlink safety, hashing, duplicates, integrity."""
from __future__ import annotations

import os

import pytest

from tools.dip0 import config as C
from tools.dip0 import integrity
from tools.dip0.walk import HashCache, group_duplicates, walk_source


def _rels(res):
    return {r["relative_path"] for r in res.files}


class TestExclusions:
    def test_junk_excluded_but_counted(self, tree):
        res = walk_source()
        names = {j["filename"] for j in res.junk}
        assert names == {"Thumbs.db", ".DS_Store", "~$lock.doc"}
        assert not any(r["filename"] in names for r in res.files)

    def test_junk_files_still_exist_on_disk(self, tree):
        walk_source()
        assert (C.SOURCE_ROOT / "Thumbs.db").exists()   # excluded ≠ deleted

    def test_skipped_dirs_not_descended(self, tree):
        res = walk_source()
        assert not any("__MACOSX" in p for p in _rels(res))
        assert not any("/.cache/" in p for p in _rels(res))
        assert any(p.endswith("__MACOSX") for p in res.skipped_dirs)
        assert any(p.endswith(".cache") for p in res.skipped_dirs)


class TestSymlinks:
    def test_symlinks_recorded_never_followed(self, tree):
        res = walk_source()
        by = {s["relative_path"].split("/")[-1]: s for s in res.symlinks}
        assert "link_internal.ai" in by and "link_escape.txt" in by
        assert all(s["followed"] is False for s in res.symlinks)
        # a symlink is never inventoried as a real file
        assert not any(p.endswith("link_internal.ai") for p in _rels(res))

    def test_escaping_symlink_flagged(self, tree):
        res = walk_source()
        esc = next(s for s in res.symlinks if s["relative_path"].endswith("link_escape.txt"))
        assert esc["escapes_source_root"] is True

    def test_symlinked_dir_loop_not_traversed(self, tree):
        res = walk_source()   # must terminate; link_loop is a dir symlink
        assert any(s["relative_path"].endswith("link_loop") for s in res.symlinks)


class TestHashing:
    def test_every_file_hashed(self, tree):
        res = walk_source()
        assert res.files and all(len(r["sha256"]) == 64 for r in res.files)

    def test_cache_hits_on_second_pass(self, tree):
        cache = HashCache(C.OUT_TEMP / "hash_cache.json")
        walk_source(cache=cache)
        assert cache.misses > 0 and cache.hits == 0
        cache.save()
        cache2 = HashCache(C.OUT_TEMP / "hash_cache.json")
        walk_source(cache=cache2)
        assert cache2.hits > 0 and cache2.misses == 0

    def test_cache_invalidated_by_mtime(self, tree):
        cache = HashCache(C.OUT_TEMP / "hash_cache.json")
        walk_source(cache=cache)
        cache.save()
        p = C.SOURCE_ROOT / "historical AI production designs" / "LP5526-E.ai"
        p.write_bytes(p.read_bytes() + b"changed")   # fixture-only mutation
        cache2 = HashCache(C.OUT_TEMP / "hash_cache.json")
        walk_source(cache=cache2)
        assert cache2.misses == 1   # only the touched file re-hashed


class TestDuplicates:
    def test_exact_duplicate_group_detected(self, tree):
        res = walk_source()
        d = group_duplicates(res.files)
        rose = [g for g in d["groups"] if g["copies"] == 2
                and all("rose.eps" in m for m in
                        [g["canonical_candidate"], *g["duplicate_members"]])]
        assert len(rose) == 1
        g = rose[0]
        assert g["confidence"] == 1.0 and g["basis"] == "sha256_exact"
        assert g["cross_folder"] is True
        assert g["redundant_bytes"] == g["size_bytes"]
        # canonical = shallowest path; the deeper copy is the duplicate member
        assert g["canonical_candidate"].count("/") <= g["duplicate_members"][0].count("/")

    def test_detection_only_no_mutation(self, tree):
        res = walk_source()
        before = {r["relative_path"] for r in res.files}
        group_duplicates(res.files)
        after = {r["relative_path"] for r in walk_source().files}
        assert before == after   # nothing deleted/moved/replaced

    def test_index_maps_every_member(self, tree):
        res = walk_source()
        d = group_duplicates(res.files)
        for g in d["groups"]:
            for m in [g["canonical_candidate"], *g["duplicate_members"]]:
                assert d["index"][m] == g["group_id"]

    def test_zero_byte_files_never_grouped(self, tree):
        (C.SOURCE_ROOT / "empty1.txt").write_bytes(b"")
        (C.SOURCE_ROOT / "empty2.txt").write_bytes(b"")
        d = group_duplicates(walk_source().files)
        assert not any(g["size_bytes"] == 0 for g in d["groups"])


class TestIntegrity:
    def test_snapshot_detects_nothing_when_unchanged(self, tree):
        before = integrity.snapshot()
        walk_source()                       # the audit itself must not mutate
        cmp = integrity.compare(before, integrity.snapshot())
        assert cmp["unchanged"] is True

    def test_snapshot_detects_modification(self, tree):
        before = integrity.snapshot()
        p = C.SOURCE_ROOT / "Fonts" / "Brand.otf"
        p.write_bytes(p.read_bytes() + b"x")
        cmp = integrity.compare(before, integrity.snapshot())
        assert cmp["unchanged"] is False
        assert any("Brand.otf" in m for m in cmp["modified"])

    def test_snapshot_includes_junk(self, tree):
        assert any("Thumbs.db" in p for p in integrity.snapshot())

    def test_hash_stability_sample(self, tree):
        res = walk_source()
        v = integrity.verify_hashes(res.files, sample=None)
        assert v["stable"] is True and v["checked"] == len(res.files)

    def test_output_root_outside_source(self, tree):
        assert integrity.no_output_under_source()["ok"] is True

    def test_assert_output_safe_rejects_source_paths(self, tree):
        with pytest.raises(RuntimeError):
            C.assert_output_safe(C.SOURCE_ROOT / "inventory")
        C.assert_output_safe(C.OUT_REPORTS)   # must not raise


class TestRecordShape:
    def test_relative_paths_are_materials_rooted(self, tree):
        res = walk_source()
        assert all(r["relative_path"].startswith("materials/") for r in res.files)
        assert all(not os.path.isabs(r["relative_path"]) for r in res.files)

    def test_parser_support_status_assigned(self, tree):
        res = walk_source()
        by = {r["filename"]: r["parser_support"]["status"] for r in res.files}
        assert by["LP5526-E.ai"] == "supported"
        assert by["bundle.zip"] == "archive"
        assert by["shirt.psd"] == "partial"
        assert by["old.fon"] == "unsupported"
        assert by["License premium.txt"] == "evidence"
