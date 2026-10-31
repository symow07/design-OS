"""Seed a clickable dieline-pipeline demo.

Creates a Product with real straight-tuck-end carton dimensions (Scenario A —
no AI/API key needed) and a DesignTask parked at Gate 1 with three placeholder
design variations, so you can click the full flow in the dashboard:

    Gate 1 (approve a design)
      -> Confirm Dimensions gate (pre-filled from the product record)
      -> generated dieline SVG at Gate 2
      -> Approve Final -> Completed (download SVG + spec PDF)

Usage:
    python manage.py seed_dieline_demo

Requires a Brand to exist first (run `python manage.py seed_bbrose`).
"""
import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignTask, GeneratedImage

DEMO_PREFIX = "[DEMO]"

_VARIATIONS = [
    ("Midnight Botanical", (26, 26, 26), (181, 137, 90), 9),
    ("Blush Minimal", (242, 196, 206), (90, 60, 70), 8),
    ("Cream Heritage", (245, 237, 214), (140, 110, 70), 7),
]


class Command(BaseCommand):
    help = "Seed a clickable dieline pipeline demo (product + Gate 1 task)."

    def handle(self, *args, **options):
        brand = Brand.objects.first()
        if not brand:
            raise CommandError("No Brand found. Run `python manage.py seed_bbrose` first.")

        product, _ = Product.objects.get_or_create(
            product_id="BBR-SK-100",
            defaults=dict(brand=brand, name="Velvet Bloom Serum Carton",
                          category="SK", year=2026),
        )
        product.brand = brand
        product.name = "Velvet Bloom Serum Carton"
        product.product_type = "carton"
        product.width_mm = 35
        product.depth_mm = 35
        product.height_mm = 100
        product.dimensions = "35 x 35 x 100 mm (W x D x H)"
        product.finish_notes = "Soft-touch matte laminate, gold foil logo"
        product.save()

        # Idempotent: clear any previous demo tasks.
        DesignTask.objects.filter(task_text__startswith=DEMO_PREFIX).delete()

        task = DesignTask.objects.create(
            brand=brand, product=product, status="awaiting_gate_1",
            task_text=f"{DEMO_PREFIX} Luxury serum carton — soft matte black with gold foil botanical motif",
        )

        for n, (name, bg, fg, score) in enumerate(_VARIATIONS, start=1):
            image = GeneratedImage(
                task=task, direction_name=name, prompt_used="demo placeholder",
                image_url="", variation_number=n, qa_passed=score >= 7,
                qa_notes='{"score": %d, "recommendation": "approve", "issues": []}' % score,
            )
            image.image_file.save(
                f"demo_task_{task.id}_v{n}.png",
                ContentFile(self._placeholder_png(name, bg, fg)),
                save=True,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded demo: product {product.product_id} "
            f"({product.width_mm}x{product.depth_mm}x{product.height_mm} mm), "
            f"task #{task.id} at Gate 1 with {task.images.count()} designs."
        ))
        self.stdout.write("Open the dashboard, select the [DEMO] task, and click through Gate 1.")

    @staticmethod
    def _placeholder_png(name, bg, fg):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (600, 900), bg)
        d = ImageDraw.Draw(im)
        d.rectangle([30, 30, 570, 870], outline=fg, width=3)
        d.text((60, 80), "BBROSE", fill=fg)
        d.text((60, 430), name, fill=fg)
        d.text((60, 470), "Velvet Bloom Serum", fill=fg)
        d.text((60, 820), "35 x 35 x 100 mm", fill=fg)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()
