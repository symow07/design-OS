"""2A-9C slice 0 — framework generalization regression.

The opposing-tuck baseline is the non-regression net: every frozen value
in the committed 2A-9B reports (fixture outcomes, geometry hashes, content
hashes, sweep counts) must reproduce exactly through the generalized
capability-driven framework. Plus: adapter registry, closure declarations,
and the four independent authority states.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.test import TestCase

from apps.dielines.qualification.authority import (
    AuthorityError,
    MACHINE_GRANTABLE,
    authority_record,
    technical_projection,
)
from apps.dielines.qualification.runner import (
    adapter_for,
    fixtures_for,
    qualify,
    registered_adapters,
    seeded_property_sweep,
    sweep_seed_for,
)

DOCS = Path("docs/qualification/reference_opposed_tuck_carton_0_1")


class ByteStabilityTests(TestCase):
    """The generalized framework reproduces the accepted 2A-9B evidence."""

    def test_committed_matrix_values_reproduce_exactly(self):
        adapter = adapter_for("reference_opposed_tuck_carton")
        committed = json.loads(
            (DOCS / "qualification_matrix.json").read_text())
        assert committed["rows"], "committed matrix is empty"
        for row in committed["rows"]:
            result = qualify(row["input"], adapter)
            outcome = ("SUPPORTED" if result.supported else
                       ("REJECTED_BY_DOMAIN" if result.violations
                        else "INVARIANT_FAILURE"))
            assert outcome == row["outcome"], (row["case"], outcome)
            if row["outcome"] == "SUPPORTED":
                assert result.geometry_hash == row["geometry_hash"], \
                    row["case"]
                assert result.content_hashes == row["content_hashes"], \
                    row["case"]

    def test_committed_sweep_counts_reproduce_exactly(self):
        adapter = adapter_for("reference_opposed_tuck_carton")
        committed = json.loads(
            (DOCS / "property_test_report.json").read_text())
        seed = committed["summary"]["seed"]
        assert seed == sweep_seed_for("reference_opposed_tuck_carton")
        sweep = seeded_property_sweep(
            adapter, seed=seed,
            n_in_domain=committed["summary"]["in_domain_samples"],
            n_random=committed["summary"]["random_samples"])
        assert sweep["failures"] == []
        assert sweep["supported"] == committed["summary"]["supported"]
        assert sweep["rejected_by_domain"] == \
            committed["summary"]["rejected_by_domain"]


class AdapterRegistryTests(TestCase):
    def test_registry_is_explicit(self):
        assert "reference_opposed_tuck_carton" in registered_adapters()
        assert "straight_tuck_end_carton" in registered_adapters()
        assert adapter_for("tuck_top_auto_bottom_carton") is None
        adapter = adapter_for("reference_opposed_tuck_carton")
        assert adapter.key == "reference_opposed_tuck_carton/0.1"

    def test_closure_capabilities_are_declared_not_assumed(self):
        adapter = adapter_for("reference_opposed_tuck_carton")
        closure = adapter.closure
        assert closure.orientation == "OPPOSING_TUCK"
        assert closure.major_tuck_count == 2
        assert closure.top_tuck_panel != closure.bottom_tuck_panel
        assert closure.locking_mechanism == "ENTRY_SLIT_EARS"
        assert closure.slit_type == "ENTRY_SLIT_L_CUT"
        assert closure.fold_sequence == ("dust_flap", "dust_flap",
                                         "major_tuck")
        assert closure.physical_validation_requirement == \
            "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"
        # the capability views the invariants read are derived from it
        assert adapter.dust_panels == list(closure.dust_panels)
        assert adapter.expected_slit_count == 8

    def test_fixture_sets_are_frozen_per_archetype(self):
        fixtures = fixtures_for("reference_opposed_tuck_carton")
        assert "task_50_exact" in fixtures
        assert "measured_reference_28x28x120" in \
            fixtures_for("straight_tuck_end_carton")
        assert fixtures_for("tuck_top_auto_bottom_carton") == {}


class AuthorityStateTests(TestCase):
    def test_states_are_independent_and_machine_bounded(self):
        assert MACHINE_GRANTABLE == {"TECHNICALLY_QUALIFIED_DOMAIN"}
        adapter = adapter_for("reference_opposed_tuck_carton")
        record = technical_projection(adapter, sweep_seed=20260722,
                                      accepted_commit="d4bec1b")
        assert record["state"] == "TECHNICALLY_QUALIFIED_DOMAIN"
        assert "seed=20260722" in record["evidence_identity"]
        assert any("no physical or production authority" in lim
                   for lim in record["limitations"])

    def test_physical_states_require_fit_pass_evidence(self):
        with self.assertRaises(AuthorityError):
            authority_record(
                state="PHYSICALLY_VALIDATED_INSTANCE",
                archetype_key="x/0.1",
                validation_source="visual review",
                evidence_identity="screenshot")   # no FIT_PASS -> refused
        record = authority_record(
            state="PHYSICALLY_VALIDATED_INSTANCE",
            archetype_key="x/0.1", geometry_hash="abc",
            board_thickness_mm=0.5,
            validation_source="printed 100% sample",
            evidence_identity="physical_validation record: FIT_PASS abc")
        assert record["geometry_hash"] == "abc"

    def test_manufacturer_state_requires_manufacturer(self):
        with self.assertRaises(AuthorityError):
            authority_record(
                state="PRODUCTION_AUTHORIZED_BY_MANUFACTURER",
                archetype_key="x/0.1",
                validation_source="press run",
                evidence_identity="PO-123")
        record = authority_record(
            state="PRODUCTION_AUTHORIZED_BY_MANUFACTURER",
            archetype_key="x/0.1", manufacturer="ACME Print Co",
            validation_source="press run",
            evidence_identity="PO-123")
        assert record["manufacturer"] == "ACME Print Co"

    def test_provenance_is_mandatory(self):
        with self.assertRaises(AuthorityError):
            authority_record(state="TECHNICALLY_QUALIFIED_DOMAIN",
                             archetype_key="x/0.1",
                             validation_source="", evidence_identity="")
