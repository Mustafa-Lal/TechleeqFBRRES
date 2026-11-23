from test_workflow import api
from app import core as m


def setup(api, qty=20):
    c, auth = api
    h = auth("manager")
    assert (
        c.put(
            "/settings/tax",
            headers=h,
            json={
                "province": "punjab",
                "tax_bps": 1000,
                "source": "Official test fixture",
            },
        ).status_code
        == 200
    )
    cat = c.post("/menu/categories", headers=h, json={"name": "Meals"}).json()["id"]
    stock = c.post(
        "/inventory/items",
        headers=h,
        json={"name": "Bottles", "unit": "each", "threshold": 2},
    ).json()["id"]
    c.post(
        "/inventory/purchases",
        headers=h,
        json={
            "stock_id": stock,
            "quantity": qty,
            "total_cost": qty * 300,
            "supplier_reference": "B1",
        },
    )
    item = c.post(
        "/menu/items",
        headers=h,
        json={
            "name": "Drink",
            "category_id": cat,
            "price": 1000,
            "recipe": [{"stock_id": stock, "quantity": 1}],
        },
    ).json()["id"]
    return c, h, item, stock


def place(c, h, item, **kwargs):
    r = c.post(
        "/orders",
        headers=h,
        json={"lines": [{"item_id": item, "quantity": 1}], **kwargs},
    )
    assert r.status_code == 201, r.text
    return r.json()


def pay(c, h, o, ref="PAY"):
    r = c.post(
        f"/orders/{o['id']}/payments",
        headers=h,
        json={"amount": o["total"], "method": "cash", "reference": ref},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_scheduled_discounts_and_combo_consumption(api):
    c, h, item, stock = setup(api)
    c.post(
        "/menu/promotions",
        headers=h,
        json={"name": "Expired", "kind": "percent", "value": 5000, "ends_at": 1},
    )
    c.post(
        "/menu/promotions",
        headers=h,
        json={"name": "Ten percent", "kind": "percent", "value": 1000},
    )
    combo = c.post(
        "/menu/combos",
        headers=h,
        json={
            "name": "Pair",
            "price": 1500,
            "components": [{"item_id": item, "quantity": 2}],
        },
    ).json()
    o = c.post(
        "/orders", headers=h, json={"lines": [{"combo_id": combo["id"], "quantity": 1}]}
    ).json()
    assert o["discount"] == 150 and o["total"] == 1485
    pay(c, h, o)
    assert (
        c.post(
            f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"}
        ).status_code
        == 200
    )
    assert c.get("/inventory/items", headers=h).json()[0]["quantity"] == 18


def test_reservations_cancel_and_notifications(api):
    c, h, item, stock = setup(api, 1)
    o = place(c, h, item)
    assert (
        c.post(
            "/orders", headers=h, json={"lines": [{"item_id": item, "quantity": 1}]}
        ).status_code
        == 409
    )
    p = pay(c, h, o)
    result = c.post(
        f"/orders/{o['id']}/cancel", headers=h, json={"reason": "Customer cancelled"}
    ).json()
    assert result["status"] == "cancelled" and result["refunded"] == 1100
    assert c.get("/inventory/items", headers=h).json()[0]["quantity"] == 1
    place(c, h, item)
    alerts = c.get("/notifications", headers=h).json()
    assert len([a for a in alerts if a["active"]]) == 1


def test_refund_limits_and_profit(api):
    c, h, item, stock = setup(api)
    o = place(c, h, item)
    p = pay(c, h, o)
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"})
    payload = {
        "payment_id": p["id"],
        "amount": 550,
        "reason": "Partial refund",
        "line_indices": [0],
    }
    assert (
        c.post(f"/orders/{o['id']}/refunds", headers=h, json=payload).status_code == 200
    )
    report = c.get("/reports/dashboard", headers=h).json()
    assert report["net_sales"] == 500 and report["gross_profit"] == 200
    payload["amount"] = 551
    assert (
        c.post(f"/orders/{o['id']}/refunds", headers=h, json=payload).status_code == 409
    )
    assert c.get("/inventory/items", headers=h).json()[0]["quantity"] == 19


def test_cash_shift_and_receipt(api):
    c, h, item, stock = setup(api)
    shift = c.post("/shifts/open", headers=h, json={"opening_float": 5000}).json()
    o = place(c, h, item)
    pay(c, h, o)
    receipt = c.get(f"/orders/{o['id']}/receipt", headers=h)
    assert receipt.status_code == 200 and "COPY" not in receipt.text
    assert "COPY" in c.get(f"/orders/{o['id']}/receipt", headers=h).text
    c.post(
        f"/shifts/{shift['id']}/movements",
        headers=h,
        json={"amount": -100, "reason": "Drawer removal"},
    )
    closed = c.post(
        f"/shifts/{shift['id']}/close", headers=h, json={"counted_cash": 6000}
    ).json()
    assert closed["difference"] == 0


def test_supplier_purchase_return_and_adjustment(api):
    c, h, item, stock = setup(api)
    supplier = c.post("/suppliers", headers=h, json={"name": "Wholesale"}).json()["id"]
    purchase = {
        "stock_id": stock,
        "quantity": 10,
        "total_cost": 3000,
        "supplier_reference": "SUP1",
        "supplier_id": supplier,
    }
    p = c.post("/inventory/purchases", headers=h, json=purchase).json()
    assert c.post("/inventory/purchases", headers=h, json=purchase).status_code == 409
    c.post(f"/inventory/purchases/{p['id']}/payments", headers=h, json={"amount": 1000})
    assert c.get("/reports/suppliers", headers=h).json()[0]["outstanding"] == 2000
    c.post(
        f"/inventory/purchases/{p['id']}/return",
        headers=h,
        json={"reason": "Returned unopened"},
    )
    assert c.get("/reports/suppliers", headers=h).json()[0]["outstanding"] == 0
    a = c.post(
        "/inventory/adjustments",
        headers=h,
        json={"stock_id": stock, "quantity": -2, "reason": "Spoiled"},
    ).json()["id"]
    assert c.post(f"/inventory/adjustments/{a}/approve", headers=h).status_code == 200
    assert c.post(f"/inventory/adjustments/{a}/approve", headers=h).status_code == 409
    assert c.get("/reports/dashboard", headers=h).json()["inventory_losses"] == 600


def test_user_deactivation_and_last_manager(api):
    c, auth = api
    h = auth("manager")
    cashier = auth("cashier")
    users = c.get("/users", headers=h).json()
    manager_id = next(u["id"] for u in users if u["role"] == "manager")
    cashier_id = next(u["id"] for u in users if u["role"] == "cashier")
    assert (
        c.put(
            f"/users/{manager_id}", headers=h, json={"role": "cashier", "active": True}
        ).status_code
        == 409
    )
    assert (
        c.put(
            f"/users/{cashier_id}", headers=h, json={"role": "cashier", "active": False}
        ).status_code
        == 200
    )
    assert c.get("/auth/me", headers=cashier).status_code == 401


def test_tax_inclusive_card_and_method_validation(api):
    c, h, item, stock = setup(api)
    c.put(
        "/settings/tax",
        headers=h,
        json={
            "province": "sindh",
            "tax_bps": 1000,
            "card_tax_bps": 500,
            "inclusive": True,
            "source": "Test",
        },
    )
    o = place(c, h, item, payment_mode="card")
    assert o["total"] == 1000 and o["tax"] == 48 and o["net"] == 952
    assert (
        c.post(
            f"/orders/{o['id']}/payments",
            headers=h,
            json={"amount": 1000, "method": "cash", "reference": "wrong"},
        ).status_code
        == 409
    )


def test_expense_reversal_export_and_display_permissions(api):
    c, h, item, stock = setup(api)
    e = c.post(
        "/expenses",
        headers=h,
        json={"category": "Rent", "description": "Monthly rent", "amount": 5000},
    ).json()
    assert c.get("/reports/dashboard", headers=h).json()["operating_profit"] == -5000
    c.post(f"/expenses/{e['id']}/reverse", headers=h, json={"reason": "Duplicate"})
    assert c.get("/reports/dashboard", headers=h).json()["operating_profit"] == 0
    assert c.get("/reports/export/expense", headers=h).status_code == 200
    display = api[1]("display")
    assert c.get("/displays/preparation", headers=display).status_code == 403
    assert c.get("/reports/dashboard", headers=display).status_code == 403


def test_openapi_generation(api):
    c, _ = api
    r = c.get("/openapi.json")
    assert r.status_code == 200
    assert "/menu/promotions" in r.json()["paths"]
