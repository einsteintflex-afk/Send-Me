import csv
from .conftest import FakeProvider, login, pay_order, pid, place_order


def paid_order(client, student, shop_id):
    o = place_order(client, student, shop_id)
    ref = pay_order(client, student, o["id"])
    client.post(f"/payments/verify/{ref}", headers=student)
    return o["id"]


def test_full_journey(client, student, shop_id, fee_set, shop_h, rider_h, admin):
    oid = paid_order(client, student, shop_id)
    riders = client.get("/shop/riders", headers=shop_h).json()
    assert [r["name"] for r in riders] == ["Kojo Rider"]
    # exact statuses and order of workflow
    assert client.post(f"/shop/orders/{oid}/status", headers=shop_h, json={"status": "Shopping"}).status_code == 409
    for st in ("Accepted", "Shopping"):
        assert client.post(f"/shop/orders/{oid}/status", headers=shop_h, json={"status": st}).json()["status"] == st
    # rider details stay empty until assigned
    assert client.get(f"/orders/{oid}", headers=student).json()["rider"] is None
    assert client.post(f"/shop/orders/{oid}/status", headers=shop_h, json={"status": "On the Way"}).status_code == 409
    assert client.post(f"/shop/orders/{oid}/assign", headers=shop_h, json={"rider_id": riders[0]["id"]}).status_code == 200
    assert client.get(f"/orders/{oid}", headers=student).json()["rider"]["name"] == "Kojo Rider"
    assert client.post(f"/rider/deliveries/{oid}/pickup", headers=rider_h).status_code == 409  # not accepted yet
    assert client.post(f"/rider/deliveries/{oid}/accept", headers=rider_h).status_code == 200
    assert client.post(f"/rider/deliveries/{oid}/pickup", headers=rider_h).json()["status"] == "On the Way"
    assert client.post(f"/rider/deliveries/{oid}/failed", headers=rider_h, json={"reason": "Nobody at room"}).status_code == 200
    assert client.post(f"/rider/deliveries/{oid}/delivered", headers=rider_h).json()["status"] == "Delivered"
    o = client.get(f"/orders/{oid}", headers=student).json()
    assert [t["status"] for t in o["timeline"]][-4:] == ["Accepted", "Shopping", "On the Way", "Delivered"]
    assert client.get("/orders", headers=student).json()[0]["status"] == "Delivered"
    kinds = {n["kind"] for n in client.get("/notifications", headers=student).json()}
    assert {"order_confirmed", "order_accepted", "order_preparing", "rider_assigned", "order_dispatched", "order_delivered", "delivery_failed"} <= kinds
    assert client.post(f"/orders/{oid}/review", headers=student, json={"rating": 5}).status_code == 201
    assert client.get("/admin/reports/summary", headers=admin).json()["revenue"] == 17.0
    # closed orders cannot change
    assert client.post(f"/shop/orders/{oid}/status", headers=shop_h, json={"status": "Cancelled"}).status_code == 409


def test_cancellation_rules(client, student, shop_id, fee_set, shop_h):
    oid = paid_order(client, student, shop_id)
    c = client.post(f"/orders/{oid}/cancel", headers=student).json()
    assert c["status"] == "Cancelled" and c["payment_status"] == "refund_pending"
    oid2 = paid_order(client, student, shop_id)
    client.post(f"/shop/orders/{oid2}/status", headers=shop_h, json={"status": "Accepted"})
    assert client.post(f"/orders/{oid2}/cancel", headers=student).status_code == 409  # student can't cancel after acceptance
    assert client.post(f"/shop/orders/{oid2}/status", headers=shop_h, json={"status": "Cancelled", "note": "Out of stock"}).status_code == 200


def test_cancel_unpaid_order(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    assert client.post(f"/orders/{o['id']}/cancel", headers=student).json()["payment_status"] == "abandoned"


def test_unlisted_request_before_checkout(client, student, shop_id, fee_set, shop_h):
    r = client.post("/cart/requests", headers=student, json={"shop_id": shop_id, "name": "A4 notebook", "quantity": 2}).json()
    req = r["requests"][0]
    assert req["unit_price"] is None and r["pending_confirmation"] and r["subtotal"] == 0
    listed = client.get("/shop/requests", headers=shop_h).json()
    assert listed[0]["name"] == "A4 notebook"
    client.post(f"/shop/requests/{listed[0]['id']}/respond", headers=shop_h, json={"accept": True, "unit_price": "6.50"})
    cart = client.get("/cart", headers=student).json()
    assert cart["requests"][0]["unit_price"] == 6.5 and cart["subtotal"] == 13.0
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    o = client.post("/checkout", headers=student, json={"address_id": addr}).json()
    assert o["total"] == 16.0 and o["items"][0]["is_request"] is True
    assert "request_priced" in [n["kind"] for n in client.get("/notifications", headers=student).json()]


def test_unlisted_request_price_approval_after_order(client, student, shop_id, fee_set, shop_h):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original")})
    client.post("/cart/requests", headers=student, json={"shop_id": shop_id, "name": "Plain notebook"})
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    o = client.post("/checkout", headers=student, json={"address_id": addr}).json()
    item = next(i for i in o["items"] if i["is_request"])
    assert item["unit_price"] is None and item["needs_confirmation"] and o["total"] == 10.0  # charged: 7 + 3 fee only
    ref = pay_order(client, student, o["id"])
    client.post(f"/payments/verify/{ref}", headers=student)
    rid = item["request_id"]
    client.post(f"/shop/requests/{rid}/respond", headers=shop_h, json={"accept": True, "unit_price": "8"})
    # nothing extra charged until the student approves
    assert client.get(f"/orders/{o['id']}", headers=student).json()["total"] == 10.0
    pay = client.post(f"/orders/{o['id']}/requests/{rid}/approve", headers=student).json()
    assert pay["amount"] == 8.0
    FakeProvider.results[pay["reference"]] = {"status": "success", "amount": 800, "currency": "GHS"}
    after = client.post(f"/payments/verify/{pay['reference']}", headers=student).json()["order"]
    assert after["total"] == 18.0 and after["subtotal"] == 15.0


def test_request_rejected_and_declined(client, student, shop_id, shop_h):
    client.post("/cart/requests", headers=student, json={"shop_id": shop_id, "name": "Unobtainium"})
    rid = client.get("/shop/requests", headers=shop_h).json()[0]["id"]
    client.post(f"/shop/requests/{rid}/respond", headers=shop_h, json={"accept": False})
    assert client.get("/cart", headers=student).json()["requests"][0]["status"] == "rejected"
    assert client.post(f"/shop/requests/{rid}/respond", headers=shop_h, json={"accept": True, "unit_price": "1"}).status_code == 409
    assert client.post(f"/shop/requests/{rid}/respond", headers=shop_h, json={"accept": True}).status_code in (409, 422)


def test_request_needs_price_when_accepting(client, student, shop_id, shop_h):
    client.post("/cart/requests", headers=student, json={"shop_id": shop_id, "name": "Thing"})
    rid = client.get("/shop/requests", headers=shop_h).json()[0]["id"]
    assert client.post(f"/shop/requests/{rid}/respond", headers=shop_h, json={"accept": True}).status_code == 422


def test_request_image_upload_validation(client, student):
    assert client.post("/cart/requests/image", headers=student, files={"file": ("a.png", b"not an image", "image/png")}).status_code == 415
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    r = client.post("/cart/requests/image", headers=student, files={"file": ("a.png", png, "image/png")})
    assert r.status_code == 200 and r.json()["image_url"].startswith("/uploads/requests/")


# ---- permissions ----
def test_role_boundaries(client, student, shop_h, rider_h, admin, shop_id, fee_set):
    oid = paid_order(client, student, shop_id)
    assert client.get("/shop/orders", headers=student).status_code == 403
    assert client.get("/admin/users", headers=shop_h).status_code == 403
    assert client.get("/admin/users", headers=student).status_code == 403
    assert client.get("/rider/deliveries", headers=student).status_code == 403
    assert client.get("/cart", headers=shop_h).status_code == 403
    assert client.get("/rider/deliveries", headers=rider_h).json() == []
    assert client.get(f"/rider/deliveries/{oid}", headers=rider_h).status_code == 404  # not assigned to this rider
    assert client.get("/shop/overview", headers=admin).status_code == 400  # admin must name a shop
    assert client.get(f"/shop/overview?shop_id={shop_id}", headers=admin).status_code == 200


def test_shop_cannot_touch_other_shop(client, shop_h, admin, shop_id):
    camp = client.get("/universities").json()[0]["campuses"][0]["id"]
    other = client.post("/admin/shops", headers=admin, json={"campus_id": camp, "name": "Other Shop", "slug": "other-shop"}).json()["id"]
    assert client.get(f"/shop/orders?shop_id={other}", headers=shop_h).status_code == 403
    client.post(f"/admin/shops/{other}/staff", headers=admin, json={"full_name": "Other Boss", "email": "o@x.com",
                "phone": "0200000009", "password": "otherpass1", "role": "shop_admin"})
    oh = login(client, "o@x.com", "otherpass1")
    assert client.get("/shop/products", headers=oh).json() == []  # only its own (empty) inventory
    pid_ = pid(client, "Indomie")
    assert client.patch(f"/shop/products/{pid_}", headers=oh, json={"price": "1"}).status_code == 404


# ---- shop management ----
def test_product_management(client, shop_h):
    body = {"name": "Milo", "category": "breakfast", "price": "25.50", "variants": [{"name": "Small tin", "price": "12"}]}
    p = client.post("/shop/products", headers=shop_h, json=body).json()
    assert p["price"] == 25.5 and p["variants"][0]["name"] == "Small tin"
    assert client.post("/shop/products", headers=shop_h, json=body).status_code == 409
    assert client.patch(f"/shop/products/{p['id']}", headers=shop_h, json={"availability": "unavailable"}).json()["availability"] == "unavailable"
    assert client.put(f"/shop/products/{p['id']}", headers=shop_h, json={**body, "price": "26", "variants": []}).json()["price"] == 26.0
    assert client.delete(f"/shop/products/{p['id']}", headers=shop_h).status_code == 204
    assert client.get(f"/products/{p['id']}").status_code == 404
    assert client.post("/shop/products", headers=shop_h, json={**body, "name": "X", "category": "nope"}).status_code == 422


def test_low_stock_alert_only_when_configured(client, shop_h, shop_id):
    client.post("/shop/products", headers=shop_h, json={"name": "Pens", "category": "stationery", "price": "2", "stock_qty": 2, "low_stock_threshold": 5})
    ov = client.get("/shop/overview", headers=shop_h).json()
    assert [x["name"] for x in ov["low_stock"]] == ["Pens"]


def test_shop_settings(client, shop_h):
    s = client.patch("/shop/settings", headers=shop_h, json={"phones": ["+233200000099"], "delivery_estimate_minutes": 30}).json()
    assert s["phones"] == ["+233200000099"] and s["location"] == "Opposite R Block"


def test_estimated_arrival_only_when_configured(client, student, shop_id, fee_set, shop_h):
    oid = paid_order(client, student, shop_id)
    assert client.get(f"/orders/{oid}", headers=student).json()["estimated_arrival"] is None
    client.patch("/shop/settings", headers=shop_h, json={"delivery_estimate_minutes": 30})
    oid2 = paid_order(client, student, shop_id)
    assert client.get(f"/orders/{oid2}", headers=student).json()["estimated_arrival"] is not None


def test_closed_shop_blocks_checkout(client, student, shop_h, fee_set):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original")})
    client.patch("/shop/settings", headers=shop_h, json={"accepting_orders": False})
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    assert client.post("/checkout", headers=student, json={"address_id": addr}).status_code == 409


# ---- admin ----
def test_admin_management_and_audit(client, admin):
    assert client.post("/admin/riders", headers=admin, json={"full_name": "New Rider", "email": "r2@x.com", "phone": "0551112222",
                       "password": "riderpass2", "campus_id": client.get("/universities").json()[0]["campuses"][0]["id"]}).status_code == 201
    assert login(client, "r2@x.com", "riderpass2")
    assert any(u["full_name"] == "New Rider" for u in client.get("/admin/users?role=rider", headers=admin).json())
    assert client.post("/admin/categories", headers=admin, json={"slug": "gadgets", "name": "Gadgets"}).status_code == 201
    assert client.post("/admin/promotions", headers=admin, json={"title": "Welcome"}).status_code == 201
    assert client.get("/promotions").json()[0]["title"] == "Welcome"
    assert {a["action"] for a in client.get("/admin/audit", headers=admin).json()} >= {"rider.create", "category.create"}
    assert client.post("/admin/users/1/active", headers=admin, json={"is_active": False}).status_code in (200, 409)


def test_rider_other_campus_rejected(client, admin, shop_h, student, shop_id, fee_set):
    uni = client.get("/universities").json()[0]["id"]
    camp2 = client.post("/admin/campuses", headers=admin, json={"university_id": uni, "name": "Annex"}).json()["id"]
    rid = client.post("/admin/riders", headers=admin, json={"full_name": "Far Rider", "email": "far@x.com", "phone": "0552223333",
                      "password": "riderpass3", "campus_id": camp2}).json()["id"]
    oid = paid_order(client, student, shop_id)
    assert client.post(f"/shop/orders/{oid}/assign", headers=shop_h, json={"rider_id": rid}).status_code == 409


def test_rate_limit(client, monkeypatch):
    from app.config import get_settings
    import app.main as m
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_minute", 3)
    m._hits.clear()
    codes = [client.post("/auth/login", json={"identifier": "a@b.com", "password": "xxxxxxxx"}).status_code for _ in range(5)]
    assert codes[-1] == 429
    m._hits.clear()


def test_catalog_import(tmp_path):
    from app.db import SessionLocal
    from app.scripts.import_catalog import run
    f = tmp_path / "c.csv"
    with open(f, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "category", "price", "variant", "availability", "stock_qty", "description"])
        w.writerow(["Milo", "breakfast", "", "", "", "", ""])
        w.writerow(["Sprite", "drinks", "5", "Small", "", "", ""])
        w.writerow(["Sprite", "drinks", "9", "1 litre", "", "", ""])
    with SessionLocal() as db:
        res = run(db, str(f), "ugmsa-mini-mart")
    assert res["committed"] and res["created_products"] == 2 and res["variants"] == 2 and res["without_price"] == ["Milo"]
    bad = tmp_path / "b.csv"
    bad.write_text("name,category,price,variant,availability,stock_qty,description\nX,nope,1,,,,\nY,drinks,abc,,,,\n")
    with SessionLocal() as db:
        res = run(db, str(bad), "ugmsa-mini-mart")
    assert not res["committed"] and len(res["errors"]) == 2


def test_health_and_security_headers(client):
    r = client.get("/health")
    assert r.json()["ok"] and r.headers["x-content-type-options"] == "nosniff"


def test_real_catalog_imports_cleanly_and_exactly():
    import os
    from sqlalchemy import select as sel
    from app.db import SessionLocal
    from app.models import Product, Shop
    from app.scripts.import_catalog import run
    path = os.path.join(os.path.dirname(__file__), "..", "data", "ugmsa_catalog.csv")
    with SessionLocal() as db:
        res = run(db, path, "ugmsa-mini-mart")
        assert res["errors"] == [] and res["committed"] and res["created_products"] == 86  # 2 of the 88 already exist in the test fixture and are updated
        by = {p.name: p for p in db.scalars(sel(Product))}
        assert float(by["Coca-cola(1 litre)"].price) == 19.0 and by["Coca-cola(1 litre)"].stock_qty is None
        assert float(by["Basmati Rice"].price) == 480.0 and by["Bic Pen"].stock_qty == 325
        assert by["Malta Guinness"].availability.value == "unavailable"
        assert "Mom’s margic sardine" in by and "Indomie (Hungry man size)" in by
        assert db.scalar(sel(Shop)).phones == ["+233576966929", "+233546504543"]
