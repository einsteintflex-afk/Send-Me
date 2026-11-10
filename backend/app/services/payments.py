import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (Order, OrderStatus, OrderStatusHistory, Payment, PaymentStatus, Product, ProductRequest,
                      ProductVariant, RequestStatus, Shop, User, WebhookEvent)
from .notify import notify, notify_shop
from .orders import next_order_number, utcnow
from .util import money


class PaymentProvider(Protocol):
    def initialize(self, *, email: str, amount_pesewas: int, reference: str, callback_url: str,
                   metadata: dict) -> dict: ...
    def verify(self, reference: str) -> dict: ...


class PaystackProvider:
    """Thin Paystack client. Secret key comes only from the environment."""

    def __init__(self):
        s = get_settings()
        if not s.paystack_secret_key:
            raise HTTPException(503, "Online payment is not set up yet. Please try again later.")
        self.base = s.paystack_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {s.paystack_secret_key}"}

    def _call(self, method: str, path: str, **kw) -> dict:
        try:
            r = httpx.request(method, self.base + path, headers=self.headers, timeout=20, **kw)
            data = r.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "We could not reach the payment provider. Please try again.")
        if r.status_code >= 400 or not data.get("status"):
            raise HTTPException(502, "The payment provider rejected the request.")
        return data["data"]

    def initialize(self, *, email, amount_pesewas, reference, callback_url, metadata):
        return self._call("POST", "/transaction/initialize", json={
            "email": email, "amount": amount_pesewas, "currency": get_settings().currency,
            "reference": reference, "callback_url": callback_url, "metadata": metadata,
            "channels": ["mobile_money", "card"]})

    def verify(self, reference):
        return self._call("GET", f"/transaction/verify/{reference}")


_provider_factory = PaystackProvider


def get_provider() -> PaymentProvider:
    return _provider_factory()


def set_provider_factory(f):  # used by tests
    global _provider_factory
    _provider_factory = f


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    key = get_settings().paystack_secret_key
    if not key or not signature:
        return False
    digest = hmac.new(key.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)


def new_reference() -> str:
    return "SMP-" + secrets.token_hex(10)


def init_payment(db: Session, order: Order, user: User, kind="order", request: ProductRequest | None = None,
                 amount: Decimal | None = None) -> Payment:
    if order.user_id != user.id:
        raise HTTPException(404, "Order not found.")
    if kind == "order":
        if order.payment_status == PaymentStatus.paid:
            raise HTTPException(409, "This order is already paid.")
        if order.status == OrderStatus.cancelled:
            raise HTTPException(409, "This order was cancelled.")
        amount = order.total
        # Reuse an open payment so a double tap cannot create two charges.
        open_p = db.scalar(select(Payment).where(Payment.order_id == order.id, Payment.kind == "order",
                                                 Payment.status == "initialized"))
        if open_p and open_p.provider_payload and open_p.provider_payload.get("authorization_url"):
            return open_p
    provider = get_provider()
    ref = new_reference()
    data = provider.initialize(email=user.email, amount_pesewas=int(money(amount) * 100), reference=ref,
                               callback_url=f"{get_settings().frontend_url}/orders/{order.id}",
                               metadata={"order_id": order.id, "kind": kind})
    p = Payment(order_id=order.id, kind=kind, request_id=request.id if request else None, reference=ref,
                amount=money(amount), currency=get_settings().currency, status="initialized",
                provider_payload={"authorization_url": data.get("authorization_url"),
                                  "access_code": data.get("access_code")})
    db.add(p)
    db.flush()
    return p


def apply_provider_result(db: Session, reference: str, data: dict) -> Payment:
    """Idempotently apply a verified provider transaction. Safe to call from webhook and verify endpoint."""
    p = db.scalar(select(Payment).where(Payment.reference == reference).with_for_update())
    if not p:
        raise HTTPException(404, "Unknown payment.")
    if p.status == "success":
        return p
    status = data.get("status")
    order = db.get(Order, p.order_id)
    if status == "success":
        expected = int(money(p.amount) * 100)
        if data.get("amount") != expected or (data.get("currency") or p.currency) != p.currency:
            p.status = "failed"
            p.provider_payload = {**(p.provider_payload or {}), "error": "amount_or_currency_mismatch"}
            notify(db, order.user_id, "payment_issue", "Payment problem",
                   "Your payment did not match the order amount. Contact support.", order.id)
            return p
        p.status = "success"
        p.channel = data.get("channel")
        p.verified_at = utcnow()
        if p.kind == "order":
            _order_paid(db, order)
        else:
            _topup_paid(db, order, p)
    elif status in ("failed", "reversed"):
        p.status = "failed"
        if p.kind == "order" and order.payment_status != PaymentStatus.paid:
            order.payment_status = PaymentStatus.failed
        notify(db, order.user_id, "payment_issue", "Payment failed", "Your payment did not go through. You can try again.", order.id)
    elif status == "abandoned":
        p.status = "abandoned"
        if p.kind == "order" and order.payment_status != PaymentStatus.paid:
            order.payment_status = PaymentStatus.abandoned
    # other statuses (ongoing, pending): leave initialized
    return p


def _order_paid(db: Session, order: Order) -> None:
    order.payment_status = PaymentStatus.paid
    if not order.number:
        order.number = next_order_number(db)
    shop = db.get(Shop, order.shop_id)
    if shop.delivery_estimate_minutes:
        order.estimated_arrival = utcnow() + timedelta(minutes=shop.delivery_estimate_minutes)
    order.history.append(OrderStatusHistory(status=OrderStatus.pending, note="Payment confirmed"))
    for it in order.items:  # decrement tracked stock only
        if it.is_request:
            continue
        if it.variant_id:
            v = db.get(ProductVariant, it.variant_id)
            if v and v.stock_qty is not None:
                v.stock_qty = max(0, v.stock_qty - it.quantity)
        else:
            pr = db.get(Product, it.product_id)
            if pr and pr.stock_qty is not None:
                pr.stock_qty = max(0, pr.stock_qty - it.quantity)
    notify(db, order.user_id, "order_confirmed", "Order confirmed",
           f"Payment received. Your order {order.number} has been sent to {shop.name}.", order.id)
    notify_shop(db, order.shop_id, "new_order", "New order", f"New paid order {order.number}.", order.id)


def _topup_paid(db: Session, order: Order, p: Payment) -> None:
    req = db.get(ProductRequest, p.request_id)
    item = next((i for i in order.items if i.request_id == req.id), None)
    item.unit_price = money(req.confirmed_unit_price)
    req.status = RequestStatus.approved
    order.subtotal = money(order.subtotal + item.unit_price * item.quantity)
    order.total = money(order.total + p.amount)
    notify(db, order.user_id, "request_paid", "Extra item paid", f"Payment received for {req.name}.", order.id)
    notify_shop(db, order.shop_id, "request_paid", "Special item paid", f"{req.name} is paid for on {order.number}.", order.id)


def handle_webhook(db: Session, raw_body: bytes, signature: str | None, payload: dict) -> str:
    if not verify_signature(raw_body, signature):
        raise HTTPException(401, "Invalid signature.")
    data = payload.get("data") or {}
    reference = data.get("reference")
    if not reference:
        return "ignored"
    event_key = f"{payload.get('event')}:{reference}"
    try:
        with db.begin_nested():
            db.add(WebhookEvent(provider="paystack", event_key=event_key))
            db.flush()
    except IntegrityError:
        return "duplicate"
    event = payload.get("event")
    if event == "charge.success":
        # Never trust the webhook body alone: confirm with the provider.
        verified = get_provider().verify(reference)
        apply_provider_result(db, reference, verified)
    return "ok"
