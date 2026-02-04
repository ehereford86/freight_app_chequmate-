from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

router = APIRouter()


class FairRatePolicy(BaseModel):
    """
    Pilot policy object used by negotiate.py.
    Keep it simple and stable: defaults + small helper dicts.
    """

    # Core defaults referenced by negotiate.py
    default_driver_loaded_mile_pay: float = Field(4.25, ge=0)
    default_detention_per_hour: float = Field(25.0, ge=0)
    default_carrier_cost_per_total_mile: float = Field(0.60, ge=0)

    default_carrier_margin_pct: float = Field(0.06, ge=0, le=1)
    default_broker_margin_pct: float = Field(0.10, ge=0, le=1)
    default_dispatch_pct: float = Field(0.08, ge=0, le=1)

    # Guardrail for requiring override_reason
    driver_reason_threshold: float = Field(5.00, ge=0)

    notes: list[str] = Field(
        default_factory=lambda: [
            "Pilot policy object used by negotiate.py.",
            "For production: store in DB and version it.",
        ]
    )

    def caps_dict(self) -> dict:
        # You can add real caps later. Keep empty for now so UI doesn't crash.
        return {}

    def defaults_dict(self) -> dict:
        # What the UI might want to show as defaults.
        return {
            "default_driver_loaded_mile_pay": self.default_driver_loaded_mile_pay,
            "default_detention_per_hour": self.default_detention_per_hour,
            "default_carrier_cost_per_total_mile": self.default_carrier_cost_per_total_mile,
            "default_carrier_margin_pct": self.default_carrier_margin_pct,
            "default_broker_margin_pct": self.default_broker_margin_pct,
            "default_dispatch_pct": self.default_dispatch_pct,
            "driver_reason_threshold": self.driver_reason_threshold,
        }

    def public_dict(self) -> dict:
        # Same as defaults_dict for now; keeps your existing endpoint stable.
        return self.defaults_dict()


def get_fair_rate_policy() -> FairRatePolicy:
    return FairRatePolicy()


def require_broker() -> bool:
    return True


@router.get("/broker/fair-rate-policy")
def broker_fair_rate_policy(_ok: bool = Depends(require_broker)):
    return {"ok": True, "policy": get_fair_rate_policy().model_dump()}
