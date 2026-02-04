from __future__ import annotations

import os
import sqlite3
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt

import db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.environ.get("SECRET_KEY", "dev-secret")
JWT_ALGO = "HS256"
RESET_EXP_MIN = 30  # minutes


# -------------------
# Helpers
# -------------------
def _connect():
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _hash(pw: str) -> str:
    return pwd_context.hash(pw)


def _verify(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


def _send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)


def _reset_token(username: str) -> str:
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
            raise ValueError()
        return data["username"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")


# -------------------
# Models
# -------------------
class ForgotReq(BaseModel):
    username: str


class ResetReq(BaseModel):
    token: str
    new_password: str


# -------------------
# Forgot password
# -------------------
@router.post("/forgot-password")
def forgot_password(body: ForgotReq):
    con = _connect()
    try:
        row = con.execute(
            "SELECT username, email FROM users WHERE username=?",
            (body.username,),
        ).fetchone()

        # Do NOT reveal if user exists
        if not row:
            return {"ok": True}

        token = _reset_token(row["username"])
        base = os.environ.get("RESET_URL_BASE", "").rstrip("/")
        link = f"{base}/reset-password?token={token}"

        _send_email(
            row["email"],
            "Chequmate – Password Reset",
            f"""
You requested a password reset.

Reset link (valid {RESET_EXP_MIN} minutes):
{link}

If you didn’t request this, ignore this email.
""".strip(),
        )

        return {"ok": True}
    finally:
        con.close()


# -------------------
# Reset password
# -------------------
@router.post("/reset-password")
def reset_password(body: ResetReq):
    username = _decode_reset(body.token)

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password too short")

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
