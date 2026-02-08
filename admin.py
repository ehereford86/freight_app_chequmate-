from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from passlib.context import CryptContext

import db
from auth import require_admin

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(pw: str) -> str:
    return pwd_context.hash(pw)


def _get_password_col() -> str:
    """
    Support both schemas:
      - users.password_hash
      - users.password
    Auto-detect at runtime.
    """
    with db._conn() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()]
    if "password_hash" in cols:
        return "password_hash"
    if "password" in cols:
        return "password"
    raise RuntimeError("Could not find password column (password_hash or password) in users table")


@router.get("/admin/pending-brokers")
def pending_brokers(limit: int = 200, u: Dict[str, Any] = Depends(require_admin)):
    try:
        items = db.list_pending_brokers(limit=limit)
        return {"ok": True, "count": len(items), "items": items}
    except AttributeError:
        # Fallback if db.py doesn't have helper
        with db._conn() as con:
            rows = con.execute(
                """
                SELECT username, email, role, broker_status, broker_mc, created_at
                FROM users
                WHERE role='broker' AND broker_status='pending'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            items.append(
                {
                    "username": d.get("username"),
                    "email": d.get("email"),
                    "role": d.get("role"),
                    "broker_status": d.get("broker_status"),
                    "broker_mc": d.get("broker_mc"),
                    "created_at": d.get("created_at"),
                }
            )
        return {"ok": True, "count": len(items), "items": items}


@router.post("/admin/approve-broker-user")
async def approve_broker_user(request: Request, u: Dict[str, Any] = Depends(require_admin)):
    body = await request.json()
    username = (body.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")

    row = db.get_user(username)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user = dict(row)
    if (user.get("role") or "").lower() != "broker":
        raise HTTPException(status_code=400, detail="User is not a broker")

    with db._conn() as con:
        con.execute(
            "UPDATE users SET broker_status='approved' WHERE username=?",
            (username,),
        )
    try:
        db.audit(u.get("username") or "admin", "approve_broker", f"user:{username}", None)
    except Exception:
        pass

    return {"ok": True, "username": username, "broker_status": "approved"}


@router.post("/admin/reject-broker-user")
async def reject_broker_user(request: Request, u: Dict[str, Any] = Depends(require_admin)):
    body = await request.json()
    username = (body.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")

    row = db.get_user(username)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user = dict(row)
    if (user.get("role") or "").lower() != "broker":
        raise HTTPException(status_code=400, detail="User is not a broker")

    with db._conn() as con:
        con.execute(
            "UPDATE users SET broker_status='rejected' WHERE username=?",
            (username,),
        )
    try:
        db.audit(u.get("username") or "admin", "reject_broker", f"user:{username}", None)
    except Exception:
        pass

    return {"ok": True, "username": username, "broker_status": "rejected"}


@router.post("/admin/reset-user-password")
async def reset_user_password(request: Request, u: Dict[str, Any] = Depends(require_admin)):
    """
    Admin-only: force reset any user's password (driver/dispatcher/broker/admin).
    This avoids email/SMPP dependency.
    JSON: { "username": "Monett", "new_password": "TempPass123!" }
    """
    body = await request.json()
    username = (body.get("username") or "").strip()
    new_password = body.get("new_password") or ""

    if not username:
        raise HTTPException(status_code=400, detail="username required")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="new_password must be at least 8 characters")

    row = db.get_user(username)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    password_col = _get_password_col()
    pw_hash = _hash(new_password)

    with db._conn() as con:
        con.execute(
            f"UPDATE users SET {password_col}=? WHERE username=?",
            (pw_hash, username),
        )

    try:
        db.audit(u.get("username") or "admin", "admin_reset_password", f"user:{username}", None)
    except Exception:
        pass

    return {"ok": True, "username": username, "password_reset": True}
