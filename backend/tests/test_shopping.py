from .conftest import pid


def test_browse_search_and_synonyms(client):
    assert client.get("/categories").json()
    names = lambda q: [i["name"] for i in client.get("/products", params={"q": q}).json()["items"]]
    assert "Bel Malt Original" in names("malt")
    assert "Indomie" in names("noodles")  # synonym
    assert "Coca-Cola" in names("coke")
    assert names("zzzz") == []
    assert client.get("/products", params={"category": "noodles"}).json()["total"] == 1
    avail = [i["name"] for i in client.get("/products", params={"availability": "available"}).json()["items"]]
    assert "Bullet Energy" not in avail


def test_unpriced_product_shows_no_invented_price(client):
    water = client.get(f"/products/{pid(client, 'Water')}").json()
    assert water["price"] is None and water["price_listed"] is False and water["orderable"] is False


def test_variants_listed(client):
    d = client.get(f"/products/{pid(client, 'Coca-Cola')}").json()
    assert {v["name"]: v["price"] for v in d["variants"]} == {"Small": 4.0, "1 litre": 12.0}


def test_suggestions_and_popular(client):
    client.get("/products", params={"q": "milo"})
    assert client.get("/search/suggestions", params={"q": "ind"}).json() == ["Indomie"]
    assert "milo" in client.get("/search/popular").json()


def test_cart_operations(client, student):
    p = pid(client, "Bel Malt Original")
    r = client.post("/cart/items", headers=student, json={"product_id": p, "quantity": 2}).json()
    assert r["subtotal"] == 14.0 and r["items"][0]["quantity"] == 2
    line = r["items"][0]["id"]
    assert client.patch(f"/cart/items/{line}", headers=student, json={"quantity": 3}).json()["subtotal"] == 21.0
    assert client.patch(f"/cart/items/{line}", headers=student, json={"quantity": 0}).json()["items"] == []


def test_cart_persists(client, student):
    client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original")})
    assert len(client.get("/cart", headers=student).json()["items"]) == 1


def test_cannot_add_unavailable_unpriced_or_unchosen_variant(client, student):
    assert client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bullet Energy")}).status_code == 409
    assert client.post("/cart/items", headers=student, json={"product_id": pid(client, "Water")}).status_code == 409
    assert client.post("/cart/items", headers=student, json={"product_id": pid(client, "Coca-Cola")}).status_code == 422


def test_variant_in_cart(client, student):
    d = client.get(f"/products/{pid(client, 'Coca-Cola')}").json()
    v = next(x for x in d["variants"] if x["name"] == "1 litre")
    r = client.post("/cart/items", headers=student, json={"product_id": d["id"], "variant_id": v["id"]}).json()
    assert r["items"][0]["variant"] == "1 litre" and r["subtotal"] == 12.0


def test_stock_limit_only_when_tracked(client, student):
    assert client.post("/cart/items", headers=student, json={"product_id": pid(client, "Indomie"), "quantity": 4}).status_code == 409
    assert client.post("/cart/items", headers=student, json={"product_id": pid(client, "Indomie"), "quantity": 3}).status_code == 201
    assert client.post("/cart/items", headers=student, json={"product_id": pid(client, "Bel Malt Original"), "quantity": 50}).status_code == 201


def test_cart_requires_student_login(client):
    assert client.get("/cart").status_code == 401
