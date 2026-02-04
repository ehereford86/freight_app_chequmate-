import json
import os
import requests
from fastapi import APIRouter, HTTPException, Header

router = APIRouter()

# -----------------------------
# Debug route safety
# -----------------------------
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

# -----------------------------
# EIA Diesel price (weekly)
# -----------------------------
EIA_URL = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
EIA_KEY_ENV = "EIA_API_KEY"

# National default series (what you already used)
EIA_SERIES_NATIONAL = os.environ.get("EIA_SERIES_NATIONAL", "EMD_EPD2D_PTE_NUS_DPG").strip()

# Optional: map state -> EIA series ID (JSON string)
# Example:
# export EIA_SERIES_BY_STATE_JSON='{"TX":"<series>", "CA":"<series>"}'
EIA_SERIES_BY_STATE_JSON = os.environ.get("EIA_SERIES_BY_STATE_JSON", "").strip()

def _load_state_series_map() -> dict:
    if not EIA_SERIES_BY_STATE_JSON:
        return {}
    try:
        m = json.loads(EIA_SERIES_BY_STATE_JSON)
        if isinstance(m, dict):
            out = {}
            for k, v in m.items():
                kk = str(k).strip().upper()
                vv = str(v).strip()
                if kk and vv:
                    out[kk] = vv
            return out
    except Exception:
        return {}
    return {}

def _pick_series_id(origin_state: str | None, mode: str | None) -> tuple[str, dict]:
    """
    mode:
      - "national" (default)
      - "origin_state" (try state map; fallback national)
    """
    mode = (mode or "national").strip().lower()
    state = (origin_state or "").strip().upper()

    meta = {
        "mode": mode,
        "origin_state": state or None,
        "series_id": None,
        "series_fallback": False,
    }

    if mode == "origin_state" and state:
        m = _load_state_series_map()
        if state in m:
            meta["series_id"] = m[state]
            return m[state], meta
        meta["series_fallback"] = True

    meta["series_id"] = EIA_SERIES_NATIONAL
    return EIA_SERIES_NATIONAL, meta

def get_diesel_price(origin_state: str | None = None, mode: str | None = None):
    """
    Returns: (diesel_price_float_or_None, meta_dict)

    meta includes:
      - ok/status/error/url
      - source = "EIA"
      - series_id
      - period (weekly date string) when available
      - mode/origin_state and whether a fallback happened
    """
    api_key = os.environ.get(EIA_KEY_ENV, "").strip()
    if not api_key:
        return None, {
            "ok": False,
            "status": None,
            "error": f"Missing {EIA_KEY_ENV}",
            "url": None,
            "source": "UNAVAILABLE",
            "series_id": None,
            "period": None,
            "mode": (mode or "national"),
            "origin_state": (origin_state or None),
        }

    series_id, pick_meta = _pick_series_id(origin_state, mode)

    params = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 1,
    }

    try:
        r = requests.get(EIA_URL, params=params, timeout=10)
        safe_url = r.url.replace(api_key, _mask(api_key))

        meta = {
            "ok": bool(r.ok),
            "status": int(r.status_code),
            "url": safe_url,
            "error": None,
            "source": "EIA",
            "series_id": series_id,
            "period": None,
            **pick_meta,
        }

        if not r.ok:
            text = (r.text or "")[:300]
            meta["error"] = f"HTTP {r.status_code}: {text}"
            meta["source"] = "EIA_ERROR"
            return None, meta

        j = r.json()
        data = (((j or {}).get("response") or {}).get("data") or [])
        if not data:
            meta["error"] = "No data rows returned"
            meta["source"] = "EIA_ERROR"
            return None, meta

        row = data[0] or {}
        meta["period"] = row.get("period")

        val = row.get("value", None)
        try:
            return float(val), meta
        except Exception:
            meta["error"] = f"Bad value type: {repr(val)}"
            meta["source"] = "EIA_ERROR"
            return None, meta

    except Exception as ex:
        return None, {
            "ok": False,
            "status": None,
            "error": f"Exception: {repr(ex)}",
            "url": EIA_URL,
            "source": "EIA_ERROR",
            "series_id": series_id,
            "period": None,
            **pick_meta,
        }

@router.get("/_debug/eia", include_in_schema=False)
def debug_eia(x_debug_token: str | None = Header(default=None, alias="X-Debug-Token")):
    _require_debug_token(x_debug_token)
    price, meta = get_diesel_price()
    return {"diesel_price": price, "meta": meta}
