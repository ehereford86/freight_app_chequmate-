from fastapi import APIRouter
from fuel import get_fuel_surcharge

router = APIRouter()

@router.get("/calculate-rate", description="This is the endpoint your UI button calls.\nIt returns a full breakdown and includes national fuel surcharge per mile.")
def calculate_rate(
    miles: float = 0,
    linehaul_rate: float = 0,
    deadhead_miles: float = 0,
    deadhead_rate: float = 0,
    broker_margin_percent: float = 0.10,
    broker_fee_flat: float = 0,
    detention: float = 0,
    lumper_fee: float = 0,
    extra_stop_fee: float = 0,
):
    fuel = get_fuel_surcharge()
    fs_per_mile = fuel["fuel_surcharge_per_mile"]

    linehaul_total = miles * linehaul_rate
    deadhead_total = deadhead_miles * deadhead_rate
    fuel_total = (miles + deadhead_miles) * fs_per_mile
    accessorials_total = detention + lumper_fee + extra_stop_fee

    subtotal = linehaul_total + deadhead_total + fuel_total + accessorials_total
    broker_margin_amount = subtotal * broker_margin_percent
    total = subtotal + broker_margin_amount + broker_fee_flat

    return {
        "inputs": {
            "miles": miles,
            "linehaul_rate": linehaul_rate,
            "deadhead_miles": deadhead_miles,
            "deadhead_rate": deadhead_rate,
            "broker_margin_percent": broker_margin_percent,
            "broker_fee_flat": broker_fee_flat,
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
            "broker_margin_amount": round(broker_margin_amount, 2),
            "broker_fee_flat": round(broker_fee_flat, 2),
            "total": round(total, 2),
        }
    }