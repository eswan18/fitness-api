# Fitness API – Setup & Usage

## Overview

This API aggregates and analyzes fitness data from multiple sources:
- **Strava**: Outdoor runs via OAuth API integration
- **MapMyFitness**: Historical/treadmill runs via CSV upload
- **Hevy**: Weightlifting data via the Hevy API
- **Apple Health (Health Auto Export)**: Runs and rides pushed by the HAE iOS app to `POST /ingest/hae`

The frontend dashboard is a separate project — see [fitness-dashboard](https://github.com/eswan18/fitness-dashboard).

---

## 1. Prerequisites
- Python 3.12+ (recommended: [uv](https://github.com/astral-sh/uv))
- [Make](https://www.gnu.org/software/make/) (for convenience commands)
- A PostgreSQL database (Neon in production)
- A running [identity](https://github.com/eswan18/identity) OAuth provider (for authenticating mutation endpoints)
- Optional, per integration you want: a Strava API app, a Hevy API key, Google Calendar OAuth credentials, or a MapMyFitness CSV export

---

## 2. Environment Variables

Copy `.env.dev.example` to `.env.dev` and fill in your values. The authoritative list (and which values are secret) lives in [`CLAUDE.md`](CLAUDE.md#environment-variables); the essentials:

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `IDENTITY_PROVIDER_URL` | OAuth identity provider base URL (used for network calls) |
| `JWT_ISSUER` | Expected JWT issuer (`iss`) claim — the external identity URL |
| `JWT_AUDIENCE` | Expected JWT audience claim |
| `PUBLIC_API_BASE_URL` | Public URL of this API (used in OAuth redirects) |
| `PUBLIC_DASHBOARD_BASE_URL` | Public URL of the frontend dashboard |
| `TRMNL_API_KEY` | API key for the TRMNL device endpoint |
| `OAUTH_STATE_SECRET` | Secret for signing OAuth `state` CSRF tokens |

### Optional integrations

| Variable | Description |
|----------|-------------|
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | Strava OAuth app credentials (see Strava Setup below) |
| `STRAVA_OAUTH_URL` / `STRAVA_TOKEN_URL` | Strava OAuth authorize/token URLs |
| `HEVY_API_KEY` | Hevy API key for lifting sync |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_CALENDAR_ID` | Google Calendar sync credentials (`GOOGLE_CALENDAR_ID` defaults to `primary`) |
| `MMF_TIMEZONE` | Timezone for MapMyFitness CSV timestamps (default: `America/Chicago`; can also be set per-upload) |
| `LOG_LEVEL` | Logging level (default: `WARNING`) |

> Strava and Google access/refresh tokens are **not** environment variables — they're obtained through the in-app OAuth flow and stored in the database (see below).

---

## 3. Authentication

The API uses OAuth 2.0 for authentication via an external identity provider. Authentication is required for all mutation endpoints (POST, PATCH, DELETE operations).

### Protected Endpoints
The following endpoints require OAuth Bearer tokens:
- `POST /strava/sync` — Refresh Strava data
- `POST /mmf/upload-csv` — Upload MapMyFitness CSV
- `PATCH /runs/{run_id}` — Update a run
- `PATCH /shoes/{shoe_id}` — Update shoe information
- `POST /sync/runs/{run_id}` — Sync run to Google Calendar
- `DELETE /sync/runs/{run_id}` — Remove run from Google Calendar

### Read-Only Endpoints (No Auth Required)
All GET endpoints are publicly accessible:
- `GET /runs` — Fetch runs
- `GET /metrics/*` — Fetch aggregated metrics
- `GET /shoes` — Fetch shoes
- `GET /health` — Health check

### How It Works
1. The frontend dashboard (a separate project) handles OAuth login automatically when you access protected features
2. After login, the frontend includes a Bearer token in the `Authorization` header
3. The API validates tokens by calling the identity provider's `/oauth/userinfo` endpoint
4. Tokens expire after 1 hour and are automatically refreshed by the frontend

### Manual API Access
If you need to make authenticated requests directly (e.g., via curl or scripts), you'll need to obtain an OAuth access token from the identity provider first. Contact your administrator for API credentials.

---

## 4. Strava Setup (Optional)

Strava integration uses OAuth and stores credentials in the **database** — there are no Strava token environment variables, only the client app credentials.

### Initial Setup

1. **Create a Strava API Application**:
   - Go to [Strava API Settings](https://www.strava.com/settings/api)
   - Click "Create App" and fill in the details
   - Set the "Authorization Callback Domain" to match `PUBLIC_API_BASE_URL` (e.g. `localhost` for local dev)
   - Note your Client ID and Client Secret

2. **Set Environment Variables**:
   ```env
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   ```

3. **Authorize via the OAuth flow**:
   - Visit `/oauth/strava/authorize` (or fetch the URL from `/oauth/strava/authorize-url`)
   - Authorize the app on Strava; you'll be redirected back to `/oauth/strava/callback` and tokens are stored in the database
   - Check status at `/oauth/strava/status`

### Token Management

Access and refresh tokens live in the database and are refreshed automatically at runtime. Re-authorize via `/oauth/strava/authorize` only if the tokens are revoked or expire.

---

## 5. Google Calendar Setup (Optional)

Google Calendar sync allows you to automatically create calendar events for your runs. This section covers the complete setup and ongoing maintenance of OAuth tokens.

### Initial Setup

1. **Create Google Cloud Console Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing one
   - Enable the Google Calendar API
   - Create OAuth 2.0 Web Application credentials (not Desktop)
   - Add authorized redirect URI: `https://your-api-domain.com/oauth/google/callback`
   - Note your Client ID and Client Secret

2. **Set Environment Variables**:
   Add to your `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```

3. **Authorize via OAuth Flow**:
   - Visit `/oauth/google/authorize` endpoint (or use the API docs at `/docs`)
   - You'll be redirected to Google to authorize the application
   - After authorization, you'll be redirected back and tokens will be stored in the database
   - Check authorization status at `/oauth/google/status`

### OAuth Token Lifecycle

**🔄 Automatic Token Management**: The application handles token refresh automatically.

- **Access Token**: Expires after ~1 hour, automatically refreshed using refresh token
- **Refresh Token**: Long-lived (typically 6 months to indefinite), stored in the database
- **Auto-Refresh**: Tokens are proactively refreshed before expiration, or automatically on 401 errors
- **Expiration Tracking**: Access token expiration is tracked and stored in the database

### When You Need to Re-authenticate

You'll need to re-authorize via `/oauth/google/authorize` if:

1. **Refresh Token Expires**: 
   - Google revokes refresh tokens after 6+ months of inactivity
   - You'll see errors indicating the refresh token is expired/revoked
   
2. **Credentials Revoked**: 
   - You manually revoke access in Google Account settings
   - Security incident or suspicious activity detected by Google
   
3. **Scope Changes**: 
   - Application requires additional Google API permissions
   - Current implementation only needs `https://www.googleapis.com/auth/calendar`

### Troubleshooting OAuth Issues

**Symptoms of expired/invalid tokens**:
- Sync operations fail with "authentication failed" messages
- API logs show "Refresh token expired or revoked" errors
- Google Calendar events not being created

**How to check token status**:
```sh
# Check authorization status
curl "http://localhost:8000/oauth/google/status"

# Test a sync operation - if it works, tokens are valid
curl -X POST "http://localhost:8000/sync/runs/your_run_id"

# Check failed syncs for authentication errors
curl "http://localhost:8000/sync/runs/failed"
```

**To refresh credentials**:
1. Visit `/oauth/google/authorize` to re-authorize
2. Tokens will be automatically updated in the database
3. No need to restart the API server

### Security Notes

- **Never commit OAuth tokens to version control**
- **Refresh tokens are equivalent to passwords** - stored securely in the database
- **Access tokens expire quickly** - safe to log for debugging
- **Consider token rotation** if credentials may have been compromised

---

## 6. Getting the Data

### MapMyFitness
- Download your data as CSV from:  
  https://www.mapmyfitness.com/workout/export/csv
- Upload the CSV file via the API endpoint `POST /mmf/upload-csv` (requires authentication)
- Or use the frontend dashboard's upload feature to upload your CSV file

### Strava
- Authorize Strava via `/oauth/strava/authorize` (see [Strava Setup](#4-strava-setup-optional) above), then run `POST /strava/sync` to import activities.

---

## 7. Installing Dependencies

From the project root directory:

```sh
uv sync
```

This will install all dependencies as specified in the `uv.lock` file, ensuring a reproducible environment.

---

## 8. Starting the API Server

- **Development server (with auto-reload):**
  ```sh
  ENV=dev make dev
  # or
  ENV=dev uv run -m uvicorn fitness.app:app --reload
  ```

- **Production server:**
  ```sh
  ENV=prod make serve
  # or
  ENV=prod uv run -m uvicorn fitness.app:app
  ```

- The API will be available at `http://localhost:8000`.

- You can optionally also set the log level with the `LOG_LEVEL` environment variable. For example:
  ```sh
  ENV=dev LOG_LEVEL=debug make dev
  ```

---

## 9. API Documentation

- Interactive API docs (auto-generated by FastAPI) are available at:  
  `http://localhost:8000/docs`

---

## 10. Key Endpoints

- `GET /runs` — All runs with optional date filtering, timezone-aware filtering, and sorting.
- `GET /runs/details` — Detailed runs including shoes, shoe retirement notes, run version, and Google Calendar sync info. Optional query: `synced=true|false` to filter by Google Calendar sync status. Alias: `/runs-details`.
- `PATCH /runs/{run_id}` — Edit a run (with history tracking).
- `POST /mmf/upload-csv` — Upload MapMyFitness CSV data (requires authentication).
- `POST /strava/sync` — Fetch and update Strava data (requires authentication).
- `GET /metrics/...` — Aggregated metrics (see docs for full list).
- `POST /sync/runs/{run_id}` — Sync a run to Google Calendar; `DELETE` to remove.

## 11. Example: Quick Test

Fetch all runs:
```sh
curl "http://localhost:8000/runs"
```

Fetch metrics (see `/docs` for all endpoints):
```sh
curl "http://localhost:8000/metrics/mileage/by-shoe"
```

Fetch detailed runs (includes shoes, run version, and Google Calendar sync status):
```sh
curl "http://localhost:8000/runs/details?start=2024-01-01&end=2024-12-31&sort_by=distance&sort_order=desc&synced=true"
```

Response fields (per run):
- `id`, `datetime_utc`, `type`, `distance`, `duration`, `source`, `avg_heart_rate`
- `shoe_id`, `shoes`, `shoe_retirement_notes`, `deleted_at`, `version`
- `is_synced`, `sync_status`, `synced_at`, `google_event_id`, `synced_version`, `error_message`

Test Google Calendar sync (if configured):
```sh
# Sync a run to Google Calendar
curl -X POST "http://localhost:8000/sync/runs/your_run_id"

# Check sync status
curl "http://localhost:8000/sync/runs/your_run_id/status"

# Remove sync from Google Calendar  
curl -X DELETE "http://localhost:8000/sync/runs/your_run_id"
```

---

## 12. Testing

Before running tests, install dev dependencies (pytest, testcontainers, etc.):

```sh
uv sync --group dev
```

- **Unit tests only** (fast, no external services, no containers):
  ```sh
  make test
  ```

- **End-to-end (E2E) API + DB workflow tests** (uses Testcontainers Postgres + Alembic):
  - Requires Docker running
  ```sh
  make e2e-test
  ```

- **Integration tests with Strava (external system)**:
  - Requires valid Strava credentials in `.env.dev`
  ```sh
  make int-test
  ```

- **All tests**:
  ```sh
  make all-test
  ```

- **Linting, formatting, and type checks**:
  ```sh
  make lint
  make format
  make ty
  ```
