"""
Management command to create a superuser from environment variables.

Used on platforms like Render (free plan) where there's no shell access.
Set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD in the
Render environment variables to use this.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a superuser from DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD env vars'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not email or not password:
            self.stdout.write(self.style.NOTICE(
                'DJANGO_SUPERUSER_EMAIL and/or DJANGO_SUPERUSER_PASSWORD not set — skipping.'
            ))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{email}" already exists — skipping.'
            ))
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(
            f'Superuser "{email}" created successfully.'
        ))
