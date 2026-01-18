from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from db import init_db

# Explicit router imports (no silent failures)
import auth
import fuel
import pricing

app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/")
def home():
    return {"message": "Freight app API is running"}


@app.get("/app")
def app_ui():
    index_path = WEBAPP_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse(status_code=404, content={"detail": "UI not found"})
    return index_path.read_text(encoding="utf-8")


# Mount /webapp assets (CSS/JS/images)
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")


# Convenience routes some pages still hit
@app.get("/app.js")
def app_js():
    js_path = WEBAPP_DIR / "app.js"
    if not js_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return js_path.read_text(encoding="utf-8")


@app.get("/app.css")
def app_css():
    css_path = WEBAPP_DIR / "app.css"
    if not css_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return css_path.read_text(encoding="utf-8")


# Routers (THIS is what you’re missing right now)
app.include_router(auth.router)
app.include_router(fuel.router)
app.include_router(pricing.router)
