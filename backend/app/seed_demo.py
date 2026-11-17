"""DEVELOPMENT ONLY demo data so every screen has something to show.
Everything here is a placeholder: accounts, passwords, delivery rate and map points are NOT real business data.
Refuses to run when ENV=production.   Run: python -m app.seed_demo"""
import os
from sqlalchemy import select
from .config import get_settings
from .db import SessionLocal
from .models import Campus, Hostel, Rider, Role, Shop, ShopStaff, SystemSetting, University, User
from .scripts.import_catalog import run as import_catalog
from .security import hash_password
from .seed import seed

DEMO_PASSWORD = "demo12345"  # development only
DEMO_ACCOUNTS = [
    ("admin@sendme.local", "0200000001", "Demo Administrator", Role.super_admin),
    ("shop@sendme.local", "0200000002", "Demo Shop Manager", Role.shop_admin),
    ("student@sendme.local", "0200000003", "Demo Student", Role.student),
    (None, "0200000004", "Demo Rider", Role.rider),
]
# Placeholder points near one spot so the maps have something to draw. Not surveyed locations.
DEMO_POINTS = {"shop": (5.6500, -0.1870), "D block(College of health sciences student hostel)": (5.6512, -0.1862),
               "B- block": (5.6508, -0.1881), "R-block": (5.6503, -0.1873), "BQ": (5.6490, -0.1860),
               "M-block": (5.6495, -0.1885), "N- block": (5.6518, -0.1875)}


def main():
    if get_settings().env == "production":
        raise SystemExit("Refusing to load demo data in production.")
    with SessionLocal() as db:
        seed(db, "Demo University (rename in Admin)")
        campus = db.scalar(select(Campus))
        shop = db.scalar(select(Shop).where(Shop.slug == "ugmsa-mini-mart"))
        shop.latitude, shop.longitude = DEMO_POINTS["shop"]
        shop.delivery_estimate_minutes = shop.delivery_estimate_minutes or 30
        for h in db.scalars(select(Hostel)):
            if h.name in DEMO_POINTS and h.latitude is None:
                h.latitude, h.longitude = DEMO_POINTS[h.name]
        for email, phone, name, role in DEMO_ACCOUNTS:
            ph = "+233" + phone[1:]
            if db.scalar(select(User).where(User.phone == ph)):
                continue
            u = User(email=email, phone=ph, full_name=name, role=role, password_hash=hash_password(DEMO_PASSWORD),
                     email_verified=True)
            db.add(u)
            db.flush()
            if role == Role.shop_admin:
                db.add(ShopStaff(user_id=u.id, shop_id=shop.id))
            if role == Role.rider:
                db.add(Rider(user_id=u.id, campus_id=campus.id))
            if role == Role.student:
                from .models import Address, StudentProfile
                uni = db.scalar(select(University))
                db.add(StudentProfile(user_id=u.id, university_id=uni.id))
                h = db.scalar(select(Hostel).where(Hostel.name == "R-block"))
                db.add(Address(user_id=u.id, campus_id=campus.id, kind="hostel", label="R-block", hostel="R-block",
                               hostel_id=h.id, room="A1", is_default=True))
        if not db.get(SystemSetting, "delivery_distance"):
            db.add(SystemSetting(key="delivery_distance",
                                 value={"rate_per_km": "5.00", "min_fee": "3.00", "travel_mode": "WALK"}))
        db.merge(SystemSetting(key="demo_mode", value={"on": True,
                "note": "Placeholder delivery rate, map points and accounts. Replace before launch."}))
        db.commit()
        path = os.path.join(os.path.dirname(__file__), "..", "data", "ugmsa_catalog.csv")
        res = import_catalog(db, path, "ugmsa-mini-mart")
        print("Catalogue:", {k: res[k] for k in ("created_products", "errors", "committed")})
    print("Demo data ready. Demo password for every demo account (development only):", DEMO_PASSWORD)


if __name__ == "__main__":
    main()
