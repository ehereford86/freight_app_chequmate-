from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

# Import routers explicitly (no silent failures)
from auth import router as auth_router, init_db
from fuel import router as fuel_router
from pricing import router as pricing_router
from fmcsa import router as fmcsa_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

# -----------------------------
# Startup (DB init)
# -----------------------------
@app.on_event("startup")
def startup():
    init_db()

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

# Serve static assets so CSS/JS/logo load
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

# -----------------------------
# API Routers
# -----------------------------
app.include_router(auth_router)
app.include_router(fuel_router)
app.include_router(pricing_router)
app.include_router(fmcsa_router)