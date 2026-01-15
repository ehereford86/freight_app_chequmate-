import os
import sqlite3
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, APIRouter
from fastapi.security import OAuth2PasswordBearer

# ---------------------
# SECURITY CONFIG
# ---------------------
SECRET_KEY = os.getenv("SECRET_KEY", "chequmat_super_secret_key_change_later")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

DB_FILE = "users.db"

router = APIRouter()

# ---------------------
# DATABASE
# ---------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY,
          username TEXT UNIQUE,
          password TEXT,
          mc_number TEXT,
          role TEXT,
          broker_status TEXT DEFAULT 'none'
      )
    """)
    conn.commit()
    conn.close()

def get_user_record(username: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT username, password, role, mc_number, broker_status FROM users WHERE username=?",
        (username,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "username": row[0],
        "password": row[1],
        "role": row[2],
        "mc_number": row[3] or "",
        "broker_status": row[4] or "none",
    }

# ---------------------
# PASSWORD TOOLS
# ---------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)

# ---------------------
# USERS
# ---------------------
def create_user(username: str, password: str, role: str = "dispatcher"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE username=?", (username,))
    if c.fetchone():
        conn.close()
        return {"error": "Username exists"}

    hashed = hash_password(password)
    c.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, hashed, role)
    )
    conn.commit()
    conn.close()
    return {"success": True, "username": username, "role": role}

def authenticate_user(username: str, password: str):
    user = get_user_record(username)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return {
        "username": user["username"],
        "role": user["role"],
        "mc_number": user["mc_number"],
        "broker_status": user["broker_status"],
    }

def set_broker_request(username: str, mc_number: str, status: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET broker_status=?, mc_number=? WHERE username=?",
        (status, mc_number, username)
    )
    conn.commit()
    conn.close()
    return {"success": True, "username": username, "broker_status": status, "mc_number": mc_number}

def set_user_role(username: str, role: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET role=? WHERE username=?", (role, username))
    conn.commit()
    conn.close()
    return {"success": True, "username": username, "role": role}

# ---------------------
# JWT
# ---------------------
def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = data.copy()
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = get_user_record(username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return {
            "username": user["username"],
            "role": user["role"],
            "mc_number": user["mc_number"],
            "broker_status": user["broker_status"],
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid or expired")

# ---------------------
# ROUTES
# ---------------------
@router.get("/register")
def register(username: str, password: str, role: str = "dispatcher"):
    # prevent self-registering as broker/broker_carrier
    if role in ("broker", "broker_carrier"):
        raise HTTPException(status_code=400, detail="Use broker-onboard to request broker access")
    return create_user(username, password, role)

@router.get("/login")
def login(username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/verify-token")
def verify_token(user=Depends(get_current_user)):
    return {
        "username": user["username"],
        "role": user["role"],
        "mc_number": user.get("mc_number", ""),
        "broker_status": user.get("broker_status", "none"),
    }

# ---------------------
# ADMIN (manual approval)
# ---------------------
def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return user

@router.get("/admin/approve-broker")
def admin_approve_broker(username: str, mc_number: str, role: str = "broker", admin=Depends(require_admin)):
    if role not in ("broker", "broker_carrier"):
        raise HTTPException(status_code=400, detail="role must be broker or broker_carrier")
    set_broker_request(username, mc_number, "approved")
    set_user_role(username, role)
    return {
        "success": True,
        "approved_username": username,
        "mc_number": mc_number,
        "new_role": role,
        "broker_status": "approved",
    }

@router.get("/admin/reject-broker")
def admin_reject_broker(username: str, admin=Depends(require_admin)):
    set_broker_request(username, "", "rejected")
    return {
        "success": True,
        "rejected_username": username,
        "broker_status": "rejected",
    }

@router.get("/admin/list-broker-requests")
def admin_list_broker_requests(admin=Depends(require_admin)):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, role, mc_number, broker_status FROM users WHERE broker_status != 'none'")
    rows = c.fetchall()
    conn.close()

    return [
        {"username": r[0], "role": r[1], "mc_number": r[2] or "", "broker_status": r[3] or "none"}
        for r in rows
    ]