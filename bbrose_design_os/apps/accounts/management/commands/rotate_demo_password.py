"""Rotate the demo/admin password (Milestone 8.4 / audit C6).

Usage:
    manage.py rotate_demo_password                     # rotate 'admin', print a generated password
    manage.py rotate_demo_password --password <value>  # set a supplied value
    manage.py rotate_demo_password --username <user>   # target another account
"""
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Reset a user's password (default: 'admin'). Prints a securely "
        "generated password when none is supplied."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin",
                            help="Account to rotate (default: admin).")
        parser.add_argument("--password", default=None,
                            help="New password; generated when omitted.")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist:
            raise CommandError(f"User {options['username']!r} does not exist.")

        password = options["password"] or secrets.token_urlsafe(16)
        user.set_password(password)
        user.save(update_fields=["password"])

        if options["password"]:
            self.stdout.write(self.style.SUCCESS(
                f"Password updated for {user.username!r}."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Password for {user.username!r} rotated to: {password}"
            ))
        self.stdout.write(
            "Give the new password to whoever signs in with this account."
        )
