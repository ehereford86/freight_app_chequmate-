from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

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


@app.get("/", include_in_schema=False)
def root():
    return JSONResponse({"ok": True, "service": "chequmate-freight-api"})


@app.get("/__version", include_in_schema=False)
def version():
    # Render sets RENDER_GIT_COMMIT on most setups; if not, you'll see empty.
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
_try_include("admin_ui")  # if present / needed

# UI routers you want exposed on Render
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
