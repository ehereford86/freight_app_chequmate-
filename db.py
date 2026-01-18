import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent / "freight.db"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with _conn() as con:
        # Users table (create if missing)
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            mc_number TEXT,
            broker_status TEXT DEFAULT 'none',
            email TEXT,
            created_at TEXT
        )
        """)

        # Make sure columns exist (safe migration for older dbs)
        cols = {r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()}

        def add_col(name, sqltype, default_sql=None):
            nonlocal cols
            if name in cols:
                return
            stmt = f"ALTER TABLE users ADD COLUMN {name} {sqltype}"
            if default_sql is not None:
                stmt += f" DEFAULT {default_sql}"
            con.execute(stmt)
            cols.add(name)

        add_col("broker_mc", "TEXT", "NULL")
        add_col("broker_status", "TEXT", "'none'")
        add_col("email", "TEXT", "NULL")
        add_col("mc_number", "TEXT", "NULL")

        # Password resets table
        con.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # Broker request table (optional)
        con.execute("""
        CREATE TABLE IF NOT EXISTS broker_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            broker_mc TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        con.commit()

def create_user(username: str, password_hash: str, role: str, broker_mc: str | None = None, broker_status: str = "none", email: str | None = None, mc_number: str | None = None):
    with _conn() as con:
        con.execute(
            """
            INSERT INTO users (username, password_hash, role, broker_mc, broker_status, email, mc_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, password_hash, role, broker_mc, broker_status, email, mc_number, now_iso()),
        )
        con.commit()

def get_user(username: str):
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def set_password(username: str, password_hash: str):
    with _conn() as con:
        con.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        con.commit()

def set_email(username: str, email: str):
    with _conn() as con:
        con.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
        con.commit()

def set_broker_status(username: str, status: str):
    with _conn() as con:
        con.execute("UPDATE users SET broker_status = ? WHERE username = ?", (status, username))
        con.commit()

def list_broker_requests():
    with _conn() as con:
        return con.execute("SELECT * FROM broker_requests ORDER BY id DESC").fetchall()

def add_broker_request(username: str, broker_mc: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO broker_requests (username, broker_mc, created_at) VALUES (?, ?, ?)",
            (username, broker_mc, now_iso()),
        )
        con.commit()

def delete_broker_request(username: str):
    with _conn() as con:
        con.execute("DELETE FROM broker_requests WHERE username = ?", (username,))
        con.commit()

def create_reset(username: str, token: str, expires_at: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO password_resets (username, token, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (username, token, expires_at, now_iso()),
        )
        con.commit()

def get_reset(username: str, token: str):
    with _conn() as con:
        return con.execute(
            """
            SELECT * FROM password_resets
            WHERE username = ? AND token = ?
            ORDER BY id DESC LIMIT 1
            """,
            (username, token),
        ).fetchone()

def delete_resets(username: str):
    with _conn() as con:
        con.execute("DELETE FROM password_resets WHERE username = ?", (username,))
        con.commit()
