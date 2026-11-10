from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select

from ..deps import DB, CurrentUser, SuperAdmin
from ..models import (AuditLog, Campus, Category, Complaint, DeliveryPricing, Order, OrderStatus, Payment,
                      PaymentStatus, Promotion, Review, Rider, Role, Shop, ShopStaff, SystemSetting, University, User)
from ..security import hash_password
from ..serializers import f, shop_out
from ..services.audit import audit
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


def _create_user(db, body: StaffIn, role: Role) -> User:
    phone = normalize_gh_phone(body.phone)
    if db.scalar(select(User).where(or_(User.email == body.email.lower(), User.phone == phone))):
        raise HTTPException(409, "An account with this email or phone number already exists.")
    u = User(email=body.email.lower(), phone=phone, full_name=body.full_name.strip(), role=role,
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


class RiderIn(StaffIn):
    campus_id: int
    role: Role = Role.rider


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
