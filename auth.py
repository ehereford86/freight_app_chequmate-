import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from passlib.context import CryptContext

import db

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = db.get_env("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = int(db.get_env("JWT_EXPIRE_MIN", "43200"))  # 30 days default

ROLES = {"driver", "dispatcher", "broker", "admin"}


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, pw_hash: str) -> bool:
    return pwd_context.verify(pw, pw_hash)


def make_token(payload: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MIN)
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
        if request.headers.get("content-type", "").startswith("application/json"):
            return await request.json()
    except Exception:
        pass
    return {}


def seed_admin_if_needed():
    admin_user = (db.get_env("ADMIN_USERNAME", "") or "").strip()
    admin_pass = (db.get_env("ADMIN_PASSWORD", "") or "").strip()
    if not admin_user or not admin_pass:
        return

    u = db.get_user(admin_user)
    if not u:
        db.create_user(
            admin_user,
            hash_password(admin_pass),
            role="admin",
            broker_mc=None,
            broker_status="approved",
        )
    else:
        if u["role"] != "admin":
            db.set_role(admin_user, "admin")


def get_current_user(request: Request):
    token = _bearer_token(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
        username = payload.get("username")
        if not username:
            return None
        return db.get_user(username)
    except JWTError:
        return None


def get_current_user_optional(request: Request):
    # Dependency-friendly alias used by other modules
    return get_current_user(request)


def require_user(request: Request):
    u = get_current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return u


def require_role(*allowed_roles: str):
    allowed = set(allowed_roles)

    def _dep(request: Request):
        u = require_user(request)
        if u["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return u

    return _dep


@router.get("/verify-token")
def verify_token(request: Request):
    u = get_current_user(request)
    if not u:
        return JSONResponse(status_code=401, content={"ok": False})
    return {
        "ok": True,
        "username": u["username"],
        "role": u["role"],
        "broker_status": u["broker_status"],
        "broker_mc": u["broker_mc"],
    }


# ---- LOGIN ----
@router.get("/login")
def login_get(username: str, password: str):
    u = db.get_user(username)
    if not u or not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = make_token({"username": u["username"], "role": u["role"]})
    return {"ok": True, "token": token, "role": u["role"], "broker_status": u["broker_status"]}


@router.post("/login")
async def login_post(request: Request):
    body = await read_json(request)
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username/password")

    u = db.get_user(username)
    if not u or not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = make_token({"username": u["username"], "role": u["role"]})
    return {"ok": True, "token": token, "role": u["role"], "broker_status": u["broker_status"]}


# ---- REGISTER ----
@router.get("/register")
def register_get(username: str, password: str, role: str = "driver", broker_mc: str | None = None):
    role = (role or "driver").lower().strip()
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
        db.create_broker_request(username, broker_mc)
    else:
        db.create_user(username, hash_password(password), role=role, broker_mc=None, broker_status=broker_status)

    return {"ok": True, "message": "Registered"}


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
        db.create_broker_request(username, broker_mc)
    else:
        db.create_user(username, hash_password(password), role=role, broker_mc=None, broker_status=broker_status)

    return {"ok": True, "message": "Registered"}


# ---- ADMIN: broker approval ----
@router.get("/admin/list-broker-requests")
def admin_list_brokers(status: str = "pending", u=Depends(require_role("admin"))):
    rows = db.list_broker_requests(status=status)
    return {"ok": True, "requests": [dict(r) for r in rows]}


@router.post("/admin/approve-broker")
async def admin_approve(request: Request, u=Depends(require_role("admin"))):
    body = await read_json(request)
    req_id = body.get("id")
    if req_id is None:
        raise HTTPException(status_code=400, detail="Missing id")

    db.set_broker_request_status(int(req_id), "approved")
    with db._conn() as con:
        r = con.execute("SELECT username FROM broker_requests WHERE id = ?", (int(req_id),)).fetchone()
    if r:
        db.set_broker_status(r["username"], "approved")
    return {"ok": True}


@router.post("/admin/reject-broker")
async def admin_reject(request: Request, u=Depends(require_role("admin"))):
    body = await read_json(request)
    req_id = body.get("id")
    if req_id is None:
        raise HTTPException(status_code=400, detail="Missing id")

    db.set_broker_request_status(int(req_id), "rejected")
    with db._conn() as con:
        r = con.execute("SELECT username FROM broker_requests WHERE id = ?", (int(req_id),)).fetchone()
    if r:
        db.set_broker_status(r["username"], "rejected")
    return {"ok": True}


# ---- Password reset (email comes next phase) ----
@router.post("/password-reset/request")
async def password_reset_request(request: Request):
    body = await read_json(request)
    username = (body.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Missing username")

    u = db.get_user(username)
    # Always respond generically so we don't leak whether the user exists
    if not u:
        return {"ok": True, "message": "If the user exists, a reset was created."}

    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    db.create_reset(username, token, expires_at.isoformat())

    # For now we return token (dev/testing). Next phase: email it.
    return {"ok": True, "token": token, "expires_at": expires_at.isoformat()}


@router.post("/password-reset/confirm")
async def password_reset_confirm(request: Request):
    body = await read_json(request)
    username = (body.get("username") or "").strip()
    token = (body.get("token") or "").strip()
    new_password = (body.get("new_password") or "").strip()

    if not username or not token:
        raise HTTPException(status_code=400, detail="Missing data")

    r = db.get_reset(username, token)
    if not r:
        raise HTTPException(status_code=400, detail="Invalid reset")

    expires_at = datetime.fromisoformat(r["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Reset expired")

    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    db.set_password(username, hash_password(new_password))
    db.delete_resets(username)
    return {"ok": True, "message": "Password updated. Please login."}
