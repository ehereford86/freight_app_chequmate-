from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import importlib

# -----------------------------
# App setup
# -----------------------------
app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

# -----------------------------
# Static UI assets
# -----------------------------
# Serves:
#   /webapp/app.css
#   /webapp/app.js
#   /webapp/assets/chequmate-logo.png
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

# -----------------------------
# Health / Root
# -----------------------------
@app.get("/")
def home():
    return {"message": "Freight app API is running"}

@app.head("/")
def home_head():
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

# IMPORTANT: curl -I /app sends HEAD, so support it
@app.head("/app")
def app_ui_head():
    return Response(status_code=200)

# Optional: avoid noisy console error for favicon
@app.get("/favicon.ico")
def favicon():
    ico = WEBAPP_DIR / "favicon.ico"
    if ico.exists():
        return FileResponse(ico)
    return Response(status_code=204)

# -----------------------------
# API Routers (if present)
# -----------------------------
for mod_name in ("auth", "fuel", "pricing", "fmcsa"):
    try:
        module = importlib.import_module(mod_name)
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
    except Exception:
        # Don't crash the whole app if a router import fails
        pass