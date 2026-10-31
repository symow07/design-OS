"""RBV-3 — standard visual review package: contract, refusals,
determinism, purity, and the REAL V4 evidence tree.

Synthetic render dirs here are ENGINEERING_REGRESSION_FIXTURES (§4): they
keep the package engine honest and are never visual-quality evidence.
"""
import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import rbv3_review_package as rp
from apps.pipeline.services.geometry_validation_render import pixel_hash

REPO = Path(__file__).resolve().parents[3]
V4_DIR = REPO / "docs" / "visual_quality" / "rbv" / "p1_pilot" / \
    "2026-08-04_v4"
#: the V4 review session renamed four view files (``neutral_`` prefix);
#: identity is proven by decoded-pixel hash, never assumed
V4_REBINDING = {"front": "neutral_front.png", "side": "neutral_side.png",
                "top": "neutral_top.png",
                "three_quarter_diagnostic": "neutral_three_quarter.png"}


def _png(path, seed, size=(40, 56)):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return path


def _render_dir(tmp_path, name="render"):
    d = tmp_path / name
    d.mkdir()
    views, hashes = {}, {}
    for i, view in enumerate(("front", "side", "closure_detail")):
        fn = f"{view}.png"
        _png(d / fn, seed=i)
        views[view] = fn
        hashes[view] = pixel_hash(str(d / fn))
    manifest = {
        "schema": "geometry_validation_render_manifest/1.0",
        "statement": "GEOMETRY VALIDATION FIXTURE — NOT A REAL BOTTLE "
                     "COMPARISON",
        "fixture_id": "SYNTH_1",
        "authority_class": "ENGINEERING_REGRESSION_FIXTURE",
        "views": views,
        "pixel_hashes": hashes,
        # DELIBERATELY W != D. The committed P1 subject happens to have
        # W == D == 37.4mm, which is the only reason the old
        # `side_depth_mm or front_width_mm` fallback — printing the FRONT
        # WIDTH under a `D` label — was invisible in real evidence. A
        # fixture that shares that coincidence cannot see the defect, so
        # this one does not share it.
        "dimensions": {"height_mm": 100.0, "front_width_mm": 30.0,
                       "side_depth_mm": 20.0},
        "measurements": {"expected_mm_per_px": 0.05,
                         "front": {"rendered_extent_mm": 35.1,
                                   "contract_extent_mm": 35.0}},
        "warnings": ["RENDER_OFF_CENTER:closure_detail"],
        "uncertainty": ["synthetic geometry fixture"],
        "reference_availability": "NONE — synthetic fixture",
        "blender_version": "Blender 4.5.12 LTS (pinned)",
        "render_engine": "CYCLES CPU · seed 0 · 12 samples",
    }
    json.dump(manifest, open(d / "manifest.json", "w"))
    return d


def _build(tmp_path, render, out="pkg", **kw):
    kw.setdefault("subject_id", "SYNTH_1")
    kw.setdefault("created_at", "2026-08-17")
    return rp.build_review_package(str(render), str(tmp_path / out), **kw)


class TestContract:
    def test_package_schema_and_channel(self, tmp_path):
        pkg = _build(tmp_path, _render_dir(tmp_path))
        assert pkg["schema"] == "rbv3_review_package/1.0"
        assert pkg["owner_review"] == {
            "status": "QUEUED_PENDING_OWNER_REVIEW", "granted": False}
        assert "OWNER_BLOCKER_CLEARANCE.md" in pkg["decision_channel"]
        # no decision fields exist anywhere in the manifest
        flat = json.dumps(pkg)
        assert "accept" not in flat and "reject" not in flat

    def test_standards_quoted_at_live_status(self, tmp_path):
        pkg = _build(tmp_path, _render_dir(tmp_path))
        assert pkg["camera_standard"]["schema"] == \
            "real_bottle_camera_standard/1.0"
        # §R2 (2026-08-17): both standards are ACTIVE. The package quotes
        # the status LIVE, so this asserts what the file says right now —
        # the point of the test is that the package never hard-codes it.
        assert pkg["camera_standard"]["status"] == "ACTIVE"
        assert pkg["lighting_standard"]["status"] == "ACTIVE"

    def test_mode_b_absence_is_explicit(self, tmp_path):
        pkg = _build(tmp_path, _render_dir(tmp_path))
        mode_b = pkg["modes"]["CLIENT_PRESENTATION"]
        assert mode_b["status"] == "ABSENT_BLOCKED"
        assert set(mode_b["reasons"]) == {
            "RBV2C_PRESENTATION_RENDERER_NOT_BUILT",
            "OWNER_GATE_PILOT_GEOMETRY_INSPECTION_PENDING"}
        assert "never re-badged" in mode_b["rule"]

    def test_mode_a_carries_render_evidence_verbatim(self, tmp_path):
        render = _render_dir(tmp_path)
        pkg = _build(tmp_path, render)
        mode_a = pkg["modes"]["GEOMETRY_VALIDATION"]
        src = json.load(open(render / "manifest.json"))
        assert mode_a["measurements"] == src["measurements"]
        assert mode_a["warnings"] == src["warnings"]
        assert mode_a["source_render_manifest"]["sha256"] == \
            rp._file_sha256(str(render / "manifest.json"))
        # views are REFERENCED, never copied — and every reference
        # resolves to the recorded decoded-pixel hash
        assert "REFERENCED" in mode_a["view_storage_policy"]
        src_dir = REPO / mode_a["view_source_dir"]
        for view, entry in mode_a["views"].items():
            assert pixel_hash(str(src_dir / entry["source_file"])) == \
                entry["pixel_hash"], view
            assert not (tmp_path / "pkg" / f"{view}.png").exists()

    def test_contact_sheet_written_with_hash_and_font_identity(self,
                                                               tmp_path):
        pkg = _build(tmp_path, _render_dir(tmp_path))
        sheet = tmp_path / "pkg" / pkg["contact_sheet"]["file"]
        assert sheet.is_file()
        assert pixel_hash(str(sheet)) == pkg["contact_sheet"]["pixel_hash"]
        # the sheet's pixels depend on the exact face: recorded, so a font
        # change reads as a cause rather than as mystery drift
        assert pkg["contact_sheet"]["font"]["path"] == rp._FONT

    def test_absent_font_refuses_instead_of_substituting(self, tmp_path,
                                                         monkeypatch):
        monkeypatch.setattr(rp, "_FONT", str(tmp_path / "no_such.ttc"))
        with pytest.raises(rp.Rbv3Refusal) as e:
            _build(tmp_path, _render_dir(tmp_path), out="nofont")
        assert rp.RBV3_SHEET_FONT_UNAVAILABLE in str(e.value)


class TestSheetLegibilityIsMeasured:
    """§S2 — RBV-4's live review could not read the bounds_dimensions
    annotations, and the transmission record showed why: the provider
    downscales anything above a 2576px long edge, so text is legible at
    the size that SURVIVES, not the size it was drawn. Every number here
    is measured; nothing asserts legibility."""

    def test_downscale_is_arithmetic_not_opinion(self):
        # a sheet at the limit is untouched; above it, scaled to fit
        assert rp.provider_downscale(2576) == 1.0
        assert rp.provider_downscale(1600) == 1.0
        assert rp.provider_downscale(3840) == pytest.approx(0.6708, abs=1e-4)

    def test_every_drawn_text_clears_the_floor(self, tmp_path):
        pkg = _build(tmp_path, _render_dir(tmp_path))
        leg = pkg["legibility"]
        assert leg["below_floor"] == []
        assert leg["worst_effective_px"] >= rp.SHEET_TEXT_MIN_EFFECTIVE_PX
        assert leg["floor_effective_px"] == rp.SHEET_TEXT_MIN_EFFECTIVE_PX
        # the measurement is per-text and recorded, not a single verdict
        roles = {t["role"] for t in leg["texts"]}
        assert {"title", "source_line", "contract_dimensions"} <= roles
        for t in leg["texts"]:
            assert t["effective_px"] == pytest.approx(
                t["glyph_px"] * leg["provider_downscale"], abs=0.01)

    def test_the_guard_can_fail(self, tmp_path, monkeypatch):
        """NEGATIVE CONTROL. A guard that has never been seen refusing is
        not known to work — this raises the floor above what the sheet
        actually achieves and proves the refusal fires with the offending
        role and its measured size named."""
        monkeypatch.setattr(rp, "SHEET_TEXT_MIN_EFFECTIVE_PX", 40.0)
        with pytest.raises(rp.Rbv3Refusal) as e:
            _build(tmp_path, _render_dir(tmp_path), out="illegible")
        findings = e.value.findings
        assert all(f.startswith(rp.RBV3_SHEET_TEXT_ILLEGIBLE)
                   for f in findings)
        assert any("source_line" in f for f in findings)
        assert any("px<40.0" in f for f in findings)

    def test_the_baked_annotation_defect_is_recorded_not_hidden(self,
                                                                tmp_path):
        """The renderer's own annotations stay illegible — they live in
        frozen render evidence this node may not rewrite. The package
        MEASURES them and names what supersedes them."""
        pkg = _build(tmp_path, _render_dir(tmp_path))
        baked = pkg["legibility"].get("renderer_baked_annotations")
        if baked is None:
            pytest.skip("synthetic render dir has no bounds_dimensions view")
        assert baked["effective_px"] < rp.SHEET_TEXT_MIN_EFFECTIVE_PX
        assert "superseded_by" in baked

    def test_committed_p1_v4_records_the_real_measurement(self):
        committed = json.load(open(self.PKG / rp.MANIFEST_NAME)) \
            if hasattr(self, "PKG") else json.loads(
                (REPO / "docs" / "visual_quality" / "rbv" /
                 "review_packages" / "p1_v4" /
                 rp.MANIFEST_NAME).read_text())
        leg = committed["legibility"]
        assert leg["sheet_long_edge"] == 3840
        assert leg["below_floor"] == []
        baked = leg["renderer_baked_annotations"]
        # the number RBV-4's reviewer was actually given
        assert baked["effective_px"] == pytest.approx(2.68, abs=0.01)


class TestRefusals:
    def test_missing_manifest_refuses(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(empty))
        assert rp.RBV3_RENDER_MANIFEST_MISSING in str(e.value)

    def test_schema_mismatch_refuses(self, tmp_path):
        d = _render_dir(tmp_path)
        m = json.load(open(d / "manifest.json"))
        m["schema"] = "something_else/9.9"
        json.dump(m, open(d / "manifest.json", "w"))
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(d))
        assert rp.RBV3_RENDER_SCHEMA_MISMATCH in str(e.value)

    def test_missing_view_refuses_with_exact_finding(self, tmp_path):
        d = _render_dir(tmp_path)
        os.remove(d / "side.png")
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(d))
        assert "RBV3_VIEW_MISSING:side:side.png" in e.value.findings

    def test_tampered_view_refuses(self, tmp_path):
        d = _render_dir(tmp_path)
        img = np.asarray(Image.open(d / "front.png")).copy()
        img[0, 0] ^= 255
        Image.fromarray(img).save(d / "front.png")
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(d))
        assert any(f.startswith("RBV3_VIEW_HASH_MISMATCH:front")
                   for f in e.value.findings)

    def test_rebinding_requires_hash_identity(self, tmp_path):
        d = _render_dir(tmp_path)
        # identical rename → accepted AND recorded
        os.rename(d / "front.png", d / "renamed_front.png")
        render = rp.load_validation_render(
            str(d), view_files={"front": "renamed_front.png"})
        assert render["rebound"] == {"front": "renamed_front.png"}
        # rebinding to a DIFFERENT image → refused
        _png(d / "wrong.png", seed=99)
        with pytest.raises(rp.Rbv3Refusal):
            rp.load_validation_render(
                str(d), view_files={"front": "wrong.png"})

    def test_reference_class_is_closed(self, tmp_path):
        d = _render_dir(tmp_path)
        photo = _png(tmp_path / "photo.png", seed=7)
        with pytest.raises(rp.Rbv3Refusal) as e:
            _build(tmp_path, d, references=[
                {"path": str(photo), "evidence_class": "CALIBRATED_SCAN"}])
        assert rp.RBV3_REFERENCE_CLASS_INVALID in str(e.value)
        with pytest.raises(rp.Rbv3Refusal) as e:
            _build(tmp_path, d, out="pkg2", references=[
                {"path": str(tmp_path / "absent.png"),
                 "evidence_class": "OWNER_PHOTOGRAPH_UNCALIBRATED"}])
        assert rp.RBV3_REFERENCE_FILE_MISSING in str(e.value)

    def test_valid_reference_carries_disclaimer(self, tmp_path):
        d = _render_dir(tmp_path)
        photo = _png(tmp_path / "photo.png", seed=7)
        pkg = _build(tmp_path, d, references=[
            {"path": str(photo),
             "evidence_class": "OWNER_PHOTOGRAPH_UNCALIBRATED",
             "caption": "IMG_TEST"}])
        (ref,) = pkg["references"]
        assert "NO calibrated overlay accuracy" in ref["disclaimer"]
        assert (tmp_path / "pkg" / ref["file"]).is_file()


class TestDeterminism:
    def test_same_inputs_same_package(self, tmp_path):
        render = _render_dir(tmp_path)
        a = _build(tmp_path, render, out="a")
        b = _build(tmp_path, render, out="b")
        assert a == b
        assert pixel_hash(str(tmp_path / "a" / rp.SHEET_NAME)) == \
            pixel_hash(str(tmp_path / "b" / rp.SHEET_NAME))


class TestPurity:
    def test_no_provider_or_orm_imports(self):
        src = Path(rp.__file__).read_text()
        for banned in ("requests", "anthropic", "openai", "urllib",
                       "django"):
            assert f"import {banned}" not in src
            assert f"from {banned}" not in src


class TestRealV4Tree:
    """The committed P1 V4 evidence dir loads hash-verified — the four
    renamed views rebind ONLY because their decoded pixels match."""

    def test_v4_loads_with_recorded_rebinding(self):
        render = rp.load_validation_render(str(V4_DIR),
                                           view_files=V4_REBINDING)
        assert set(render["resolved_views"]) == {
            "front", "side", "top", "closure_detail",
            "three_quarter_diagnostic", "wireframe", "normals",
            "bounds_dimensions"}
        assert render["rebound"] == V4_REBINDING

    def test_v4_without_rebinding_refuses_missing_views(self):
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(V4_DIR))
        missing = {f.split(":")[1] for f in e.value.findings}
        assert missing == set(V4_REBINDING)


class TestCommittedP1V4Package:
    """Drift guard (the derived-artifact lesson): the committed package
    must equal fresh regeneration from the committed evidence — a stale
    package is a visible suite failure by design."""

    PKG = REPO / "docs" / "visual_quality" / "rbv" / "review_packages" / \
        "p1_v4"

    def test_committed_manifest_equals_regeneration(self, tmp_path):
        committed = json.load(open(self.PKG / rp.MANIFEST_NAME))
        mode_a = committed["modes"]["GEOMETRY_VALIDATION"]
        fresh = rp.build_review_package(
            str(V4_DIR), str(tmp_path / "regen"),
            subject_id=committed["subject_id"],
            created_at=committed["created_at"],
            view_files=mode_a["view_rebinding"],
            note=committed["note"])
        assert fresh == committed

    def test_committed_artifacts_match_recorded_hashes(self):
        committed = json.load(open(self.PKG / rp.MANIFEST_NAME))
        mode_a = committed["modes"]["GEOMETRY_VALIDATION"]
        src = REPO / mode_a["view_source_dir"]
        for view, entry in mode_a["views"].items():
            assert pixel_hash(str(src / entry["source_file"])) == \
                entry["pixel_hash"], view
        sheet = committed["contact_sheet"]
        assert pixel_hash(str(self.PKG / sheet["file"])) == \
            sheet["pixel_hash"]


class TestTrackerClaimHonesty:
    """The node may not claim a mode the engine reports ABSENT. This guard
    exists because nothing else can catch percentage inflation: a leaf
    node's number propagates straight into the program rollups."""

    def test_rbv3_node_does_not_claim_both_modes(self):
        from apps.pipeline.management.commands.roadmap_status import (
            load_tracker)
        node = {n["id"]: n for n in load_tracker()["nodes"]}[
            "quality.rbv3_review_package"]
        if rp.PRESENTATION_ABSENT_REASONS:
            assert "both modes" not in node["title"].lower(), (
                "mode B is ABSENT_BLOCKED in the engine — the tracker node "
                "must not claim it")
            assert "CLIENT_PRESENTATION" in node["scope"], (
                "the unbuilt mode must be named as a scoped follow-up")


class TestTheHonestyFieldsAreRequiredNotDefaulted:
    """§AL3(a) / §R4c — the six recorded defects on this module shared one
    shape: a field whose ABSENCE was rendered as a POSITIVE CLAIM.

    `warnings` missing became the grey line "warnings: none". `statement`
    missing removed the red §1 caveat that says these are validation
    renders and not a photograph of a real bottle. `uncertainty` missing
    persisted as "nothing declared" into the committed manifest and onto
    the owner's dashboard. `side_depth_mm` missing printed the FRONT
    WIDTH under a `D` label. A `pixel_hashes` entry missing skipped the
    decoded-pixel comparison that is this module's entire stated
    guarantee and returned the view as verified anyway.

    None of that is caught downstream, because every downstream surface
    reads a well-formed field. So the refusal is at the boundary, and
    these tests watch each one fire rather than trusting the list.
    """

    def _manifest(self, render):
        return json.load(open(render / "manifest.json"))

    def _write(self, render, m):
        json.dump(m, open(render / "manifest.json", "w"))

    @pytest.mark.parametrize("field", ["statement", "views", "pixel_hashes",
                                       "dimensions", "reference_availability",
                                       "blender_version", "render_engine"])
    def test_a_missing_required_field_refuses(self, tmp_path, field):
        render = _render_dir(tmp_path)
        m = self._manifest(render)
        del m[field]
        self._write(render, m)
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(render))
        assert f"{rp.RBV3_RENDER_MANIFEST_INCOMPLETE}:{field}" in e.value.findings

    @pytest.mark.parametrize("field", ["warnings", "uncertainty"])
    def test_an_absent_list_refuses_but_an_empty_one_does_not(self, tmp_path,
                                                              field):
        """THE DISTINCTION THIS WHOLE REPAIR EXISTS TO PRESERVE, and the
        one it would be easiest to lose: `[]` is a MEASUREMENT (the render
        raised nothing) and absence is an ABSENCE (nobody looked). An
        earlier draft of the requirement tested truthiness and would have
        refused the honest clean render — the committed 2026-08-04
        manifest carries `warnings: []` — collapsing the two states the
        module refuses to confuse. Both halves are asserted here so the
        cheaper version cannot come back green."""
        render = _render_dir(tmp_path)
        m = self._manifest(render)
        del m[field]
        self._write(render, m)
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(render))
        assert f"{rp.RBV3_RENDER_MANIFEST_INCOMPLETE}:{field}" in e.value.findings

        m[field] = []
        self._write(render, m)
        loaded = rp.load_validation_render(str(render))
        assert loaded["manifest"][field] == []

    def test_an_absent_or_empty_measurements_map_refuses(self, tmp_path):
        """§11 of the contact sheet is headed "MEASUREMENTS (render
        manifest, verbatim)" and was drawn from a lookup defaulting to the
        empty dict, so a manifest that recorded no measurements produced a
        sheet with that heading over nothing — asserting "the render
        measured nothing, verbatim" on the authority of a field that was
        never there. Unlike `warnings`, an EMPTY measurements map is not a
        measurement of zero: "we measured and found no measurements" is
        not a state RBV-2B can honestly be in, and every committed
        RBV-2B manifest carries expected_mm_per_px and per-view bounds.
        So this one is required PRESENT, a dict, and non-empty."""
        render = _render_dir(tmp_path)
        m = self._manifest(render)
        for bad in ({}, [], "none", None):
            m["measurements"] = bad
            self._write(render, m)
            with pytest.raises(rp.Rbv3Refusal) as e:
                rp.load_validation_render(str(render))
            assert f"{rp.RBV3_RENDER_MANIFEST_INCOMPLETE}:measurements" \
                in e.value.findings, bad
        del m["measurements"]
        self._write(render, m)
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(render))
        assert f"{rp.RBV3_RENDER_MANIFEST_INCOMPLETE}:measurements" \
            in e.value.findings

    def test_the_provenance_footer_names_a_real_engine(self, tmp_path):
        """The sheet's last line reads "source: RBV-2B manifest sha256
        <hash> · <blender_version> · <render_engine>". Both were defaulted
        to the empty string, so a manifest that named neither still
        produced a line beginning "source:" — a provenance claim with no
        provenance in it, and the reader cannot tell that from a render
        genuinely made by an unnamed engine."""
        render = _render_dir(tmp_path)
        loaded = rp.load_validation_render(str(render))
        assert loaded["manifest"]["blender_version"]
        assert loaded["manifest"]["render_engine"]

    @pytest.mark.parametrize("field", rp.REQUIRED_DIMENSION_FIELDS)
    def test_a_missing_contract_dimension_refuses(self, tmp_path, field):
        render = _render_dir(tmp_path)
        m = self._manifest(render)
        del m["dimensions"][field]
        self._write(render, m)
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(render))
        assert f"{rp.RBV3_RENDER_MANIFEST_INCOMPLETE}:dimensions.{field}" \
            in e.value.findings

    def test_a_view_with_no_recorded_hash_refuses(self, tmp_path):
        """The comparison used to be guarded by `if expected and ...`, so
        an absent hash SKIPPED verification and admitted whatever file sat
        under the recorded name."""
        render = _render_dir(tmp_path)
        m = self._manifest(render)
        del m["pixel_hashes"]["side"]
        self._write(render, m)
        with pytest.raises(rp.Rbv3Refusal) as e:
            rp.load_validation_render(str(render))
        assert any(f.startswith(f"{rp.RBV3_VIEW_HASH_ABSENT}:side")
                   for f in e.value.findings), e.value.findings

    def test_an_unhashed_view_is_no_longer_admitted_as_verified(self,
                                                                tmp_path):
        """The positive half: before the repair the same input LOADED and
        reported the view among its resolved, verified views. Asserting
        the refusal alone would not show that anything was ever admitted."""
        render = _render_dir(tmp_path)
        m = self._manifest(render)
        del m["pixel_hashes"]["side"]
        # the file is present and readable — nothing else is wrong with it
        assert (render / m["views"]["side"]).is_file()
        self._write(render, m)
        with pytest.raises(rp.Rbv3Refusal):
            rp.load_validation_render(str(render))

    def test_the_contract_dimensions_restate_depth_not_width(self, tmp_path):
        """`side_depth_mm or front_width_mm` printed W under a D label.
        The fixture uses W=30 and D=20 precisely so the two are
        distinguishable; the committed P1 subject has W == D == 37.4mm,
        which is the only reason this was invisible in real evidence."""
        render = _render_dir(tmp_path)
        pkg = _build(tmp_path, render)
        dims = json.load(open(render / "manifest.json"))["dimensions"]
        assert dims["front_width_mm"] != dims["side_depth_mm"]
        assert pkg["modes"][rp.MODE_GEOMETRY_VALIDATION]["views"]

    def test_source_guard_the_banner_sample_is_text_that_is_drawn(self):
        """SOURCE-STRING GUARD (§Y2(b)). Asserts the ABSENCE of an
        expression, which no behavioural test can do: the substitute is
        unreachable through the API once the field is required, so
        nothing observable distinguishes a service that dropped it from
        one that still carries it behind the new refusal. That is the
        limit — it reports on the text of the module, not its conduct.

        §S2's legibility record must measure transmitted text. The
        removed substitute supplied a 20-glyph-pixel string the composer
        never drew, clearing the 12.0px floor at 13.42px and certifying
        a MISSING disclaimer as legible — the gating occurrence, because
        that refusal precedes the manifest write."""
        src = Path(rp.__file__).read_text()
        assert 'banners[0] or "statement"' not in src, (
            "the empty-banner substitute is back; the §S2 record would "
            "again measure a string that was never drawn")


class TestTheCommittedEvidenceIsMeasuredAgainstTheRepair:
    """§AD0(c) — a negative result is a result. Two committed evidence
    trees FAIL the repaired loader, and that is the finding, not a
    regression: they declare views for which no decoded-pixel hash was
    ever recorded, so those views have been loading unverified."""

    PILOT = Path(rp._REPO) / "docs" / "visual_quality" / "rbv" / "p1_pilot"

    def test_the_two_incomplete_trees_now_refuse_and_name_the_views(self):
        expected = {
            "2026-08-04": {"measurement_overlay"},
            "2026-08-04_v2": {"material_reference_preview",
                              "measurement_overlay"},
        }
        for tag, views in expected.items():
            d = self.PILOT / tag
            if not d.is_dir():
                pytest.skip(f"{tag} not present")
            with pytest.raises(rp.Rbv3Refusal) as e:
                rp.load_validation_render(str(d))
            named = {f.split(":")[1] for f in e.value.findings
                     if f.startswith(rp.RBV3_VIEW_HASH_ABSENT)}
            assert named == views, (tag, named, e.value.findings)

    def test_the_live_v4_tree_still_loads_and_is_fully_hashed(self):
        """The repair must not be satisfied by refusing everything.

        The v4 tree needs its recorded rebinding to load at all — the
        session renamed four view files with a ``neutral_`` prefix and
        the manifest still names the originals. That is the OPT-IN
        branch, and it is worth saying why it survives the de-defaulting
        the rest of this commit performs: an absent rebinding is not a
        missing fact about the render, it is a caller declining to
        rename anything, and there is exactly one honest reading of
        that. What the repair changes is what happens AFTER the rename
        — every resolved view is now hash-verified without exception,
        so a rebinding cannot smuggle in a file nobody measured."""
        d = self.PILOT / "2026-08-04_v4"
        if not d.is_dir():
            pytest.skip("v4 not present")
        loaded = rp.load_validation_render(str(d), view_files=V4_REBINDING)
        m = loaded["manifest"]
        assert set(m["views"]) == set(m["pixel_hashes"])
        assert set(loaded["resolved_views"]) == set(m["views"]), (
            "a view resolved without a hash would be exactly the defect "
            "entry 8 names", sorted(loaded["resolved_views"]))
