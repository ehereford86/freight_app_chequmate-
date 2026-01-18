from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from passlib.context import CryptContext

import db

router = APIRouter()

# -----------------------------
# Security / JWT
# -----------------------------
JWT_SECRET = db.get_env("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
TOKEN_TTL_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(pw, hashed)
    except Exception:
        return False


def create_access_token(payload: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = dict(payload)
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=TOKEN_TTL_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)


def _bearer_token(req: Request) -> Optional[str]:
    auth = req.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip() or None


# -----------------------------
# Current user dependency
# -----------------------------
def get_current_user(req: Request) -> Optional[dict]:
    """
    Used by other modules (pricing.py etc).
    Returns user dict or None if not logged in.
    """
    token = _bearer_token(req)
    if not token:
        return None

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        username = payload.get("sub")
        if not username:
            return None
        u = db.get_user(username)
        if not u:
            return None

        # Normalize sqlite Row -> dict
        return {
            "id": u["id"],
            "username": u["username"],
            "role": u["role"],
            "broker_status": u["broker_status"],
            "mc_number": u["mc_number"],
        }
    except JWTError:
        return None


def require_user(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(*roles: str):
    def _dep(user: dict = Depends(require_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep


# -----------------------------
# Auth endpoints
# -----------------------------
@router.post("/login")
def login(payload: Dict[str, Any]):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    u = db.get_user(username)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": username})
    return {
        "ok": True,
        "token": token,
        "user": {
            "username": u["username"],
            "role": u["role"],
            "broker_status": u["broker_status"],
            "mc_number": u["mc_number"],
        }
    }


@router.post("/register")
def register(payload: Dict[str, Any]):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    role = (payload.get("role") or "driver").strip().lower()
    mc_number = (payload.get("mc_number") or "").strip() or None

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if role not in ("driver", "dispatcher", "broker", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")

    if db.get_user(username):
        raise HTTPException(status_code=400, detail="Username already exists")

    broker_status = "none"
    if role == "broker":
        # Brokers require MC# and are pending until admin approves (your requirement)
        if not mc_number:
            raise HTTPException(status_code=400, detail="Broker MC# required")
        broker_status = "pending"
        db.create_user(username, hash_password(password), role, mc_number=mc_number, broker_status=broker_status)
        db.create_broker_request(username, mc_number)
    else:
        db.create_user(username, hash_password(password), role, mc_number=None, broker_status=broker_status)

    return {"ok": True, "message": "Registered"}


@router.get("/verify-token")
def verify_token(user: Optional[dict] = Depends(get_current_user)):
    return {"ok": True, "logged_in": bool(user), "user": user}


# -----------------------------
# Admin endpoints (broker approval)
# -----------------------------
@router.get("/admin/list-broker-requests")
def admin_list_broker_requests(user: dict = Depends(require_role("admin"))):
    rows = db.list_broker_requests("pending")
    return {"ok": True, "requests": [dict(r) for r in rows]}


@router.post("/admin/approve-broker")
def admin_approve_broker(payload: Dict[str, Any], user: dict = Depends(require_role("admin"))):
    rid = payload.get("request_id")
    if rid is None:
        raise HTTPException(status_code=400, detail="Missing request_id")
    req = db.approve_broker_request(int(rid))
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True, "approved": dict(req)}


@router.post("/admin/reject-broker")
def admin_reject_broker(payload: Dict[str, Any], user: dict = Depends(require_role("admin"))):
    rid = payload.get("request_id")
    if rid is None:
        raise HTTPException(status_code=400, detail="Missing request_id")
    req = db.reject_broker_request(int(rid))
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True, "rejected": dict(req)}
