import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, Header, HTTPException
import bcrypt
import jwt
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuthToken, User
from ..config import get_settings


def hash_password(password: str) -> str:
    """Hash password using bcrypt with random salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash. Supports both bcrypt and legacy SHA256."""
    # Try bcrypt first
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    # Legacy SHA256 fallback for migration
    legacy_salt = "saas-pro-static-salt"
    legacy_hash = hashlib.sha256(f"{legacy_salt}:{password}".encode("utf-8")).hexdigest()
    if legacy_hash == hashed:
        return True
    return False


def is_legacy_hash(hashed: str) -> bool:
    """Check if password hash is legacy SHA256 format."""
    return not (hashed.startswith("$2b$") or hashed.startswith("$2a$"))


def create_token(db: Session, user: User) -> str:
    """Create JWT token with expiration."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=120),
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    # Store in AuthToken table for revocation support
    db.add(AuthToken(user_id=user.id, token=token))
    db.commit()
    return token


def decode_token(token: str) -> dict:
    """Decode and verify JWT token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")


def get_current_user(authorization: str = Header(""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    # Decode JWT
    payload = decode_token(token)
    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


# ============================================================
# 权限判断辅助函数
# ============================================================

PAID_PLANS = {"pro_monthly", "pro_yearly", "pro_plus_yearly"}


def is_paid(user) -> bool:
    """判断用户是否为付费用户"""
    if not user or not user.plan_code:
        return False
    return user.plan_code in PAID_PLANS


def has_smart_timeline(user) -> bool:
    """判断用户是否拥有智能时间线功能（pro_plus_yearly 专属）"""
    if not user or not user.plan_code:
        return False
    return user.plan_code == "pro_plus_yearly"


def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI 依赖：要求用户为管理员"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def get_current_user_optional(authorization: str = Header(""), db: Session = Depends(get_db)) -> User | None:
    """未携带 Token 时视为访客（免费档）；携带但无效时仍返回 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        return None
    payload = decode_token(token)
    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user
