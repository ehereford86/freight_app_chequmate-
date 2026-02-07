from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

import db
import fuel
from auth import require_broker_approved, read_json
from fair_rate_policy import FairRatePolicy

router = APIRouter()

# -----------------------------
# Helpers
# -----------------------------
def ok(payload: dict) -> dict:
    return {"ok": True, **payload}

def fail(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )

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
        raise fail("LOAD_NOT_FOUND", "Load not found", 404)
    return dict(row)

def _broker_can_access(load: dict, broker_user: dict) -> None:
    if (load.get("broker_mc") or "") != (broker_user.get("broker_mc") or ""):
        raise fail("FORBIDDEN", "Forbidden", 403)

def _update_load_fields(load_id: int, updated_by: str, fields: dict) -> None:
    fn = getattr(db, "update_load_fields", None)
    if not callable(fn):
        raise RuntimeError("db.update_load_fields is not available")
    fn(int(load_id), str(updated_by), fields)

def _r2(x: float) -> float:
    return float(round(float(x), 2))

# -----------------------------
# Fuel (MPG MODEL)
# -----------------------------
DEFAULT_MPG = float(os.environ.get("DEFAULT_MPG", "6.5"))

def _fuel_costs_loaded_miles(loaded_miles: float, origin_state: str | None, fuel_mode: str | None) -> tuple[float, float, dict]:
    diesel_price, meta = fuel.get_diesel_price(origin_state=origin_state, mode=fuel_mode)

    mpg = DEFAULT_MPG if DEFAULT_MPG > 0 else 6.5

    if diesel_price is None:
        fuel_per_mile = 0.0
        fuel_total = 0.0
        meta_out = {
            "ok": False,
            "source": (meta.get("source") if isinstance(meta, dict) else "UNAVAILABLE") or "UNAVAILABLE",
            "diesel_price": None,
            "period": (meta.get("period") if isinstance(meta, dict) else None),
            "series_id": (meta.get("series_id") if isinstance(meta, dict) else None),
            "mode": (meta.get("mode") if isinstance(meta, dict) else (fuel_mode or "national")),
            "origin_state": (meta.get("origin_state") if isinstance(meta, dict) else origin_state),
            "mpg": float(mpg),
            "fuel_surcharge_per_mile": fuel_per_mile,
            "fuel_per_mile": fuel_per_mile,
            "fuel_total": fuel_total,
            "meta": meta if isinstance(meta, dict) else {"ok": False, "error": "no meta"},
        }
        return fuel_per_mile, fuel_total, meta_out

    fuel_per_mile = float(diesel_price) / float(mpg)
    fuel_total = fuel_per_mile * float(loaded_miles)

    fuel_total = float(round(fuel_total, 2))
    fuel_per_mile = float(round(fuel_per_mile, 5))

    meta_out = {
        "ok": True,
        "source": "EIA",
        "diesel_price": float(diesel_price),
        "period": (meta.get("period") if isinstance(meta, dict) else None),
        "series_id": (meta.get("series_id") if isinstance(meta, dict) else None),
        "mode": (meta.get("mode") if isinstance(meta, dict) else (fuel_mode or "national")),
        "origin_state": (meta.get("origin_state") if isinstance(meta, dict) else origin_state),
        "mpg": float(mpg),
        "fuel_surcharge_per_mile": fuel_per_mile,
        "fuel_per_mile": fuel_per_mile,
        "fuel_total": fuel_total,
        "meta": meta if isinstance(meta, dict) else {"ok": True, "source": "EIA"},
    }
    return fuel_per_mile, fuel_total, meta_out

# -----------------------------
# API
# -----------------------------
@router.post("/broker/loads/{load_id}/negotiate")
async def broker_negotiate(load_id: int, request: Request, u=Depends(require_broker_approved)):
    policy = FairRatePolicy()

    load = _require_load(load_id)
    _broker_can_access(load, u)

    body = await read_json(request)

    loaded_miles = _safe_float(body.get("loaded_miles"), 0.0)
    total_miles = _safe_float(body.get("total_miles"), 0.0)
    if loaded_miles <= 0 or total_miles <= 0:
        raise fail("BAD_INPUT", "loaded_miles and total_miles must be > 0", 400)
    if total_miles < loaded_miles:
        raise fail("BAD_INPUT", "total_miles cannot be < loaded_miles", 400)

    fuel_mode = (body.get("fuel_mode") or "national").strip().lower()
    origin_state = (body.get("origin_state") or "").strip().upper() or None

    lumper_fee = _safe_float(body.get("lumper_fee"), 0.0)
    detention_hours = _safe_float(body.get("detention_hours"), 0.0)
    breakdown_fee = _safe_float(body.get("breakdown_fee"), 0.0)
    layover_days = int(_safe_float(body.get("layover_days"), 0))
    layover_per_day = _safe_float(body.get("layover_per_day"), 0.0)

    driver_cpm = _safe_float(body.get("driver_loaded_mile_pay"), policy.default_driver_loaded_mile_pay)

    override_reason = body.get("override_reason")
    apply_to_load = bool(body.get("apply_to_load"))

    warnings: list[str] = []
    if driver_cpm > policy.driver_reason_threshold and not override_reason:
        warnings.append("Driver CPM exceeds threshold")

    driver_linehaul_pay = driver_cpm * loaded_miles
    driver_detention_pay = detention_hours * policy.default_detention_per_hour
    driver_layover_pay = layover_days * layover_per_day
    driver_breakdown_pay = breakdown_fee
    driver_total = driver_linehaul_pay + driver_detention_pay + driver_layover_pay + driver_breakdown_pay

    carrier_operating_cost = policy.default_carrier_cost_per_total_mile * total_miles
    carrier_accessorials = lumper_fee

    fuel_per_mile, fuel_total, fuel_obj = _fuel_costs_loaded_miles(
        loaded_miles, origin_state=origin_state, fuel_mode=fuel_mode
    )

    carrier_cost_subtotal = driver_total + carrier_operating_cost + carrier_accessorials + fuel_total
    carrier_revenue = carrier_cost_subtotal * (1.0 + policy.default_carrier_margin_pct)
    dispatch_fee = carrier_revenue * policy.default_dispatch_pct
    broker_cost = carrier_revenue + dispatch_fee
    customer_rate_total = broker_cost * (1.0 + policy.default_broker_margin_pct)

    broker_profit = customer_rate_total - broker_cost
    broker_margin_pct_real = (broker_profit / customer_rate_total) if customer_rate_total > 0 else 0.0
    linehaul = max(customer_rate_total - fuel_total, 0.0)

    breakdown = {
        "driver_linehaul_pay": _r2(driver_linehaul_pay),
        "driver_detention_pay": _r2(driver_detention_pay),
        "driver_breakdown_pay": _r2(driver_breakdown_pay),
        "driver_layover_pay": _r2(driver_layover_pay),
        "driver_total_pay": _r2(driver_total),
        "fuel_total": _r2(fuel_total),
        "carrier_operating_cost": _r2(carrier_operating_cost),
        "carrier_accessorials": _r2(carrier_accessorials),
        "carrier_cost_subtotal": _r2(carrier_cost_subtotal),
        "carrier_revenue": _r2(carrier_revenue),
        "dispatch_fee": _r2(dispatch_fee),
        "broker_cost": _r2(broker_cost),
        "customer_rate_total": _r2(customer_rate_total),
        "broker_profit": _r2(broker_profit),
        "broker_margin_pct_real": float(round(float(broker_margin_pct_real), 4)),
        "linehaul": _r2(linehaul),
    }

    selected = {
        "driver_loaded_mile_pay": float(driver_cpm),
        "override_reason": override_reason,
        "fuel_mode": fuel_mode,
        "origin_state": origin_state,
        "fuel_per_mile": float(fuel_per_mile),
        "broker_rate": breakdown["customer_rate_total"],
        "all_in": breakdown["customer_rate_total"],
        "linehaul": breakdown["linehaul"],
        "driver_pay": breakdown["driver_total_pay"],
        "fuel_surcharge": breakdown["fuel_total"],
        "fuel_total": breakdown["fuel_total"],
        "carrier_total": breakdown["carrier_revenue"],
        "carrier_cost_est": breakdown["carrier_cost_subtotal"],
        "dispatcher_cut": breakdown["dispatch_fee"],
        "broker_profit": breakdown["broker_profit"],
        "broker_margin": breakdown["broker_margin_pct_real"],
    }

    market_assumptions = {
        "carrier_cost_per_total_mile": float(policy.default_carrier_cost_per_total_mile),
        "carrier_margin_pct": float(policy.default_carrier_margin_pct),
        "broker_margin_pct": float(policy.default_broker_margin_pct),
        "dispatch_pct": float(policy.default_dispatch_pct),
        "detention_per_hour": float(policy.default_detention_per_hour),
        "driver_reason_threshold": float(policy.driver_reason_threshold),
        "fuel_source": fuel_obj.get("source"),
        "diesel_price": fuel_obj.get("diesel_price"),
        "fuel_period": fuel_obj.get("period"),
        "fuel_series_id": fuel_obj.get("series_id"),
        "mpg": fuel_obj.get("mpg"),
    }

    audit_meta = {
        "inputs": {
            "loaded_miles": loaded_miles,
            "total_miles": total_miles,
            "lumper_fee": lumper_fee,
            "detention_hours": detention_hours,
            "breakdown_fee": breakdown_fee,
            "layover_days": layover_days,
            "layover_per_day": layover_per_day,
            "fuel_mode": fuel_mode,
            "origin_state": origin_state,
        },
        "selected": {
            "driver_loaded_mile_pay": driver_cpm,
            "override_reason": override_reason,
            "fuel_per_mile": fuel_per_mile,
        },
        "market_assumptions": market_assumptions,
    }

    try:
        db.create_load_negotiation(
            load_id=int(load_id),
            broker_username=u.get("username"),
            applied=apply_to_load,
            override_reason=override_reason if override_reason else None,
            inputs=audit_meta["inputs"],
            selected=selected,
            fuel=fuel_obj,
            breakdown=breakdown,
            warnings=warnings,
        )
    except Exception:
        pass

    try:
        db.audit(u["username"], "negotiate_rate", f"load:{int(load_id)}", json.dumps(audit_meta))
    except Exception:
        pass

    if apply_to_load:
        updated_by = u.get("username") or "system"
        _update_load_fields(
            int(load_id),
            updated_by,
            {
                "driver_pay": float(breakdown.get("driver_total_pay", 0.0)),
                "fuel_surcharge": float(breakdown.get("fuel_total", 0.0)),
            },
        )
        try:
            db.audit(updated_by, "apply_negotiated_rate", f"load:{int(load_id)}", None)
        except Exception:
            pass

    return {
        "ok": True,
        "load_id": int(load_id),
        "broker_mc": u.get("broker_mc"),
        "warnings": warnings,
        "policy_caps": policy.caps_dict(),
        "policy_defaults": policy.defaults_dict(),
        "market_assumptions": market_assumptions,
        "inputs": audit_meta["inputs"],
        "selected": selected,
        "fuel": fuel_obj,
        "breakdown": breakdown,
        "apply_to_load": apply_to_load,
    }
