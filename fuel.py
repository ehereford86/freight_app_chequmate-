# fuel.py
import os
import requests
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()


def _debug_enabled() -> bool:
    return os.environ.get("ENABLE_DEBUG_ROUTES", "0").strip() == "1"


def _require_admin(user=Depends(lambda: None)):
    """
    Requires an authenticated admin user.
    Uses auth.get_current_user() if available; otherwise denies access.
    """
    try:
        import auth
        get_current_user = getattr(auth, "get_current_user", None)
        if get_current_user is None:
            raise HTTPException(status_code=403, detail="Admin only")
        user = get_current_user()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin only")

    if not user or (isinstance(user, dict) and user.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _mask(s: str, keep: int = 4) -> str:
    """Mask secrets for debug output."""
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return ("*" * (len(s) - keep)) + s[-keep:]


def get_diesel_price():
    """
    Fetch diesel price from EIA.
    Returns:
      (diesel_price_float_or_None, meta_dict)

    meta_dict never includes the API key (only masked length/last chars).
    """
    api_key = os.environ.get("EIA_API_KEY", "")
    if not api_key:
        return None, {
            "ok": False,
            "status": None,
            "error": "Missing EIA_API_KEY",
            "url": None,
        }

    url = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
    params = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": "EMD_EPD2D_PTE_NUS_DPG",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 1,
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        safe_url = r.url.replace(api_key, _mask(api_key))

        meta = {
            "ok": bool(r.ok),
            "status": int(r.status_code),
            "url": safe_url,
            "error": None,
        }

        if not r.ok:
            text = (r.text or "")[:300]
            meta["error"] = f"HTTP {r.status_code}: {text}"
            return None, meta

        j = r.json()
        data = (((j or {}).get("response") or {}).get("data") or [])
        if not data:
            meta["error"] = "No data rows returned"
            return None, meta

        val = data[0].get("value", None)
        try:
            return float(val), meta
        except Exception:
            meta["error"] = f"Bad value type: {repr(val)}"
            return None, meta

    except Exception as ex:
        return None, {
            "ok": False,
            "status": None,
            "error": f"Exception: {repr(ex)}",
            "url": url,
        }


@router.get("/_debug/eia", include_in_schema=False)
def debug_eia(_admin=Depends(_require_admin)):
    """
    Debug endpoint is OFF unless ENABLE_DEBUG_ROUTES=1.
    Admin-only even when enabled.
    """
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not Found")

    price, meta = get_diesel_price()
    return {"diesel_price": price, "meta": meta}
