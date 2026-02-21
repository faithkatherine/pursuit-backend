from celery import shared_task
from django.utils import timezone

from apps.users.models import RefreshToken, UserSession


@shared_task
def cleanup_expired_tokens():
    """
    Celery task to clean up expired refresh tokens and old inactive sessions.
    Run this task periodically (e.g., daily) via Celery Beat.
    """
    now = timezone.now()
    cutoff_date = now - timezone.timedelta(days=30)

    # Delete expired refresh tokens
    expired_tokens_count, _ = RefreshToken.objects.filter(
        expires_at__lt=now
    ).delete()

    # Delete old revoked tokens (older than 30 days)
    old_revoked_count, _ = RefreshToken.objects.filter(
        is_revoked=True,
        created_at__lt=cutoff_date
    ).delete()

    # Delete old inactive sessions (older than 30 days)
    old_sessions_count, _ = UserSession.objects.filter(
        is_active=False,
        created_at__lt=cutoff_date
    ).delete()

    total_deleted = expired_tokens_count + old_revoked_count + old_sessions_count

    return {
        'expired_tokens': expired_tokens_count,
        'old_revoked_tokens': old_revoked_count,
        'old_sessions': old_sessions_count,
        'total': total_deleted
    }
