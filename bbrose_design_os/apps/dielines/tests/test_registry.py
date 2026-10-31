"""Canonical template registry (Phase 2A-6 §2) + selection priority (§3)."""
from __future__ import annotations

import importlib

import pytest

from apps.dielines import registry
from apps.dielines.geometry.engine import _STYLE_CONFIG, calculate_dieline
from apps.dielines.geometry.ecma_ste import _SPECS as _ECMA_SPECS
from apps.dielines.geometry.opposed_tuck import _SPECS as _OPPOSED_SPECS
from apps.dielines.geometry.side_seam import _SPEC_REGISTRY
from apps.dielines.validators.schema import DielineInputJSON, _SUPPORTED_TEMPLATES


def _own_solver_templates():
    """Day 13, D-D13-3: templates solved by their own module from the product records, taking no carton input (no
    panel sequence, no W/D/H parameters) — the stand die, counter_tray_header 1.0, published by its number only (0.1,
    the family counter display, went to archive/ in the consolidation of 2026-10-28). Each must name a module that
    really solves its record and draws its die; that is its 'buildable', since the carton engine's dispatch never
    sees it."""
    from apps.dielines.tests.test_counter_display import MATRIX
    own = set()
    for d in registry.all_templates(current_only=False):
        if d.panel_sequence == () and d.required_parameters == ():
            module = importlib.import_module(d.geometry_module)
            if d.geometry_module.endswith('stand_templates'):     # the stand family (owner's part 2, 2026-10-31)
                record = module.solve(d.template_id, product={'width_mm': 15.0, 'depth_mm': 15.0, 'height_mm': 100.0, 'cap_mm': 30.0}, rows=1, columns=4)
                assert module.build_die(record).parts, d.template_id
            else:
                assert module.build_die(module.solve(**MATRIX['bottle 1×4 flat, E-flute'])).parts, d.template_id
            own.add(d.template_id)
    return own


class TestRegistryContract:
    def test_registered_template_resolves(self):
        defn = registry.resolve("skynte_foundation_tuck_carton")
        assert defn.version == "1.0"
        assert defn.key == "skynte_foundation_tuck_carton/1.0"

    def test_unknown_template_fails_closed(self):
        with pytest.raises(registry.UnknownTemplate):
            registry.resolve("mystery_carton")
        assert registry.is_registered("mystery_carton") is False

    def test_version_pin_is_exact(self):
        with pytest.raises(registry.TemplateVersionMismatch):
            registry.resolve("skynte_foundation_tuck_carton", "0.9")
        # the published version resolves
        assert registry.resolve("skynte_foundation_tuck_carton", "1.0")

    def test_registry_matches_engine_dispatch(self):
        """Every registered template must be buildable and vice versa —
        a registry entry with no geometry is a lie to the reviewer."""
        buildable = (set(_STYLE_CONFIG) | set(_SPEC_REGISTRY)
                     | set(_ECMA_SPECS) | set(_OPPOSED_SPECS))
        registered = {d.template_id for d in registry.all_templates(current_only=False)}
        own = _own_solver_templates()        # Day 13, D-D13-3: built by its own module, not the carton engine
        assert own == {"counter_tray_header", "stepped_tiered", "lid_header_tray", "slanted_front", "tester_unit"}
        assert registered == buildable | own and not own & buildable
        assert registered - own == set(_SUPPORTED_TEMPLATES)

    @pytest.mark.parametrize(
        "template_id", [d.template_id for d in registry.all_templates()])
    def test_declared_panel_order_matches_the_drawn_die(self, template_id):
        """The registry is the structural source of truth the confirmation
        page and the Gate-2 panel-sequence check both read — so it must equal
        what the engine actually draws, for EVERY template. (A registry that
        merely agrees with itself is how task #47's mismatch happened.)"""
        if template_id in _own_solver_templates():
            # Day 13, D-D13-3: no carton panel run to compare; its parts are what its own module draws
            module = importlib.import_module(registry.resolve(template_id).geometry_module)
            drawn = [p.name for p in module.build_die(module.full_record()).parts]
            assert registry.resolve(template_id).panel_order() == []
            assert drawn == ["tray", "slot insert", "front platform", "back platform"]
            return
        # 2A-9B: the opposing-tuck archetype enforces a derived domain
        # (W >= D + t + 20 for folded dust clearance), so it is drawn at
        # dimensions inside its own domain — same contract check.
        dims = ({"width_mm": 90.0, "depth_mm": 32.0, "height_mm": 140.0}
                if template_id == "reference_opposed_tuck_carton"
                else {"width_mm": 42.0, "depth_mm": 32.0,
                      "height_mm": 140.0})
        params = DielineInputJSON(
            template=template_id, unit="mm",
            dimensions=dims,
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                          "thickness_compensation": True},
            metadata={"product_name": "registry check", "product_type": "carton"},
        )
        drawn = [p.name for p in calculate_dieline(params).panels]
        assert registry.resolve(template_id).panel_order() == drawn

    def test_panel_sequences_are_explicit_and_differ(self):
        ste = registry.resolve("straight_tuck_end_carton")
        skynte = registry.resolve("skynte_foundation_tuck_carton")
        # STE seats the glue tab against the tuck-carrying BACK panel;
        # the side-seam archetype seats it against a SIDE panel.
        assert ste.panel_order()[1] == "back"
        assert skynte.panel_order()[1] == "side_left"
        assert ste.panel_order() != skynte.panel_order()
        assert ste.glue_seam_position == registry.SEAM_ON_MAIN
        assert skynte.glue_seam_position == registry.SEAM_ON_SIDE

    def test_capabilities_declared(self):
        skynte = registry.resolve("skynte_foundation_tuck_carton")
        assert "tuck_base_entry_slits" in skynte.flap_capabilities
        assert "shoulder_lock_notches_2t" in skynte.notch_capabilities
        # the generic STE does NOT claim entry slits it does not draw
        ste = registry.resolve("straight_tuck_end_carton")
        assert "tuck_base_entry_slits" not in ste.flap_capabilities

    def test_generic_flagging(self):
        assert registry.is_generic("straight_tuck_end_carton") is True
        assert registry.is_generic("skynte_foundation_tuck_carton") is False

    def test_dimensions_constrain_but_never_select(self):
        defn = registry.resolve("skynte_foundation_tuck_carton")
        assert defn.fits_dimensions(
            {"width_mm": 42, "depth_mm": 32, "height_mm": 140}) == []
        problems = defn.fits_dimensions(
            {"width_mm": 42, "depth_mm": 32, "height_mm": 2000})
        assert problems and "height_mm" in problems[0]

    def test_geometry_hash_is_stable_and_parameter_sensitive(self):
        a = registry.geometry_hash("t", "1.0", {"w": 1, "h": 2})
        b = registry.geometry_hash("t", "1.0", {"h": 2, "w": 1})
        c = registry.geometry_hash("t", "1.0", {"w": 1, "h": 3})
        d = registry.geometry_hash("t", "1.1", {"w": 1, "h": 2})
        assert a == b
        assert a != c and a != d


class TestSelectionPriority:
    """Deterministic priority, and the impossibility of a silent generic."""

    @staticmethod
    def _task(product=None):
        from types import SimpleNamespace
        return SimpleNamespace(product=product)

    @staticmethod
    def _product_with_association(template_id):
        from types import SimpleNamespace
        structure = SimpleNamespace(
            structure_id="PKG-STR-009",
            surface_zones={"dieline_template": template_id})
        return SimpleNamespace(packaging_structure=structure)

    def _select(self, **kw):
        from apps.pipeline.services.template_selection import select_template
        return select_template(kw.pop("task", self._task()), **kw)

    def test_priority_1_user_confirmation_wins(self):
        sel = self._select(
            task=self._task(self._product_with_association(
                "straight_tuck_end_carton")),
            user_template="skynte_foundation_tuck_carton")
        assert sel.resolved and sel.source == "EXPLICIT_USER_CONFIRMATION"
        assert sel.template_id == "skynte_foundation_tuck_carton"
        assert sel.confidence == 1.0

    def test_priority_2_product_association(self):
        sel = self._select(task=self._task(self._product_with_association(
            "skynte_foundation_tuck_carton")))
        assert sel.resolved and sel.source == "PRODUCT_TEMPLATE_ASSOCIATION"

    def test_priority_4_strategy_only_above_floor(self):
        high = self._select(strategy_recommendation=(
            "straight_tuck_end_carton", 0.8))
        assert high.resolved and high.source == "TARGET_STRATEGY_RECOMMENDATION"
        low = self._select(strategy_recommendation=(
            "straight_tuck_end_carton", 0.5))
        assert low.resolved is False
        assert low.code == "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"

    def test_no_evidence_requires_human_confirmation(self):
        sel = self._select()
        assert sel.resolved is False
        assert sel.code == "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"
        assert sel.template_id == ""          # never a substitute
        # 2A-9E: candidates come from the NEW-selection chooser — STE/RTE
        # recommend the corrected 1.2 and offer 1.1 as advanced legacy;
        # a generic/auto-bottom version is never offered.
        classes = {c["key"]: c["new_selection_class"]
                   for c in sel.candidates}
        assert classes["straight_tuck_end_carton/1.2"] == \
            "RECOMMENDED_CORRECTED_VERSION"
        assert classes["straight_tuck_end_carton/1.1"] == \
            "LEGACY_REPRODUCTION_ONLY"

    def test_generic_requires_explicit_acceptance(self):
        assert self._select().resolved is False
        accepted = self._select(generic_accepted=True)
        assert accepted.resolved and accepted.source == "GENERIC_FALLBACK_ACCEPTED"
        assert accepted.template_id == "straight_tuck_end_carton"

    def test_structural_reference_blocks_generic_acceptance(self):
        """Evidence outranks acceptance: a customer die exists, so a generic
        structure cannot be accepted over it."""
        sel = self._select(
            task=self._task(self._product_with_association(
                "skynte_foundation_tuck_carton")),
            generic_accepted=True)
        assert sel.resolved and sel.source == "PRODUCT_TEMPLATE_ASSOCIATION"

    def test_unregistered_association_never_substitutes(self):
        sel = self._select(task=self._task(
            self._product_with_association("legacy_unknown_carton")))
        assert sel.resolved is False
        assert sel.code == "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"
        assert any("unregistered" in r or "unknown" in r for r in sel.reasons)

    def test_out_of_range_dimensions_downgrade_to_confirmation(self):
        sel = self._select(user_template="skynte_foundation_tuck_carton",
                           dimensions={"width_mm": 42, "depth_mm": 32,
                                       "height_mm": 4000})
        assert sel.resolved is False
        assert sel.code == "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"
