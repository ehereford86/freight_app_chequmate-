from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any

from auth import require_broker_approved, require_role, read_json

router = APIRouter()

def _safe_str(v: Any) -> str:
    return (v or "").strip()

@router.get("/fmcsa/search")
def fmcsa_search(
    q: str = "",
    u=Depends(require_role("admin", "broker")),
):
    """
    Broker/Admin only.
    Placeholder until you wire your real FMCSA verification approach.

    Why this exists now:
      - so /fmcsa endpoints show up in OpenAPI
      - so the frontend can integrate today
      - so role lockdown is enforced now
    """
    # If broker, must be approved
    if u["role"] == "broker" and (u.get("broker_status") or "") != "approved":
        raise HTTPException(status_code=403, detail="Broker not approved")

    q = _safe_str(q)
    if not q:
        raise HTTPException(status_code=400, detail="Missing q")

    # FMCSA blocked/not configured: return a stable 503 contract
    return {
        "ok": False,
        "error": "FMCSA integration not configured/blocked. Endpoints are live; wire provider or dataset next.",
        "query": q,
        "results": [],
    }

@router.post("/fmcsa/verify")
async def fmcsa_verify(
    request: Request,
    u=Depends(require_role("admin", "broker")),
):
    """
    Broker/Admin only.
    Accepts JSON: { "mc_number": "123456" } OR { "dot_number": "123456" }
    Returns stable contract for frontend wiring.
    """
    if u["role"] == "broker" and (u.get("broker_status") or "") != "approved":
        raise HTTPException(status_code=403, detail="Broker not approved")

    body = await read_json(request)
    mc = _safe_str(body.get("mc_number") or body.get("mc") or "")
    dot = _safe_str(body.get("dot_number") or body.get("dot") or "")

    if not mc and not dot:
        raise HTTPException(status_code=400, detail="Provide mc_number or dot_number")

    return {
        "ok": False,
        "verified": False,
        "status": "unverified",
        "mc_number": mc or None,
        "dot_number": dot or None,
        "error": "FMCSA integration not configured/blocked. Endpoints are live; wire provider or dataset next.",
    }
