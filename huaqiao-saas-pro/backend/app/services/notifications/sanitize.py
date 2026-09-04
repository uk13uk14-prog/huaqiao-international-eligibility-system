"""Sanitize notification text — never leak secrets or full IDs."""
from __future__ import annotations
import re

_PATTERNS = [
    (re.compile(r"(?<!\d)\d{17}[\dXx]\b"), "[证件已隐藏]"),
    (re.compile(r"(?<![A-Za-z0-9])[EeGgPp]\d{7,9}\b"), "[证件已隐藏]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.I), "Bearer [已隐藏]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+={0,2}\.[A-Za-z0-9_\-]+={0,2}\b"), "[token已隐藏]"),
    (re.compile(r"\bgAAAA[A-Za-z0-9_\-+/=]{20,}\b"), "[密文已隐藏]"),
    (re.compile(r"(password|passwd|pwd)\s*[:=]\s*\S+", re.I), r"\1=[已隐藏]"),
    (re.compile(r"(api[_-]?key|secret|token)\s*[:=]\s*\S+", re.I), r"\1=[已隐藏]"),
    (re.compile(r"cipher_blob\s*[:=]\s*\S+", re.I), "cipher_blob=[已隐藏]"),
]
_LOCKSCREEN_SAFE = "你有一条重要提醒，请进入国侨升学查看。"

def sanitize_text(text: str | None, *, for_lockscreen: bool = False) -> str:
    raw = str(text or "")
    if for_lockscreen:
        if any(p.search(raw) for p, _ in _PATTERNS):
            return _LOCKSCREEN_SAFE
        lowered = raw.lower()
        if "护照" in raw or "身份证" in raw or "password" in lowered or "cipher" in lowered:
            return _LOCKSCREEN_SAFE
    out = raw
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out.strip()

def assert_no_raw_secrets(text: str) -> bool:
    s = text or ""
    if re.search(r"\b\d{17}[\dXx]\b", s):
        return False
    if re.search(r"\beyJ[A-Za-z0-9_\-]+=*\.", s):
        return False
    if re.search(r"\bgAAAA[A-Za-z0-9_\-+/=]{40,}\b", s):
        return False
    if re.search(r"(password|passwd)\s*[:=]\s*(?!\[已隐藏\])\S+", s, re.I):
        return False
    return True
