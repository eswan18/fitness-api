# Unit tests only
test:
	uv run pytest -m "not e2e"

# End-to-end tests only
e2e-test:
	uv run pytest -m "e2e"

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
