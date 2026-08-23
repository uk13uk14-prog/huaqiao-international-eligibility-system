from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "国际生资格智评系统 SaaS Pro"
    database_url: str = "sqlite:///./saas_pro.db"
    cors_origins: str = "http://localhost:5180,http://127.0.0.1:5180,http://localhost:5174,http://127.0.0.1:5174"
    ai_api_key: str = ""
    ai_base_url: str = "https://api.example.com/v1"
    ai_model: str = "default-chat-model"
    public_base_url: str = "http://127.0.0.1:8010"
    frontend_base_url: str = "http://127.0.0.1:5180"
    wechat_pay_enabled: bool = False
    alipay_enabled: bool = False
    # 客户资料库服务端加密（Fernet）；留空则在首次需要时回退为仅 BASE64（生产环境请务必配置）
    vault_fernet_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
