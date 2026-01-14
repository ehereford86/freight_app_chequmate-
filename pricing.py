# pricing.py
from dataclasses import dataclass

@dataclass
class QuoteInput:
    miles: int
    equipment: str
    is_alaska: bool
    over_width: bool


def calculate_chequmat_quote(data: QuoteInput):
    # Base rates
    BASE_RATES = {
        "RGN": 4.10,
        "FLATBED": 3.25,
        "STEPDECK": 3.60
    }

    base_rate = BASE_RATES.get(data.equipment, 3.00)
    base_linehaul = data.miles * base_rate

    # Alaska uplift
    alaska_multiplier = 1.30 if data.is_alaska else 1.00
    adjusted_linehaul = base_linehaul * alaska_multiplier

    # Permits / OSOW
    permit_cost = 3000 if data.over_width else 0

    carrier_cost = adjusted_linehaul + permit_cost

    # Chequmat margin logic
    broker_margin = max(1500, carrier_cost * 0.07)

    shipper_rate = carrier_cost + broker_margin

    return {
        "miles": data.miles,
        "equipment": data.equipment,
        "carrier_cost": round(carrier_cost, 2),
        "broker_margin": round(broker_margin, 2),
        "shipper_rate": round(shipper_rate, 2)
    }
