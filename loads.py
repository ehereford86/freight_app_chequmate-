from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any
import uuid
import os
import re

import db
import routing_ors
from auth import (
    require_driver,
    require_dispatcher_linked,
    require_broker_approved,
    read_json,
)

router = APIRouter()

# -----------------------------
# Helpers
# -----------------------------
def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)

def _require_load(load_id: int) -> dict:
    row = db.get_load(int(load_id))
    if not row:
        raise HTTPException(status_code=404, detail="Load not found")
    return dict(row)

def _driver_can_access(load: dict, username: str) -> None:
    if (load.get("driver_username") or "") != username:
        raise HTTPException(status_code=403, detail="Forbidden")

def _dispatcher_can_access(load: dict, dispatcher_user: dict) -> None:
    if (load.get("broker_mc") or "") != (dispatcher_user.get("broker_mc") or ""):
        raise HTTPException(status_code=403, detail="Forbidden")

def _broker_can_access(load: dict, broker_user: dict) -> None:
    if (load.get("broker_mc") or "") != (broker_user.get("broker_mc") or ""):
        raise HTTPException(status_code=403, detail="Forbidden")

def _require_pending(load: dict) -> None:
    if (load.get("visibility") or "") != "pending":
        raise HTTPException(status_code=400, detail="Only pending loads can be modified by broker")

def _require_published(load: dict) -> None:
    if (load.get("visibility") or "") != "published":
        raise HTTPException(status_code=400, detail="Only published loads allowed")

def _require_not_paid(load: dict) -> None:
    if load.get("paid_at"):
        raise HTTPException(status_code=400, detail="Load is paid and locked")

def _require_not_invoiced(load: dict) -> None:
    if load.get("invoiced_at"):
        raise HTTPException(status_code=400, detail="Load is invoiced and locked")

def _limited_ratecon_view(load: dict) -> dict:
    return {
        "driver_pay": float(load.get("driver_pay") or 0.0),
        "fuel_surcharge": float(load.get("fuel_surcharge") or 0.0),
        "ratecon_terms": load.get("ratecon_terms"),
    }

def _fuel_breakdown_readonly(load: dict) -> dict:
    return {
        "fuel_surcharge": float(load.get("fuel_surcharge") or 0.0),
        "note": "Read-only fuel surcharge stored on this load.",
    }

def _deadhead_buffer_pct() -> float:
    """
    Configurable deadhead buffer percentage.
    Env: DEADHEAD_BUFFER_PCT
      - Accepts "0.07" or "7" (treated as 7% if > 1)
    Default: 0.07 (7%)
    Clamped: 0.00 .. 0.30
    """
    raw = (os.environ.get("DEADHEAD_BUFFER_PCT") or "").strip()
    if not raw:
        return 0.07
    try:
        v = float(raw)
    except Exception:
        return 0.07
    if v > 1.0:
        v = v / 100.0
    if v < 0.0:
        v = 0.0
    if v > 0.30:
        v = 0.30
    return v

_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

def _extract_us_zip(addr: str) -> str | None:
    if not addr:
        return None
    m = _ZIP_RE.search(addr)
    if not m:
        return None
    return m.group(1)

# -----------------------------
# DRIVER (Assigned loads + calculator + status)
# -----------------------------
@router.get("/driver/loads")
def driver_list_loads(u=Depends(require_driver)):
    rows = db.list_loads_by_driver(u["username"])
    loads = [dict(r) for r in rows]
    for l in loads:
        l["ratecon_limited"] = _limited_ratecon_view(l)
        l["fuel_breakdown"] = _fuel_breakdown_readonly(l)
    return {"ok": True, "loads": loads}

@router.get("/driver/loads/{load_id}")
def driver_get_load(load_id: int, u=Depends(require_driver)):
    load = _require_load(load_id)
    _driver_can_access(load, u["username"])
    view = {
        "id": load["id"],
        "status": load.get("status"),
        "visibility": load.get("visibility"),
        "pickup_address": load.get("pickup_address"),
        "pickup_appt": load.get("pickup_appt"),
        "delivery_address": load.get("delivery_address"),
        "delivery_appt": load.get("delivery_appt"),
        "customer_ref": load.get("customer_ref"),
        "shipper_name": load.get("shipper_name"),
        "driver_username": load.get("driver_username"),
        "dispatcher_username": load.get("dispatcher_username"),
        "ratecon_limited": _limited_ratecon_view(load),
        "fuel_breakdown": _fuel_breakdown_readonly(load),
        "delivered_at": load.get("delivered_at"),
        "invoiced_at": load.get("invoiced_at"),
        "paid_at": load.get("paid_at"),
        "invoice_number": load.get("invoice_number"),
        "updated_at": load.get("updated_at"),
        "created_at": load.get("created_at"),
    }
    return {"ok": True, "load": view}

@router.post("/driver/miles")
async def driver_zip_miles(request: Request, u=Depends(require_driver)):
    body = await read_json(request)
    origin_zip = (body.get("origin_zip") or "").strip()
    dest_zip = (body.get("dest_zip") or "").strip()
    country = (body.get("country") or "US").strip().upper()

    if not origin_zip or not dest_zip:
        raise HTTPException(status_code=400, detail="origin_zip and dest_zip required")

    miles, seconds, meta = routing_ors.route_miles_zip_to_zip(origin_zip, dest_zip, country=country)
    return {"ok": True, "origin_zip": origin_zip, "dest_zip": dest_zip, "country": country, "miles": miles, "seconds": seconds, "meta": meta}

@router.post("/driver/pay-calc")
async def driver_pay_calc(request: Request, u=Depends(require_driver)):
    body = await read_json(request)

    origin_zip = (body.get("origin_zip") or "").strip()
    dest_zip = (body.get("dest_zip") or "").strip()
    country = (body.get("country") or "US").strip().upper()

    actual_miles = _safe_float(body.get("actual_miles"), 0.0)
    use_actual = bool(body.get("use_actual_miles")) or (actual_miles > 0)

    routed_miles = None
    routed_seconds = None
    miles_meta: dict[str, Any] = {"ok": False, "source": "none"}

    if use_actual:
        miles = actual_miles
        miles_source = "actual"
    else:
        if not origin_zip or not dest_zip:
            raise HTTPException(status_code=400, detail="Provide origin_zip + dest_zip, or provide actual_miles")
        routed_miles, routed_seconds, miles_meta = routing_ors.route_miles_zip_to_zip(origin_zip, dest_zip, country=country)
        if routed_miles is None:
            raise HTTPException(status_code=400, detail=f"Routing failed: {miles_meta}")
        miles = float(routed_miles)
        miles_source = "zip_to_zip"

    cpm = _safe_float(body.get("cents_per_mile") or body.get("cpm"), 0.0)
    if cpm <= 0:
        raise HTTPException(status_code=400, detail="cpm (cents_per_mile) must be > 0")

    lumper = _safe_float(body.get("lumper"), 0.0)
    breakdown_fee = _safe_float(body.get("breakdown_fee"), 0.0)
    detention_hours = _safe_float(body.get("detention_hours"), 0.0)
    detention_rate = _safe_float(body.get("detention_rate_per_hour"), 0.0)
    layover_days = int(_safe_float(body.get("layover_days"), 0))
    layover_per_day = _safe_float(body.get("layover_per_day"), 0.0)

    linehaul = float(round(miles * cpm, 2))
    detention_pay = float(round(detention_hours * detention_rate, 2))
    layover_pay = float(round(layover_days * layover_per_day, 2))
    total = float(round(linehaul + lumper + breakdown_fee + detention_pay + layover_pay, 2))

    return {
        "ok": True,
        "driver": u.get("username"),
        "miles": {
            "source": miles_source,
            "miles_used": float(round(miles, 2)),
            "actual_miles": float(round(actual_miles, 2)) if actual_miles else 0.0,
            "origin_zip": origin_zip or None,
            "dest_zip": dest_zip or None,
            "country": country,
            "routed_miles": float(round(routed_miles, 2)) if routed_miles else None,
            "routed_seconds": float(routed_seconds) if routed_seconds else None,
            "meta": miles_meta,
        },
        "inputs": {
            "cpm": float(cpm),
            "lumper": float(lumper),
            "breakdown_fee": float(breakdown_fee),
            "detention_hours": float(detention_hours),
            "detention_rate_per_hour": float(detention_rate),
            "layover_days": int(layover_days),
            "layover_per_day": float(layover_per_day),
        },
        "breakdown": {
            "linehaul": linehaul,
            "detention": detention_pay,
            "layover": layover_pay,
            "lumper": float(round(lumper, 2)),
            "breakdown_fee": float(round(breakdown_fee, 2)),
            "total_pay": total,
        },
    }

@router.post("/driver/loads/{load_id}/accept")
async def driver_accept(load_id: int, u=Depends(require_driver)):
    load = _require_load(load_id)
    _driver_can_access(load, u["username"])
    _require_not_paid(load)

    db.update_load_fields(int(load_id), u["username"], {"status": "accepted"})
    try:
        db.audit(u["username"], "driver_accept", f"load:{int(load_id)}", None)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "status": "accepted"}

@router.post("/driver/loads/{load_id}/status")
async def driver_set_status(load_id: int, request: Request, u=Depends(require_driver)):
    load = _require_load(load_id)
    _driver_can_access(load, u["username"])
    _require_not_paid(load)

    body = await read_json(request)
    status = (body.get("status") or "").strip().lower()

    allowed = {
        "accepted",
        "enroute_pickup",
        "at_pickup",
        "loaded",
        "enroute_delivery",
        "at_delivery",
        "delivered",
    }
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Bad status. Allowed: {sorted(list(allowed))}")

    fields: dict[str, Any] = {"status": status}
    if status == "delivered" and not load.get("delivered_at"):
        fields["delivered_at"] = db.now_iso()

    db.update_load_fields(int(load_id), u["username"], fields)
    try:
        db.audit(u["username"], "driver_status", f"load:{int(load_id)}", status)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "status": status}

# -----------------------------
# DISPATCHER (Published board + assign/unassign/release + driver roster)
# -----------------------------
@router.get("/dispatcher/loads")
def dispatcher_list_loads(u=Depends(require_dispatcher_linked)):
    rows = db.list_loads_published_by_dispatcher(u["username"], u["broker_mc"])
    return {"ok": True, "loads": [dict(r) for r in rows]}

@router.get("/dispatcher/loads/{load_id}")
def dispatcher_get_load(load_id: int, u=Depends(require_dispatcher_linked)):
    load = _require_load(load_id)
    _dispatcher_can_access(load, u)
    return {"ok": True, "load": load}


@router.get("/dispatcher/drivers")
def dispatcher_list_drivers(u=Depends(require_dispatcher_linked)):
    rows = db.list_users_by_role_and_broker_mc("driver", u["broker_mc"], limit=500)
    drivers = [dict(r).get("username") for r in rows]
    drivers = [d for d in drivers if d]
    drivers.sort()
    return {"ok": True, "drivers": drivers}

@router.post("/dispatcher/loads/{load_id}/assign-driver")
async def dispatcher_assign_driver(load_id: int, request: Request, u=Depends(require_dispatcher_linked)):
    load = _require_load(load_id)
    _dispatcher_can_access(load, u)
    _require_published(load)
    _require_not_paid(load)
    _require_not_invoiced(load)

    body = await read_json(request)
    driver_username = (body.get("driver_username") or "").strip()
    if not driver_username:
        raise HTTPException(status_code=400, detail="Missing driver_username")

    target = db.get_user(driver_username)
    target = dict(target) if target else None
    if not target or (target.get("role") != "driver"):
        raise HTTPException(status_code=400, detail="Target user must be a driver")
    if (target.get("broker_mc") or "") != (u.get("broker_mc") or ""):
        raise HTTPException(status_code=403, detail="Driver not linked to your broker_mc")

    db.assign_driver(int(load_id), driver_username, u["username"])

    try:
        db.audit(u["username"], "dispatcher_assign_driver", f"load:{int(load_id)}", f"driver:{driver_username}")
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "driver_username": driver_username}

@router.post("/dispatcher/loads/{load_id}/unassign-driver")
async def dispatcher_unassign_driver(load_id: int, u=Depends(require_dispatcher_linked)):
    load = _require_load(load_id)
    _dispatcher_can_access(load, u)
    _require_published(load)
    _require_not_paid(load)
    _require_not_invoiced(load)

    db.unassign_driver(int(load_id))

    try:
        db.audit(u["username"], "dispatcher_unassign_driver", f"load:{int(load_id)}", None)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "unassigned": True}

@router.post("/dispatcher/loads/{load_id}/release")
async def dispatcher_release(load_id: int, u=Depends(require_dispatcher_linked)):
    load = _require_load(load_id)
    _dispatcher_can_access(load, u)
    _require_published(load)
    _require_not_paid(load)
    _require_not_invoiced(load)

    if hasattr(db, "release_load"):
        db.release_load(int(load_id))
    else:
        db.update_load_fields(int(load_id), u["username"], {"dispatcher_username": None, "driver_username": None})

    try:
        db.audit(u["username"], "dispatcher_release", f"load:{int(load_id)}", None)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "released": True}

# -----------------------------
# BROKER (approved)
# -----------------------------
@router.get("/broker/loads")
def broker_list_loads(u=Depends(require_broker_approved)):
    rows = db.list_loads_by_broker(u["broker_mc"])
    return {"ok": True, "loads": [dict(r) for r in rows]}

@router.get("/broker/loads/{load_id}")
def broker_get_load(load_id: int, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)
    return {"ok": True, "load": load}

@router.post("/broker/loads/{load_id}/route-miles")
async def broker_route_miles(load_id: int, request: Request, u=Depends(require_broker_approved)):
    """
    Auto-calc miles for Negotiation Calculator:
      loaded_miles = routed miles (zip->zip)
      total_miles  = routed miles * (1 + deadhead buffer)
    Deadhead buffer is env-configurable: DEADHEAD_BUFFER_PCT (default 0.07).
    """
    load = _require_load(load_id)
    _broker_can_access(load, u)

    body = await read_json(request)
    country = (body.get("country") or "US").strip().upper()

    pickup_address = (load.get("pickup_address") or "").strip()
    delivery_address = (load.get("delivery_address") or "").strip()

    if country != "US":
        raise HTTPException(status_code=400, detail="route-miles currently supports US only")

    oz = _extract_us_zip(pickup_address)
    dz = _extract_us_zip(delivery_address)
    if not oz or not dz:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing ZIP(s) in load addresses",
                "pickup_address": pickup_address,
                "delivery_address": delivery_address,
                "hint": "Include 5-digit ZIP in pickup_address and delivery_address for auto-routing.",
            },
        )

    miles, seconds, meta = routing_ors.route_miles_zip_to_zip(oz, dz, country=country)
    if miles is None:
        raise HTTPException(status_code=400, detail={"error": "Routing failed", "meta": meta})

    buffer_pct = _deadhead_buffer_pct()
    loaded_miles = float(round(float(miles), 2))
    total_miles = float(round(loaded_miles * (1.0 + buffer_pct), 2))

    return {
        "ok": True,
        "load_id": int(load_id),
        "country": country,
        "origin_zip": oz,
        "dest_zip": dz,
        "loaded_miles": loaded_miles,
        "total_miles": total_miles,
        "deadhead_buffer_pct": float(round(buffer_pct, 4)),
        "routed_seconds": float(seconds) if seconds is not None else None,
        "meta": meta,
    }

@router.get("/broker/loads/{load_id}/negotiations")
def broker_list_negotiations(load_id: int, limit: int = 20, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    rows = db.list_load_negotiations(int(load_id), int(limit))
    out = []
    for r in rows:
        d = dict(r)
        out.append({
            "id": d.get("id"),
            "load_id": d.get("load_id"),
            "broker_username": d.get("broker_username"),
            "applied": bool(d.get("applied")),
            "override_reason": d.get("override_reason"),
            "inputs": db.json_loads_safe(d.get("inputs_json")) or {},
            "selected": db.json_loads_safe(d.get("selected_json")) or {},
            "fuel": db.json_loads_safe(d.get("fuel_json")) or {},
            "breakdown": db.json_loads_safe(d.get("breakdown_json")) or {},
            "warnings": db.json_loads_safe(d.get("warnings_json")) or [],
            "created_at": d.get("created_at"),
        })
    return {"ok": True, "load_id": int(load_id), "negotiations": out}

@router.post("/broker/loads/create")
async def broker_create_load(request: Request, u=Depends(require_broker_approved)):
    body = await read_json(request)

    pickup_address = (body.get("pickup_address") or "").strip()
    delivery_address = (body.get("delivery_address") or "").strip()
    if not pickup_address or not delivery_address:
        raise HTTPException(status_code=400, detail="pickup_address and delivery_address required")

    shipper_name = (body.get("shipper_name") or "").strip() or None
    customer_ref = (body.get("customer_ref") or "").strip() or None
    pickup_appt = (body.get("pickup_appt") or "").strip() or None
    delivery_appt = (body.get("delivery_appt") or "").strip() or None
    dispatcher_username = (body.get("dispatcher_username") or "").strip() or None

    ratecon_terms = (body.get("ratecon_terms") or "").strip() or None
    driver_pay = _safe_float(body.get("driver_pay"), 0.0)
    fuel_surcharge_amt = _safe_float(body.get("fuel_surcharge"), 0.0)

    if dispatcher_username:
        du = db.get_user(dispatcher_username)
        du = dict(du) if du else None
        if not du or du.get("role") != "dispatcher":
            raise HTTPException(status_code=400, detail="dispatcher_username must be a dispatcher")
        if (du.get("broker_mc") or "") != u["broker_mc"]:
            raise HTTPException(status_code=403, detail="Dispatcher not linked to your broker_mc")

    load_id = db.create_load(
        broker_mc=u["broker_mc"],
        pickup_address=pickup_address,
        delivery_address=delivery_address,
        shipper_name=shipper_name,
        customer_ref=customer_ref,
        pickup_appt=pickup_appt,
        delivery_appt=delivery_appt,
        dispatcher_username=dispatcher_username,
        ratecon_terms=ratecon_terms,
        driver_pay=driver_pay,
        fuel_surcharge=fuel_surcharge_amt,
        visibility="pending",
        created_by=u["username"],
    )
    try:
        db.audit(u["username"], "create_load", f"load:{int(load_id)}", None)
    except Exception:
        pass
    return {"ok": True, "load_id": load_id}

# -----------------------------
# BROKER actions (pending moderation)
# Needed by /broker-ui buttons: Publish / Edit / Cancel / Delete
# -----------------------------

@router.post("/broker/loads/{load_id}/publish")
async def broker_publish_load(load_id: int, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    if (load.get("visibility") or "").lower() != "pending":
        raise HTTPException(status_code=400, detail="Only pending loads can be published")

    _require_not_paid(load)
    _require_not_invoiced(load)

    db.set_load_visibility(int(load_id), "published", reviewed_by=u["username"], pulled_reason=None)
    try:
        db.audit(u["username"], "broker_publish", f"load:{int(load_id)}", None)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "visibility": "published"}

@router.post("/broker/loads/{load_id}/cancel")
async def broker_cancel_load(load_id: int, request: Request, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    if (load.get("visibility") or "").lower() != "pending":
        raise HTTPException(status_code=400, detail="Only pending loads can be canceled")

    _require_not_paid(load)
    _require_not_invoiced(load)

    body = await read_json(request)
    reason = (body.get("reason") or "").strip() or "Canceled by broker"

    db.set_load_visibility(int(load_id), "pulled", reviewed_by=u["username"], pulled_reason=reason)
    try:
        db.audit(u["username"], "broker_cancel", f"load:{int(load_id)}", reason)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "visibility": "pulled", "pulled_reason": reason}

@router.post("/broker/loads/{load_id}/delete")
async def broker_delete_load(load_id: int, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    if (load.get("visibility") or "").lower() != "pending":
        raise HTTPException(status_code=400, detail="Only pending loads can be deleted")

    _require_not_paid(load)
    _require_not_invoiced(load)

    db.hard_delete_load(int(load_id))
    try:
        db.audit(u["username"], "broker_delete", f"load:{int(load_id)}", None)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "deleted": True}

@router.post("/broker/loads/{load_id}/update")
async def broker_update_load(load_id: int, request: Request, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    if (load.get("visibility") or "").lower() != "pending":
        raise HTTPException(status_code=400, detail="Only pending loads can be edited")

    _require_not_paid(load)
    _require_not_invoiced(load)

    body = await read_json(request)

    allowed = {
        "shipper_name",
        "customer_ref",
        "pickup_address",
        "pickup_appt",
        "delivery_address",
        "delivery_appt",
        "dispatcher_username",
        "status",
        "ratecon_terms",
    }

    fields = {}
    for k in allowed:
        if k in body:
            fields[k] = body.get(k)

    for k in list(fields.keys()):
        v = fields[k]
        if isinstance(v, str):
            v = v.strip()
            fields[k] = (v if v != "" else None)

    if "dispatcher_username" in fields and fields["dispatcher_username"]:
        du = db.get_user(fields["dispatcher_username"])
        du = dict(du) if du else None
        if not du or du.get("role") != "dispatcher":
            raise HTTPException(status_code=400, detail="dispatcher_username must be a dispatcher")
        if (du.get("broker_mc") or "") != (u.get("broker_mc") or ""):
            raise HTTPException(status_code=403, detail="Dispatcher not linked to your broker_mc")

    if "pickup_address" in fields:
        if not (fields["pickup_address"] or "").strip():
            raise HTTPException(status_code=400, detail="pickup_address required")
    if "delivery_address" in fields:
        if not (fields["delivery_address"] or "").strip():
            raise HTTPException(status_code=400, detail="delivery_address required")

    db.update_load_fields(int(load_id), u["username"], fields)

    try:
        db.audit(u["username"], "broker_update", f"load:{int(load_id)}", db.json_dumps_safe(fields))
    except Exception:
        pass

    return {"ok": True, "load_id": int(load_id), "updated": True}

# -----------------------------
# ✅ NEW: BROKER INVOICE (NO DELIVERED REQUIRED)
# -----------------------------
@router.post("/broker/loads/{load_id}/invoice")
async def broker_invoice_load(load_id: int, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    if (load.get("visibility") or "").lower() != "published":
        raise HTTPException(status_code=400, detail="Only published loads can be invoiced")

    _require_not_paid(load)
    _require_not_invoiced(load)

    invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
    fields = {
        "invoiced_at": db.now_iso(),
        "invoice_number": invoice_number,
    }

    db.update_load_fields(int(load_id), u["username"], fields)
    try:
        db.audit(u["username"], "broker_invoice", f"load:{int(load_id)}", invoice_number)
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "invoice_number": invoice_number, "invoiced_at": fields["invoiced_at"]}

# -----------------------------
# ✅ NEW: BROKER MARK PAID (FINAL LOCK)
# -----------------------------
@router.post("/broker/loads/{load_id}/paid")
async def broker_mark_paid(load_id: int, u=Depends(require_broker_approved)):
    load = _require_load(load_id)
    _broker_can_access(load, u)

    if not load.get("invoiced_at"):
        raise HTTPException(status_code=400, detail="Load must be invoiced first")

    if load.get("paid_at"):
        return {"ok": True, "load_id": int(load_id), "paid_at": load.get("paid_at")}

    fields = {"paid_at": db.now_iso()}
    db.update_load_fields(int(load_id), u["username"], fields)
    try:
        db.audit(u["username"], "broker_paid", f"load:{int(load_id)}", fields["paid_at"])
    except Exception:
        pass
    return {"ok": True, "load_id": int(load_id), "paid_at": fields["paid_at"]}
