from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

import db

router = APIRouter()


# ---------------------------
# Admin auth (simple + strict)
# ---------------------------
def _require_admin(x_admin_key: Optional[str]) -> None:
    expected = os.environ.get("ADMIN_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_KEY is not set on the server.",
        )
    if not x_admin_key or x_admin_key.strip() != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _tables(con: sqlite3.Connection) -> List[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def _table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return [r["name"] for r in rows]


def _pick_user_table(con: sqlite3.Connection) -> str:
    # Common patterns
    candidates = [
        "users",
        "user",
        "accounts",
        "account",
        "auth_users",
        "auth_user",
    ]
    existing = set(_tables(con))
    for t in candidates:
        if t in existing:
            return t

    # Fallback heuristic: table that has BOTH username and role columns
    for t in existing:
        cols = set(_table_columns(con, t))
        if "username" in cols and "role" in cols:
            return t

    raise HTTPException(
        status_code=500,
        detail=f"Could not find a user table. Tables: {sorted(existing)}",
    )


def _ensure_broker_link_column(con: sqlite3.Connection, user_table: str) -> str:
    """
    Ensures there is a column we can use to link dispatcher -> broker.
    Returns the column name.
    """
    cols = set(_table_columns(con, user_table))

    # If you already have one of these, use it.
    for col in ["broker_username", "linked_broker", "broker_id", "broker"]:
        if col in cols:
            return col

    # Otherwise, add broker_username (simple, readable, portable)
    con.execute(f"ALTER TABLE {user_table} ADD COLUMN broker_username TEXT")
    con.commit()
    return "broker_username"


def _user_exists(con: sqlite3.Connection, user_table: str, username: str, role: Optional[str] = None) -> bool:
    if role:
        row = con.execute(
            f"SELECT 1 FROM {user_table} WHERE username=? AND role=? LIMIT 1",
            (username, role),
        ).fetchone()
    else:
        row = con.execute(
            f"SELECT 1 FROM {user_table} WHERE username=? LIMIT 1",
            (username,),
        ).fetchone()
    return row is not None


class LinkDispatcherReq(BaseModel):
    dispatcher_username: str
    broker_username: str


@router.get("/admin/db-info", include_in_schema=False)
def admin_db_info(x_admin_key: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    _require_admin(x_admin_key)
    con = _connect()
    try:
        user_table = _pick_user_table(con)
        cols = _table_columns(con, user_table)
        return {
            "ok": True,
            "db_path": db.DB_PATH,
            "tables": _tables(con),
            "user_table": user_table,
            "user_columns": cols,
        }
    finally:
        con.close()


@router.post("/admin/link-dispatcher", include_in_schema=False)
def admin_link_dispatcher(
    body: LinkDispatcherReq,
    x_admin_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    _require_admin(x_admin_key)

    dispatcher = body.dispatcher_username.strip()
    broker = body.broker_username.strip()
    if not dispatcher or not broker:
        raise HTTPException(status_code=400, detail="dispatcher_username and broker_username are required")

    con = _connect()
    try:
        user_table = _pick_user_table(con)

        # Validate users exist
        if not _user_exists(con, user_table, dispatcher, role="dispatcher"):
            raise HTTPException(status_code=404, detail=f"Dispatcher not found: {dispatcher}")
        if not _user_exists(con, user_table, broker, role="broker"):
            raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")

        link_col = _ensure_broker_link_column(con, user_table)

        # Link dispatcher -> broker
        con.execute(
            f"UPDATE {user_table} SET {link_col}=? WHERE username=? AND role='dispatcher'",
            (broker, dispatcher),
        )
        con.commit()

        # Return updated row
        row = con.execute(
            f"SELECT username, role, {link_col} AS broker_link FROM {user_table} WHERE username=? AND role='dispatcher'",
            (dispatcher,),
        ).fetchone()

        return {
            "ok": True,
            "user_table": user_table,
            "link_column": link_col,
            "dispatcher": dict(row) if row else {"username": dispatcher, "role": "dispatcher"},
        }
    finally:
        con.close()
