from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "国际生资格智评系统 SaaS Pro"
    env: str = "development"
    database_url: str = "sqlite:///./saas_pro.db"
    cors_origins: str = "http://localhost:5180,http://127.0.0.1:5180,http://localhost:5174,http://127.0.0.1:5174"
    jwt_secret_key: str = "change-me-in-production"
    vault_fernet_key: str = ""
    admin_token: str = ""
    ai_api_key: str = ""
    ai_base_url: str = "https://api.example.com/v1"
    ai_model: str = "default-chat-model"
    public_base_url: str = "http://127.0.0.1:8010"
    frontend_base_url: str = "http://127.0.0.1:5180"
    wechat_pay_enabled: bool = False
    alipay_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def validate_production_config(self):
        """Validate that required secrets are set in production."""
        if self.env != "production":
            return
        errors = []
        if not self.jwt_secret_key or self.jwt_secret_key == "change-me-in-production":
            errors.append("JWT_SECRET_KEY must be set in production")
        if not self.vault_fernet_key:
            errors.append("VAULT_FERNET_KEY must be set in production")
        if not self.admin_token:
            errors.append("ADMIN_TOKEN must be set in production")
        if errors:
            raise RuntimeError("Production config errors: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
