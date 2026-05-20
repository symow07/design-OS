import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Product


class Command(BaseCommand):
    help = 'Match PNG files to products by product_id in filename'

    def add_arguments(self, parser):
        parser.add_argument('--folder', required=True)
        parser.add_argument('--brand_id', required=True, type=int)
        parser.add_argument(
            '--field',
            default='product_image',
            choices=['product_image', 'packaging_image'],
        )

    def handle(self, *args, **options):
        folder = options['folder']
        field = options['field']

        if not os.path.isdir(folder):
            raise CommandError(f'Folder not found: {folder}')

        matched, unmatched = 0, []
        png_files = [f for f in os.listdir(folder) if f.lower().endswith('.png')]

        for filename in png_files:
            # Expect filename like BBR-CO-042.png or BBR-CO-042_packaging.png
            product_id = filename.split('_')[0].replace('.png', '').strip()
            try:
                product = Product.objects.get(
                    product_id=product_id, brand_id=options['brand_id']
                )
                filepath = os.path.join(folder, filename)
                with open(filepath, 'rb') as f:
                    getattr(product, field).save(filename, File(f), save=True)
                matched += 1
            except Product.DoesNotExist:
                unmatched.append(f'{filename} → no product with ID {product_id}')

        self.stdout.write(self.style.SUCCESS(f'Matched and saved: {matched}'))
        if unmatched:
            self.stdout.write(self.style.WARNING('Unmatched files:'))
            for u in unmatched:
                self.stdout.write(f'  {u}')
