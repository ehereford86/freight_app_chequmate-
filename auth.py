import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt, JWTError
from passlib.context import CryptContext

import db

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_ME_IN_RENDER")
ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.getenv("JWT_EXPIRE_MIN", "10080"))  # default 7 days

def hash_password(p: str) -> str:
    return pwd_context.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd_context.verify(p, hashed)

def create_token(username: str, role: str, broker_status: str):
    exp = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {"sub": username, "role": role, "broker_status": broker_status, "exp": exp}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1].strip()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    u = db.get_user(username)
    if not u:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "username": u["username"],
        "email": u["email"],
        "role": u["role"],
        "broker_status": u["broker_status"],
        "mc_number": u["mc_number"],
        "legal_name": u["legal_name"],
    }

def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dep

def require_broker_approved(user=Depends(get_current_user)):
    if user["role"] != "broker" or user["broker_status"] != "approved":
        raise HTTPException(status_code=403, detail="Broker access requires approval")
    return user

@router.get("/register")
def register(username: str, password: str, role: str, email: str | None = None):
    username = (username or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    # Only allow driver/dispatcher self-register
    if role not in ("driver", "dispatcher"):
        raise HTTPException(status_code=400, detail="Role must be driver or dispatcher")

    if db.get_user(username):
        raise HTTPException(status_code=400, detail="Username already exists")

    db.create_user(username=username, email=email, password_hash=hash_password(password), role=role)
    return {"ok": True, "message": "Registered. Now login."}

@router.get("/login")
def login(username: str, password: str):
    u = db.get_user((username or "").strip())
    if not u:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(u["username"], u["role"], u["broker_status"])
    return {"access_token": token, "token_type": "bearer"}

@router.get("/verify-token")
def verify_token(user=Depends(get_current_user)):
    return user

@router.get("/broker-onboard")
def broker_onboard(mc_number: str, legal_name_confirm: str, user=Depends(require_role("driver", "dispatcher"))):
    mc_number = (mc_number or "").strip()
    legal = (legal_name_confirm or "").strip()
    if not mc_number:
        raise HTTPException(status_code=400, detail="MC number required")
    if not legal:
        raise HTTPException(status_code=400, detail="Legal name required")

    # Store request as pending; admin approves and promotes to broker.
    db.set_broker_request(user["username"], mc_number, legal)
    return {"ok": True, "message": "Broker request submitted for admin approval."}

# ---- Admin approvals ----
@router.get("/admin/list-broker-requests")
def admin_list(user=Depends(require_role("admin"))):
    rows = db.list_pending_brokers()
    return {"pending": [dict(r) for r in rows]}

@router.get("/admin/approve-broker")
def admin_approve(username: str, user=Depends(require_role("admin"))):
    if not db.get_user(username):
        raise HTTPException(status_code=404, detail="User not found")
    db.approve_broker(username)
    return {"ok": True, "message": f"{username} approved and promoted to broker."}

@router.get("/admin/reject-broker")
def admin_reject(username: str, user=Depends(require_role("admin"))):
    if not db.get_user(username):
        raise HTTPException(status_code=404, detail="User not found")
    db.reject_broker(username)
    return {"ok": True, "message": f"{username} rejected."}

# ---- Password reset (email) ----
def _smtp_send(to_email: str, subject: str, body: str):
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    pw = os.getenv("SMTP_PASS", "").strip()
    from_email = os.getenv("SMTP_FROM", user).strip()

    if not host or not user or not pw or not from_email:
        raise HTTPException(status_code=501, detail="Email not configured on server (SMTP env vars missing)")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)

@router.get("/request-password-reset")
def request_password_reset(username: str):
    u = db.get_user((username or "").strip())
    if not u:
        # Don't leak account existence
        return {"ok": True, "message": "If the account exists, a reset email will be sent."}

    if not u["email"]:
        raise HTTPException(status_code=400, detail="No email on file for this user")

    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)

    db.delete_resets(u["username"])
    db.save_reset_token(u["username"], token, expires.isoformat())

    reset_link = f"{os.getenv('PUBLIC_BASE_URL','https://chequmate-freight-api.onrender.com')}/webapp/index.html#reset={u['username']}:{token}"
    body = f"Chequmate Freight password reset link (expires in 30 minutes):\n\n{reset_link}\n"
    _smtp_send(u["email"], "Chequmate Freight - Password Reset", body)

    return {"ok": True, "message": "Reset email sent (if SMTP is configured)."}

@router.get("/reset-password")
def reset_password(username: str, token: str, new_password: str):
    u = db.get_user((username or "").strip())
    if not u:
        raise HTTPException(status_code=400, detail="Invalid reset")

    r = db.get_reset(u["username"], token)
    if not r:
        raise HTTPException(status_code=400, detail="Invalid reset")

    expires_at = datetime.fromisoformat(r["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Reset expired")

    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    db.set_password(u["username"], hash_password(new_password))
    db.delete_resets(u["username"])
    return {"ok": True, "message": "Password updated. Please login."}
