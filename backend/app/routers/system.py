import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, CurrentUser, Student, SuperAdmin
from ..models import Order, Payment, SystemSetting
from ..services.payments import payment_mode

router = APIRouter(tags=["system"])


def _demo(db) -> bool:
    row = db.get(SystemSetting, "demo_mode")
    return bool(row and row.value.get("on"))


@router.get("/config")
def public_config(db: DB):
    s = get_settings()
    return {"currency": "GHS", "payment_mode": payment_mode(), "maps_mode": "google" if s.google_maps_api_key else "openstreetmap",
            "demo": _demo(db), "tagline": "Your Campus. Your Essentials. Delivered."}


@router.get("/admin/integrations", dependencies=[SuperAdmin])
def integrations(db: DB):
    s = get_settings()
    mode = payment_mode()
    return {
        "payments": {"mode": mode, "provider": "paystack", "secret_key_set": bool(s.paystack_secret_key),
                     "webhook_url_path": "/payments/webhook/paystack",
                     "note": {"mock": "Simulated checkout. No real money moves.",
                              "test": "Paystack test mode. No real money moves.",
                              "live": "Paystack LIVE. Real money.",
                              "unconfigured": "Payments are off. Set PAYSTACK_SECRET_KEY."}[mode]},
        "maps": {"google_key_set": bool(s.google_maps_api_key),
                 "mode": "google" if s.google_maps_api_key else "straight_line_and_openstreetmap",
                 "note": "Without a Google key, delivery distance is straight-line (approximate) and maps use OpenStreetMap."},
        "email": {"backend": s.email_backend, "note": "Console only. Emails are written to the server log, not sent."},
        "push": {"configured": False},
        "demo_data": _demo(db),
        "env": s.env,
        "launch_checklist": [
            "Set ENV=production and a strong JWT_SECRET",
            "Set PAYSTACK_SECRET_KEY (test first, then live) and add the webhook URL in Paystack",
            "Set GOOGLE_MAPS_API_KEY and confirm hostel/shop locations in Admin > Delivery",
            "Set the price per km (or a flat fee) in Admin > Delivery",
            "Create real rider accounts in Admin > Riders",
            "Remove demo data (run python -m app.seed on a fresh database, not seed_demo)",
            "Configure email sending",
        ],
    }


class MockIn(BaseModel):
    outcome: str  # success | failed | abandoned


@router.post("/dev/mock-pay/{reference}", dependencies=[Student])
def mock_pay(reference: str, body: MockIn, user: CurrentUser, db: DB):
    """DEVELOPMENT ONLY: records the result of the simulated checkout."""
    if payment_mode() != "mock":
        raise HTTPException(404, "Not found.")
    if body.outcome not in ("success", "failed", "abandoned"):
        raise HTTPException(422, "Unknown outcome.")
    p = db.scalar(select(Payment).where(Payment.reference == reference))
    o = db.get(Order, p.order_id) if p else None
    if not p or o.user_id != user.id:
        raise HTTPException(404, "Payment not found.")
    p.provider_payload = {**(p.provider_payload or {}), "mock_outcome": body.outcome}
    db.commit()
    return {"ok": True}
