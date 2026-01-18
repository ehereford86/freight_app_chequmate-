import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "users.db"

def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,                 -- driver | dispatcher | broker | admin
            broker_status TEXT NOT NULL,         -- none | pending | approved | rejected
            mc_number TEXT,
            legal_name TEXT,
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """)
        con.commit()

    _seed_admin_from_env()

def _seed_admin_from_env():
    admin_user = os.getenv("ADMIN_USERNAME", "").strip()
    admin_pass = os.getenv("ADMIN_PASSWORD", "").strip()
    admin_email = os.getenv("ADMIN_EMAIL", "").strip()

    # If not set, do nothing. (You MUST set on Render for production.)
    if not admin_user or not admin_pass:
        return

    # Hashing is done in auth.py; we import lazily to avoid circular imports.
    from auth import hash_password

    with _conn() as con:
        row = con.execute("SELECT username FROM users WHERE username = ?", (admin_user,)).fetchone()
        if row:
            return

        con.execute("""
            INSERT INTO users (username, email, password_hash, role, broker_status, mc_number, legal_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            admin_user,
            admin_email or None,
            hash_password(admin_pass),
            "admin",
            "approved",
            None,
            None,
            datetime.utcnow().isoformat()
        ))
        con.commit()

def get_user(username: str):
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def create_user(username: str, email: str | None, password_hash: str, role: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO users (username, email, password_hash, role, broker_status, mc_number, legal_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            email,
            password_hash,
            role,
            "none",
            None,
            None,
            datetime.utcnow().isoformat()
        ))
        con.commit()

def set_broker_request(username: str, mc_number: str, legal_name: str):
    with _conn() as con:
        con.execute("""
            UPDATE users
            SET mc_number = ?, legal_name = ?, broker_status = ?
            WHERE username = ?
        """, (mc_number, legal_name, "pending", username))
        con.commit()

def list_pending_brokers():
    with _conn() as con:
        return con.execute("""
            SELECT username, email, mc_number, legal_name, broker_status, role, created_at
            FROM users
            WHERE broker_status = 'pending'
            ORDER BY created_at DESC
        """).fetchall()

def approve_broker(username: str):
    with _conn() as con:
        con.execute("""
            UPDATE users
            SET broker_status = 'approved', role = 'broker'
            WHERE username = ?
        """, (username,))
        con.commit()

def reject_broker(username: str):
    with _conn() as con:
        con.execute("""
            UPDATE users
            SET broker_status = 'rejected'
            WHERE username = ?
        """, (username,))
        con.commit()

def set_password(username: str, new_hash: str):
    with _conn() as con:
        con.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))
        con.commit()

def save_reset_token(username: str, token: str, expires_at_iso: str):
    with _conn() as con:
        con.execute("INSERT INTO password_resets (username, token, expires_at) VALUES (?, ?, ?)",
                    (username, token, expires_at_iso))
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
