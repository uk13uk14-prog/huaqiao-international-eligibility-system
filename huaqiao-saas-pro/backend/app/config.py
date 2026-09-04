import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "国际生资格智评系统 SaaS Pro"
    env: str = "development"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./saas_pro.db")
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
    wechat_pay_mch_id: str = ""
    wechat_pay_api_v3_key: str = ""
    wechat_pay_serial_no: str = ""
    wechat_pay_public_key: str = ""  # WeChat Pay platform certificate public key (PEM)
    alipay_enabled: bool = False
    alipay_app_id: str = ""
    alipay_public_key: str = ""
    # R4.3 Privacy settings
    privacy_hmac_secret: str = ""  # For blind index (searchable encryption)
    # Production recovery: skip seed_data on startup (deploy scripts set GUOQIAO_SKIP_SEED=1).
    # Default False preserves normal dev/test seed behavior.
    guoqiao_skip_seed: bool = False

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
