"""Tests for app-level middleware wiring."""

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from fitness.app.app import app


def test_gzip_and_cors_middleware_registered():
    """GZip must be registered (compresses large metrics lists), and CORS must
    stay outermost so it still sets headers on every response, gzipped or not."""
    classes = [m.cls for m in app.user_middleware]
    assert GZipMiddleware in classes
    assert CORSMiddleware in classes
    # In Starlette, add_middleware inserts at index 0, so a lower index == added
    # later == outer layer. CORS was added after GZip, so it must be outermost.
    assert classes.index(CORSMiddleware) < classes.index(GZipMiddleware)
