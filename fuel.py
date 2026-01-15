import os
import requests
from fastapi import APIRouter

router = APIRouter()

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
SERIES_DIESEL_US = "EMD_EPD2D_PTE_NUS_DPG"

def get_fuel_surcharge(
    base_price: float = 1.25,
    multiplier: float = 0.06,
):
    api_key = (os.getenv("EIA_API_KEY") or "").strip()

    # Fallback (keeps the app functional even if env var isn't set yet)
    if not api_key:
        api_key = "8TNeHiHQAm2CuZjIRiemysGRJlufFNEfkogwLDba"

    params = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": SERIES_DIESEL_US,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 1,
    }

    source_url = (
        f"{EIA_BASE}?api_key={api_key}"
        f"&frequency=weekly&data[0]=value"
        f"&facets[series][]={SERIES_DIESEL_US}"
        f"&sort[0][column]=period&sort[0][direction]=desc&length=1"
    )

    r = requests.get(EIA_BASE, params=params, timeout=10)
    data = r.json()

    diesel_str = data["response"]["data"][0]["value"]
    diesel_price = float(diesel_str)

    if diesel_price <= base_price:
        fs_per_mile = 0.0
    else:
        fs_per_mile = (diesel_price - base_price) * multiplier

    return {
        "diesel_price": round(diesel_price, 3),
        "fuel_surcharge_per_mile": round(fs_per_mile, 4),
        "base_price": base_price,
        "multiplier_used": multiplier,
        "source": source_url,
    }

@router.get("/fuel-surcharge")
def fuel_surcharge():
    return get_fuel_surcharge()