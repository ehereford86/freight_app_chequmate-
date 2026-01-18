import os
import requests
from fastapi import APIRouter, HTTPException, Header

router = APIRouter()

def _debug_enabled() -> bool:
    return os.environ.get("ENABLE_DEBUG_ROUTES", "0").strip() == "1"

def _require_debug_token(x_debug_token: str | None) -> None:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not Found")

    secret = os.environ.get("DEBUG_ADMIN_TOKEN", "").strip()
    if not secret:
        raise HTTPException(status_code=404, detail="Not Found")

    if not x_debug_token or x_debug_token.strip() != secret:
        raise HTTPException(status_code=403, detail="Forbidden")

def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return ("*" * (len(s) - keep)) + s[-keep:]

def get_diesel_price():
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
def debug_eia(x_debug_token: str | None = Header(default=None, alias="X-Debug-Token")):
    _require_debug_token(x_debug_token)
    price, meta = get_diesel_price()
    return {"diesel_price": price, "meta": meta}
