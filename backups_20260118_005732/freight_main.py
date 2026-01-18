from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
import auth

app = FastAPI(title="Freight App API", version="0.1.0")

WEBAPP_DIR = Path(__file__).parent / "webapp"

@app.on_event("startup")
def startup():
    db.init_db()
    auth.seed_admin_if_needed()

# Serve /webapp assets
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")

@app.get("/")
def home():
    return {"message": "Freight app API is running"}

# UI entrypoint
@app.get("/app")
def app_ui():
    index_path = WEBAPP_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse(status_code=404, content={"detail": "webapp/index.html missing"})
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

# Keep compatibility with old direct paths if your HTML ever references them
@app.get("/app.css")
def app_css_redirect():
    return JSONResponse(status_code=404, content={"detail": "Use /webapp/app.css"})

@app.get("/app.js")
def app_js_redirect():
    return JSONResponse(status_code=404, content={"detail": "Use /webapp/app.js"})

# Routers
app.include_router(auth.router)

# NOTE: your pricing/fuel routers can be re-added once they import cleanly.
# For now, we only add what your UI needs to login/register/admin now.
