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

Key variables (see `.env.dev.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (optional, for calendar sync)
- `IDENTITY_PROVIDER_URL` - OAuth provider base URL

## Testing Notes

- Unit tests are fast and require no external services
- E2E tests use testcontainers (Docker) for PostgreSQL
- Integration tests require valid Strava credentials in `.env.dev`
- Test factories in `tests/_factories/` generate consistent test data
