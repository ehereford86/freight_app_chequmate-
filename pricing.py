# pricing.py
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from fuel import get_fuel_surcharge
from auth import SECRET_KEY, ALGORITHM, get_user_record

router = APIRouter()

# Optional auth: lets drivers/dispatchers use calculator without logging in,
# but if a valid token is present we can tailor the response by role.
oauth2_optional = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def get_optional_user(token: Optional[str] = Depends(oauth2_optional)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        return get_user_record(username)
    except JWTError:
        return None
    except Exception:
        return None


def is_broker_role(role: str) -> bool:
    return role in ("broker", "broker_carrier", "admin")


@router.get(
    "/calculate-rate",
    description=(
        "This is the endpoint your UI button calls.\n"
        "It returns a full breakdown and includes national fuel surcharge per mile.\n"
        "Broker-only fields are hidden from drivers/dispatchers."
    ),
)
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
    user=Depends(get_optional_user),
):
    role = (user or {}).get("role") or "guest"
    broker_view = is_broker_role(role)

    # Always compute fuel the same way
    fuel = get_fuel_surcharge()
    fs_per_mile = float(fuel.get("fuel_surcharge_per_mile") or 0.0)

    # Core math
    linehaul_total = miles * linehaul_rate
    deadhead_total = deadhead_miles * deadhead_rate
    fuel_total = (miles + deadhead_miles) * fs_per_mile
    accessorials_total = detention + lumper_fee + extra_stop_fee

    subtotal = linehaul_total + deadhead_total + fuel_total + accessorials_total

    # Non-brokers: force broker fields OFF, even if they pass them in query params
    if not broker_view:
        broker_margin_percent = 0.0
        broker_fee_flat = 0.0

    broker_margin_amount = subtotal * broker_margin_percent
    total = subtotal + broker_margin_amount + broker_fee_flat

    # Build response
    resp = {
        "role_view": role,  # helps you debug who is seeing what
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
        },
    }

    # Broker-only fields included ONLY for broker/admin roles
    if broker_view:
        resp["inputs"]["broker_margin_percent"] = broker_margin_percent
        resp["inputs"]["broker_fee_flat"] = broker_fee_flat
        resp["breakdown"]["broker_margin_amount"] = round(broker_margin_amount, 2)
        resp["breakdown"]["broker_fee_flat"] = round(broker_fee_flat, 2)

    return resp