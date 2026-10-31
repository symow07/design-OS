"""Phase 2B-3V-PRE — product-container asset resolution search quality (§7).

Proves the resolver searches beyond the direct Product image fields, that an
exact SKU/name match outranks a category match and a similar lip-gloss box is
NOT treated as exact product evidence, that rights/permissions are untouched
and exact assets need human confirmation, and that no provider is called.
"""
from __future__ import annotations

import json
import shutil
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Brand, DesignReference, Product
from apps.pipeline.services import container_asset_resolver as r


def _tmp_empty_inventory(tmpdir):
    p = tmpdir / "inv.jsonl"
    p.write_text("")
    return str(p)


class AssetResolverTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="BBR-CO-410", name="Rosé Nectar Lip Gloss",
            category="CO", year=2026, product_type="lip gloss",
            width_mm=35, depth_mm=25, height_mm=95)
        # a same-family lip-gloss box (NOT the exact product)
        DesignReference.objects.create(
            name="YB-1030_LG5862", category="CO", product_type="lip gloss",
            tags=["bold typography"], summary="BBROSE lip gloss tube boxes",
            image_path="references/ref_YB-1030.png", active=True)
        # an unrelated category item
        DesignReference.objects.create(
            name="FB-2056", category="CO", product_type="face powder",
            tags=["butterfly"], summary="BBROSE face powder box", active=True)

    def _resolve(self, inv_path=None):
        with override_settings(DIP_INVENTORY_PATH=inv_path or "/no/such/inv.jsonl"):
            return r.resolve_product_assets(self.product)

    def test_searches_beyond_direct_product_image_fields(self):
        # product has no images, yet candidates are found via DesignReference
        assert not self.product.product_image
        rec = self._resolve()
        assert "DesignReference" in rec["sources_searched"]
        assert rec["same_family_or_archetype_candidates"]

    def test_no_exact_asset_yields_library_grounded(self):
        rec = self._resolve()
        assert rec["exact_asset_found"] is False
        assert rec["recommended_pilot_mode"] == r.LIBRARY_GROUNDED
        assert rec["photo_to_profile_validation"] == "NOT_APPLICABLE"
        assert rec["outcome"].startswith("NO_EXACT_PRODUCT_ASSET")

    def test_similar_lip_gloss_is_not_exact(self):
        rec = self._resolve()
        cls = {c["asset_id"]: c["classification"]
               for c in rec["same_family_or_archetype_candidates"]}
        yb = next(k for k in cls if "YB-1030" in
                  DesignReference.objects.get(pk=int(k.split(":")[1])).name)
        assert cls[yb] in (r.SAME_FAMILY, r.SAME_ARCHETYPE)   # never EXACT

    def test_exact_sku_match_outranks_category(self):
        # a reference whose text carries the exact SKU → EXACT, ranked first
        DesignReference.objects.create(
            name="RoséNectar master BBR-CO-410", category="CO",
            product_type="lip gloss", summary="BBR-CO-410 container artwork",
            image_path="references/ref_co410.png", active=True)
        rec = self._resolve()
        assert rec["exact_asset_found"] is True
        assert rec["recommended_pilot_mode"] == r.PHOTO_GROUNDED
        top = rec["exact_candidates"][0]
        assert top["classification"] in (
            r.EXACT_PACKAGING_ARTWORK, r.EXACT_CONTAINER_IMAGE)
        assert "bbr-co-410" in top["matched_terms"]

    def test_exact_requires_confirmation_and_no_auto_evidence(self):
        DesignReference.objects.create(
            name="BBR-CO-410 exact", category="CO", product_type="lip gloss",
            summary="BBR-CO-410", image_path="r.png", active=True)
        rec = self._resolve()
        assert rec["requires_human_confirmation"] is True
        # an unconfirmed exact candidate may not yet be product evidence
        top = rec["exact_candidates"][0]
        assert top["permitted_use"]["product_evidence"] is False
        assert top["permitted_use"]["production_artwork"] is False

    def test_rights_and_permission_state_unchanged(self):
        rec = self._resolve()
        for c in rec["same_family_or_archetype_candidates"]:
            assert c["permission_state"] == "CANDIDATE"
            assert c["rights_status"] in ("RIGHTS_UNREVIEWED", "UNVERIFIED")

    def test_inventory_ai_preview_can_become_candidate(self, ):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        inv = d / "inv.jsonl"
        inv.write_text(json.dumps({
            "relative_path": "materials/bbrose lip gloss tube master.ai",
            "extension": ".ai", "category": {"value": "REUSABLE_VECTOR_ASSET"},
            "sha256": "deadbeef"}) + "\n")
        rec = self._resolve(str(inv))
        inv_cands = [c for group in ("same_family_or_archetype_candidates",
                                     "category_or_decorative_candidates")
                     for c in rec[group] if c["source_type"] == "DIP_INVENTORY"]
        assert inv_cands and inv_cands[0]["filename"].endswith(".ai")

    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_no_provider_call(self, mock_claude):
        self._resolve()
        mock_claude.assert_not_called()

    def test_resolution_hash_deterministic(self):
        assert self._resolve()["resolution_hash"] == self._resolve()["resolution_hash"]

    def test_a_slim_product_resolves_as_its_own_form(self):
        """§BH70(1): the tube's word list held "mascara" and "liner", so a mascara and an eyeliner resolved as a
        squeeze tube, and a lipstick resolved as nothing. Each resolves as its own form; a gloss is still a tube and a
        palette is still a compact."""
        from types import SimpleNamespace
        cases = {"lipstick": "lipstick", "mascara": "mascara", "liquid eyeliner": "mascara", "eyeliner": "pencil",
                 "eye pencil": "pencil", "lip liner": "pencil", "lip gloss": "tube", "gloss palette": "compact",
                 "serum bottle": "bottle", "lip balm": "jar"}
        for ptype, form in cases.items():
            assert r._archetype_of(SimpleNamespace(product_type=ptype, name="")) == form, (ptype, form)
