# Running Dashboard

A Python API (in `./api`) and a React front end (in `./dashboard`) that together display my running data from Strava and MapMyRun.

## Authentication

This application uses OAuth 2.0 for authentication via the [Identity Provider](https://github.com/eswan18/identity). The dashboard handles the OAuth login flow automatically when accessing protected features (e.g., updating data, editing runs).

**Setup Requirements:**
- Identity provider running and configured (see identity repo README)
- OAuth client registered for the dashboard
- Environment variables configured in both `api/.env` and `dashboard/.env`

See `api/README.md` for detailed authentication setup instructions.

## Testing

See `api/README.md` for full details. Quick start:

```sh
cd api
uv sync --group dev
# Unit tests
make test
# End-to-end API+DB tests (requires Docker)
make e2e-test
# External integration tests (Strava credentials required)
make int-test
```
