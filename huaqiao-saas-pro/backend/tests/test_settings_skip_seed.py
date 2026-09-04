"""Settings contract: production recovery .env keys must load without ValidationError."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_guoqiao_skip_seed_default_false(monkeypatch):
    monkeypatch.delenv("GUOQIAO_SKIP_SEED", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt")
    monkeypatch.setenv("VAULT_FERNET_KEY", "dGVzdC12YXVsdC1rZXktMzItYnl0ZXMhISEh")  # placeholder; may not be valid fernet
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_settings_skip_default.db")
    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.guoqiao_skip_seed is False


def test_guoqiao_skip_seed_env_true_and_m1_env_compat(monkeypatch):
    """Mirrors keys already written by m1-production-db-upgrade-recover.sh."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:pass@127.0.0.1:5433/huaqiao",
    )
    monkeypatch.setenv("GUOQIAO_SKIP_SEED", "1")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.guoqiaoplan.com")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.guoqiaoplan.com")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.guoqiaoplan.com")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-key")
    monkeypatch.setenv("VAULT_FERNET_KEY", "")

    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.guoqiao_skip_seed is True
    assert "127.0.0.1:5433/huaqiao" in s.database_url
    assert s.database_url.startswith("postgresql")
    assert s.public_base_url == "https://api.guoqiaoplan.com"
    assert s.frontend_base_url == "https://app.guoqiaoplan.com"
    assert "app.guoqiaoplan.com" in s.cors_origins


@pytest.mark.parametrize("val", ["true", "TRUE", "yes", "Yes"])
def test_guoqiao_skip_seed_truthy_strings(monkeypatch, val):
    monkeypatch.setenv("GUOQIAO_SKIP_SEED", val)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_settings_skip_truthy.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt")
    from app.config import Settings

    s = Settings(_env_file=None)
    assert s.guoqiao_skip_seed is True
