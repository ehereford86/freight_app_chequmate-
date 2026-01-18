from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

import db

APP_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = APP_DIR / "webapp"
INDEX_FILE = WEBAPP_DIR / "index.html"

app = FastAPI(title="Freight App API", version="0.1.0")


# -----------------------------
# Debug route gate + admin guard
# -----------------------------
def _debug_enabled() -> bool:
    return os.environ.get("ENABLE_DEBUG_ROUTES", "0").strip() == "1"


def _require_admin(user=Depends(lambda: None)):
    """
    Requires an authenticated admin user.

    This uses auth.get_current_user() if available; otherwise denies access.
    We keep it defensive so your app doesn't crash on import changes.
    """
    try:
        import auth  # local module
        get_current_user = getattr(auth, "get_current_user", None)
        if get_current_user is None:
            raise HTTPException(status_code=403, detail="Admin only")
        user = get_current_user()  # may raise internally
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin only")

    if not user or (isinstance(user, dict) and user.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@app.get("/_debug/env", include_in_schema=False)
def _debug_env(_admin=Depends(_require_admin)):
    """
    Debug endpoint is OFF unless ENABLE_DEBUG_ROUTES=1.
    Returns only presence + length (no secret leaked).
    """
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not Found")

    v = os.environ.get("EIA_API_KEY")
    return {"has_EIA_API_KEY": bool(v), "EIA_API_KEY_len": (len(v) if v else 0)}


# -----------------------------
# Startup
# -----------------------------
@app.on_event("startup")
def _startup():
    # init DB
    try:
        if hasattr(db, "init_db"):
            db.init_db()
    except Exception:
        pass

    # seed admin (optional; doesn't crash if function missing)
    try:
        import auth
        if hasattr(auth, "seed_admin_if_needed"):
            auth.seed_admin_if_needed()
    except Exception:
        pass


# -----------------------------
# Basic endpoints
# -----------------------------
@app.get("/", include_in_schema=False)
def home():
    return {"message": "Freight app API is running"}


# UI
@app.get("/app", include_in_schema=False)
def app_ui():
    if INDEX_FILE.exists():
        return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>UI not found</h1>", status_code=404)


# Serve /webapp assets
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")


# Optional convenience routes (if your UI ever hits /app.js or /app.css)
@app.get("/app.js", include_in_schema=False)
def app_js():
    f = WEBAPP_DIR / "app.js"
    if f.exists():
        return HTMLResponse(f.read_text(encoding="utf-8"), media_type="text/javascript")
    return JSONResponse({"detail": "Not Found"}, status_code=404)


@app.get("/app.css", include_in_schema=False)
def app_css():
    f = WEBAPP_DIR / "app.css"
    if f.exists():
        return HTMLResponse(f.read_text(encoding="utf-8"), media_type="text/css")
    return JSONResponse({"detail": "Not Found"}, status_code=404)


# -----------------------------
# API Routers
# -----------------------------
def _safe_include(module_name: str):
    try:
        module = __import__(module_name)
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
            return True
    except Exception:
        return False
    return False


# Must-have routers
_safe_include("auth")
_safe_include("pricing")

# Optional routers if present
_safe_include("fuel")
_safe_include("fmcsa")
