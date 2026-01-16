from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import importlib
import logging

# -----------------------------
# App setup
# -----------------------------
app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

log = logging.getLogger("freight_app")

# -----------------------------
# Static assets (CSS/JS/logo)
# -----------------------------
# This makes these URLs work:
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

# Render (and some proxies) may send HEAD /
@app.head("/")
def home_head():
    return Response(status_code=200)

# -----------------------------
# Web UI
# -----------------------------
@app.get("/app")
def app_ui():
    """
    Serves the web UI entrypoint.
    """
    index_file = WEBAPP_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(status_code=404, content={"detail": "webapp/index.html not found"})
    return FileResponse(index_file)

# -----------------------------
# API Routers
# -----------------------------
# Loads your routes if these modules define `router = APIRouter()`
for mod_name in ("auth", "fuel", "pricing", "fmcsa"):
    try:
        module = importlib.import_module(mod_name)
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
        else:
            log.warning("Module '%s' has no attribute 'router' (skipped).", mod_name)
    except Exception as e:
        # Don't crash the whole app if a router import fails.
        log.exception("Failed to import router module '%s': %s", mod_name, e)