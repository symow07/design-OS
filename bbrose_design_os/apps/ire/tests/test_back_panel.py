"""§W1 — the full-scale back panel, checked against the document it lands on.

Two things are easy to get wrong here and both are checked from the emitted
artefact rather than from the producer's own return value. The first is that a
panel can be drawn at true dimensions and still be invisible to the axis that
was supposed to start measuring it (§W1(b)) — the readers all treated any
surface group as schematic, so a full-scale panel would have been excluded by
the very machinery that excludes the strip. The second is that "untruncated"
is a claim about copy, and a wrap that loses the space it breaks at looks
exactly like a panel that dropped a character.

The strip is not measured harder anywhere in this file (§W1(c)); it is only
checked to still be there, and to still be distinguishable from the panel.
"""
import pytest

from apps.ire import back_panel as bp
from apps.ire import container_production_method as cpm
from apps.ire import text_metrics
from apps.ire.compose_container import (HERO_SURFACE, SURFACE_GROUP_PREFIX,
                                        TRUE_SCALE_SURFACE_PREFIX)
from apps.ire.compose_dropper import compose_dropper_sheet
from apps.ire.container_composition_metrics import (front_hierarchy_runs,
                                                    measure_composition_metrics)
from apps.ire.container_overlap import measure_text_overlaps
from apps.ire.container_text_floor import (FALLBACK_FLOOR_PT, SOURCE_TABLE,
                                           measure_text_floor)
from apps.ire.container_typography_metrics import container_view_text_runs

_GEOMETRY = {"total_height_mm": 104.0, "body_height_mm": 70.5,
             "body_diameter_mm": 31.5, "collar_height_mm": 9.5,
             "bulb_height_mm": 21.5, "collar_diameter_mm": 21.5,
             "bulb_width_mm": 11.0, "visible_neck_mm": 2.5,
             "neck_diameter_mm": 9.0, "base_thickness_mm": 3.5,
             "shoulder_radius_mm": 3.0, "frost_intensity": 0.7,
             "translucency": 0.35}

#: the zone ``propose_zones`` derives for this dropper — 70% × 60% of a
#: Ø31.5 × 70.5 body. Written out rather than computed so that a change to the
#: coverage constants shows up here as a changed panel, not as a silent one.
_BACK_ZONE = {"zone_id": "z_back", "zone_type": "BACK_PRINT_ZONE",
              "parent_surface": "BODY_BACK", "x": 4.8, "y": 14.1,
              "width": 22.0, "height": 42.3}
_FRONT_ZONE = {"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE",
               "x": 4.8, "y": 14.1, "width": 22.0, "height": 42.3}

#: what the product record supplies today: a name, a net content, and five
#: sections still awaiting owner content.
_LIVE = [{"heading": "PRODUCT", "text": "Rose Damascena Serum"},
         {"heading": "DESCRIPTION", "text": "CONTENT_VERIFICATION_REQUIRED"},
         {"heading": "INGREDIENTS", "text": "CONTENT_VERIFICATION_REQUIRED"},
         {"heading": "DIRECTIONS", "text": "CONTENT_VERIFICATION_REQUIRED"},
         {"heading": "WARNINGS", "text": "CONTENT_VERIFICATION_REQUIRED"},
         {"heading": "MANUFACTURER", "text": "CONTENT_VERIFICATION_REQUIRED"},
         {"heading": "NET CONTENT", "text": "30 ml / 1.01 fl. oz."}]

_INCI = ("AQUA (WATER), ROSA DAMASCENA FLOWER WATER, GLYCERIN, PROPANEDIOL, "
         "NIACINAMIDE, SODIUM HYALURONATE, ROSA DAMASCENA FLOWER OIL, "
         "TOCOPHEROL, PANTHENOL, ALLANTOIN, XANTHAN GUM, CITRIC ACID, "
         "SODIUM BENZOATE, POTASSIUM SORBATE, PHENOXYETHANOL, "
         "ETHYLHEXYLGLYCERIN, CITRONELLOL, GERANIOL, LINALOOL, FARNESOL")
_REAL = [{"heading": "PRODUCT", "text": "Rose Damascena Serum"},
         {"heading": "INGREDIENTS", "text": _INCI},
         {"heading": "DIRECTIONS", "text": "Apply 2-3 drops to cleansed skin "
                                           "morning and evening."},
         {"heading": "NET CONTENT", "text": "30 ml / 1.01 fl. oz."}]

#: §BH67(c)2, OWNER RULED 2026-09-24: "Derive both from the product record;
#: where the record is silent, print nothing." The dropper composer no longer
#: holds its front's descriptor or net content — the production call hands in
#: the product record's. A fixture measuring a front drawn WITH the two lines
#: hands in these, the words every such measurement was taken with, so each
#: measured number stands unchanged. The fixtures' input, not any product's copy.
_FRONT_RECORD = {"descriptor": "N I G H T   R E P A I R   O I L",
                 "net_content": "30 ml / 1.01 fl. oz."}
#: §BH68(d), OWNER RULED 2026-09-24: "Derive it from the product record; print nothing where the record is silent." The
#: lockup's module default "Rose" / "Damascena" is gone, so a fixture measuring the front drawn WITH its name hands the
#: name in, as the sheet hands in the record's: these two lines, the ones every such measurement was taken with.
_FRONT_NAME_LINES = ("Rose", "Damascena")


#: every character limit the strip applies, body and heading, in both of the
#: forms the strip states them in.
COPY_LIMITS = {70.0, 60.0, 40.0, 36.0}


#: §Z3 — the production methods for THIS document, hand-written because
#: `propose_zones` gives a bottle SCREEN_PRINT on both faces and the case worth
#: exercising is the one where the two surfaces DISAGREE: a 4.0 pt label on the
#: front, a 6.0 pt hot stamp on the back. It is the record the sprint-10 census
#: was taken against, so the 15 back-panel runs it found are the 15 here.
_METHODS = {"methods": [
    {"method_id": "m_front", "method_type": "ADHESIVE_LABEL",
     "minimum_text_size_pt": 4.0, "target_surfaces": [HERO_SURFACE]},
    {"method_id": "m_back", "method_type": "HOT_STAMP",
     "minimum_text_size_pt": 6.0, "target_surfaces": [bp.SURFACE]}]}
#: [His correction of 2026-10-07: "Floor: 3 pt."] the same record CONFIRMED by a person: a print method someone confirmed
#: holds a label at its own minimum (``back_panel.label_floor_pt``); the record above, which nobody confirmed, is an
#: assumption, and under it a label shrinks evenly to his 3 pt
_CONFIRMED_METHODS = {"methods": [dict(m, authority_state=cpm.INFERRED_NONAUTHORITATIVE,
                                         confirmed_by="BBrose (a test fixture's confirmation)")
                                  for m in _METHODS["methods"]]}


def _document(sections=None, zones=None, methods=None):
    """The sheet. ``methods`` absent is §W2(b)'s unrecorded case — the back
    panel takes the disclosed 5.0 pt fallback — and it is the default here on
    purpose, so that every test written before §Z3 still measures what it was
    written to measure."""
    return compose_dropper_sheet(
        _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE] if zones is None else zones,
        reference_path=None, logo_path=None, product_name="Rose Damascena",
        sku="X", back_sections=_LIVE if sections is None else sections,
        revision_status="TEST", methods_record=methods)


def _panel_runs(doc):
    return [node for node, _ in doc.walk()
            if getattr(node, "type", "") == "text"
            and str(getattr(node, "name", "") or "").startswith("back-panel-")]


def _faces():
    faces = text_metrics.resolve_metric_faces({})
    return (faces.get("regular") or (None,))[0], (faces.get("bold") or (None,))[0]


class TestThePanelIsTheZoneAtTrueScale:
    """§W1(a) — a real surface at true dimensions, not a strip glyph."""

    def test_the_panel_is_the_confirmed_zones_own_width_and_height(self):
        record = _document().metadata[bp.SCHEMA]
        assert record["emitted"] is True
        assert record["zone_id"] == "z_back"
        assert record["panel_mm"] == [_BACK_ZONE["width"],
                                      _BACK_ZONE["height"]]

    def test_a_different_zone_is_a_different_panel(self):
        """True scale means the zone decides. A panel that came out the same
        size for a different zone would be a sheet rectangle wearing a
        measurement."""
        wide = dict(_BACK_ZONE, width=30.0, height=55.0)
        record = _document(zones=[_FRONT_ZONE, wide]).metadata[bp.SCHEMA]
        assert record["panel_mm"] == [30.0, 55.0]
        assert record["column_mm"] == 30.0 - 2 * bp.MARGIN_MM

    def test_the_boundary_drawn_is_the_zone_and_not_the_sheet_slot(self):
        doc = _document()
        rects = [n for n, _ in doc.walk()
                 if str(getattr(n, "name", "") or "") == "back-panel-boundary"]
        assert len(rects) == 1
        assert (rects[0].w, rects[0].h) == (_BACK_ZONE["width"],
                                            _BACK_ZONE["height"])

    def test_no_confirmed_zone_means_no_panel_and_a_named_reason(self):
        record = _document(zones=[_FRONT_ZONE]).metadata[bp.SCHEMA]
        assert record["emitted"] is False
        assert record["codes"] == [bp.NO_CONFIRMED_ZONE]
        assert bp.ZONE_TYPE in record["reason"]
        assert _panel_runs(_document(zones=[_FRONT_ZONE])) == []

    def test_the_copy_is_set_at_the_ruled_floor_not_at_a_sheet_scale(self):
        """§W2(b)'s disclosed fallback, because the composer holds no methods
        record. The strip's 1.0–2.1 pt is what §W1 was written about."""
        doc = _document()
        assert doc.metadata[bp.SCHEMA]["size_pt"] == FALLBACK_FLOOR_PT
        assert {r.size_pt for r in _panel_runs(doc)} == {FALLBACK_FLOOR_PT}


class TestTheStripsLimitsDoNotFollowTheCopy:
    """§W1(d) — 70/40 characters are a strip constraint and stay there."""

    def test_every_supplied_character_survives_when_the_panel_holds_it(self):
        record = _document().metadata[bp.SCHEMA]
        assert record["fits"] is True
        assert record["copy_preserved"] is True
        assert record["characters_not_emitted"] == 0
        assert record["characters_emitted"] == record["characters_supplied"]

    def test_a_section_longer_than_the_strips_limit_is_emitted_whole(self):
        """70 characters is where the strip cut the copy. On a panel with room
        for it, a 200-character section comes out entire."""
        long_copy = _INCI[:200]
        assert len(long_copy) > 70
        record = _document(sections=[{"heading": "INGREDIENTS",
                                      "text": long_copy}],
                           zones=[_FRONT_ZONE,
                                  dict(_BACK_ZONE, width=40.0, height=60.0)]
                           ).metadata[bp.SCHEMA]
        assert record["fits"] is True
        assert record["sections"][0]["characters_emitted"] == \
            len("INGREDIENTS") + len(long_copy)

    def test_the_emitted_lines_reconstruct_the_supplied_copy(self):
        """The strongest form of the claim, and the one a character count
        cannot make: a wrap consumes the space it breaks at, so counting
        characters alone would report a dropped space as dropped copy — and
        would equally hide one real dropped character per line."""
        doc = _document()
        drawn = {}
        for run in _panel_runs(doc):
            _, _, index, role, _ = str(run.name).split("-")
            drawn.setdefault((int(index), role), []).append(run.text)
        for index, section in enumerate(_LIVE):
            assert " ".join(drawn.get((index, "heading"), [])) == \
                section["heading"]
            assert " ".join(drawn.get((index, "copy"), [])) == section["text"]

    @pytest.mark.parametrize("limit", sorted(COPY_LIMITS))
    def test_a_section_one_character_past_each_strip_limit_is_whole(self, limit):
        """The behavioural form of the claim, and the one a constant scan
        cannot make: a limit that is computed rather than written down would
        pass the scan below and still cut here."""
        text = _INCI[:int(limit) + 1]
        assert len(" ".join(text.split())) == int(limit) + 1
        record = _document(sections=[{"heading": "INGREDIENTS", "text": text}],
                           zones=[_FRONT_ZONE,
                                  dict(_BACK_ZONE, width=40.0, height=60.0)]
                           ).metadata[bp.SCHEMA]
        assert record["fits"] is True
        assert record["sections"][0]["characters_emitted"] == \
            len("INGREDIENTS") + len(text)

    @pytest.mark.parametrize("limit", sorted(COPY_LIMITS))
    def test_a_heading_past_each_strip_limit_is_whole_too(self, limit):
        """The strip cuts headings at their own limit, and a heading is copy.
        A producer that stopped cutting body text and kept cutting headings
        would satisfy every body-copy test in this file."""
        heading = "INGREDIENTS AND MATERIALS OF THIS COSMETIC PREPARATION"
        heading = (heading * 3)[:int(limit) + 1]
        record = _document(sections=[{"heading": heading, "text": "x"}],
                           zones=[_FRONT_ZONE,
                                  dict(_BACK_ZONE, width=40.0, height=60.0)]
                           ).metadata[bp.SCHEMA]
        assert record["fits"] is True
        assert record["sections"][0]["heading"] == heading
        assert record["sections"][0]["characters_emitted"] == len(heading) + 1

    def test_no_truncation_constant_hides_in_the_producer(self):
        """The limits are named in the module only as the thing it refuses."""
        assert COPY_LIMITS.isdisjoint(_producer_constants())


#: [His correction of 2026-10-07: "Only if it still doesn't fit at 3 pt, stop and tell me".] the dropper's own back
#: (42.3 mm) now holds the real copy shrunk evenly to 3.75 pt; this one, 20 mm tall, does not hold it even at 3 pt — the
#: case this class was written to measure, measured where it still exists
_OVER_BACK_ZONE = dict(_BACK_ZONE, height=20.0)


def _over():
    return _document(sections=_REAL, zones=[_FRONT_ZONE, _OVER_BACK_ZONE])


class TestCopyThatDoesNotFitIsAFindingNotACut:
    """§W1(d) — it comes back to the owner; it is not solved by truncating."""

    def test_the_shortfall_is_measured_and_named_by_section(self):
        record = _over().metadata[bp.SCHEMA]
        assert record["fits"] is False
        assert record["codes"] == [bp.COPY_EXCEEDS_PANEL]
        assert record["overflow_mm"] > 0
        assert record["overflow_mm"] == round(
            record["height_required_mm"] - record["height_available_mm"], 3)
        short = [s for s in record["sections"]
                 if s["lines_emitted"] < s["lines_required"]]
        assert [s["heading"] for s in short] == ["INGREDIENTS", "DIRECTIONS",
                                                 "NET CONTENT"]
        assert record["characters_not_emitted"] > 0

    def test_what_is_drawn_is_a_prefix_of_what_was_supplied(self):
        """A prefix means the panel's edge stopped the copy. Anything else
        means something rewrote it on the way to the panel."""
        doc = _over()
        record = doc.metadata[bp.SCHEMA]
        assert record["copy_preserved"] is True
        drawn = {}
        for run in _panel_runs(doc):
            _, _, index, role, _ = str(run.name).split("-")
            drawn.setdefault((int(index), role), []).append(run.text)
        assert record["characters_not_emitted"] > 0
        for index, supplied in enumerate(_REAL):
            for role, key in (("heading", "heading"), ("copy", "text")):
                emitted = " ".join(drawn.get((index, role), []))
                assert supplied[key].startswith(emitted)

    def test_nothing_is_drawn_past_the_panels_own_edge(self):
        doc = _over()
        record = doc.metadata[bp.SCHEMA]
        bottom = record["origin_mm"][1] + record["panel_mm"][1]
        assert _panel_runs(doc)
        assert max(r.y for r in _panel_runs(doc)) <= bottom

    def test_the_finding_travels_on_the_document_the_target_emits(self):
        doc = _over()
        assert doc.metadata[bp.SCHEMA]["rule"] == bp.RULE
        assert "OWNER_BLOCKER_CLEARANCE.md §W1" in bp.RULE
        assert bp.COPY_EXCEEDS_PANEL in bp.NO_TRUNCATION

    def test_an_overflowing_panel_still_crosses_no_artboard(self):
        """The shortfall is reported, not drawn off the page — an element over
        the trim is a separate §W3(c) finding and must not be manufactured
        here."""
        with_panel = measure_composition_metrics(_over())
        without = measure_composition_metrics(
            _document(sections=_REAL, zones=[_FRONT_ZONE]))
        assert with_panel["elements_outside_artboard"] == \
            without["elements_outside_artboard"]
        assert with_panel["blocking_overlaps"] == without["blocking_overlaps"]


class TestTheAxisMeasuresItLikeAnyOtherSurface:
    """§W1(b) — once it exists, it is measured, and on ITS surface."""

    def test_the_panels_runs_are_container_view_and_carry_their_surface(self):
        runs, strip = container_view_text_runs(_document())
        named = {str(n.name): s for n, s in runs if str(n.name).startswith(
            "back-panel-")}
        assert named and set(named.values()) == {bp.SURFACE}
        assert not any(str(n.name).startswith("back-panel-")
                       for n, _ in strip)

    def test_the_floor_that_governs_it_is_the_back_surfaces_own(self):
        """The point of carrying the surface: a run judged against the FRONT's
        print method is judged against a different physical process. [His correction of 2026-10-07] a confirmed one:
        an unconfirmed method no longer holds a label above his 3 pt (see test_wik_back_panel_floor)."""
        record = measure_text_floor(_document(methods=_CONFIRMED_METHODS), _CONFIRMED_METHODS)
        panel = [r for r in record["runs"]
                 if r["node_name"].startswith("back-panel-")]
        assert panel
        assert {r["floor_pt"] for r in panel} == {6.0}
        assert {r["floor_source"] for r in panel} == {SOURCE_TABLE}

    def test_composing_without_the_record_is_how_the_two_disagreed(self):
        """§Z3 — the defect, kept as the test that shows the fix is load-bearing.

        A sheet composed with NO methods record takes §W2(b)'s 5.0 pt fallback
        while the axis resolves BODY_BACK's own 6.0 pt hot stamp, and every
        panel run is below its floor. That is not a bad number: it is the
        composer and the axis reading different sources. Threading one record
        to both is what §Z3(a) rules, and the pair of assertions below is the
        only place the difference is visible. [His correction of 2026-10-07] the hot stamp confirmed, as only a
        confirmed method now holds a label above his 3 pt."""
        blind = measure_text_floor(_document(), _CONFIRMED_METHODS)
        blind_panel = [r for r in blind["runs"]
                       if r["node_name"].startswith("back-panel-")]
        assert blind_panel and all(r["below"] for r in blind_panel)
        assert {r["size_pt"] for r in blind_panel} == {FALLBACK_FLOOR_PT}

        wired = measure_text_floor(_document(methods=_CONFIRMED_METHODS), _CONFIRMED_METHODS)
        wired_panel = [r for r in wired["runs"]
                       if r["node_name"].startswith("back-panel-")]
        assert wired_panel and not any(r["below"] for r in wired_panel)
        assert {r["size_pt"] for r in wired_panel} == {6.0}

    def test_the_overlap_axis_examines_the_panels_own_runs(self):
        doc = _document()
        with_panel = measure_text_overlaps(doc)
        without = measure_text_overlaps(_document(zones=[_FRONT_ZONE]))
        assert with_panel["runs_examined"] == \
            without["runs_examined"] + doc.metadata[bp.SCHEMA]["lines_emitted"]
        assert with_panel["blocking"] == without["blocking"] == []

    def test_the_panels_keyline_is_artwork_its_own_type_sits_over(self):
        """§W1(b) where the number that moves is not the one a reader reaches
        for first. Every line of the panel sits over the panel's keyline, and
        §W3(b) rules type over a rule non-blocking — so ``blocking`` stays
        empty whatever happens here, and a reader that filed the full-scale
        group as strip furniture would show up ONLY as these pairs going
        missing."""
        doc = _document()
        record = measure_text_overlaps(doc)
        drawn = {str(r.name) for r in _panel_runs(doc)}
        over_keyline = {n for p in record["non_blocking_over_artwork"]
                        if "back-panel-boundary" in p["nodes"]
                        for n in p["nodes"]}
        assert drawn and drawn <= over_keyline
        assert record["blocking"] == []

    def test_the_production_method_record_attributes_it_to_its_surface(self):
        geometry = cpm._decoration_geometry(_document())
        assert geometry["min_text_size_pt_by_surface"][bp.SURFACE] == \
            FALLBACK_FLOOR_PT

    def test_it_is_artwork_and_not_counted_as_schematic(self):
        with_panel = cpm._decoration_geometry(_document())
        without = cpm._decoration_geometry(_document(zones=[_FRONT_ZONE]))
        assert with_panel["text_runs_excluded_as_schematic"] == \
            without["text_runs_excluded_as_schematic"]
        assert bp.SURFACE not in without["min_text_size_pt_by_surface"]

    def test_drawing_it_full_size_does_not_make_it_front_hierarchy(self):
        """The exclusion is on the surface, not on the scale — a container
        whose front carried no type must not report a front hierarchy off the
        back panel's INCI block."""
        names = [str(getattr(r, "name", "") or "")
                 for r in front_hierarchy_runs(_document())]
        assert names
        assert not any(n.startswith("back-panel-") for n in names)


class TestTheStripStaysAndStaysAMap:
    """§W1(a) keeps the strip; §W1(c) forbids measuring it harder."""

    def test_the_schematic_panel_is_still_emitted_beside_the_real_one(self):
        doc = _document()
        groups = {str(getattr(n, "name", "") or "") for n, _ in doc.walk()}
        assert f"{SURFACE_GROUP_PREFIX}{bp.SURFACE}" in groups
        assert f"{TRUE_SCALE_SURFACE_PREFIX}{bp.SURFACE}" in groups

    def test_the_two_prefixes_cannot_half_match_each_other(self):
        assert not TRUE_SCALE_SURFACE_PREFIX.startswith(SURFACE_GROUP_PREFIX)
        assert not SURFACE_GROUP_PREFIX.startswith(TRUE_SCALE_SURFACE_PREFIX)

    def test_the_strips_own_runs_are_still_excluded_from_the_container_view(self):
        _, strip = container_view_text_runs(_document())
        assert [str(n.name) for n, _ in strip
                if str(n.name).startswith("back-section-")]


class TestAFitNobodyMeasuredDrawsNoPanel:
    """A wrap computed from a char-count guess is a fit reported off a guess."""

    def test_an_unregistered_face_yields_no_wrap_at_all(self):
        assert bp.wrap_lines("some copy", 5.0, 20.0, "NoSuchFace") is None
        assert bp.wrap_lines("some copy", 5.0, 20.0, None) is None

    def test_a_word_wider_than_the_column_keeps_its_own_line_unbroken(self):
        regular, _ = _faces()
        lines = bp.wrap_lines("ETHYLHEXYLGLYCERIN", 5.0, 4.0, regular)
        assert lines == ["ETHYLHEXYLGLYCERIN"]

    def test_no_panel_is_drawn_on_a_layout_nobody_measured(self, monkeypatch):
        monkeypatch.setattr(text_metrics, "resolve_metric_faces",
                            lambda *a, **k: {})
        group, record = bp.compose_back_panel(_LIVE, _BACK_ZONE, 0.0, 0.0)
        assert group is None
        assert record["emitted"] is False
        assert record["fit_measured"] is False
        assert record["fits"] is None
        assert bp.FIT_UNMEASURED in record["codes"]

    def test_a_wrap_that_loses_a_word_is_reported_as_copy_not_preserved(self,
                                                                       monkeypatch):
        """``copy_preserved`` is the only claim in the record that a character
        count cannot make, so it has to be able to come back False. Without a
        wrapper that misbehaves nothing ever drives it there, and a flag that
        is True on every input is not a check."""
        regular, bold = _faces()
        monkeypatch.setattr(bp, "wrap_lines",
                            lambda text, *a, **k: str(text).split()[:-1])
        record = bp.layout([{"heading": "INGREDIENTS", "text": _INCI}],
                           40.0, 60.0, size_pt=5.0, regular=regular, bold=bold)
        assert record["copy_preserved"] is False

    def test_an_unmeasured_fit_is_not_reported_as_a_fit(self):
        record = bp.layout(_LIVE, 22.0, 42.3, size_pt=5.0,
                           regular="NoSuchFace", bold="NoSuchFace")
        assert record["fit_measured"] is False
        assert record["fits"] is None
        assert record["codes"] == [bp.FIT_UNMEASURED]


def _producer_constants():
    """Floats included: 70 written as ``70.0`` is the same cut."""
    return {float(value) for name, value in vars(bp).items()
            if not name.startswith("__")
            and isinstance(value, (int, float))
            and not isinstance(value, bool)}


@pytest.mark.parametrize("width,height", [(22.0, 42.3), (30.0, 55.0),
                                          (18.0, 30.0)])
def test_the_required_height_is_computed_from_the_panel_it_is_given(width,
                                                                    height):
    """Three panels, one copy: the layout has to answer differently for each
    or it is not measuring the panel at all."""
    regular, bold = _faces()
    record = bp.layout(_REAL, width, height, size_pt=5.0, regular=regular,
                       bold=bold)
    assert record["column_mm"] == round(width - 2 * bp.MARGIN_MM, 3)
    assert record["height_available_mm"] == round(height - 2 * bp.MARGIN_MM, 3)
    assert record["lines_required"] >= len(_REAL) * 2


class TestTheBackCarriesItsZonesOwnSafeMargin:
    """§BH54(b), the second block, (n), OWNER RULED 2026-09-19: "THE BACK CARRIES A SAFE MARGIN on the same principle as
    the front: derive it from the back zone the way 16.0 was derived from the front, state the derivation, and apply it.
    Do not type 3.0 because it is a round number." The front's 16.0 is its zone's width less twice that zone record's own
    `safe_margin_mm`; the back panel now insets by ITS zone record's own `safe_margin_mm` — read, never typed."""

    SEVEN = [{"heading": "PRODUCT", "text": "Rose Damascena Night Repair Oil"}] + [
        {"heading": h, "text": "CONTENT_VERIFICATION_REQUIRED"}
        for h in ("DESCRIPTION", "INGREDIENTS", "DIRECTIONS", "WARNINGS", "MANUFACTURER", "NET CONTENT")]

    def _zone(self, height, **more):
        return {**_BACK_ZONE, "width": 22.0, "height": height, **more}

    def test_the_margin_is_read_from_the_zones_record_and_never_typed(self):
        for margin in (3.0, 2.25, 0.5):                       # whatever the record says — no number is privileged
            assert bp.zone_margin(self._zone(42.6, safe_margin_mm=margin)) == (margin, bp.MARGIN_FROM_ZONE)
        for unusable in (None, "wide", 0, -3.0, 11.0):        # 11.0 leaves a 22 mm zone no column at all
            assert bp.zone_margin(self._zone(42.6, safe_margin_mm=unusable)) == (bp.MARGIN_MM, bp.MARGIN_LEGACY)
        assert bp.zone_margin(self._zone(42.6)) == (bp.MARGIN_MM, bp.MARGIN_LEGACY)      # no field: nothing to derive from
        assert bp.zone_margin(None) == (bp.MARGIN_MM, bp.MARGIN_LEGACY)

    def test_the_back_is_derived_the_way_the_fronts_safe_area_is(self):
        """The front's safe area is `width − 2 × safe_margin_mm` of ITS zone (compose_dropper.front_copy_fit); the back's
        column is the same arithmetic on the back zone's own record — 22.0 − 2 × 3.0 = 16.0 on both faces of task 52
        before the front widened."""
        regular, bold = _faces()
        zone = self._zone(42.6, safe_margin_mm=3.0)
        _group, record = bp.compose_back_panel(self.SEVEN, zone, 10.0, 20.0)
        assert record["margin_mm"] == 3.0 and record["margin_source"] == bp.MARGIN_FROM_ZONE
        assert record["column_mm"] == round(zone["width"] - 2 * zone["safe_margin_mm"], 3) == 16.0
        assert record["height_available_mm"] == round(zone["height"] - 2 * zone["safe_margin_mm"], 3) == 36.6
        # [his goal of 2026-10-06, item 8] the faces it was measured in, named — an anonymous call measures as the legacy
        assert record.pop("measured_in") == {"copy": regular, "heading": bold, "arabic_copy": None,
                                             "arabic_heading": None}
        assert record == {**bp.layout(self.SEVEN, 22.0, 42.6, size_pt=record["size_pt"], regular=regular, bold=bold,
                                      margin_mm=zone["safe_margin_mm"]),
                          "size_source": record["size_source"], "margin_source": bp.MARGIN_FROM_ZONE, "emitted": True,
                          "zone_id": "z_back", "origin_mm": [10.0, 20.0]}

    def test_no_copy_is_drawn_inside_the_margin(self):
        """What a taller zone alone could never do (the 1.5 mm inset ignored the zone's margin whatever its height):
        every run starts at the zone's edge plus its margin, and no baseline falls in the margin at its foot."""
        zone = self._zone(42.6, safe_margin_mm=3.0)
        group, record = bp.compose_back_panel(self.SEVEN, zone, 10.0, 20.0)
        runs = [n for n in group.children if getattr(n, "type", "") == "text"]
        assert runs and {round(n.x, 6) for n in runs} == {13.0}                           # x + the record's 3.0
        assert max(n.y for n in runs) <= 20.0 + 42.6 - 3.0 + 1e-9
        assert min(n.y for n in runs) >= 20.0 + 3.0
        rules = [n for n in group.children if str(getattr(n, "name", "")).endswith("-rule")]
        assert rules and all(r.segments[0].x == 13.0 and r.segments[1].x == 10.0 + 22.0 - 3.0 for r in rules)

    def test_the_minimum_zone_that_holds_the_seven_at_5_pt_is_42_6_and_below_it_they_shrink_evenly_then_stop(self):
        """His (g): "Measure the minimum back zone that holds all seven at their floors … Nothing regulatory is ever
        dropped to fit." The seven need 36.55 mm of copy height; inside a 3.0 mm margin that is 42.55 → 42.6. [His
        correction of 2026-10-07: "Shrink the whole label evenly until everything fits, keeping its layout, spacing and
        order. Floor: 3 pt. Only if it still doesn't fit at 3 pt, stop and tell me".] The 39.6 that once blocked now holds
        all seven at 4.5 pt, the same fifteen lines; a 28 mm zone does not hold them even at 3 pt, and the panel says so by
        name and blocks, excluding NET CONTENT rather than shrinking below the floor."""
        _g, tall = bp.compose_back_panel(self.SEVEN, self._zone(42.6, safe_margin_mm=3.0), 0.0, 0.0)
        assert tall["height_required_mm"] == 36.55 and tall["fits"] is True and tall["codes"] == []
        assert tall["lines_emitted"] == tall["lines_required"] == 15 and tall["size_pt"] == 5.0
        _g, shrunk = bp.compose_back_panel(self.SEVEN, self._zone(39.6, safe_margin_mm=3.0), 0.0, 0.0)
        assert shrunk["fits"] is True and shrunk["codes"] == [] and shrunk["size_pt"] == 4.5
        assert shrunk["lines_emitted"] == shrunk["lines_required"] == 15                          # its layout kept
        _g, short = bp.compose_back_panel(self.SEVEN, self._zone(28.0, safe_margin_mm=3.0), 0.0, 0.0)
        assert short["fits"] is False and short["codes"] == [bp.COPY_EXCEEDS_PANEL]
        assert short["size_pt"] == bp.LABEL_FLOOR_PT == 3.0 and short["overflow_mm"] > 0
        assert [s["heading"] for s in short["sections"] if s["lines_emitted"] < s["lines_required"]] == ["NET CONTENT"]
        _g, legacy = bp.compose_back_panel(self.SEVEN, self._zone(39.6), 0.0, 0.0)                 # no margin on the record
        assert legacy["fits"] is True and legacy["margin_source"] == bp.MARGIN_LEGACY and legacy["column_mm"] == 19.0


def test_his_final_goal_a_a_containers_back_label_is_trilingual_its_arabic_set_from_the_right():
    """His final goal (2026-10-05, transcribed at 32e9aaf), A: "Go: container back labels are trilingual too (English,
    Spanish, Arabic), translated per design." The back's English, then its Spanish under their own headings, then its
    Arabic — each Arabic line wrapped on its own words in the Arabic face and set from the column's right edge, inside the
    zone's margin; nothing cut."""
    from apps.ire.graph import TextRun
    sections = [{"heading": "How to use", "text": "Smooth a little over clean skin, morning and night.", "lang": "en"},
                {"heading": "MODO DE USO", "text": "Aplicar un poco sobre la piel limpia, mañana y noche.", "lang": "es"},
                {"heading": "طريقة الاستعمال", "text": "يُطبَّق قليل منه على بشرة نظيفة صباحاً ومساءً.", "lang": "ar"}]
    zone = {"zone_id": "z_back", "zone_type": "BACK_PRINT_ZONE", "x": 0.0, "y": 0.0, "width": 40.0, "height": 60.0,
            "safe_margin_mm": 2.0}
    group, record = bp.compose_back_panel(sections, zone, 10.0, 20.0, size_pt=6.0)
    assert record["fits"] is True and record["copy_preserved"] is True, record
    arabic = [e for e in record["lines"] if e.get("lang") == "ar"]
    assert arabic and all(e["section"] == 2 for e in arabic)
    runs = [n for n in group.children if isinstance(n, TextRun)]
    ar_runs = [r for r in runs if r.rtl]
    assert ar_runs and all(r.align == "right" and abs(r.x - (10.0 + 40.0 - 2.0)) < 1e-9 for r in ar_runs)
    assert all(r.align == "left" for r in runs if not r.rtl)
    order = [e["section"] for e in record["lines"]]
    assert order == sorted(order)                                         # English, then Spanish, then Arabic



def test_his_final_goal_c5c_a_containers_back_carries_the_languages_he_chose():
    """[His final goal, 2026-10-05, C5: "STOP and offer ... fewer languages"] The back's languages are his choice of a
    stopped back's offers: a language left out is his choice, never a code; all three when he has not chosen."""
    from apps.pipeline.targets.container import label_languages, trilingual_sections
    sections = [{"heading": "How to use", "text": "Smooth over lips."}, {"heading": "Warnings", "text": "External use."}]
    from apps.pipeline.targets.container import back_english
    kept = {"english": back_english(sections), "translations": {
        "es": {"how_to_use": "Aplicar.", "warnings": "Uso externo."},
        "ar": {"how_to_use": "يُطبَّق.", "warnings": "للاستخدام الخارجي."}}}
    every, codes = trilingual_sections(sections, kept)
    assert [s["lang"] for s in every] == ["en", "en", "es", "es", "ar", "ar"] and codes == []
    two, codes = trilingual_sections(sections, kept, languages=("en", "es"))
    assert [s["lang"] for s in two] == ["en", "en", "es", "es"] and codes == []
    one, codes = trilingual_sections(sections, {}, languages=("en",))
    assert [s["lang"] for s in one] == ["en", "en"] and codes == []       # no translation asked of an English back
    assert label_languages({}) == ("en", "es", "ar") and label_languages(
        {"container_label_languages": ["en"]}) == ("en",)


def test_his_final_goal_c5c_a_stopped_back_offers_each_smaller_set_its_back_holds():
    """Each set of fewer languages (the carton's own sets) is measured by composing the back again — offered where its
    back panel's own fit says it holds, never where it does not."""
    from types import SimpleNamespace

    from apps.pipeline.targets.container import back_english, back_label_offers
    sections = [{"heading": "How to use", "text": "Smooth over lips."}, {"heading": "Warnings", "text": "External use."}]
    kept = {"english": back_english(sections), "translations": {
        "es": {"how_to_use": "Aplicar.", "warnings": "Uso externo."},
        "ar": {"how_to_use": "يُطبَّق.", "warnings": "للاستخدام الخارجي."}}}
    seen = []

    def compose_again(secs):
        langs = sorted({s["lang"] for s in secs})
        seen.append(langs)
        return SimpleNamespace(metadata={"container_back_panel/1.0": {"fits": len(langs) <= 2 and "ar" not in langs}})
    offers = back_label_offers(compose_again, sections, kept, ("en", "es", "ar"))
    assert sorted(map(tuple, seen)) == [("ar", "en"), ("en",), ("en", "es")]
    assert [o["languages"] for o in offers] == [["en", "es"], ["en"]]


def test_his_correction_of_2026_10_07_a_container_back_shrinks_evenly_to_3_pt_before_it_stops():
    """[His correction of 2026-10-07 (transcribed at a6b2092): "my rule for every design: when the label doesn't fit,
    the text gets SMALLER ... Shrink the whole label evenly until everything fits, keeping its layout, spacing and
    order. Floor: 3 pt."] A container's back that does not stand at its 5 pt fallback: there is a height at which it
    stands only shrunk — every line at one size, under 5 pt and not under 3 — in its own faces (no narrower face), each
    drawn run at that size; a height at which it does not stand even at 3 pt says so (fits False) and is laid at 3 pt; a
    print method's recorded minimum is never undercut."""
    meta = {"typography_surface": "apps/ire/compose_container.py::compose_container_graph"}
    sections = [{"heading": "INGREDIENTS", "text": _INCI, "fine": True},
                {"heading": "STORY", "text": "Petals gathered at dawn in the valley, pressed slowly into a soft and "
                                             "luminous serum, then rested for a season before it is bottled."},
                {"heading": "NOTES", "text": "Kept in the shade, away from the sun, it holds its colour and its "
                                             "scent through the year.", "fine": True}]
    shrunk = stopped = None
    for tenth in range(600, 100, -5):
        zone = dict(_BACK_ZONE, height=tenth / 10.0)
        group, record = bp.compose_back_panel(sections, zone, 10.0, 20.0, doc_metadata=meta,
                                              heading_role="heading", copy_role="body")
        if record["fits"] and record["size_pt"] < 5.0 and shrunk is None:
            shrunk = (group, record)
        if not record["fits"]:
            stopped = record
            break
    assert shrunk and stopped, "no height that shrinks, or none that stops"
    group, record = shrunk
    sizes = {round(e.get("size_pt", record["size_pt"]), 2) for e in record["lines"]}
    assert sizes == {record["size_pt"]} and 3.0 <= record["size_pt"] < 5.0, (sizes, record["size_pt"])
    runs = [n for n in group.children if getattr(n, "type", "") == "text"]
    assert runs and {n.size_pt for n in runs} == {record["size_pt"]} and {n.font for n in runs} <= {"body", "heading"}
    assert "face" not in record and stopped["size_pt"] == bp.LABEL_FLOOR_PT == 3.0



#: 122's back copy as it is drawn: his English, the system's Spanish and Arabic (its sticker's own translations)
_BACK_122 = [
    {"heading": "Description", "text": "A soft, fast-absorbing hand cream with a gentle rose scent.", "lang": "en"},
    {"heading": "Ingredients / INGREDIENTES", "text": "Aqua, Glycerin, Butyrospermum Parkii Butter, Cetearyl Alcohol, "
                                                     "Parfum, Phenoxyethanol.", "lang": "en"},
    {"heading": "How to use", "text": "massage into clean hands as often as needed.", "lang": "en"},
    {"heading": "Warnings", "text": "For external use only. Avoid contact with eyes.", "lang": "en"},
    {"heading": "Net content", "text": "60 ml ℮ 2 fl oz", "lang": "en"},
    {"heading": "DESCRIPCIÓN", "text": "Crema de manos suave y de rápida absorción con delicado aroma a rosa.",
     "lang": "es"},
    {"heading": "MODO DE USO", "text": "Aplicar masajeando sobre las manos limpias con la frecuencia necesaria.",
     "lang": "es"},
    {"heading": "ADVERTENCIAS", "text": "Solo para uso externo. Evitar el contacto con los ojos.", "lang": "es"},
    {"heading": "الوصف", "text": "كريم يدين ناعم سريع الامتصاص بعطر ورد لطيف.", "lang": "ar"},
    {"heading": "طريقة الاستعمال", "text": "يدلّك على اليدين النظيفتين عند الحاجة.", "lang": "ar"},
    {"heading": "تحذيرات", "text": "للاستخدام الخارجي فقط. تجنب ملامسة العينين.", "lang": "ar"},
]


def test_his_finding_122_a_product_back_uses_its_whole_area_its_three_languages_balanced():
    """[His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), C: "Back label laid out like packaging, using the whole area: clear hierarchy, the
    three languages as balanced blocks; never cramped at the bottom with empty space below."] 122's back, 54.9 x 99.9 mm,
    in English, Spanish and Arabic: the label grows from its print size while its whole copy stands, to GROW_MAX_PT, and
    the height it leaves is shared between its language blocks — its last line at its foot, never a third of the panel
    empty below; each block's headings bold over its copy; an evidence sheet's back stays as it was."""
    meta = {"typography_surface": "apps/ire/compose_container.py::compose_container_graph"}
    zone = dict(_BACK_ZONE, width=54.9, height=99.9, safe_margin_mm=3.0)
    group, record = bp.compose_back_panel(_BACK_122, zone, 0.0, 0.0, doc_metadata=meta, heading_role="heading",
                                          copy_role="body", fill_area=True)
    assert record["fits"] is True and record["grown_from_pt"] < record["size_pt"] <= bp.GROW_MAX_PT, record["size_pt"]
    assert record["block_gap_mm"] > 0.0
    last = max(e["baseline_mm"] for e in record["lines"])
    assert record["height_available_mm"] - last < 0.08 * record["height_available_mm"], (last, record)
    firsts = {}
    for e in record["lines"]:
        firsts.setdefault(_BACK_122[e["section"]]["lang"], e["baseline_mm"])
    assert firsts["en"] < firsts["es"] < firsts["ar"]                    # three blocks, in his order
    runs = [n for n in group.children if getattr(n, "type", "") == "text"]
    assert {n.font for n in runs if "-heading-" in n.name} == {"heading"} and {n.font for n in runs
                                                                              if "-copy-" in n.name} == {"body"}
    _g, exempt = bp.compose_back_panel(_BACK_122, zone, 0.0, 0.0, heading_role="heading", copy_role="body",
                                       fill_area=True)
    assert "grown_from_pt" not in exempt and exempt["block_gap_mm"] == 0.0
    _g, sheet = bp.compose_back_panel(_BACK_122, zone, 0.0, 0.0, doc_metadata=meta, heading_role="heading",
                                      copy_role="body")                     # the dropper's sheet: as it was
    assert "grown_from_pt" not in sheet and sheet["block_gap_mm"] == 0.0
