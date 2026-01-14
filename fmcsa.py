import os
import requests

FMCSA_KEY = os.getenv("FMCSA_KEY", "DEMO").strip()

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

        # Hard block / forbidden
        if status == 403:
            return {
                "valid": False,
                "mc_number": mc_number,
                "error": "FMCSA blocked request (HTTP 403)",
            }

        # Any other non-200
        if status != 200:
            return {
                "valid": False,
                "mc_number": mc_number,
                "error": f"FMCSA HTTP {status}",
                "raw": raw[:300],
            }

        # Must be JSON (FMCSA sometimes returns HTML/text)
        if not raw.startswith("{"):
            return {
                "valid": False,
                "mc_number": mc_number,
                "error": "FMCSA returned non-JSON response",
                "raw": raw[:300],
            }

        data = r.json()

        # Typical FMCSA structure
        carrier = (data.get("content") or {}).get("carrier") or {}

        if not carrier:
            return {
                "valid": False,
                "mc_number": mc_number,
                "error": "No carrier data returned",
            }

        entity_type = (carrier.get("entityType") or "").upper()

        # Role mapping (simple + predictable)
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
        return {
            "valid": False,
            "mc_number": mc_number,
            "error": f"FMCSA request failed: {str(e)}",
        }