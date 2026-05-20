import csv
import os

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Brand, ColorSystem, PackagingStructure, Product


class Command(BaseCommand):
    help = 'Import products from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to products CSV')
        parser.add_argument('--brand_id', required=True, type=int)
        parser.add_argument('--dry-run', action='store_true', help='Validate without saving')

    def handle(self, *args, **options):
        brand = Brand.objects.get(id=options['brand_id'])
        filepath = options['file']
        dry_run = options['dry_run']

        if not os.path.exists(filepath):
            raise CommandError(f'File not found: {filepath}')

        created, skipped, errors = 0, 0, []

        with open(filepath, encoding='utf-8-sig') as f:  # utf-8-sig handles Excel BOM
            reader = csv.DictReader(f)

            required_fields = {'product_id', 'name', 'category', 'year'}
            if not required_fields.issubset(set(reader.fieldnames or [])):
                raise CommandError(
                    f'CSV missing required columns. Need: {required_fields}. '
                    f'Got: {reader.fieldnames}'
                )

            for row_num, row in enumerate(reader, start=2):
                product_id = row.get('product_id', '').strip()
                if not product_id:
                    errors.append(f'Row {row_num}: empty product_id — skipped')
                    continue

                if Product.objects.filter(product_id=product_id).exists():
                    skipped += 1
                    continue

                try:
                    kwargs = {
                        'brand': brand,
                        'product_id': product_id,
                        'name': row.get('name', '').strip(),
                        'category': row.get('category', '').strip().upper()[:2],
                        'year': int(row.get('year', 2025)),
                        'status': row.get('status', 'active').strip(),
                        'dimensions': row.get('dimensions', '').strip(),
                        'finish_notes': row.get('finish_notes', '').strip(),
                        'notes': row.get('notes', '').strip(),
                    }

                    struct_id = row.get('structure_id', '').strip()
                    if struct_id:
                        try:
                            kwargs['packaging_structure'] = PackagingStructure.objects.get(
                                structure_id=struct_id
                            )
                        except PackagingStructure.DoesNotExist:
                            errors.append(
                                f'Row {row_num}: structure_id {struct_id} not found — linked as null'
                            )

                    cs_id = row.get('color_system_id', '').strip()
                    if cs_id:
                        try:
                            kwargs['color_system'] = ColorSystem.objects.get(system_id=cs_id)
                        except ColorSystem.DoesNotExist:
                            errors.append(
                                f'Row {row_num}: color_system_id {cs_id} not found — linked as null'
                            )

                    if not dry_run:
                        Product.objects.create(**kwargs)
                    created += 1

                except Exception as e:
                    errors.append(f'Row {row_num} ({product_id}): {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Created: {created} | Skipped (duplicates): {skipped} | Errors: {len(errors)}'
        ))
        if errors:
            self.stdout.write(self.style.WARNING('Errors:'))
            for err in errors:
                self.stdout.write(f'  {err}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no records saved.'))
