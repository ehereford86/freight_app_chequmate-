from fastapi import APIRouter, Request
from typing import Any

import fuel
from auth import get_current_user, read_json

router = APIRouter()

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)

@router.get("/calculate-rate")
async def calculate_rate(
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
    Public calculator (guest allowed):
    - Uses LIVE diesel (EIA) when EIA_API_KEY is set.
    - Returns role_context if token is present.
    """
    u = get_current_user(request)
    role = (u.get("role") if u else "guest") or "guest"
    broker_status = (u.get("broker_status") if u else "none") or "none"

    miles = _safe_float(miles, 0.0)
    linehaul_rate = _safe_float(linehaul_rate, 0.0)
    deadhead_miles = _safe_float(deadhead_miles, 0.0)
    deadhead_rate = _safe_float(deadhead_rate, 0.0)
    detention = _safe_float(detention, 0.0)
    lumper_fee = _safe_float(lumper_fee, 0.0)
    extra_stop_fee = _safe_float(extra_stop_fee, 0.0)

    diesel_price, meta = fuel.get_diesel_price()

    base_price = 1.25
    multiplier = 0.06
    fsc_per_mile = 0.0
    fuel_err = None
    source = None

    if diesel_price is None:
        fuel_err = (meta or {}).get("error") or "No diesel price available"
        source = (meta or {}).get("source") or "EIA"
    else:
        source = (meta or {}).get("source") or "EIA"
        fsc_per_mile = max(0.0, (float(diesel_price) - base_price) * multiplier)

    linehaul_total = miles * linehaul_rate
    deadhead_total = deadhead_miles * deadhead_rate
    fuel_total = miles * fsc_per_mile
    accessorials_total = detention + lumper_fee + extra_stop_fee

    subtotal = linehaul_total + deadhead_total
    total = subtotal + fuel_total + accessorials_total

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
        "fuel": {
            "diesel_price": diesel_price,
            "base_price": base_price,
            "multiplier_used": multiplier,
            "fuel_surcharge_per_mile": round(fsc_per_mile, 5),
            "error": fuel_err,
            "source": source,
        },
        "breakdown": {
            "linehaul_total": round(linehaul_total, 3),
            "deadhead_total": round(deadhead_total, 3),
            "fuel_total": round(fuel_total, 3),
            "accessorials_total": round(accessorials_total, 3),
            "subtotal": round(subtotal, 3),
            "total": round(total, 3),
        },
        "role_context": {
            "logged_in": bool(u),
            "role": role,
            "broker_status": broker_status,
        },
    }
