from fastapi import Header, HTTPException

from .config import get_settings


def verify_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    settings = get_settings()
    if not (settings.admin_token or "").strip():
        raise HTTPException(status_code=503, detail="服务器未配置 ADMIN_TOKEN，请在 .env 中设置后重启服务")
    if not x_admin_token or x_admin_token.strip() != settings.admin_token.strip():
        raise HTTPException(status_code=401, detail="无效的管理令牌")
    return True
