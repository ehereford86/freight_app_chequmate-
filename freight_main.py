from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Chequmate Freight System", version="0.1.0")


def _try_include(module_name: str, router_attr: str = "router") -> None:
    """
    Best-effort include_router so Render doesn't crash if a module isn't present.
    Keeps startup stable across environments.
    """
    try:
        mod = __import__(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] WARNING: could not include {module_name}.{router_attr}: {e!r}")


@app.get("/", include_in_schema=False)
def root():
    # Simple health + hint for humans
    return JSONResponse({"ok": True, "service": "chequmate-freight-api"})


# Core API routers
_try_include("auth")            # /login, /register (if present)
_try_include("db")              # if you expose anything (optional)
_try_include("pricing")         # if router exists (optional)
_try_include("loads")           # load routes
_try_include("negotiate")       # negotiate routes
_try_include("fuel")            # fuel routes

# UI routers (these are the ones you need on Render)
_try_include("broker_ui")
_try_include("driver_ui")
_try_include("dispatcher_ui")
