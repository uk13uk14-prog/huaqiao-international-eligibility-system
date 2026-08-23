"""R1 Security Tests for free backend."""
import os
import sys

os.environ.setdefault("ADMIN_TOKEN", "")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestAdminTokenGate:
    """Test ADMIN_TOKEN production gate."""

    def test_production_empty_admin_token_raises(self):
        from app.config import Settings
        s = Settings(env="production", admin_token="")
        with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
            s.validate_production_config()

    def test_production_short_admin_token_raises(self):
        from app.config import Settings
        s = Settings(env="production", admin_token="abc")
        with pytest.raises(RuntimeError, match="at least 16"):
            s.validate_production_config()

    def test_production_strong_admin_token_passes(self):
        from app.config import Settings
        s = Settings(env="production", admin_token="strong-secret-token-12345")
        s.validate_production_config()  # Should not raise

    def test_development_empty_admin_token_ok(self):
        from app.config import Settings
        s = Settings(env="development", admin_token="")
        s.validate_production_config()  # Should not raise
