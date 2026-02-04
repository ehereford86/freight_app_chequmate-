from __future__ import annotations

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Chequmate Freight System", version="0.1.0")


def _try_include(module_name: str, router_attr: str = "router") -> None:
    """
    Best-effort include_router so prod doesn't crash if a module isn't present.
    IMPORTANT: We log loudly so you can see failures in Render logs.
    """
    try:
        mod = __import__(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] ERROR including {module_name}.{router_attr}: {e!r}")


# Serve your SPA + static assets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/webapp", StaticFiles(directory=WEBAPP_DIR), name="webapp")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root(request: Request):
    accept = (request.headers.get("accept") or "").lower()

    # If a browser is hitting the root, send them to the universal app.
    # CLI tools typically accept application/json, so they keep getting JSON.
    if "text/html" in accept and "application/json" not in accept:
        return RedirectResponse(url="/app", status_code=302)

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
_try_include("admin_ui")

# Universal login / registration SPA routes
_try_include("universal_ui")

# Existing UI routers (do not modify their files)
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
