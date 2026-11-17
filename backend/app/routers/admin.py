from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select

from ..deps import DB, CurrentUser, SuperAdmin
from ..models import (AuditLog, Campus, Category, Complaint, Hostel, ProductRequest, RequestStatus, DeliveryPricing, Order, OrderStatus, Payment,
                      PaymentStatus, Promotion, Review, Rider, Role, Shop, ShopStaff, SystemSetting, University, User)
from ..security import hash_password
from ..serializers import f, shop_out
from ..services.audit import audit
from ..services.maps import MapsError, get_maps
from ..services.pricing import MODES, SETTING_KEY
from ..services.util import money, normalize_gh_phone

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[SuperAdmin])


def _user_out(u: User):
    return {"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "role": u.role.value,
            "is_active": u.is_active}


@router.get("/users")
def users(db: DB, role: Role | None = None, q: str | None = None, limit: int = 100, offset: int = 0):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like),
                                User.phone.like(f"%{q}%")))
    return [_user_out(u) for u in db.scalars(query.order_by(User.id.desc()).limit(min(limit, 200)).offset(offset))]


class ActiveIn(BaseModel):
    is_active: bool


@router.post("/users/{uid}/active")
def set_active(uid: int, body: ActiveIn, admin: CurrentUser, db: DB):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found.")
    if u.id == admin.id:
        raise HTTPException(409, "You cannot suspend your own account.")
    u.is_active = body.is_active
    audit(db, admin.id, "user.suspend" if not body.is_active else "user.reactivate", f"user:{u.id}")
    db.commit()
    return _user_out(u)


class NameIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)


@router.post("/universities", status_code=201)
def add_university(body: NameIn, admin: CurrentUser, db: DB):
    if db.scalar(select(University).where(University.name == body.name)):
        raise HTTPException(409, "That university already exists.")
    u = University(name=body.name)
    db.add(u)
    audit(db, admin.id, "university.create", body.name)
    db.commit()
    return {"id": u.id, "name": u.name}


class CampusIn(BaseModel):
    university_id: int
    name: str = Field(min_length=2, max_length=200)


@router.post("/campuses", status_code=201)
def add_campus(body: CampusIn, admin: CurrentUser, db: DB):
    if not db.get(University, body.university_id):
        raise HTTPException(404, "University not found.")
    c = Campus(university_id=body.university_id, name=body.name)
    db.add(c)
    audit(db, admin.id, "campus.create", body.name)
    db.commit()
    return {"id": c.id, "name": c.name}


class ShopIn(BaseModel):
    campus_id: int
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern="^[a-z0-9-]{2,100}$")
    location: str | None = None
    phones: list[str] = []


@router.post("/shops", status_code=201)
def add_shop(body: ShopIn, admin: CurrentUser, db: DB):
    if not db.get(Campus, body.campus_id):
        raise HTTPException(404, "Campus not found.")
    if db.scalar(select(Shop).where(Shop.slug == body.slug)):
        raise HTTPException(409, "That shop address is taken.")
    s = Shop(**body.model_dump())
    db.add(s)
    audit(db, admin.id, "shop.create", body.name)
    db.commit()
    return shop_out(s)


@router.get("/shops")
def all_shops(db: DB):
    return [{**shop_out(s), "active": s.active} for s in db.scalars(select(Shop).order_by(Shop.name))]


class ShopActiveIn(BaseModel):
    active: bool


@router.post("/shops/{sid}/active")
def shop_active(sid: int, body: ShopActiveIn, admin: CurrentUser, db: DB):
    s = db.get(Shop, sid)
    if not s:
        raise HTTPException(404, "Shop not found.")
    s.active = body.active
    audit(db, admin.id, "shop.active", f"shop:{sid}", {"active": body.active})
    db.commit()
    return shop_out(s)


class StaffIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str
    password: str = Field(min_length=8, max_length=128)
    role: Role


def _create_user(db, body, role: Role) -> User:
    phone = normalize_gh_phone(body.phone)
    email = body.email.lower() if body.email else None
    clash = [User.phone == phone] + ([User.email == email] if email else [])
    if db.scalar(select(User).where(or_(*clash))):
        raise HTTPException(409, "An account with this email or phone number already exists.")
    u = User(email=email, phone=phone, full_name=body.full_name.strip(), role=role,
             password_hash=hash_password(body.password), email_verified=True)
    db.add(u)
    db.flush()
    return u


@router.post("/shops/{sid}/staff", status_code=201)
def add_staff(sid: int, body: StaffIn, admin: CurrentUser, db: DB):
    if body.role not in (Role.shop_admin, Role.shop_staff):
        raise HTTPException(422, "Role must be shop_admin or shop_staff.")
    if not db.get(Shop, sid):
        raise HTTPException(404, "Shop not found.")
    u = _create_user(db, body, body.role)
    db.add(ShopStaff(user_id=u.id, shop_id=sid))
    audit(db, admin.id, "staff.create", f"user:{u.id}", {"shop": sid})
    db.commit()
    return _user_out(u)


class RiderIn(BaseModel):
    """Riders sign in with their phone number. Email is optional."""
    full_name: str = Field(min_length=2, max_length=200)
    phone: str
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    campus_id: int


@router.post("/riders", status_code=201)
def add_rider(body: RiderIn, admin: CurrentUser, db: DB):
    if not db.get(Campus, body.campus_id):
        raise HTTPException(404, "Campus not found.")
    u = _create_user(db, body, Role.rider)
    db.add(Rider(user_id=u.id, campus_id=body.campus_id))
    audit(db, admin.id, "rider.create", f"user:{u.id}")
    db.commit()
    return _user_out(u)


class FeeIn(BaseModel):
    fee: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    shop_id: int | None = None
    campus_id: int | None = None


@router.put("/delivery-pricing")
def set_fee(body: FeeIn, admin: CurrentUser, db: DB):
    row = db.scalar(select(DeliveryPricing).where(DeliveryPricing.shop_id == body.shop_id,
                                                  DeliveryPricing.campus_id == body.campus_id))
    if row:
        row.fee = money(body.fee)
    else:
        db.add(DeliveryPricing(shop_id=body.shop_id, campus_id=body.campus_id, fee=money(body.fee)))
    audit(db, admin.id, "delivery_fee.set", None, {"fee": str(body.fee), "shop": body.shop_id, "campus": body.campus_id})
    db.commit()
    return {"ok": True}


@router.get("/delivery-pricing")
def list_fees(db: DB):
    return [{"id": r.id, "shop_id": r.shop_id, "campus_id": r.campus_id, "fee": f(r.fee)}
            for r in db.scalars(select(DeliveryPricing))]


class CategoryIn(BaseModel):
    slug: str = Field(pattern="^[a-z0-9-]{2,100}$")
    name: str = Field(min_length=2, max_length=100)
    icon: str | None = None
    sort_order: int = 0


@router.post("/categories", status_code=201)
def add_category(body: CategoryIn, admin: CurrentUser, db: DB):
    if db.scalar(select(Category).where(Category.slug == body.slug)):
        raise HTTPException(409, "That category already exists.")
    c = Category(**body.model_dump())
    db.add(c)
    audit(db, admin.id, "category.create", body.slug)
    db.commit()
    return {"id": c.id, "slug": c.slug, "name": c.name}


class PromoIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str | None = Field(default=None, max_length=500)
    image_url: str | None = None
    campus_id: int | None = None
    active: bool = True


@router.post("/promotions", status_code=201)
def add_promo(body: PromoIn, admin: CurrentUser, db: DB):
    p = Promotion(**body.model_dump())
    db.add(p)
    audit(db, admin.id, "promotion.create", body.title)
    db.commit()
    return {"id": p.id}


@router.get("/payments")
def payments(db: DB, status: str | None = None, limit: int = 100):
    q = select(Payment)
    if status:
        q = q.where(Payment.status == status)
    return [{"id": p.id, "order_id": p.order_id, "reference": p.reference, "kind": p.kind, "amount": f(p.amount),
             "status": p.status, "channel": p.channel} for p in db.scalars(q.order_by(Payment.id.desc()).limit(min(limit, 200)))]


@router.get("/orders")
def orders(db: DB, status: str | None = None, limit: int = 100):
    q = select(Order)
    if status:
        try:
            q = q.where(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(422, "Unknown status.")
    return [{"id": o.id, "number": o.number, "shop_id": o.shop_id, "status": o.status.value,
             "payment_status": o.payment_status.value, "total": f(o.total)}
            for o in db.scalars(q.order_by(Order.id.desc()).limit(min(limit, 200)))]


@router.get("/reports/summary")
def report(db: DB):
    paid = (Order.payment_status == PaymentStatus.paid) & (Order.status != OrderStatus.cancelled)
    rev = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(paid))
    per_shop = db.execute(select(Order.shop_id, func.count(), func.coalesce(func.sum(Order.total), 0))
                          .where(paid).group_by(Order.shop_id)).all()
    by_status = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    return {"currency": "GHS", "revenue": f(rev),
            "students": db.scalar(select(func.count()).select_from(User).where(User.role == Role.student)),
            "orders_by_status": {s.value: by_status.get(s, 0) for s in OrderStatus},
            "per_shop": [{"shop_id": s, "orders": n, "revenue": f(r)} for s, n, r in per_shop],
            "refunds_pending": db.scalar(select(func.count()).select_from(Order).where(
                Order.payment_status == PaymentStatus.refund_pending)),
            "average_rating": f(db.scalar(select(func.avg(Review.rating))))}


@router.get("/complaints")
def complaints(db: DB):
    return [{"id": c.id, "user_id": c.user_id, "order_id": c.order_id, "message": c.message, "status": c.status}
            for c in db.scalars(select(Complaint).order_by(Complaint.id.desc()).limit(200))]


class ComplaintIn(BaseModel):
    status: str = Field(pattern="^(open|resolved)$")


@router.post("/complaints/{cid}")
def update_complaint(cid: int, body: ComplaintIn, admin: CurrentUser, db: DB):
    c = db.get(Complaint, cid)
    if not c:
        raise HTTPException(404, "Complaint not found.")
    c.status = body.status
    audit(db, admin.id, "complaint.update", f"complaint:{cid}")
    db.commit()
    return {"ok": True}


@router.get("/audit")
def audit_log(db: DB, limit: int = 100):
    return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "target": a.target, "detail": a.detail,
             "at": a.created_at.isoformat()} for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)))]


class SettingIn(BaseModel):
    value: dict


@router.put("/settings/{key}")
def put_setting(key: str, body: SettingIn, admin: CurrentUser, db: DB):
    row = db.get(SystemSetting, key)
    if row:
        row.value = body.value
    else:
        db.add(SystemSetting(key=key, value=body.value))
    audit(db, admin.id, "setting.set", key)
    db.commit()
    return {"ok": True}


@router.get("/settings")
def get_settings_(db: DB):
    return {r.key: r.value for r in db.scalars(select(SystemSetting))}


class HostelIn(BaseModel):
    campus_id: int
    name: str = Field(min_length=1, max_length=200)


@router.post("/hostels", status_code=201)
def add_hostel(body: HostelIn, admin: CurrentUser, db: DB):
    if not db.get(Campus, body.campus_id):
        raise HTTPException(404, "Campus not found.")
    if db.scalar(select(Hostel).where(Hostel.campus_id == body.campus_id, Hostel.name == body.name)):
        raise HTTPException(409, "That hostel already exists.")
    h = Hostel(campus_id=body.campus_id, name=body.name)
    db.add(h)
    audit(db, admin.id, "hostel.create", body.name)
    db.commit()
    return {"id": h.id, "name": h.name}


@router.post("/hostels/{hid}/active")
def hostel_active(hid: int, body: ShopActiveIn, admin: CurrentUser, db: DB):
    h = db.get(Hostel, hid)
    if not h:
        raise HTTPException(404, "Hostel not found.")
    h.active = body.active
    audit(db, admin.id, "hostel.active", f"hostel:{hid}", {"active": body.active})
    db.commit()
    return {"id": h.id, "active": h.active}


class PasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@router.post("/users/{uid}/password")
def admin_set_password(uid: int, body: PasswordIn, admin: CurrentUser, db: DB):
    """For riders and staff without email, who cannot use the email reset link."""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found.")
    u.password_hash = hash_password(body.password)
    audit(db, admin.id, "user.password_reset", f"user:{u.id}")
    db.commit()
    return {"ok": True}


# ---- distance-based delivery pricing and locations ----
class DistanceIn(BaseModel):
    rate_per_km: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    min_fee: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    travel_mode: str = "WALK"


@router.put("/delivery-distance")
def set_distance_pricing(body: DistanceIn, admin: CurrentUser, db: DB):
    if body.travel_mode not in MODES:
        raise HTTPException(422, "travel_mode must be WALK, DRIVE or TWO_WHEELER.")
    val = {"rate_per_km": str(body.rate_per_km), "min_fee": str(body.min_fee) if body.min_fee is not None else None,
           "travel_mode": body.travel_mode}
    row = db.get(SystemSetting, SETTING_KEY)
    if row:
        row.value = val
    else:
        db.add(SystemSetting(key=SETTING_KEY, value=val))
    audit(db, admin.id, "delivery_distance.set", None, val)
    db.commit()
    return val


@router.get("/delivery-distance")
def get_distance_pricing(db: DB):
    row = db.get(SystemSetting, SETTING_KEY)
    return row.value if row else None


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@router.put("/shops/{sid}/location")
def set_shop_location(sid: int, body: LocationIn, admin: CurrentUser, db: DB):
    s = db.get(Shop, sid)
    if not s:
        raise HTTPException(404, "Shop not found.")
    s.latitude, s.longitude = body.latitude, body.longitude
    audit(db, admin.id, "shop.location", f"shop:{sid}", body.model_dump())
    db.commit()
    return {"id": s.id, "latitude": body.latitude, "longitude": body.longitude}


@router.put("/hostels/{hid}/location")
def set_hostel_location(hid: int, body: LocationIn, admin: CurrentUser, db: DB):
    h = db.get(Hostel, hid)
    if not h:
        raise HTTPException(404, "Hostel not found.")
    h.latitude, h.longitude = body.latitude, body.longitude
    audit(db, admin.id, "hostel.location", f"hostel:{hid}", body.model_dump())
    db.commit()
    return {"id": h.id, "latitude": body.latitude, "longitude": body.longitude}


@router.get("/locations")
def list_locations(db: DB):
    return {"shops": [{"id": s.id, "name": s.name, "latitude": float(s.latitude) if s.latitude is not None else None,
                       "longitude": float(s.longitude) if s.longitude is not None else None} for s in db.scalars(select(Shop))],
            "hostels": [{"id": h.id, "name": h.name, "latitude": float(h.latitude) if h.latitude is not None else None,
                         "longitude": float(h.longitude) if h.longitude is not None else None}
                        for h in db.scalars(select(Hostel).order_by(Hostel.sort_order))]}


class GeocodeIn(BaseModel):
    apply: bool = False
    only_missing: bool = True
    area_hint: str = Field(default="", max_length=200)  # e.g. the university name, to improve matches


@router.post("/geocode")
def geocode_all(body: GeocodeIn, admin: CurrentUser, db: DB):
    """Ask Google where the shops and hostels are. By default this only PREVIEWS the results.
    Check them on a map, then call again with apply=true (or set exact points by hand)."""
    try:
        maps = get_maps()
    except MapsError:
        raise HTTPException(503, "Google Maps is not set up. Add GOOGLE_MAPS_API_KEY, or enter locations by hand.")
    out = []
    targets = [("shop", s.id, f"{s.name}, {s.location or ''}", s) for s in db.scalars(select(Shop))] + \
              [("hostel", h.id, h.name, h) for h in db.scalars(select(Hostel))]
    for kind, id_, name, obj in targets:
        if body.only_missing and obj.latitude is not None:
            continue
        q = ", ".join(x for x in (name, body.area_hint, "Ghana") if x)
        try:
            found = maps.geocode(q)
        except MapsError:
            found = None
        out.append({"type": kind, "id": id_, "name": name, "query": q,
                    "latitude": found[0] if found else None, "longitude": found[1] if found else None,
                    "found": bool(found), "applied": bool(found and body.apply)})
        if found and body.apply:
            obj.latitude, obj.longitude = found
    if body.apply:
        audit(db, admin.id, "geocode.apply", None, {"count": sum(1 for o in out if o["applied"])})
    db.commit()
    return out


# ---- unlisted item requests across all shops ----
@router.get("/requests")
def all_requests(db: DB, status: str | None = None):
    q = select(ProductRequest)
    if status:
        try:
            q = q.where(ProductRequest.status == RequestStatus(status))
        except ValueError:
            raise HTTPException(422, "Unknown status.")
    rows = db.scalars(q.order_by(ProductRequest.id.desc()).limit(200)).all()
    return [{"id": r.id, "shop_id": r.shop_id, "user_id": r.user_id, "student": db.get(User, r.user_id).full_name, "name": r.name, "description": r.description,
             "brand": r.brand, "quantity": r.quantity, "image_url": r.image_url, "status": r.status.value,
             "confirmed_unit_price": f(r.confirmed_unit_price), "order_id": r.order_id} for r in rows]


@router.post("/requests/{rid}/respond")
def admin_respond(rid: int, body: dict, admin: CurrentUser, db: DB):
    from .shop import RespondIn, respond
    r = db.get(ProductRequest, rid)
    if not r:
        raise HTTPException(404, "Request not found.")
    return respond(rid, RespondIn(**body), admin, db, r.shop_id)


@router.put("/universities/{uid}")
def rename_university(uid: int, body: NameIn, admin: CurrentUser, db: DB):
    u = db.get(University, uid)
    if not u:
        raise HTTPException(404, "University not found.")
    u.name = body.name
    audit(db, admin.id, "university.rename", f"university:{uid}", {"name": body.name})
    db.commit()
    return {"id": u.id, "name": u.name}


@router.get("/orders/{oid}")
def admin_order(oid: int, db: DB):
    from ..serializers import order_out
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found.")
    out = order_out(o)
    u = db.get(User, o.user_id)
    out["customer"] = {"name": u.full_name, "phone": u.phone}
    return out


@router.get("/shops/{sid}/staff")
def shop_staff(sid: int, db: DB):
    rows = db.scalars(select(User).join(ShopStaff, ShopStaff.user_id == User.id).where(ShopStaff.shop_id == sid))
    return [_user_out(u) for u in rows]


@router.get("/riders")
def list_riders(db: DB):
    rows = db.scalars(select(Rider)).all()
    return [{"id": r.user_id, "name": r.user.full_name, "phone": r.user.phone, "is_active": r.user.is_active,
             "campus_id": r.campus_id, "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None} for r in rows]


@router.get("/orders/{oid}/tracking")
def admin_tracking(oid: int, db: DB):
    from .delivery import build_tracking
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found.")
    return build_tracking(db, o)
