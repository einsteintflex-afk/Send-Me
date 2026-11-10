import hashlib
import hmac
import json
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_sendme.db"
os.environ["PAYSTACK_SECRET_KEY"] = "sk_test_unit"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ENV"] = "test"
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "10000"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import (Campus, Category, Product, ProductVariant, Rider, Role, Shop, ShopStaff, University, User,
                        DeliveryPricing)
from app.security import hash_password
from app.seed import seed
from app.services import payments as psvc


class FakeProvider:
    """Stands in for Paystack. Tests set .results[ref] to control verification."""
    results: dict = {}
    initialized: dict = {}

    def initialize(self, *, email, amount_pesewas, reference, callback_url, metadata):
        FakeProvider.initialized[reference] = amount_pesewas
        return {"authorization_url": f"https://checkout.test/{reference}", "access_code": "ac_" + reference}

    def verify(self, reference):
        if reference in FakeProvider.results:
            return FakeProvider.results[reference]
        return {"status": "abandoned", "amount": FakeProvider.initialized.get(reference), "currency": "GHS"}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    FakeProvider.results, FakeProvider.initialized = {}, {}
    psvc.set_provider_factory(FakeProvider)
    with SessionLocal() as db:
        seed(db, "Test University")
        shop = db.scalar(select(Shop))
        cat = lambda s: db.scalar(select(Category).where(Category.slug == s))
        db.add_all([
            Product(shop_id=shop.id, category_id=cat("drinks").id, name="Bel Malt Original", price=7),
            Product(shop_id=shop.id, category_id=cat("drinks").id, name="Water", price=None),  # no price supplied
            Product(shop_id=shop.id, category_id=cat("noodles").id, name="Indomie", price=5, stock_qty=3),
            Product(shop_id=shop.id, category_id=cat("drinks").id, name="Bullet Energy", price=9,
                    availability="unavailable"),
        ])
        coke = Product(shop_id=shop.id, category_id=cat("drinks").id, name="Coca-Cola", price=None)
        coke.variants = [ProductVariant(name="Small", price=4), ProductVariant(name="1 litre", price=12)]
        db.add(coke)
        db.add(User(email="admin@x.com", phone="+233200000001", full_name="Admin", role=Role.super_admin,
                    password_hash=hash_password("adminpass1"), email_verified=True))
        for role, em, ph in ((Role.shop_admin, "shop@x.com", "+233200000002"), (Role.shop_staff, "staff@x.com", "+233200000003")):
            u = User(email=em, phone=ph, full_name=em, role=role, password_hash=hash_password("shoppass1"))
            db.add(u)
            db.flush()
            db.add(ShopStaff(user_id=u.id, shop_id=shop.id))
        rd = User(email="rider@x.com", phone="+233200000004", full_name="Kojo Rider", role=Role.rider,
                  password_hash=hash_password("riderpass1"))
        db.add(rd)
        db.flush()
        campus = db.scalar(select(Campus))
        db.add(Rider(user_id=rd.id, campus_id=campus.id))
        db.commit()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, ident, pw):
    r = client.post("/auth/login", json={"identifier": ident, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def admin(client):
    return login(client, "admin@x.com", "adminpass1")


@pytest.fixture
def shop_h(client):
    return login(client, "shop@x.com", "shoppass1")


@pytest.fixture
def staff_h(client):
    return login(client, "staff@x.com", "shoppass1")


@pytest.fixture
def rider_h(client):
    return login(client, "rider@x.com", "riderpass1")


def register(client, email="ama@x.com", phone="024 123 4567"):
    uni = client.get("/universities").json()[0]["id"]
    r = client.post("/auth/register", json={"full_name": "Ama Mensah", "phone": phone, "email": email,
                                            "password": "password123", "university_id": uni, "hostel": "Test Hall",
                                            "block": "A", "room": "204"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def student(client):
    return register(client)


@pytest.fixture
def student2(client):
    return register(client, "kofi@x.com", "055 000 1111")


@pytest.fixture
def shop_id():
    with SessionLocal() as db:
        return db.scalar(select(Shop)).id


@pytest.fixture
def fee_set(client, admin):
    assert client.put("/admin/delivery-pricing", headers=admin, json={"fee": "3.00"}).status_code == 200


def pid(client, name):
    items = client.get("/products", params={"q": name}).json()["items"]
    return next(i for i in items if i["name"] == name)["id"]


def sign(body: dict):
    raw = json.dumps(body).encode()
    return raw, hmac.new(b"sk_test_unit", raw, hashlib.sha512).hexdigest()


def place_order(client, student, shop_id, fee=True):
    """Add 2 Bel Malt (GH₵7 each) and checkout. Returns order json."""
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original"), "quantity": 2})
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    r = client.post("/checkout", headers=student, json={"address_id": addr}, )
    assert r.status_code == 201, r.text
    return r.json()


def pay_order(client, student, order_id, amount_override=None):
    ref = client.post(f"/orders/{order_id}/pay", headers=student).json()["reference"]
    amt = amount_override if amount_override is not None else FakeProvider.initialized[ref]
    FakeProvider.results[ref] = {"status": "success", "amount": amt, "currency": "GHS", "channel": "mobile_money"}
    return ref
