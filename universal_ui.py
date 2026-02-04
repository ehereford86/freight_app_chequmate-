from __future__ import annotations

import os
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WEBAPP_INDEX = os.path.join(BASE_DIR, "webapp", "index.html")
STATIC_LOGIN = os.path.join(BASE_DIR, "static", "login.html")


@router.get("/app", include_in_schema=False)
def app_index():
    # Your universal SPA entrypoint
    return FileResponse(WEBAPP_INDEX)


@router.get("/login-ui", include_in_schema=False)
def legacy_login():
    # Optional: your older standalone login page
    return FileResponse(STATIC_LOGIN)


@router.get("/portal", include_in_schema=False)
def portal_redirect():
    # Friendly alias
    return RedirectResponse(url="/app", status_code=302)
