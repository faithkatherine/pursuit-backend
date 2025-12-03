# Token Cleanup Documentation

## Overview

The authentication system includes automatic cleanup of expired refresh tokens and inactive user sessions to maintain database health and security.

## Manual Cleanup

You can manually run the cleanup command:

```bash
# Dry run to see what would be deleted
python manage.py cleanup_tokens --dry-run

# Actually delete expired tokens and sessions
python manage.py cleanup_tokens

# Delete tokens/sessions older than 60 days (default is 30)
python manage.py cleanup_tokens --days=60
```

### What Gets Cleaned Up

1. **Expired Refresh Tokens**: Tokens where `expires_at < now()`
2. **Old Revoked Tokens**: Revoked tokens older than N days (default: 30)
3. **Old Inactive Sessions**: Inactive sessions older than N days (default: 30)

## Automated Cleanup with Celery

The system includes a Celery Beat task that automatically runs daily at 2:00 AM UTC.

### Setup Celery Beat

1. Make sure Redis is running (Celery broker):
   ```bash
   redis-server
   ```

2. Start Celery worker:
   ```bash
   celery -A pursuit_backend worker --loglevel=info
   ```

3. Start Celery Beat (scheduler):
   ```bash
   celery -A pursuit_backend beat --loglevel=info
   ```

### Production Setup

For production, use a process manager like Supervisor or systemd:

**Example Supervisor config** (`/etc/supervisor/conf.d/celery.conf`):

```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A pursuit_backend worker --loglevel=info
directory=/path/to/pursuit-backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log

[program:celery-beat]
command=/path/to/venv/bin/celery -A pursuit_backend beat --loglevel=info
directory=/path/to/pursuit-backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/beat.log
```

### Customizing the Schedule

Edit `pursuit_backend/celery.py` to change the schedule:

```python
app.conf.beat_schedule = {
    'cleanup-expired-tokens-daily': {
        'task': 'apps.users.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=2, minute=0),  # Change time here
    },
}
```

Examples:
- Every day at 3:00 AM: `crontab(hour=3, minute=0)`
- Every 12 hours: `crontab(hour='*/12')`
- Every Sunday at midnight: `crontab(hour=0, minute=0, day_of_week=0)`

## Monitoring

The Celery task returns a dict with cleanup statistics:

```python
{
    'expired_tokens': 15,
    'old_revoked_tokens': 8,
    'old_sessions': 23,
    'total': 46
}
```

You can monitor these in your Celery logs or integrate with monitoring tools like Sentry or Datadog.

## Database Impact

The cleanup operation:
- Uses efficient bulk `DELETE` queries
- Runs during low-traffic hours (2 AM default)
- Should complete in under 1 second for most databases
- Uses database indexes on `expires_at`, `created_at`, and `is_revoked` fields

## Security Considerations

- Expired tokens are completely removed from the database
- Users cannot use deleted tokens even if they somehow retained them
- Active sessions and valid tokens are never affected
- The cleanup maintains referential integrity (cascading deletes)
