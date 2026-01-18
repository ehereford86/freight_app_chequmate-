from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Local modules (must exist in your repo)
from db import init_db

app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
INDEX_HTML = WEBAPP_DIR / "index.html"

@app.on_event("startup")
def _startup():
    # Initialize / migrate DB tables
    init_db()

# -----------------------------
# Static assets
# -----------------------------
# Serve /webapp/* (app.js, app.css, assets, index.html)
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

# -----------------------------
# Health
# -----------------------------
@app.get("/")
def home():
    return {"message": "Freight app API is running"}

# -----------------------------
# UI
# -----------------------------
@app.get("/app")
def app_ui():
    # IMPORTANT: return the actual HTML (your issue was returning empty body)
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML), media_type="text/html")
    return JSONResponse(status_code=404, content={"detail": "webapp/index.html not found"})

# Optional convenience routes (not required, but harmless)
@app.get("/app.js")
def app_js():
    p = WEBAPP_DIR / "app.js"
    if p.exists():
        return FileResponse(str(p), media_type="text/javascript")
    return JSONResponse(status_code=404, content={"detail": "webapp/app.js not found"})

@app.get("/app.css")
def app_css():
    p = WEBAPP_DIR / "app.css"
    if p.exists():
        return FileResponse(str(p), media_type="text/css")
    return JSONResponse(status_code=404, content={"detail": "webapp/app.css not found"})

# -----------------------------
# API Routers
# -----------------------------
for mod_name in ("auth", "fuel", "pricing", "fmcsa"):
    try:
        module = __import__(mod_name)
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
    except Exception:
        # Don't crash if a router import fails
        pass
