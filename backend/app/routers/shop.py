from decimal import Decimal
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..deps import DB, CurrentUser, ShopUser, shop_scope
from ..models import (Availability, Category, Order, OrderStatus, PaymentStatus, Product, ProductRequest,
                      ProductVariant, RequestStatus, Rider, Shop, User, Payment)
from ..routers.cart import save_image
from ..serializers import order_out, product_out, shop_out, f
from ..services import orders as osvc
from ..services.audit import audit
from ..services.notify import notify
from ..services.util import money

router = APIRouter(prefix="/shop", tags=["shop"], dependencies=[ShopUser])


def sid(db, user, shop_id):  # resolve the shop this user may touch
    return shop_scope(db, user, shop_id)


def _order(db, shop_id, oid) -> Order:
    o = db.get(Order, oid)
    if not o or o.shop_id != shop_id or o.payment_status not in (PaymentStatus.paid, PaymentStatus.refund_pending,
                                                                   PaymentStatus.refunded):
        raise HTTPException(404, "Order not found.")
    return o


def _shop_order_out(db, o: Order):
    out = order_out(o)
    u = db.get(User, o.user_id)
    out["customer"] = {"name": u.full_name, "phone": u.phone}
    return out


@router.get("/overview")
def overview(user: CurrentUser, db: DB, shop_id: int | None = None):
    s = sid(db, user, shop_id)
    paid = Order.payment_status.in_([PaymentStatus.paid, PaymentStatus.refund_pending, PaymentStatus.refunded])
    counts = dict(db.execute(select(Order.status, func.count()).where(Order.shop_id == s, paid).group_by(Order.status)).all())
    revenue = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(
        Order.shop_id == s, Order.payment_status == PaymentStatus.paid, Order.status != OrderStatus.cancelled))
    recent = db.scalars(select(Payment).join(Order, Payment.order_id == Order.id).where(
        Order.shop_id == s, Payment.status == "success").order_by(Payment.id.desc()).limit(10)).all()
    low = db.scalars(select(Product).where(Product.shop_id == s, Product.stock_qty.is_not(None),
                                           Product.low_stock_threshold.is_not(None),
                                           Product.stock_qty <= Product.low_stock_threshold)).all()
    return {"total_orders": sum(counts.values()),
            "by_status": {st.value: counts.get(st, 0) for st in OrderStatus},
            "revenue": f(revenue), "currency": "GHS",
            "recent_transactions": [{"reference": p.reference, "amount": f(p.amount), "channel": p.channel,
                                     "at": p.verified_at.isoformat() if p.verified_at else None} for p in recent],
            "low_stock": [{"id": p.id, "name": p.name, "stock_qty": p.stock_qty} for p in low],
            "open_requests": db.scalar(select(func.count()).select_from(ProductRequest).where(
                ProductRequest.shop_id == s, ProductRequest.status == RequestStatus.submitted))}


@router.get("/orders")
def list_orders(user: CurrentUser, db: DB, shop_id: int | None = None, status: str | None = None):
    s = sid(db, user, shop_id)
    q = select(Order).where(Order.shop_id == s, Order.payment_status.in_(
        [PaymentStatus.paid, PaymentStatus.refund_pending, PaymentStatus.refunded]))
    if status:
        try:
            q = q.where(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(422, "Unknown status.")
    return [_shop_order_out(db, o) for o in db.scalars(q.order_by(Order.id.desc()).limit(200))]


@router.get("/orders/{oid}")
def order_detail(oid: int, user: CurrentUser, db: DB, shop_id: int | None = None):
    return _shop_order_out(db, _order(db, sid(db, user, shop_id), oid))


class StatusIn(BaseModel):
    status: OrderStatus
    note: str | None = Field(default=None, max_length=300)


@router.post("/orders/{oid}/status")
def update_status(oid: int, body: StatusIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    o = _order(db, sid(db, user, shop_id), oid)
    osvc.change_status(db, o, body.status, user, body.note)
    audit(db, user.id, "order.status", f"order:{o.id}", {"to": body.status.value})
    db.commit()
    return _shop_order_out(db, o)


class AssignIn(BaseModel):
    rider_id: int


@router.post("/orders/{oid}/assign")
def assign(oid: int, body: AssignIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    o = _order(db, sid(db, user, shop_id), oid)
    osvc.assign_rider(db, o, body.rider_id, user)
    audit(db, user.id, "order.assign_rider", f"order:{o.id}", {"rider": body.rider_id})
    db.commit()
    return _shop_order_out(db, o)


@router.get("/riders")
def riders(user: CurrentUser, db: DB, shop_id: int | None = None):
    s = db.get(Shop, sid(db, user, shop_id))
    rows = db.scalars(select(Rider).where(Rider.campus_id == s.campus_id, Rider.active.is_(True))).all()
    return [{"id": r.user_id, "name": r.user.full_name, "phone": r.user.phone} for r in rows]


# ---- catalogue ----
class VariantIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    availability: Availability = Availability.available
    stock_qty: int | None = Field(default=None, ge=0)


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    availability: Availability = Availability.available
    stock_qty: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    featured: bool = False
    image_url: str | None = Field(default=None, max_length=500)
    variants: list[VariantIn] = []


def _cat(db, slug) -> Category:
    c = db.scalar(select(Category).where(Category.slug == slug))
    if not c:
        raise HTTPException(422, "Unknown category.")
    return c


@router.get("/products")
def list_products(user: CurrentUser, db: DB, shop_id: int | None = None):
    s = sid(db, user, shop_id)
    rows = db.scalars(select(Product).where(Product.shop_id == s).order_by(Product.name)).all()
    return [{**product_out(p, detail=True), "stock_qty": p.stock_qty, "low_stock_threshold": p.low_stock_threshold,
             "active": p.active} for p in rows]


@router.post("/products", status_code=201)
def create_product(body: ProductIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    s = sid(db, user, shop_id)
    if db.scalar(select(Product).where(Product.shop_id == s, Product.name == body.name)):
        raise HTTPException(409, "This shop already has a product with that name.")
    p = Product(shop_id=s, category_id=_cat(db, body.category).id, **body.model_dump(exclude={"category", "variants"}))
    p.variants = [ProductVariant(**v.model_dump()) for v in body.variants]
    db.add(p)
    audit(db, user.id, "product.create", body.name)
    db.commit()
    return product_out(p, detail=True)


def _own_product(db, s, pid) -> Product:
    p = db.get(Product, pid)
    if not p or p.shop_id != s:
        raise HTTPException(404, "Product not found.")
    return p


@router.put("/products/{pid}")
def update_product(pid: int, body: ProductIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    s = sid(db, user, shop_id)
    p = _own_product(db, s, pid)
    for k, v in body.model_dump(exclude={"category", "variants"}).items():
        setattr(p, k, v)
    p.category_id = _cat(db, body.category).id
    old = {v.name: v for v in p.variants}
    keep = set()
    for vin in body.variants:
        keep.add(vin.name)
        if vin.name in old:
            for k, v in vin.model_dump().items():
                setattr(old[vin.name], k, v)
        else:
            p.variants.append(ProductVariant(**vin.model_dump()))
    for name, v in old.items():
        if name not in keep:
            p.variants.remove(v)
    audit(db, user.id, "product.update", f"product:{p.id}")
    db.commit()
    return product_out(p, detail=True)


class AvailIn(BaseModel):
    availability: Availability | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    stock_qty: int | None = Field(default=None, ge=0)


@router.patch("/products/{pid}")
def quick_update(pid: int, body: AvailIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    p = _own_product(db, sid(db, user, shop_id), pid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    audit(db, user.id, "product.quick_update", f"product:{p.id}", body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return product_out(p, detail=True)


@router.delete("/products/{pid}", status_code=204)
def deactivate_product(pid: int, user: CurrentUser, db: DB, shop_id: int | None = None):
    p = _own_product(db, sid(db, user, shop_id), pid)
    p.active = False  # soft delete: past orders keep their snapshots
    audit(db, user.id, "product.deactivate", f"product:{p.id}")
    db.commit()


@router.post("/products/{pid}/image")
def product_image(pid: int, user: CurrentUser, db: DB, file: UploadFile = File(...), shop_id: int | None = None):
    p = _own_product(db, sid(db, user, shop_id), pid)
    p.image_url = save_image(file, "products")
    db.commit()
    return {"image_url": p.image_url}


# ---- unlisted item requests ----
def _req_out(r: ProductRequest):
    return {"id": r.id, "name": r.name, "description": r.description, "brand": r.brand, "quantity": r.quantity,
            "image_url": r.image_url, "status": r.status.value, "confirmed_unit_price": f(r.confirmed_unit_price),
            "order_id": r.order_id, "shop_note": r.shop_note}


@router.get("/requests")
def list_requests(user: CurrentUser, db: DB, shop_id: int | None = None, status: str | None = None):
    s = sid(db, user, shop_id)
    q = select(ProductRequest).where(ProductRequest.shop_id == s)
    if status:
        try:
            q = q.where(ProductRequest.status == RequestStatus(status))
        except ValueError:
            raise HTTPException(422, "Unknown status.")
    return [_req_out(r) for r in db.scalars(q.order_by(ProductRequest.id.desc()).limit(200))]


class RespondIn(BaseModel):
    accept: bool
    unit_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    note: str | None = Field(default=None, max_length=300)


@router.post("/requests/{rid}/respond")
def respond(rid: int, body: RespondIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    s = sid(db, user, shop_id)
    r = db.get(ProductRequest, rid)
    if not r or r.shop_id != s:
        raise HTTPException(404, "Request not found.")
    if r.status not in (RequestStatus.submitted, RequestStatus.priced):
        raise HTTPException(409, "This request has already been settled.")
    if body.accept:
        if body.unit_price is None:
            raise HTTPException(422, "Enter the confirmed price.")
        r.confirmed_unit_price = money(body.unit_price)
        r.status = RequestStatus.priced
        msg = f"{r.name} is available at GH₵ {r.confirmed_unit_price} each."
        if r.order_id:
            msg += " Open your order to approve the price and pay."
        notify(db, r.user_id, "request_priced", "Price confirmed", msg, r.order_id)
    else:
        r.status = RequestStatus.rejected
        notify(db, r.user_id, "request_rejected", "Item not available", f"The shop cannot supply {r.name}.", r.order_id)
    r.shop_note = body.note
    audit(db, user.id, "request.respond", f"request:{r.id}", {"accept": body.accept})
    db.commit()
    return _req_out(r)


# ---- settings ----
class SettingsIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    phones: list[str] | None = None
    opening_hours: dict | None = None
    delivery_estimate_minutes: int | None = Field(default=None, ge=1, le=600)
    accepting_orders: bool | None = None


@router.get("/settings")
def get_settings_(user: CurrentUser, db: DB, shop_id: int | None = None):
    return shop_out(db.get(Shop, sid(db, user, shop_id)))


@router.patch("/settings")
def update_settings(body: SettingsIn, user: CurrentUser, db: DB, shop_id: int | None = None):
    s = db.get(Shop, sid(db, user, shop_id))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    audit(db, user.id, "shop.settings", f"shop:{s.id}")
    db.commit()
    return shop_out(s)
