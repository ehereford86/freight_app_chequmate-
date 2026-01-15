import os
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
SERIES_DIESEL_US = "EMD_EPD2D_PTE_NUS_DPG"

def get_fuel_surcharge(
    api_key: str | None = None,
    base_price: float = 1.25,
    multiplier: float = 0.06,
):
    """
    Returns a dict that ALWAYS contains:
      - diesel_price (float|None)
      - fuel_surcharge_per_mile (float|None)
      - base_price (float)
      - multiplier_used (float)
      - source (str)
      - error (str|None)   <-- present only on failure

    Formula:
      fs_per_mile = max(0, diesel_price - base_price) * multiplier
    """
    if api_key is None:
        api_key = os.getenv("EIA_API_KEY", "").strip()

    # If no env var exists, fallback to your current default key (keeps it working)
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

    try:
        r = requests.get(EIA_BASE, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        diesel_str = data["response"]["data"][0]["value"]
        diesel_price = float(diesel_str)

        fs_per_mile = 0.0 if diesel_price <= base_price else (diesel_price - base_price) * multiplier

        return {
            "diesel_price": round(diesel_price, 3),
            "fuel_surcharge_per_mile": round(fs_per_mile, 4),
            "base_price": float(base_price),
            "multiplier_used": float(multiplier),
            "source": source_url,
            "error": None,
        }

    except Exception as e:
        # CRITICAL: still return the same keys so callers don't crash
        return {
            "diesel_price": None,
            "fuel_surcharge_per_mile": None,
            "base_price": float(base_price),
            "multiplier_used": float(multiplier),
            "source": source_url,
            "error": str(e),
        }

@router.get("/fuel-surcharge")
def fuel_surcharge():
    data = get_fuel_surcharge()
    # Don’t throw 500; return a useful message if it failed
    if data.get("fuel_surcharge_per_mile") is None:
        raise HTTPException(status_code=502, detail=f"Fuel surcharge unavailable: {data.get('error')}")
    return data