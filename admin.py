from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
import auth

router = APIRouter()

# Minimal schema guard (keeps things robust if DB is empty/new)
def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _init_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            broker_status TEXT DEFAULT 'none',
            broker_mc TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    con.commit()

class ApproveRejectReq(BaseModel):
    username: str

@router.get("/admin/pending-brokers")
def pending_brokers(limit: int = 200, user: Dict[str, Any] = Depends(auth.require_admin)):
    con = _connect()
    try:
        _init_schema(con)
        rows = con.execute(
            """
            SELECT username, email, role, broker_status, broker_mc, created_at
            FROM users
            WHERE role='broker' AND lower(coalesce(broker_status,'none'))='pending'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return {
            "ok": True,
            "count": len(rows),
            "items": [dict(r) for r in rows],
        }
    finally:
        con.close()

@router.post("/admin/approve-broker-user")
def approve_broker_user(body: ApproveRejectReq, user: Dict[str, Any] = Depends(auth.require_admin)):
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")

    con = _connect()
    try:
        _init_schema(con)
        row = con.execute(
            "SELECT username, role, broker_status FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if (row["role"] or "").lower() != "broker":
            raise HTTPException(status_code=400, detail="User is not a broker")

        con.execute(
            "UPDATE users SET broker_status='approved' WHERE username=?",
            (username,),
        )
        con.commit()
        return {"ok": True, "username": username, "broker_status": "approved"}
    finally:
        con.close()

@router.post("/admin/reject-broker-user")
def reject_broker_user(body: ApproveRejectReq, user: Dict[str, Any] = Depends(auth.require_admin)):
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")

    con = _connect()
    try:
        _init_schema(con)
        row = con.execute(
            "SELECT username, role FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if (row["role"] or "").lower() != "broker":
            raise HTTPException(status_code=400, detail="User is not a broker")

        con.execute(
            "UPDATE users SET broker_status='rejected' WHERE username=?",
            (username,),
        )
        con.commit()
        return {"ok": True, "username": username, "broker_status": "rejected"}
    finally:
        con.close()
