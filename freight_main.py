from __future__ import annotations

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Chequmate Freight System", version="0.1.0")

# Serve /static on Render too (login.html, images if you add them)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    print(f"[boot] mounted /static -> {STATIC_DIR}")


def _try_include(module_name: str, router_attr: str = "router") -> None:
    try:
        mod = __import__(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] ERROR including {module_name}.{router_attr}: {e!r}")


@app.get("/", include_in_schema=False)
def root(request: Request):
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return RedirectResponse(url="/login-ui", status_code=302)
    return JSONResponse({"ok": True, "service": "chequmate-freight-api"})


@app.get("/__version", include_in_schema=False)
def version():
    return JSONResponse(
        {
            "ok": True,
            "render_git_commit": os.environ.get("RENDER_GIT_COMMIT", ""),
            "python": os.environ.get("PYTHON_VERSION", ""),
        }
    )


# Core API routers
_try_include("auth")
_try_include("loads")
_try_include("negotiate")
_try_include("fuel")
_try_include("pricing")
_try_include("fmcsa")
_try_include("admin_ui")

# UI routers exposed on Render
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
_try_include("login_ui")
