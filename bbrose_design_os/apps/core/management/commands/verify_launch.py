from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Verify the system is ready for daily operation'

    def handle(self, *args, **options):
        checks = []

        def ok(label):
            checks.append(('✓', label))
            self.stdout.write(self.style.SUCCESS(f'  ✓ {label}'))

        def fail(label, detail=''):
            checks.append(('✗', label))
            self.stdout.write(self.style.ERROR(f'  ✗ {label}{" — " + detail if detail else ""}'))

        self.stdout.write('\n=== BBROSE Design OS — Launch Verification ===\n')

        # Environment
        self.stdout.write('ENVIRONMENT:')
        for key in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'DATABASE_URL', 'REDIS_URL']:
            if key == 'DATABASE_URL':
                # DATABASE_URL is consumed into settings.DATABASES via env.db(),
                # not stored as a settings attribute — verify the parsed config.
                db = settings.DATABASES.get('default', {})
                ok('DATABASE_URL configured') if db.get('NAME') else fail('DATABASE_URL missing')
            elif hasattr(settings, key):
                ok(f'{key} set') if getattr(settings, key, '') else fail(f'{key} missing')
            else:
                fail(f'{key} not in settings')

        if settings.DEBUG:
            fail('DEBUG=False', 'Set DEBUG=False for production')
        else:
            ok('DEBUG=False')

        # Database
        self.stdout.write('\nDATABASE:')
        try:
            from apps.core.models import Brand, Product, ColorSystem
            brand = Brand.objects.first()
            if brand:
                ok(f'Brand seeded: {brand.name}')
                pc = Product.objects.filter(brand=brand).count()
                ok(f'{pc} products in catalog') if pc > 0 else fail('No products — run import_products')
                cs = ColorSystem.objects.filter(brand=brand, status='canonical').count()
                ok(f'{cs} canonical color systems') if cs > 0 else fail('No color systems — run seed_bbrose')
            else:
                fail('No brand found — run seed_bbrose')
        except Exception as e:
            fail(f'Database error: {e}')

        # Redis / Celery
        self.stdout.write('\nCELERY / REDIS:')
        try:
            import redis
            r = redis.from_url(settings.CELERY_BROKER_URL)
            r.ping()
            ok('Redis reachable')
        except Exception as e:
            fail(f'Redis not reachable: {e}')

        # Pipeline
        self.stdout.write('\nPIPELINE:')
        try:
            from apps.pipeline.models import DesignTask
            completed = DesignTask.objects.filter(status='completed').count()
            ok(f'{completed} completed tasks in database')
        except Exception as e:
            fail(f'Pipeline models error: {e}')

        # Media storage
        self.stdout.write('\nMEDIA:')
        import os
        media_root = settings.MEDIA_ROOT
        if os.path.isdir(media_root):
            ok(f'MEDIA_ROOT exists: {media_root}')
        else:
            try:
                os.makedirs(media_root, exist_ok=True)
                ok(f'MEDIA_ROOT created: {media_root}')
            except Exception as e:
                fail(f'Cannot create MEDIA_ROOT: {e}')

        # Summary
        total = len(checks)
        passed = sum(1 for c in checks if c[0] == '✓')
        failed = total - passed
        self.stdout.write(f'\n=== {passed}/{total} checks passed ===')

        if failed == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ System is ready for daily operation.\n'))
        else:
            self.stdout.write(self.style.ERROR(f'\n✗ {failed} issue(s) must be resolved before launch.\n'))
