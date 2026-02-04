from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_LOGIN_PATH = Path(__file__).resolve().parent / "static" / "login.html"


def _read_login_html() -> str:
    try:
        return _LOGIN_PATH.read_text(encoding="utf-8")
    except Exception as e:
        # Show a simple error page instead of crashing the app.
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Login UI missing</title></head>
<body style="font-family:system-ui;padding:24px;">
<h2>Login UI file not found</h2>
<p>Expected: <code>{_LOGIN_PATH}</code></p>
<p>Error: <code>{repr(e)}</code></p>
</body></html>
"""


@router.get("/login-ui", response_class=HTMLResponse, include_in_schema=False)
def login_ui():
    return HTMLResponse(_read_login_html())
