from datetime import datetime, timedelta
import secrets
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import MembershipPlan, Order, PaymentOrder, User

PAYMENT_CHANNELS = {"mock", "wechat", "alipay"}


def make_order_no(channel: str) -> str:
    return f"PAY-{channel.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"


def apply_membership(db: Session, user: User, plan: MembershipPlan, source: str, amount: int = 0):
    user.plan_code = plan.code
    base = datetime.utcnow() if not user.membership_until or user.membership_until < datetime.utcnow() else user.membership_until
    user.membership_until = base + timedelta(days=plan.duration_days or 0)
    if plan.code == "lifetime":
        user.membership_until = datetime.utcnow() + timedelta(days=36500)
    db.add(Order(tenant_id=user.tenant_id, user_id=user.id, plan_code=plan.code, amount=amount, status="paid", source=source))
    db.commit()
    db.refresh(user)
    return user


def create_payment_order(db: Session, user: User, plan_code: str, channel: str):
    channel = channel.lower().strip()
    if channel not in PAYMENT_CHANNELS:
        raise ValueError("不支持的支付通道")
    plan = db.query(MembershipPlan).filter(MembershipPlan.code == plan_code, MembershipPlan.is_active == True).first()
    if not plan or plan.code == "free":
        raise ValueError("套餐不存在或不可购买")
    settings = get_settings()
    order_no = make_order_no(channel)
    if channel == "mock":
        pay_url = f"{settings.frontend_base_url}/mock-pay?order_no={order_no}"
        qr_content = f"MOCK_PAY::{order_no}::{plan.price}"
    elif channel == "wechat":
        pay_url = f"weixin://wxpay/bizpayurl?pr={order_no}"
        qr_content = f"WECHAT_PAY_PLACEHOLDER::{order_no}::{plan.price}"
    else:
        pay_url = f"https://openapi.alipay.com/gateway.do?out_trade_no={order_no}"
        qr_content = f"ALIPAY_PLACEHOLDER::{order_no}::{plan.price}"
    payment = PaymentOrder(order_no=order_no, tenant_id=user.tenant_id, user_id=user.id, plan_code=plan.code, channel=channel, amount=plan.price, status="pending", pay_url=pay_url, qr_content=qr_content)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment, plan


def mark_payment_paid(db: Session, order_no: str, provider_trade_no: str = ""):
    payment = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not payment:
        raise ValueError("支付订单不存在")
    if payment.status == "paid":
        return payment
    plan = db.query(MembershipPlan).filter(MembershipPlan.code == payment.plan_code).first()
    user = db.query(User).filter(User.id == payment.user_id).first()
    if not plan or not user:
        raise ValueError("支付订单数据不完整")
    payment.status = "paid"
    payment.provider_trade_no = provider_trade_no
    payment.paid_at = datetime.utcnow()
    apply_membership(db, user, plan, source=f"payment_{payment.channel}", amount=payment.amount)
    db.commit()
    db.refresh(payment)
    return payment
