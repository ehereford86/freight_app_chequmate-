from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

import auth

router = APIRouter()

def _to_float(x, default=0.0):
    try:
        if x is None or x == "":
            return float(default)
        return float(x)
    except Exception:
        return float(default)

def _to_money(x):
    try:
        return round(float(x) + 1e-9, 2)
    except Exception:
        return 0.0

async def _read_json(request: Request) -> dict:
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            return await request.json()
    except Exception:
        pass
    return {}

def _fuel_calc(miles: float, linehaul_rate: float) -> dict:
    """
    Tries to use fuel.py if present. If not available or EIA key missing,
    returns $0 fuel with a clear note (so the UI stays stable).
    """
    try:
        import fuel  # local module
    except Exception:
        return {
            "diesel_price": None,
            "base_price": 1.25,
            "multiplier_used": 0.06,
            "fuel_surcharge_per_mile": 0.0,
            "error": "Fuel module not available",
            "source": None,
        }

    # Try common helper names without breaking if they don't exist
    try:
        if hasattr(fuel, "fuel_quote"):
            # expected to return dict with fuel_surcharge_per_mile
            return fuel.fuel_quote(base_price=1.25, multiplier=0.06)
        if hasattr(fuel, "get_fuel_quote"):
            return fuel.get_fuel_quote(base_price=1.25, multiplier=0.06)
        if hasattr(fuel, "get_fuel_surcharge_per_mile"):
            per_mile = fuel.get_fuel_surcharge_per_mile(base_price=1.25, multiplier=0.06)
            return {
                "diesel_price": None,
                "base_price": 1.25,
                "multiplier_used": 0.06,
                "fuel_surcharge_per_mile": float(per_mile or 0.0),
                "error": None,
                "source": "EIA",
            }
    except Exception as e:
        return {
            "diesel_price": None,
            "base_price": 1.25,
            "multiplier_used": 0.06,
            "fuel_surcharge_per_mile": 0.0,
            "error": str(e),
            "source": None,
        }

    # Fallback (safe)
    return {
        "diesel_price": None,
        "base_price": 1.25,
        "multiplier_used": 0.06,
        "fuel_surcharge_per_mile": 0.0,
        "error": "No diesel price available (check EIA_API_KEY)",
        "source": None,
    }

def _build_response(request: Request, payload: dict):
    miles = _to_float(payload.get("miles"), 0)
    linehaul_rate = _to_float(payload.get("linehaul_rate") or payload.get("linehaulRate"), 0)
    deadhead_miles = _to_float(payload.get("deadhead_miles") or payload.get("deadheadMiles"), 0)
    deadhead_rate = _to_float(payload.get("deadhead_rate") or payload.get("deadheadRate"), 0)

    detention = _to_float(payload.get("detention"), 0)
    lumper_fee = _to_float(payload.get("lumper_fee") or payload.get("lumperFee"), 0)
    extra_stop_fee = _to_float(payload.get("extra_stop_fee") or payload.get("extraStopFee"), 0)

    # Math
    linehaul_total = miles * linehaul_rate
    deadhead_total = deadhead_miles * deadhead_rate

    fuel_info = _fuel_calc(miles, linehaul_rate)
    fuel_total = miles * float(fuel_info.get("fuel_surcharge_per_mile") or 0.0)

    accessorials_total = detention + lumper_fee + extra_stop_fee
    subtotal = linehaul_total + deadhead_total + fuel_total + accessorials_total
    total = subtotal

    user = auth.get_current_user(request)

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
        "fuel": fuel_info,
        "breakdown": {
            "linehaul_total": _to_money(linehaul_total),
            "deadhead_total": _to_money(deadhead_total),
            "fuel_total": _to_money(fuel_total),
            "accessorials_total": _to_money(accessorials_total),
            "subtotal": _to_money(subtotal),
            "total": _to_money(total),
        },
        "role_context": {
            "logged_in": bool(user),
            "role": (user["role"] if user else "guest"),
            "broker_status": (user["broker_status"] if user else "none"),
        },
    }

@router.get("/calculate-rate")
def calculate_rate_get(
    request: Request,
    miles: float = 0,
    linehaul_rate: float = 0,
    deadhead_miles: float = 0,
    deadhead_rate: float = 0,
    detention: float = 0,
    lumper_fee: float = 0,
    extra_stop_fee: float = 0,
):
    try:
        payload = {
            "miles": miles,
            "linehaul_rate": linehaul_rate,
            "deadhead_miles": deadhead_miles,
            "deadhead_rate": deadhead_rate,
            "detention": detention,
            "lumper_fee": lumper_fee,
            "extra_stop_fee": extra_stop_fee,
        }
        return _build_response(request, payload)
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "Calculation failed"})

@router.post("/calculate-rate")
async def calculate_rate_post(request: Request):
    try:
        payload = await _read_json(request)
        return _build_response(request, payload)
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "Calculation failed"})
