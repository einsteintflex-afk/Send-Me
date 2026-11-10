from sqlalchemy import select
from app.db import SessionLocal
from app.models import Product, Payment, Order
from .conftest import FakeProvider, pay_order, pid, place_order, sign


def test_checkout_requires_delivery_fee(client, student, shop_id):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original")})
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    r = client.post("/checkout", headers=student, json={"address_id": addr})
    assert r.status_code == 409 and "delivery fee" in r.json()["detail"]


def test_checkout_totals_and_snapshot(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    assert o["subtotal"] == 14.0 and o["delivery_fee"] == 3.0 and o["total"] == 17.0
    assert o["status"] == "Pending" and o["payment_status"] == "awaiting_payment" and o["number"] is None
    # later price change must not alter the order
    with SessionLocal() as db:
        db.scalar(select(Product).where(Product.name == "Bel Malt Original")).price = 99
        db.commit()
    assert client.get(f"/orders/{o['id']}", headers=student).json()["items"][0]["unit_price"] == 7.0
    assert client.get("/cart", headers=student).json()["items"] == []


def test_checkout_idempotent(client, student, shop_id, fee_set):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original")})
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    h = {**student, "Idempotency-Key": "abc123"}
    a = client.post("/checkout", headers=h, json={"address_id": addr}).json()
    b = client.post("/checkout", headers=h, json={"address_id": addr}).json()
    assert a["id"] == b["id"]
    assert len(client.get("/orders", headers=student).json()) == 1


def test_checkout_validates_destination(client, student, fee_set):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original")})
    assert client.post("/checkout", headers=student, json={"address_id": 9999}).status_code == 422


def test_empty_cart_rejected(client, student, fee_set):
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    assert client.post("/checkout", headers=student, json={"address_id": addr}).status_code == 422


def test_payment_success_flow(client, student, shop_id, fee_set, shop_h):
    o = place_order(client, student, shop_id)
    # shop cannot see unpaid orders
    assert client.get("/shop/orders", headers=shop_h).json() == []
    ref = pay_order(client, student, o["id"])
    assert FakeProvider.initialized[ref] == 1700  # pesewas
    r = client.post(f"/payments/verify/{ref}", headers=student).json()
    assert r["payment_status"] == "success"
    order = r["order"]
    assert order["payment_status"] == "paid" and order["number"].startswith("SM-") and order["number"].endswith("000001")
    assert len(client.get("/shop/orders", headers=shop_h).json()) == 1
    notes = [n["kind"] for n in client.get("/notifications", headers=student).json()]
    assert "order_confirmed" in notes


def test_unverified_payment_does_not_mark_paid(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    ref = client.post(f"/orders/{o['id']}/pay", headers=student).json()["reference"]
    r = client.post(f"/payments/verify/{ref}", headers=student).json()  # provider says abandoned
    assert r["payment_status"] == "abandoned" and r["order"]["payment_status"] == "abandoned"
    assert r["order"]["number"] is None


def test_failed_payment_and_retry(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    ref = client.post(f"/orders/{o['id']}/pay", headers=student).json()["reference"]
    FakeProvider.results[ref] = {"status": "failed", "amount": 1700, "currency": "GHS"}
    assert client.post(f"/payments/verify/{ref}", headers=student).json()["order"]["payment_status"] == "failed"
    ref2 = pay_order(client, student, o["id"])
    assert ref2 != ref
    assert client.post(f"/payments/verify/{ref2}", headers=student).json()["order"]["payment_status"] == "paid"


def test_amount_mismatch_rejected(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    ref = pay_order(client, student, o["id"], amount_override=100)
    r = client.post(f"/payments/verify/{ref}", headers=student).json()
    assert r["payment_status"] == "failed" and r["order"]["payment_status"] != "paid"


def test_duplicate_pay_click_reuses_payment(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    a = client.post(f"/orders/{o['id']}/pay", headers=student).json()
    b = client.post(f"/orders/{o['id']}/pay", headers=student).json()
    assert a["reference"] == b["reference"]
    with SessionLocal() as db:
        assert len(db.scalars(select(Payment)).all()) == 1


def test_cannot_pay_twice_and_no_second_number(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    ref = pay_order(client, student, o["id"])
    client.post(f"/payments/verify/{ref}", headers=student)
    client.post(f"/payments/verify/{ref}", headers=student)  # repeat verify is harmless
    assert client.post(f"/orders/{o['id']}/pay", headers=student).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(Order)).number == "SM-%d-000001" % __import__("datetime").datetime.now().year


def test_webhook_signature_and_duplicates(client, student, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    ref = pay_order(client, student, o["id"])
    body = {"event": "charge.success", "data": {"reference": ref}}
    raw, sig = sign(body)
    assert client.post("/payments/webhook/paystack", content=raw, headers={"x-paystack-signature": "bad"}).status_code == 401
    assert client.post("/payments/webhook/paystack", content=raw).status_code == 401
    assert client.post("/payments/webhook/paystack", content=raw, headers={"x-paystack-signature": sig}).json()["result"] == "ok"
    assert client.post("/payments/webhook/paystack", content=raw, headers={"x-paystack-signature": sig}).json()["result"] == "duplicate"
    order = client.get(f"/orders/{o['id']}", headers=student).json()
    assert order["payment_status"] == "paid"
    with SessionLocal() as db:
        assert db.scalar(select(Product).where(Product.name == "Indomie")).stock_qty == 3  # untouched


def test_stock_decremented_after_payment(client, student, shop_id, fee_set):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Indomie"), "quantity": 2})
    addr = client.get("/auth/addresses", headers=student).json()[0]["id"]
    o = client.post("/checkout", headers=student, json={"address_id": addr}).json()
    ref = pay_order(client, student, o["id"])
    client.post(f"/payments/verify/{ref}", headers=student)
    with SessionLocal() as db:
        assert db.scalar(select(Product).where(Product.name == "Indomie")).stock_qty == 1


def test_student_cannot_see_others_orders(client, student, student2, shop_id, fee_set):
    o = place_order(client, student, shop_id)
    assert client.get(f"/orders/{o['id']}", headers=student2).status_code == 404
    assert client.post(f"/orders/{o['id']}/pay", headers=student2).status_code == 404
    assert client.get("/orders", headers=student2).json() == []


def test_unconfigured_payments_return_503(client, student, shop_id, fee_set, monkeypatch):
    from app.services import payments
    from app.config import get_settings
    o = place_order(client, student, shop_id)
    payments.set_provider_factory(payments.PaystackProvider)
    monkeypatch.setattr(get_settings(), "paystack_secret_key", "")
    assert client.post(f"/orders/{o['id']}/pay", headers=student).status_code == 503
