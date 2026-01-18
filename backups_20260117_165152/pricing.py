from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth import get_current_user
from fuel import fuel_surcharge

router = APIRouter()

@router.get("/calculate-rate")
def calculate_rate(
    request: Request,
    miles: float,
    linehaul_rate: float,
    deadhead_miles: float = 0.0,
    deadhead_rate: float = 0.0,
    detention: float = 0.0,
    lumper_fee: float = 0.0,
    extra_stop_fee: float = 0.0,
):
    try:
        # Guest allowed; role info is returned for UI decisions
        user = None
        try:
            user = get_current_user(request)
        except Exception:
            user = None

        fuel = fuel_surcharge()
        fpm = float(fuel.get("fuel_surcharge_per_mile") or 0.0)

        linehaul_total = miles * linehaul_rate
        deadhead_total = deadhead_miles * deadhead_rate
        accessorials_total = detention + lumper_fee + extra_stop_fee
        fuel_total = miles * fpm

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
            "fuel": fuel,
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
                "broker_status": (user["broker_status"] if user else "none"),
            }
        }
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "Calculation failed"})
