import os
import sqlite3
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# ---------------------
# SECURITY CONFIG
# ---------------------

# Use Render env var in production. Falls back to local default.
SECRET_KEY = os.getenv("SECRET_KEY", "chequmat_super_secret_key_change_later")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

DB_FILE = "users.db"

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
    """Return full user row we care about, or None."""
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