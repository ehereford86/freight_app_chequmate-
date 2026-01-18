from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from db import init_db

app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

# -----------------------------
# Startup: init DB + seed admin (env-based)
# -----------------------------
@app.on_event("startup")
def _startup():
    init_db()

# -----------------------------
# No-cache middleware for UI assets
# (prevents the "back to ugly / old JS" problem)
# -----------------------------
@app.middleware("http")
async def no_cache_ui_assets(request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if p == "/app" or p.startswith("/webapp/") or p in ("/app.js", "/app.css"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp

# -----------------------------
# Health / Root
# -----------------------------
@app.get("/")
def home():
    return {"message": "Freight app API is running"}

@app.head("/")
def home_head():
    return Response(status_code=200)

# Platforms sometimes probe /app
@app.head("/app")
def app_head():
    return Response(status_code=200)

# -----------------------------
# Web UI
# -----------------------------
@app.get("/app")
def app_ui():
    index_file = WEBAPP_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(status_code=404, content={"detail": "webapp/index.html not found"})
    return FileResponse(index_file)

# Serve /webapp assets
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

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
