from app.services.notify import OUTBOX
from .conftest import login, register


def test_register_and_login(client):
    h = register(client)
    me = client.get("/auth/me", headers=h).json()
    assert me["phone"] == "+233241234567" and me["role"] == "student"
    assert login(client, "ama@x.com", "password123")
    assert login(client, "0241234567", "password123")  # phone login


def test_invalid_credentials_and_duplicates(client, student):
    assert client.post("/auth/login", json={"identifier": "ama@x.com", "password": "wrong-pass"}).status_code == 401
    uni = client.get("/universities").json()[0]["id"]
    dup = client.post("/auth/register", json={"full_name": "Dup", "phone": "0241234567", "email": "new@x.com",
                                              "password": "password123", "university_id": uni, "hostel": "H", "room": "1"})
    assert dup.status_code == 409


def test_bad_phone_and_short_password(client):
    uni = client.get("/universities").json()[0]["id"]
    base = {"full_name": "Ama", "email": "z@x.com", "university_id": uni, "hostel": "H", "room": "1"}
    assert client.post("/auth/register", json={**base, "phone": "12345", "password": "password123"}).status_code == 422
    assert client.post("/auth/register", json={**base, "phone": "0241234567", "password": "short"}).status_code == 422


def test_password_recovery(client, student):
    OUTBOX.clear()
    assert client.post("/auth/forgot-password", json={"email": "ama@x.com"}).status_code == 200
    token = OUTBOX[-1]["body"].split("token=")[1]
    assert client.post("/auth/reset-password", json={"token": token, "password": "newpassword9"}).status_code == 200
    assert client.post("/auth/reset-password", json={"token": token, "password": "another-pass1"}).status_code == 400  # one use
    assert login(client, "ama@x.com", "newpassword9")
    # unknown email gives the same reply
    assert client.post("/auth/forgot-password", json={"email": "nobody@x.com"}).status_code == 200


def test_email_verification(client):
    OUTBOX.clear()
    h = register(client)
    token = OUTBOX[-1]["body"].split("token=")[1]
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get("/auth/me", headers=h).json()["email_verified"] is True


def test_saved_addresses(client, student):
    r = client.post("/auth/addresses", headers=student, json={"kind": "pickup_point", "label": "Main gate",
                                                              "place": "Main gate"})
    assert r.status_code == 201
    assert len(client.get("/auth/addresses", headers=student).json()) == 2
    assert client.post("/auth/addresses", headers=student, json={"kind": "hostel", "label": "x"}).status_code == 422


def test_suspended_user_blocked(client, student, admin):
    uid = client.get("/auth/me", headers=student).json()["id"]
    assert client.post(f"/admin/users/{uid}/active", headers=admin, json={"is_active": False}).status_code == 200
    assert client.get("/auth/me", headers=student).status_code == 401
    assert client.post("/auth/login", json={"identifier": "ama@x.com", "password": "password123"}).status_code == 403


def test_hostel_list_seeded_exactly_and_admin_managed(client, admin):
    camp = client.get("/universities").json()[0]["campuses"][0]["id"]
    names = [h["name"] for h in client.get(f"/campuses/{camp}/hostels").json()]
    assert names == ["D block(College of health sciences student hostel)", "B- block", "R-block", "BQ", "M-block", "N- block"]
    hid = client.post("/admin/hostels", headers=admin, json={"campus_id": camp, "name": "Z block"}).json()["id"]
    assert client.post("/admin/hostels", headers=admin, json={"campus_id": camp, "name": "Z block"}).status_code == 409
    client.post(f"/admin/hostels/{hid}/active", headers=admin, json={"active": False})
    assert "Z block" not in [h["name"] for h in client.get(f"/campuses/{camp}/hostels").json()]
