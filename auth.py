from __future__ import annotations

import os
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt

import db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.environ.get("SECRET_KEY", "dev-secret")
JWT_ALGO = "HS256"

ACCESS_EXP_HOURS = 24
RESET_EXP_MIN = 30


# -------------------
# DB helpers
# -------------------
def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _init_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            broker_status TEXT DEFAULT 'none',
            broker_mc TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    con.commit()


def _hash(pw: str) -> str:
    return pwd_context.hash(pw)


def _verify(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


# -------------------
# JSON helper (some modules expect this)
# -------------------
async def read_json(request: Request) -> Dict[str, Any]:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# -------------------
# Email
# -------------------
def _send_email(to_email: str, subject: str, body: str) -> None:
    smtp_from = os.environ.get("SMTP_FROM")
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_from, smtp_host, smtp_port, smtp_user, smtp_pass]):
        return

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, int(smtp_port)) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)


# -------------------
# Tokens
# -------------------
def _access_token(username: str, role: str, broker_status: str, broker_mc: Optional[str]) -> str:
    payload = {
        "username": username,
        "role": role,
        "broker_status": broker_status,
        "broker_mc": broker_mc,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _reset_token(username: str) -> str:
    payload = {
        "username": username,
        "scope": "password_reset",
        "exp": datetime.utcnow() + timedelta(minutes=RESET_EXP_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode_reset(token: str) -> str:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if data.get("scope") != "password_reset":
            raise ValueError("bad scope")
        return data["username"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")


def _decode_access_token(token: str) -> Dict[str, Any]:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if "username" not in data or "role" not in data:
            raise ValueError("missing claims")
        return data
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1].strip()


# -------------------
# AUTH exports
# -------------------
def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _extract_bearer(authorization)
    return _decode_access_token(token)


def _role_check(user: Dict[str, Any], role: str) -> Dict[str, Any]:
    role = (role or "").strip().lower()
    if (user.get("role") or "").lower() != role:
        raise HTTPException(status_code=403, detail=f"{role} role required")
    return user


def require_role(*args):
    """
    Supports all patterns we’ve had over time:

    1) NEW dependency factory:
       dep = require_role("admin")
       def route(user=Depends(dep)): ...

    2) OLD direct check:
       require_role(user_dict, "admin")

    3) LEGACY “weird” style used in some modules:
       require_role(Depends(get_current_user), "admin")
       (This happens at import time and must NOT crash.)
    """
    # Style 1: require_role("admin")
    if len(args) == 1:
        role = (args[0] or "").strip().lower()

        def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
            return _role_check(user, role)

        return _dep

    # Styles 2/3: require_role(x, "admin")
    if len(args) == 2:
        first, role = args
        role = (str(role) or "").strip().lower()

        # If caller passed a Depends object (or anything non-dict) at import time,
        # treat it as a request for a dependency function instead of crashing.
        if not isinstance(first, dict):
            def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
                return _role_check(user, role)
            return _dep

        return _role_check(first, role)

    raise TypeError("require_role expects (role) or (user_or_depends, role)")


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _role_check(user, "admin")


def require_driver(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _role_check(user, "driver")


def require_dispatcher(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _role_check(user, "dispatcher")


def require_dispatcher_linked(user: Dict[str, Any] = Depends(require_dispatcher)) -> Dict[str, Any]:
    broker_mc = (user.get("broker_mc") or "").strip()
    if not broker_mc:
        raise HTTPException(status_code=403, detail="Dispatcher not linked to a broker")
    return user


def require_broker_approved(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    user = _role_check(user, "broker")
    if (user.get("broker_status") or "none").lower() != "approved":
        raise HTTPException(status_code=403, detail="Broker not approved")
    return user


# -------------------
# Models
# -------------------
class RegisterReq(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str
    role: str
    broker_mc: Optional[str] = None


class LoginReq(BaseModel):
    username: str
    password: str


class ForgotReq(BaseModel):
    username: str


class ResetReq(BaseModel):
    token: str
    new_password: str


# -------------------
# Routes
# -------------------
@router.post("/register")
def register(body: RegisterReq):
    username = body.username.strip()
    role = body.role.strip().lower()

    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if role not in {"driver", "dispatcher", "broker", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    broker_status = "none"
    broker_mc = None
    if role == "broker":
        if not body.broker_mc or not body.broker_mc.strip():
            raise HTTPException(status_code=400, detail="broker_mc required for brokers")
        broker_status = "pending"
        broker_mc = body.broker_mc.strip()

    con = _connect()
    try:
        _init_schema(con)

        existing = con.execute("SELECT username FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

        con.execute(
            """
            INSERT INTO users (username, email, password_hash, role, broker_status, broker_mc, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                str(body.email).strip().lower() if body.email else None,
                _hash(body.password),
                role,
                broker_status,
                broker_mc,
                datetime.utcnow().isoformat(),
            ),
        )
        con.commit()
        return {"ok": True, "message": "Registered"}
    finally:
        con.close()


@router.post("/login")
def login(body: LoginReq):
    con = _connect()
    try:
        _init_schema(con)

        row = con.execute(
            "SELECT username, password_hash, role, broker_status, broker_mc FROM users WHERE username=?",
            (body.username.strip(),),
        ).fetchone()

        if not row or not _verify(body.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = _access_token(row["username"], row["role"], row["broker_status"], row["broker_mc"])
        return {
            "ok": True,
            "token": token,
            "role": row["role"],
            "broker_status": row["broker_status"],
            "broker_mc": row["broker_mc"],
        }
    finally:
        con.close()


@router.post("/forgot-password")
def forgot_password(body: ForgotReq):
    con = _connect()
    try:
        _init_schema(con)

        row = con.execute(
            "SELECT username, email FROM users WHERE username=?",
            (body.username.strip(),),
        ).fetchone()

        if not row:
            return {"ok": True}

        if not row["email"]:
            return {"ok": True}

        token = _reset_token(row["username"])
        base = os.environ.get("RESET_URL_BASE", "").rstrip("/")
        link = f"{base}/reset-password?token={token}" if base else f"/reset-password?token={token}"

        _send_email(
            row["email"],
            "Chequmate – Password Reset",
            (
                "You requested a password reset.\n\n"
                f"Reset link (valid {RESET_EXP_MIN} minutes):\n{link}\n\n"
                "If you didn’t request this, ignore this email.\n"
            ),
        )
        return {"ok": True}
    finally:
        con.close()


@router.post("/password-reset/request")
def password_reset_request(body: ForgotReq):
    return forgot_password(body)


@router.post("/reset-password")
def reset_password(body: ResetReq):
    username = _decode_reset(body.token)

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    con = _connect()
    try:
        _init_schema(con)
        con.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (_hash(body.new_password), username),
        )
        con.commit()
        return {"ok": True}
    finally:
        con.close()


@router.post("/password-reset/confirm")
def password_reset_confirm(body: ResetReq):
    return reset_password(body)
