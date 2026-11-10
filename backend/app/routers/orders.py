from typing import Annotated
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..deps import DB, CurrentUser, Student
from ..models import (Notification, Order, OrderStatus, PaymentStatus, ProductRequest, RequestStatus, Review)
from ..serializers import order_out
from ..services import orders as osvc
from ..services import payments as psvc
from ..services.notify import notify_shop

router = APIRouter(tags=["orders"])


class CheckoutIn(BaseModel):
    address_id: int
    instructions: str | None = Field(default=None, max_length=300)


def _mine(db, user, oid) -> Order:
    o = db.get(Order, oid)
    if not o or o.user_id != user.id:
        raise HTTPException(404, "Order not found.")  # same answer for other people's orders
    return o


@router.post("/checkout", status_code=201, dependencies=[Student])
def checkout(body: CheckoutIn, user: CurrentUser, db: DB,
             idempotency_key: Annotated[str | None, Header(max_length=64)] = None):
    order = osvc.create_order_from_cart(db, user, body.address_id, body.instructions, idempotency_key)
    db.commit()
    return order_out(order)


@router.get("/orders", dependencies=[Student])
def my_orders(user: CurrentUser, db: DB):
    rows = db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())).all()
    return [order_out(o) for o in rows]


@router.get("/orders/{oid}", dependencies=[Student])
def order_detail(oid: int, user: CurrentUser, db: DB):
    return order_out(_mine(db, user, oid))


@router.post("/orders/{oid}/cancel", dependencies=[Student])
def cancel(oid: int, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    if o.status != OrderStatus.pending:
        raise HTTPException(409, "This order can no longer be cancelled because the shop has already accepted it. Contact the shop.")
    osvc.change_status(db, o, OrderStatus.cancelled, user, "Cancelled by student")
    if o.payment_status == PaymentStatus.awaiting:
        o.payment_status = PaymentStatus.abandoned
    notify_shop(db, o.shop_id, "order_cancelled", "Order cancelled", f"{o.number or '#'+str(o.id)} was cancelled by the student.", o.id)
    db.commit()
    return order_out(o)


@router.post("/orders/{oid}/pay", dependencies=[Student])
def pay(oid: int, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    p = psvc.init_payment(db, o, user)
    db.commit()
    return {"reference": p.reference, "authorization_url": p.provider_payload.get("authorization_url"),
            "amount": float(p.amount), "currency": p.currency}


@router.post("/payments/verify/{reference}", dependencies=[Student])
def verify(reference: str, user: CurrentUser, db: DB):
    from ..models import Payment
    p = db.scalar(select(Payment).where(Payment.reference == reference))
    if not p or db.get(Order, p.order_id).user_id != user.id:
        raise HTTPException(404, "Payment not found.")
    if p.status != "success":
        data = psvc.get_provider().verify(reference)
        p = psvc.apply_provider_result(db, reference, data)
        db.commit()
    o = db.get(Order, p.order_id)
    return {"payment_status": p.status, "order": order_out(o)}


@router.post("/payments/webhook/paystack")
async def paystack_webhook(request: Request, db: DB, x_paystack_signature: Annotated[str | None, Header()] = None):
    raw = await request.body()
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Bad payload.")
    result = psvc.handle_webhook(db, raw, x_paystack_signature, payload)
    db.commit()
    return {"result": result}


# ---- unlisted item price approval (after order exists) ----
@router.post("/orders/{oid}/requests/{rid}/approve", dependencies=[Student])
def approve_request_price(oid: int, rid: int, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    r = db.get(ProductRequest, rid)
    if not r or r.order_id != o.id:
        raise HTTPException(404, "Request not found.")
    if r.status != RequestStatus.priced or r.confirmed_unit_price is None:
        raise HTTPException(409, "There is no price to approve for this item.")
    if o.status in (OrderStatus.cancelled, OrderStatus.delivered):
        raise HTTPException(409, "This order is closed.")
    amount = r.confirmed_unit_price * r.quantity
    p = psvc.init_payment(db, o, user, kind="request_topup", request=r, amount=amount)
    db.commit()
    return {"reference": p.reference, "authorization_url": p.provider_payload.get("authorization_url"),
            "amount": float(p.amount), "currency": p.currency}


@router.post("/orders/{oid}/requests/{rid}/decline", dependencies=[Student])
def decline_request_price(oid: int, rid: int, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    r = db.get(ProductRequest, rid)
    if not r or r.order_id != o.id or r.status != RequestStatus.priced:
        raise HTTPException(404, "Request not found.")
    r.status = RequestStatus.declined
    db.commit()
    return order_out(o)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


@router.post("/orders/{oid}/review", status_code=201, dependencies=[Student])
def review(oid: int, body: ReviewIn, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    if o.status != OrderStatus.delivered:
        raise HTTPException(409, "You can review an order after it is delivered.")
    if db.scalar(select(Review).where(Review.order_id == o.id)):
        raise HTTPException(409, "You already reviewed this order.")
    db.add(Review(order_id=o.id, user_id=user.id, shop_id=o.shop_id, rating=body.rating, comment=body.comment))
    db.commit()
    return {"ok": True}


# ---- notifications ----
@router.get("/notifications")
def notifications(user: CurrentUser, db: DB):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.id.desc()).limit(100)).all()
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "order_id": n.order_id, "read": n.read,
             "created_at": n.created_at.isoformat()} for n in rows]


@router.post("/notifications/read")
def mark_read(user: CurrentUser, db: DB):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))):
        n.read = True
    db.commit()
    return {"ok": True}
