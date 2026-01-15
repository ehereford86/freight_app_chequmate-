import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user, set_broker_request, set_user_role

router = APIRouter()

FMCSA_KEY = (os.getenv("FMCSA_KEY") or "DEMO").strip()

def lookup_mc(mc_number: str):
    mc_number = (mc_number or "").strip()
    if not mc_number:
        return {"valid": False, "mc_number": mc_number, "error": "MC number required"}

    url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/{mc_number}?webKey={FMCSA_KEY}"
    headers = {
        "User-Agent": "Mozilla/5.0 (ChequmateFreight/0.1)",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        status = r.status_code
        raw = (r.text or "").strip()

        if status == 403:
            return {"valid": False, "mc_number": mc_number, "error": "FMCSA blocked request (HTTP 403)"}

        if status != 200:
            return {"valid": False, "mc_number": mc_number, "error": f"FMCSA HTTP {status}", "raw": raw[:300]}

        if not raw.startswith("{"):
            return {"valid": False, "mc_number": mc_number, "error": "FMCSA returned non-JSON response", "raw": raw[:300]}

        data = r.json()
        carrier = (data.get("content") or {}).get("carrier") or {}
        if not carrier:
            return {"valid": False, "mc_number": mc_number, "error": "No carrier data returned"}

        entity_type = (carrier.get("entityType") or "").upper()

        if entity_type == "BROKER":
            role = "broker"
        elif entity_type in ("BROKER/CARRIER", "CARRIER/BROKER"):
            role = "broker_carrier"
        else:
            role = "carrier"

        return {
            "valid": True,
            "mc_number": mc_number,
            "legal_name": carrier.get("legalName"),
            "dot_number": carrier.get("dotNumber"),
            "entity_type": carrier.get("entityType"),
            "operating_status": carrier.get("operatingStatus"),
            "role": role,
            "is_broker": role in ("broker", "broker_carrier"),
        }

    except Exception as e:
        return {"valid": False, "mc_number": mc_number, "error": f"FMCSA request failed: {str(e)}"}

@router.get("/broker-onboard", description="If FMCSA works: set role based on entity type and mark approved.\nIf FMCSA blocked: mark pending (still stores MC).")
def broker_onboard(mc_number: str, user=Depends(get_current_user)):
    result = lookup_mc(mc_number)

    # Verified broker
    if result.get("valid") and result.get("role") in ("broker", "broker_carrier"):
        set_broker_request(user["username"], mc_number, "approved")
        set_user_role(user["username"], result["role"])
        return {"success": True, "broker_status": "approved", "mc_number": mc_number, "details": result}

    # Blocked
    err = (result.get("error") or "")
    if "403" in err:
        set_broker_request(user["username"], mc_number, "pending")
        return {"success": True, "broker_status": "pending", "mc_number": mc_number, "note": "FMCSA blocked; pending for admin review"}

    # Not broker
    set_broker_request(user["username"], mc_number, "rejected")
    return {"success": True, "broker_status": "rejected", "mc_number": mc_number, "details": result}

@router.get("/verify-broker")
def verify_broker(user=Depends(get_current_user)):
    # Must be broker role
    if user.get("role") not in ("broker", "broker_carrier"):
        raise HTTPException(status_code=403, detail="Broker access only")

    # Must be approved
    if (user.get("broker_status") or "none") != "approved":
        raise HTTPException(status_code=403, detail="Broker not approved")

    mc_number = (user.get("mc_number") or "").strip()
    if not mc_number:
        raise HTTPException(status_code=400, detail="No MC number on file")

    return lookup_mc(mc_number)