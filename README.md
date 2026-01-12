# Fitness API – Setup & Usage

## Overview

This API provides analysis and aggregation of your running data from two sources:
- **MapMyFitness**: Historical and treadmill runs (CSV export)
- **Strava**: Outdoor runs (via Strava API)

---

## 1. Prerequisites
- Python 3.12+ (recommended: [uv](https://github.com/astral-sh/uv))
- [Make](https://www.gnu.org/software/make/) (for convenience commands)
- Strava account (for outdoor run data)
- MapMyFitness CSV export (for historical/treadmill runs)

---

## 2. Environment Variables

Create a `.env` file in the project root directory with the following variables:

```env
# Required: OAuth Identity Provider
IDENTITY_PROVIDER_URL=http://localhost:8080

# Required for Strava API integration
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
STRAVA_REFRESH_TOKEN=your_strava_refresh_token

# Optional: Set the timezone for MMF data (default: America/Chicago)
# Used when uploading MapMyFitness CSV files via the API
MMF_TIMEZONE=America/Chicago

# Optional: Google Calendar sync (leave blank to disable sync features)
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
# Optional: target calendar (defaults to "primary" if unset)
GOOGLE_CALENDAR_ID=your_calendar_id
```

- **IDENTITY_PROVIDER_URL**:
  Base URL of the OAuth identity provider. Required for authenticating mutation endpoints (PATCH, POST, DELETE operations). The separate frontend dashboard handles OAuth login automatically.

- **STRAVA_CLIENT_ID / SECRET / REFRESH_TOKEN**:  
  Get these from your Strava API application settings. See "Strava Setup" section below for initial setup.
- **STRAVA_ACCESS_TOKEN / EXPIRES_AT** (optional):  
  Auto-managed by the system after initial setup. These are automatically refreshed and updated.
- **MMF_TIMEZONE**:  
  Optional timezone for interpreting MapMyFitness CSV data when uploading. Defaults to "America/Chicago" if not set. Can also be specified per-upload via the API endpoint.
- **GOOGLE_CLIENT_ID / SECRET**:  
  OAuth 2.0 credentials from Google Cloud Console (https://console.cloud.google.com). Required for Google Calendar sync. Tokens are stored in the database via the OAuth flow.
- **GOOGLE_CALENDAR_ID** (optional):
  Calendar to create events in. If not provided, the API will use the `primary` calendar.

---

## 3. Authentication

The API uses OAuth 2.0 for authentication via an external identity provider. Authentication is required for all mutation endpoints (POST, PATCH, DELETE operations).

### Protected Endpoints
The following endpoints require OAuth Bearer tokens:
- `POST /strava/update-data` — Refresh Strava data
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

## 4. Strava Setup

Strava integration is required for fetching running activities. This section covers the complete setup and ongoing maintenance of OAuth tokens.

### Initial Setup

1. **Create Strava API Application**:
   - Go to [Strava API Settings](https://www.strava.com/settings/api)
   - Click "Create App" and fill in the application details
   - Set "Authorization Callback Domain" to `localhost`
   - Note your Client ID and Client Secret

2. **Get OAuth Tokens via Manual Authorization**:
   - Construct the authorization URL:
     ```
     https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&scope=activity:read_all&approval_prompt=auto
     ```
   - Visit the URL in your browser and authorize the app
   - After authorization, you'll be redirected to `localhost` with a `code` parameter in the URL
   - Exchange the code for tokens:
     ```sh
     curl -X POST https://www.strava.com/oauth/token \
       -d client_id=YOUR_CLIENT_ID \
       -d client_secret=YOUR_CLIENT_SECRET \
       -d code=AUTHORIZATION_CODE \
       -d grant_type=authorization_code
     ```
   - The response will contain your access token, refresh token, and expiration timestamp

3. **Add to Environment File**:
   Copy the values to your `.env` file:
   ```sh
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   STRAVA_REFRESH_TOKEN=your_refresh_token
   ```

### Token Management

The system automatically handles token refresh during runtime:
- **Access tokens** expire every 6 hours and are auto-refreshed using the refresh token
- **Refresh tokens** are long-lived and updated when rotated by Strava
- **No re-authentication** needed during API operation
- **Manual refresh**: Re-authorize via the steps above if tokens become invalid

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

**🔄 Automatic Token Management**: The application handles token refresh automatically! At least I think so.

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
- The API will prompt you to authorize the app on first run if credentials are missing or expired.

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
  ENV=dev uv run -m uvicorn fitness.app.app:app --reload
  ```

- **Production server:**
  ```sh
  ENV=prod make serve
  # or
  ENV=prod uv run -m uvicorn fitness.app.app:app
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
- `POST /strava/update-data` — Fetch and update Strava data (requires authentication).
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
