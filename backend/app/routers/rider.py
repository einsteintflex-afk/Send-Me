from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import DB, CurrentUser, RiderUser
from ..models import DeliveryAssignment, Order, OrderStatus, Rider, User
from ..serializers import order_out
from ..services import orders as osvc
from ..services.notify import notify, notify_shop

router = APIRouter(prefix="/rider", tags=["rider"], dependencies=[RiderUser])


def _mine(db, user, oid) -> Order:
    o = db.get(Order, oid)
    if not o or not o.assignment or o.assignment.rider_id != user.id:
        raise HTTPException(404, "Delivery not found.")  # riders only ever see their own deliveries
    return o


def _out(db, o):
    out = order_out(o)
    u = db.get(User, o.user_id)
    out["customer"] = {"name": u.full_name, "phone": u.phone}
    out["failed_reason"] = o.assignment.failed_reason
    return out


@router.get("/deliveries")
def deliveries(user: CurrentUser, db: DB, active: bool = True):
    q = select(Order).join(DeliveryAssignment, DeliveryAssignment.order_id == Order.id).where(
        DeliveryAssignment.rider_id == user.id)
    if active:
        q = q.where(Order.status.in_([OrderStatus.accepted, OrderStatus.shopping, OrderStatus.on_the_way]))
    return [_out(db, o) for o in db.scalars(q.order_by(Order.id.desc()))]


@router.get("/deliveries/{oid}")
def delivery(oid: int, user: CurrentUser, db: DB):
    return _out(db, _mine(db, user, oid))


@router.post("/deliveries/{oid}/accept")
def accept(oid: int, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    if o.status in (OrderStatus.delivered, OrderStatus.cancelled):
        raise HTTPException(409, "This delivery is closed.")
    if not o.assignment.accepted_at:
        o.assignment.accepted_at = datetime.now(timezone.utc)
        notify_shop(db, o.shop_id, "rider_accepted", "Rider accepted", f"Rider accepted {o.number}.", o.id)
    db.commit()
    return _out(db, o)


@router.post("/deliveries/{oid}/pickup")
def pickup(oid: int, user: CurrentUser, db: DB):
    """Rider collected the order from the shop. Moves Shopping to On the Way."""
    o = _mine(db, user, oid)
    if not o.assignment.accepted_at:
        raise HTTPException(409, "Accept the delivery first.")
    osvc.change_status(db, o, OrderStatus.on_the_way, user, "Collected by rider")
    db.commit()
    return _out(db, o)


@router.post("/deliveries/{oid}/delivered")
def delivered(oid: int, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    osvc.change_status(db, o, OrderStatus.delivered, user, "Delivered by rider")
    db.commit()
    return _out(db, o)


class FailIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/deliveries/{oid}/failed")
def failed(oid: int, body: FailIn, user: CurrentUser, db: DB):
    o = _mine(db, user, oid)
    if o.status != OrderStatus.on_the_way:
        raise HTTPException(409, "You can report a failed attempt once the order is on the way.")
    o.assignment.failed_reason = body.reason
    notify(db, o.user_id, "delivery_failed", "Delivery attempt unsuccessful",
           f"The rider could not complete delivery: {body.reason}", o.id)
    notify_shop(db, o.shop_id, "delivery_failed", "Delivery attempt failed", f"{o.number}: {body.reason}", o.id)
    db.commit()
    return _out(db, o)


class LocIn(BaseModel):
    lat: Decimal = Field(ge=-90, le=90)
    lng: Decimal = Field(ge=-180, le=180)


@router.post("/location")
def location(body: LocIn, user: CurrentUser, db: DB):
    """GPS hook. The rider app can post positions here; students see them on tracking once enabled in the UI."""
    r = db.get(Rider, user.id)
    r.last_lat, r.last_lng, r.last_seen_at = body.lat, body.lng, datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
