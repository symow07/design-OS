"""VQR-3 — the logo axis stops being UNMEASURED, and says something true.

``visual_quality_gate._logo_axis`` has read ``container_logo_metrics/1.0``
since VQR-2A and nothing produced it, so the axis was UNMEASURED — blocking
— for the whole arc. These tests pin the PROPERTIES the producer claims,
not the numbers one run happened to print:

* distortion is DERIVED from the asset's own intrinsic aspect, over a
  generated space of aspects, so a hard-coded ``False`` cannot pass;
* an unmeasurable asset yields NO record, because a record whose
  ``materially_distorted`` is absent reads at the gate as "undistorted" —
  a claim made from no measurement;
* across several placements the WORST case governs, so a defective
  placement cannot be averaged away;
* the gate's ``logo_min_extent_pt`` is untouched. The axis is meant to
  flip by artwork being fixed, never by the floor being lowered.
"""
import json
import os

import pytest
from django.conf import settings

from apps.ire import container_logo_metrics as clm
from apps.ire import design_graph_v2 as dg2
# [the owner's second answer of 2026-09-25: the placed marks as production reads them — apps/ire/brand_mark.py]
from apps.ire.brand_mark import logo_nodes as _logo_nodes
from apps.ire.compose_container import (
    compose_container_graph,
    container_design_graph_record,
)
from apps.ire.graph import Document, Group, Image
from apps.ire.nodes import rect_clip
from apps.pipeline.services import visual_quality_gate as vqg
from apps.pipeline.targets.container import _owner_confirmed_logo_assets
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

APPROVED_PNG = os.path.join(
    settings.BASE_DIR, "docs", "visual_quality", "vq2", "brand",
    "bbrose_logo_approved.png")


def _png(tmp_path, name, width, height):
    """A real raster of an exactly known intrinsic aspect."""
    from PIL import Image as PILImage
    path = tmp_path / name
    PILImage.new("RGB", (width, height), (200, 120, 140)).save(path)
    return str(path)


def _doc(*images, page=(100.0, 200.0)):
    return Document(page_w=page[0], page_h=page[1],
                    root=Group(name="Root", children=list(images)))


def _image(src, *, name="logo", x=10.0, y=10.0, w=40.0, h=10.0, clip=None):
    return Image(name=name, src=src, x=x, y=y, w=w, h=h, clip=clip)


def _composed(logo_path, **kw):
    return compose_container_graph(
        build_backbone(ContainerProfile(archetype="bottle", )), logo_path=logo_path,
        product_name="Liquid Veil", sku="LV-01", native=True, **kw)


def _composed_dropper(logo_path):
    """The OTHER composer. The dropper sheet is a separate placement site
    with its own hard-coded aspect in its history, and until this existed
    the only dropper test in the suite passed logo_path=None — so that site
    was fixed and unguarded at the same time."""
    from apps.ire.compose_dropper import compose_dropper_sheet
    geometry = {
        "total_height_mm": 104.0, "body_height_mm": 70.5,
        "body_diameter_mm": 31.5, "collar_height_mm": 9.5,
        "bulb_height_mm": 21.5, "collar_diameter_mm": 21.5,
        "bulb_width_mm": 11.0, "visible_neck_mm": 2.5,
        "neck_diameter_mm": 9.0, "base_thickness_mm": 3.5,
        "shoulder_radius_mm": 3.0, "frost_intensity": 0.7,
        "translucency": 0.35}
    zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE",
              "x": 5.5, "y": 10.0, "width": 22.0, "height": 40.0}]
    return compose_dropper_sheet(
        geometry, zones=zones, reference_path=None, logo_path=logo_path,
        product_name="Rose Damascena", sku="X",
        back_sections=[{"heading": "P", "text": "x"}],
        revision_status="TEST")


def _graph(doc):
    return dg2.build(
        container_design_graph_record(doc, zones_consumed=[], mode="native"),
        components=dg2.components_from_document(doc, backbone_source="test"))


class TestTheAxisWasUnmeasuredAndIsNowMeasured:
    """Against the REAL composer output, not a hand-written spec dict."""

    def test_without_the_producer_the_axis_is_unmeasured(self):
        doc = _composed(settings.BRAND_LOGO_PATH)
        axis = vqg._logo_axis({}, _graph(doc))
        assert axis["state"] == vqg.UNMEASURED
        assert axis["code"] == vqg.VQ_LOGO_METRICS_UNMEASURED
        # the axis is blocking while unmeasured — that is why this matters
        assert axis["required"] is True

    def test_with_the_producer_the_real_document_is_measured(self):
        doc = _composed(settings.BRAND_LOGO_PATH)
        record = clm.measure_logo_metrics(doc)
        assert record is not None
        axis = vqg._logo_axis({clm.SCHEMA: record}, _graph(doc))
        assert axis["state"] in (vqg.PASS, vqg.FAIL)
        assert axis["state"] != vqg.UNMEASURED

    def test_the_real_document_places_the_logo_at_the_assets_own_aspect(self):
        """The composer used to place every logo at a hard-coded 0.36
        whatever the file was, stretching the deployed mark by 73%. The
        height is now read from the asset, so the emitted aspect IS the
        intrinsic one — and the same measurement still condemns the old
        number, which is what makes this a fix rather than a blind spot."""
        record = clm.measure_logo_metrics(_composed(settings.BRAND_LOGO_PATH))
        placement = record["placements"][0]
        assert record["materially_distorted"] is False
        assert placement["rendered_aspect"] == placement["intrinsic_aspect"]

        # the superseded constant, measured through the same code that
        # cleared the fix: 0.36 was a real defect, not a tolerance artefact
        was = _doc(_image(settings.BRAND_LOGO_PATH,
                          w=placement["placed_mm"][2],
                          h=placement["placed_mm"][2] * 0.36))
        old = clm.measure_logo_metrics(was)
        assert old["materially_distorted"] is True
        assert old["placements"][0]["aspect_deviation"] > 0.7

    def test_the_owners_own_asset_places_at_the_aspect_the_owner_confirmed(
            self):
        """Ties the emitted artwork back to the OWNER'S record, not merely to
        the PNG: the confirmation states the mark's bounds in points, and the
        placed aspect must be the aspect those bounds describe."""
        record = clm.measure_logo_metrics(
            _composed(APPROVED_PNG), confirmed_assets=[APPROVED_PNG])
        assert record["assets"][0]["owner_confirmed"] is True
        assert record["materially_distorted"] is False

        with open(os.path.join(
                settings.BASE_DIR, "docs", "visual_quality", "vq2",
                "vq2_authoritative_bbrose_logo.json")) as fh:
            confirmed = json.load(fh)
        x0, y0, x1, y1 = confirmed["extraction_bounds_pt"]
        assert record["placements"][0]["rendered_aspect"] == pytest.approx(
            (y1 - y0) / (x1 - x0), rel=1e-3)

    def test_two_assets_of_different_aspect_do_not_render_the_same_shape(self):
        """The regression guard. A re-hard-coded height would place both of
        these identically; reading the file cannot."""
        wide = clm.measure_logo_metrics(_composed(settings.BRAND_LOGO_PATH))
        tall = clm.measure_logo_metrics(_composed(APPROVED_PNG))
        assert wide["placements"][0]["rendered_extent_pt"] == \
            tall["placements"][0]["rendered_extent_pt"]
        assert wide["placements"][0]["rendered_aspect"] != \
            tall["placements"][0]["rendered_aspect"]

    def test_an_unreadable_asset_places_no_logo_rather_than_a_guessed_one(
            self, tmp_path):
        """No aspect means no placement. The composer must not fall back to
        a shape it invented — that is the defect being fixed."""
        broken = tmp_path / "broken-logo.png"
        broken.write_bytes(b"not a png")
        doc = _composed(str(broken))
        assert clm.logo_image_nodes(doc) == []
        # [the owner's second answer of 2026-09-25: production reads the placed marks through brand_mark.logo_nodes
        # (the raster and the mark drawn from an approved master alike) and no longer calls logo_image_nodes; both
        # are held — logo_image_nodes is the raster classifier logo_nodes must equal, node for node, on a document
        # with no master-drawn mark]
        assert _logo_nodes(doc) == []
        assert clm.measure_logo_metrics(doc) is None


class TestTheDropperSheetPlacesItsLogosUndistorted:
    """The second placement site. The container composer and the dropper
    composer each carried their own invented aspect (0.36 and 0.30), so
    fixing one proves nothing about the other."""

    def test_every_dropper_placement_is_undistorted(self):
        record = clm.measure_logo_metrics(
            _composed_dropper(settings.BRAND_LOGO_PATH))
        assert record is not None
        # the sheet draws the mark twice — hero and flat view
        assert record["placement_count"] >= 2
        for placement in record["placements"]:
            assert placement["aspect_deviation"] == 0.0, placement
        assert record["materially_distorted"] is False

    def test_the_dropper_axis_passes_on_measured_geometry(self):
        doc = _composed_dropper(settings.BRAND_LOGO_PATH)
        record = clm.measure_logo_metrics(doc)
        axis = vqg._logo_axis({clm.SCHEMA: record}, _graph(doc))
        assert axis["state"] == vqg.PASS, (axis, record)

    def test_the_dropper_reads_the_asset_rather_than_a_constant(self):
        """Two assets of different aspect must place as different shapes at
        the same width — a re-hard-coded height could not do that."""
        wide = clm.measure_logo_metrics(
            _composed_dropper(settings.BRAND_LOGO_PATH))["placements"][0]
        tall = clm.measure_logo_metrics(
            _composed_dropper(APPROVED_PNG))["placements"][0]
        assert wide["rendered_extent_pt"] == tall["rendered_extent_pt"]
        assert wide["rendered_aspect"] != tall["rendered_aspect"]


class TestDistortionIsDerivedNotAsserted:
    """Generated over aspects, so neither a hard-coded True nor a
    hard-coded False survives."""

    @pytest.mark.parametrize("width,height", [
        (1439, 300), (3721, 886), (100, 100), (300, 1439), (2000, 41)])
    def test_a_placement_at_the_assets_own_aspect_is_undistorted(
            self, tmp_path, width, height):
        src = _png(tmp_path, f"a{width}x{height}.png", width, height)
        placed_w = 40.0
        doc = _doc(_image(src, w=placed_w, h=placed_w * height / width))
        record = clm.measure_logo_metrics(doc)
        assert record["materially_distorted"] is False
        assert record["placements"][0]["aspect_deviation"] \
            <= clm.ASPECT_TOLERANCE

    @pytest.mark.parametrize("stretch", [0.5, 0.8, 0.97, 1.03, 1.2, 1.727, 4.0])
    def test_any_placement_off_that_aspect_is_distorted(self, tmp_path,
                                                        stretch):
        src = _png(tmp_path, "a.png", 1439, 300)
        native_h = 40.0 * 300 / 1439
        doc = _doc(_image(src, w=40.0, h=native_h * stretch))
        record = clm.measure_logo_metrics(doc)
        expected = abs(stretch - 1.0) > clm.ASPECT_TOLERANCE
        assert record["materially_distorted"] is expected
        assert record["placements"][0]["aspect_deviation"] == \
            pytest.approx(abs(stretch - 1.0), abs=1e-6)

    @pytest.mark.parametrize("w,h", [(0.0, 10.0), (40.0, 0.0), (0.0, 0.0)])
    def test_a_box_with_no_aspect_is_a_measured_defect(self, tmp_path, w, h):
        """Not unmeasurable — measurably broken. It must reach the gate as a
        FAIL, never as a plausible-looking 0.0 aspect."""
        src = _png(tmp_path, "a.png", 400, 100)
        record = clm.measure_logo_metrics(_doc(_image(src, w=w, h=h)))
        placement = record["placements"][0]
        assert placement["degenerate_box"] is True
        assert placement["rendered_aspect"] is None
        assert placement["aspect_deviation"] is None
        assert record["materially_distorted"] is True
        assert vqg._logo_axis({clm.SCHEMA: record}, {})["state"] == vqg.FAIL

    def test_the_intrinsic_aspect_is_read_from_the_file_not_the_node(
            self, tmp_path):
        """Two placements of identical geometry, different assets: only the
        one whose file disagrees with the box is distorted."""
        square = _png(tmp_path, "square.png", 400, 400)
        wide = _png(tmp_path, "wide.png", 400, 100)
        assert clm.measure_logo_metrics(
            _doc(_image(square, w=30.0, h=30.0)))[
                "materially_distorted"] is False
        assert clm.measure_logo_metrics(
            _doc(_image(wide, w=30.0, h=30.0)))[
                "materially_distorted"] is True


class TestAnUnmeasurableAssetProducesNoRecord:
    """A record the gate can read is a claim. No measurement, no claim."""

    def test_no_logo_emitted_means_no_record(self):
        doc = _composed(None)
        assert clm.logo_image_nodes(doc) == []
        assert _logo_nodes(doc) == []        # [2026-09-25: what production reads — see the note above]
        assert clm.measure_logo_metrics(doc) is None

    def test_a_logo_node_whose_asset_cannot_be_read_produces_no_record(
            self, tmp_path):
        bad = tmp_path / "logo.png"
        bad.write_bytes(b"not a png")
        doc = _doc(_image(str(bad)))
        # the node IS there — the absence is of the MEASUREMENT, not the logo
        assert len(clm.logo_image_nodes(doc)) == 1
        assert _logo_nodes(doc) == clm.logo_image_nodes(doc)     # [2026-09-25: what production reads, node for node]
        assert clm.measure_logo_metrics(doc) is None

    def test_that_absence_leaves_the_axis_unmeasured_not_passing(
            self, tmp_path):
        bad = tmp_path / "logo.png"
        bad.write_bytes(b"not a png")
        doc = _doc(_image(str(bad)))
        spec = {}
        record = clm.measure_logo_metrics(doc)
        if record is not None:
            spec[clm.SCHEMA] = record
        axis = vqg._logo_axis(spec, _graph(doc))
        assert axis["state"] == vqg.UNMEASURED

    def test_one_unreadable_asset_suppresses_the_whole_record(self, tmp_path):
        """A partial record would let a measured placement vouch for an
        unmeasured one."""
        good = _png(tmp_path, "good.png", 400, 100)
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not a png")
        doc = _doc(_image(good, name="logo-hero", w=40.0, h=10.0),
                   _image(str(bad), name="logo-flat", w=20.0, h=5.0))
        assert clm.measure_logo_metrics(doc) is None


class TestTheWorstPlacementGoverns:
    def test_extent_is_the_smallest_placement_not_the_average(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, name="logo-hero", w=40.0, h=10.0),
                   _image(src, name="logo-flat", w=4.0, h=1.0))
        record = clm.measure_logo_metrics(doc)
        extents = [p["rendered_extent_pt"] for p in record["placements"]]
        assert record["placement_count"] == 2
        assert record["rendered_extent_pt"] == min(extents)

    def test_one_distorted_placement_distorts_the_record(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, name="logo-hero", w=40.0, h=10.0),
                   _image(src, name="logo-flat", w=40.0, h=25.0))
        record = clm.measure_logo_metrics(doc)
        assert [p["materially_distorted"] for p in record["placements"]] \
            == [False, True]
        assert record["materially_distorted"] is True

    def test_one_clipped_placement_clips_the_record(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, name="logo-hero", w=40.0, h=10.0),
                   _image(src, name="logo-off", x=90.0, w=40.0, h=10.0))
        record = clm.measure_logo_metrics(doc)
        assert record["clipped"] is True
        assert "page_bounds" in record["placements"][1]["clip_findings"]


class TestClippingIsMeasuredGeometry:
    def test_a_placement_inside_its_clip_is_not_clipped(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, x=10.0, y=10.0, w=40.0, h=10.0,
                          clip=rect_clip(5.0, 5.0, 50.0, 20.0)))
        record = clm.measure_logo_metrics(doc)
        assert record["clipped"] is False

    def test_a_placement_leaving_its_clip_is_clipped(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, x=10.0, y=10.0, w=40.0, h=10.0,
                          clip=rect_clip(10.0, 10.0, 20.0, 10.0)))
        record = clm.measure_logo_metrics(doc)
        assert record["clipped"] is True
        assert record["placements"][0]["clip_findings"] == ["clip_path"]

    def test_a_placement_leaving_the_page_is_clipped(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, x=-5.0, y=10.0, w=40.0, h=10.0))
        record = clm.measure_logo_metrics(doc)
        assert record["clipped"] is True
        assert record["placements"][0]["clip_findings"] == ["page_bounds"]


class TestOwnerConfirmationIsNeverInvented:
    def test_with_no_confirmation_supplied_the_answer_is_unknown(
            self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        record = clm.measure_logo_metrics(_doc(_image(src)))
        # None, NOT False — nothing was checked, so nothing is denied
        assert record["assets"][0]["owner_confirmed"] is None

    def test_the_deployed_asset_is_not_one_the_owner_confirmed(self):
        confirmed = _owner_confirmed_logo_assets()
        assert confirmed, "the VQ-2 owner confirmation record must be on disk"
        record = clm.measure_logo_metrics(
            _composed(settings.BRAND_LOGO_PATH), confirmed_assets=confirmed)
        assert record["assets"][0]["owner_confirmed"] is False

    def test_the_confirmed_paths_come_from_the_owners_record(self):
        names = {os.path.basename(p) for p in _owner_confirmed_logo_assets()}
        assert names == {"bbrose_logo_approved.ai", "bbrose_logo_approved.pdf",
                         "bbrose_logo_approved.png"}


class TestComponentBoundsAreMeasuredNotInvented:
    def test_an_image_components_bounds_are_its_emitted_box(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = _doc(_image(src, w=17.28, h=6.221))
        logo = [c for c in dg2.components_from_document(doc)
                if c["role"] == dg2.ROLE_LOGO][0]
        assert logo["bounds_mm"] == {"width_mm": 17.28, "height_mm": 6.221}
        assert logo["provenance"]["bounds_measured_from"] == \
            "emitted image node box"

    def test_a_group_component_still_has_no_bounds(self, tmp_path):
        src = _png(tmp_path, "a.png", 400, 100)
        doc = Document(page_w=100.0, page_h=200.0, root=Group(
            name="Root", children=[
                _image(src),
                Group(name="motif-botanical", children=[]),
                Group(name="Surface-front", children=[])]))
        groups = [c for c in dg2.components_from_document(doc)
                  if c["role"] in (dg2.ROLE_MOTIF, dg2.ROLE_LABEL_PANEL)]
        assert len(groups) == 2
        assert all(c["bounds_mm"] is None for c in groups)
        assert all("bounds_measured_from" not in c["provenance"]
                   for c in groups)

    def test_the_real_documents_logo_bounds_match_the_metrics(self):
        doc = _composed(settings.BRAND_LOGO_PATH)
        record = clm.measure_logo_metrics(doc)
        logo = [c for c in dg2.components_from_document(doc)
                if c["role"] == dg2.ROLE_LOGO][0]
        placed = record["placements"][0]["placed_mm"]
        assert logo["bounds_mm"] == {"width_mm": placed[2],
                                     "height_mm": placed[3]}


class TestTheThresholdIsNotTouched:
    def test_the_minimum_extent_floor_is_unchanged(self):
        assert vqg.THRESHOLDS["logo_min_extent_pt"] == 8.0

    def test_the_aspect_tolerance_is_not_the_gates_design_threshold(self):
        """Borrowing `silhouette_max_aspect_deviation` would import a
        provenance that was calibrated for something else."""
        assert clm.ASPECT_TOLERANCE != \
            vqg.THRESHOLDS["silhouette_max_aspect_deviation"]

    def test_the_pass_does_not_depend_on_the_tolerance(self):
        """The emitted deviation is EXACTLY zero, so the artwork would clear
        a tolerance of nothing at all. The axis does not pass because 0.01
        is generous — it passes because the placement stopped guessing."""
        record = clm.measure_logo_metrics(_composed(settings.BRAND_LOGO_PATH))
        assert record["placements"][0]["aspect_deviation"] == 0.0


# =====================================================================================================================
# THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
# testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." The switch
# (apps/ire/brand_mark.py) is built and NOT thrown: his trace is on file nowhere. Every master below is a SYNTHETIC
# fixture (apps/ire/tests/brand_mark_fixtures.py) placed in a pytest tmp_path, except the one test that READS his two
# trace files where they sit, to prove their shapes are covered — and places neither.
# =====================================================================================================================

#: potrace's DOCTYPE as the fixtures carry it — read at collection, for the grammar's parametrised refusals
from apps.ire.tests.brand_mark_fixtures import POTRACE_DOCTYPE_BYTES as FX_DOCTYPE  # noqa: E402


def _approval_root(tmp_path, svg=None, **overrides):
    from apps.ire.tests import brand_mark_fixtures as FX
    root = tmp_path / "root"
    FX.write_approval(root, FX.POTRACE_STYLE if svg is None else svg, **overrides)
    return root


@pytest.fixture
def lookup_on(monkeypatch):
    """The approval lookup, ON for one test — the suite runs with it off."""
    monkeypatch.setattr(settings, "BRAND_MARK_APPROVAL_LOOKUP", True)


class TestTheSwitchIsBuiltAndNotThrown:

    def test_the_suite_never_reads_an_approval_even_a_valid_one(self, tmp_path):
        """No test moves the day his approved master is placed: the suite's lookup is off, so a VALID approval on
        file is not read — the PNG is drawn and no master is handed to any composer."""
        from apps.ire import brand_mark as B
        assert settings.BRAND_MARK_APPROVAL_LOOKUP is False
        root = _approval_root(tmp_path)
        assert B.approved_master(root=root)["state"] == B.LOOKUP_OFF
        house = B.house_mark(root=root)
        assert (house["state"], house["master"], house["codes"]) == (B.LOOKUP_OFF, None, [])
        assert B.confirmed_assets(root=root) == []

    def test_with_no_approval_on_file_the_png_is_the_one_picked_before(self, tmp_path, lookup_on):
        from apps.ire import brand_mark as B
        house = B.house_mark(root=tmp_path)
        before = settings.BRAND_LOGO_PATH if (settings.BRAND_LOGO_PATH
                                              and os.path.exists(settings.BRAND_LOGO_PATH)) else None
        assert (house["state"], house["master"], house["codes"], house["png"]) == (B.NO_APPROVAL, None, [], before)

    def test_an_uploaded_logo_stays_the_tasks_own_raster(self, tmp_path, lookup_on):
        """Exactly the pick made before: an uploaded logo, only if it exists — never BRAND_LOGO_PATH in its place —
        and never the master, even with a valid approval on file."""
        from apps.ire import brand_mark as B
        root = _approval_root(tmp_path)
        upload = _png(tmp_path, "upload.png", 300, 100)
        house = B.house_mark({"logo": upload}, root=root)
        assert (house["state"], house["png"], house["master"]) == (B.UPLOADED, upload, None)
        gone = B.house_mark({"logo": str(tmp_path / "missing.png")}, root=root)
        assert (gone["png"], gone["master"]) == (None, None)

    def test_a_valid_approval_hands_the_composers_its_master(self, tmp_path, lookup_on):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        root = _approval_root(tmp_path)
        house = B.house_mark(root=root)
        assert (house["state"], house["codes"]) == (B.APPROVED, [])
        assert house["master"].sha256 == FX.sha256(FX.POTRACE_STYLE)
        assert B.confirmed_assets(root=root) == [house["master"].path]
        record = json.loads(json.dumps(B.selection_record(house)))
        assert record["master"]["ink_aspect"] == round(FX.POTRACE_INK_ASPECT, 6)
        assert record["approval"]["owner_words"].startswith("A TEST FIXTURE")

    @pytest.mark.parametrize("breach, code, words", [
        # [review of 2026-09-25, §BH58(e): each code names only what was measured — a record that does not parse is
        # UNREADABLE, one that parses and lacks a field INCOMPLETE (the field named), a failed match MATCH_FAILED; a
        # master is MISSING only when it is not found, and UNREADABLE with its OS error otherwise]
        ("unparseable", "BRAND_MARK_APPROVAL_UNREADABLE", "does not parse as JSON"),
        ("not_an_object", "BRAND_MARK_APPROVAL_UNREADABLE", "not a JSON object"),
        ("record_is_a_folder", "BRAND_MARK_APPROVAL_UNREADABLE", "does not read: EISDIR"),
        ("no_words", "BRAND_MARK_APPROVAL_INCOMPLETE", "the owner's words are missing"),
        ("no_register", "BRAND_MARK_APPROVAL_INCOMPLETE", "the register line is missing"),
        ("no_calendar_date", "BRAND_MARK_APPROVAL_INCOMPLETE", "the date 2026-02-30 is not a calendar date"),
        ("match_not_recorded", "BRAND_MARK_APPROVAL_INCOMPLETE", "the emitter-vs-MuPDF match is not recorded"),
        ("match_failed", "BRAND_MARK_APPROVAL_MATCH_FAILED", "the recorded emitter-vs-MuPDF match did not pass"),
        ("missing", "BRAND_MARK_MASTER_MISSING", "bbrose-logo.svg is not found"),
        ("master_is_a_folder", "BRAND_MARK_MASTER_UNREADABLE", "bbrose-logo.svg does not read: EISDIR"),
        ("edited", "BRAND_MARK_MASTER_SHA_MISMATCH", "the master on file hashes"),
        ("stroked", "BRAND_MARK_MASTER_REFUSED", "STROKE"),
    ])
    def test_a_record_that_does_not_hold_draws_the_png_and_names_its_code(self, tmp_path, lookup_on, breach, code,
                                                                          words):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        stroked = FX.variant(b'stroke="none"', b'stroke="#000000"')
        overrides = {"no_words": {"owner_words": " "}, "no_register": {"register": ""},
                     "no_calendar_date": {"date": "2026-02-30"}, "match_not_recorded": {"match": {}},
                     "match_failed": {"match": {"emitter_vs_mupdf": {"passed": False}}}}.get(breach, {})
        root = _approval_root(tmp_path, svg=stroked if breach == "stroked" else None, **overrides)
        folder = root.joinpath(*B.MARK_DIR)
        if breach == "unparseable":
            (folder / B.APPROVAL_FILE).write_text("{ not json")
        elif breach == "not_an_object":
            (folder / B.APPROVAL_FILE).write_text("[1, 2]")
        elif breach == "record_is_a_folder":
            (folder / B.APPROVAL_FILE).unlink()
            (folder / B.APPROVAL_FILE).mkdir()
        elif breach == "missing":
            (folder / B.MASTER_FILE).unlink()
        elif breach == "master_is_a_folder":
            (folder / B.MASTER_FILE).unlink()
            (folder / B.MASTER_FILE).mkdir()
        elif breach == "edited":
            (folder / B.MASTER_FILE).write_bytes(FX.POTRACE_STYLE.replace(b"M1000 1000", b"M1000 1001"))
        house = B.house_mark(root=root)
        assert (house["state"], house["codes"], house["master"]) == (B.REFUSED, [code], None)
        assert words in house["reason"], house["reason"]
        assert house["png"] == (settings.BRAND_LOGO_PATH if os.path.exists(settings.BRAND_LOGO_PATH) else None)
        assert B.confirmed_assets(root=root) == []

    def test_an_incomplete_record_and_a_failed_match_are_named_apart(self, tmp_path, lookup_on):
        """Both at once: two codes, each saying only what it measured."""
        from apps.ire import brand_mark as B
        root = _approval_root(tmp_path, owner_words="", match={"emitter_vs_mupdf": {"passed": False}})
        house = B.house_mark(root=root)
        assert house["codes"] == [B.CODE_APPROVAL_INCOMPLETE, B.CODE_APPROVAL_MATCH_FAILED]
        assert "the owner's words are missing" in house["reason"] and "did not pass" in house["reason"]

    def test_the_review_board_says_the_marks_state_only_when_an_approval_is_on_file(self, tmp_path, lookup_on):
        """The Review Board row reads the record by the switch's own schema constant: the master's sha256 when the
        approval holds, the PNG with every code when it is refused, and NO row when none is on file."""
        from apps.ire import brand_mark as B
        from apps.pipeline.targets.container import _reconstruction_rows
        base = {"container_selected_variation/1.0": {"variation_id": "A_PETAL_WINDOW", "verified": True}}

        def row(spec):
            return [r["value"] for r in _reconstruction_rows(spec) if r["label"] == "Brand mark"]
        approved = B.selection_record(B.house_mark(root=_approval_root(tmp_path / "ok")))
        refused = B.selection_record(B.house_mark(root=_approval_root(tmp_path / "no", owner_words="")))
        assert row(dict(base)) == []
        assert row(dict(base, **{B.SCHEMA: approved})) == [
            "drawn from the approved vector master %s" % approved["master"]["sha256"][:16]]
        assert row(dict(base, **{B.SCHEMA: refused})) == [
            "the PNG — the approval on file is refused: %s" % B.CODE_APPROVAL_INCOMPLETE]

    def test_the_vq2_record_on_file_is_not_an_approval_of_the_master(self, tmp_path, lookup_on, monkeypatch):
        """053d54e's VQ2 record (a different drawing, light blue) is the owner's confirmation of THAT file. A root
        holding it — and nothing under docs/brand/mark — has no approved master, and the confirmed list is the VQ2
        list alone."""
        import shutil

        from apps.ire import brand_mark as B
        root = tmp_path / "root"
        vq2 = os.path.join("docs", "visual_quality", "vq2", "vq2_authoritative_bbrose_logo.json")
        (root / os.path.dirname(vq2)).mkdir(parents=True)
        shutil.copyfile(os.path.join(settings.BASE_DIR, vq2), root / vq2)
        assert B.approved_master(root=root)["state"] == B.NO_APPROVAL
        monkeypatch.setattr(settings, "BASE_DIR", root)
        assert {os.path.basename(p) for p in _owner_confirmed_logo_assets()} == {
            "bbrose_logo_approved.ai", "bbrose_logo_approved.pdf", "bbrose_logo_approved.png"}

    def test_the_confirmed_list_joins_the_master_only_when_its_approval_holds(self, tmp_path, lookup_on,
                                                                               monkeypatch):
        from apps.ire import brand_mark as B
        root = _approval_root(tmp_path)
        monkeypatch.setattr(settings, "BASE_DIR", root)
        master_path = str(root.joinpath(*B.MARK_DIR, B.MASTER_FILE))
        assert _owner_confirmed_logo_assets() == [master_path]            # no VQ2 record under this root
        root.joinpath(*B.MARK_DIR, B.MASTER_FILE).write_bytes(b"<svg/>")
        assert _owner_confirmed_logo_assets() == []

    def test_the_logo_axis_measures_the_vector_mark_and_confirms_it_only_from_its_record(self):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        master = B.read_master(FX.POTRACE_STYLE, path="/fixture/bbrose-logo.svg")
        doc = _composed(None, logo_master=master)
        for confirmed, verdict in (([master.path], True), ([], None), (_owner_confirmed_logo_assets(), False)):
            record = clm.measure_logo_metrics(doc, confirmed_assets=confirmed)
            assert record["materially_distorted"] is False and record["clipped"] is False
            asset = record["assets"][0]
            assert (asset["sha256"], asset["intrinsic_px"], asset["owner_confirmed"]) == (
                master.sha256, None, verdict)
        logo = [c for c in dg2.components_from_document(doc) if c["role"] == dg2.ROLE_LOGO]
        placed = record["placements"][0]["placed_mm"]
        assert [c["bounds_mm"] for c in logo] == [{"width_mm": placed[2], "height_mm": placed[3]}]


class TestTheMastersGrammar:
    """What the approval covers — potrace's grammar and the ® redraw's — and, BY NAME, everything it does not."""

    def _svglib_census(self, tmp_path, data):
        from reportlab.graphics.shapes import Group as RLGroup
        from reportlab.graphics.shapes import Path as RLPath
        from svglib.svglib import svg2rlg
        path = tmp_path / "svglib.svg"
        path.write_bytes(data)
        counts = {"paths": 0, "subpaths": 0, "curves": 0, "lines": 0}

        def walk(node):
            if isinstance(node, RLGroup):
                for child in node.contents:
                    walk(child)
            elif isinstance(node, RLPath):
                counts["paths"] += 1
                counts["subpaths"] += node.operators.count(0)
                counts["lines"] += node.operators.count(1)
                counts["curves"] += node.operators.count(2)
        walk(svg2rlg(str(path)))
        return counts

    def test_both_covered_grammars_read_as_svglib_reads_them(self, tmp_path):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        for data, census in ((FX.POTRACE_STYLE, {"paths": 2, "subpaths": 5, "curves": 8, "lines": 12}),
                             (FX.REG_STYLE, {"paths": 4, "subpaths": 8, "curves": 16, "lines": 15})):
            master = B.read_master(data)
            assert master.census == census == self._svglib_census(tmp_path, data)
            assert master.fill == "#000000"
        assert B.read_master(FX.POTRACE_STYLE).bounds == FX.POTRACE_INK

    def test_the_owners_two_trace_files_are_covered_and_read_exactly(self, tmp_path):
        """READ where they sit — never placed, never copied into the tree — and only the two files on record, by
        sha256: a re-trace is a different file and this skips rather than judging it. The trace record's own census
        (9 paths, 18 subpaths, 3587 curves, 72 lines) and svglib's reading both agree with the switch's; the ® redraw's
        absolute paths beside the group are covered; each file's INK aspect is its own and its padded viewBox's is
        ~5 % off."""
        import hashlib

        from apps.ire import brand_mark as B
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 4, "archive", "work", "bh69_rounds_logo_trace_ui_build", "logo")
        files = {"bbrose-logo-traced.svg": (
                     "7acc36cb2dc4249faaa3c0d9007a8e4ee38078654426df583261778170c76b62",
                     {"paths": 9, "subpaths": 18, "curves": 3587, "lines": 72}),
                 "bbrose-logo-traced-reg.svg": (
                     "dcdb005e0b491b217262f1bbd1903f26b0845c26dd2995e03cfd8111409d813b",
                     {"paths": 9, "subpaths": 18, "curves": 3382, "lines": 74})}
        for name, (sha, census) in files.items():
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                pytest.skip("the owner's trace files are not on this machine")
            with open(path, "rb") as fh:
                data = fh.read()
            if hashlib.sha256(data).hexdigest() != sha:
                pytest.skip(f"{name} is not the file on record (re-traced?) — nothing to judge")
            master = B.read_master(data)
            assert master.census == census == self._svglib_census(tmp_path, data)
            assert master.fill == "#000000"
            assert (305.0 / 1397.0) / master.aspect > 1.04          # the viewBox would stretch the placed box
            # [review of 2026-09-25: the module's docstring says both real traces hold exactly ONE <g> — made true
            # by this count, not by the grammar's refusal of a second]
            import xml.etree.ElementTree as ET
            assert sum(1 for el in ET.fromstring(data).iter() if el.tag == "{http://www.w3.org/2000/svg}g") == 1

    def test_the_ink_bounds_are_the_curves_extrema_never_their_control_points(self):
        from apps.ire import brand_mark as B
        svg = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -15 20 20">'
               b'<path d="M 0 0 C 0 -10 10 -10 10 0 Z"/></svg>')
        assert B.read_master(svg).bounds == pytest.approx((0.0, -7.5, 10.0, 0.0), abs=1e-12)

    @pytest.mark.parametrize("old, new, reason", [
        (b"</g>", b'</g>\n<image href="logo.png" width="10" height="10"/>', "IMAGE"),
        (b"</g>", b'</g>\n<use href="#x"/>', "LINK"),
        (b'<path d="M8000', b'<path xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="#x" d="M8000', "LINK"),
        (b"</g>", b"</g>\n<text>BBROSE</text>", "TEXT"),
        (b'stroke="none"', b'stroke="#000000"', "STROKE"),
        (b'<path d="M8000', b'<path stroke-width="2" d="M8000', "STROKE"),
        (b'<path d="M8000', b'<path fill="#FF0000" d="M8000', "SECOND_FILL_COLOUR"),
        (b'<path d="M8000', b'<path fill="url(#gold)" d="M8000', "FILL"),
        (b'<path d="M8000', b'<path fill-rule="evenodd" d="M8000', "FILL_RULE"),
        (b"scale(0.010000,-0.010000)", b"rotate(3)", "TRANSFORM"),
        (b'<path d="M8000', b'<path transform="translate(1,1)" d="M8000', "TRANSFORM"),
        (b"</g>", b"</g>\n<style>path{fill:red}</style>", "ELEMENT"),
        (b"</g>", b'</g>\n<rect width="5" height="5"/>', "ELEMENT"),
        (b'<path d="M8000', b'<path style="fill:red" d="M8000', "ATTRIBUTE"),
        (b'<path d="M8000', b'<path opacity="0.5" d="M8000', "ATTRIBUTE"),
        (b"M8000 2000 c0 552", b"M8000 2000 a10 10 0 0 1 5 5 c0 552", "PATH_COMMAND"),
        (b"M1000 1000 l3500", b"M1000 l3500", "PATH_DATA"),
        # [review of 2026-09-25 — the grammar made exact. THE RAW BYTES, read before any parser sees them: a DTD with
        # an ENTITY (potrace's DOCTYPE replaced whole), any other DOCTYPE, a comment, CDATA, a processing
        # instruction or an XML declaration that is not potrace's own and first, a byte-order mark, bytes that are
        # not UTF-8]
        (FX_DOCTYPE, b'<!DOCTYPE svg [<!ENTITY m "x">]>', "ENTITY"),
        (FX_DOCTYPE, b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                     b'"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">', "DOCTYPE"),
        (FX_DOCTYPE, FX_DOCTYPE + b"\n" + FX_DOCTYPE, "DOCTYPE"),
        (b"</g>", b"</g>\n<!-- a note -->", "COMMENT"),
        (b"a potrace-style", b"<![CDATA[x]]> a potrace-style", "CDATA"),
        (b"<metadata>", b'<?xml-stylesheet href="gold.css"?>\n<metadata>', "PROCESSING_INSTRUCTION"),
        (b'<?xml version="1.0" standalone="no"?>', b'<?xml version="1.0" encoding="ISO-8859-1"?>',
         "PROCESSING_INSTRUCTION"),
        (b'<?xml version="1.0" standalone="no"?>', b'\n<?xml version="1.0" standalone="no"?>',
         "PROCESSING_INSTRUCTION"),
        (b"<?xml", b"\xef\xbb\xbf<?xml", "BYTE_ORDER_MARK"),
        (b"a potrace-style", b"a potrace\xff\xfestyle", "NOT_UTF8"),
        # NUMBERS: ASCII, finite and within ten million — never read through a Unicode digit or space
        (b"M1000 1000 l3500", b"M1000 1000 l1e999", "NUMBER"),
        (b"M1000 1000 l3500", b"M1000 1000 l1e8", "NUMBER"),
        (b"translate(0.000000,40.000000)", b"translate(0.000000,1e999)", "NUMBER"),
        (b"l3500 0 0 2000", b"l3500 0 NaN 2000", "PATH_COMMAND"),      # NaN is letters: never a number
        (b"translate(0.000000,40.000000)", b"translate(NaN,40.000000)", "TRANSFORM"),
        (b"M1000 1000 l3500", "M1000 1000 l٣500".encode("utf-8"), "PATH_DATA"),
        (b"M1000 1000 l3500", "M1000 1000 l3500".encode("utf-8"), "PATH_DATA"),
        # ONE group, as potrace writes; a transform that scales to nothing; a path with no data
        (b"</g>\n", b'</g>\n<g fill="#000000"><path d="M 1 1 L 2 1 L 2 2 Z"/></g>\n', "ELEMENT"),
        (b"scale(0.010000,-0.010000)", b"scale(0,-0.010000)", "TRANSFORM"),
        (b'<path d="M8000', b'<path fill="#000000"/>\n<path d="M8000', "PATH_DATA"),
    ])
    def test_anything_the_approval_did_not_cover_is_refused_by_name(self, old, new, reason):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        with pytest.raises(B.MarkRefused) as refused:
            B.read_master(FX.variant(old, new))
        assert refused.value.reason == reason, str(refused.value)

    def test_the_raw_byte_scan_is_what_refuses_not_the_parser(self):
        """NEGATIVE CONTROL of the raw-byte scan: the XML parser READS a comment, a processing instruction and a DTD
        with an internal ENTITY without complaint — so without the scan each would be read as a master."""
        import xml.etree.ElementTree as ET

        from apps.ire.tests import brand_mark_fixtures as FX
        for old, new in ((b"</g>", b"</g>\n<!-- a note -->"),
                         (b"<metadata>", b'<?xml-stylesheet href="gold.css"?>\n<metadata>'),
                         (FX_DOCTYPE, b'<!DOCTYPE svg [<!ENTITY m "x">]>')):
            ET.fromstring(FX.variant(old, new))           # the parser takes it

    def test_the_covered_declaration_and_doctype_are_read(self):
        """potrace's own declaration and DOCTYPE, however their whitespace falls, are covered — and so is a file
        without either."""
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        one_line = FX.variant(FX_DOCTYPE, b" ".join(FX_DOCTYPE.split()))
        bare = FX.variant(b'<?xml version="1.0" standalone="no"?>\n' + FX_DOCTYPE + b"\n", b"")
        for data in (FX.POTRACE_STYLE, one_line, bare):
            assert B.read_master(data).bounds == FX.POTRACE_INK

    def test_a_file_that_is_no_svg_or_draws_nothing_is_refused_by_name(self):
        from apps.ire import brand_mark as B
        for data, reason in ((b"<svg", "NOT_SVG"),
                             (b'<html xmlns="http://www.w3.org/2000/svg"/>', "NOT_SVG"),
                             (b'<svg xmlns="http://www.w3.org/2000/svg"><metadata>x</metadata></svg>', "NO_INK")):
            with pytest.raises(B.MarkRefused) as refused:
                B.read_master(data)
            assert refused.value.reason == reason


_TOOL: dict = {}


def _placement_tool():
    """The tool, loaded ONCE by FILE PATH under a private name (the two `tools` directories: see
    apps/ire/tests/test_wiv_leading_comparison.py's note); its module body imports nothing from `tools`. Once, so the
    refusal a test catches is the class the tool raised."""
    if "module" not in _TOOL:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bh69_brand_mark_place", os.path.join(settings.BASE_DIR, "tools", "brand_mark_place.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _TOOL["module"] = module
    return _TOOL["module"]


class TestThePlacementToolIsTheOneAct:
    """``tools/brand_mark_place.py`` — run here on SYNTHETIC fixtures only; never on the owner's trace. A rehearsal
    writes into a pytest tmp_path, outside the git root; ``--place`` writes into a TEMP live root (``live_root``) and
    never the tree's docs/brand/mark; his words are checked against the fixtures' TEST register (``register_root``)."""

    def _args(self, tmp_path, svg, **kw):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        tmp_path.mkdir(parents=True, exist_ok=True)
        src = tmp_path / "approved.svg"
        src.write_bytes(svg)
        png = FX.source_png(tmp_path / "source.png", kw.pop("png_of", svg))
        args = dict(svg_path=str(src), words=FX.REGISTER_WORDS, register=FX.REGISTER_LINE, date="2026-09-25",
                    source_png=png, tracer="a synthetic fixture", tracer_settings="",
                    out_dir=str(tmp_path.joinpath("root", *B.MARK_DIR)),
                    register_root=FX.write_register(tmp_path / "register"), live_root=str(tmp_path / "live"))
        args.update(kw)
        return args

    def _place(self, tmp_path, svg, **kw):
        tool = _placement_tool()
        args = self._args(tmp_path, svg, **kw)
        return tool, tool.place(args.pop("svg_path"), **args)

    def test_it_places_the_approved_paths_byte_for_byte_cropped_to_their_ink(self, tmp_path, lookup_on):
        import re

        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        pytest.importorskip("fitz")
        _tool, record = self._place(tmp_path, FX.REG_STYLE)
        placed = tmp_path.joinpath("root", *B.MARK_DIR, B.MASTER_FILE).read_bytes()
        assert re.findall(rb"<path[^>]*>", placed) == re.findall(rb"<path[^>]*>", FX.REG_STYLE)
        assert re.findall(rb"<g[^>]*>", placed) == re.findall(rb"<g[^>]*>", FX.REG_STYLE)
        assert record["master_sha256"] == FX.sha256(placed) != record["approved_file"]["sha256"]
        assert record["approved_file"]["sha256"] == FX.sha256(FX.REG_STYLE)
        assert [float(v) for v in record["crop"]["viewBox"].split()] == pytest.approx([10.0, 2.0, 85.0, 28.0])
        bar = record["match"]["emitter_vs_mupdf"]
        assert (bar["passed"], bar["px_disagreeing_over_half"]) == (True, 0)
        assert record["match"]["master_vs_source_png"]["bar"] is None
        # his words as handed over on ONE line, found in the register's paragraph that wraps them over two quoted lines
        assert (record["owner_words"], record["register"], record["written_as"]) == (
            FX.REGISTER_WORDS, FX.REGISTER_LINE, "REHEARSAL")
        assert B.approval_problems(record) == []
        house = B.house_mark(root=tmp_path / "root")
        assert (house["state"], house["master"].sha256) == (B.APPROVED, record["master_sha256"])
        assert house["master"].bounds == B.read_master(FX.REG_STYLE).bounds
        assert not (tmp_path / "live").exists()                   # a rehearsal never touches the live folder

    def test_a_drawing_that_differs_from_its_source_png_is_recorded_and_still_placed(self, tmp_path):
        """The approved drawing, not the PNG, is the mark: the ® redrawn at his word disagrees with the PNG's by
        design, and the tool records by how much without making it a bar."""
        from apps.ire.tests import brand_mark_fixtures as FX
        pytest.importorskip("fitz")
        _tool, record = self._place(tmp_path, FX.REG_STYLE, png_of=FX.POTRACE_STYLE)
        assert record["match"]["emitter_vs_mupdf"]["passed"] is True
        assert record["match"]["master_vs_source_png"]["px_disagreeing_over_half"] > 0

    def test_a_source_png_of_another_canvas_is_said_never_cropped_to_a_number(self, tmp_path):
        """[Review of 2026-09-25.] The PNG comparison is recorded, never a bar: a PNG whose canvas is not the SVG's
        is SAID to be another size — no number is made by cropping the two to a common size — and the bar, the
        emitter against MuPDF at one size by construction, still holds."""
        from PIL import Image as PILImage

        from apps.ire.tests import brand_mark_fixtures as FX
        pytest.importorskip("fitz")
        other = tmp_path / "other.png"
        tmp_path.mkdir(parents=True, exist_ok=True)
        PILImage.new("RGBA", (400, 100), (0, 0, 0, 0)).save(other)
        _tool, record = self._place(tmp_path, FX.POTRACE_STYLE, source_png=str(other))
        source = record["match"]["master_vs_source_png"]
        assert (source["compared"], source["reason"], source["bar"]) == (False, "RASTER_SIZE_MISMATCH", None)
        assert "400x160 px against 400x100 px" in source["detail"]
        assert record["match"]["emitter_vs_mupdf"]["passed"] is True

    def test_rasters_of_different_sizes_are_refused_never_cropped(self):
        import numpy as np
        tool = _placement_tool()
        with pytest.raises(tool.PlacementRefused) as refused:
            tool.compare(np.zeros((40, 100)), np.zeros((41, 100)), "a test")
        assert refused.value.reason == "RASTER_SIZE_MISMATCH"
        same = tool.compare(np.zeros((40, 100)), np.ones((40, 100)), "a test")
        assert (same["raster_px"], same["px_disagreeing_over_half"]) == ([100, 40], 4000)

    @pytest.mark.parametrize("change, reason", [
        ({"words": "  "}, "NO_OWNER_WORDS"),
        ({"register": "the register"}, "NO_REGISTER_LINE"),
        ({"register": "MISSING.md:1"}, "REGISTER_NOT_FOUND"),
        ({"register": "TEST_FIXTURE.md:2"}, "REGISTER_LINE_NOT_FOUND"),            # a blank line
        ({"register": "TEST_FIXTURE.md:5"}, "REGISTER_LINE_NOT_FOUND"),            # a quoted paragraph break
        ({"register": "TEST_FIXTURE.md:99"}, "REGISTER_LINE_NOT_FOUND"),
        ({"words": "A second paragraph the words above never reach."}, "WORDS_NOT_IN_REGISTER"),
        ({"words": "these are not the owner's words and approve everything"}, "WORDS_NOT_IN_REGISTER"),
        ({"date": "25/09/2026"}, "BAD_DATE"),
        ({"date": "2026-02-30"}, "BAD_DATE"),
        ({"tracer": ""}, "NO_TRACER"),
        ({"svg_path": "missing"}, "SVG_NOT_FOUND"),
        ({"source_png": "missing"}, "SOURCE_PNG_NOT_FOUND"),
        ({"svg": "stroked"}, "GRAMMAR"),
        ({"out_dir": "media"}, "MEDIA_REFUSED"),
        ({"out_dir": None}, "NO_OUT"),
        ({"out_dir": "repository"}, "OUT_INSIDE_REPOSITORY"),
        ({"place": True}, "OUT_WITH_PLACE"),
        ({"replace": "0" * 64}, "REPLACE_WITHOUT_PLACE"),
    ])
    def test_it_refuses_by_name_and_writes_nothing(self, tmp_path, change, reason):
        from apps.ire.tests import brand_mark_fixtures as FX
        tool = _placement_tool()
        svg = FX.variant(b'stroke="none"', b'stroke="#000000"') if change.pop("svg", None) else FX.POTRACE_STYLE
        repository = os.path.join(tool.git_root(), "bh69-rehearsal-that-must-not-be-written")
        where = {"media": str(tmp_path / "media" / "brand"), "repository": repository}
        if change.get("out_dir") in where:
            change["out_dir"] = where[change["out_dir"]]
        for key in ("svg_path", "source_png"):
            if change.get(key) == "missing":
                change[key] = str(tmp_path / f"missing-{key}")
        args = self._args(tmp_path, svg, png_of=FX.POTRACE_STYLE)
        args.update(change)
        with pytest.raises(tool.PlacementRefused) as refused:
            tool.place(args.pop("svg_path"), **args)
        assert refused.value.reason == reason, str(refused.value)
        for written in (tmp_path / "root", tmp_path / "media", tmp_path / "live", repository):
            assert not os.path.exists(written), written

    def test_place_writes_the_live_folder_once_and_replaces_only_the_master_it_names(self, tmp_path, lookup_on):
        """[Review of 2026-09-25.] ``--place`` writes the live folder — a TEMP live root here — and is then guarded:
        a second placement is refused while a master is on file (ALREADY_PLACED), a ``--replace`` naming another
        sha256 is refused (REPLACE_MISMATCH), and only ``--replace <the sha256 on file>`` replaces it. A refusal leaves
        both files byte for byte as they were."""
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        pytest.importorskip("fitz")
        tool = _placement_tool()
        live_root = tmp_path / "live_root"
        live = live_root.joinpath(*B.MARK_DIR)
        first = self._args(tmp_path / "a", FX.POTRACE_STYLE, out_dir=None, place=True, live_root=str(live_root))
        record = tool.place(first.pop("svg_path"), **first)
        assert record["written_as"] == "PLACED"
        on_file = {name: (live / name).read_bytes() for name in (B.MASTER_FILE, B.APPROVAL_FILE)}
        house = B.house_mark(root=live_root)
        assert house["master"].sha256 == record["master_sha256"] == FX.sha256(on_file[B.MASTER_FILE])
        for replace, reason in ((None, "ALREADY_PLACED"), ("f" * 64, "REPLACE_MISMATCH")):
            again = self._args(tmp_path / "b", FX.REG_STYLE, out_dir=None, place=True, live_root=str(live_root),
                               replace=replace)
            with pytest.raises(tool.PlacementRefused) as refused:
                tool.place(again.pop("svg_path"), **again)
            assert refused.value.reason == reason
            assert {name: (live / name).read_bytes() for name in on_file} == on_file
        swap = self._args(tmp_path / "c", FX.REG_STYLE, out_dir=None, place=True, live_root=str(live_root),
                          replace=record["master_sha256"])
        replaced = tool.place(swap.pop("svg_path"), **swap)
        assert replaced["master_sha256"] != record["master_sha256"]
        house = B.house_mark(root=live_root)
        assert (house["state"], house["master"].sha256) == (B.APPROVED, replaced["master_sha256"])

    def test_a_record_on_file_without_its_master_still_guards_the_live_folder(self, tmp_path):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        tool = _placement_tool()
        live_root = tmp_path / "live_root"
        FX.write_approval(live_root, FX.POTRACE_STYLE)
        live_root.joinpath(*B.MARK_DIR, B.MASTER_FILE).unlink()
        args = self._args(tmp_path / "a", FX.REG_STYLE, out_dir=None, place=True, live_root=str(live_root))
        with pytest.raises(tool.PlacementRefused) as refused:
            tool.place(args.pop("svg_path"), **args)
        assert refused.value.reason == "ALREADY_PLACED" and FX.sha256(FX.POTRACE_STYLE) in refused.value.detail
        assert not live_root.joinpath(*B.MARK_DIR, B.MASTER_FILE).exists()

    def test_the_crop_must_leave_the_viewbox_on_the_ink(self, tmp_path, monkeypatch):
        """NEGATIVE CONTROL of step 3: a crop that left the padded viewBox in place is refused at CROP, by name."""
        from apps.ire.tests import brand_mark_fixtures as FX
        tool = _placement_tool()
        monkeypatch.setattr(tool, "crop_to_ink", lambda data, bounds: data)
        with pytest.raises(tool.PlacementRefused) as refused:
            self._place(tmp_path, FX.POTRACE_STYLE)
        assert refused.value.reason == "CROP" and "is not the ink" in refused.value.detail
        assert not (tmp_path / "root").exists()

    def test_the_root_start_tag_is_found_by_parsing(self):
        """The crop rewrites the ROOT's start tag, found by the parser's own byte index — never the first '<svg' the
        raw bytes happen to hold (here inside a processing instruction), and a '>' inside a quoted value does not
        end it."""
        tool = _placement_tool()
        tag = b'<svg xmlns="http://www.w3.org/2000/svg" version="a>b" viewBox="0 0 10 10">'
        data = b'<?xml version="1.0"?>\n<?note <svg viewBox="9 9 9 9"> ?>\n' + tag + b'<path d="M0 0"/></svg>'
        start, end = tool.root_tag_span(data)
        assert data[start:end] == tag

    def test_the_command_line_takes_out_or_place_and_never_neither(self, tmp_path, capsys):
        tool = _placement_tool()
        common = ["--svg", "x.svg", "--words", "w", "--register", "R.md:1", "--date", "2026-09-25",
                  "--source-png", "x.png", "--tracer", "t"]
        for extra in ([], ["--out", str(tmp_path), "--place"]):
            with pytest.raises(SystemExit) as refused:
                tool.main(common + extra)
            assert refused.value.code == 2
        inside = os.path.join(tool.git_root(), "bh69-rehearsal-that-must-not-be-written")
        assert tool.main(common + ["--out", inside]) == 1
        assert "BRAND_MARK_PLACEMENT_REFUSED OUT_INSIDE_REPOSITORY" in capsys.readouterr().out
        assert not os.path.exists(inside)

    def test_the_match_bar_catches_an_emitter_that_fills_by_the_wrong_rule(self, tmp_path, monkeypatch):
        """NEGATIVE CONTROL, kept: with the emitter's fill rule taken away (reportlab's even-odd default), the
        same-direction fixture's inner square is a hole in the emitter's drawing and filled in MuPDF's — the tool
        refuses at MATCH and writes nothing."""
        from apps.ire.emitters import pdf_ai
        from apps.ire.tests import brand_mark_fixtures as FX
        pytest.importorskip("fitz")
        monkeypatch.setattr(pdf_ai, "_fill_mode", lambda node: None)
        tool = _placement_tool()
        with pytest.raises(tool.PlacementRefused) as refused:
            self._place(tmp_path, FX.SAME_DIRECTION)
        assert refused.value.reason == "MATCH"
        assert not (tmp_path / "root").exists()


# =====================================================================================================================
# [Review of 2026-09-25, MAJOR 2] THE PRODUCTION CALL SITES THROW THE SWITCH. Each test drives the REAL production
# function — never a composer called by hand — with the approval lookup ON and a SYNTHETIC approval record and master
# under a TEMP mark root (settings.BRAND_MARK_ROOT; never the tree's docs/brand/mark), with stand-ins only for the
# task, its output and the readers that reach the database, the concept image or the provider; a spy on the composer
# (or on the first step after it) records what the call site handed over and STOPS the run there, so nothing after
# it is written. Each has its control: the SAME approval on file with the lookup OFF (the suite's own setting) hands
# over exactly what was handed over before the switch existed.
# =====================================================================================================================

class _Reached(Exception):
    """A spy's stop: the call site under test was reached, and nothing after it runs."""


def _switch_on(tmp_path, monkeypatch, *, lookup=True, **overrides):
    """A SYNTHETIC approval and master on file under a TEMP mark root, and the lookup set as asked. Returns the
    master's sha256."""
    from apps.ire.tests import brand_mark_fixtures as FX
    root = tmp_path / "mark_root"
    FX.write_approval(root, FX.POTRACE_STYLE, **overrides)
    monkeypatch.setattr(settings, "BRAND_MARK_APPROVAL_LOOKUP", lookup)
    monkeypatch.setattr(settings, "BRAND_MARK_ROOT", str(root), raising=False)
    return FX.sha256(FX.POTRACE_STYLE)


def _png_before():
    """The raster every call site picked before the switch: BRAND_LOGO_PATH, only if it exists."""
    path = settings.BRAND_LOGO_PATH
    return path if (path and os.path.exists(path)) else None


def _stand_ins(spec):
    """A task and its output as the production functions read them — no row, no database."""
    from types import SimpleNamespace

    class _Outputs:
        def __init__(self, output):
            self._output = output

        def exclude(self, **_kw):
            return self

        def order_by(self, *_a):
            return self

        def first(self):
            return self._output

    product = SimpleNamespace(pk=None, name="Focus Pressed Powder", product_type=None, net_weight="", name_ar="")
    output = SimpleNamespace(pk=69, spec_sheet=spec, approved_image=None)
    # [his goal of 2026-10-12, (6): "a finish plate ... is made only when my brief or the concept shows it"] the brief
    # asks for the wordmark's foil, so the concept's finish line plates it
    task = SimpleNamespace(pk=990069, id=990069, brand_id=None, product=product,
                           task_text="Finish: the BBROSE wordmark in rose-gold foil.",
                           design_target="product_container", references=SimpleNamespace(all=lambda: []),
                           packaging_outputs=_Outputs(output))
    output.task = task
    return task, output


#: the concept the container runs are handed: its finish sentence asks for foil on the wordmark
_CONCEPT = {"verified": True, "variation_id": "A_PETAL_WINDOW", "title": "Contour Petal — Controlled Window",
            "motif_signature": "Seven closed Bézier petal-droplets in a loose radial cluster inside the cartouche window",
            "finish_signature": "BBROSE wordmark in rose-gold foil",
            "typography_signature": "Tall classical serif wide-tracked small caps",
            "color_field_signature": "Warm Cream #FAF3EC ground"}

#: a HUMAN-confirmed dropper, as the extensions record carries it
_DROPPER_FIELDS = {"total_height": 104.0, "body_height": 70.5, "body_diameter": 31.5, "collar_height": 9.5,
                   "bulb_height": 21.5, "collar_diameter": 21.5, "neck_diameter": 9.0, "visible_neck_height": 2.5,
                   "bulb_width": 11.0, "base_thickness": 3.5, "shoulder_radius": 3.0}


def _dropper_spec():
    from apps.pipeline.services import selected_concept_contract as scc
    return {"product_name": "Focus Pressed Powder", "sku": "BBR-SK-069",
            # §BH70(1), 2026-09-27: a confirmed dropper's record names its form, as every real one does (task 52's
            # says "bottle") — the design loop now draws a dropper only for the form its record names and refuses a
            # record that names none, where it used to assume a bottle (item 10 of the list he was sent)
            "container_profile/1.0": {"archetype": "bottle"},
            scc.EXTENSIONS_SCHEMA: {"confirmation_state": scc.HUMAN_CONFIRMED,
                                    "fields": {k: {"value": v} for k, v in _DROPPER_FIELDS.items()}},
            "container_decoration_zones/1.0": {"zones": [
                {"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT",
                 "x": 5.5, "y": 10.0, "width": 22.0, "height": 40.0}]}}


class TestTheProductionCallSitesThrowTheSwitch:

    def _reconstruct(self, monkeypatch, path):
        """``reconstruct_container`` — the call at targets/container/__init__.py that picks the house mark — driven
        to ``container_finishes.apply``: the spy applies the REAL finishes to the REAL composed document, keeps
        both, and stops the run before anything is emitted or saved."""
        from types import SimpleNamespace

        from apps.ire import container_finishes
        from apps.pipeline.services import container_visual_graph as cvg
        from apps.pipeline.targets import container as C
        seen: dict = {}
        real_apply = container_finishes.apply

        def spy(doc, record, **kw):
            seen.update(doc=doc, kwargs=kw, result=real_apply(doc, record, **kw))
            raise _Reached()
        monkeypatch.setattr(container_finishes, "apply", spy)
        monkeypatch.setattr(C, "_brand_palette", lambda task: [])
        monkeypatch.setattr(cvg, "resolve_selected_variation_identity", lambda task, output: {
            "identity": {"variation_id": _CONCEPT["variation_id"], "verified": True}, "structured": dict(_CONCEPT)})
        monkeypatch.setattr(cvg, "build_visual_graph", lambda *a, **k: {"fields": {}})
        if path == "dropper":
            spec = _dropper_spec()
            confirmed = {"archetype": "bottle", "variant": "cylindrical", "height_mm": 104, "width_mm": 31.5}
        else:
            spec = {"product_name": "Focus Pressed Powder", "sku": "BBR-CO-2060",
                    "container_decoration_zones/1.0": {"zones": [
                        {"zone_id": "z-front", "parent_surface": "BODY_FRONT", "surface_family": "body"}]}}
            confirmed = {"archetype": "bottle", "variant": "cylindrical", "height_mm": 110, "width_mm": 40}
        task, output = _stand_ins(spec)
        with pytest.raises(_Reached):
            C.reconstruct_container(SimpleNamespace(task=task), output, confirmed)
        return spec, seen

    @pytest.mark.parametrize("path", ["generic", "dropper"])
    def test_the_container_target_draws_the_vector_mark_and_its_foil_is_applied(self, tmp_path, monkeypatch, path):
        from apps.ire import brand_mark as B
        from apps.ire import container_finishes as F
        sha = _switch_on(tmp_path, monkeypatch)
        spec, seen = self._reconstruct(monkeypatch, path)
        assert (spec[B.SCHEMA]["state"], spec[B.SCHEMA]["master"]["sha256"]) == (B.APPROVED, sha)
        marks = _logo_nodes(seen["doc"])
        assert marks and all(B.is_mark(n) and n.asset_id == B.ASSET_PREFIX + sha for n in marks)
        rows = [r for r in seen["result"]["applied"] if r["target"] == "lockup"]
        assert [(r["finish"], r["state"]) for r in rows] == [("foil", F.APPLIED)] and rows[0]["nodes"]
        assert "refused_approval" not in seen["kwargs"]

    @pytest.mark.parametrize("path", ["generic", "dropper"])
    def test_with_the_lookup_off_the_container_target_is_what_it_was(self, tmp_path, monkeypatch, path):
        """CONTROL: the same valid approval on file, the lookup off — no record on the spec, the raster drawn, the
        lockup's foil refused in the words it always had, and ``apply`` called exactly as before."""
        from apps.ire import brand_mark as B
        from apps.ire import container_finishes as F
        _switch_on(tmp_path, monkeypatch, lookup=False)
        spec, seen = self._reconstruct(monkeypatch, path)
        assert B.SCHEMA not in spec
        marks = _logo_nodes(seen["doc"])
        assert marks and all(n.type == "image" for n in marks) and marks[0].src == _png_before()
        rows = [r for r in seen["result"]["applied"] if r["target"] == "lockup"]
        assert [r["state"] for r in rows] == [F.REFUSED_NO_VECTOR_MASTER]
        assert "until a vector master exists" in rows[0]["how"] and "approval_refused" not in rows[0]
        assert seen["kwargs"] == {"brand_metallic_hex": seen["kwargs"]["brand_metallic_hex"]}

    def test_a_refused_approval_reaches_the_lockups_row_with_its_code(self, tmp_path, monkeypatch):
        from apps.ire import brand_mark as B
        from apps.ire import container_finishes as F
        _switch_on(tmp_path, monkeypatch, owner_words=" ")
        spec, seen = self._reconstruct(monkeypatch, "generic")
        record = spec[B.SCHEMA]
        assert (record["state"], record["codes"], record["master"]) == (B.REFUSED, [B.CODE_APPROVAL_INCOMPLETE], None)
        assert all(n.type == "image" for n in _logo_nodes(seen["doc"]))
        [row] = [r for r in seen["result"]["applied"] if r["target"] == "lockup"]
        assert row["state"] == F.REFUSED_NO_VECTOR_MASTER
        assert row["approval_refused"]["codes"] == [B.CODE_APPROVAL_INCOMPLETE]
        assert "approval on file is refused (BRAND_MARK_APPROVAL_INCOMPLETE:" in row["how"]

    def _artwork(self, monkeypatch):
        from types import SimpleNamespace

        from apps.ire import compose_artwork as ca
        from apps.pipeline.targets.artwork import MarketingMaterialTarget
        seen: dict = {}
        real = ca.artwork_document

        def spy(fmt, copy, **kw):
            seen.update(kwargs=kw, doc=real(fmt, copy, **kw)[0])
            raise _Reached()
        monkeypatch.setattr(ca, "artwork_document", spy)
        target = MarketingMaterialTarget()
        monkeypatch.setattr(target, "copy_for", lambda task: ca.ArtworkCopy(headline="Focus Pressed Powder",
                                                                            headline_source="a test stand-in"))
        task, _output = _stand_ins({})
        with pytest.raises(_Reached):
            target.begin_output(SimpleNamespace(task=task), SimpleNamespace(image_file=None, id=1))
        return seen

    def test_the_artwork_target_hands_its_composer_the_master(self, tmp_path, monkeypatch):
        from apps.ire import brand_mark as B
        sha = _switch_on(tmp_path, monkeypatch)
        seen = self._artwork(monkeypatch)
        assert seen["kwargs"]["logo_master"].sha256 == sha and seen["kwargs"]["logo"] == _png_before()
        marks = _logo_nodes(seen["doc"])
        assert marks and all(B.is_mark(n) for n in marks)

    def test_with_the_lookup_off_the_artwork_target_is_what_it_was(self, tmp_path, monkeypatch):
        _switch_on(tmp_path, monkeypatch, lookup=False)
        seen = self._artwork(monkeypatch)
        assert "logo_master" not in seen["kwargs"] and seen["kwargs"]["logo"] == _png_before()
        assert all(n.type == "image" for n in _logo_nodes(seen["doc"]))

    def _exploration(self, tmp_path, monkeypatch):
        from apps.dashboard import exploration_render as ER
        from apps.ire import compose_dropper
        seen: dict = {}
        real = compose_dropper.compose_dropper_sheet

        def spy(geometry, **kw):
            seen.update(kwargs=kw, doc=real(geometry, **kw))
            raise _Reached()
        monkeypatch.setattr(compose_dropper, "compose_dropper_sheet", spy)
        monkeypatch.setattr(settings, "EXPLORATION_STORE", str(tmp_path / "exploration_store"), raising=False)
        task, _output = _stand_ins(_dropper_spec())
        with pytest.raises(_Reached):
            ER.render(task, None)
        seen["inputs"] = ER.frozen_inputs(task)
        seen["sha"] = ER.inputs_sha256(seen["inputs"])
        assert not (tmp_path / "exploration_store").exists()          # stopped before the store is written
        return seen

    def test_an_exploration_render_hands_its_composer_the_master(self, tmp_path, monkeypatch):
        from apps.ire import brand_mark as B
        sha = _switch_on(tmp_path, monkeypatch)
        seen = self._exploration(tmp_path, monkeypatch)
        assert seen["kwargs"]["logo_master"].sha256 == sha and seen["kwargs"]["logo_path"] == _png_before()
        marks = _logo_nodes(seen["doc"])
        assert marks and all(B.is_mark(n) for n in marks)
        # the inputs' identity names the master by its sha256 — and differs from the identity without it
        without = dict(seen["inputs"], kwargs={k: v for k, v in seen["inputs"]["kwargs"].items() if k != "logo_master"})
        from apps.dashboard.exploration_render import inputs_sha256
        assert seen["sha"] != inputs_sha256(without)

    def test_with_the_lookup_off_an_exploration_render_is_what_it_was(self, tmp_path, monkeypatch):
        _switch_on(tmp_path, monkeypatch, lookup=False)
        seen = self._exploration(tmp_path, monkeypatch)
        assert "logo_master" not in seen["kwargs"] and seen["kwargs"]["logo_path"] == _png_before()
        assert all(n.type == "image" for n in _logo_nodes(seen["doc"]))

    def _exports(self, tmp_path, monkeypatch):
        """[the clean-up of 2026-10-04: the export has one composer — the carton's own, compose_components_graph; the
        style composer's branch left it] The spy stops the export where its composer is called; it stops with a
        BaseException because the export's composition is best-effort and catches Exception."""
        from types import SimpleNamespace

        from apps.dielines.services.export_service import generate_exports
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire import compose
        seen: dict = {}

        class _Stop(BaseException):
            pass

        def spy(coords, **kw):
            seen.update(kwargs=kw)
            raise _Stop()
        monkeypatch.setattr(compose, "compose_components_graph", spy)
        monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path / "media_root"))
        params = DielineInputJSON(template="straight_tuck_end_carton", unit="mm",
                                  dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120},
                                  print_settings={}, construction={},
                                  metadata={"product_name": "Focus Pressed Powder", "product_type": "pressed powder"})
        with pytest.raises(_Stop):
            generate_exports(SimpleNamespace(id="bh69-switch"), params)
        return seen

    def test_the_dieline_export_hands_its_composer_the_master(self, tmp_path, monkeypatch):
        sha = _switch_on(tmp_path, monkeypatch)
        seen = self._exports(tmp_path, monkeypatch)
        assert seen["kwargs"]["logo_master"].sha256 == sha and seen["kwargs"]["logo_path"] == _png_before()

    def test_with_the_lookup_off_the_dieline_export_is_what_it_was(self, tmp_path, monkeypatch):
        _switch_on(tmp_path, monkeypatch, lookup=False)
        seen = self._exports(tmp_path, monkeypatch)
        assert "logo_master" not in seen["kwargs"] and seen["kwargs"]["logo_path"] == _png_before()

    def _handoff(self, monkeypatch):
        from apps.ire.handoff import container_adapter
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.services.native_handoff import generate_container_native_handoff
        seen: dict = {}

        def spy(doc, spec, out_dir, **kw):
            seen.update(doc=doc, kwargs=kw)
            raise _Reached()
        monkeypatch.setattr(container_adapter, "build_container_handoff_package", spy)
        rec = cc.merge_user_profile(cc.build_inferred_profile("bottle", "slim"),
                                    {"body_width_mm": 35.0, "body_depth_mm": 25.0, "body_height_mm": 95.0})
        zones = cc.propose_zones(rec)
        spec = {"product_name": "Focus Pressed Powder", "sku": "BBR-CO-069", "colors": {},
                "container_profile/1.0": rec, "container_decoration_zones/1.0": {"zones": zones},
                "container_reconstruction": {"status": "RECONSTRUCTED", "blockers": []}}
        _task, output = _stand_ins(spec)
        with pytest.raises(_Reached):
            generate_container_native_handoff(output, None)
        return seen

    def test_the_container_handoff_draws_the_master_and_ships_no_raster(self, tmp_path, monkeypatch):
        from apps.ire import brand_mark as B
        _switch_on(tmp_path, monkeypatch)
        seen = self._handoff(monkeypatch)
        marks = _logo_nodes(seen["doc"])
        assert marks and all(B.is_mark(n) for n in marks)
        assert seen["kwargs"]["logo_asset"] is None

    def test_with_the_lookup_off_the_container_handoff_is_what_it_was(self, tmp_path, monkeypatch):
        _switch_on(tmp_path, monkeypatch, lookup=False)
        seen = self._handoff(monkeypatch)
        assert all(n.type == "image" for n in _logo_nodes(seen["doc"]))
        assert seen["kwargs"]["logo_asset"] == _png_before()
