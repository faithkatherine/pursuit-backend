# Pursuit Backend

A comprehensive Django backend with GraphQL API for the Pursuit mobile application - a travel and bucket list management platform.

## Features

- **Authentication & Authorization**
  - JWT-based authentication
  - Google OAuth2 integration
  - Username/password authentication
  - User profile management
  - Onboarding flow

- **Bucket List Management**
  - Create and organize bucket lists
  - Categorized bucket items
  - Progress tracking
  - Image uploads
  - Location-based items

- **Travel Recommendations**
  - Personalized recommendations
  - Location-based suggestions
  - Category filtering
  - User interaction tracking

- **Insights & Analytics**
  - User progress insights
  - Travel statistics
  - Weather integration
  - Goal tracking

- **GraphQL & REST APIs**
  - Comprehensive GraphQL schema
  - RESTful API endpoints
  - Real-time subscriptions ready
  - Comprehensive filtering and search

## Tech Stack

- **Backend**: Django 5.0, Django REST Framework
- **GraphQL**: Graphene-Django
- **Database**: PostgreSQL with optimized indexes
- **Authentication**: JWT with refresh tokens
- **Caching**: Redis
- **Task Queue**: Celery
- **File Storage**: Django storages (S3 ready)
- **Testing**: Pytest, Factory Boy
- **Code Quality**: Black, isort, flake8

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis 6+

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/faithkatherine/pursuit-backend.git
   cd pursuit-backend
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment setup**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Database setup**

   ```bash
   createdb pursuit_db
   python manage.py migrate
   python manage.py load_initial_data
   ```

6. **Create superuser**

   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

### Environment Variables

Create a `.env` file with the following variables:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=pursuit_db
DB_USER=pursuit_user
DB_PASSWORD=pursuit_password
DB_HOST=localhost
DB_PORT=5432

# JWT Settings
JWT_SECRET_KEY=your-jwt-secret-key
JWT_EXPIRATION_DELTA=604800
JWT_REFRESH_EXPIRATION_DELTA=2592000

# Google OAuth
GOOGLE_OAUTH2_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-google-client-secret

# Redis
REDIS_URL=redis://127.0.0.1:6379/1

# Email
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## API Endpoints

### REST API

- **Authentication**
  - `POST /api/auth/signup/` - User registration
  - `POST /api/auth/signin/` - User login
  - `POST /api/auth/google-signin/` - Google OAuth login
  - `POST /api/auth/refresh/` - Refresh JWT token
  - `POST /api/auth/signout/` - User logout

- **Buckets**
  - `GET /api/buckets/items/` - List bucket items
  - `POST /api/buckets/items/` - Create bucket item
  - `PUT /api/buckets/items/{id}/` - Update bucket item
  - `DELETE /api/buckets/items/{id}/` - Delete bucket item
  - `GET /api/buckets/categories/` - List categories

- **Recommendations**
  - `GET /api/recommendations/` - List recommendations

### GraphQL API

Access GraphQL Playground at `/graphql/`

**Queries:**

```graphql
query {
  me {
    id
    name
    email
    hasCompletedOnboarding
  }

  bucketItems {
    id
    title
    description
    amount
    completed
    category {
      name
      emoji
    }
  }

  recommendations {
    id
    title
    location
    image
    amount
  }

  home {
    greeting
    weather {
      city
      condition
      temperature
    }
    insights {
      progress {
        completed
        yearlyGoal
        percentage
      }
    }
  }
}
```

**Mutations:**

```graphql
mutation {
  signUp(
    email: "user@example.com"
    username: "username"
    firstName: "John"
    password: "securepassword"
  ) {
    user {
      id
      name
      email
    }
    accessToken
  }

  addBucketItem(
    title: "Visit Tokyo"
    description: "Explore the amazing city of Tokyo"
    estimatedCost: 2500.00
  ) {
    bucketItem {
      id
      title
      amount
    }
  }
}
```

## Database Schema

### Core Models

- **User** - Custom user model with profile fields
- **UserProfile** - Extended user information
- **Category** - Bucket item categories

### Bucket Models

- **BucketList** - User's bucket lists
- **BucketItem** - Individual bucket list items
- **BucketItemPhoto** - Additional photos for items
- **BucketItemProgress** - Progress tracking

### Recommendation Models

- **Recommendation** - Travel and activity recommendations
- **UserRecommendation** - User interaction tracking

### Insight Models

- **WeatherData** - Weather information
- **UserInsight** - User analytics and insights
- **HomeData** - Dashboard data

## Security Features

- JWT token authentication with refresh tokens
- Rate limiting on authentication endpoints
- SQL injection protection
- XSS protection
- CSRF protection
- Secure password hashing
- Login attempt tracking
- Token revocation support

## Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific test file
pytest tests/test_accounts.py

# Run with verbose output
pytest -v
```

## Code Quality

```bash
# Format code
black .
isort .

# Lint code
flake8

# Run all quality checks
pre-commit run --all-files
```

## Deployment

### Production Settings

1. Set `DEBUG=False`
2. Configure proper `ALLOWED_HOSTS`
3. Set up production database
4. Configure static/media file serving
5. Set up SSL certificates
6. Configure email backend
7. Set up monitoring and logging

### Docker Support

```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "pursuit_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For support and questions, please open an issue in the repository.
