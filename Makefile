# Unit tests only (fast, no external dependencies)
test:
	uv run pytest -m "not e2e and not integration"

# End-to-end tests only (requires Docker for Postgres)
e2e-test:
	uv run pytest -m "e2e"

# Integration tests only (requires real Strava/Google credentials)
int-test:
	uv run pytest -m "integration"

# All tests
all-test:
	uv run pytest

lint:
	uv run ruff check

format:
	uv run ruff format

ty:
	uv run ty check 

dev:
	# Start a development server
	uv run -m uvicorn fitness.app:app

serve:
	# Start a production server
	uv run -m uvicorn fitness.app:app
