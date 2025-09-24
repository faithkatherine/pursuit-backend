#!/bin/bash

# Django Pursuit Backend Setup Script
# This script sets up the Django backend for development

echo "🚀 Setting up Pursuit Django Backend..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9+ and try again."
    exit 1
fi

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL not found. Please install PostgreSQL and create a database."
    echo "   You can also use SQLite for development by modifying settings.py"
fi

# Check if Redis is installed
if ! command -v redis-cli &> /dev/null; then
    echo "⚠️  Redis not found. Please install Redis for caching and task queue."
    echo "   On macOS: brew install redis"
    echo "   On Ubuntu: sudo apt-get install redis-server"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration!"
fi

# Database operations
echo "🗃️  Setting up database..."

# Check if we can connect to PostgreSQL
if command -v psql &> /dev/null; then
    echo "🔗 Checking database connection..."
    
    # Try to create database (this might fail if it already exists, which is fine)
    createdb pursuit_db 2>/dev/null || echo "Database might already exist, continuing..."
    
    # Run migrations
    echo "📊 Running database migrations..."
    python manage.py migrate
    
    # Load initial data
    echo "📋 Loading initial data..."
    python manage.py load_initial_data
else
    echo "⚠️  Skipping database setup - PostgreSQL not found"
    echo "   You can modify settings.py to use SQLite for development"
fi

# Create superuser (optional)
echo "👤 Creating superuser (optional)..."
echo "Press Ctrl+C to skip superuser creation"
python manage.py createsuperuser || echo "Skipped superuser creation"

echo ""
echo "✅ Setup complete!"
echo ""
echo "🏃 To start the development server:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver"
echo ""
echo "📖 Access the API at:"
echo "   REST API: http://127.0.0.1:8000/api/"
echo "   GraphQL: http://127.0.0.1:8000/graphql/"
echo "   Admin: http://127.0.0.1:8000/admin/"
echo ""
echo "📝 Don't forget to:"
echo "   1. Edit .env file with your configuration"
echo "   2. Set up Google OAuth credentials"
echo "   3. Configure email settings"
echo ""
echo "🎉 Happy coding!"
