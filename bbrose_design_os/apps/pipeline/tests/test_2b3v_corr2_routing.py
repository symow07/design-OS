"""Phase 2B-3V-CORR-2 — per-variation visual-reference routing.

CORR-1 fixed WHICH files may reach the provider (approved-only). CORR-2 fixes
that each variation's images.edit call receives EXACTLY its assigned approved
subset — not the union of every approved file. These tests pin:

  §2  the resolver returns exactly the assigned subset for a variation;
  §4  pre-spend enforces passed == opened == assigned ⊆ approved (expansion,
      reduction, unapproved, missing, plan-mismatch all fail → zero calls);
  §5  assigned / opened / passed persist as DISTINCT provenance fields;
  §3  three variations may carry three different subsets;
  §7  a one-reference task keeps the named contract; a zero-reference task
      stays structured and never falls back to house visuals.

No test makes a real provider call.
"""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import base64
import copy
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Brand, DesignReference, Product
from apps.pipeline.models import (
    ConceptInfluencePlan,
    ConceptReference,
    CreativeBrief,
    DesignTask,
    GeneratedImage,
)


def _b64_response():
    data = MagicMock()
    data.url = None
    data.b64_json = base64.b64encode(b"png").decode()
    resp = MagicMock()
    resp.data = [data]
    resp._request_id, resp.id = "req", "op"
    return resp


def _claude(payload):
    import json
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=5, output_tokens=5)
    resp.id, resp._request_id = "m", "r"
    return resp


class _Mixin(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rosé Nectar",
            category="CO", year=2026, product_type="lip gloss")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="lip gloss",
            status="running", design_target="product_container")

    def _approve(self, count):
        rows = []
        for i in range(count):
            (Path(self.media) / f"c{i}.png").write_bytes(b"\x89PNG")
            rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:{i}", title=f"ref{i}",
                image_root="media", image_path=f"c{i}.png",
                permission_status=ConceptReference.PERMISSION_APPROVED))
        plan = {"schema_version": "material_influence_plan/1.0",
                "references": [{"reference_id": r.pk} for r in rows]}
        ConceptInfluencePlan.objects.create(
            task=self.task, schema_version="material_influence_plan/1.0",
            plan=plan, plan_hash="ph")
        return rows

    def _bundle(self):
        from apps.pipeline.services.visual_reference_resolver import (
            resolve_visual_references)
        return resolve_visual_references(self.task)


# --- §2 resolver subset -----------------------------------------------------

class ResolverSubsetTests(_Mixin):
    def test_provider_files_for_returns_exactly_the_assigned_subset(self):
        rows = self._approve(3)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            files, has_logo, opened = b.provider_files_for([rows[0].pk, rows[2].pk])
        assert opened == [rows[0].pk, rows[2].pk]
        assert {Path(f).name for f in files} == {"c0.png", "c2.png"}

    def test_provider_files_for_never_expands_to_full_set(self):
        rows = self._approve(3)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            _, _, opened = b.provider_files_for([rows[1].pk])
        assert opened == [rows[1].pk]              # not all three


# --- §4 exact-set pre-spend -------------------------------------------------

class VariationPreSpendTests(_Mixin):
    def _validate(self, bundle, assigned, opened, passed, plan_hash=None):
        from apps.pipeline.services.provider_prespend import (
            validate_variation_prespend)
        return validate_variation_prespend(
            self.task, bundle, variation_id="A_PETAL_WINDOW",
            assigned_ids=assigned, opened_ids=opened, passed_ids=passed,
            expected_plan_hash=plan_hash)

    def test_exact_match_passes(self):
        rows = self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            res = self._validate(b, [rows[0].pk], [rows[0].pk], [rows[0].pk])
        assert res.ok and res.codes == []
        assert res.detail["assigned_reference_ids"] == [rows[0].pk]

    def test_expansion_fails(self):
        rows = self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            res = self._validate(b, [rows[0].pk],
                                 [rows[0].pk, rows[1].pk], [rows[0].pk, rows[1].pk])
        assert not res.ok
        assert any("VARIATION_REFERENCE_SET_EXPANDED" in c for c in res.codes)

    def test_reduction_fails(self):
        rows = self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            res = self._validate(b, [rows[0].pk, rows[1].pk], [rows[0].pk],
                                 [rows[0].pk])
        assert not res.ok
        assert any("VARIATION_REFERENCE_SET_REDUCED" in c for c in res.codes)

    def test_unapproved_assigned_fails(self):
        rows = self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            res = self._validate(b, [rows[0].pk, 9999], [rows[0].pk], [rows[0].pk])
        assert not res.ok
        assert any("VARIATION_REFERENCE_NOT_APPROVED" in c for c in res.codes)

    def test_missing_assigned_file_fails(self):
        rows = self._approve(2)
        (Path(self.media) / "c1.png").unlink()      # approved but file gone
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            res = self._validate(b, [rows[0].pk, rows[1].pk], [rows[0].pk],
                                 [rows[0].pk])
        assert not res.ok
        assert any("VARIATION_REFERENCE_FILE_MISSING" in c for c in res.codes)

    def test_plan_hash_mismatch_fails(self):
        rows = self._approve(1)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            b = self._bundle()
            res = self._validate(b, [rows[0].pk], [rows[0].pk], [rows[0].pk],
                                 plan_hash="different")
        assert not res.ok
        assert any("VARIATION_REFERENCE_PLAN_MISMATCH" in c for c in res.codes)


# --- §3/§5 end-to-end routing through the container render ------------------

def _payload(subsets, plan_hash, ids, no_refs=False):
    from apps.pipeline.services import container_gate1 as cg1
    base = {
        "typography_signature": "serif", "composition_signature": "column",
        "motif_signature": "petals", "cap_body_signature": "rose-gold cap",
        "decoration_zone_signature": "window", "color_field_signature": "blush",
        "finish_signature": "spot-uv",
        "native_reconstruction_plan": "live type + Bézier petals + gradients",
        "prompt": ("a tall slim lip-gloss tube with a rose-gold dome cap on a "
                   "blush studio surface, its native-vector petal-window design "
                   "built from live serif typography, translucent vector "
                   "gradient fields, closed Bézier petal droplets and precise "
                   "spot-UV finish masks, photographed as a luxury beauty "
                   "concept packshot with shallow depth of field and warm key "
                   "light rfrom the upper right, award-winning packaging craft")}
    variations = []
    for n, vid in enumerate(cg1.CONTAINER_VARIATION_IDENTITIES):
        v = copy.deepcopy(base)
        v["variation_id"] = vid
        v["title"] = vid
        for f in cg1.CONTAINER_DIVERSITY_FIELDS:
            v[f] = f"{v[f]} {n}"                 # 7-axis distinct
        if not no_refs:
            v["reference_ids"] = subsets[n]
        variations.append(v)
    return {"schema_version": cg1.CONTAINER_GATE1_SCHEMA,
            "approved_reference_ids": sorted(ids),
            "influence_plan_hash": plan_hash, "variations": variations}


class PerVariationRenderTests(_Mixin):
    def _brief(self):
        return CreativeBrief.objects.create(
            task=self.task,
            design_intent={"schema_version": "structured_director/2.3"},
            directions=[{"direction_id": "d1", "name": "Liquid Petal Veil"}],
            selected_direction_id="d1")

    def _run(self, payload, edit_mock=True):
        from apps.pipeline.agents.aria import ARIAAgent
        self._brief()
        with patch("apps.pipeline.agents.creative_director.call_claude") as cd, \
                patch("apps.pipeline.services.claude_service.call_claude",
                      return_value=_claude(payload)), \
                patch("apps.pipeline.agents.image_producer.openai.images.edit",
                      return_value=_b64_response()) as edit, \
                patch("apps.pipeline.agents.image_producer.openai.images.generate",
                      return_value=_b64_response()) as gen, \
                patch("apps.pipeline.agents.qa_reviewer.call_claude",
                      return_value=_claude(critique(8))):
            with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL="gpt-image-1",
                                   BRAND_LOGO_PATH="", MAX_REVISION_PASSES=0):
                ARIAAgent(self.task.pk)._render_variations(
                    {"direction_id": "d1", "name": "Liquid Petal Veil"})
        return cd, edit, gen

    def test_three_variations_carry_three_different_subsets(self):
        rows = self._approve(3)
        ids = [r.pk for r in rows]
        subsets = [[ids[0]], [ids[1]], [ids[0], ids[2]]]
        cd, edit, gen = self._run(_payload(subsets, "ph", ids))
        cd.assert_not_called()
        gen.assert_not_called()
        images = {i.reference_provenance["variation_identity"]: i
                  for i in GeneratedImage.objects.filter(task=self.task)}
        assert len(images) == 3
        want = {"A_PETAL_WINDOW": [ids[0]], "B_LIQUID_VEIL": [ids[1]],
                "C_DEWDROP_CONSTELLATION": sorted([ids[0], ids[2]])}
        for vid, exp in want.items():
            prov = images[vid].reference_provenance
            # §5: assigned / opened / passed all EXACT and DISTINCT fields
            assert sorted(prov["assigned_reference_ids"]) == sorted(exp)
            assert sorted(prov["passed_reference_ids"]) == sorted(exp)
            assert sorted(prov["opened_reference_ids"]) == sorted(exp)
            assert prov["approved_reference_ids"] == ids
            # never the full union unless the subset IS the full set
            assert sorted(prov["concept_reference_ids"]) == sorted(exp)

    def test_one_reference_task_keeps_named_contract(self):
        rows = self._approve(1)
        cd, edit, gen = self._run(
            _payload([[rows[0].pk]] * 3, "ph", [rows[0].pk]))
        from apps.pipeline.services import container_gate1 as cg1
        ids = {i.reference_provenance["variation_identity"]
               for i in GeneratedImage.objects.filter(task=self.task)}
        assert ids == set(cg1.CONTAINER_VARIATION_IDENTITIES)   # not generic
        for i in GeneratedImage.objects.filter(task=self.task):
            assert i.reference_provenance["assigned_reference_ids"] == [rows[0].pk]

    def test_zero_reference_task_stays_structured_never_house(self):
        # §7: no approved refs → structured A/B/C contract, no visual grounding,
        # never a house reference, never generic variation_N.
        self._house_ref = DesignReference.objects.create(
            name="YB-1039", image_path="h.png", category="CO",
            product_type="lip gloss", tags=["g"], summary="house")
        (Path(self.media) / "h.png").write_bytes(b"\x89PNG")
        cd, edit, gen = self._run(_payload(None, "", [], no_refs=True))
        from apps.pipeline.services import container_gate1 as cg1
        imgs = GeneratedImage.objects.filter(task=self.task)
        assert imgs.count() == 3
        assert {i.reference_provenance["variation_identity"] for i in imgs} == \
            set(cg1.CONTAINER_VARIATION_IDENTITIES)
        for i in imgs:
            files = i.reference_provenance["visual_files_passed"]
            assert not any("h.png" in f for f in files)   # no house visual
        edit.assert_not_called()                  # no concept files → generate
        gen.assert_called()
