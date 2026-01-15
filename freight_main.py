from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# -----------------------------
# App setup
# -----------------------------
app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

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

# Mount /webapp so these work:
#   /webapp/app.css
#   /webapp/app.js
#   /webapp/assets/chequmate-logo.png
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

# -----------------------------
# API Routers (optional but expected)
# -----------------------------
# These will load your routes if your modules define `router = APIRouter()`
for mod_name in ("auth", "fuel", "pricing", "fmcsa"):
    try:
        module = __import__(mod_name)
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
    except Exception:
        # Don't crash the whole app if a router import fails;
        # your core UI + home route still loads.
        pass