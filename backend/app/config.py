import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "国际生资格智评系统"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./eligibility.db")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    admin_token: str = ""
    ai_api_key: str = ""
    ai_base_url: str = "https://api.example.com/v1"
    ai_model: str = "default-chat-model"
    env: str = "development"
    # R4.3 Privacy settings
    privacy_hmac_secret: str = ""  # For blind index (searchable encryption)
    privacy_vault_key: str = ""  # For field-level encryption (defaults to VAULT_FERNET_KEY if empty)

    @property
    def cors_origin_list(self):
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_production_config(self):
        """Validate required settings for production. Call at startup."""
        if self.env == "production":
            if not self.admin_token or self.admin_token in ("", "change-me-in-production"):
                raise RuntimeError(
                    "ADMIN_TOKEN must be set in production environment. "
                    "Set a strong, random token via environment variable."
                )
            if len(self.admin_token) < 16:
                raise RuntimeError("ADMIN_TOKEN must be at least 16 characters in production")

    class Config:
        env_file = ".env"


def get_settings():
    return Settings()
