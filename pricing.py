from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import os
from urllib.parse import urlencode

# Use the SAME fuel module that powers /_debug/eia
import fuel

router = APIRouter()

def _to_float(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)

def _role_context(request: Request) -> dict:
    """
    Best-effort role context.
    We do NOT break the calculator if auth changes.
    If Authorization header contains a Bearer token and auth supports it,
    it can be extended later. For now keep stable.
    """
    return {
        "logged_in": False,
        "role": "guest",
        "broker_status": "none",
    }

@router.get("/calculate-rate")
def calculate_rate(
    request: Request,
    miles: float = 0.0,
    linehaul_rate: float = 0.0,
    deadhead_miles: float = 0.0,
    deadhead_rate: float = 0.0,
    detention: float = 0.0,
    lumper_fee: float = 0.0,
    extra_stop_fee: float = 0.0,
):
    """
    GET /calculate-rate

    Returns:
      - inputs
      - fuel (diesel price + surcharge)
      - breakdown
      - role_context (stable, guest by default)
    """
    try:
        miles = _to_float(miles, 0.0)
        linehaul_rate = _to_float(linehaul_rate, 0.0)
        deadhead_miles = _to_float(deadhead_miles, 0.0)
        deadhead_rate = _to_float(deadhead_rate, 0.0)
        detention = _to_float(detention, 0.0)
        lumper_fee = _to_float(lumper_fee, 0.0)
        extra_stop_fee = _to_float(extra_stop_fee, 0.0)

        # Totals (simple + predictable)
        linehaul_total = miles * linehaul_rate
        deadhead_total = deadhead_miles * deadhead_rate
        accessorials_total = detention + lumper_fee + extra_stop_fee

        # Fuel surcharge settings (same defaults you’ve been using)
        base_price = _to_float(os.environ.get("FUEL_BASE_PRICE", 1.25), 1.25)
        multiplier = _to_float(os.environ.get("FUEL_MULTIPLIER", 0.06), 0.06)

        # IMPORTANT: use the exact same EIA function as /_debug/eia
        diesel_price, meta = fuel.get_diesel_price()

        if diesel_price is None:
            per_mile = 0.0
            fuel_total = 0.0
            fuel_block = {
                "diesel_price": None,
                "base_price": base_price,
                "multiplier_used": multiplier,
                "fuel_surcharge_per_mile": 0.0,
                "error": "No diesel price available (check EIA_API_KEY)",
                "source": None,
            }
        else:
            # Simple common model: (diesel - base) * multiplier, never below 0
            per_mile = max(0.0, (float(diesel_price) - base_price) * multiplier)
            fuel_total = per_mile * miles
            fuel_block = {
                "diesel_price": float(diesel_price),
                "base_price": base_price,
                "multiplier_used": multiplier,
                "fuel_surcharge_per_mile": per_mile,
                "error": None,
                "source": "EIA",
            }

        subtotal = linehaul_total + deadhead_total + accessorials_total
        total = subtotal + fuel_total

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
            "fuel": fuel_block,
            "breakdown": {
                "linehaul_total": linehaul_total,
                "deadhead_total": deadhead_total,
                "fuel_total": fuel_total,
                "accessorials_total": accessorials_total,
                "subtotal": subtotal,
                "total": total,
            },
            "role_context": _role_context(request),
        }

    except Exception:
        return JSONResponse(status_code=500, content={"detail": "Calculation failed"})
