import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "freight.db")))

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_env(name: str, default: str | None = None) -> str | None:
    """
    Safe environment variable helper. Keeps all env lookups consistent.
    """
    return os.environ.get(name, default)

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _table_cols(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}

def _add_col_if_missing(con: sqlite3.Connection, table: str, name: str, sqltype: str, default_sql: str | None = None) -> None:
    cols = _table_cols(con, table)
    if name in cols:
        return
    stmt = f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"
    if default_sql is not None:
        stmt += f" DEFAULT {default_sql}"
    con.execute(stmt)

def init_db() -> None:
    with _conn() as con:
        # Base schema (keep compatible with existing DBs)
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
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

        # Migrations: add columns if missing
        _add_col_if_missing(con, "users", "broker_mc", "TEXT", "NULL")
        _add_col_if_missing(con, "users", "broker_status", "TEXT", "'none'")
        _add_col_if_missing(con, "users", "email", "TEXT", "NULL")
        _add_col_if_missing(con, "users", "mc_number", "TEXT", "NULL")  # legacy compatibility
        con.commit()

def create_user(username: str, password_hash: str, role: str, broker_mc: Optional[str] = None, broker_status: str = "none") -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO users (username, password_hash, role, broker_mc, broker_status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (username, password_hash, role, broker_mc, broker_status, now_iso()),
        )
        con.commit()

def get_user(username: str):
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE username = ? LIMIT 1", (username,)).fetchone()
        return row

def set_password(username: str, password_hash: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        con.commit()

def set_email(username: str, email: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
        con.commit()

def create_reset(username: str, token: str, expires_at_iso: str) -> None:
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

def delete_resets(username: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM password_resets WHERE username = ?", (username,))
        con.commit()
