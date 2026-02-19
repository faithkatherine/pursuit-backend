# Environment Variables

All environment variables used by the Pursuit backend, organized by category.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your values
python manage.py runserver
```

## Environment Switching

The active settings module is controlled by `DJANGO_SETTINGS_MODULE`:

| Value | Used by |
|---|---|
| `pursuit_backend.settings.development` | `manage.py` default (local dev) |
| `pursuit_backend.settings.staging` | Set explicitly for staging deploys |
| `pursuit_backend.settings.production` | `wsgi.py`/`asgi.py` default (gunicorn) |

Override in your shell:
```bash
DJANGO_SETTINGS_MODULE=pursuit_backend.settings.staging python manage.py check
```

## Variables Reference

### Django Core

| Variable | Required | Default | Stages | Description |
|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | No | `*.development` (manage.py) / `*.production` (wsgi) | All | Which settings module to load |
| `SECRET_KEY` | **Prod/Staging** | `django-insecure-change-me-in-production` | All | Django cryptographic signing key. Production fails if left as default. |
| `ALLOWED_HOSTS` | **Prod/Staging** | `localhost,127.0.0.1,0.0.0.0,10.0.2.2` | All | Comma-separated hostnames. Development allows all (`*`). |

### Database (PostgreSQL + PostGIS)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **Prod/Staging** | — | Full connection URI (e.g. `postgres://user:pass@host:5432/dbname`). Auto-provided by Render. When set, takes precedence over the individual `DB_*` variables below. |
| `DB_NAME` | No | `pursuit_db` | Database name (ignored when `DATABASE_URL` is set) |
| `DB_USER` | No | `pursuit_user` | Database user (ignored when `DATABASE_URL` is set) |
| `DB_PASSWORD` | **Prod** | `pursuit_password` | Database password. Production fails if left as default (ignored when `DATABASE_URL` is set). |
| `DB_HOST` | No | `localhost` | Database host (ignored when `DATABASE_URL` is set) |
| `DB_PORT` | No | `5432` | Database port (ignored when `DATABASE_URL` is set) |

### JWT Authentication

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | **Prod/Staging** | Empty | Key for signing JWTs. In development, falls back to `SECRET_KEY`. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |

### Google OAuth

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | No | Empty | Google OAuth web client ID |
| `GOOGLE_CLIENT_SECRET` | No | Empty | Google OAuth web client secret |
| `GOOGLE_ANDROID_CLIENT_ID` | No | Empty | Google OAuth Android client ID |
| `GOOGLE_IOS_CLIENT_ID` | No | Empty | Google OAuth iOS client ID |

### Redis / Cache

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_URL` | No | `redis://127.0.0.1:6379/1` | Redis connection URL for Django cache |

### Celery (Task Queue)

| Variable | Required | Default | Description |
|---|---|---|---|
| `CELERY_BROKER_URL` | No | `redis://127.0.0.1:6379/0` | Message broker URL |
| `CELERY_RESULT_BACKEND` | No | `redis://127.0.0.1:6379/0` | Result backend URL |

### Email

| Variable | Required | Default | Description |
|---|---|---|---|
| `EMAIL_HOST` | No | `smtp.gmail.com` | SMTP host |
| `EMAIL_PORT` | No | `587` | SMTP port |
| `EMAIL_USE_TLS` | No | `True` | Enable TLS |
| `EMAIL_HOST_USER` | No | Empty | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | Empty | SMTP password / app password |
| `DEFAULT_FROM_EMAIL` | No | `noreply@pursuit.com` | Default sender address |

Note: In development, all emails are printed to the console regardless of these settings.

### CORS (Staging/Production)

| Variable | Required | Default | Description |
|---|---|---|---|
| `CORS_ALLOWED_ORIGINS` | **Prod/Staging** | Empty | Comma-separated allowed origins (e.g., `https://app.pursuit.com,https://www.pursuit.com`) |

## GitHub Secrets for CI/CD

When deploying, configure these secrets in your GitHub repository (Settings > Secrets and variables > Actions):

| Secret | Used in | Description |
|---|---|---|
| `SECRET_KEY` | Staging/Production deploy | Django secret key |
| `JWT_SECRET_KEY` | Staging/Production deploy | JWT signing key |
| `DB_PASSWORD` | Staging/Production deploy | Database password |
| `ALLOWED_HOSTS` | Staging/Production deploy | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | Staging/Production deploy | Comma-separated origins |

CI tests use hardcoded non-sensitive values and do not require GitHub Secrets.

## Production Startup Validation

The production settings module validates on startup that:

1. `SECRET_KEY` is not the insecure default
2. `JWT_SECRET_KEY` is set
3. `ALLOWED_HOSTS` is not empty
4. `DB_PASSWORD` is not the insecure default (skipped when `DATABASE_URL` is set)

If any check fails, Django will refuse to start with a clear error message listing all missing/invalid variables.
