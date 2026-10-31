"""DIP-0C4a — per-face font audit, TTC handling, family grouping, duplicates.

Two kinds of test live here. Most build *synthetic* faces and never touch the source
library. A handful are real-corpus integration tests that read actual fonts under
``materials/`` — by DIP-0 design, the audit must be proven against the real read-only
library, never a fake. Those reach the corpus through :func:`_corpus_font`, which anchors
to the absolute ``SOURCE_ROOT`` (so the suite is cwd-independent, matching how
``run_c4a.load_fonts()`` already resolves the corpus) and skips cleanly when the
git-ignored ``materials/`` library is absent — as it is on CI, which does not run this file.
"""
from __future__ import annotations

import pytest

from tools.dip0c import config as C
from tools.dip0c import fontfamily as FF
from tools.dip0c import fontinfo as FI
from tools.dip0c import run_c4a


def _corpus_font(relpath: str):
    """A real corpus font resolved by absolute SOURCE_ROOT (cwd-independent).

    Skips cleanly when the optional, git-ignored ``materials/`` library is not present in
    this checkout — these are local integration tests, not CI tests. Anchoring here is what
    fixes the earlier failure: a bare ``"materials/..."`` string only resolves when pytest
    runs from the repo root, so the same test passed from repo root and failed from
    ``bbrose_design_os/``.
    """
    path = C.SOURCE_ROOT / relpath
    if not path.exists():
        pytest.skip(f"materials/ font not present: {relpath}")
    return path


# --- fixtures: synthetic faces, so grouping is tested without touching materials/ ---
def face(family16=None, family1="X", ps="X-Regular", vendor="ACME", *,
         sha="h0", index=0, path="materials/pkg/x.ttf", weight=400,
         width="NORMAL", scripts=("latin",), dominant="latin",
         blocks=("U+00000", "U+00100"), axes=(), version="1.000",
         fstype_raw=0):
    return {
        "face_id": FI.face_id(sha, index, ps),
        "source_path": path,
        "source_sha256": sha,
        "collection_index": index,
        "extension": ".ttf",
        "names": {"family_typographic": family16, "family_legacy": family1,
                  "postscript_name": ps, "subfamily_legacy": "Regular",
                  "full_name": ps, "copyright": None, "manufacturer": None},
        "vendor_id": vendor,
        "version": version,
        "weight_class": weight,
        "width_class": width,
        "italic": False, "bold": False,
        "is_variable": bool(axes),
        "variable_axes": [{"tag": t, "min": 100, "default": 400, "max": 900}
                          for t in axes],
        "scripts": list(scripts),
        "script_coverage": {s: 100 for s in scripts},
        "dominant_script": dominant,
        "cmap_codepoints": 300,
        "unicode_blocks": list(blocks),
        "glyph_count": 300,
        "tables": ["cmap", "head", "name"],
        "fstype": {"raw": fstype_raw, "flags": ["INSTALLABLE_EMBEDDING"],
                   "is_permission": False, "note": "metadata"},
        "warnings": [],
        "parse_status": FI.PARSED,
        "capability": FI.CAP_DIRECT,
    }


def _by_hash(faces):
    d = {}
    for f in faces:
        d.setdefault(f["source_sha256"], []).append({"relative_path": f["source_path"]})
    return d


def group_of(faces):
    return FF.build_groups(faces, by_hash=_by_hash(faces))


# === a file is not a font ====================================================
def test_a_ttc_yields_one_face_per_font_not_one_per_file():
    r = FI.audit_file(_corpus_font("Fonts/3333/mingliub.ttc"))
    assert r["is_collection"] is True
    assert r["face_count"] == 3                     # THREE fonts in ONE file
    assert len({f["face_id"] for f in r["faces"]}) == 3
    assert [f["collection_index"] for f in r["faces"]] == [0, 1, 2]
    # ...and they carry DIFFERENT families
    fams = {f["names"]["family_legacy"] for f in r["faces"]}
    assert len(fams) == 3


def test_faces_in_one_collection_may_land_in_different_family_groups():
    a = face(family1="MingLiU-ExtB", ps="MingLiU-ExtB", sha="h1", index=0)
    b = face(family1="PMingLiU-ExtB", ps="PMingLiU-ExtB", sha="h1", index=1)
    gs = group_of([a, b])
    assert len(gs) == 2
    assert {g["family_key"] for g in gs} == {"mingliu extb", "pmingliu extb"}


def test_face_id_is_stable_and_content_derived():
    a = FI.face_id("abc", 0, "Foo-Regular")
    assert a == FI.face_id("abc", 0, "Foo-Regular")      # deterministic
    assert a != FI.face_id("abc", 1, "Foo-Regular")      # index matters
    assert a != FI.face_id("def", 0, "Foo-Regular")      # content matters


# === fail closed =============================================================
def test_a_fon_file_fails_closed_and_is_not_dropped():
    r = FI.audit_file(_corpus_font("Fonts/3333/8514oemg.fon"))
    assert r["parse_status"] == FI.UNSUPPORTED_FORMAT
    assert r["capability"] == FI.CAP_REQUIRES_HUMAN
    assert r["faces"] == []
    assert "not an sfnt" in r["error"]
    assert r["source_sha256"]                     # it is still IN the corpus


def test_a_corrupt_font_fails_closed(tmp_path):
    p = tmp_path / "broken.ttf"
    p.write_bytes(b"\x00\x01\x00\x00" + b"\xff" * 200)
    r = FI.audit_file(p)
    assert r["parse_status"] == FI.PARSE_FAILED
    assert r["capability"] == FI.CAP_REQUIRES_HUMAN
    assert r["error"]


def test_the_audit_never_modifies_the_source(tmp_path):
    src = _corpus_font("Fonts/3333/consola.ttf")
    before = src.stat().st_mtime_ns, src.stat().st_size
    FI.audit_file(src)
    assert (src.stat().st_mtime_ns, src.stat().st_size) == before


# === script coverage =========================================================
def test_supplementary_plane_cjk_is_not_reported_as_latin():
    """MingLiU-ExtB is 42,711 CJK Ext-B codepoints and 165 Latin ones. Under BMP-only
    ranges it reported as 'latin' — the wrong answer, from the wrong ranges."""
    r = FI.audit_file(_corpus_font("Fonts/3333/mingliub.ttc"))
    f = r["faces"][0]
    assert f["dominant_script"] == "cjk_ext_b"
    assert f["script_coverage"]["cjk_ext_b"] > 40000
    assert f["script_coverage"]["cjk_ext_b"] > f["script_coverage"].get("latin", 0)


def test_presence_is_not_coverage():
    """Every script carries its COUNT, so 8 Greek glyphs never outrank 40,000 CJK."""
    r = FI.audit_file(_corpus_font("Fonts/3333/consola.ttf"))
    f = r["faces"][0]
    assert f["dominant_script"] == "latin"
    assert f["script_coverage"]["latin"] > f["script_coverage"]["greek"]


# === fsType is metadata, never permission ====================================
def test_fstype_is_recorded_and_grants_nothing():
    r = FI.audit_file(_corpus_font("Fonts/3333/consola.ttf"))
    fs = r["faces"][0]["fstype"]
    assert fs["raw"] is not None
    assert fs["flags"]
    assert fs["is_permission"] is False
    assert "NOT a licence" in fs["note"]


def test_an_installable_fstype_does_not_imply_a_right_to_use():
    f = face(fstype_raw=0)
    assert f["fstype"]["is_permission"] is False
    # nothing in a group derives a permission from it
    g = group_of([f])[0]
    assert "permission" not in str(g).lower() or g.get("human_confirmed_family") is None


# === dedup before parse ======================================================
def test_dedup_groups_by_hash_before_anything_is_parsed():
    files = [
        {"sha256": "a", "relative_path": "materials/Fonts/x.ttf"},
        {"sha256": "a", "relative_path": "materials/Fonts/3333/x.ttf"},
        {"sha256": "b", "relative_path": "materials/Fonts/y.ttf"},
    ]
    dd = FF.dedupe(files)
    assert dd["files_total"] == 3
    assert dd["files_unique"] == 2
    assert dd["duplicate_group_count"] == 1
    assert dd["files_in_duplicate_groups"] == 2
    assert dd["by_hash"]["a"][0]["relative_path"] < dd["by_hash"]["a"][1]["relative_path"]


def test_a_duplicate_family_records_its_duplicate_hashes():
    a = face(sha="dup", path="materials/Fonts/x.ttf")
    b = face(sha="dup", path="materials/Fonts/3333/x.ttf", index=0)
    by_hash = {"dup": [{"relative_path": "materials/Fonts/x.ttf"},
                       {"relative_path": "materials/Fonts/3333/x.ttf"}]}
    g = FF.build_groups([a, b], by_hash=by_hash)[0]
    assert FF.EV_EXACT_DUPLICATE in g["supporting_evidence"]
    assert g["duplicate_hashes"] == ["dup"]


# === D2: the family key ======================================================
def test_name_id_16_is_preferred_over_name_id_1():
    f = face(family16="Sinkin Sans", family1="Sinkin Sans 400 Regular")
    key, src = FF.family_key(f)
    assert key == "sinkin sans"
    assert src == "name_id_16"


def test_id16_holds_weights_together_where_id1_would_fragment():
    """The real corpus case: SinkinSans-400Regular has ID16 'Sinkin Sans' but ID1
    'Sinkin Sans 400 Regular'. Under ID1 every weight becomes its own family."""
    faces = [face(family16="Sinkin Sans", family1=f"Sinkin Sans {w} Regular",
                  ps=f"SinkinSans-{w}Regular", sha=f"h{w}", weight=w)
             for w in (300, 400, 700)]
    gs = group_of(faces)
    assert len(gs) == 1                       # ONE family
    assert gs[0]["face_count"] == 3
    assert gs[0]["weight_classes"] == [300, 400, 700]
    assert FF.EV_WEIGHT_LADDER in gs[0]["supporting_evidence"]

    id1_keys = {FF.normalize(f["names"]["family_legacy"]) for f in faces}
    assert len(id1_keys) == 3                 # ...would have been THREE


def test_the_fallback_to_id1_is_used_when_id16_is_absent():
    f = face(family16=None, family1="Consolas")
    key, src = FF.family_key(f)
    assert key == "consolas"
    assert src == "name_id_1"


# === grouping safeguards =====================================================
def test_a_generic_name_never_merges_unrelated_fonts():
    a = face(family16=None, family1="Regular", ps="AlphaOne", vendor="AAAA",
             sha="h1", path="materials/pkgA/a.ttf")
    b = face(family16=None, family1="Regular", ps="BetaTwo", vendor="BBBB",
             sha="h2", path="materials/pkgB/b.ttf")
    gs = group_of([a, b])
    assert len(gs) == 2                       # SPLIT, not merged
    for g in gs:
        assert g["state"] == FF.FAMILY_NAME_TOO_GENERIC
        assert FF.CONFLICT_GENERIC in g["conflicting_evidence"]


@pytest.mark.parametrize("name", ["regular", "roman", "sans", "serif", "script",
                                  "display", "italic", "bold"])
def test_style_words_are_recognised_as_generic(name):
    assert FF.is_generic(name)


def test_the_same_name_under_different_vendors_is_split_not_merged():
    a = face(family16="Nova", vendor="AAAA", sha="h1", ps="Nova-Regular")
    b = face(family16="Nova", vendor="ZZZZ", sha="h2", ps="Nova-Regular")
    gs = group_of([a, b])
    assert len(gs) == 2
    for g in gs:
        assert g["state"] == FF.FAMILY_RELATIONSHIP_REVIEW_REQUIRED
        assert FF.CONFLICT_VENDOR in g["conflicting_evidence"]
        assert "coincidence" in g["note"]


def test_incompatible_glyph_coverage_flags_review():
    a = face(family16="Nova", sha="h1", dominant="latin",
             blocks=("U+00000", "U+00100"))
    b = face(family16="Nova", sha="h2", dominant="cjk_ext_b",
             blocks=("U+20000", "U+20100"))
    g = group_of([a, b])[0]
    assert g["state"] == FF.FAMILY_RELATIONSHIP_REVIEW_REQUIRED
    assert FF.CONFLICT_COVERAGE in g["conflicting_evidence"]
    assert g["incompatible_faces"]


def test_multiple_source_packages_are_recorded_as_a_conflict():
    a = face(family16="Nova", sha="h1", path="materials/pkgA/a.ttf")
    b = face(family16="Nova", sha="h2", path="materials/pkgB/b.ttf")
    g = group_of([a, b])[0]
    assert FF.CONFLICT_PACKAGE in g["conflicting_evidence"]
    assert len(g["source_packages"]) == 2
    assert g["state"] == FF.FAMILY_RELATIONSHIP_REVIEW_REQUIRED


def test_a_clean_family_records_its_supporting_evidence():
    faces = [face(family16="Exo", ps=f"Exo-{w}", sha=f"h{w}", weight=w,
                  axes=("wght",))
             for w in (300, 400, 700)]
    g = group_of(faces)[0]
    assert g["state"] == FF.FAMILY_GROUPED
    assert g["conflicting_evidence"] == []
    for ev in (FF.EV_SAME_ID16, FF.EV_SAME_VENDOR, FF.EV_SAME_PACKAGE,
               FF.EV_WEIGHT_LADDER, FF.EV_VARIABLE_AXES):
        assert ev in g["supporting_evidence"]
    assert g["is_variable"] is True
    assert g["variable_axes"] == ["wght"]


def test_a_group_is_a_hypothesis_not_identity_proof():
    g = group_of([face(family16="Nova")])[0]
    assert "HYPOTHESIS" in g["note"]
    assert g["human_confirmed_family"] is None      # human only


def test_grouping_is_deterministic():
    faces = [face(family16="Nova", ps=f"Nova-{i}", sha=f"h{i}") for i in range(5)]
    assert group_of(faces) == group_of(list(reversed(faces)))


# === the corpus ==============================================================
def test_the_real_corpus_audits_and_the_numbers_hold():
    if not (C.SOURCE_ROOT / "Fonts").exists():
        pytest.skip("materials/ font library not present")
    # [the clean-up of 2026-10-04 — his fifth and sixth answers: the duplicate copies, the Cracked-by fonts and the
    # screen fonts left materials/ and the DIP-0A inventory lost exactly their 1,092 FONT rows (M1 1,028, M4 27, M5 37,
    # reconciled against the pre-move index); re-measured here: 5,212 -> 4,120 files, 4,157 -> 4,099 unique, 1,047 -> 20 duplicate groups, 2,102 -> 41 files in them. The faces, families and packages are read from
    # the C4a output on disk, made before the move, and still count the removed fonts — said in the clean-up's report.]
    files = run_c4a.load_fonts()
    assert len(files) == 4120
    dd = FF.dedupe(files)
    assert dd["files_unique"] == 4099
    assert dd["duplicate_group_count"] == 20
    assert dd["files_in_duplicate_groups"] == 41


def test_c4a_acts_on_nothing():
    """The whole slice AUDITS. It never acts: no install, no copy, no render, no
    subprocess, no network. Checked against real call sites, not prose — the word
    "install" appears legitimately in fsType flags and in these very docstrings.
    """
    import ast
    import inspect
    banned_calls = {"system", "popen", "run", "check_call", "check_output", "copy",
                    "copy2", "copyfile", "move", "rename", "unlink", "remove",
                    "rmtree", "urlopen", "get", "post"}
    banned_imports = {"subprocess", "shutil", "urllib", "requests", "socket",
                      "matplotlib", "PIL.ImageFont"}
    for mod in (FI, FF, run_c4a):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                name = getattr(node, "module", None) or ""
                names = [a.name for a in node.names] + [name]
                for n in names:
                    assert n.split(".")[0] not in banned_imports, \
                        f"{mod.__name__} imports {n}"
            if isinstance(node, ast.Call):
                fn = node.func
                attr = getattr(fn, "attr", None)
                if attr in banned_calls:
                    # `.get(...)` on a dict is fine; a network get is not
                    val = getattr(fn, "value", None)
                    if attr == "get" and not isinstance(val, ast.Name):
                        continue
                    if attr == "get":
                        continue
                    raise AssertionError(f"{mod.__name__} calls .{attr}()")


def test_no_font_is_written_rendered_or_exposed():
    """C4a opens fonts read-only and writes JSON. Nothing else."""
    r = FI.audit_file(_corpus_font("Fonts/3333/consola.ttf"))
    assert "glyph_bitmap" not in r and "preview" not in r
    assert "rendered" not in str(r).lower()
    # the audit carries metadata, never font binary
    assert not any(isinstance(v, bytes) for v in r.values())
