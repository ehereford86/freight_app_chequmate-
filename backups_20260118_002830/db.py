import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent / "freight.db"


def get_env(key: str, default: str | None = None) -> str | None:
    """
    Safe env getter used by other modules (auth/pricing/etc).
    Returns default if missing/blank.
    """
    val = os.environ.get(key)
    if val is None:
        return default
    val = val.strip()
    return val if val else default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        # Users
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'driver',
                broker_status TEXT NOT NULL DEFAULT 'none',
                mc_number TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Password reset tokens
        con.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Broker onboarding requests (admin approval)
        con.execute("""
            CREATE TABLE IF NOT EXISTS broker_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                mc_number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)

        con.commit()


# ---------- users ----------
def get_user(username: str):
    with _conn() as con:
        return con.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()


def create_user(username: str, password_hash: str, role: str, mc_number: str | None = None, broker_status: str = "none"):
    with _conn() as con:
        con.execute("""
            INSERT INTO users (username, password_hash, role, broker_status, mc_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, password_hash, role, broker_status, mc_number, now_iso()))
        con.commit()


def set_password(username: str, password_hash: str):
    with _conn() as con:
        con.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username)
        )
        con.commit()


def set_broker_status(username: str, status: str):
    with _conn() as con:
        con.execute(
            "UPDATE users SET broker_status = ? WHERE username = ?",
            (status, username)
        )
        con.commit()


# ---------- broker requests ----------
def create_broker_request(username: str, mc_number: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO broker_requests (username, mc_number, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (username, mc_number, now_iso()))
        con.commit()


def list_broker_requests(status: str = "pending"):
    with _conn() as con:
        return con.execute("""
            SELECT * FROM broker_requests
            WHERE status = ?
            ORDER BY id DESC
        """, (status,)).fetchall()


def approve_broker_request(request_id: int):
    with _conn() as con:
        req = con.execute("SELECT * FROM broker_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return None
        con.execute("UPDATE broker_requests SET status = 'approved' WHERE id = ?", (request_id,))
        con.execute("UPDATE users SET broker_status = 'approved' WHERE username = ?", (req["username"],))
        con.commit()
        return req


def reject_broker_request(request_id: int):
    with _conn() as con:
        req = con.execute("SELECT * FROM broker_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return None
        con.execute("UPDATE broker_requests SET status = 'rejected' WHERE id = ?", (request_id,))
        con.commit()
        return req


# ---------- password resets ----------
def create_reset(username: str, token: str, expires_at_iso: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO password_resets (username, token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        """, (username, token, expires_at_iso, now_iso()))
        con.commit()


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
