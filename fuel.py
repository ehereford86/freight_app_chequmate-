# fuel.py
import os
import requests
from fastapi import APIRouter

router = APIRouter()


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

    # EIA v2 endpoint (weekly U.S. on-highway diesel)
    # If EIA ever changes their series IDs, this debug endpoint will show us.
    url = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
    params = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": "EMD_EPD2D_PTE_NUS_DPG",  # U.S. No 2 Diesel Retail Prices (Dollars per Gallon)
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 1,
    }

    try:
        r = requests.get(url, params=params, timeout=10)

        # Defensive: mask key if it appears in URL (it will, since it's a query param)
        safe_url = r.url.replace(api_key, _mask(api_key))

        meta = {
            "ok": bool(r.ok),
            "status": int(r.status_code),
            "url": safe_url,
            "error": None,
        }

        if not r.ok:
            # Keep short to avoid giant logs, but enough to see the real reason.
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


@router.get("/_debug/eia")
def debug_eia():
    """
    Safe debug endpoint:
    - shows whether EIA call worked
    - shows status code + short error text
    - masks the API key
    """
    price, meta = get_diesel_price()
    return {"diesel_price": price, "meta": meta}
