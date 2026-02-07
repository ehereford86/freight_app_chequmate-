from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import auth


HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
FAVICON_PATH = STATIC_DIR / "favicon.ico"

# Admin docs access:
# - Option A: query param ?admin_key=...
# - Option B: Authorization: Bearer <admin JWT>
ADMIN_DOCS_KEY = (os.environ.get("ADMIN_DOCS_KEY") or "").strip()


def _deny(status: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": msg})


def _is_public_path(path: str) -> bool:
    # Public landing + static assets + login/register + UIs
    if path in {
        "/",
        "/favicon.ico",
        "/login",
        "/register",
        "/forgot-password",
        "/password-reset/request",
        "/reset-password",
        "/password-reset/confirm",
        "/login-ui",
        "/driver-ui",
        "/broker-ui",
        "/dispatcher-ui",
        "/__importcheck",
        "/static/index.html",
    }:
        return True

    if path.startswith("/static/"):
        return True

    return False


def _required_role_for_path(path: str) -> Optional[str]:
    # Role-gated areas
    if path.startswith("/driver/"):
        return "driver"
    if path.startswith("/dispatcher/"):
        return "dispatcher"
    if path.startswith("/broker/"):
        return "broker"
    if path.startswith("/admin/"):
        return "admin"

    # Special: authenticated, any-role endpoints
    if path in {"/verify-token", "/me/set-email"}:
        return "__auth__"

    # Everything else must be explicitly classified
    return None


def _check_docs_access(request: Request) -> Optional[dict]:
    """
    Returns user dict if admin JWT present, or {} if admin_key is valid,
    or None if not authorized.
    """
    # Option A: admin_key
    key = (request.query_params.get("admin_key") or "").strip()
    if ADMIN_DOCS_KEY and key and key == ADMIN_DOCS_KEY:
        return {}

    # Option B: admin JWT
    try:
        u = auth.get_current_user(authorization=request.headers.get("authorization"))
        role = (u.get("role") or "").strip().lower()
        if role == "admin":
            return u
    except Exception:
        pass

    return None


app = FastAPI(
    title="Chequmate Freight System",
    version="0.1.0",
    docs_url=None,       # lock default docs
    redoc_url=None,
    openapi_url=None,    # lock default openapi
)


# ---- Static ----
try:
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        print(f"[boot] mounted /static -> {STATIC_DIR}")
except Exception as e:
    print("[boot] WARNING: could not mount /static:", repr(e))


# ---- Favicon ----
@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def favicon():
    if FAVICON_PATH.exists():
        return FileResponse(str(FAVICON_PATH))
    # Don’t 500 if missing; just no-content
    return HTMLResponse(status_code=204, content="")


# ---- Root: landing for browsers, JSON for API ----
@app.get("/", include_in_schema=False)
def root(request: Request):
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return RedirectResponse(url="/static/index.html", status_code=302)
    return JSONResponse({"ok": True, "service": "chequmate-freight-api"})


# ---- Locked Docs + OpenAPI ----
@app.get("/docs", include_in_schema=False)
def docs(request: Request):
    ok = _check_docs_access(request)
    if ok is None:
        return _deny(401, "Unauthorized")

    # Serve Swagger UI but point it at our locked openapi route
    return HTMLResponse(
        """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Chequmate Docs (Admin)</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    const url = new URL(window.location.href);
    const admin_key = url.searchParams.get("admin_key") || "";
    const specUrl = admin_key ? ("/openapi.json?admin_key=" + encodeURIComponent(admin_key)) : "/openapi.json";
    SwaggerUIBundle({ url: specUrl, dom_id: "#swagger-ui" });
  </script>
</body>
</html>
        """.strip()
    )


@app.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request):
    ok = _check_docs_access(request)
    if ok is None:
        return _deny(401, "Unauthorized")
    return JSONResponse(app.openapi())


# ---- RBAC/ABAC Guard ----
@app.middleware("http")
async def rbac_abac_guard(request: Request, call_next: Callable):
    path = request.url.path or "/"

    # docs/openapi are handled explicitly above
    if path in {"/docs", "/openapi.json"}:
        return await call_next(request)

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

    # If route just requires authentication (any role), allow
    if required == "__auth__":
        request.state.user = user
        return await call_next(request)

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


# ---- Router include helper ----
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
    "routing_ors",
    "fmcsa",
    "admin",         # IMPORTANT: admin endpoints
    "admin_ui",
    "login_ui",
    "broker_ui",
    "driver_ui",
    "dispatcher_ui",
]:
    _safe_include(_m)
