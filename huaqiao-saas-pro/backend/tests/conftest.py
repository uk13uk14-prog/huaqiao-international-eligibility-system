"""Shared pytest fixtures for SaaS backend tests."""
import os

from cryptography.fernet import Fernet

# Must run before any test module imports app.main / settings.
os.environ.setdefault("ENV", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-shared-conftest")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_shared_conftest.db")


import pytest


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Avoid SlowAPI register/login rate limits across the full suite."""
    try:
        from app.main import limiter

        was = getattr(limiter, "enabled", True)
        limiter.enabled = False
        yield
        limiter.enabled = was
    except Exception:
        yield
