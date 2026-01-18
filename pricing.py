from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

import fuel
from auth import get_current_user_optional

router = APIRouter()

def _to_float(v, default=0.0):
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)

@router.get("/calculate-rate")
def calculate_rate(
    miles: float = 0.0,
    linehaul_rate: float = 0.0,
    deadhead_miles: float = 0.0,
    deadhead_rate: float = 0.0,
    detention: float = 0.0,
    lumper_fee: float = 0.0,
    extra_stop_fee: float = 0.0,
    user=Depends(get_current_user_optional),
):
    """
    GET /calculate-rate
    Returns:
      - inputs
      - fuel breakdown (using EIA diesel price if available)
      - totals breakdown
      - role context
    """
    try:
        miles = _to_float(miles, 0.0)
        linehaul_rate = _to_float(linehaul_rate, 0.0)
        deadhead_miles = _to_float(deadhead_miles, 0.0)
        deadhead_rate = _to_float(deadhead_rate, 0.0)
        detention = _to_float(detention, 0.0)
        lumper_fee = _to_float(lumper_fee, 0.0)
        extra_stop_fee = _to_float(extra_stop_fee, 0.0)

        # Linehaul + deadhead
        linehaul_total = miles * linehaul_rate
        deadhead_total = deadhead_miles * deadhead_rate

        # Accessorials
        accessorials_total = detention + lumper_fee + extra_stop_fee

        # Fuel surcharge per mile (use same logic as fuel.py)
        base_price = 1.25
        multiplier = 0.06

        diesel_price, meta = fuel.get_diesel_price()
        if diesel_price is None:
            per_mile = 0.0
            fuel_error = "No diesel price available (check EIA_API_KEY)"
            fuel_source = None
        else:
            per_mile = max(0.0, (float(diesel_price) - base_price) * multiplier)
            fuel_error = None
            fuel_source = "EIA"

        fuel_total = miles * per_mile

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
            "fuel": {
                "diesel_price": diesel_price,
                "base_price": base_price,
                "multiplier_used": multiplier,
                "fuel_surcharge_per_mile": per_mile,
                "error": fuel_error,
                "source": fuel_source,
                "meta": meta,
            },
            "breakdown": {
                "linehaul_total": linehaul_total,
                "deadhead_total": deadhead_total,
                "fuel_total": fuel_total,
                "accessorials_total": accessorials_total,
                "subtotal": subtotal,
                "total": total,
            },
            "role_context": {
                "logged_in": bool(user),
                "role": (user["role"] if user else "guest"),
                "broker_status": (user.get("broker_status") if user else "none"),
            },
        }
    except HTTPException:
        raise
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "Calculation failed"})
