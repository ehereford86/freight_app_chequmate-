import os
import requests
from fastapi import APIRouter

router = APIRouter()

EIA_API_KEY = os.getenv("EIA_API_KEY", "").strip()

@router.get("/fuel-surcharge")
def fuel_surcharge():
    base_price = 1.25
    multiplier = 0.06

    if not EIA_API_KEY:
        return {
            "diesel_price": None,
            "base_price": base_price,
            "multiplier_used": multiplier,
            "fuel_surcharge_per_mile": 0.0,
            "error": "Missing EIA_API_KEY env var on server",
            "source": None
        }

    try:
        url = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
        params = {
            "api_key": EIA_API_KEY,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[series][]": "EMD_EPD2D_PTE_NUS_DPG",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": 0,
            "length": 1,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        j = r.json()
        val = j["response"]["data"][0]["value"]
        diesel = float(val)

        per_mile = max(0.0, (diesel - base_price) * multiplier)

        return {
            "diesel_price": diesel,
            "base_price": base_price,
            "multiplier_used": multiplier,
            "fuel_surcharge_per_mile": per_mile,
            "error": None,
            "source": "EIA"
        }
    except Exception:
        return {
            "diesel_price": None,
            "base_price": base_price,
            "multiplier_used": multiplier,
            "fuel_surcharge_per_mile": 0.0,
            "error": "No diesel price available",
            "source": None
        }
