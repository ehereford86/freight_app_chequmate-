from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
FAVICON_PATH = STATIC_DIR / "favicon.ico"

ADMIN_KEY = (os.environ.get("ADMIN_KEY") or "").strip()

def _admin_key_ok(request: Request) -> bool:
    """
    Browser-friendly admin gate for sensitive endpoints (docs/openapi).
    Accepts:
      - header: X-Admin-Key: <ADMIN_KEY>
      - query:  ?admin_key=<ADMIN_KEY>
    """
    if not ADMIN_KEY:
        return False
    hdr = (request.headers.get("x-admin-key") or "").strip()
    q = (request.query_params.get("admin_key") or "").strip()
    return hdr == ADMIN_KEY or q == ADMIN_KEY


# Disable default swagger/redoc. We'll add our own protected routes.
app = FastAPI(
    title="Chequmate Freight System",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Mount /static (login.html, css, js, favicon, landing page, etc.)
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"[boot] mounted /static -> {STATIC_DIR}")


def _try_include(module_name: str, router_attr: str = "router") -> None:
    try:
        mod = __import__(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included router: {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] WARNING: could not include {module_name}.{router_attr}: {e!r}")


# -------------------------
# Public landing + favicon
# -------------------------
@app.get("/", include_in_schema=False)
def root(request: Request):
    accept = (request.headers.get("accept") or "").lower()

    # If browser: serve landing page if present, else redirect to login UI.
    if "text/html" in accept:
        idx = STATIC_DIR / "index.html"
        if idx.exists():
            return FileResponse(str(idx), media_type="text/html")
        return RedirectResponse(url="/login-ui", status_code=302)

    # If API client:
    return JSONResponse({"ok": True, "service": "chequmate-freight-api"})


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def favicon():
    if not FAVICON_PATH.exists():
        # 204 is nicer than 404 for browser noise
        return JSONResponse(status_code=204, content=None)
    return FileResponse(str(FAVICON_PATH), media_type="image/x-icon")


# -------------------------
# Protected Swagger + OpenAPI
# -------------------------
@app.get("/docs", include_in_schema=False)
def docs(request: Request):
    if not _admin_key_ok(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Chequmate Docs (Admin)")


@app.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request):
    if not _admin_key_ok(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse(app.openapi())


# -------------------------
# Routers
# -------------------------
# Core auth + data
_try_include("auth")
_try_include("db")           # harmless if db exposes no router
_try_include("loads")
_try_include("negotiate")
_try_include("fuel")
_try_include("pricing")
_try_include("routing_ors")
_try_include("fmcsa")

# Admin + UI
_try_include("admin")
_try_include("admin_ui")
_try_include("login_ui")
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
