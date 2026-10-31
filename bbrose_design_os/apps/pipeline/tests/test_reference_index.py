"""Product-aware reference selection (2026-07-06)."""
from __future__ import annotations

from pathlib import Path

from django.test import TestCase

from apps.core.models import Brand, DesignReference, Product
from apps.pipeline.services.reference_index import select_references


class SelectReferencesTests(TestCase):
    def setUp(self):
        import shutil
        import tempfile

        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.settings_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.settings_media, True)
        media = Path(self.settings_media)

        def ref(name, category, product_type, tags):
            png = media / f"{name}.png"
            png.write_bytes(b"\x89PNG fake")
            return DesignReference.objects.create(
                name=name, image_path=f"{name}.png", category=category,
                product_type=product_type, tags=tags,
                summary=f"{product_type} reference",
            )

        self.lip = ref("lip1", "CO", "lip gloss", ["gloss", "pink", "foil"])
        self.brow = ref("brow1", "CO", "eyebrow powder", ["eyes", "brown"])
        self.serum = ref("serum1", "SK", "serum carton", ["dew", "hydration", "droplet"])

    def _task(self, text, product=None):
        from apps.pipeline.models import DesignTask
        return DesignTask.objects.create(
            brand=self.brand, task_text=text, status="queued", product=product,
        )

    def test_skincare_task_prefers_skincare_refs(self):
        product = Product.objects.create(
            brand=self.brand, product_id="SK-1", name="Hydra Serum",
            category="SK", year=2026, product_type="serum carton")
        with self.settings(MEDIA_ROOT=self.settings_media):
            picked = select_references(self._task("hyaluronic serum box", product), 2)
        assert picked and picked[0].endswith("serum1.png")

    def test_lip_task_prefers_lip_refs(self):
        product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="Silk Lip Gloss",
            category="CO", year=2026, product_type="lip gloss")
        with self.settings(MEDIA_ROOT=self.settings_media):
            picked = select_references(self._task("new lip gloss carton", product), 1)
        assert picked and picked[0].endswith("lip1.png")

    def test_no_match_falls_back_to_newest(self):
        with self.settings(MEDIA_ROOT=self.settings_media):
            picked = select_references(self._task("mystery widget"), 2)
        assert len(picked) == 2   # newest two, never empty
