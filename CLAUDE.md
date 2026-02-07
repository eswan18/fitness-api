# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

Fitness API is a Python backend for analyzing and aggregating fitness data from multiple sources:
- **Strava**: Outdoor runs via OAuth API integration
- **MapMyFitness**: Historical/treadmill runs via CSV upload
- **Hevy**: Weightlifting data via Hevy API integration

The frontend dashboard is a separate project and not included in this repository.

## Tech Stack

- **FastAPI** - REST API framework
- **PostgreSQL** - Database (Neon DB in production)
- **psycopg3** - Raw SQL (no ORM)
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **uv** - Package management

## Key Commands

```bash
# Install dependencies
uv sync

# Run dev server
make dev

# Run tests
make test          # Unit tests only (fast)
make e2e-test      # E2E tests with Postgres container (requires Docker)
make int-test      # Integration tests (requires Strava credentials)
make all-test      # All tests

# Code quality
make lint          # Run ruff linter
make format        # Format with ruff
make ty            # Type checking

# Database
uv run alembic upgrade head              # Run migrations
uv run alembic revision -m "message"     # Create new migration
```

## Directory Structure

```
fitness/
├── app/           # FastAPI app, routes, auth
│   └── routers/   # API endpoint handlers
├── db/            # Database layer (raw SQL queries)
├── models/        # Pydantic models
├── agg/           # Aggregation logic (metrics calculations)
├── config/        # Configuration management
├── load/          # Data loading (Strava, MMF)
├── integrations/  # External service clients (Strava, Google, Hevy)
└── utils/         # Utilities

tests/
├── app/           # API tests
├── db/            # Database tests
├── e2e/           # End-to-end tests (require Docker)
├── integrations/  # Integration tests
└── _factories/    # Test data factories
```

## Architecture Patterns

### Database Layer
- **Raw SQL via psycopg3** - No ORM, direct queries in `fitness/db/`
- **Context managers** - Connection management with automatic cleanup
- **Deterministic IDs** - Strava runs: `strava_{id}`, MMF runs: `mmf_{id}`, Shoes: normalized name

### Data Patterns
- **Soft deletion** - `deleted_at` field, records preserved for audit
- **Version tracking** - `runs_history` table tracks all edits
- **Upsert operations** - Safe re-imports without duplicates

### Authentication
- OAuth 2.0 via external identity provider
- Bearer tokens for mutation endpoints (POST/PATCH/DELETE)
- Read endpoints (GET) are public

## Environment Variables

See `.env.dev.example` for a template. 🔑 = secret, do not commit.

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` 🔑 | PostgreSQL connection string |
| `IDENTITY_PROVIDER_URL` | OAuth identity provider base URL |
| `JWT_AUDIENCE` | Expected JWT audience claim |
| `PUBLIC_API_BASE_URL` | Public URL of this API (used in OAuth redirects) |
| `PUBLIC_DASHBOARD_BASE_URL` | Public URL of the frontend dashboard |
| `TRMNL_API_KEY` 🔑 | API key for TRMNL device authentication |

### Strava integration

| Variable | Description |
|----------|-------------|
| `STRAVA_CLIENT_ID` 🔑 | Strava OAuth client ID |
| `STRAVA_CLIENT_SECRET` 🔑 | Strava OAuth client secret |
| `STRAVA_OAUTH_URL` | Strava OAuth authorize URL |
| `STRAVA_TOKEN_URL` | Strava OAuth token URL |

### Google Calendar integration (optional)

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` 🔑 | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` 🔑 | Google OAuth client secret |
| `GOOGLE_CALENDAR_ID` | Target calendar ID (defaults to `primary`) |

### Hevy integration (optional)

| Variable | Description |
|----------|-------------|
| `HEVY_API_KEY` 🔑 | Hevy API key for lifting data sync |

### Other optional

| Variable | Description |
|----------|-------------|
| `ENV` | Environment name; loads `.env.dev` or `.env.prod` (default: `dev`) |
| `LOG_LEVEL` | Logging level (default: `WARNING`) |
| `MMF_TIMEZONE` | Timezone for MapMyFitness data (default: `America/Chicago`) |

## Testing Notes

- Unit tests are fast and require no external services
- E2E tests use testcontainers (Docker) for PostgreSQL
- Integration tests require valid Strava credentials in `.env.dev`
- Test factories in `tests/_factories/` generate consistent test data
