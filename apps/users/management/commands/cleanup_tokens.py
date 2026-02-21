from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models import RefreshToken, UserSession


class Command(BaseCommand):
    help = "Clean up expired refresh tokens and inactive sessions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete tokens/sessions older than N days (default: 30)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        days = options["days"]
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        self.stdout.write(self.style.WARNING(f'{"DRY RUN: " if dry_run else ""}Cleaning up tokens and sessions...'))

        # Clean up expired refresh tokens
        expired_tokens = RefreshToken.objects.filter(expires_at__lt=timezone.now())
        expired_count = expired_tokens.count()

        if expired_count > 0:
            self.stdout.write(f"Found {expired_count} expired refresh tokens")
            if not dry_run:
                deleted_count, _ = expired_tokens.delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted_count} expired refresh tokens"))
        else:
            self.stdout.write("No expired refresh tokens found")

        # Clean up revoked tokens older than cutoff date
        old_revoked_tokens = RefreshToken.objects.filter(is_revoked=True, created_at__lt=cutoff_date)
        old_revoked_count = old_revoked_tokens.count()

        if old_revoked_count > 0:
            self.stdout.write(f"Found {old_revoked_count} old revoked refresh tokens (older than {days} days)")
            if not dry_run:
                deleted_count, _ = old_revoked_tokens.delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted_count} old revoked tokens"))
        else:
            self.stdout.write(f"No old revoked tokens found (older than {days} days)")

        # Clean up inactive sessions older than cutoff date
        old_inactive_sessions = UserSession.objects.filter(is_active=False, created_at__lt=cutoff_date)
        old_inactive_count = old_inactive_sessions.count()

        if old_inactive_count > 0:
            self.stdout.write(f"Found {old_inactive_count} old inactive sessions (older than {days} days)")
            if not dry_run:
                deleted_count, _ = old_inactive_sessions.delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted_count} old inactive sessions"))
        else:
            self.stdout.write(f"No old inactive sessions found (older than {days} days)")

        # Summary
        total = expired_count + old_revoked_count + old_inactive_count
        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDRY RUN: Would delete {total} total records"))
            self.stdout.write("Run without --dry-run to actually delete these records")
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Cleanup complete! Processed {total} total records"))
