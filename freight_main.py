from __future__ import annotations

import os
import importlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Chequmate Freight System", version="0.1.0")


def _try_include(module_name: str, router_attr: str = "router") -> None:
    """
    Best-effort include_router so prod doesn't crash if a module isn't present.
    IMPORTANT: We log loudly so you can see failures in Render logs.
    """
    try:
        mod = importlib.import_module(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] ERROR including {module_name}.{router_attr}: {e!r}")


# --- Static files (Render needs this, since it runs freight_main:app) ---
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists() and STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"[boot] mounted /static -> {STATIC_DIR}")
else:
    print(f"[boot] WARNING: static dir not found at {STATIC_DIR}")


# --- Routes ---
@app.get("/", include_in_schema=False)
def root():
    # Universal entry: send users to the login portal
    return RedirectResponse(url="/login-ui", status_code=302)


@app.get("/__version", include_in_schema=False)
def version():
    return JSONResponse(
        {
            "ok": True,
            "render_git_commit": os.environ.get("RENDER_GIT_COMMIT", ""),
            "python": os.environ.get("PYTHON_VERSION", ""),
        }
    )


@app.get("/__routes", include_in_schema=False)
def routes():
    """
    Debug helper: shows what routes are ACTUALLY mounted in the running app.
    Safe: returns only method + path.
    """
    out = []
    for r in app.routes:
        path = getattr(r, "path", "")
        methods = sorted(list(getattr(r, "methods", []) or []))
        if path:
            out.append({"path": path, "methods": methods})
    out.sort(key=lambda x: x["path"])
    return {"ok": True, "count": len(out), "routes": out}


@app.get("/__importcheck", include_in_schema=False)
def importcheck():
    """
    Debug helper: attempts to import each module and reports success/failure.
    This tells us why /register is missing on Render (auth import error, etc).
    """
    modules = [
        "auth",
        "loads",
        "negotiate",
        "fuel",
        "pricing",
        "fmcsa",
        "admin_ui",
        "login_ui",
        "broker_ui",
        "driver_ui",
        "dispatcher_ui",
    ]

    results: list[dict[str, Any]] = []
    for name in modules:
        row: dict[str, Any] = {"module": name, "ok": False}
        try:
            mod = importlib.import_module(name)
            row["ok"] = True
            row["has_router"] = hasattr(mod, "router")
            row["file"] = getattr(mod, "__file__", "")
        except Exception as e:
            row["error"] = repr(e)
        results.append(row)

    return {"ok": True, "results": results}


# Core API routers
_try_include("auth")
_try_include("loads")
_try_include("negotiate")
_try_include("fuel")
_try_include("pricing")
_try_include("fmcsa")
_try_include("admin_ui")

# UI routers exposed on Render
_try_include("login_ui")
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
