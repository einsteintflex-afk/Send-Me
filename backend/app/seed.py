"""Creates reference data only: categories, first university/campus and UGMSA Mini Mart.
No prices, stock, phone numbers or riders are invented. Run: python -m app.seed"""
import os
from sqlalchemy import select
from .db import SessionLocal
from .models import Campus, Category, Hostel, Role, Shop, University, User
from .security import hash_password

# Exactly as supplied by the business. Edit via the admin API, not here, once live.
HOSTELS = [
    "D block(College of health sciences student hostel)", "B- block", "R-block", "BQ", "M-block", "N- block",
]
CATEGORIES = [
    ("drinks", "Drinks & Beverages"), ("snacks", "Snacks & Confectionery"), ("breakfast", "Breakfast & Cereals"),
    ("noodles", "Noodles & Quick Meals"), ("bread", "Bread & Bakery"), ("dairy", "Milk, Dairy & Eggs"),
    ("canned", "Canned Foods"), ("groceries", "Groceries & Staples"), ("personal-care", "Personal Care"),
    ("toiletries", "Toiletries"), ("household", "Household Products"), ("stationery", "Stationery"),
    ("apparel", "Clothing & Apparel"),
]


def seed(db, university_name: str | None = None):
    for i, (slug, name) in enumerate(CATEGORIES):
        if not db.scalar(select(Category).where(Category.slug == slug)):
            db.add(Category(slug=slug, name=name, sort_order=i))
    uname = university_name or os.getenv("SEED_UNIVERSITY", "University (set in admin)")
    uni = db.scalar(select(University).where(University.name == uname))
    if not uni:
        uni = University(name=uname)
        db.add(uni)
        db.flush()
    campus = db.scalar(select(Campus).where(Campus.university_id == uni.id))
    if not campus:
        campus = Campus(university_id=uni.id, name="Main Campus")
        db.add(campus)
        db.flush()
    for i, hname in enumerate(HOSTELS):
        if not db.scalar(select(Hostel).where(Hostel.campus_id == campus.id, Hostel.name == hname)):
            db.add(Hostel(campus_id=campus.id, name=hname, sort_order=i))
    if not db.scalar(select(Shop).where(Shop.slug == "ugmsa-mini-mart")):
        db.add(Shop(campus_id=campus.id, name="UGMSA Mini Mart", slug="ugmsa-mini-mart", location="Opposite R Block",
                    phones=[]))  # phone numbers must be entered by the shop or admin
    email, pw = os.getenv("SEED_ADMIN_EMAIL"), os.getenv("SEED_ADMIN_PASSWORD")
    if email and pw and not db.scalar(select(User).where(User.email == email.lower())):
        db.add(User(email=email.lower(), phone=os.getenv("SEED_ADMIN_PHONE", "+233000000000"), full_name="Super Admin",
                    password_hash=hash_password(pw), role=Role.super_admin, email_verified=True))
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as s:
        seed(s)
    print("Seed complete.")
