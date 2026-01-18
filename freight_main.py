from fastapi import FastAPI, HTTPException, Header
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
# Debug gate (safe + independent)
# -----------------------------
def _debug_enabled() -> bool:
    return os.environ.get("ENABLE_DEBUG_ROUTES", "0").strip() == "1"

def _require_debug_token(x_debug_token: str | None) -> None:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not Found")

    secret = os.environ.get("DEBUG_ADMIN_TOKEN", "").strip()
    if not secret:
        raise HTTPException(status_code=404, detail="Not Found")

    if not x_debug_token or x_debug_token.strip() != secret:
        raise HTTPException(status_code=403, detail="Forbidden")

@app.get("/_debug/env", include_in_schema=False)
def _debug_env(x_debug_token: str | None = Header(default=None, alias="X-Debug-Token")):
    _require_debug_token(x_debug_token)
    v = os.environ.get("EIA_API_KEY")
    return {"has_EIA_API_KEY": bool(v), "EIA_API_KEY_len": (len(v) if v else 0)}

# -----------------------------
# Startup
# -----------------------------
@app.on_event("startup")
def _startup():
    try:
        if hasattr(db, "init_db"):
            db.init_db()
    except Exception:
        pass

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

@app.get("/app", include_in_schema=False)
def app_ui():
    if INDEX_FILE.exists():
        return HTMLResponse(INDEX_FILE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>UI not found</h1>", status_code=404)

if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

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

_safe_include("auth")
_safe_include("pricing")
_safe_include("fuel")
_safe_include("fmcsa")
