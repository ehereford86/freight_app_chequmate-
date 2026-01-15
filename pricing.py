from fastapi import APIRouter, HTTPException
from fuel import get_fuel_surcharge

router = APIRouter()

@router.get(
    "/calculate-rate",
    description="Returns a full breakdown and includes national fuel surcharge per mile."
)
def calculate_rate(
    miles: float = 0,
    linehaul_rate: float = 0,
    deadhead_miles: float = 0,
    deadhead_rate: float = 0,
    detention: float = 0,
    lumper_fee: float = 0,
    extra_stop_fee: float = 0,
):
    fuel = get_fuel_surcharge()
    fs_per_mile = fuel.get("fuel_surcharge_per_mile")

    # If fuel lookup failed, do NOT crash with 500
    if fs_per_mile is None:
        raise HTTPException(
            status_code=502,
            detail=f"Fuel surcharge unavailable: {fuel.get('error')}"
        )

    # Core totals
    linehaul_total = miles * linehaul_rate
    deadhead_total = deadhead_miles * deadhead_rate
    fuel_total = (miles + deadhead_miles) * float(fs_per_mile)
    accessorials_total = detention + lumper_fee + extra_stop_fee

    subtotal = linehaul_total + deadhead_total + fuel_total + accessorials_total
    total = subtotal  # broker margin/fees removed for non-broker view

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
            "subtotal": round(subtotal, 2),
            "total": round(total, 2),
        }
    }