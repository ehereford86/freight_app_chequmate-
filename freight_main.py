from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Chequmate Freight System", version="0.1.0")

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


def _try_include(module_name: str, router_attr: str = "router") -> None:
    """
    Best-effort include_router so prod doesn't crash if a module isn't present.
    Logs loudly so failures show up in Render logs.
    """
    try:
        mod = __import__(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] ERROR including {module_name}.{router_attr}: {e!r}")


@app.get("/", include_in_schema=False)
def root():
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


# ---- Static + Universal Login UI ----
# Render needs this so /static/login.html and images work.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"[boot] mounted /static -> {STATIC_DIR}")
else:
    print(f"[boot] WARNING: static dir not found at {STATIC_DIR}")


@app.get("/login-ui", include_in_schema=False)
def login_ui():
    f = STATIC_DIR / "login.html"
    if not f.exists():
        return JSONResponse(status_code=404, content={"detail": "static/login.html not found"})
    return FileResponse(str(f), media_type="text/html")


# ---- Core API routers ----
_try_include("auth")
_try_include("loads")
_try_include("negotiate")
_try_include("fuel")
_try_include("pricing")
_try_include("fmcsa")
_try_include("admin_ui")

# ---- UI routers (already working for you) ----
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
