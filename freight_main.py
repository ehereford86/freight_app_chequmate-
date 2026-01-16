from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles


# -----------------------------
# App setup (DEFINE APP FIRST)
# -----------------------------
app = FastAPI(title="Freight App API", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
WEBAPP_DIR = BASE_DIR / "webapp"

# -----------------------------
# Static assets
# -----------------------------
# This makes these work:
#   /webapp/app.css
#   /webapp/app.js
#   /webapp/assets/chequmate-logo.png
if WEBAPP_DIR.exists():
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR)), name="webapp")


# -----------------------------
# Health / Root
# -----------------------------
@app.get("/")
def home():
    return {"message": "Freight app API is running"}

@app.head("/")
def home_head():
    return Response(status_code=200)


# -----------------------------
# Web UI
# -----------------------------
@app.get("/app")
def app_ui():
    index_file = WEBAPP_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(status_code=404, content={"detail": "webapp/index.html not found"})
    return FileResponse(index_file)

# IMPORTANT: allow HEAD /app (Render/proxies health-check this sometimes)
@app.head("/app")
def app_ui_head():
    return Response(status_code=200)

# Optional: silence the harmless favicon 404
@app.get("/favicon.ico")
def favicon():
    ico = WEBAPP_DIR / "assets" / "chequmate-logo.png"
    if ico.exists():
        return FileResponse(ico)
    return Response(status_code=204)


# -----------------------------
# Fuel surcharge (SAFE: never 500)
# -----------------------------
def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _fetch_eia_diesel_price() -> Dict[str, Any]:
    """
    Returns:
      {
        "diesel_price": float|None,
        "source": str|None,
        "error": str|None
      }
    Never raises.
    """
    key = os.getenv("EIA_API_KEY", "").strip()
    if not key:
        return {
            "diesel_price": None,
            "source": None,
            "error": "Missing EIA_API_KEY env var on server (set it on Render)",
        }

    # EIA v2 weekly U.S. No.2 Diesel retail price (commonly used)
    # If EIA changes the series, we still won't crash—error will be returned.
    url = (
        "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
        f"?api_key={key}"
        "&frequency=weekly"
        "&data[0]=value"
        "&facets[series][]=EMD_EPD2D_PTE_NUS_DPG"
        "&sort[0][column]=period"
        "&sort[0][direction]=desc"
        "&offset=0"
        "&length=1"
    )

    try:
        req = Request(url, headers={"User-Agent": "chequmate-freight-app/1.0"})
        with urlopen(req, timeout=15) as r:
            payload = json.loads(r.read().decode("utf-8"))

        data = payload.get("response", {}).get("data", [])
        if not data:
            return {"diesel_price": None, "source": url, "error": "EIA returned no data"}

        price = data[0].get("value", None)
        diesel_price = _safe_float(price, default=0.0)
        if diesel_price <= 0:
            return {"diesel_price": None, "source": url, "error": f"Bad diesel price from EIA: {price}"}

        return {"diesel_price": diesel_price, "source": url, "error": None}

    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        return {"diesel_price": None, "source": url, "error": f"EIA request failed: {e}"}
    except Exception as e:
        return {"diesel_price": None, "source": url, "error": f"Unexpected EIA error: {e}"}

def _fuel_surcharge_per_mile(diesel_price: Optional[float]) -> Dict[str, Any]:
    """
    Simple model:
      base_price: $1.25
      multiplier: 0.06
      surcharge = max(0, diesel_price - base_price) * multiplier
    Never raises.
    """
    base_price = 1.25
    multiplier = 0.06

    if diesel_price is None:
        return {
            "diesel_price": None,
            "base_price": base_price,
            "multiplier_used": multiplier,
            "fuel_surcharge_per_mile": 0.0,
            "error": "No diesel price available",
        }

    surcharge = max(0.0, float(diesel_price) - base_price) * multiplier
    return {
        "diesel_price": float(diesel_price),
        "base_price": base_price,
        "multiplier_used": multiplier,
        "fuel_surcharge_per_mile": float(round(surcharge, 4)),
        "error": None,
    }

@app.get("/fuel-surcharge")
def fuel_surcharge():
    eia = _fetch_eia_diesel_price()
    fuel = _fuel_surcharge_per_mile(eia.get("diesel_price"))
    fuel["source"] = eia.get("source")
    # if missing key, pass that through (but still 200 OK)
    if eia.get("error") and not fuel.get("error"):
        fuel["error"] = eia["error"]
    return fuel


# -----------------------------
# Rate calculator (SAFE: never 500)
# -----------------------------
@app.get("/calculate-rate")
def calculate_rate(
    miles: float = 650,
    linehaul_rate: float = 3.00,
    deadhead_miles: float = 0,
    deadhead_rate: float = 0,
    detention: float = 0,
    lumper_fee: float = 0,
    extra_stop_fee: float = 0,
):
    # sanitize
    miles = max(0.0, _safe_float(miles))
    linehaul_rate = max(0.0, _safe_float(linehaul_rate))
    deadhead_miles = max(0.0, _safe_float(deadhead_miles))
    deadhead_rate = max(0.0, _safe_float(deadhead_rate))
    detention = max(0.0, _safe_float(detention))
    lumper_fee = max(0.0, _safe_float(lumper_fee))
    extra_stop_fee = max(0.0, _safe_float(extra_stop_fee))

    # Fuel lookup should NEVER kill the calculator
    eia = _fetch_eia_diesel_price()
    fuel = _fuel_surcharge_per_mile(eia.get("diesel_price"))
    fuel["source"] = eia.get("source")
    if eia.get("error") and not fuel.get("error"):
        fuel["error"] = eia["error"]

    fuel_surcharge_per_mile = _safe_float(fuel.get("fuel_surcharge_per_mile"), 0.0)

    linehaul_total = miles * linehaul_rate
    deadhead_total = deadhead_miles * deadhead_rate
    fuel_total = miles * fuel_surcharge_per_mile
    accessorials_total = detention + lumper_fee + extra_stop_fee
    total = linehaul_total + deadhead_total + fuel_total + accessorials_total

    return {
        "inputs": {
            "miles": miles,
            "linehaul_rate": linehaul_rate,
            "deadhead_miles": deadhead_miles,
            "deadhead_rate": deadhead_rate,
            "detention": detention,
            "lumper_fee": lumper_fee,
            "extra_stop_fee": extra_stop_fee,
        },
        "fuel": fuel,
        "breakdown": {
            "linehaul_total": round(linehaul_total, 2),
            "deadhead_total": round(deadhead_total, 2),
            "fuel_total": round(fuel_total, 2),
            "accessorials_total": round(accessorials_total, 2),
            "subtotal": round(total, 2),
            "total": round(total, 2),
        },
    }


# -----------------------------
# Optional: keep your other routers, but NEVER crash if they fail.
# -----------------------------
for mod_name in ("auth", "fuel", "pricing", "fmcsa"):
    try:
        module = __import__(mod_name)
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
    except Exception:
        pass