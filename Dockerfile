FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached unless lock/pyproject changes)
COPY uv.lock pyproject.toml README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY fitness/ fitness/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER 1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "fitness.app:app", "--host", "0.0.0.0", "--port", "8000"]
