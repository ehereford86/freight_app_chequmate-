import requests

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
SERIES_DIESEL_US = "EMD_EPD2D_PTE_NUS_DPG"

def get_fuel_surcharge(
    api_key: str = "8TNeHiHQAm2CuZjIRiemysGRJlufFNEfkogwLDba",
    base_price: float = 1.25,
    multiplier: float = 0.06,
):
    """
    Returns:
      - diesel_price (float)
      - fuel_surcharge_percent (float)
      - base_price (float)
      - multiplier_used (float)
      - source (str)

    Formula:
      fuel_surcharge_percent = max(0, (diesel_price - base_price) / multiplier) * 100
    """
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
        data = r.json()

        # Expected shape: data["response"]["data"][0]["value"]
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

    except Exception as e:
        return {
            "diesel_price": None,
            "fuel_surcharge_percent": None,
            "base_price": base_price,
            "multiplier_used": multiplier,
            "source": source_url,
            "error": str(e),
        }
