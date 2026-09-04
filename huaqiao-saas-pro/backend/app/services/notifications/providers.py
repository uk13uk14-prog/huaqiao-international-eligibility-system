"""Push provider abstraction — V1: IN_APP + DevNull. No invented FCM/APNS keys."""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from .constants import PROVIDER_APNS, PROVIDER_FCM, PROVIDER_IN_APP, PROVIDER_WEB_PUSH
from .sanitize import sanitize_text

logger = logging.getLogger("guoqiao.notifications.push")

@dataclass
class PushPayload:
    notification_id: int
    title: str
    body: str
    priority: str
    action_url: str = ""

@dataclass
class PushResult:
    ok: bool
    provider: str
    detail: str = ""

class PushProvider(ABC):
    name: str = "BASE"
    @abstractmethod
    def send(self, *, device_token: str, payload: PushPayload) -> PushResult:
        raise NotImplementedError

class InAppProvider(PushProvider):
    name = PROVIDER_IN_APP
    def send(self, *, device_token: str, payload: PushPayload) -> PushResult:
        _ = device_token
        return PushResult(ok=True, provider=self.name, detail="in_app_ready")

class DevNullProvider(PushProvider):
    def __init__(self, name: str):
        self.name = name
    def send(self, *, device_token: str, payload: PushPayload) -> PushResult:
        _ = device_token
        logger.info("dev_push_skipped provider=%s notification_id=%s priority=%s",
                    self.name, payload.notification_id, payload.priority)
        return PushResult(ok=True, provider=self.name, detail="dev_adapter_no_credentials")

_REGISTRY = {
    PROVIDER_IN_APP: InAppProvider(),
    PROVIDER_WEB_PUSH: DevNullProvider(PROVIDER_WEB_PUSH),
    PROVIDER_FCM: DevNullProvider(PROVIDER_FCM),
    PROVIDER_APNS: DevNullProvider(PROVIDER_APNS),
}

def get_provider(name: str | None) -> PushProvider:
    key = (name or PROVIDER_IN_APP).upper()
    return _REGISTRY.get(key) or _REGISTRY[PROVIDER_IN_APP]

def deliver(*, provider_name: str, device_token: str, notification_id: int, title: str,
            body: str, priority: str, action_url: str = "", for_lockscreen: bool = True) -> PushResult:
    provider = get_provider(provider_name)
    payload = PushPayload(
        notification_id=notification_id,
        title=sanitize_text(title, for_lockscreen=for_lockscreen),
        body=sanitize_text(body, for_lockscreen=for_lockscreen),
        priority=priority,
        action_url=action_url or "",
    )
    return provider.send(device_token=device_token or "", payload=payload)

def provider_status() -> dict[str, Any]:
    return {
        "IN_APP": {"ready": True, "credentials": False},
        "WEB_PUSH": {"ready": False, "credentials": False, "note": "dev adapter only"},
        "FCM": {"ready": False, "credentials": False, "note": "no keys invented"},
        "APNS": {"ready": False, "credentials": False, "note": "no keys invented"},
    }
