"""VQR-3 — a text extent must say whether it was MEASURED or GUESSED.

``text_metrics`` was written for exactly this defect class (2A-6E-CORR-10: a
report claimed a 67%-wide name group while quoting a 0.52 em/char placeholder
guess). It fixed the WIDTH and left two silent fallbacks behind:

* ``text_width_mm`` returns ``len(text) * size * 0.52`` when the face is not
  registered — a plausible float with nothing marking it as an estimate;
* ``cap_height_em`` returns the 0.72 constant when it has no path, and
  ``resolve_metric_font`` structurally returns ``(name, None)`` on its own
  fallback branch, so the constant is what container callers actually get.

The repo faces are registered from a path ``_resolve_fonts`` already holds, and
NotoSans' real cap height is 0.714 — so today's guess is wrong by under 1%.
That closeness is luck, not design: a confirmed brand face is supposed to
arrive through ``doc.metadata['confirmed_font']``, and its cap height is
whatever it is.

These tests pin the PROPERTY — a measurement caller can obtain None instead of
a guess, and a measured value is derived from the FILE — never the numbers one
face happens to have. The expectations below are computed from the TTF in the
test, so a hard-coded 0.714 cannot pass them either.
"""
import os

from apps.ire import text_metrics as tm


def _noto_bold_path():
    from apps.dielines.exporters.counter_display_files import _repo_font
    return _repo_font("NotoSans-Bold.ttf")


def _cap_em_from_file(path):
    """The face's cap height read independently of the implementation."""
    from fontTools.ttLib import TTFont
    with TTFont(path, lazy=True) as font:
        return font["OS/2"].sCapHeight / font["head"].unitsPerEm


class TestFallbacksAreReachable:
    """The guessing branches exist and are reachable — pinned so a future
    refactor cannot quietly delete the hazard these tests describe."""

    def test_unregistered_face_yields_the_char_count_guess(self):
        width = tm.text_width_mm("BBROSE", 10.0, "NoSuchFace-Bold")
        assert width == len("BBROSE") * 10.0 * tm._FALLBACK_ADVANCE_EM

    def test_absent_path_yields_the_cap_height_guess(self):
        assert tm.cap_height_em(None) == tm._FALLBACK_CAP_EM
        assert tm.cap_height_em("/no/such/face.ttf") == tm._FALLBACK_CAP_EM


class TestStrictReadersRefuseToGuess:
    """A measurement caller must be able to get NOTHING rather than a guess.

    This mirrors ``container_logo_metrics``: when the asset cannot be read
    there is no record, because a record built from an unstated estimate reads
    downstream as a measurement.
    """

    def test_width_is_none_when_the_face_is_not_registered(self):
        assert tm.text_width_mm_measured("BBROSE", 10.0,
                                         "NoSuchFace-Bold") is None
        assert tm.text_width_mm_measured("BBROSE", 10.0, "") is None
        assert tm.text_width_mm_measured("BBROSE", 10.0, None) is None

    def test_cap_height_is_none_when_the_face_cannot_be_read(self):
        assert tm.cap_height_em_measured(None) is None
        assert tm.cap_height_em_measured("/no/such/face.ttf") is None

    def test_strict_width_matches_the_lenient_one_when_truly_measured(self):
        """Same number when a real face answers — the strict reader adds a
        refusal, it does not change the measurement."""
        from apps.dielines.exporters.counter_display_files import _resolve_fonts
        _, bold = _resolve_fonts()
        strict = tm.text_width_mm_measured("BBROSE", 10.0, bold)
        assert strict is not None
        assert strict == tm.text_width_mm("BBROSE", 10.0, bold)

    def test_a_measured_width_is_not_the_char_count_guess(self):
        """Derived, not asserted: the guess is computed here from the same
        inputs, so a strict reader that secretly fell back would fail."""
        from apps.dielines.exporters.counter_display_files import _resolve_fonts
        _, bold = _resolve_fonts()
        guess = len("BBROSE") * 10.0 * tm._FALLBACK_ADVANCE_EM
        assert tm.text_width_mm_measured("BBROSE", 10.0, bold) != guess


class TestResolvedFontCarriesItsPath:
    """``resolve_metric_font`` returned ``(name, None)`` on its fallback
    branch while ``_resolve_fonts`` held the path it had just registered from.
    Every container caller therefore measured widths from the real face and
    took the cap height from a constant — half measured, half assumed, with
    one tuple describing both."""

    def test_the_repo_face_resolves_with_a_readable_path(self):
        name, path = tm.resolve_metric_font({})
        assert name, "no metric face resolved at all"
        assert path, f"{name} resolved with no path — cap height cannot be read"
        assert os.path.exists(path)

    def test_the_resolved_path_yields_a_cap_height_read_from_the_file(self):
        _, path = tm.resolve_metric_font({})
        assert tm.cap_height_em_measured(path) == _cap_em_from_file(path)

    def test_a_confirmed_face_still_wins_over_the_repo_default(self):
        """The owner's face is the point of the metadata channel; the path fix
        must not shadow it."""
        bold = _noto_bold_path()
        name, path = tm.resolve_metric_font(
            {"confirmed_font": {"name": "ConfirmedProbeFace", "path": bold}})
        assert name == "ConfirmedProbeFace"
        assert path == bold

    def test_an_unloadable_confirmed_face_falls_back_with_a_path(self):
        """A broken confirmation must not cost the fallback its path — that
        would reinstate the guess through the error route."""
        name, path = tm.resolve_metric_font(
            {"confirmed_font": {"name": "Missing", "path": "/no/such.ttf"}})
        assert name and path and os.path.exists(path)


class TestEveryRoleResolves:
    """``geometry_report`` measured a ``bold`` run with the bold face and
    EVERY other run with ``font_name=None`` and a bare ``0.72`` literal — two
    guesses — while reporting a single ``metric_font`` as though one face had
    measured the lot. Each logical role must resolve to the face the emitter
    will actually draw it with."""

    def test_the_emitter_roles_all_resolve_with_readable_paths(self):
        faces = tm.resolve_metric_faces({})
        assert set(faces) == {"regular", "bold", "arabic"}
        for role, (name, path) in faces.items():
            assert name, f"{role} resolved to no face"
            assert path and os.path.exists(path), f"{role} has no readable path"

    def test_roles_match_the_map_the_emitter_builds(self):
        """Derived from the emitter's own resolution, not from a copy of it:
        if ``pdf_ai`` changes which face a role draws with, this fails."""
        from apps.dielines.exporters.counter_display_files import (
            _resolve_arabic_font, _resolve_fonts)
        regular, bold = _resolve_fonts()
        expected = {"regular": regular, "bold": bold,
                    "arabic": _resolve_arabic_font() or regular}
        assert {r: n for r, (n, _) in tm.resolve_metric_faces({}).items()} \
            == expected

    def test_a_regular_run_is_not_measured_with_the_bold_face(self):
        faces = tm.resolve_metric_faces({})
        reg_name, bold_name = faces["regular"][0], faces["bold"][0]
        assert reg_name != bold_name, "test needs two distinct faces"
        reg = tm.text_width_mm_measured("BBROSE SERUM", 10.0, reg_name)
        bold = tm.text_width_mm_measured("BBROSE SERUM", 10.0, bold_name)
        assert reg is not None and bold is not None
        assert reg != bold, ("the two faces advance identically, so this "
                             "test cannot detect the wrong one being used")

    def test_a_confirmed_face_replaces_only_the_bold_role(self):
        bold_path = _noto_bold_path()
        faces = tm.resolve_metric_faces(
            {"confirmed_font": {"name": "ConfirmedRoleProbe",
                                "path": bold_path}})
        assert faces["bold"][0] == "ConfirmedRoleProbe"
        assert faces["regular"][0] != "ConfirmedRoleProbe"


class TestTheGeometryReportMeasuresEachRunWithItsOwnFace:
    """The consumer, not the helper. Reverting ``measure_front_geometry`` to
    ``bold_font if node.font == 'bold' else None`` passed every existing test
    including the golden baseline, so the report's text extents were pinned
    by nothing — these assert the emitted numbers, not the plumbing."""

    TEXT = "BBROSE SERUM"
    SIZE_PT = 8.0
    PANEL = 100.0

    def _report(self):
        """One string at one size in two roles. ``tagline`` and
        ``product-name-*`` are the names the report surfaces boxes under."""
        from apps.ire.geometry_report import measure_front_geometry
        from apps.ire.graph import Color, Document, Group, TextRun
        black = Color.from_hex("#000000")
        doc = Document(page_w=self.PANEL, page_h=self.PANEL, root=Group(
            name="Root", children=[
                TextRun(name="product-name-0", text=self.TEXT, x=10.0, y=40.0,
                        font="bold", size_pt=self.SIZE_PT, color=black),
                TextRun(name="tagline", text=self.TEXT, x=10.0, y=60.0,
                        font="regular", size_pt=self.SIZE_PT, color=black)]))
        return measure_front_geometry(doc, (0.0, 0.0, self.PANEL, self.PANEL))

    def test_a_regular_run_is_not_measured_by_the_char_count_guess(self):
        """The regular run's width must be its own face's advance, never
        ``len(text) * size * 0.52``. The guess is recomputed here from the
        same inputs, so it cannot drift out of step with the code."""
        report = self._report()
        size_mm = self.SIZE_PT / 2.835
        guess = len(self.TEXT) * size_mm * tm._FALLBACK_ADVANCE_EM
        assert report["tagline"]["w"] != round(guess / self.PANEL, 3)

    def test_the_two_roles_do_not_report_identical_extents(self):
        report = self._report()
        assert report["tagline"]["w"] \
            != report["name_lines"]["product-name-0"]["w"], (
                "a regular and a bold run of the same string at the same size "
                "measured identically — one face is being asked about both")

    def test_the_report_states_which_roles_were_measured(self):
        """The Latin roles are read from their files. ARABIC IS NOT, and the
        report says so: NotoNaskhArabic's OS/2 declares ``sCapHeight = 0``
        because the script has no capitals, so there is no cap height to read
        and the layout constant stands in.

        That role was ALREADY using 0.72 before this change — silently. The
        value did not have to move for the honesty to improve; what changed is
        that a consumer can now tell this one apart from the two beside it.
        """
        prov = self._report()["text_metrics_provenance"]
        assert set(prov["faces_by_role"]) == {"regular", "bold", "arabic"}
        for role in ("regular", "bold"):
            entry = prov["faces_by_role"][role]
            assert entry["font"] and entry["cap_height_measured"] is True, role
            assert entry["cap_height_em"] != tm._FALLBACK_CAP_EM, role
        arabic = prov["faces_by_role"]["arabic"]
        assert arabic["font"], "the arabic face itself did not resolve"
        assert arabic["cap_height_measured"] is False
        assert arabic["cap_height_em"] == tm._FALLBACK_CAP_EM
        assert prov["roles_estimated"] == ["arabic"]
        assert prov["all_roles_measured"] is False

    def test_the_unmeasurable_role_is_named_by_the_face_not_by_a_hardcode(self):
        """Derived from the file: if a future Arabic face DID declare a cap
        height, this test would demand the report stop calling it estimated."""
        faces = tm.resolve_metric_faces({})
        _, arabic_path = faces["arabic"]
        declared = _cap_em_from_file(arabic_path)
        prov = self._report()["text_metrics_provenance"]
        estimated = "arabic" in prov["roles_estimated"]
        assert estimated == (declared == 0.0)


# ---- §BH32(e)/(h) W3: on a NON-exempt surface the measurers read the layer's map.

def test_resolve_metric_faces_comes_from_the_selection_layer_for_a_non_exempt_surface():
    from apps.ire.text_metrics import resolve_metric_faces
    from apps.ire import font_roles as FR
    md = {FR.SURFACE_KEY: FR.NON_EXEMPT_EXERCISE}
    faces = resolve_metric_faces(md)
    assert faces["regular"][0] == "Poppins-Regular" and faces["regular"][1].endswith("Poppins-Regular.ttf")
    assert faces["bold"][0] == "Poppins-Light"
    assert faces["arabic"][0] == "NotoNaskhArabic-Regular"
    assert faces["body"] == faces["regular"] and faces["display"] == faces["bold"]
    # and the anonymous call — the way the ruled surfaces' measurers ask — is 41604ac
    assert set(resolve_metric_faces({})) == {"regular", "bold", "arabic"}


def test_his_goal_of_2026_10_06_item_8_a_line_is_measured_by_its_real_outlines_in_the_face_it_is_drawn_in():
    """His goal of 2026-10-06, item 8: "Fix the container back-label 1 mm safe-margin overrun: measure with the real font
    outlines so it never crosses. A warning is not a fix." A line's drawn width is its advances widened by any ink its
    glyphs' outlines put past them, read from the registered file; and a container's back label is measured in the faces
    the emitter draws it in — the theme's body and heading, and their Arabic — never the legacy Noto Sans it was measured
    in while the theme drew it (117's ingredients line measured narrower than it printed)."""
    from apps.ire import back_panel as bp
    from apps.ire.font_roles import resolve_roles
    faces = resolve_roles(("body", "heading", "arabic-body", "arabic-heading"))["faces"]
    line = "Aqua, Glycerin, Cocos Nucifera Oil, Cetearyl Alcohol, Rosa"
    em = 5 * bp.MM_PER_PT
    adv = tm.text_width_mm_measured(line, em, faces["body"][0])
    drawn = tm.drawn_width_mm(line, em, faces["body"][0])
    assert drawn is not None and drawn >= adv
    left, right = tm.ink_span_em(line, tm.registered_font_path(faces["body"][0]))
    assert right <= adv / em + 1e-9 or drawn > adv                 # ink past the last advance widens the measure
    noto = tm.drawn_width_mm(line, em, "NotoSans")
    assert noto is not None and abs(drawn - noto) > 0.5             # the two faces measure the line differently
    zone = {"zone_id": "z_back", "width": 55.0, "height": 99.0, "safe_margin_mm": 3.0}
    sections = [{"heading": "Ingredients", "text": line + " Damascena Flower Water, Glycerin, Parfum."}]
    _g, rec = bp.compose_back_panel(sections, zone, 0.0, 0.0, heading_role="heading", copy_role="body",
                                    doc_metadata={"typography_surface":
                                                  "apps/ire/compose_container.py::compose_container_graph"})
    assert rec["measured_in"]["copy"] == faces["body"][0] and rec["measured_in"]["heading"] == faces["heading"][0]
    assert rec["measured_in"]["arabic_heading"] == faces["arabic-heading"][0]
    column = 55.0 - 2 * 3.0
    for entry in rec["lines"]:
        face = rec["measured_in"]["heading" if entry["role"] == "heading" else "copy"]
        size = entry.get("size_pt", rec["size_pt"]) * bp.MM_PER_PT
        assert tm.drawn_width_mm(entry["text"], size, face) <= column + 1e-6, entry
