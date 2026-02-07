from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

import auth

HERE = Path(__file__).resolve().parent
FAVICON_PATH = HERE / "static" / "favicon.ico"


def _is_public_path(path: str) -> bool:
    # Public = allowed through the middleware (route itself can still enforce auth)
    if path in {
        "/", "/openapi.json", "/docs", "/redoc",

        # Auth endpoints
        "/login", "/register",
        "/verify-token",
        "/me/set-email",
        "/forgot-password", "/password-reset/request",
        "/reset-password", "/password-reset/confirm",

        # UI pages
        "/login-ui", "/driver-ui", "/broker-ui", "/dispatcher-ui", "/admin-ui",

        # Assets
        "/favicon.ico",

        # Internal
        "/__importcheck",
    }:
        return True

    if path.startswith("/static/"):
        return True
    if path.startswith("/docs/") or path.startswith("/redoc/"):
        return True
    return False


def _required_role_for_path(path: str) -> Optional[str]:
    if path.startswith("/driver/"):
        return "driver"
    if path.startswith("/dispatcher/"):
        return "dispatcher"
    if path.startswith("/broker/"):
        return "broker"
    if path.startswith("/admin/"):
        return "admin"
    return None


def _deny(status: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": msg})


app = FastAPI(title="Chequmate Freight System", version="0.1.0")

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("[boot] mounted /static -> ./static")
except Exception as e:
    print("[boot] WARNING: could not mount /static:", repr(e))


# Serve favicon as a real file (GET + HEAD)
@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def favicon():
    if not FAVICON_PATH.exists():
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return FileResponse(str(FAVICON_PATH))


@app.middleware("http")
async def rbac_abac_guard(request: Request, call_next: Callable):
    path = request.url.path or "/"

    if _is_public_path(path):
        return await call_next(request)

    required = _required_role_for_path(path)

    # Deny-by-default for any unclassified route.
    if required is None:
        return _deny(403, "Access denied (unclassified route).")

    # Authenticate
    try:
        user = auth.get_current_user(authorization=request.headers.get("authorization"))
    except Exception as e:
        msg = getattr(e, "detail", None) or "Unauthorized"
        code = getattr(e, "status_code", 401)
        return _deny(int(code), str(msg))

    # Enforce role
    role = (user.get("role") or "").strip().lower()
    if role != required:
        return _deny(403, f"{required} role required")

    # ABAC add-ons
    if required == "broker":
        if (user.get("broker_status") or "none").lower() != "approved":
            return _deny(403, "Broker not approved")

    if required == "dispatcher":
        broker_mc = (user.get("broker_mc") or "").strip()
        if not broker_mc:
            return _deny(403, "Dispatcher not linked to a broker")

    request.state.user = user
    return await call_next(request)


def _safe_include(modname: str):
    try:
        mod = __import__(modname)
        router = getattr(mod, "router", None)
        if router is None:
            print(f"[boot] WARNING: {modname} has no router")
            return
        app.include_router(router)
        print(f"[boot] included router: {modname}.router")
    except Exception as e:
        print(f"[boot] WARNING: could not include {modname}.router:", repr(e))


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


@app.get("/")
def root():
    return {"ok": True, "service": "chequmate-freight-local"}
