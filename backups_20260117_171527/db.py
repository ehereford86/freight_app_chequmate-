import os
import highlight
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "app.db")))

def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con

def _has_column(con, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)

def ensure_schema():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        # Users
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'driver',           -- admin/broker/dispatcher/driver
            email TEXT,                                    -- may be added by migration
            broker_mc TEXT,                                -- which broker the user belongs to
            broker_status TEXT NOT NULL DEFAULT 'none',     -- none/pending/approved/rejected
            created_at TEXT NOT NULL
        )
        """)

        # Auto-migrate: add missing columns safely
        if not _has_column(con, "users", "email"):
            con.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if not _has_column(con, "users", "broker_mc"):
            con.execute("ALTER TABLE users ADD COLUMN broker_mc TEXT")
        if not _has_column(con, "users", "broker_status"):
            con.execute("ALTER TABLE users ADD COLUMN broker_status TEXT NOT NULL DEFAULT 'none'")
        if not _has_column(con, "users", "created_at"):
            con.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

        # Broker approval queue
        con.execute("""
        CREATE TABLE IF NOT EXISTS broker_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            mc TEXT NOT NULL,
            company_name TEXT,
            contact_email TEXT,
            status TEXT NOT NULL DEFAULT 'pending', -- pending/approved/rejected
            created_at TEXT NOT NULL
        )
        """)

        # Password reset tokens (MVP: token generation; email delivery can be added later)
        con.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        con.commit()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def get_user(username: str):
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def create_user(username: str, password_hash: str, role: str, email: str = None, broker_mc: str = None, broker_status: str = "none"):
    with _conn() as con:
        con.execute("""
            INSERT INTO users (username, password_hash, role, email, broker_mc, broker_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, password_hash, role, email, broker_mc, broker_status, now_iso()))
        con.commit()

def set_password(username: str, password_hash: str):
    with _conn() as con:
        con.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        con.commit()

def set_email(username: str, email: str):
    with _conn() as con:
        con.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
        con.commit()

def set_role(username: str, role: str):
    with _conn() as con:
        con.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        con.commit()

def set_broker_link(username: str, broker_mc: str, broker_status: str):
    with _conn() as con:
        con.execute("UPDATE users SET broker_mc = ?, broker_status = ? WHERE username = ?", (broker_mc, broker_status, username))
        con.commit()

# Broker requests
def create_broker_request(username: str, mc: str, company_name: str = None, contact_email: str = None):
    with _conn() as con:
        con.execute("""
            INSERT INTO broker_requests (username, mc, company_name, contact_email, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (username, mc, company_name, contact_email, now_iso()))
        con.commit()

def list_broker_requests(status: str = "pending"):
    with _conn() as con:
        return con.execute("""
            SELECT * FROM broker_requests
            WHERE status = ?
            ORDER BY id DESC
        """, (status,)).fetchall()

def set_broker_request_status(req_id: int, status: str):
    with _conn() as con:
        con.execute("UPDATE broker_requests SET status = ? WHERE id = ?", (status, req_id))
        con.commit()

def get_broker_request(req_id: int):
    with _conn() as con:
        return con.execute("SELECT * FROM broker_requests WHERE id = ?", (req_id,)).fetchone()

# Password resets
def create_reset(username: str, token: str, minutes_valid: int = 30):
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=minutes_valid)).isoformat()
    with _conn() as con:
        con.execute("""
            INSERT INTO password_resets (username, token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        """, (username, token, expires_at, now_iso()))
        con.commit()
    return expires_at

def get_reset(username: str, token: str):
    with _conn() as con:
        return con.execute("""
            SELECT * FROM password_resets
            WHERE username = ? AND token = ?
            ORDER BY id DESC LIMIT 1
        """, (username, token)).fetchone()

def delete_resets(username: str):
    with _conn() as con:
        con.execute("DELETE FROM password_resets WHERE username = ?", (username,))
        con.commit()
