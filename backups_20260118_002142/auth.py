from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext

import db

router = APIRouter()

# -----------------------------
# Security / JWT
# -----------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = db.get_env("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_HOURS = int(db.get_env("JWT_EXPIRE_HOURS", "24"))

def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(pw, hashed)
    except Exception:
        return False

def make_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def auth_user_from_request(request: Request):
    # Reads Authorization: Bearer <token>
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        return None
    u = db.get_user(username)
    return u

# -----------------------------
# Request bodies (POST support)
# -----------------------------
class LoginBody(BaseModel):
    username: str
    password: str

class RegisterBody(BaseModel):
    username: str
    password: str
    role: str = "driver"
    broker_mc: str | None = None

# -----------------------------
# Login / Register (GET + POST)
# -----------------------------
@router.get("/login")
def login_get(username: str, password: str):
    u = db.get_user(username)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = make_token(u["username"], u["role"])
    return {"ok": True, "token": token, "role": u["role"], "broker_status": u.get("broker_status", "none")}

@router.post("/login")
def login_post(body: LoginBody):
    # This is what your UI fetch() is doing (POST). Fixes 405 immediately.
    return login_get(body.username, body.password)

@router.get("/register")
def register_get(username: str, password: str, role: str = "driver", broker_mc: str | None = None):
    role_norm = (role or "").strip().lower()
    if role_norm not in ("broker", "dispatcher", "driver"):
        raise HTTPException(status_code=400, detail="Invalid role")

    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if role_norm == "broker":
        if not broker_mc or not broker_mc.strip():
            raise HTTPException(status_code=400, detail="Broker MC# is required for brokers")

    if db.get_user(username):
        raise HTTPException(status_code=400, detail="Username already exists")

    broker_status = "none"
    broker_mc_clean = None
    if role_norm == "broker":
        broker_status = "pending"   # admin approval required
        broker_mc_clean = broker_mc.strip()

    db.create_user(
        username=username,
        password_hash=hash_password(password),
        role=role_norm,
        broker_mc=broker_mc_clean,
        broker_status=broker_status,
    )
    return {"ok": True, "message": "Registered", "role": role_norm, "broker_status": broker_status}

@router.post("/register")
def register_post(body: RegisterBody):
    return register_get(body.username, body.password, body.role, body.broker_mc)

@router.get("/verify-token")
def verify_token(request: Request):
    u = auth_user_from_request(request)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"ok": True, "username": u["username"], "role": u["role"], "broker_status": u.get("broker_status", "none")}

@router.get("/logout")
def logout():
    # Stateless JWT: client deletes token. Endpoint kept for UI convenience.
    return {"ok": True}

