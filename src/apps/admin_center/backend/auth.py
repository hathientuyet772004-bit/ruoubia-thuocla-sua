from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Response

from apps.admin_center.backend.settings import settings


SESSION_COOKIE = "admin_center_session"


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.failures: dict[str, deque[int]] = defaultdict(deque)

    def reset(self) -> None:
        self.failures.clear()

    def check(self, key: str) -> None:
        now = int(time.time())
        bucket = self.failures[key]
        self._prune(bucket, now)
        if len(bucket) >= self.max_attempts:
            raise HTTPException(status_code=429, detail="Too many failed login attempts")

    def record_failure(self, key: str) -> None:
        now = int(time.time())
        bucket = self.failures[key]
        self._prune(bucket, now)
        bucket.append(now)

    def record_success(self, key: str) -> None:
        self.failures.pop(key, None)

    def _prune(self, bucket: deque[int], now: int) -> None:
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()


login_rate_limiter = LoginRateLimiter()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signature(payload: str) -> str:
    return _encode(hmac.new(settings.ADMIN_SESSION_SECRET.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())


def create_session(response: Response, role: str = "admin") -> dict[str, str]:
    payload = _encode(json.dumps({
        "role": role,
        "exp": int(time.time()) + settings.ADMIN_SESSION_TTL_SECONDS,
    }, separators=(",", ":")).encode("utf-8"))
    response.set_cookie(
        SESSION_COOKIE,
        f"{payload}.{_signature(payload)}",
        httponly=True,
        max_age=settings.ADMIN_SESSION_TTL_SECONDS,
        samesite="lax",
        secure=settings.ENV.lower() == "production",
        path="/",
    )
    return {"role": role}


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def session_from_request(request: Request) -> dict[str, str]:
    value = request.cookies.get(SESSION_COOKIE)
    if not value or "." not in value:
        raise HTTPException(status_code=401, detail="Admin login required")
    payload, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _signature(payload)):
        raise HTTPException(status_code=401, detail="Admin session is invalid")
    try:
        claims = json.loads(_decode(payload))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Admin session is invalid")
    if int(claims.get("exp", 0)) <= int(time.time()):
        raise HTTPException(status_code=401, detail="Admin session expired")
    role = str(claims.get("role", "")).strip().lower()
    if role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Admin role cannot mutate data")
    return {"role": role}


def verify_password(password: str) -> bool:
    return hmac.compare_digest(password, settings.ADMIN_PASSWORD)


def login_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"
