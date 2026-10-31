"""Design Graph 2.0 — semantic components with mandatory provenance, and
the guarantee that it breaks neither path the visual-quality gate reads.

v2 EXTENDS a live contract. `container_design_graph/1.1` is a census of
primitives; v2 adds the semantic layer above it while carrying the census
forward verbatim. The gate reads `product_bounds` (structural fallback)
and `reconstruction_silhouette` (R2b's measured comparison) off the same
record, and a v2 build that dropped either would not raise anywhere — it
would just make an axis quietly UNMEASURED again. That is the property
these tests exist to pin.
"""
import pytest

from apps.ire import design_graph_v2 as dg2
from apps.pipeline.services import visual_quality_gate as vqg


def _base(**over):
    """A realistic container_design_graph/1.1 census."""
    rec = {
        "schema_version": "container_design_graph/1.1",
        "mode": "native",
        "archetype": "cylindrical_serum_dropper",
        "zones_consumed": ["front"],
        "primitives": {"live_text": 3, "vector_paths": 12,
                       "reference_rasters": 1, "logo_rasters": 1},
        "decorative_raster_count": 0,
        "surface_groups": ["front"],
        "motif_groups": [],
    }
    rec.update(over)
    return rec


def _prov(**over):
    p = {"origin": dg2.ORIGIN_CONFIRMED_INTENT,
         "source": "intent field product_name",
         "confirmation_state": "CONFIRMED"}
    p.update(over)
    return p


class TestProvenanceIsMandatory:
    """A component without recorded provenance is not a component."""

    def test_a_component_with_provenance_builds(self):
        c = dg2.component("label-front", role=dg2.ROLE_LABEL_PANEL,
                          provenance=_prov())
        assert c["provenance"]["origin"] == dg2.ORIGIN_CONFIRMED_INTENT
        assert c["role"] == dg2.ROLE_LABEL_PANEL

    @pytest.mark.parametrize("bad", [None, {}, "confirmed", 0])
    def test_a_component_without_provenance_refuses(self, bad):
        with pytest.raises(dg2.DesignGraphV2Error) as e:
            dg2.component("x", role=dg2.ROLE_LOGO, provenance=bad)
        assert e.value.findings[0].startswith(
            dg2.DG2_COMPONENT_WITHOUT_PROVENANCE)

    @pytest.mark.parametrize("field", dg2.PROVENANCE_REQUIRED)
    def test_each_required_provenance_field_is_enforced(self, field):
        prov = _prov()
        del prov[field]
        with pytest.raises(dg2.DesignGraphV2Error) as e:
            dg2.component("x", role=dg2.ROLE_LOGO, provenance=prov)
        assert any(field in f for f in e.value.findings)

    def test_there_is_no_unknown_or_generated_origin(self):
        """The closed set is the point: AI never generates geometry, so an
        origin that cannot be named is a refusal rather than a category."""
        joined = " ".join(dg2.ORIGINS).upper()
        assert "UNKNOWN" not in joined
        assert "GENERATED" not in joined
        with pytest.raises(dg2.DesignGraphV2Error) as e:
            dg2.component("x", role=dg2.ROLE_LOGO,
                          provenance=_prov(origin="AI_GENERATED"))
        assert e.value.findings[0].startswith(dg2.DG2_ORIGIN_INVALID)

    def test_roles_are_a_closed_set(self):
        with pytest.raises(dg2.DesignGraphV2Error) as e:
            dg2.component("x", role="VIBES", provenance=_prov())
        assert e.value.findings[0].startswith(dg2.DG2_ROLE_INVALID)

    def test_bounds_are_optional_but_never_fake(self):
        assert dg2.component("x", role=dg2.ROLE_LOGO,
                             provenance=_prov())["bounds_mm"] is None
        good = dg2.component("x", role=dg2.ROLE_LOGO, provenance=_prov(),
                             bounds_mm={"width_mm": 20, "height_mm": 10})
        assert good["bounds_mm"] == {"width_mm": 20.0, "height_mm": 10.0}
        for bad in ({"width_mm": 0, "height_mm": 5},
                    {"width_mm": -1, "height_mm": 5},
                    {"width_mm": 5}):
            with pytest.raises(dg2.DesignGraphV2Error) as e:
                dg2.component("x", role=dg2.ROLE_LOGO, provenance=_prov(),
                              bounds_mm=bad)
            assert e.value.findings[0].startswith(dg2.DG2_BOUNDS_INVALID)


class TestV2IsAdditive:
    def test_the_census_survives_verbatim(self):
        base = _base()
        rec = dg2.build(base)
        assert rec["schema_version"] == dg2.SCHEMA
        assert rec["extends"] == "container_design_graph/1.1"
        for key, value in base.items():
            if key == "schema_version":
                continue
            assert rec[key] == value, key
            assert rec["census"][key] == value, key

    def test_a_non_graph_record_refuses(self):
        for bad in ({}, {"schema_version": "something_else/1.0"}, None):
            with pytest.raises(dg2.DesignGraphV2Error) as e:
                dg2.build(bad)
            assert e.value.findings[0].startswith(
                dg2.DG2_BASE_RECORD_INVALID)

    def test_components_are_revalidated_at_the_build_entry_point(self):
        """A caller may hand-assemble a component dict; provenance is not
        optional at any entry point."""
        with pytest.raises(dg2.DesignGraphV2Error):
            dg2.build(_base(), components=[
                {"component_id": "x", "role": dg2.ROLE_LOGO,
                 "provenance": {}}])


class TestTheGatePathsSurvive:
    """The launcher's binding constraint: v2 must not break either path
    `visual_quality_gate._silhouette_axis` reads."""

    PROFILE = {"width_mm": 37.4, "height_mm": 114.3}

    def test_the_structural_product_bounds_path_still_resolves(self):
        base = _base(product_bounds={"width_pt": 106.0, "height_pt": 324.0})
        rec = dg2.build(base)
        assert rec["product_bounds"] == base["product_bounds"]
        axis = vqg._silhouette_axis(rec, self.PROFILE)
        # structural conformance is measured; concept fidelity still is not
        assert axis["measured"]["structural_silhouette_conformance"] in (
            vqg.PASS, vqg.FAIL)
        assert axis["state"] in (vqg.UNMEASURED, vqg.FAIL)

    def test_the_r2b_measured_path_still_resolves(self):
        comparison = {
            "schema": "reconstruction_silhouette_measurement/1.0",
            "binding_statistic": "mean_abs_deviation",
            "mean_abs_deviation": 0.01, "max_abs_deviation": 0.09,
            "threshold": 0.03, "threshold_status": "OWNER_CALIBRATED",
            "within_threshold": True,
            "resolution": {"silhouette_height_px": 614,
                           "effective_dpi": 101.9, "requested_dpi": 150,
                           "requested_dpi_achieved": False,
                           "quantisation_warning": None},
        }
        rec = dg2.build(_base(reconstruction_silhouette=comparison))
        assert vqg._silhouette_axis(rec, self.PROFILE)["state"] == vqg.PASS

    def test_structural_conformance_still_refuses_to_claim_concept_fidelity(
            self):
        """The VQR-1 owner correction, preserved: a structural PASS is
        recorded separately and the axis stays UNMEASURED without a
        concept comparison."""
        rec = dg2.build(_base(
            product_bounds={"width_pt": 106.0, "height_pt": 324.0}))
        axis = vqg._silhouette_axis(rec, self.PROFILE)
        if axis["measured"]["structural_silhouette_conformance"] == vqg.PASS:
            assert axis["state"] == vqg.UNMEASURED

    @pytest.mark.parametrize("key", dg2.GATE_READ_KEYS)
    def test_every_gate_read_key_survives_a_build(self, key):
        """The failure mode this guards would not raise anywhere else: a
        v2 build that lost one of these keys would simply make an axis
        quietly UNMEASURED again, with nothing to notice it. So each key
        the gate reads is asserted to survive, one test per key."""
        base = _base(**{key: {"probe": True}})
        assert dg2.build(base)[key] == {"probe": True}

    def test_the_gate_read_key_list_matches_what_the_gate_reads(self):
        """A key the gate reads but this module does not list would be
        unprotected. Checked against the gate's own source rather than
        against memory."""
        import inspect
        src = inspect.getsource(vqg._silhouette_axis)
        for key in ("product_bounds", "reconstruction_silhouette"):
            assert f'"{key}"' in src, key
            assert key in dg2.GATE_READ_KEYS, key


class TestComponentsFromDocument:
    def test_unclassifiable_nodes_are_left_out_not_guessed(self):
        """An unclassified primitive stays a primitive in the census,
        which is honest; a guessed component would be a claim."""

        class _Node:
            def __init__(self, type_, name):
                self.type, self.name = type_, name

        class _Doc:
            def __init__(self, nodes):
                self._n = nodes

            def walk(self):
                return [(n, None) for n in self._n]

        doc = _Doc([_Node("path", "mystery-shape"),
                    _Node("image", "logo-primary"),
                    _Node("group", "motif-botanical")])
        comps = dg2.components_from_document(doc)
        roles = {c["role"] for c in comps}
        assert roles == {dg2.ROLE_LOGO, dg2.ROLE_MOTIF}
        assert all(c["provenance"]["origin"] in dg2.ORIGINS for c in comps)
        # the unclassifiable path produced nothing rather than a component
        assert not any("mystery" in c["component_id"] for c in comps)
