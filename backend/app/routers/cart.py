import os
import secrets
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, CurrentUser, Student
from ..models import (Availability, Cart, CartItem, Product, ProductRequest, ProductVariant, RequestStatus, Shop)
from ..serializers import f
from ..services.pricing import delivery_fee
from ..services.util import money

router = APIRouter(prefix="/cart", tags=["cart"], dependencies=[Student])

ALLOWED_IMG = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}


def sniff_image(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(file: UploadFile, sub: str) -> str:
    s = get_settings()
    data = file.file.read(s.max_upload_bytes + 1)
    if len(data) > s.max_upload_bytes:
        raise HTTPException(413, "That image is too large. Maximum size is 2 MB.")
    kind = sniff_image(data)
    if kind not in ALLOWED_IMG:
        raise HTTPException(415, "Upload a JPG, PNG or WebP image.")
    os.makedirs(os.path.join(s.upload_dir, sub), exist_ok=True)
    name = secrets.token_hex(12) + ALLOWED_IMG[kind]
    with open(os.path.join(s.upload_dir, sub, name), "wb") as fh:
        fh.write(data)
    return f"/uploads/{sub}/{name}"


def get_cart(db, user) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if not cart:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()
    return cart


def cart_view(db, user) -> dict:
    cart = get_cart(db, user)
    lines, subtotal, shop_ids, warnings = [], 0, set(), []
    for ci in cart.items:
        p = ci.product
        unit = ci.variant.price if ci.variant and ci.variant.price is not None else p.price
        avail = (ci.variant.availability if ci.variant else p.availability) == Availability.available and p.active
        ok = avail and unit is not None
        if not ok:
            warnings.append(f"{p.name} is not available to order right now.")
        if unit is not None:
            subtotal += money(unit) * ci.quantity
        shop_ids.add(p.shop_id)
        lines.append({"id": ci.id, "product_id": p.id, "name": p.name, "variant": ci.variant.name if ci.variant else None,
                      "variant_id": ci.variant_id, "image_url": p.image_url, "unit_price": f(unit), "quantity": ci.quantity,
                      "line_total": f(money(unit) * ci.quantity) if unit is not None else None, "orderable": ok})
    reqs = db.scalars(select(ProductRequest).where(ProductRequest.user_id == user.id,
                                                   ProductRequest.in_cart.is_(True))).all()
    req_out = []
    for r in reqs:
        shop_ids.add(r.shop_id)
        priced = r.status == RequestStatus.priced
        if priced:
            subtotal += money(r.confirmed_unit_price) * r.quantity
        req_out.append({"id": r.id, "name": r.name, "description": r.description, "brand": r.brand,
                        "quantity": r.quantity, "image_url": r.image_url, "status": r.status.value,
                        "unit_price": f(r.confirmed_unit_price) if priced else None, "shop_note": r.shop_note,
                        "message": ("Price confirmed by the shop." if priced else
                                    "Rejected by the shop. Remove it to continue." if r.status == RequestStatus.rejected
                                    else "Price and availability need shop confirmation.")})
    fee, shop = None, None
    if len(shop_ids) == 1:
        shop = db.get(Shop, next(iter(shop_ids)))
        fee = delivery_fee(db, shop)
    elif len(shop_ids) > 1:
        warnings.append("Your cart has items from different shops. Order from one shop at a time.")
    total = (subtotal + fee) if fee is not None else None
    return {"shop_id": shop.id if shop else None, "shop_name": shop.name if shop else None, "items": lines,
            "requests": req_out, "subtotal": f(subtotal), "delivery_fee": f(fee), "discount": 0.0,
            "total": f(total), "currency": "GHS", "warnings": warnings,
            "fee_configured": fee is not None or shop is None,
            "pending_confirmation": any(r["status"] == "submitted" for r in req_out)}


@router.get("")
def read_cart(user: CurrentUser, db: DB):
    out = cart_view(db, user)
    db.commit()
    return out


class AddIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=50)


@router.post("/items", status_code=201)
def add_item(body: AddIn, user: CurrentUser, db: DB):
    p = db.get(Product, body.product_id)
    if not p or not p.active:
        raise HTTPException(404, "Product not found.")
    v = None
    if body.variant_id:
        v = db.get(ProductVariant, body.variant_id)
        if not v or v.product_id != p.id:
            raise HTTPException(422, "Choose a valid option.")
    elif p.variants:
        raise HTTPException(422, "Choose an option first.")
    avail = v.availability if v else p.availability
    unit = v.price if v and v.price is not None else p.price
    if avail != Availability.available:
        raise HTTPException(409, f"{p.name} is not available right now.")
    if unit is None:
        raise HTTPException(409, f"{p.name} has no price yet, so it cannot be ordered. You can request it as a special item.")
    cart = get_cart(db, user)
    other = {i.product.shop_id for i in cart.items}
    reqs = {r.shop_id for r in db.scalars(select(ProductRequest).where(
        ProductRequest.user_id == user.id, ProductRequest.in_cart.is_(True)))}
    if (other | reqs) - {p.shop_id}:
        raise HTTPException(409, "Your cart has items from another shop. Finish or clear it first.")
    line = next((i for i in cart.items if i.product_id == p.id and i.variant_id == (v.id if v else None)), None)
    qty = (line.quantity if line else 0) + body.quantity
    stock = v.stock_qty if v else p.stock_qty
    if stock is not None and qty > stock:
        raise HTTPException(409, f"Only {stock} of {p.name} left.")
    if line:
        line.quantity = qty
    else:
        db.add(CartItem(cart_id=cart.id, product_id=p.id, variant_id=v.id if v else None, quantity=body.quantity))
    db.flush()
    db.expire(cart)
    out = cart_view(db, user)
    db.commit()
    return out


class QtyIn(BaseModel):
    quantity: int = Field(ge=0, le=50)


@router.patch("/items/{item_id}")
def set_qty(item_id: int, body: QtyIn, user: CurrentUser, db: DB):
    cart = get_cart(db, user)
    line = next((i for i in cart.items if i.id == item_id), None)
    if not line:
        raise HTTPException(404, "Item not in your cart.")
    if body.quantity == 0:
        db.delete(line)
    else:
        stock = line.variant.stock_qty if line.variant else line.product.stock_qty
        if stock is not None and body.quantity > stock:
            raise HTTPException(409, f"Only {stock} of {line.product.name} left.")
        line.quantity = body.quantity
    db.flush()
    db.expire(cart)
    out = cart_view(db, user)
    db.commit()
    return out


@router.delete("")
def clear_cart(user: CurrentUser, db: DB):
    cart = get_cart(db, user)
    for i in list(cart.items):
        db.delete(i)
    for r in db.scalars(select(ProductRequest).where(ProductRequest.user_id == user.id, ProductRequest.in_cart.is_(True))):
        r.in_cart = False
    db.flush()
    db.expire(cart)
    out = cart_view(db, user)
    db.commit()
    return out


# ---- unlisted item requests ----
class RequestIn(BaseModel):
    shop_id: int
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    brand: str | None = Field(default=None, max_length=100)
    quantity: int = Field(default=1, ge=1, le=50)
    image_url: str | None = Field(default=None, max_length=500)


@router.post("/requests", status_code=201)
def create_request(body: RequestIn, user: CurrentUser, db: DB):
    shop = db.get(Shop, body.shop_id)
    if not shop or not shop.active:
        raise HTTPException(404, "Shop not found.")
    cart = get_cart(db, user)
    other = {i.product.shop_id for i in cart.items} | {r.shop_id for r in db.scalars(select(ProductRequest).where(
        ProductRequest.user_id == user.id, ProductRequest.in_cart.is_(True)))}
    if other - {shop.id}:
        raise HTTPException(409, "Your cart has items from another shop. Finish or clear it first.")
    if body.image_url and not body.image_url.startswith("/uploads/"):
        raise HTTPException(422, "Upload the reference image through Send Me.")
    r = ProductRequest(user_id=user.id, shop_id=shop.id, **body.model_dump(exclude={"shop_id"}))
    db.add(r)
    db.flush()
    out = cart_view(db, user)
    db.commit()
    return out


@router.post("/requests/image")
def upload_request_image(file: UploadFile = File(...)):
    return {"image_url": save_image(file, "requests")}


@router.delete("/requests/{rid}")
def remove_request(rid: int, user: CurrentUser, db: DB):
    r = db.get(ProductRequest, rid)
    if not r or r.user_id != user.id or not r.in_cart:
        raise HTTPException(404, "Request not found.")
    r.in_cart = False
    db.flush()
    out = cart_view(db, user)
    db.commit()
    return out
