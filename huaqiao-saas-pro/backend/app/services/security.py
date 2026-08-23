import hashlib
import secrets
from datetime import datetime
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuthToken, User


def hash_password(password: str) -> str:
    salt = "saas-pro-static-salt"
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def create_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(36)
    db.add(AuthToken(user_id=user.id, token=token))
    db.commit()
    return token


def get_current_user(authorization: str = Header(""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.replace("Bearer ", "", 1).strip()
    row = db.query(AuthToken).filter(AuthToken.token == token).first()
    if not row:
        raise HTTPException(status_code=401, detail="登录已失效")
    user = db.query(User).filter(User.id == row.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


def get_current_user_optional(authorization: str = Header(""), db: Session = Depends(get_db)) -> User | None:
    """未携带 Token 时视为访客（免费档）；携带但无效时仍返回 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        return None
    row = db.query(AuthToken).filter(AuthToken.token == token).first()
    if not row:
        raise HTTPException(status_code=401, detail="登录已失效")
    user = db.query(User).filter(User.id == row.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


PAID_PLAN_CODES = frozenset(
    {"monthly", "yearly", "lifetime", "vip_month", "vip_year", "vip_three_year"}
)


def is_paid(user: User) -> bool:
    if user.plan_code == "lifetime":
        return True
    if user.plan_code not in PAID_PLAN_CODES:
        return False
    return bool(user.membership_until and user.membership_until > datetime.utcnow())


def has_smart_timeline(user: User) -> bool:
    """完整智能时间轴：年会员、三年会员、终身及兼容旧年度套餐。"""
    if not is_paid(user):
        return False
    return user.plan_code in frozenset({"vip_year", "vip_three_year", "yearly", "lifetime"})
