from fastapi import FastAPI, Query, Depends, HTTPException
from auth import (
    init_db,
    create_user,
    authenticate_user,
    create_token,
    get_current_user,
    set_broker_request,
    set_user_role,
)
from fuel import get_fuel_surcharge
from fmcsa import lookup_mc
import sqlite3

app = FastAPI(title="Freight App API")
init_db()


# ---------------------
# BASIC
# ---------------------
@app.get("/")
def home():
    return {"message": "Freight app API is running"}


# Render (and other platforms) may send HEAD / for health checks
@app.head("/")
def home_head():
    return


@app.get("/fuel-surcharge")
def fuel_surcharge():
    return get_fuel_surcharge()


# ---------------------
# AUTH (GET for quick curl testing)
# ---------------------
@app.get("/register")
def register(username: str, password: str, role: str = "dispatcher"):
    # prevent self-registering as broker/broker_carrier
    if role in ("broker", "broker_carrier"):
        raise HTTPException(status_code=400, detail="Use broker-onboarding to request broker access")
    return create_user(username, password, role)


@app.get("/login")
def login(username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Keep token minimal; DB is source of truth on every request
    token = create_token({"sub": user["username"]})
    return {
        "access_token": token,
        "role": user["role"],
        "mc_number": user.get("mc_number", ""),
        "broker_status": user.get("broker_status", "none"),
    }


@app.get("/verify-token")
def verify_token(user=Depends(get_current_user)):
    # user comes from DB every request (role/status can't go stale)
    return {
        "username": user["username"],
        "role": user["role"],
        "mc_number": user.get("mc_number", ""),
        "broker_status": user.get("broker_status", "none"),
    }


# ---------------------
# BROKER ONBOARDING
# ---------------------
@app.get(
    "/broker-onboard",
    description=(
        "Attempt to verify broker status using FMCSA.\n"
        "- If verified: mark approved + upgrade role\n"
        "- If FMCSA blocked (403): mark pending\n"
        "- Else: mark rejected"
    ),
)
def broker_onboard(mc_number: str, user=Depends(get_current_user)):
    result = lookup_mc(mc_number)

    # If FMCSA lookup works and says broker, approve + upgrade role
    if result.get("valid") and result.get("role") in ("broker", "broker_carrier"):
        set_broker_request(user["username"], mc_number, "approved")
        set_user_role(user["username"], result["role"])
        return {
            "approved": True,
            "pending": False,
            "mc_number": mc_number,
            "message": "Broker verified and role upgraded.",
            "details": result,
        }

    # If FMCSA blocked/unavailable, mark pending
    err = (result.get("error") or "")
    if (not result.get("valid")) and ("403" in err):
        set_broker_request(user["username"], mc_number, "pending")
        return {
            "approved": False,
            "pending": True,
            "mc_number": mc_number,
            "message": "FMCSA blocked. Broker access pending manual verification.",
            "details": result,
        }

    # Not broker
    set_broker_request(user["username"], mc_number, "rejected")
    return {
        "approved": False,
        "pending": False,
        "mc_number": mc_number,
        "message": "Not a broker per FMCSA response",
        "details": result,
    }


@app.get("/verify-broker")
def verify_broker(user=Depends(get_current_user)):
    """
    Broker-only verification endpoint.
    IMPORTANT: We do NOT accept a query mc_number here.
    We verify the logged-in user's stored mc_number verifies broker access.
    """
    # Must be a broker role
    if user["role"] not in ("broker", "broker_carrier"):
        raise HTTPException(status_code=403, detail="Broker access only")

    # Must be approved (prevents pending users from hitting broker endpoints)
    if (user.get("broker_status") or "none") != "approved":
        raise HTTPException(status_code=403, detail="Broker not approved")

    mc_number = (user.get("mc_number") or "").strip()
    if not mc_number:
        raise HTTPException(status_code=400, detail="No MC number on file for this user")

    return lookup_mc(mc_number)


# ---------------------
# ADMIN: MANUAL APPROVAL (FOR TESTING WHEN FMCSA IS BLOCKED)
# ---------------------
def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return user


@app.get("/admin/approve-broker")
def admin_approve_broker(
    username: str,
    mc_number: str,
    role: str = "broker",
    admin=Depends(require_admin),
):
    if role not in ("broker", "broker_carrier"):
        raise HTTPException(status_code=400, detail="role must be broker or broker_carrier")

    set_broker_request(username, mc_number, "approved")
    set_user_role(username, role)

    return {
        "success": True,
        "approved_username": username,
        "mc_number": mc_number,
        "new_role": role,
        "broker_status": "approved",
    }


@app.get("/admin/reject-broker")
def admin_reject_broker(
    username: str,
    admin=Depends(require_admin),
):
    # Rejected blocks broker verification; keep role unchanged
    set_broker_request(username, "", "rejected")
    return {
        "success": True,
        "rejected_username": username,
        "broker_status": "rejected",
    }


@app.get("/admin/list-broker-requests")
def admin_list_broker_requests(admin=Depends(require_admin)):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT username, role, mc_number, broker_status FROM users WHERE broker_status != 'none'")
    rows = c.fetchall()
    conn.close()

    return [
        {"username": r[0], "role": r[1], "mc_number": r[2] or "", "broker_status": r[3] or "none"}
        for r in rows
    ]


# ---------------------
# PRICING / CALC
# ---------------------
@app.get("/calculate-rate")
def calculate_rate(
    miles: float,
    linehaul_rate: float,
    deadhead_miles: float = 0,
    deadhead_rate: float = 0,
    driver_percent: float = 0,
    driver_flat_rate: float = 0,
    broker_margin_percent: float = 0,
    broker_fee_flat: float = 0,

    # Standard 11 accessorials
    tonu: float = 0,
    layover: float = 0,
    detention: float = 0,
    tarp_fee: float = 0,
    lumper_fee: float = 0,
    extra_stop_fee: float = 0,
    after_hours_fee: float = 0,
    border_crossing_fee: float = 0,
    oversize_permit_fee: float = 0,
    hazmat_fee: float = 0,
    reefer_fuel_surcharge: float = 0,

    # Unlimited custom accessorials
    custom_names: list[str] = Query(default=[]),
    custom_amounts: list[float] = Query(default=[]),
):
    fs_data = get_fuel_surcharge()
    diesel_price = fs_data["diesel_price"]
    fs_per_mile = fs_data["fuel_surcharge_per_mile"]

    # BASE LINEHAUL
    base_cost = miles * linehaul_rate

    # DEADHEAD
    deadhead_cost = deadhead_miles * deadhead_rate

    # FUEL SURCHARGE (per mile)
    all_miles = miles + deadhead_miles
    fs_amount = all_miles * fs_per_mile

    # STANDARD ACCESSORIAL TOTAL
    standard_accessorials = {
        "tonu": tonu,
        "layover": layover,
        "detention": detention,
        "tarp_fee": tarp_fee,
        "lumper_fee": lumper_fee,
        "extra_stop_fee": extra_stop_fee,
        "after_hours_fee": after_hours_fee,
        "border_crossing_fee": border_crossing_fee,
        "oversize_permit_fee": oversize_permit_fee,
        "hazmat_fee": hazmat_fee,
        "reefer_fuel_surcharge": reefer_fuel_surcharge,
    }
    standard_total = sum(standard_accessorials.values())

    # CUSTOM ACCESSORIALS
    if len(custom_names) != len(custom_amounts):
        raise HTTPException(
            status_code=400,
            detail=f"custom_names count ({len(custom_names)}) must match custom_amounts count ({len(custom_amounts)})",
        )

    custom_items = [{"name": n, "amount": a} for n, a in zip(custom_names, custom_amounts)]
    custom_total = sum(custom_amounts)

    # TOTAL REVENUE BEFORE SPLITS
    total_revenue = base_cost + fs_amount + deadhead_cost + standard_total + custom_total

    # DRIVER PAY
    driver_pay = driver_flat_rate if driver_flat_rate > 0 else total_revenue * driver_percent

    # BROKER FEES
    broker_margin = total_revenue * broker_margin_percent
    broker_total_fees = broker_margin + broker_fee_flat

    # TRUCK/CARRIER PAY
    truck_pay = total_revenue - broker_total_fees

    # PROFIT
    profit_total = broker_total_fees
    profit_per_mile = profit_total / all_miles if all_miles > 0 else 0

    return {
        "miles": miles,
        "deadhead_miles": deadhead_miles,
        "linehaul_rate": linehaul_rate,

        "standard_accessorials": standard_accessorials,
        "standard_accessorial_total": round(standard_total, 2),

        "custom_items": custom_items,
        "custom_accessorial_total": round(custom_total, 2),

        "base_linehaul_amount": round(base_cost, 2),
        "fuel_surcharge_per_mile": fs_per_mile,
        "fuel_surcharge_amount": round(fs_amount, 2),
        "deadhead_cost": round(deadhead_cost, 2),

        "total_revenue": round(total_revenue, 2),

        "driver_pay": round(driver_pay, 2),
        "broker_revenue": round(broker_total_fees, 2),
        "truck_pay": round(truck_pay, 2),

        "profit_total": round(profit_total, 2),
        "profit_per_mile": round(profit_per_mile, 2),

        "diesel_price": diesel_price,
        "all_miles": all_miles,
    }