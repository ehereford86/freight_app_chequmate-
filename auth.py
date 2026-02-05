from __future__ import annotations

import os
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import jwt

import db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.environ.get("SECRET_KEY", "dev-secret")
JWT_ALGO = "HS256"

ACCESS_EXP_HOURS = 12
RESET_EXP_MIN = 30  # minutes


# -------------------
# DB / schema helpers
# -------------------
def _connect():
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _ensure_schema():
    con = _connect()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              username TEXT PRIMARY KEY,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL,
              email TEXT,
              broker_mc TEXT,
              broker_status TEXT NOT NULL DEFAULT 'none',
              created_at TEXT NOT NULL
            )
            """
        )

        # If table existed without email, add it.
        cols = [r["name"] for r in con.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN email TEXT")

        if "broker_mc" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN broker_mc TEXT")

        if "broker_status" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN broker_status TEXT NOT NULL DEFAULT 'none'")

        if "created_at" not in cols:
            con.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

        con.commit()
    finally:
        con.close()


_ensure_schema()


def _hash(pw: str) -> str:
    return pwd_context.hash(pw)


def _verify(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


def _send_email(to_email: str, subject: str, body: str):
    # Fail loudly if SMTP isn't configured correctly
    required = ["SMTP_FROM", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"]
    for k in required:
        if not os.environ.get(k):
            raise RuntimeError(f"Missing env var: {k}")

    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)


def _make_access_token(username: str, role: str) -> str:
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_EXP_HOURS),
        "scope": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _make_reset_token(username: str) -> str:
    payload = {
        "username": username,
        "exp": datetime.utcnow() + timedelta(minutes=RESET_EXP_MIN),
        "scope": "password_reset",
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


# -------------------
# Models
# -------------------
class RegisterReq(BaseModel):
    username: str
    password: str
    role: str
    email: EmailStr | None = None
    broker_mc: str | None = None


class LoginReq(BaseModel):
    username: str
    password: str


class ForgotReq(BaseModel):
    username: str


class ResetReq(BaseModel):
    token: str
    new_password: str


# -------------------
# Auth endpoints
# -------------------
@router.post("/register")
def register(body: RegisterReq):
    u = body.username.strip()
    p = body.password

    if not u:
        raise HTTPException(status_code=400, detail="Username required")
    if len(p) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    role = (body.role or "").strip().lower()
    if role not in ("broker", "dispatcher", "driver"):
        raise HTTPException(status_code=400, detail="Invalid role")

    # Traditional rule: you can't do password recovery without an email.
    if not body.email:
        raise HTTPException(status_code=400, detail="Email is required")

    broker_status = "none"
    broker_mc = None
    if role == "broker":
        broker_status = "pending"
        broker_mc = (body.broker_mc or "").strip()
        if not broker_mc:
            raise HTTPException(status_code=400, detail="broker_mc is required for brokers")

    con = _connect()
    try:
        existing = con.execute("SELECT username FROM users WHERE username=?", (u,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

        con.execute(
            """
            INSERT INTO users (username, password_hash, role, email, broker_mc, broker_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (u, _hash(p), role, str(body.email), broker_mc, broker_status, datetime.utcnow().isoformat()),
        )
        con.commit()
        return {"ok": True, "message": "Registered"}
    finally:
        con.close()


@router.post("/login")
def login(body: LoginReq):
    u = body.username.strip()
    p = body.password

    con = _connect()
    try:
        row = con.execute(
            "SELECT username, password_hash, role, broker_status, broker_mc FROM users WHERE username=?",
            (u,),
        ).fetchone()
        if not row or not _verify(p, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = _make_access_token(row["username"], row["role"])
        return {
            "ok": True,
            "token": token,
            "role": row["role"],
            "broker_status": row["broker_status"],
            "broker_mc": row["broker_mc"],
        }
    finally:
        con.close()


# -------------------
# Forgot / reset password
# -------------------
@router.post("/forgot-password")
def forgot_password(body: ForgotReq):
    con = _connect()
    try:
        row = con.execute(
            "SELECT username, email FROM users WHERE username=?",
            (body.username.strip(),),
        ).fetchone()

        # Do NOT reveal if the user exists.
        if not row:
            return {"ok": True}

        if not row["email"]:
            # Still don't reveal existence; just behave like success.
            # Admin can set email later.
            return {"ok": True}

        token = _make_reset_token(row["username"])
        base = os.environ.get("RESET_URL_BASE", "").rstrip("/")
        if not base:
            raise RuntimeError("RESET_URL_BASE is not set")
        link = f"{base}/reset-ui?token={token}"

        _send_email(
            row["email"],
            "Chequmate – Password Reset",
            (
                "You requested a password reset.\n\n"
                f"Reset link (valid {RESET_EXP_MIN} minutes):\n{link}\n\n"
                "If you didn’t request this, ignore this email."
            ),
        )

        return {"ok": True}
    finally:
        con.close()


@router.post("/reset-password")
def reset_password(body: ResetReq):
    username = _decode_reset(body.token)

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    con = _connect()
    try:
        con.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (_hash(body.new_password), username),
        )
        con.commit()
        return {"ok": True}
    finally:
        con.close()
