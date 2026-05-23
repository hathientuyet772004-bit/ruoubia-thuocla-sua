from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from apps.admin_center.backend.auth import clear_session, create_session, login_key, login_rate_limiter, session_from_request, verify_password
from apps.admin_center.backend.schemas import LoginSchema

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginSchema, request: Request, response: Response):
    key = login_key(request)
    login_rate_limiter.check(key)
    if not verify_password(payload.password):
        login_rate_limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid admin password")
    login_rate_limiter.record_success(key)
    return create_session(response)


@router.get("/session")
async def current_session(request: Request):
    return session_from_request(request)


@router.post("/logout")
async def logout(response: Response):
    clear_session(response)
    return {"status": "logged_out"}
