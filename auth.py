import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from passlib.context import CryptContext

import db
import mailer

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = (db.get_env("JWT_SECRET", "dev-secret-change-me") or "dev-secret-change-me").strip()
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = int((db.get_env("JWT_EXPIRE_MIN", "43200") or "43200"))  # 30 days default

ROLES = {"driver", "dispatcher", "broker", "admin"}

# Password reset behavior:
RESET_TOKEN_MIN = int((db.get_env("RESET_TOKEN_MIN", "30") or "30"))  # token expiry in minutes
RESET_RETURN_TOKEN = (db.get_env("RESET_RETURN_TOKEN", "1") or "1").strip() == "1"  # dev/testing default ON


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, pw_hash: str) -> bool:
    return pwd_context.verify(pw, pw_hash)


def make_token(payload: dict) -> str:
    exp = _now_utc() + timedelta(minutes=JWT_EXPIRE_MIN)
    data = dict(payload)
    data["exp"] = exp
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


def _bearer_token(request: Request) -> str | None:
    h = request.headers.get("authorization") or request.headers.get("Authorization")
    if not h:
        return None
    if not h.lower().startswith("bearer "):
        return None
    return h.split(" ", 1)[1].strip()


async def read_json(request: Request) -> dict:
    try:
        if (request.headers.get("content-type") or "").startswith("application/json"):
            return await request.json()
    except Exception:
        pass
    return {}


def get_current_user(request: Request):
    token = _bearer_token(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
        username = payload.get("username")
        if not username:
            return None
        u = db.get_user(username)
        return dict(u) if u else None
    except JWTError:
        return None


# pricing.py expects this import
def get_current_user_optional(request: Request):
    return get_current_user(request)


def require_user(request: Request):
    u = get_current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if int(u.get("account_locked") or 0) == 1:
        raise HTTPException(status_code=403, detail="Account locked")
    return u


def require_role(*allowed_roles: str):
    allowed = set(allowed_roles)

    def _dep(request: Request):
        u = require_user(request)
        if u["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return u

    return _dep


def require_driver():
    return require_role("driver")


def require_dispatcher_linked():
    def _dep(request: Request):
        u = require_user(request)
        if u["role"] != "dispatcher":
            raise HTTPException(status_code=403, detail="Forbidden")
        if not (u.get("broker_mc") or "").strip():
            raise HTTPException(status_code=403, detail="Dispatcher not linked to broker")
        return u

    return _dep


def require_broker_approved():
    def _dep(request: Request):
        u = require_user(request)
        if u["role"] != "broker":
            raise HTTPException(status_code=403, detail="Forbidden")
        if (u.get("broker_status") or "") != "approved":
            raise HTTPException(status_code=403, detail="Broker not approved")
        if not (u.get("broker_mc") or "").strip():
            raise HTTPException(status_code=403, detail="Broker missing broker_mc")
        return u

    return _dep


# --- Compatibility functions (fmcsa.py expects these imports) ---
def set_user_role(username: str, role: str) -> None:
    role = (role or "").strip().lower()
    if role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    if hasattr(db, "set_user_role"):
        db.set_user_role(username, role)
        return

    with db._conn() as con:
        con.execute("UPDATE users SET role=? WHERE username=?", (role, username))
        con.commit()


def set_broker_request(username: str, mc_number: str, status: str = "pending") -> None:
    mc_number = (mc_number or "").strip()
    status = (status or "").strip().lower() or "pending"
    if status not in {"pending", "approved", "rejected"}:
        status = "pending"

    if hasattr(db, "create_broker_request"):
        try:
            db.create_broker_request(username, mc_number)
        except Exception:
            pass

    with db._conn() as con:
        con.execute(
            "UPDATE users SET role='broker', broker_status=?, broker_mc=? WHERE username=?",
            (status, mc_number or None, username),
        )
        con.commit()


def _ensure_password_reset_table() -> None:
    with db._conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
              token_hash TEXT PRIMARY KEY,
              username TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        con.commit()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _set_user_password(username: str, new_hash: str) -> None:
    # prefer db helper if it exists
    if hasattr(db, "set_password_hash"):
        db.set_password_hash(username, new_hash)
        return
    with db._conn() as con:
        con.execute("UPDATE users SET password_hash=? WHERE username=?", (new_hash, username))
        con.commit()


@router.get("/verify-token")
def verify_token(request: Request):
    u = get_current_user(request)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False})
    return {
        "ok": True,
        "username": u["username"],
        "role": u["role"],
        "broker_status": u.get("broker_status"),
        "broker_mc": u.get("broker_mc"),
        "email": u.get("email"),
        "account_locked": bool(int(u.get("account_locked") or 0)),
        "is_admin": (u.get("role") == "admin"),
    }


@router.post("/me/set-email")
async def me_set_email(request: Request, u=Depends(require_user)):
    body = await read_json(request)
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Missing email")
    if len(email) > 254:
        raise HTTPException(status_code=400, detail="Bad email")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Bad email format")
    db.set_email(u["username"], email)
    try:
        db.audit(u["username"], "set_email", "user:" + u["username"], None)
    except Exception:
        pass
    return {"ok": True}


@router.post("/login")
async def login_post(request: Request):
    body = await read_json(request)
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username/password")

    row = db.get_user(username)
    u = dict(row) if row else None
    if not u or not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if int(u.get("account_locked") or 0) == 1:
        raise HTTPException(status_code=403, detail="Account locked")

    token = make_token({"username": u["username"], "role": u["role"]})
    return {"ok": True, "token": token, "role": u["role"], "broker_status": u.get("broker_status"), "broker_mc": u.get("broker_mc")}


@router.post("/register")
async def register_post(request: Request):
    body = await read_json(request)
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    role = (body.get("role") or "driver").lower().strip()
    broker_mc = (body.get("broker_mc") or body.get("brokerMC") or "").strip() or None

    if role not in ROLES or role == "admin":
        raise HTTPException(status_code=400, detail="Invalid role")
    if not username or not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Bad username/password")

    if db.get_user(username):
        raise HTTPException(status_code=400, detail="Username already exists")

    broker_status = "none"
    if role == "broker":
        if not broker_mc:
            raise HTTPException(status_code=400, detail="Broker MC# required")
        broker_status = "pending"

    db.create_user(username, hash_password(password), role=role, broker_mc=broker_mc, broker_status=broker_status)

    if role == "broker":
        try:
            db.create_broker_request(username, broker_mc or "")
        except Exception:
            pass
        try:
            db.audit(username, "register_broker", "user:" + username, f'{{"broker_mc":"{broker_mc}","broker_status":"{broker_status}"}}')
        except Exception:
            pass
    else:
        try:
            db.audit(username, "register", "user:" + username, f'{{"role":"{role}"}}')
        except Exception:
            pass

    return {"ok": True, "message": "Registered"}


# -----------------------------
# Password Reset (REAL FLOW)
# -----------------------------

@router.post("/password-reset/request")
async def password_reset_request(request: Request):
    """
    Request a password reset token for username/email.
    - If email sending is configured, send it.
    - For dev/testing, optionally return token in response (RESET_RETURN_TOKEN=1).
    """
    body = await read_json(request)
    who = (body.get("username_or_email") or body.get("username") or body.get("email") or "").strip()
    if not who:
        raise HTTPException(status_code=400, detail="Missing username_or_email")

    _ensure_password_reset_table()

    # Lookup user by username OR email
    user = None
    try:
        row = db.get_user(who)
        user = dict(row) if row else None
    except Exception:
        user = None

    if not user:
        # try email lookup
        try:
            with db._conn() as con:
                row = con.execute("SELECT * FROM users WHERE lower(email)=?", (who.lower(),)).fetchone()
                user = dict(row) if row else None
        except Exception:
            user = None

    # Always respond OK to avoid account enumeration
    if not user:
        return {"ok": True}

    if int(user.get("account_locked") or 0) == 1:
        return {"ok": True}

    token = secrets.token_urlsafe(28)
    th = _hash_token(token)
    expires = _now_utc() + timedelta(minutes=RESET_TOKEN_MIN)

    with db._conn() as con:
        # clear old tokens for this user (keeps table clean)
        try:
            con.execute("DELETE FROM password_resets WHERE username=?", (user["username"],))
        except Exception:
            pass
        con.execute(
            "INSERT OR REPLACE INTO password_resets (token_hash, username, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (th, user["username"], _iso(expires), _iso(_now_utc())),
        )
        con.commit()

    # Send email if we have one and mailer supports it
    email = (user.get("email") or "").strip().lower()
    if email:
        try:
            # Keep message simple; testers can copy token.
            subject = "Chequmate password reset"
            text = f"Your Chequmate password reset token:\n\n{token}\n\nThis token expires in {RESET_TOKEN_MIN} minutes."
            if hasattr(mailer, "send_email"):
                mailer.send_email(email, subject, text)
        except Exception:
            pass

    # For testing/dev you often want the token returned
    if RESET_RETURN_TOKEN:
        return {"ok": True, "reset_token": token, "expires_minutes": RESET_TOKEN_MIN}

    return {"ok": True, "expires_minutes": RESET_TOKEN_MIN}


@router.post("/password-reset/confirm")
async def password_reset_confirm(request: Request):
    """
    Confirm reset token and set new password.
    """
    body = await read_json(request)
    token = (body.get("token") or "").strip()
    new_password = (body.get("new_password") or "").strip()

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Missing token/new_password")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    _ensure_password_reset_table()

    th = _hash_token(token)
    with db._conn() as con:
        row = con.execute(
            "SELECT username, expires_at FROM password_resets WHERE token_hash=?",
            (th,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        username = row["username"] if isinstance(row, dict) else row[0]
        expires_at = row["expires_at"] if isinstance(row, dict) else row[1]

        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            exp = _now_utc() - timedelta(minutes=1)

        if _now_utc() > exp:
            # expire and delete
            con.execute("DELETE FROM password_resets WHERE token_hash=?", (th,))
            con.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        # set password
        _set_user_password(username, hash_password(new_password))

        # consume token
        con.execute("DELETE FROM password_resets WHERE token_hash=?", (th,))
        con.commit()

    try:
        db.audit(username, "password_reset", "user:" + username, None)
    except Exception:
        pass

    return {"ok": True}
