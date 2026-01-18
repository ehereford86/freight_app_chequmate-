import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(os.getenv("DB_PATH", "freight.db")).resolve()

def get_env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None and v != "" else default

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'driver',
            broker_mc TEXT DEFAULT NULL,
            broker_status TEXT NOT NULL DEFAULT 'none',
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS broker_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            broker_mc TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """)
        con.commit()

def get_user(username: str):
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def create_user(username: str, password_hash: str, role: str, broker_mc: str | None = None, broker_status: str = "none"):
    with _conn() as con:
        con.execute(
            "INSERT INTO users (username, password_hash, role, broker_mc, broker_status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (username, password_hash, role, broker_mc, broker_status, now_iso()),
        )
        con.commit()

def set_password(username: str, password_hash: str):
    with _conn() as con:
        con.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        con.commit()

def set_role(username: str, role: str):
    with _conn() as con:
        con.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        con.commit()

def set_broker_status(username: str, status: str):
    with _conn() as con:
        con.execute("UPDATE users SET broker_status = ? WHERE username = ?", (status, username))
        con.commit()

def set_broker_mc(username: str, broker_mc: str):
    with _conn() as con:
        con.execute("UPDATE users SET broker_mc = ? WHERE username = ?", (broker_mc, username))
        con.commit()

def create_broker_request(username: str, broker_mc: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO broker_requests (username, broker_mc, status, created_at) VALUES (?, ?, 'pending', ?)",
            (username, broker_mc, now_iso()),
        )
        con.commit()

def list_broker_requests(status: str = "pending"):
    with _conn() as con:
        return con.execute("SELECT * FROM broker_requests WHERE status = ? ORDER BY id DESC", (status,)).fetchall()

def set_broker_request_status(req_id: int, status: str):
    with _conn() as con:
        con.execute("UPDATE broker_requests SET status = ? WHERE id = ?", (status, req_id))
        con.commit()

def create_reset(username: str, token: str, expires_at_iso: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO password_resets (username, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (username, token, expires_at_iso, now_iso()),
        )
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
