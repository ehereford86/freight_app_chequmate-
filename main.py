from __future__ import annotations

import importlib
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles


app = FastAPI(title="Chequmate Freight System", version="0.1.0")

# Static mounts (keep traditional structure)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.isdir(".well-known"):
    app.mount("/.well-known", StaticFiles(directory=".well-known"), name="well-known")


@app.get("/favicon.ico")
def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/", response_class=HTMLResponse)
def home():
    return open("static/login.html", encoding="utf-8").read()


def _try_include(module_name: str, router_attr: str = "router") -> None:
    try:
        mod = importlib.import_module(module_name)
        router = getattr(mod, router_attr)
        app.include_router(router)
        print(f"[boot] included router: {module_name}.{router_attr}")
    except Exception as e:
        print(f"[boot] WARNING: could not include {module_name}.{router_attr}: {e!r}")


# Core API / routers (include whatever exists in your repo)
_try_include("auth")            # login/register if you have it
_try_include("loads")           # if your loads routes live here
_try_include("broker")          # if broker routes are here
_try_include("driver")          # if driver routes are here
_try_include("dispatcher")      # if dispatcher routes are here

# Features we KNOW you have
_try_include("fuel")
_try_include("negotiate")
_try_include("broker_ui")

# Add the missing UI pages (fixes your 404s)
_try_include("driver_ui")
_try_include("dispatcher_ui")
