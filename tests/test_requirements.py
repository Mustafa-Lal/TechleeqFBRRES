import asyncio
import json
import time
from test_workflow import api
from test_operations import setup, place, pay
from app import core, features, migrate


def create_role(c, h, name, role):
    result = c.post(
        "/users",
        headers=h,
        json={"username": name, "password": "test-password", "role": role},
    )
    assert result.status_code == 201, result.text
    login = c.post(
        "/auth/login", json={"username": name, "password": "test-password"}
    ).json()
    return result.json()["id"], {"Authorization": "Bearer " + login["access_token"]}


def test_roles_account_lifecycle_and_password_change(api):
    c, auth = api
    h = auth("manager")
    ident, clerk = create_role(c, h, "clerk", "entry_clerk")
    category = c.post(
        "/inventory/categories", headers=clerk, json={"name": "Meat"}
    ).json()
    stock = c.post(
        "/inventory/items",
        headers=clerk,
        json={
            "name": "Chicken",
            "unit": "gram",
            "threshold": 10,
            "category_id": category["id"],
            "code": "CHICKEN",
        },
    ).json()
    assert stock["code"] == "CHICKEN"
    assert (
        c.post(
            "/inventory/items",
            headers=clerk,
            json={
                "name": "Duplicate",
                "unit": "gram",
                "threshold": 0,
                "code": "CHICKEN",
            },
        ).status_code
        == 409
    )
    assert c.post("/suppliers", headers=clerk, json={"name": "Farm"}).status_code == 201
    for path in ("/users", "/reports/dashboard", "/menu/items", "/orders"):
        assert c.get(path, headers=clerk).status_code == 403
    assert (
        c.post(
            "/menu/categories", headers=clerk, json={"name": "Forbidden"}
        ).status_code
        == 403
    )
    assert c.delete("/inventory/purchases/1", headers=clerk).status_code in (404, 405)
    assert (
        c.post(
            f"/users/{ident}/password",
            headers=clerk,
            json={"password": "changed-password", "old_password": "test-password"},
        ).status_code
        == 200
    )
    assert c.get("/auth/me", headers=clerk).status_code == 401
    assert (
        c.post(
            "/auth/login", json={"username": "clerk", "password": "changed-password"}
        ).status_code
        == 200
    )
    assert (
        c.post(
            f"/users/{ident}/password", headers=h, json={"password": "manager-reset"}
        ).status_code
        == 200
    )
    assert (
        c.put(
            f"/users/{ident}", headers=h, json={"role": "cashier", "active": False}
        ).status_code
        == 200
    )
    assert (
        c.post(
            "/auth/login", json={"username": "clerk", "password": "manager-reset"}
        ).status_code
        == 401
    )
    assert (
        c.put(
            f"/users/{ident}", headers=h, json={"role": "entry_clerk", "active": True}
        ).status_code
        == 200
    )
    assert c.get("/inventory/items", headers=h).json()[0]["code"] == "CHICKEN"


def test_menu_variants_and_historical_snapshots(api):
    c, h, item, stock = setup(api)
    category = c.get("/menu/categories", headers=h).json()[0]["id"]
    variant = c.post(
        "/menu/items",
        headers=h,
        json={
            "name": "Large",
            "code": "LARGE",
            "category_id": category,
            "price": 2000,
            "parent_item_id": item,
            "description": "Large drink",
            "image_url": "/images/drink.png",
            "recipe": [{"stock_id": stock, "quantity": 2}],
        },
    ).json()
    o = place(c, h, variant["id"])
    assert (
        o["lines"][0]["price"] == 2000 and o["lines"][0]["recipe"][0]["quantity"] == 2
    )
    data = {k: v for k, v in variant.items() if k != "id"}
    data.update(name="Renamed", price=3000, available=False)
    assert (
        c.put(f"/menu/items/{variant['id']}", headers=h, json=data).status_code == 200
    )
    assert variant["id"] not in [
        i["id"] for i in c.get("/menu/items", headers=api[1]("cashier")).json()
    ]
    assert c.get(f"/orders/{o['id']}", headers=h).json()["lines"][0]["name"] == "Large"
    data["available"] = True
    c.put(f"/menu/items/{variant['id']}", headers=h, json=data)
    assert (
        c.post(
            "/orders/preview",
            headers=h,
            json={"lines": [{"item_id": variant["id"], "quantity": 1}]},
        ).json()["subtotal"]
        == 3000
    )
    assert (
        c.put(
            f"/menu/categories/{category}",
            headers=h,
            json={"name": "Hidden", "active": False, "position": 3},
        ).status_code
        == 200
    )
    assert c.get("/menu/items", headers=api[1]("cashier")).json() == []
    assert c.delete(f"/menu/items/{item}", headers=h).status_code == 405


def test_promotion_targets_schedules_stacking_and_combo_availability(api, monkeypatch):
    c, h, item, stock = setup(api)
    t = time.time()
    category = c.get("/menu/categories", headers=h).json()[0]["id"]
    fixed = c.post(
        "/menu/promotions",
        headers=h,
        json={
            "name": "Fixed",
            "kind": "fixed",
            "value": 100,
            "category_ids": [category],
            "starts_at": t - 1,
            "ends_at": t + 10,
            "stackable": True,
            "priority": 10,
        },
    ).json()
    percent = c.post(
        "/menu/promotions",
        headers=h,
        json={
            "name": "Percentage",
            "kind": "percent",
            "value": 1000,
            "item_ids": [item],
            "stackable": True,
            "priority": 5,
        },
    ).json()
    basket = {"lines": [{"item_id": item, "quantity": 1}]}
    quoted = c.post("/orders/preview", headers=h, json=basket).json()
    assert quoted["discount"] == 190
    old = place(c, h, item)
    monkeypatch.setattr(features.time, "time", lambda: t + 11)
    assert c.post("/orders/preview", headers=h, json=basket).json()["discount"] == 100
    percent["active"] = False
    percent.pop("id")
    c.put(
        f"/menu/promotions/{old['lines'][0]['promotions'][1]['id']}",
        headers=h,
        json=percent,
    )
    assert c.post("/orders/preview", headers=h, json=basket).json()["discount"] == 0
    assert c.get(f"/orders/{old['id']}", headers=h).json()["discount"] == 190
    c.post(
        "/menu/promotions",
        headers=h,
        json={"name": "Capped", "kind": "fixed", "value": 99999},
    )
    assert c.post("/orders/preview", headers=h, json=basket).json()["total"] == 0
    combo = c.post(
        "/menu/combos",
        headers=h,
        json={
            "name": "Future",
            "price": 100,
            "starts_at": t + 100,
            "components": [{"item_id": item, "quantity": 1}],
        },
    ).json()
    assert (
        c.post(
            "/orders/preview",
            headers=h,
            json={"lines": [{"combo_id": combo["id"], "quantity": 1}]},
        ).status_code
        == 409
    )


def test_queue_filters_preview_and_status_history(api):
    c, h, item, stock = setup(api)
    cash = api[1]("cashier")
    assert (
        c.post(
            "/orders/preview",
            headers=cash,
            json={
                "lines": [{"item_id": item, "quantity": 2, "notes": "No ice"}],
                "notes": "Takeaway",
            },
        ).json()["total"]
        == 2200
    )
    assert c.get("/orders", headers=cash).json() == []
    first = place(c, cash, item, notes="Takeaway")
    second = place(c, cash, item)
    assert first["confirmed_at"] >= first["created"]
    assert first["code"] != second["code"]
    assert [
        o["id"]
        for o in c.get("/orders", headers=cash, params={"status": "queued"}).json()
    ] == [first["id"], second["id"]]
    assert (
        len(c.get("/orders", headers=cash, params={"code": first["code"]}).json()) == 1
    )
    ident, other = create_role(c, h, "cashier2", "cashier")
    assert c.get(f"/orders/{first['id']}", headers=other).status_code == 200
    assert c.get("/orders", headers=h, params={"cashier_id": ident}).json() == []
    assert (
        c.post(
            f"/orders/{first['id']}/status",
            headers=cash,
            json={
                "status": "preparing",
                "allow_unpaid": True,
                "reason": "Not authorized",
            },
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/orders/{first['id']}/status",
            headers=h,
            json={
                "status": "preparing",
                "allow_unpaid": True,
                "reason": "Manager approved account",
            },
        ).status_code
        == 200
    )
    history = c.get(
        "/audit/records",
        headers=h,
        params={"entity": "order", "record_id": first["id"]},
    ).json()
    assert any(
        r["current"]["status"] == "preparing" and r["user_id"] is not None
        for r in history
    )


def test_displays_sse_and_read_only_access(api):
    c, h, item, stock = setup(api)
    _, prep = create_role(c, h, "kitchen", "preparation_display")
    o = place(c, h, item, notes="Takeaway")
    pay(c, h, o)
    rows = c.get("/displays/preparation", headers=prep).json()
    assert rows[0]["notes"] == "Takeaway" and rows[0]["elapsed_seconds"] >= 0
    assert set(rows[0]["lines"][0]) == {"name", "quantity", "notes", "components"}
    assert (
        c.post(
            f"/orders/{o['id']}/status", headers=prep, json={"status": "preparing"}
        ).status_code
        == 403
    )
    display = api[1]("display")

    class Request:
        headers = {"authorization": display["Authorization"]}

        async def is_disconnected(self):
            return False

    async def first_event():
        response = await features.display_events(
            "customer", Request(), core.current(display["Authorization"])
        )
        try:
            return await anext(response.body_iterator)
        finally:
            await response.body_iterator.aclose()

    data = asyncio.run(first_event())
    assert json.loads(data.removeprefix("data: ").strip()) == [
        {"code": o["code"], "status": "preparing"}
    ]
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"})
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "ready"})
    assert c.get("/displays/preparation", headers=prep).json() == []
    assert c.get("/displays/customer", headers=display).json()[0]["status"] == "ready"


def test_split_tender_receipt_and_payment_status(api):
    c, h, item, stock = setup(api)
    o = place(c, h, item, payment_mode="mixed")
    path = f"/orders/{o['id']}/payments"
    assert (
        c.post(path, headers=h, json={"amount": 500, "method": "card"}).status_code
        == 200
    )
    assert c.get(path, headers=h).json()["status"] == "partially_paid"
    result = c.post(path, headers=h, json={"amount": 1000, "method": "cash"}).json()
    assert result["change"] == 400
    assert c.get(path, headers=h).json()["status"] == "paid"
    receipt = c.get(f"/orders/{o['id']}/receipt", headers=h).text
    assert (
        "10.00" in receipt
        and "11.00" in receipt
        and "cash" in receipt
        and "card" in receipt
    )
    assert "COPY" in c.get(f"/orders/{o['id']}/receipt", headers=h).text


def test_revisions_are_atomic_and_preserve_original_payment(api):
    c, h, item, stock = setup(api, 2)
    o = place(c, h, item)
    pay(c, h, o)
    body = {"lines": [{"item_id": item, "quantity": 99}], "reason": "Correction"}
    assert (
        c.post(f"/orders/{o['id']}/revision", headers=h, json=body).status_code == 409
    )
    assert c.get(f"/orders/{o['id']}", headers=h).json()["status"] == "queued"
    body["lines"][0]["quantity"] = 2
    result = c.post(f"/orders/{o['id']}/revision", headers=h, json=body)
    assert result.status_code == 201, result.text
    data = result.json()
    assert (
        data["reversed_order"]["refunded"] == 1100
        and data["replacement_order"]["paid"] == 0
    )
    assert data["replacement_order"]["replaces_order_id"] == o["id"]
    assert data["replacement_order"]["total"] == 2200


def test_stock_counts_opening_cost_and_stale_approval(api):
    c, h, item, stock = setup(api)
    _, clerk = create_role(c, h, "clerk", "entry_clerk")
    counted = c.post(
        "/inventory/counts",
        headers=clerk,
        json={"stock_id": stock, "counted_quantity": 18, "reason": "Physical count"},
    ).json()
    assert (
        c.post(
            f"/inventory/adjustments/{counted['id']}/approve", headers=clerk
        ).status_code
        == 403
    )
    assert (
        c.post(f"/inventory/adjustments/{counted['id']}/approve", headers=h).status_code
        == 200
    )
    stale = c.post(
        "/inventory/counts",
        headers=clerk,
        json={"stock_id": stock, "counted_quantity": 17, "reason": "Count again"},
    ).json()
    c.post(
        "/inventory/purchases",
        headers=clerk,
        json={
            "stock_id": stock,
            "quantity": 1,
            "total_cost": 300,
            "supplier_reference": "NEW",
        },
    )
    assert (
        c.post(f"/inventory/adjustments/{stale['id']}/approve", headers=h).status_code
        == 409
    )
    assert c.get("/inventory/items", headers=h).json()[0]["quantity"] == 19


def test_low_stock_alert_recovers_and_recurs(api):
    c, h, item, stock = setup(api, 1)
    first = c.get("/notifications", headers=h).json()
    assert len([n for n in first if n["active"]]) == 1
    c.post(f"/notifications/{first[0]['id']}/read", headers=h)
    c.post(
        "/inventory/purchases",
        headers=h,
        json={
            "stock_id": stock,
            "quantity": 10,
            "total_cost": 3000,
            "supplier_reference": "RESTOCK",
        },
    )
    assert not any(n["active"] for n in c.get("/notifications", headers=h).json())
    o = c.post(
        "/orders", headers=h, json={"lines": [{"item_id": item, "quantity": 10}]}
    ).json()
    alerts = c.get("/notifications", headers=h).json()
    assert len(alerts) == 2 and len([n for n in alerts if n["active"]]) == 1
    movements = c.get("/inventory/movements", headers=h).json()
    assert any(
        m["kind"] == "reservation" and m["reference"] == o["id"] for m in movements
    )


def test_expense_filters_tax_cost_treatment_and_exports(api):
    c, h, item, stock = setup(api)
    c.post("/expenses/categories", headers=h, json={"name": "Repairs"})
    expense = c.post(
        "/expenses",
        headers=h,
        json={
            "category": "Repairs",
            "description": "Repair",
            "amount": 1100,
            "recoverable_tax": 100,
            "payee": "Plumber",
            "paid": 500,
        },
    ).json()
    selected = c.get(
        "/expenses",
        headers=h,
        params={
            "category": "Repairs",
            "payee": "Plumber",
            "payment_status": "partially_paid",
        },
    ).json()
    assert [e["id"] for e in selected] == [expense["id"]]
    assert c.get("/reports/dashboard", headers=h).json()["expenses"] == 1000
    assert (
        c.get(
            "/reports/export/expense",
            headers=h,
            params={"start": expense["created"] + 1},
        ).text
        == ""
    )
    assert "Plumber" in c.get("/reports/export/expense", headers=h).text
    for period in ("today", "week", "month"):
        assert (
            c.get("/reports/period", headers=h, params={"period": period}).status_code
            == 200
        )


def test_weighted_cost_snapshot_and_uncosted_warning(api):
    c, h, item, stock = setup(api, 2)
    c.post(
        "/inventory/purchases",
        headers=h,
        json={
            "stock_id": stock,
            "quantity": 2,
            "total_cost": 1000,
            "supplier_reference": "HIGHER",
        },
    )
    o = place(c, h, item)
    pay(c, h, o)
    assert (
        c.post(
            f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"}
        ).json()["cost"]
        == 400
    )
    c.post(
        "/inventory/purchases",
        headers=h,
        json={
            "stock_id": stock,
            "quantity": 1,
            "total_cost": 10000,
            "supplier_reference": "LATER",
        },
    )
    assert c.get(f"/orders/{o['id']}", headers=h).json()["cost"] == 400
    empty = c.post(
        "/inventory/items",
        headers=h,
        json={"name": "Uncosted", "unit": "each", "threshold": 0},
    ).json()
    opening = c.post(
        "/inventory/adjustments",
        headers=h,
        json={"stock_id": empty["id"], "quantity": 1, "reason": "Opening count"},
    ).json()
    c.post(f"/inventory/adjustments/{opening['id']}/approve", headers=h)
    category = c.get("/menu/categories", headers=h).json()[0]["id"]
    product = c.post(
        "/menu/items",
        headers=h,
        json={
            "name": "Uncosted sale",
            "category_id": category,
            "price": 100,
            "recipe": [{"stock_id": empty["id"], "quantity": 1}],
        },
    ).json()
    uncosted = place(c, h, product["id"])
    pay(c, h, uncosted, "SECOND")
    c.post(f"/orders/{uncosted['id']}/status", headers=h, json={"status": "preparing"})
    assert c.get("/reports/dashboard", headers=h).json()["costs_complete"] is False


def test_restaurant_settings_and_scope(api):
    c, h, item, stock = setup(api)
    assert (
        c.put(
            "/settings/restaurant",
            headers=h,
            json={
                "name": "Sample",
                "address": "Main road",
                "phone": "123",
                "timezone": "Asia/Karachi",
                "order_prefix": "FOOD",
            },
        ).status_code
        == 200
    )
    o = place(c, h, item)
    assert o["code"].startswith("FOOD-")
    receipt = c.get(f"/orders/{o['id']}/receipt", headers=h).text
    assert "Sample" in receipt and "Main road" in receipt and "+05:00" in receipt
    paths = c.get("/openapi.json").json()["paths"]
    assert not any(
        path.startswith(("/tables", "/customer/orders", "/deploy")) for path in paths
    )


def test_legacy_migration_is_idempotent_and_preserves_backup(api):
    c, h, item, stock = setup(api)
    with core.db() as connection:
        old = core.save(
            connection,
            "order",
            {
                "subtotal": 100,
                "tax": 10,
                "tax_bps": 1000,
                "total": 110,
                "province": "punjab",
                "authority": "PRA",
                "created": time.time(),
                "status": "queued",
                "paid": 0,
                "cost": 0,
                "lines": [{"item_id": item, "quantity": 1, "price": 100, "recipe": []}],
            },
        )
    backup = migrate.migrate()
    from pathlib import Path

    assert Path(backup).exists()
    migrate.migrate()
    with core.db() as connection:
        result = core.get(connection, "order", old["id"])
        assert (
            result["net"] == 100
            and result["total"] == 110
            and result["legacy_cost_detail_missing"]
        )


def test_unpaid_cancel_has_full_fiscal_reversal(api):
    c, h, item, stock = setup(api)
    o = place(c, h, item)
    c.post(
        f"/orders/{o['id']}/cancel", headers=h, json={"reason": "Unpaid cancellation"}
    )
    credits = c.get("/fiscal/submissions", headers=h).json()["credits"]
    assert sum(r["amount"] for r in credits) == o["total"]
    assert credits[0]["net"] == o["net"] and credits[0]["tax"] == o["tax"]
    assert c.get(f"/orders/{o['id']}/payments", headers=h).json()["refunds"] == []


def test_financial_reports_reconcile_and_link_transactions(api):
    c, h, item, stock = setup(api)
    o = place(c, h, item)
    payment = pay(c, h, o)
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"})
    c.post(
        f"/orders/{o['id']}/refunds",
        headers=h,
        json={"payment_id": payment["id"], "amount": 550, "reason": "Adjustment"},
    )
    dashboard = c.get("/reports/dashboard", headers=h).json()
    operations = c.get("/reports/operations", headers=h).json()
    assert sum(operations["daily_net_sales"].values()) == dashboard["net_sales"]
    assert sum(operations["category_sales"].values()) == dashboard["net_sales"]
    assert dashboard["order_ids"] == [o["id"]]
    assert (
        c.get("/reports/items", headers=h, params={"sort_by": "net_sales"}).json()[
            "items"
        ][0]["net_sales"]
        == 500
    )
    assert c.get("/reports/export/payment", headers=h).text.find(str(o["id"])) >= 0


def test_tax_permissions_future_effective_rule_and_readiness(api):
    c, h, item, stock = setup(api)
    cash = api[1]("cashier")
    o = place(c, h, item)
    assert (
        c.put(
            "/settings/tax",
            headers=cash,
            json={"province": "sindh", "tax_bps": 0, "source": "Unauthorized"},
        ).status_code
        == 403
    )
    c.put(
        "/settings/tax",
        headers=h,
        json={
            "province": "sindh",
            "tax_bps": 2000,
            "source": "Future official rule",
            "effective_from": time.time() + 3600,
        },
    )
    quote = c.post(
        "/orders/preview", headers=h, json={"lines": [{"item_id": item, "quantity": 1}]}
    ).json()
    assert quote["province"] == "punjab" and quote["tax"] == 100
    assert (
        c.get(f"/orders/{o['id']}", headers=h).json()["tax_rule"]["source"]
        == "Official test fixture"
    )
    assert (
        c.post(
            "/fiscal/connectors",
            headers=h,
            json={
                "authority": "PRA",
                "classification_code": "98010000",
                "enabled": True,
                "mode": "live",
                "environment_prefix": "FISCAL_MISSING",
            },
        ).status_code
        == 409
    )
    audit = c.get("/audit/records", headers=h, params={"entity": "tax_rule"}).json()
    assert audit and audit[0]["current"]["effective_from"] > time.time()
