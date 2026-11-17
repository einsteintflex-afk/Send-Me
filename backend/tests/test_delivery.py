from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Rider
from app.services import maps
from app.services.maps import MapsError
from .conftest import login, pay_order, pid, FakeProvider

# Test-only coordinates (not real campus locations).
SHOP = (5.6500, -0.1870)
HOSTEL_NEAR = (5.6510, -0.1870)  # about 111 m north


class FakeMaps:
    calls = 0
    meters = 800
    geo = {}

    def route_meters(self, *a):
        FakeMaps.calls += 1
        return FakeMaps.meters

    def geocode(self, q):
        return FakeMaps.geo.get(q.split(",")[0])


class NoMaps:
    def __init__(self):
        raise MapsError("no key")


def setup_locations(client, admin, shop_id):
    camp = client.get("/universities").json()[0]["campuses"][0]["id"]
    hostels = client.get(f"/campuses/{camp}/hostels").json()
    client.put(f"/admin/shops/{shop_id}/location", headers=admin, json={"latitude": SHOP[0], "longitude": SHOP[1]})
    return hostels


def student_with_hostel(client, hostel_name):
    uni = client.get("/universities").json()[0]["id"]
    r = client.post("/auth/register", json={"full_name": "Ama", "phone": "0241234567", "email": "ama@x.com",
                    "password": "password123", "university_id": uni, "hostel": hostel_name, "room": "B404"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def cart_one(client, h):
    client.post("/cart/items", headers=h, json={"product_id": pid(client, "Bel Malt Original"), "quantity": 2})
    return client.get("/auth/addresses", headers=h).json()[0]


def test_distance_pricing_with_google(client, admin, shop_id):
    maps.set_maps_factory(FakeMaps)
    FakeMaps.calls, FakeMaps.meters = 0, 800
    hostels = setup_locations(client, admin, shop_id)
    r_block = next(h for h in hostels if h["name"] == "R-block")
    client.put(f"/admin/hostels/{r_block['id']}/location", headers=admin, json={"latitude": HOSTEL_NEAR[0], "longitude": HOSTEL_NEAR[1]})
    assert client.put("/admin/delivery-distance", headers=admin, json={"rate_per_km": "4.00", "min_fee": "2.00"}).status_code == 200
    h = student_with_hostel(client, "r-BLOCK")  # matched case-insensitively to the supplied hostel
    addr = cart_one(client, h)
    assert addr["hostel_id"] == r_block["id"]
    q = client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": addr["id"]}).json()
    assert q == {"delivery_fee": 3.2, "distance_km": 0.8, "method": "google", "currency": "GHS", "approximate": False}
    client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": addr["id"]})
    assert FakeMaps.calls == 1  # second quote served from cache
    cart = client.get(f"/cart?address_id={addr['id']}", headers=h).json()
    assert cart["delivery_fee"] == 3.2 and cart["total"] == 17.2
    o = client.post("/checkout", headers=h, json={"address_id": addr["id"]}).json()
    assert o["delivery_fee"] == 3.2 and o["total"] == 17.2 and o["delivery_distance_km"] == 0.8 and o["delivery_method"] == "google"


def test_minimum_fee_applies(client, admin, shop_id):
    maps.set_maps_factory(FakeMaps)
    FakeMaps.meters = 100
    hostels = setup_locations(client, admin, shop_id)
    client.put(f"/admin/hostels/{hostels[2]['id']}/location", headers=admin, json={"latitude": HOSTEL_NEAR[0], "longitude": HOSTEL_NEAR[1]})
    client.put("/admin/delivery-distance", headers=admin, json={"rate_per_km": "4.00", "min_fee": "2.00"})
    h = student_with_hostel(client, "R-block")
    addr = cart_one(client, h)
    assert client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": addr["id"]}).json()["delivery_fee"] == 2.0


def test_straight_line_fallback_is_labelled_approximate(client, admin, shop_id):
    maps.set_maps_factory(NoMaps)
    hostels = setup_locations(client, admin, shop_id)
    client.put(f"/admin/hostels/{hostels[2]['id']}/location", headers=admin, json={"latitude": HOSTEL_NEAR[0], "longitude": HOSTEL_NEAR[1]})
    client.put("/admin/delivery-distance", headers=admin, json={"rate_per_km": "10.00"})
    h = student_with_hostel(client, "R-block")
    addr = cart_one(client, h)
    q = client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": addr["id"]}).json()
    assert q["method"] == "straight_line" and q["approximate"] is True and 0.10 < q["distance_km"] < 0.12
    assert q["delivery_fee"] == round(q["distance_km"] * 10, 2)


def test_no_coordinates_falls_back_to_flat_fee_or_blocks(client, admin, shop_id):
    maps.set_maps_factory(FakeMaps)
    client.put("/admin/delivery-distance", headers=admin, json={"rate_per_km": "4.00"})
    h = student_with_hostel(client, "R-block")
    addr = cart_one(client, h)
    assert client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": addr["id"]}).status_code == 409
    cart = client.get("/cart", headers=h).json()
    assert cart["delivery_needs_destination"] is True and cart["fee_configured"] is True
    client.put("/admin/delivery-pricing", headers=admin, json={"fee": "3.00"})
    q = client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": addr["id"]}).json()
    assert q["method"] == "flat" and q["delivery_fee"] == 3.0


def test_pickup_point_with_gps_coordinates(client, admin, shop_id):
    maps.set_maps_factory(FakeMaps)
    FakeMaps.meters = 500
    setup_locations(client, admin, shop_id)
    client.put("/admin/delivery-distance", headers=admin, json={"rate_per_km": "6.00"})
    h = student_with_hostel(client, "R-block")
    client.post("/cart/items", headers=h, json={"product_id": pid(client, "Bel Malt Original")})
    a = client.post("/auth/addresses", headers=h, json={"kind": "pickup_point", "label": "Gate", "place": "Main gate",
                    "latitude": 5.652, "longitude": -0.186}).json()
    assert client.post("/delivery/quote", headers=h, json={"shop_id": shop_id, "address_id": a["id"]}).json()["delivery_fee"] == 3.0


def test_geocode_previews_then_applies(client, admin, shop_id):
    maps.set_maps_factory(FakeMaps)
    FakeMaps.geo = {"R-block": (5.65, -0.18), "UGMSA Mini Mart": (5.651, -0.181)}
    prev = client.post("/admin/geocode", headers=admin, json={"area_hint": "Test University"}).json()
    assert any(p["name"] == "R-block" and p["found"] and not p["applied"] for p in prev)
    assert all(l["latitude"] is None for l in client.get("/admin/locations", headers=admin).json()["hostels"])
    client.post("/admin/geocode", headers=admin, json={"apply": True})
    locs = client.get("/admin/locations", headers=admin).json()
    assert next(h for h in locs["hostels"] if h["name"] == "R-block")["latitude"] == 5.65
    assert locs["shops"][0]["latitude"] == 5.651


def test_geocode_without_key_is_503_and_no_guess(client, admin):
    maps.set_maps_factory(NoMaps)
    assert client.post("/admin/geocode", headers=admin, json={}).status_code == 503
    assert all(h["latitude"] is None for h in client.get("/admin/locations", headers=admin).json()["hostels"])


# ---- tracking ----
def delivered_setup(client, admin, shop_id, shop_h, rider_h):
    client.put("/admin/delivery-pricing", headers=admin, json={"fee": "3.00"})
    h = student_with_hostel(client, "R-block")
    cart_one(client, h)
    addr = client.get("/auth/addresses", headers=h).json()[0]["id"]
    o = client.post("/checkout", headers=h, json={"address_id": addr}).json()
    ref = pay_order(client, h, o["id"])
    client.post(f"/payments/verify/{ref}", headers=h)
    rid = client.get("/shop/riders", headers=shop_h).json()[0]["id"]
    return h, o["id"], rid


def test_tracking_only_live_when_on_the_way(client, admin, shop_id, shop_h, rider_h):
    h, oid, rid = delivered_setup(client, admin, shop_id, shop_h, rider_h)
    hostels = setup_locations(client, admin, shop_id)
    client.put(f"/admin/hostels/{hostels[2]['id']}/location", headers=admin, json={"latitude": HOSTEL_NEAR[0], "longitude": HOSTEL_NEAR[1]})
    for st in ("Accepted", "Shopping"):
        client.post(f"/shop/orders/{oid}/status", headers=shop_h, json={"status": st})
    client.post(f"/shop/orders/{oid}/assign", headers=shop_h, json={"rider_id": rid})
    client.post("/rider/location", headers=rider_h, json={"lat": 5.6505, "lng": -0.187})
    t = client.get(f"/orders/{oid}/tracking", headers=h).json()
    assert t["live"] is False and t["rider_position"] is None  # position is hidden until On the Way
    assert t["rider"]["name"] == "Kojo Rider"
    client.post(f"/rider/deliveries/{oid}/accept", headers=rider_h)
    client.post(f"/rider/deliveries/{oid}/pickup", headers=rider_h)
    client.post("/rider/location", headers=rider_h, json={"lat": 5.6505, "lng": -0.187})
    t = client.get(f"/orders/{oid}/tracking", headers=h).json()
    assert t["live"] is True and t["rider_position"]["latitude"] == 5.6505 and t["rider_position"]["stale"] is False
    assert t["destination"]["latitude"] == HOSTEL_NEAR[0] and t["shop"]["latitude"] == SHOP[0]
    assert 0.04 < t["distance_to_destination_km"] < 0.07
    # stale detection
    with SessionLocal() as db:
        r = db.scalar(select(Rider))
        r.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()
    assert client.get(f"/orders/{oid}/tracking", headers=h).json()["rider_position"]["stale"] is True
    # generic order output never carries GPS
    assert "lat" not in client.get(f"/orders/{oid}", headers=h).json()["rider"]
    client.post(f"/rider/deliveries/{oid}/delivered", headers=rider_h)
    assert client.get(f"/orders/{oid}/tracking", headers=h).json()["rider_position"] is None  # sharing ends on delivery


def test_tracking_is_private(client, admin, shop_id, shop_h, rider_h):
    h, oid, rid = delivered_setup(client, admin, shop_id, shop_h, rider_h)
    uni = client.get("/universities").json()[0]["id"]
    other = client.post("/auth/register", json={"full_name": "Kofi", "phone": "0551110000", "email": "k@x.com", "password": "password123",
                        "university_id": uni, "hostel": "BQ", "room": "1"}).json()["access_token"]
    assert client.get(f"/orders/{oid}/tracking", headers={"Authorization": "Bearer " + other}).status_code == 404
    assert client.get(f"/orders/{oid}/tracking").status_code == 401
    assert client.get(f"/orders/{oid}/tracking", headers=rider_h).status_code == 403


# ---- unlisted item alerts ----
def test_request_notifies_shop_and_admin_who_can_price_quickly(client, student, shop_id, shop_h, admin):
    client.post("/cart/requests", headers=student, json={"shop_id": shop_id, "name": "Dettol soap", "brand": "Dettol", "quantity": 2})
    for h in (shop_h, admin):
        n = client.get("/notifications", headers=h).json()
        assert n and n[0]["kind"] == "request_new" and "Dettol soap" in n[0]["body"]
    rid = client.get("/admin/requests?status=submitted", headers=admin).json()[0]["id"]
    r = client.post(f"/admin/requests/{rid}/respond", headers=admin, json={"accept": True, "unit_price": "12.50"})
    assert r.status_code == 200 and r.json()["confirmed_unit_price"] == 12.5
    n = client.get("/notifications", headers=student).json()[0]
    assert n["kind"] == "request_priced" and "12.50" in n["body"]
    assert client.get("/cart", headers=student).json()["requests"][0]["unit_price"] == 12.5
    assert client.post(f"/admin/requests/{rid}/respond", headers=shop_h, json={"accept": False}).status_code == 403


# ---- riders without email ----
def test_rider_without_email_signs_in_with_phone(client, admin):
    camp = client.get("/universities").json()[0]["campuses"][0]["id"]
    r = client.post("/admin/riders", headers=admin, json={"full_name": "Sammy", "phone": "0264944652", "password": "sammypass1", "campus_id": camp})
    assert r.status_code == 201 and r.json()["email"] is None and r.json()["phone"] == "+233264944652"
    login_h = login(client, "0264944652", "sammypass1")
    assert client.get("/auth/me", headers=login_h).json()["role"] == "rider"
    # second rider without email is fine (NULL emails do not clash)
    assert client.post("/admin/riders", headers=admin, json={"full_name": "Other", "phone": "0201112222", "password": "otherpass1", "campus_id": camp}).status_code == 201
    # duplicate phone rejected
    assert client.post("/admin/riders", headers=admin, json={"full_name": "Dup", "phone": "0264944652", "password": "duppass123", "campus_id": camp}).status_code == 409
    # admin can reset the password since there is no email link
    uid = r.json()["id"]
    assert client.post(f"/admin/users/{uid}/password", headers=admin, json={"password": "newsammy123"}).status_code == 200
    assert login(client, "0264944652", "newsammy123")


def test_mock_payment_mode_needs_explicit_simulated_confirmation(client, student, shop_id, fee_set, monkeypatch):
    """With no Paystack key outside production, checkout is simulated and never auto-succeeds."""
    from app.config import get_settings
    from app.services import payments
    from .conftest import place_order
    monkeypatch.setattr(get_settings(), "paystack_secret_key", "")
    payments.set_provider_factory(None)
    assert client.get("/config").json()["payment_mode"] == "mock"
    o = place_order(client, student, shop_id)
    pay = client.post(f"/orders/{o['id']}/pay", headers=student).json()
    assert pay["authorization_url"].startswith("/#/pay/mock?reference=")
    v = client.post(f"/payments/verify/{pay['reference']}", headers=student).json()
    assert v["payment_status"] == "abandoned"  # clicking Pay alone does not succeed
    pay = client.post(f"/orders/{o['id']}/pay", headers=student).json()
    assert client.post(f"/dev/mock-pay/{pay['reference']}", headers=student, json={"outcome": "success"}).status_code == 200
    v = client.post(f"/payments/verify/{pay['reference']}", headers=student).json()
    assert v["payment_status"] == "success" and v["order"]["payment_status"] == "paid"
    monkeypatch.setattr(get_settings(), "env", "production")
    assert client.get("/config").json()["payment_mode"] == "unconfigured"
    assert client.post(f"/dev/mock-pay/{pay['reference']}", headers=student, json={"outcome": "success"}).status_code == 404


def test_integrations_and_popular(client, admin, student):
    i = client.get("/admin/integrations", headers=admin).json()
    assert i["payments"]["mode"] in ("mock", "test", "live") and i["launch_checklist"]
    assert client.get("/admin/integrations", headers=student).status_code == 403
    assert len(client.get("/products/popular").json()) >= 1
