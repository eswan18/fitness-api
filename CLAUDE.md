# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

Fitness API is a Python backend for analyzing and aggregating fitness data from multiple sources:
- **Strava**: Outdoor runs via OAuth API integration
- **MapMyFitness**: Historical/treadmill runs via CSV upload
- **Hevy**: Weightlifting data via Hevy API integration
- **Apple Health (Health Auto Export)**: Runs and rides pushed by the HAE iOS app to `POST /ingest/hae` (decouples ingestion from Strava and captures running cadence, which Strava drops)

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

# Ingestion API tokens (per-service bearer tokens for POST /ingest/hae)
uv run fitapi-token mint --name health-auto-export   # raw token printed once
uv run fitapi-token list [--all]
uv run fitapi-token revoke --prefix fitapi_AbC123    # or --id N
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
- **Deterministic IDs** - Strava runs: `strava_{id}`, MMF runs: `mmf_{id}`, Apple Health runs/rides: `hae_{HealthKit UUID}`, Shoes: normalized name

### Apple Health ingestion (`POST /ingest/hae`)
- HAE forwards Apple Health workouts as JSON v2: `{ "data": { "workouts": [...], "metrics": [...] } }`. Timestamps are `yyyy-MM-dd HH:mm:ss Z` (space + offset, not ISO-`T`) — parse with `fitness/models/hae.py:parse_hae_timestamp`.
- Running workout names map to `runs` (`HaeRunMap` in `models/run.py`), cycling to `rides` (`HaeRideMap` in `models/ride.py`); everything else is counted as `skipped`. Both tables feed the existing TRIMP/hrTSS calc via `avg_heart_rate` + `duration`, so no calc wiring is needed.
- Idempotent: inserted with `ON CONFLICT (id) DO NOTHING` (HAE re-sends overlapping windows + retries). Re-sends never duplicate and never touch user-authored `notes`/`shoe_id`.
- `runs`/`rides` gained nullable columns `max_heart_rate`, `step_cadence` (runs only), `end_datetime_utc`, `source_name`. These are persisted on ingest but not yet surfaced by the read models (`_row_to_run`/`_row_to_ride` still select base columns) — a future enhancement.
- **No nginx/body-limit knob**: this service runs uvicorn directly behind a Cloudflare Tunnel (~100 MB cap). The issue's "raise `client_max_body_size`" task is a no-op here; if a 413 is ever seen on large GPS payloads, enable HAE "Batch Requests".

### Data Patterns
- **Soft deletion** - `deleted_at` field, records preserved for audit
- **Version tracking** - `runs_history` table tracks all edits
- **Upsert operations** - Safe re-imports without duplicates

### Authentication
- OAuth 2.0 via external identity provider
- Bearer tokens for mutation endpoints (POST/PATCH/DELETE)
- Read endpoints (GET) are public
- **Ingestion tokens** (separate system): `POST /ingest/*` endpoints use per-service bearer tokens (`fitapi_<token_urlsafe(32)>`) stored as a SHA-256 hash in the `api_tokens` table — NOT OAuth/JWT. Minted/revoked with the `fitapi-token` CLI; validated by the `require_ingest_token` dependency (`fitness/app/ingest_auth.py`). SHA-256 (not bcrypt) because the token already carries 256 bits of entropy and we need an indexed hash lookup.

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
| `OAUTH_STATE_SECRET` 🔑 | Secret for signing OAuth `state` CSRF tokens |

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
| `ENV` | Environment name: `dev`, `staging`, or `prod`. Loads `.env.{ENV}` if it exists. Default: `dev` |
| `LOG_LEVEL` | Logging level (default: `WARNING`) |
| `MMF_TIMEZONE` | Timezone for MapMyFitness data (default: `America/Chicago`) |

## Testing Notes

- Unit tests are fast and require no external services
- E2E tests use testcontainers (Docker) for PostgreSQL
- Integration tests require valid Strava credentials in `.env.dev`
- Test factories in `tests/_factories/` generate consistent test data
