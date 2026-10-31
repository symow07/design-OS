"""Phase 2B-3C §2-§6 — quantitative container fidelity.

Gates an axis only against a VERIFIED target (§2); first-pass concepts (no
targets) are UNMEASURED by construction. Proves the real firing paths: a
VERIFIED coverage target the emission misses → CONTAINER_MOTIF_COVERAGE_FAILED,
and a VERIFIED upper-left logo zone vs the emitter's centred logo →
CONTAINER_LOGO_ZONE_MISMATCH.
"""
from __future__ import annotations

from apps.ire import container_motif as cm
from apps.ire import container_quant_fidelity as qf
from apps.ire.container_fidelity import MEASURED_FAIL, UNMEASURED
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _doc(motif=True):
    prof = cc.build_inferred_profile("bottle", estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0})
    zones = cc.propose_zones(prof)
    motif_spec = cm.build_motif_spec(
        {"verified": True, "motif_signature": "powder constellation"},
        {"fields": {}}, zones, prof) if motif else cm.build_motif_spec(
        None, {"fields": {}}, zones, prof)
    bb = build_backbone(ContainerProfile(archetype="bottle", width_mm=40,
                                         height_mm=110))
    doc = compose_container_graph(bb, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=zones,
                                  native=True, motif_spec=motif_spec)
    return doc, motif_spec


def _vg(**fields):
    return {"schema_version": "container_selected_concept_visual_graph/1.0",
            "fields": fields}


def _verified(value):
    return {"value": value, "verification": "VERIFIED"}


def test_first_pass_axes_are_unmeasured_not_fabricated():
    doc, ms = _doc(motif=False)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)
    assert rep["overall"] == UNMEASURED
    assert rep["failures"] == []
    assert rep["counts"][UNMEASURED] >= 10          # most axes have no target


def test_coverage_target_miss_fails_and_is_a_readiness_finding():
    doc, ms = _doc(motif=True)
    # concept demands 90% decorative coverage; the emitted motif is far less
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(decoration_coverage=_verified(90)), ms)
    assert rep["axes"]["motif_coverage"]["state"] == MEASURED_FAIL
    assert qf.MOTIF_COVERAGE_FAILED in rep["failures"]
    assert rep["overall"] == MEASURED_FAIL


def test_coverage_uses_ink_area_not_bounding_extent():
    # a sparse constellation's INK coverage is low (~<40%), NOT the ~70%
    # bounding-box extent of the motif group — the measure must reflect ink,
    # so a realistic target near the measured ink coverage PASSES
    doc, ms = _doc(motif=True)
    fr = qf._field_rect(doc, "decoration-field")
    ink = qf._ink_coverage(doc, fr[2] * fr[3])
    assert ink < 0.5                                  # not bounding extent
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(decoration_coverage=_verified(round(ink * 100, 1))), ms)
    assert rep["axes"]["motif_coverage"]["state"] != MEASURED_FAIL


def test_logo_upper_left_target_vs_centred_emission_fails():
    doc, ms = _doc(motif=False)
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(logo_zone=_verified("upper left")), ms)
    assert rep["axes"]["logo_zone"]["state"] == MEASURED_FAIL
    assert qf.LOGO_ZONE_MISMATCH in rep["failures"]


def test_logo_zone_passes_only_on_a_compared_centred_anchor_and_never_on_no_logo():
    """§BH50(f)(5): a centred target against the emitter's centred anchor is a
    compared PASS; a target with no logo emitted is UNMEASURED (it used to
    pass for any target but upper-left); a token no instrument compares is
    UNMEASURED, named; the upper-left failure stays as it was."""
    doc, ms = _doc(motif=False)
    doc.metadata["logo_zone_used"] = "front-controlled-fallback"
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(logo_zone=_verified("centred, upper third")), ms)
    assert rep["axes"]["logo_zone"]["state"] == "MEASURED_PASS"
    assert "equal" in rep["axes"]["logo_zone"]["detail"]
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(logo_zone=_verified("lower right")), ms)
    assert rep["axes"]["logo_zone"]["state"] == UNMEASURED
    assert "lower right" in rep["axes"]["logo_zone"]["detail"]
    doc.metadata["logo_zone_used"] = ""
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(logo_zone=_verified("centred, upper third")), ms)
    assert rep["axes"]["logo_zone"]["state"] == UNMEASURED
    assert "no logo placement" in rep["axes"]["logo_zone"]["detail"]
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(logo_zone=_verified("upper left")), ms)
    assert rep["axes"]["logo_zone"]["state"] == MEASURED_FAIL


def test_the_name_axis_fails_a_definite_mismatch_and_passes_only_a_compared_match():
    """§BH50(f)(5): a right-column target against centred runs is a definite
    mismatch — a readiness finding, never a reconstruction blocker; a centred
    target against centred runs of sufficient height is a compared PASS."""
    doc, ms = _doc(motif=False)
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(product_name_zone=_verified("right column")), ms)
    assert rep["axes"]["product_name"]["state"] == MEASURED_FAIL
    assert qf.PRODUCT_NAME_ZONE_MISMATCH in rep["failures"]
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(product_name_zone=_verified("centered stack")), ms)
    assert rep["axes"]["product_name"]["state"] in ("MEASURED_PASS", MEASURED_FAIL)
    if rep["axes"]["product_name"]["state"] == "MEASURED_PASS":
        assert "equal" in rep["axes"]["product_name"]["detail"]
    else:                                     # too small for this print zone
        assert qf.PRODUCT_NAME_TOO_SMALL in rep["failures"]


def test_a_pass_never_outvotes_an_unmeasured_axis():
    """§BH50(f)(5): one measured pass beside sixteen unmeasured axes read
    MEASURED_PASS before the ruling; it reads UNMEASURED_BLOCKING now, and an
    all-unmeasured report still reads UNMEASURED."""
    doc, ms = _doc(motif=False)
    doc.metadata["logo_zone_used"] = "front-controlled-fallback"
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(logo_zone=_verified("centred, upper third")), ms)
    assert rep["axes"]["logo_zone"]["state"] == "MEASURED_PASS"
    assert rep["overall"] == "UNMEASURED_BLOCKING"
    assert rep["failures"] == []
    assert qf.measure_quantitative_fidelity(doc, _vg(), ms)["overall"] == UNMEASURED


def test_no_logo_target_is_unmeasured():
    doc, ms = _doc(motif=False)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)
    assert rep["axes"]["logo_zone"]["state"] == UNMEASURED


def test_name_fidelity_measured_against_print_zone():
    doc, ms = _doc(motif=False)
    # a VERIFIED name-zone target activates the axis; the emitted name is
    # measured against the confirmed PRINT ZONE (§4), yielding a real
    # failure — too small for, or misaligned with, the concept's zone
    rep = qf.measure_quantitative_fidelity(
        doc, _vg(product_name_zone=_verified("left column")), ms)
    assert rep["axes"]["product_name"]["state"] == MEASURED_FAIL
    assert rep["failures"]
    assert (qf.PRODUCT_NAME_ZONE_MISMATCH in rep["failures"]
            or qf.PRODUCT_NAME_TOO_SMALL in rep["failures"])
    # the report records the print-zone dimensions it measured against
    assert rep["field_zone_mm"] is not None


# --- §BH65(a): AN AXIS READS ALWAYS AND MEASURES ONLY AGAINST A TARGET -------
# His words: "it is one that has never taken a reading, and §BH55(3) does not
# protect a blank … No threshold is set from them yet: report what they read."
# Every assertion below is about the READING; the four tests together also pin
# that taking one changed no verdict, which is the whole safety of the change.

def test_bh65a_every_axis_answers_with_a_reading_or_a_stated_reason():
    doc, ms = _doc(motif=True)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)
    assert len(rep["axes"]) == 17, sorted(rep["axes"])
    for name, axis in rep["axes"].items():
        assert "reading" in axis and "reading_method" in axis, name
        assert axis["reading_method"], (
            "%s reads nothing and says nothing about why" % name)


def test_bh65a_the_two_axes_that_cannot_read_say_so_by_name():
    """§BH50(f)'s own cost list: `cap_orientation` needs "a definition first —
    only the name and its code exist", and `cap_artwork_zone` needs a cap or
    collar artwork zone his confirmed decision excludes. Neither is given a
    fabricated zero."""
    doc, ms = _doc(motif=True)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)
    assert rep["axes"]["cap_orientation"]["reading"] is None
    assert "NO DEFINITION EXISTS" in rep["axes"]["cap_orientation"]["reading_method"]
    assert rep["axes"]["cap_artwork_zone"]["reading"] is None
    assert "confirmed decision" in rep["axes"]["cap_artwork_zone"]["reading_method"]


def test_bh65a_a_reading_is_never_a_verdict():
    """THE SAFETY OF THE WHOLE CHANGE, asserted rather than asserted-about: a
    document with NO verified target reads numbers on most axes and still
    reports every one of them UNMEASURED, with no failure and no pass. §BH65(a)
    sets no threshold and §BH55(3) holds governance still."""
    doc, ms = _doc(motif=True)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)      # no targets at all
    assert rep["readings"]["taken"] >= 6, rep["readings"]
    assert rep["overall"] == UNMEASURED
    assert rep["failures"] == []
    assert rep["counts"][MEASURED_FAIL] == 0
    for name, axis in rep["axes"].items():
        assert axis["state"] == UNMEASURED, (name, axis["state"])
        assert axis["target"] is None, name


def test_bh65a_the_partition_is_on_the_record_and_adds_up():
    doc, ms = _doc(motif=True)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)
    r = rep["readings"]
    assert r["taken"] + len(r["absent"]) == len(rep["axes"]) == 17
    assert "cap_orientation" in r["absent"]
    assert "THRESHOLD" in r["scope"].upper()


def test_bh65a_the_readings_are_the_documents_own_numbers():
    """Not placeholders: the motif reading counts the marks this document
    actually emits, and the type ladder is its own run sizes."""
    doc, ms = _doc(motif=True)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)["axes"]
    ladder = rep["typography_hierarchy"]["reading"]
    assert isinstance(ladder, list) and ladder, ladder
    assert ladder == sorted(ladder, reverse=True), ladder
    assert rep["motif_continuation"]["reading"] == qf.take_readings(
        doc, qf._field_rect(doc, "decoration-field"))["motif_continuation"][0]
    density = rep["motif_density"]["reading"]
    assert density is None or density >= 0.0


def test_bh65a_the_confirmed_zone_is_the_field_when_the_document_names_none():
    """FOUND BY TAKING THE READINGS ON A LIVE COMPACT rather than on this
    file's synthetic bottle: four axes divide by a decoration field, and
    `compose_container` emits the `decoration-field` rect only on its
    non-direct-print branch — the branch a compact takes returns before it. The
    CONFIRMED zone set supplies the field instead, which adds no node to the
    document and is the geometry a human actually confirmed."""
    doc, ms = _doc(motif=True)
    stripped = [n for n, _ in doc.walk()
                if n.type == "rect" and str(getattr(n, "name", "")) == "decoration-field"]
    for node in stripped:                      # make it look like the compact path
        node.name = "decoration-field-renamed"
    bare = qf.measure_quantitative_fidelity(doc, _vg(), ms)
    assert bare["axes"]["motif_coverage"]["reading"] is None
    zoned = qf.measure_quantitative_fidelity(
        doc, _vg(), ms,
        zones=[{"zone_id": "z_lid", "width": 90.2, "height": 74.1},
               {"zone_id": "z_base", "width": 99.0, "height": 85.5}])
    assert zoned["axes"]["motif_coverage"]["reading"] is not None
    assert "z_base" in zoned["readings"]["field_source"], zoned["readings"]
    # and it still changes NO verdict
    assert zoned["overall"] == UNMEASURED and zoned["failures"] == []
    assert all(a["state"] == UNMEASURED for a in zoned["axes"].values())


def test_bh65a_a_wrapped_name_is_one_tier_not_two_runs_tied_at_the_top():
    """FOUND WHILE VERIFYING §BH65(b), AND IT CORRECTS THE EXECUTOR'S OWN (a) REPORT. Task 89's drawn file set
    "Focus Pressed" / "Powder" as one 9 pt name on two lines; the ladder read [9.0, 9.0, 5.0] and was reported
    as "two runs tied at the top — no typographic hierarchy". It was one tier. Read by tier it is [9.0, 5.0]."""
    from apps.ire.graph import Color, Document, Group, TextRun
    ink = Color.from_hex("#3A2A30")

    def run(name, text, pt):
        return TextRun(name=name, text=text, x=5.0, y=10.0, size_pt=pt, color=ink)
    doc = Document(title="t", page_w=100.0, page_h=100.0, root=Group(
        name="front", role="decoration", children=[
            run("product-name-hero-0", "Focus Pressed", 9.0),
            run("product-name-hero-1", "Powder", 9.0),
            run("front-descriptor", "pressed powder compact", 5.0)]))
    reading, method = qf.take_readings(doc, None)["typography_hierarchy"]
    assert reading == [9.0, 5.0], reading
    assert "2 tier(s) from 3 run(s)" in method and "[2, 1]" in method, method


def test_bh65a_the_stroke_defect_is_named_against_every_number_built_on_it():
    """§Z4/WI-L recorded that `_path_bbox` ignores stroke width, so a hairline
    reads zero, and that fixing it MOVES gate axes — which §BH55(3) holds still
    and that note already left to the owner. It is not fixed here, so every
    reading built on a path box carries the caveat in its own method string
    rather than being quietly wrong."""
    doc, ms = _doc(motif=True)
    rep = qf.measure_quantitative_fidelity(doc, _vg(), ms)["axes"]
    for name in ("motif_coverage", "front_back_balance", "front_dominance"):
        if rep[name]["reading"] is not None:
            assert "stroke width" in rep[name]["reading_method"], name
