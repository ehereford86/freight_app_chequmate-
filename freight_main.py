from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"
INDEX_FILE = WEBAPP_DIR / "index.html"

# -----------------------------
# Static assets (CSS/JS/images)
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
    if not INDEX_FILE.exists():
        return JSONResponse(status_code=404, content={"detail": "webapp/index.html not found"})
    return FileResponse(str(INDEX_FILE))

# Important: allow HEAD /app (curl -I, proxies, some health checks)
@app.head("/app")
def app_ui_head():
    if not INDEX_FILE.exists():
        return Response(status_code=404)
    return Response(status_code=200)

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
        # Keep the app up even if one router fails import
        pass