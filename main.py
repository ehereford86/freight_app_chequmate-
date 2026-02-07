from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

HERE = Path(__file__).resolve().parent

# Lock FastAPI's default docs/openapi off — we will serve them ourselves behind ADMIN_KEY.
app = FastAPI(
    title="Chequmate Freight System",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

STATIC_DIR = HERE / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"[boot] mounted /static -> {STATIC_DIR}")


def _safe_include(module_name: str, router_attr: str = "router") -> None:
    try:
        mod = __import__(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included router: {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] WARNING: could not include {module_name}.{router_attr}: {e!r}")


def _admin_key_ok(request: Request) -> bool:
    expected = (os.environ.get("ADMIN_KEY") or "").strip()
    if not expected:
        return False
    got = (request.query_params.get("admin_key") or "").strip()
    return got == expected


@app.get("/", include_in_schema=False)
def root(request: Request):
    accept = (request.headers.get("accept") or "").lower()
    # Browsers get landing page; API clients get JSON
    if "text/html" in accept:
        return RedirectResponse(url="/static/index.html", status_code=302)
    return JSONResponse({"ok": True, "service": "chequmate-freight-api"})


@app.get("/docs", include_in_schema=False)
def admin_docs(request: Request):
    if not _admin_key_ok(request):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    return get_swagger_ui_html(
        openapi_url=f"/openapi.json?admin_key={request.query_params.get('admin_key')}",
        title="Chequmate Docs (Admin)",
    )


@app.get("/openapi.json", include_in_schema=False)
def admin_openapi(request: Request):
    if not _admin_key_ok(request):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return app.openapi()


# Routers
for _m in [
    "auth",
    "loads",
    "negotiate",
    "fuel",
    "pricing",
    "fmcsa",
    "admin",
    "admin_ui",
    "login_ui",
    "broker_ui",
    "driver_ui",
    "dispatcher_ui",
]:
    _safe_include(_m)
