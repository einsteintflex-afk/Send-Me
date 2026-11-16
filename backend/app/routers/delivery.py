from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import DB, CurrentUser, Student
from ..models import Address, Order, OrderStatus, Shop
from ..services.maps import haversine_meters
from ..services.pricing import dest_coords, quote_delivery
from datetime import datetime, timezone

router = APIRouter(tags=["delivery"], dependencies=[Student])


class QuoteIn(BaseModel):
    shop_id: int
    address_id: int


@router.post("/delivery/quote")
def quote(body: QuoteIn, user: CurrentUser, db: DB):
    shop = db.get(Shop, body.shop_id)
    addr = db.get(Address, body.address_id)
    if not shop or not shop.active:
        raise HTTPException(404, "Shop not found.")
    if not addr or addr.user_id != user.id:
        raise HTTPException(404, "Destination not found.")
    q = quote_delivery(db, shop, addr)
    if not q:
        raise HTTPException(409, "Delivery is not available yet because the delivery fee has not been set.")
    db.commit()
    return {"delivery_fee": float(q["fee"]), "distance_km": q["distance_km"], "method": q["method"], "currency": "GHS",
            "approximate": q["method"] == "straight_line"}


STALE_SECONDS = 120


@router.get("/orders/{oid}/tracking")
def tracking(oid: int, user: CurrentUser, db: DB):
    o = db.get(Order, oid)
    if not o or o.user_id != user.id:
        raise HTTPException(404, "Order not found.")
    a = o.assignment
    live = o.status == OrderStatus.on_the_way and a is not None
    out = {"order_id": o.id, "status": o.status.value, "live": live, "rider": None, "rider_position": None,
           "destination": None, "shop": None, "distance_to_destination_km": None}
    shop = db.get(Shop, o.shop_id)
    if shop.latitude is not None:
        out["shop"] = {"name": shop.name, "latitude": float(shop.latitude), "longitude": float(shop.longitude)}
    dest = dest_coords(db, o.destination)
    if dest:
        out["destination"] = {"latitude": dest[0], "longitude": dest[1]}
    if a:
        out["rider"] = {"name": a.rider.user.full_name, "phone": a.rider.user.phone}
    # The rider's position is shared only while the order is On the Way.
    if live and a.rider.last_lat is not None:
        age = (datetime.now(timezone.utc) - (a.rider.last_seen_at if a.rider.last_seen_at.tzinfo
                                              else a.rider.last_seen_at.replace(tzinfo=timezone.utc))).total_seconds()
        out["rider_position"] = {"latitude": float(a.rider.last_lat), "longitude": float(a.rider.last_lng),
                                 "updated_at": a.rider.last_seen_at.isoformat(), "stale": age > STALE_SECONDS}
        if dest:
            out["distance_to_destination_km"] = round(haversine_meters(
                float(a.rider.last_lat), float(a.rider.last_lng), dest[0], dest[1]) / 1000, 2)
    return out
