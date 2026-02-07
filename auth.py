from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Header, Request, Query
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt

import db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = (os.environ.get("SECRET_KEY") or "dev-secret").strip()
JWT_ALGO = "HS256"

ACCESS_EXP_HOURS = 24
RESET_EXP_MIN = 30


# -------------------
# Password hashing
# -------------------
def _hash(pw: str) -> str:
    return pwd_context.hash(pw)


def _verify(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


# -------------------
# JSON helper
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

    # If SMTP isn't configured, do nothing (by design).
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
        return str(data["username"])
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
    Supports:
    - require_role("admin") as dependency factory
    - require_role(user_dict, "admin") direct check
    - tolerate legacy odd styles without crashing
    """
    if len(args) == 1:
        role = (args[0] or "").strip().lower()

        def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
            return _role_check(user, role)

        return _dep

    if len(args) == 2:
        first, role = args
        role = (str(role) or "").strip().lower()

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
    invite_code: Optional[str] = None


class LoginReq(BaseModel):
    username: str
    password: str


class ForgotReq(BaseModel):
    username: str


class ResetReq(BaseModel):
    token: str
    new_password: str


class SetEmailReq(BaseModel):
    email: EmailStr


class ChangePasswordReq(BaseModel):
    current_password: str
    new_password: str


class BootstrapAdminReq(BaseModel):
    username: str
    new_password: str


# -------------------
# Helpers
# -------------------
def _require_env_admin_key(admin_key: Optional[str]) -> None:
    expected = (os.environ.get("ADMIN_KEY") or "").strip()
    if not expected:
        # If you forgot to set it on Render, we refuse to run (safe default).
        raise HTTPException(status_code=503, detail="ADMIN_KEY not configured")
    if (admin_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _invite_required_for_brokers(invite_code: Optional[str]) -> None:
    expected = (os.environ.get("BROKER_INVITE_CODE") or "").strip()
    if not expected:
        # If you didn’t configure it, brokers cannot self-register.
        raise HTTPException(status_code=503, detail="BROKER_INVITE_CODE not configured")
    if (invite_code or "").strip() != expected:
        raise HTTPException(status_code=403, detail="Invite code required")


# -------------------
# Routes
# -------------------
@router.get("/verify-token")
def verify_token(u: Dict[str, Any] = Depends(get_current_user)):
    return {"ok": True, "user": u}


@router.post("/me/set-email")
async def me_set_email(request: Request, u: Dict[str, Any] = Depends(get_current_user)):
    body = await read_json(request)
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    try:
        db.set_email(u["username"], email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set email: {e}")
    return {"ok": True, "username": u["username"], "email": email}


@router.post("/me/change-password")
async def me_change_password(body: ChangePasswordReq, u: Dict[str, Any] = Depends(get_current_user)):
    if len(body.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    row = db.get_user(u["username"])
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user_row = dict(row)
    if not _verify(body.current_password, user_row.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Current password is wrong")

    try:
        with db._conn() as con:
            con.execute(
                "UPDATE users SET password_hash=? WHERE username=?",
                (_hash(body.new_password), u["username"]),
            )
        try:
            db.audit(u["username"], "change_password", f"user:{u['username']}", None)
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change password: {e}")


@router.post("/admin/bootstrap-admin", include_in_schema=False)
def bootstrap_admin(body: BootstrapAdminReq, admin_key: Optional[str] = Query(default=None)):
    """
    Emergency admin recovery for Render.

    Requires ?admin_key=... which must match env ADMIN_KEY.
    Creates admin user if missing, or resets password if it exists.
    """
    _require_env_admin_key(admin_key)

    username = (body.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if len(body.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    row = db.get_user(username)
    try:
        if not row:
            db.create_user(
                username=username,
                password_hash=_hash(body.new_password),
                role="admin",
                broker_mc=None,
                broker_status="none",
            )
            try:
                db.audit(username, "bootstrap_admin_create", f"user:{username}", "admin")
            except Exception:
                pass
            return {"ok": True, "action": "created", "username": username}

        # Exists -> force role admin and reset password
        with db._conn() as con:
            con.execute(
                "UPDATE users SET password_hash=?, role='admin', broker_status='none', broker_mc=NULL WHERE username=?",
                (_hash(body.new_password), username),
            )
        try:
            db.audit(username, "bootstrap_admin_reset", f"user:{username}", "admin")
        except Exception:
            pass
        return {"ok": True, "action": "reset", "username": username}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bootstrap failed: {e}")


@router.post("/register")
def register(body: RegisterReq):
    username = (body.username or "").strip()
    role = (body.role or "").strip().lower()

    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if len(body.password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if role not in {"driver", "dispatcher", "broker", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Hard lock: nobody can self-register as admin.
    if role == "admin":
        raise HTTPException(status_code=403, detail="Admin registration disabled")

    existing = db.get_user(username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    broker_status = "none"
    broker_mc = None

    if role == "broker":
        broker_mc = (body.broker_mc or "").strip()
        if not broker_mc:
            raise HTTPException(status_code=400, detail="broker_mc required for brokers")

        # Invite-only broker onboarding
        _invite_required_for_brokers(body.invite_code)

        broker_status = "pending"

    try:
        db.create_user(
            username=username,
            password_hash=_hash(body.password),
            role=role,
            broker_mc=broker_mc,
            broker_status=broker_status,
        )
        if body.email:
            db.set_email(username, str(body.email).strip().lower())

        if role == "broker" and broker_mc:
            try:
                db.create_broker_request(username, broker_mc)
            except Exception:
                pass

        try:
            db.audit(username, "register", f"user:{username}", role)
        except Exception:
            pass

        return {"ok": True, "message": "Registered"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")


@router.post("/login")
def login(body: LoginReq):
    username = (body.username or "").strip()
    pw = body.password or ""
    if not username or not pw:
        raise HTTPException(status_code=400, detail="Username + password required")

    row = db.get_user(username)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    u = dict(row)

    if int(u.get("account_locked") or 0) == 1:
        raise HTTPException(status_code=403, detail="Account locked")

    if not _verify(pw, u.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _access_token(
        u.get("username") or username,
        u.get("role") or "",
        u.get("broker_status") or "none",
        u.get("broker_mc"),
    )

    try:
        db.audit(username, "login", f"user:{username}", None)
    except Exception:
        pass

    return {
        "ok": True,
        "token": token,
        "role": u.get("role"),
        "broker_status": u.get("broker_status"),
        "broker_mc": u.get("broker_mc"),
    }


@router.post("/forgot-password")
def forgot_password(body: ForgotReq):
    username = (body.username or "").strip()
    if not username:
        return {"ok": True}

    row = db.get_user(username)
    if not row:
        return {"ok": True}

    u = dict(row)
    email = (u.get("email") or "").strip().lower()
    if not email:
        return {"ok": True}

    token = _reset_token(username)
    base = (os.environ.get("RESET_URL_BASE") or "").rstrip("/")
    link = f"{base}/reset-password?token={token}" if base else f"/reset-password?token={token}"

    _send_email(
        email,
        "Chequmate – Password Reset",
        (
            "You requested a password reset.\n\n"
            f"Reset link (valid {RESET_EXP_MIN} minutes):\n{link}\n\n"
            "If you didn’t request this, ignore this email.\n"
        ),
    )
    return {"ok": True}


@router.post("/password-reset/request")
def password_reset_request(body: ForgotReq):
    return forgot_password(body)


@router.post("/reset-password")
def reset_password(body: ResetReq):
    username = _decode_reset(body.token)

    if len(body.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        with db._conn() as con:
            con.execute(
                "UPDATE users SET password_hash=? WHERE username=?",
                (_hash(body.new_password), username),
            )
        try:
            db.audit(username, "password_reset", f"user:{username}", None)
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset failed: {e}")


@router.post("/password-reset/confirm")
def password_reset_confirm(body: ResetReq):
    return reset_password(body)
