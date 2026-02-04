from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------
# Environment helpers
# ---------------------------

def get_env(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    if v is None:
        return default
    return str(v)

def _is_render() -> bool:
    # Render sets these commonly; any one is enough.
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER_GIT_COMMIT"))

def _default_db_path() -> str:
    # On Render, repo directory can be read-only; /tmp is writable.
    if _is_render():
        return "/tmp/chequmate.db"
    # Local dev: keep in project directory
    here = Path(__file__).resolve().parent
    return str(here / "chequmate.db")

DB_PATH = (get_env("DB_PATH", "") or "").strip() or _default_db_path()

def _ensure_parent_dir(path: str) -> None:
    p = Path(path).expanduser().resolve()
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ---------------------------
# SQLite connection
# ---------------------------

@contextmanager
def _conn():
    _ensure_parent_dir(DB_PATH)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        # WAL may fail in some environments; ignore.
        pass
    con.execute("PRAGMA foreign_keys=ON;")
    try:
        _init_db(con)
        yield con
        con.commit()
    finally:
        con.close()

def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)

def _col_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)

def _add_col_if_missing(con: sqlite3.Connection, table: str, col: str, col_type: str, default_sql: str) -> None:
    if not _col_exists(con, table, col):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {default_sql}")

def _init_db(con: sqlite3.Connection) -> None:
    # USERS
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            broker_mc TEXT,
            broker_status TEXT DEFAULT 'none',
            email TEXT,
            account_locked INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    # Basic migrations (if you renamed/added fields over time)
    _add_col_if_missing(con, "users", "broker_mc", "TEXT", "NULL")
    _add_col_if_missing(con, "users", "broker_status", "TEXT", "'none'")
    _add_col_if_missing(con, "users", "email", "TEXT", "NULL")
    _add_col_if_missing(con, "users", "account_locked", "INTEGER", "0")
    _add_col_if_missing(con, "users", "created_at", "TEXT", "''")

    # BROKER REQUESTS (optional but useful)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS broker_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            mc_number TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # AUDIT LOG
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            meta TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # LOADS
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS loads (
            id TEXT PRIMARY KEY,
            broker_mc TEXT NOT NULL,
            dispatcher_username TEXT,
            visibility TEXT DEFAULT 'draft',
            status TEXT DEFAULT 'new',

            shipper_name TEXT,
            customer_ref TEXT,

            origin_city TEXT,
            origin_state TEXT,
            origin_zip TEXT,

            dest_city TEXT,
            dest_state TEXT,
            dest_zip TEXT,

            pickup_date TEXT,
            delivery_date TEXT,

            equipment TEXT,
            weight_lbs INTEGER,
            miles INTEGER,

            rate_total REAL,
            rate_per_mile REAL,

            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

# ---------------------------
# User functions
# ---------------------------

def get_user(username: str):
    u = (username or "").strip()
    if not u:
        return None
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE username = ?", (u,)).fetchone()

def create_user(
    username: str,
    password_hash: str,
    role: str,
    broker_mc: Optional[str] = None,
    broker_status: str = "none",
) -> None:
    u = (username or "").strip()
    if not u:
        raise ValueError("username required")
    with _conn() as con:
        con.execute(
            """
            INSERT INTO users (username, password_hash, role, broker_mc, broker_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (u, password_hash, role, broker_mc, broker_status or "none", now_iso()),
        )

def set_email(username: str, email: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET email=? WHERE username=?", ((email or "").strip().lower(), username))

def set_user_role(username: str, role: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET role=? WHERE username=?", ((role or "").strip().lower(), username))

def set_broker_status(username: str, status: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET broker_status=? WHERE username=?", ((status or "").strip().lower(), username))

def set_broker_mc(username: str, broker_mc: str) -> None:
    with _conn() as con:
        con.execute("UPDATE users SET broker_mc=? WHERE username=?", ((broker_mc or "").strip(), username))

def create_broker_request(username: str, mc_number: str) -> None:
    u = (username or "").strip()
    mc = (mc_number or "").strip()
    if not u or not mc:
        return
    ts = now_iso()
    with _conn() as con:
        # Keep only the most recent pending/record, but don't overthink it.
        con.execute(
            """
            INSERT INTO broker_requests (username, mc_number, status, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (u, mc, ts, ts),
        )

def list_pending_brokers(limit: int = 200):
    with _conn() as con:
        return con.execute(
            """
            SELECT username, role, broker_status, broker_mc, email, created_at
            FROM users
            WHERE role='broker' AND broker_status='pending'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(max(1, min(limit, 2000))),),
        ).fetchall()

def list_users_by_role_and_broker_mc(role: str, broker_mc: str, limit: int = 500):
    r = (role or "").strip().lower()
    mc = (broker_mc or "").strip()
    with _conn() as con:
        return con.execute(
            """
            SELECT username, role, broker_mc, broker_status, created_at
            FROM users
            WHERE lower(role)=? AND broker_mc=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (r, mc, int(max(1, min(limit, 2000)))),
        ).fetchall()

# ---------------------------
# Audit
# ---------------------------

def audit(actor: str, action: str, target: str, meta: Optional[str]) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO audit_log (actor, action, target, meta, created_at) VALUES (?, ?, ?, ?, ?)",
            ((actor or "").strip(), (action or "").strip(), (target or "").strip(), meta, now_iso()),
        )

# ---------------------------
# Loads helpers
# ---------------------------

LOAD_COLUMNS = ",".join(
    [
        "id",
        "broker_mc",
        "dispatcher_username",
        "visibility",
        "status",
        "shipper_name",
        "customer_ref",
        "origin_city",
        "origin_state",
        "origin_zip",
        "dest_city",
        "dest_state",
        "dest_zip",
        "pickup_date",
        "delivery_date",
        "equipment",
        "weight_lbs",
        "miles",
        "rate_total",
        "rate_per_mile",
        "notes",
        "created_at",
        "updated_at",
    ]
)

def upsert_load(load: Dict[str, Any]) -> None:
    # expects load["id"] and load["broker_mc"]
    lid = (load.get("id") or "").strip()
    bmc = (load.get("broker_mc") or "").strip()
    if not lid or not bmc:
        raise ValueError("load.id and load.broker_mc required")

    ts = now_iso()
    values = {k: load.get(k) for k in LOAD_COLUMNS.split(",")}
    values["id"] = lid
    values["broker_mc"] = bmc
    values["updated_at"] = ts
    if not values.get("created_at"):
        values["created_at"] = ts

    cols = LOAD_COLUMNS.split(",")
    placeholders = ",".join(["?"] * len(cols))
    updates = ",".join([f"{c}=excluded.{c}" for c in cols if c != "id"])

    with _conn() as con:
        con.execute(
            f"""
            INSERT INTO loads ({",".join(cols)}) VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {updates}
            """,
            tuple(values[c] for c in cols),
        )

def get_load(load_id: str):
    lid = (load_id or "").strip()
    if not lid:
        return None
    with _conn() as con:
        return con.execute(f"SELECT {LOAD_COLUMNS} FROM loads WHERE id=?", (lid,)).fetchone()

def list_loads_by_broker(broker_mc: str):
    mc = (broker_mc or "").strip()
    with _conn() as con:
        return con.execute(
            f"SELECT {LOAD_COLUMNS} FROM loads WHERE broker_mc=? ORDER BY created_at DESC",
            (mc,),
        ).fetchall()

def list_published_loads_by_broker_mc(broker_mc: str, limit: int = 500):
    mc = (broker_mc or "").strip()
    with _conn() as con:
        return con.execute(
            f"""
            SELECT {LOAD_COLUMNS}
            FROM loads
            WHERE broker_mc=? AND visibility='published'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (mc, int(max(1, min(limit, 2000)))),
        ).fetchall()

def list_loads_by_dispatcher(dispatcher_username: str, broker_mc: str):
    du = (dispatcher_username or "").strip()
    mc = (broker_mc or "").strip()
    with _conn() as con:
        return con.execute(
            f"""
            SELECT {LOAD_COLUMNS}
            FROM loads
            WHERE broker_mc=? AND (dispatcher_username=? OR dispatcher_username IS NULL)
            ORDER BY created_at DESC
            """,
            (mc, du),
        ).fetchall()

def list_loads_published_by_dispatcher(dispatcher_username: str, broker_mc: str):
    du = (dispatcher_username or "").strip()
    mc = (broker_mc or "").strip()
    with _conn() as con:
        return con.execute(
            f"""
            SELECT {LOAD_COLUMNS}
            FROM loads
            WHERE broker_mc=? AND dispatcher_username=? AND visibility='published'
            ORDER BY created_at DESC
            """,
            (mc, du),
        ).fetchall()
