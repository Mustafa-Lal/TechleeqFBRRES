from test_workflow import api
from test_operations import setup, place, pay


def test_purchase_conversion_recoverable_tax_and_restoration(api):
    c, h, item, stock = setup(api, 2)
    assert (
        c.put(
            f"/inventory/items/{stock}",
            headers=h,
            json={
                "name": "Bottles",
                "unit": "each",
                "threshold": 2,
                "code": "BOT",
                "conversions": {"carton": 6},
            },
        ).status_code
        == 200
    )
    supplier = c.post("/suppliers", headers=h, json={"name": "Supplier"}).json()["id"]
    invoice = c.post(
        "/inventory/invoices",
        headers=h,
        json={
            "supplier_id": supplier,
            "invoice_reference": "CARTON",
            "lines": [
                {
                    "stock_id": stock,
                    "quantity": 1,
                    "unit": "carton",
                    "unit_cost": 1200,
                    "tax": 120,
                    "recoverable_tax": True,
                }
            ],
        },
    ).json()
    assert (
        invoice["lines"][0]["base_quantity"] == 6
        and invoice["lines"][0]["cost"] == 1200
    )
    o = place(c, h, item)
    pay(c, h, o)
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"})
    c.post(
        f"/orders/{o['id']}/cancel",
        headers=h,
        json={"reason": "Unused drink", "stock_disposition": "restore_unused"},
    )
    s = c.get("/inventory/items", headers=h).json()[0]
    assert s["quantity"] == 8 and s["value"] == 1800
    assert c.get("/reports/dashboard", headers=h).json()["inventory_losses"] == 0
    assert any(
        m["kind"] == "restoration"
        for m in c.get("/inventory/movements", headers=h).json()
    )
    assert (
        c.put(
            f"/inventory/items/{stock}",
            headers=h,
            json={
                "name": "Bottles",
                "unit": "each",
                "threshold": 2,
                "code": "BOT",
                "active": False,
            },
        ).status_code
        == 200
    )
    assert c.get("/inventory/items", headers=h).json()[0]["active"] is False


def test_split_tax_collection_and_combo_report(api):
    c, h, item, stock = setup(api)
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
        "/orders",
        headers=h,
        json={
            "payment_mode": "mixed",
            "lines": [{"combo_id": combo["id"], "quantity": 1}],
        },
    ).json()
    path = f"/orders/{o['id']}/payments"
    c.post(path, headers=h, json={"amount": 500, "method": "cash"})
    c.post(path, headers=h, json={"amount": 1150, "method": "card"})
    assert c.get("/reports/dashboard", headers=h).json()["tax_collected"] == 150
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"})
    report = c.get("/reports/items", headers=h).json()
    assert len(report["items"]) == 1 and report["items"][0]["net_sales"] == 1500
    assert report["combo_component_quantities"][str(item)] == 2


def test_nonstacking_priority_minimum_and_invalid_period(api):
    c, h, item, stock = setup(api)
    c.post(
        "/menu/promotions",
        headers=h,
        json={
            "name": "High minimum",
            "kind": "fixed",
            "value": 900,
            "minimum_subtotal": 5000,
            "priority": 100,
        },
    )
    c.post(
        "/menu/promotions",
        headers=h,
        json={
            "name": "Priority winner",
            "kind": "fixed",
            "value": 100,
            "priority": 10,
            "stackable": False,
        },
    )
    c.post(
        "/menu/promotions",
        headers=h,
        json={
            "name": "Other",
            "kind": "percent",
            "value": 5000,
            "priority": 1,
            "stackable": False,
        },
    )
    o = place(c, h, item)
    assert o["discount"] == 100 and len(o["lines"][0]["promotions"]) == 1
    assert (
        c.post(
            "/menu/promotions",
            headers=h,
            json={
                "name": "Invalid",
                "kind": "fixed",
                "value": 10,
                "starts_at": 10,
                "ends_at": 5,
            },
        ).status_code
        == 422
    )


def test_combo_unavailable_component(api):
    c, h, item, stock = setup(api)
    combo = c.post(
        "/menu/combos",
        headers=h,
        json={
            "name": "Pair",
            "price": 1500,
            "components": [{"item_id": item, "quantity": 2}],
        },
    ).json()
    category = c.get("/menu/categories", headers=h).json()[0]["id"]
    c.put(
        f"/menu/items/{item}",
        headers=h,
        json={
            "name": "Drink",
            "code": "DRINK",
            "category_id": category,
            "price": 1000,
            "available": False,
            "recipe": [{"stock_id": stock, "quantity": 1}],
        },
    )
    assert (
        c.post(
            "/orders/preview",
            headers=h,
            json={"lines": [{"combo_id": combo["id"], "quantity": 1}]},
        ).status_code
        == 409
    )
