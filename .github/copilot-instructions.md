# Pursuit Backend — AI Agent Instructions

Pursuit is a hyperlocal event discovery app for Nairobi, Kenya. This Django GraphQL API serves a React Native mobile app.

## Stack & Architecture

**Core:** Django 5 + Python 3.12, Graphene-Django (GraphQL), PostgreSQL 17 (PostGIS), Redis, Celery  
**Auth:** Custom JWT (see `apps.users.authentication.JWTService`) — NOT django-graphql-jwt  
**Deployment:** Render.com, staging auto-deploys on push to `main`

```
apps/
  core/        Category, Interest — shared abstractions
  users/       User, UserProfile (location data), auth tokens, sessions
  events/      Event, EditorsPick, UserEvents (saved events)
  insights/    getHome aggregator (no models, just queries)
  recommendations/  Recommendation engine
  itinerary/   Trip model (multi-day plans)
  buckets/     DEPRECATED — ignore tests here

tests/
  factories/   UserFactory, EventFactory, CategoryFactory (factory_boy)
  graphql/     GraphQLClient wrapper, mutation/query strings
  fixtures/    user, auth_client, anon_client (pytest fixtures)
  helpers/     assert_graphql_success, assert_graphql_error
```

## Test Architecture (NEW — follow this pattern)

**Fixtures are global** via `conftest.py` at project root with `pytest_plugins`:

- `user`, `other_user`, `user_with_location`, `user_without_location_sharing` from `tests.fixtures.auth`
- `auth_client`, `anon_client` — `GraphQLClient` wrappers with JWT auto-handling
- `category`, `active_event`, `saved_event` from `tests.fixtures.db`

**Writing tests:**

```python
from tests.graphql.client import GraphQLClient
from tests.graphql.mutations import ENABLE_LOCATION, DISABLE_LOCATION
from tests.graphql.queries import GET_HOME
from tests.helpers.assertions import assert_graphql_success, assert_graphql_error

def test_enable_location(auth_client, user):
    response = auth_client.execute(ENABLE_LOCATION, variables={...})
    data = assert_graphql_success(response, "enableLocation")
    assert data["ok"] is True
```

**Factories for test data:**

```python
from tests.factories.user_factory import UserFactory
from tests.factories.event_factory import EventFactory

user = UserFactory(email="custom@example.com")
event = EventFactory(name="Jazz Night", is_free=True, category=[cat])
```

**DO NOT** inline `User.objects.create_user()` or `execute_graphql()` helpers in test files.  
**See** `apps/users/test_location.py` for reference implementation.

## GraphQL Schema Conventions

**Mutations** return `{ok: Boolean, <entity>: Type, errors: [String]}` — see `apps.users.schema.SignIn`  
**Queries** wrapped in `{ok: Boolean, <entities>: [Type]}` — see `apps.events.schema.EventsQueries`  
**Auth required:** Use `@login_required` decorator from `graphql_jwt.decorators`

**getHome aggregator** (`apps/insights/schema.py`):

- Single query returns: greeting, weather, cityName, userLocation, recommendations, trending, EditorsPick, trips, savedEvents
- **MUST return `null`** for weather/cityName/userLocation when `user.profile.allow_location_sharing=False` OR coords are null
- Cache keys: `home:{userId}:{locationTag}:{timeFilter}:{editorPickId or 'none'}` (TTL: 15min)

## Location System (critical)

`UserProfile.location` is PostGIS Point (longitude, latitude) — **order matters**  
`location_tag_from_coords()` in `apps.events.locations` maps GPS → lowercase string: `"nairobi"`, `"mombasa"`  
Location tags are **strings**, NOT FKs to a City model

**Mutations:**

- `enableLocation` stores coords + sets `allow_location_sharing=True`
- `disableLocation` **MUST null out** `location` field + set flag to `False`

## Model Rules (non-negotiable)

1. **Migrations:** Reversible with `operations` and `reverse_operations` (approximate OK with comment explaining tradeoff)
2. **Admin:** Every new model → `admin.register()` in `admin.py`
3. **N+1 prevention:** Use `select_related()` in resolvers that traverse FKs (e.g., `Event.objects.select_related('category')`)
4. **Seeds:** Idempotent via `get_or_create()` pattern

## EditorsPick Special Handling

**Model:** `event` FK, `location_tag` (string), `active_from/until`, `curator_note` (NOT NULL), `position`  
**Rule:** EditorsPick events EXCLUDED from `recommendations` and `trending` in getHome  
**Badge:** Only show `isEditorsPick=True` when explicitly fetched via EditorsPick query

## Category System

8 fixed slugs (hardcoded, not DB-driven):  
`talks-and-ideas`, `workshops-and-classes`, `concerts-and-nightlife`, `culture-and-arts`,  
`outdoors-and-active`, `food-and-drink`, `markets-and-popups`, `travel`

## Commands & Workflows

```bash
# Migrations
python manage.py makemigrations [app]
python manage.py migrate

# Seed data (idempotent)
python manage.py seed_scenario_a    # Events only
python manage.py seed_scenario_b    # Events + upcoming Trip

# Tests (pytest)
python -m pytest apps/users/test_location.py -v
python -m pytest apps/ --ignore=apps/buckets  # Skip deprecated
python -m pytest -k "test_enable_location"    # Run specific

# Django shell with iPython
python manage.py shell_plus
```

## Hard Constraints (will break production)

- **NEVER** drop/rename model fields without migration
- **NEVER** return weather data when `allow_location_sharing=False`
- **NEVER** use raw string location matching — always normalize (`.strip().lower()`)
- **NEVER** skip `select_related()` on FK traversals in resolvers
- **ALWAYS** wrap data migrations in `atomic()` transactions
