import pytest
from fastapi.testclient import TestClient
from app import core as m
from app import main


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "DB", str(tmp_path / "test.db"))
    m.initialize()
    with m.db() as c:
        for name, role in [
            ("manager", "manager"),
            ("cashier", "cashier"),
            ("display", "customer_display"),
        ]:
            c.execute(
                "INSERT INTO users(username,password,role) VALUES(?,?,?)",
                (name, m.passwords.hash("test-password"), role),
            )
    client = TestClient(m.app)

    def headers(name):
        token = client.post(
            "/auth/login", json={"username": name, "password": "test-password"}
        ).json()["access_token"]
        return {"Authorization": "Bearer " + token}

    return client, headers


def test_sale_and_privacy(api):
    c, auth = api
    manager, cashier, display = auth("manager"), auth("cashier"), auth("display")
    assert (
        c.put(
            "/settings/tax",
            headers=cashier,
            json={"province": "punjab", "tax_bps": 1000, "source": "test rule"},
        ).status_code
        == 403
    )
    c.put(
        "/settings/tax",
        headers=manager,
        json={"province": "punjab", "tax_bps": 1000, "source": "test rule"},
    )
    category = c.post(
        "/menu/categories", headers=manager, json={"name": "Drinks"}
    ).json()["id"]
    stock = c.post(
        "/inventory/items",
        headers=manager,
        json={"name": "Juice", "unit": "bottle", "threshold": 1},
    ).json()["id"]
    c.post(
        "/inventory/purchases",
        headers=manager,
        json={
            "stock_id": stock,
            "quantity": 2,
            "total_cost": 6000,
            "supplier_reference": "S1",
        },
    )
    item = c.post(
        "/menu/items",
        headers=manager,
        json={
            "name": "Juice",
            "category_id": category,
            "price": 10000,
            "recipe": [{"stock_id": stock, "quantity": 1}],
        },
    ).json()["id"]
    order = c.post(
        "/orders", headers=cashier, json={"lines": [{"item_id": item, "quantity": 1}]}
    ).json()
    path = f"/orders/{order['id']}"
    assert order["total"] == 11000
    assert (
        c.post(
            path + "/status", headers=cashier, json={"status": "preparing"}
        ).status_code
        == 409
    )
    payment = {"amount": 12000, "method": "cash", "reference": "P1"}
    assert (
        c.post(path + "/payments", headers=cashier, json=payment).json()["change"]
        == 1000
    )
    assert c.post(path + "/payments", headers=cashier, json=payment).status_code == 409
    assert (
        c.post(
            path + "/status", headers=cashier, json={"status": "preparing"}
        ).status_code
        == 200
    )
    assert (
        c.post(
            path + "/status", headers=cashier, json={"status": "preparing"}
        ).status_code
        == 409
    )
    assert c.get("/inventory/low-stock", headers=manager).json()[0]["quantity"] == 1
    assert c.get("/displays/customer", headers=display).json() == [
        {"code": order["code"], "status": "preparing"}
    ]
    assert c.get("/orders", headers=display).status_code == 403
    for status in ("ready", "collected"):
        assert (
            c.post(
                path + "/status", headers=cashier, json={"status": status}
            ).status_code
            == 200
        )
    assert c.get("/displays/customer", headers=display).json() == []
    report = c.get("/reports/dashboard", headers=manager).json()
    assert report["net_sales"] == 10000
    assert report["gross_profit"] == 7000
    c.put(
        "/settings/tax",
        headers=manager,
        json={"province": "sindh", "tax_bps": 1500, "source": "test rule"},
    )
    assert c.get("/orders", headers=cashier).json()[0]["authority"] == "PRA"


def test_authentication_and_validation(api):
    c, auth = api
    assert c.get("/orders").status_code == 401
    headers = auth("cashier")
    assert c.post("/orders", headers=headers, json={"lines": []}).status_code == 422
    assert c.post("/auth/logout", headers=headers).status_code == 200
    assert c.get("/orders", headers=headers).status_code == 401


def test_stock_shortage_rolls_back(api):
    c, auth = api
    h = auth("manager")
    c.put(
        "/settings/tax",
        headers=h,
        json={"province": "punjab", "tax_bps": 0, "source": "test rule"},
    )
    cat = c.post("/menu/categories", headers=h, json={"name": "Food"}).json()["id"]
    stock = c.post(
        "/inventory/items",
        headers=h,
        json={"name": "Rice", "unit": "gram", "threshold": 0},
    ).json()["id"]
    c.post(
        "/inventory/purchases",
        headers=h,
        json={
            "stock_id": stock,
            "quantity": 100,
            "total_cost": 1000,
            "supplier_reference": "R1",
        },
    )
    item = c.post(
        "/menu/items",
        headers=h,
        json={
            "name": "Rice",
            "category_id": cat,
            "price": 1000,
            "recipe": [{"stock_id": stock, "quantity": 60}],
        },
    ).json()["id"]
    order = c.post(
        "/orders",
        headers=h,
        json={
            "lines": [
                {"item_id": item, "quantity": 1},
                {"item_id": item, "quantity": 1},
            ],
            "allow_shortage": True,
            "reason": "test shortage",
        },
    ).json()
    path = f"/orders/{order['id']}"
    c.post(
        path + "/payments",
        headers=h,
        json={"amount": 2000, "method": "card", "reference": "RICE"},
    )
    assert (
        c.post(path + "/status", headers=h, json={"status": "preparing"}).status_code
        == 409
    )
    assert c.get("/inventory/items", headers=h).json()[0]["quantity"] == 100
    assert c.get("/orders", headers=h).json()[0]["status"] == "queued"
