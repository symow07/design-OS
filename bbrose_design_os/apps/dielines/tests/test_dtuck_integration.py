"""2A-9D commit 4 — registry/UI integration WITHOUT a default switch.

Pins: STE/RTE resolve to 1.1 (unpinned); 1.2 is reachable only by explicit
version; template selection never auto-prefers 1.2; the qualify_dimensions
endpoint qualifies 1.1 by default and 1.2 only when explicitly requested;
auto-bottom has no adapter.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines import registry
from apps.dielines.qualification.runner import adapter_for, registered_adapters


class DefaultUnchangedTests(TestCase):
    def test_current_version_is_still_1v1(self):
        assert registry.resolve("straight_tuck_end_carton").version == "1.1"
        assert registry.resolve("reverse_tuck_end_carton").version == "1.1"

    def test_1v2_reachable_only_by_explicit_pin(self):
        assert registry.resolve("straight_tuck_end_carton", "1.2").version \
            == "1.2"
        assert registry.resolve("reverse_tuck_end_carton", "1.2").version \
            == "1.2"

    def test_1v2_is_not_production_eligible(self):
        for tid in ("straight_tuck_end_carton", "reverse_tuck_end_carton"):
            defn = registry.resolve(tid, "1.2")
            assert defn.production_ready is False
            assert defn.ineligibility_code == \
                "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"

    def test_adapter_registry_has_both_versions(self):
        adapters = registered_adapters()
        assert "straight_tuck_end_carton" in adapters
        assert "straight_tuck_end_carton@1.2" in adapters
        assert "reverse_tuck_end_carton@1.2" in adapters
        assert adapter_for("tuck_top_auto_bottom_carton") is None
        assert adapter_for("tuck_top_auto_bottom_carton@1.2") is None


class SelectionNoAutoPreferTests(TestCase):
    def test_bare_user_template_requires_version_confirmation(self):
        """2A-9E changed this deliberately: a bare STE user_template no
        longer silently resolves to legacy 1.1 (that was the 2A-9D commit-4
        behavior). It now requires explicit version confirmation, with 1.2
        surfaced as the recommended correction and 1.1 as advanced legacy.
        Neither is auto-selected."""
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.services.template_selection import select_template
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x",
                                         status="awaiting_dimensions")
        dims = {"width_mm": 60, "depth_mm": 20, "height_mm": 130}
        sel = select_template(task, dimensions=dims,
                              user_template="straight_tuck_end_carton")
        assert sel.resolved is False
        assert sel.code == "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"
        classes = {c["key"]: c["new_selection_class"] for c in sel.candidates}
        assert classes["straight_tuck_end_carton/1.2"] == \
            "RECOMMENDED_CORRECTED_VERSION"
        assert classes["straight_tuck_end_carton/1.1"] == \
            "LEGACY_REPRODUCTION_ONLY"

    def test_explicit_version_confirmation_resolves(self):
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.services.template_selection import select_template
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x",
                                         status="awaiting_dimensions")
        dims = {"width_mm": 60, "depth_mm": 20, "height_mm": 130}
        # explicit 1.2 confirmation lands a 1.2 record (not resolve-default)
        sel12 = select_template(task, dimensions=dims,
                                user_template="straight_tuck_end_carton",
                                user_version="1.2")
        assert sel12.resolved is True and sel12.version == "1.2"
        # explicit legacy 1.1 still available (advanced)
        sel11 = select_template(task, dimensions=dims,
                                user_template="straight_tuck_end_carton",
                                user_version="1.1")
        assert sel11.resolved is True and sel11.version == "1.1"


class EndpointVersionTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("d9d", "d@9.com", "pw")
        g, _ = Group.objects.get_or_create(name="Reviewer")
        user.groups.add(g)
        self.client.force_login(user)

    def _q(self, body):
        return self.client.post("/api/dielines/qualify_dimensions/", body,
                                content_type="application/json").json()

    def test_default_qualifies_1v1_wide_short_rejected(self):
        r = self._q({"template": "straight_tuck_end_carton",
                     "width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0,
                     "board_thickness_mm": 0.5, "glue_tab_mm": 12.0})
        assert r["supported"] is False
        assert any("TUCK_LIP_VS_HEIGHT" in v for v in r["violations"])

    def test_explicit_1v2_qualifies_wide_short_supported(self):
        r = self._q({"template": "straight_tuck_end_carton",
                     "template_version": "1.2",
                     "width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0,
                     "board_thickness_mm": 0.5, "glue_tab_mm": 12.0})
        assert r["supported"] is True
        assert r["geometry_hash"]

    def test_explicit_1v2_rte_also_available(self):
        r = self._q({"template": "reverse_tuck_end_carton",
                     "template_version": "1.2",
                     "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
                     "board_thickness_mm": 0.5, "glue_tab_mm": 12.0})
        assert r["supported"] is True
