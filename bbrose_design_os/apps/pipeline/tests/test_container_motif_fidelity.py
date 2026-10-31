"""Phase 2B-2A slice 2 — motif fidelity (measures emitted geometry).

The gate is the emitted geometry, not the label: a SUPPORTED motif must
actually emit its expected node type, or it fails (MOTIF_MISSING /
MOTIF_FAMILY_MISMATCH). A concept with no motif is not measured, and noisy
INFERRED targets stay UNMEASURED.
"""
from __future__ import annotations

from apps.ire import container_motif_fidelity as cmf
from apps.ire.container_fidelity import (MEASURED_FAIL, MEASURED_PASS,
                                         UNMEASURED, UNMEASURED_BLOCKING)
from apps.ire.design_language import (
    POWDER_CONSTELLATION,
    RULED_FIELD,
    LanguageParameters,
)
from apps.ire.graph import Document, Group


def _doc(language):
    nodes = language.build((0.0, 0.0, 60.0, 90.0),
                           LanguageParameters(density=2.0), "front",
                           lambda x: x, lambda y: y)
    return Document(page_w=210, page_h=297,
                    root=Group(name="Artwork", role="artwork", children=nodes))


def _empty_doc():
    return Document(page_w=210, page_h=297,
                    root=Group(name="Artwork", role="artwork", children=[]))


def _spec(cap, rendered_via=None):
    return {"reconstruction_capability": cap, "rendered_via": rendered_via}


def test_supported_motif_with_matching_geometry_passes():
    rep = cmf.validate_motif_fidelity(
        _doc(POWDER_CONSTELLATION), _spec("SUPPORTED", "powder_constellation"))
    assert rep["axes"]["motif_family"]["state"] == MEASURED_PASS
    # §BH50(f)(5): the family passes; density, position, coverage and
    # continuation are unmeasured, and a pass never outvotes them — this line
    # asserted MEASURED_PASS until the ruling
    assert rep["overall"] == UNMEASURED_BLOCKING
    assert rep["counts"]["unmeasured"] >= 1
    assert rep["failures"] == []
    assert rep["measure"]["count"] > 0


def test_supported_motif_with_no_geometry_is_missing():
    rep = cmf.validate_motif_fidelity(
        _empty_doc(), _spec("SUPPORTED", "powder_constellation"))
    assert rep["axes"]["motif_family"]["state"] == MEASURED_FAIL
    assert cmf.MOTIF_MISSING in rep["failures"]


def test_wrong_family_geometry_is_mismatch():
    # ruled geometry emitted, but the spec expects powder particles
    rep = cmf.validate_motif_fidelity(
        _doc(RULED_FIELD), _spec("SUPPORTED", "powder_constellation"))
    assert rep["axes"]["motif_family"]["state"] == MEASURED_FAIL
    assert cmf.MOTIF_FAMILY_MISMATCH in rep["failures"]


def test_capability_none_is_unmeasured():
    rep = cmf.validate_motif_fidelity(_empty_doc(), _spec("NONE"))
    assert rep["overall"] == UNMEASURED
    assert rep["failures"] == []


def test_review_required_is_not_double_counted():
    # a fail-closed motif is gated as its own blocker, not as a fidelity fail
    rep = cmf.validate_motif_fidelity(_empty_doc(), _spec("REVIEW_REQUIRED"))
    assert rep["overall"] == UNMEASURED
    assert rep["failures"] == []


def test_measure_reports_count_and_centroid():
    m = cmf.measure_motif(_doc(POWDER_CONSTELLATION))
    assert m["count"] > 0
    assert m["centroid"] and m["bounding"]
