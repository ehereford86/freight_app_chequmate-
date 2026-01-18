import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

DB_PATH = Path(os.environ.get("DB_PATH", "freight.db"))

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        # Users table
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT,
            mc_number TEXT,
            broker_status TEXT DEFAULT 'none',
            created_at TEXT NOT NULL
        )
        """)

        # Broker onboarding requests (admin approval)
        con.execute("""
        CREATE TABLE IF NOT EXISTS broker_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            mc_number TEXT NOT NULL,
            company_name TEXT,
            contact_name TEXT,
            phone TEXT,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT,
            notes TEXT
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
        con.commit()

def user_by_username(username: str):
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def create_user(username: str, password_hash: str, role: str, email: Optional[str] = None,
                mc_number: Optional[str] = None, broker_status: str = "none") -> None:
    with _conn() as con:
        con.execute("""
            INSERT INTO users (username, password_hash, role, email, mc_number, broker_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (username, password_hash, role, email, mc_number, broker_status, now_iso()))
        con.commit()

def set_password(username: str, password_hash: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        con.commit()

def set_email(username: str, email: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
        con.commit()

def set_broker_status(username: str, status: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET broker_status = ? WHERE username = ?", (status, username))
        con.commit()

def list_broker_requests(status: Optional[str] = None):
    with _conn() as con:
        if status:
            return con.execute("SELECT * FROM broker_requests WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        return con.execute("SELECT * FROM broker_requests ORDER BY id DESC").fetchall()

def create_broker_request(data: Dict[str, Any]) -> None:
    with _conn() as con:
        con.execute("""
            INSERT INTO broker_requests
              (username, mc_number, company_name, contact_name, phone, email, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            data.get("username"),
            data.get("mc_number"),
            data.get("company_name"),
            data.get("contact_name"),
            data.get("phone"),
            data.get("email"),
            now_iso()
        ))
        con.commit()

def update_broker_request(username: str, status: str, reviewed_by: str, notes: str = "") -> None:
    with _conn() as con:
        con.execute("""
            UPDATE broker_requests
            SET status = ?, reviewed_at = ?, reviewed_by = ?, notes = ?
            WHERE username = ?
        """, (status, now_iso(), reviewed_by, notes, username))
        con.commit()

def create_reset(username: str, token: str, expires_at_iso: str) -> None:
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

def delete_resets(username: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM password_resets WHERE username = ?", (username,))
        con.commit()
