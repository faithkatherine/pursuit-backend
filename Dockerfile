FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DJANGO_SETTINGS_MODULE=pursuit_backend.settings.production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Collect static files (for production)
RUN DJANGO_SETTINGS_MODULE=pursuit_backend.settings.development \
    python manage.py collectstatic --noinput

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Wait for database\n\
if [ -n "$DATABASE_URL" ]; then\n\
  echo "Using DATABASE_URL — managed database, skipping pg_isready."\n\
else\n\
  _db_host=${DB_HOST:-localhost}\n\
  _db_port=${DB_PORT:-5432}\n\
  echo "Waiting for database at $_db_host:$_db_port..."\n\
  while ! pg_isready -h "$_db_host" -p "$_db_port" -q 2>/dev/null; do\n\
    sleep 1\n\
  done\n\
fi\n\
\n\
# Run migrations\n\
echo "Running migrations..."\n\
python manage.py migrate --noinput\n\
\n\
# Load initial data\n\
python manage.py load_initial_data\n\
\n\
# Start server\n\
exec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "pursuit_backend.wsgi:application"]
