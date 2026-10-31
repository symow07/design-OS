"""Seed the role groups (Milestone 11.1 / audit H2). Idempotent —
safe to run on every deploy."""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.pipeline.permissions import ALL_ROLES


class Command(BaseCommand):
    help = "Create the Designer / Reviewer / Admin role groups (idempotent)."

    def handle(self, *args, **options):
        for name in ALL_ROLES:
            group, created = Group.objects.get_or_create(name=name)
            self.stdout.write(
                self.style.SUCCESS(f"Created role group: {name}")
                if created else f"Role group already exists: {name}"
            )
