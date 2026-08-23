"""Payment callback signature verification service.

Implements official signature verification for WeChat Pay and Alipay callbacks,
with idempotency, anti-replay, and amount verification.
"""
import base64
import hashlib
import json
import logging
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PaymentOrder

logger = logging.getLogger(__name__)

# Maximum allowed timestamp drift for anti-replay (5 minutes)
MAX_TIMESTAMP_DRIFT = 300


class PaymentVerificationError(Exception):
    """Raised when payment verification fails."""
    pass


def verify_wechat_signature(headers: dict, body: bytes) -> bool:
    """Verify WeChat Pay V3 callback signature using RSA-SHA256.

    WeChat Pay V3 uses RSA-SHA256 signature.
    Signature string: timestamp\nnonce\nbody\n
    Verification uses WeChat Pay platform certificate public key.
    """
    settings = get_settings()
    if not settings.wechat_pay_public_key:
        logger.warning("WeChat Pay public key not configured")
        return False

    timestamp = headers.get("Wechatpay-Timestamp", "")
    nonce = headers.get("Wechatpay-Nonce", "")
    signature = headers.get("Wechatpay-Signature", "")
    serial = headers.get("Wechatpay-Serial", "")

    if not all([timestamp, nonce, signature, serial]):
        logger.warning("Missing WeChat Pay signature headers")
        return False

    # Verify serial number matches configured one
    if serial != settings.wechat_pay_serial_no:
        logger.warning(f"Serial number mismatch: {serial} != {settings.wechat_pay_serial_no}")
        return False

    # Anti-replay: check timestamp
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > MAX_TIMESTAMP_DRIFT:
            logger.warning(f"Timestamp drift too large: {ts}")
            return False
    except ValueError:
        logger.warning("Invalid timestamp format")
        return False

    # Construct signature string
    body_str = body.decode("utf-8") if isinstance(body, bytes) else body
    sign_str = f"{timestamp}\n{nonce}\n{body_str}\n"

    # Verify signature using RSA-SHA256 with WeChat Pay public key
    try:
        # Load the public key (PEM format)
        public_key = serialization.load_pem_public_key(
            settings.wechat_pay_public_key.encode("utf-8")
        )

        # Decode the base64 signature
        sig_bytes = base64.b64decode(signature)

        # Verify RSA-SHA256 signature
        public_key.verify(
            sig_bytes,
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        logger.warning(f"WeChat Pay signature verification failed: {e}")
        return False


def decrypt_wechat_resource(encrypted_data: dict) -> dict:
    """Decrypt WeChat Pay V3 encrypted resource using AES-256-GCM.

    The resource object contains:
    - algorithm: AES-256-GCM
    - ciphertext: Base64-encoded ciphertext
    - nonce: 12-byte nonce
    - associated_data: Associated data for AEAD
    """
    settings = get_settings()
    if not settings.wechat_pay_api_v3_key:
        raise PaymentVerificationError("WeChat Pay API v3 key not configured")

    algorithm = encrypted_data.get("algorithm")
    if algorithm != "AEAD_AES_256_GCM":
        raise PaymentVerificationError(f"Unsupported algorithm: {algorithm}")

    ciphertext = base64.b64decode(encrypted_data.get("ciphertext", ""))
    nonce = encrypted_data.get("nonce", "").encode("utf-8")
    associated_data = encrypted_data.get("associated_data", "").encode("utf-8")

    # AES-256-GCM decryption
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    api_v3_key = settings.wechat_pay_api_v3_key.encode("utf-8")
    if len(api_v3_key) != 32:
        raise PaymentVerificationError("API v3 key must be 32 bytes")

    aesgcm = AESGCM(api_v3_key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise PaymentVerificationError(f"Decryption failed: {e}")


def verify_alipay_signature(params: dict) -> bool:
    """Verify Alipay callback signature using RSA-SHA256.

    Alipay uses RSA-SHA256 signature.
    Sign string: sorted key=value pairs joined by &
    """
    settings = get_settings()
    if not settings.alipay_public_key:
        logger.warning("Alipay public key not configured")
        return False

    sign = params.pop("sign", "")
    sign_type = params.pop("sign_type", "RSA2")

    if not sign:
        logger.warning("Missing Alipay signature")
        return False

    if sign_type != "RSA2":
        logger.warning(f"Unsupported sign type: {sign_type}")
        return False

    # Construct sign string: sorted key=value pairs
    sorted_params = sorted(params.items())
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params if v)

    # Verify RSA-SHA256 signature
    try:
        public_key = serialization.load_pem_public_key(
            settings.alipay_public_key.encode("utf-8")
        )
        sig_bytes = base64.b64decode(sign)
        public_key.verify(
            sig_bytes,
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        logger.warning(f"Alipay signature verification failed: {e}")
        return False


def verify_payment_amount(db: Session, order_no: str, amount: float) -> bool:
    """Verify that the callback amount matches the order amount."""
    order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not order:
        logger.warning(f"Order not found: {order_no}")
        return False

    # Convert to cents for comparison (avoid floating point issues)
    order_amount_cents = int(order.amount * 100)
    callback_amount_cents = int(amount * 100)

    if order_amount_cents != callback_amount_cents:
        logger.warning(f"Amount mismatch for {order_no}: order={order.amount}, callback={amount}")
        return False

    return True


def check_idempotency(db: Session, order_no: str) -> Optional[PaymentOrder]:
    """Check if payment has already been processed (idempotency).

    Returns the order if already paid, None if needs processing.
    """
    order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not order:
        logger.warning(f"Order not found for idempotency check: {order_no}")
        return None

    if order.status == "paid":
        logger.info(f"Payment already processed (idempotent): {order_no}")
        return order

    return None


def process_wechat_callback(db: Session, headers: dict, body: bytes) -> PaymentOrder:
    """Process WeChat Pay callback with full verification.

    Flow:
    1. Verify RSA-SHA256 signature
    2. Parse body
    3. Decrypt resource if encrypted
    4. Check idempotency
    5. Verify amount
    6. Mark as paid
    """
    # 1. Verify signature
    if not verify_wechat_signature(headers, body):
        raise PaymentVerificationError("Invalid WeChat Pay signature")

    # 2. Parse body
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise PaymentVerificationError("Invalid JSON body")

    # 3. Decrypt resource if present
    if "resource" in data:
        data = decrypt_wechat_resource(data["resource"])

    order_no = data.get("out_trade_no") or data.get("order_no")
    amount = data.get("amount", {}).get("total", 0) / 100  # Convert fen to yuan

    if not order_no:
        raise PaymentVerificationError("Missing order_no in callback")

    # 4. Check idempotency
    existing = check_idempotency(db, order_no)
    if existing:
        return existing

    # 5. Verify amount
    if not verify_payment_amount(db, order_no, amount):
        raise PaymentVerificationError("Amount verification failed")

    # 6. Mark as paid
    from .payments import mark_payment_paid
    return mark_payment_paid(db, order_no)


def process_alipay_callback(db: Session, params: dict) -> PaymentOrder:
    """Process Alipay callback with full verification."""
    # 1. Verify signature
    params_copy = dict(params)
    if not verify_alipay_signature(params_copy):
        raise PaymentVerificationError("Invalid Alipay signature")

    # 2. Extract order info
    order_no = params.get("out_trade_no")
    amount = float(params.get("total_amount", 0))
    trade_status = params.get("trade_status")

    if not order_no:
        raise PaymentVerificationError("Missing order_no in callback")

    # 3. Check payment status
    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        raise PaymentVerificationError(f"Invalid trade status: {trade_status}")

    # 4. Check idempotency
    existing = check_idempotency(db, order_no)
    if existing:
        return existing

    # 5. Verify amount
    if not verify_payment_amount(db, order_no, amount):
        raise PaymentVerificationError("Amount verification failed")

    # 6. Mark as paid
    from .payments import mark_payment_paid
    return mark_payment_paid(db, order_no)
