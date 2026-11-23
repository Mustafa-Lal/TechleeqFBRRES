import pytest
import httpx
from concurrent.futures import ThreadPoolExecutor
from test_workflow import api
from test_operations import setup, place, pay
from app import province_adapters as adapters


def test_multi_line_invoice_partial_returns_and_rollback(api):
    c, h, item, stock = setup(api)
    supplier = c.post("/suppliers", headers=h, json={"name": "Supplier"}).json()["id"]
    body = {
        "supplier_id": supplier,
        "invoice_reference": "MULTI1",
        "lines": [
            {
                "stock_id": stock,
                "quantity": 10,
                "unit_cost": 100,
                "tax": 100,
                "recoverable_tax": True,
            },
            {"stock_id": stock, "quantity": 5, "unit_cost": 200},
        ],
        "paid": 500,
    }
    result = c.post("/inventory/invoices", headers=h, json=body)
    assert result.status_code == 201, result.text
    invoice = result.json()
    ident = invoice["id"]
    assert invoice["total"] == 2100
    assert c.post("/inventory/invoices", headers=h, json=body).status_code == 409
    returned = c.post(
        f"/inventory/invoices/{ident}/returns",
        headers=h,
        json={"reason": "Partial return", "lines": [{"line_index": 0, "quantity": 3}]},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["lines"][0]["credit"] == 330
    before = c.get("/inventory/items", headers=h).json()
    assert (
        c.post(
            f"/inventory/invoices/{ident}/returns",
            headers=h,
            json={
                "reason": "Too much",
                "lines": [
                    {"line_index": 1, "quantity": 1},
                    {"line_index": 0, "quantity": 99},
                ],
            },
        ).status_code
        == 409
    )
    assert c.get("/inventory/items", headers=h).json() == before
    assert c.get("/inventory/invoices", headers=h).json()[0]["outstanding"] == 1270


def test_attachments_access_and_validation(api):
    c, h, item, stock = setup(api)
    expense = c.post(
        "/expenses",
        headers=h,
        json={"category": "Rent", "description": "Lease", "amount": 100},
    ).json()
    path = f"/attachments/expense/{expense['id']}"
    assert (
        c.post(
            path, headers=h, files={"file": ("evil.html", b"<script>bad</script>")}
        ).status_code
        == 415
    )
    result = c.post(
        path,
        headers=h,
        files={"file": ("receipt.pdf", b"%PDF-1.4\nexample", "application/pdf")},
    )
    assert result.status_code == 201, result.text
    assert "content" not in result.json()
    ident = result.json()["id"]
    assert c.get(f"/attachments/{ident}", headers=h).content.startswith(b"%PDF-")
    assert c.get(f"/attachments/{ident}", headers=api[1]("cashier")).status_code == 403


def test_item_returns_reporting_and_privacy(api):
    c, h, item, stock = setup(api)
    cashier = api[1]("cashier")
    o = place(c, cashier, item)
    payment = pay(c, cashier, o)
    assert "cost" not in o and "recipe" not in o["lines"][0]
    c.post(f"/orders/{o['id']}/status", headers=cashier, json={"status": "preparing"})
    c.post(
        f"/orders/{o['id']}/refunds",
        headers=h,
        json={"payment_id": payment["id"], "amount": o["total"], "reason": "Returned"},
    )
    result = c.post(
        f"/orders/{o['id']}/returned-items",
        headers=h,
        json={"reason": "Returned", "items": [{"line_index": 0, "quantity": 1}]},
    )
    assert result.status_code == 200, result.text
    assert (
        c.post(
            f"/orders/{o['id']}/returned-items",
            headers=h,
            json={"reason": "Again", "items": [{"line_index": 0, "quantity": 1}]},
        ).status_code
        == 409
    )
    report = c.get("/reports/items", headers=h).json()["items"][0]
    assert report["quantity"] == 0 and report["net_sales"] == 0
    audit = c.get(
        "/audit/records", headers=h, params={"entity": "order", "record_id": o["id"]}
    ).json()
    assert audit and any(row["user_id"] is not None for row in audit)


def test_simultaneous_orders_cannot_overreserve(api):
    c, h, item, stock = setup(api, 1)

    def create(_):
        return c.post(
            "/orders", headers=h, json={"lines": [{"item_id": item, "quantity": 1}]}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(create, range(2)))
    assert sorted(statuses) == [201, 409]


@pytest.mark.parametrize(
    "province,authority,transport",
    [
        ("punjab", "PRA", "cloud"),
        ("balochistan", "BRA", "local"),
        ("islamabad", "FBR", "local"),
        ("sindh", "SRB", "cloud"),
    ],
)
def test_province_contracts_test_mode_and_snapshot(
    api, monkeypatch, province, authority, transport
):
    c, h, item, stock = setup(api)
    for key in ("POS_ID", "TOKEN", "NTN", "USERNAME", "PASSWORD"):
        monkeypatch.setenv("FISCAL_ADAPTER_" + key, "123")
    config = {
        "authority": authority,
        "transport": transport,
        "mode": "test",
        "environment_prefix": "FISCAL_ADAPTER",
        "classification_code": "98010000",
        "enabled": True,
    }
    result = c.post("/fiscal/connectors", headers=h, json=config)
    assert result.status_code == 200, result.text
    c.put(
        "/settings/tax",
        headers=h,
        json={"province": province, "tax_bps": 1000, "source": "Fixture rule"},
    )
    o = place(c, h, item)
    calls = []

    def send(url, payload, headers):
        calls.append((url, payload, headers))
        return httpx.Response(
            200,
            json={
                "srbInvoiceId": "SRB1",
                "resCode": "00",
                "QRCodeLink": "https://apps.srb.gos.pk/InvoiceVerification/MobileInvoiceStatus.jsp?invoiceVerification=SRB1",
            }
            if authority == "SRB"
            else {"Code": "100", "InvoiceNumber": "IMS1"},
        )

    monkeypatch.setattr(adapters, "send_request", send)
    path = f"/fiscal/orders/{o['id']}/submit"
    result = c.post(path, headers=h)
    assert result.json()["status"] == "test_submitted", result.text
    assert c.post(path, headers=h).json()["status"] == "test_submitted"
    assert len(calls) == 1
    if authority != "SRB":
        assert calls[0][1]["Items"][0]["SaleValue"] == 10
        assert calls[0][1]["TotalBillAmount"] == 11
    assert c.get(f"/orders/{o['id']}/qr", headers=h).status_code == 409


def test_menu_availability_and_manager_override(api):
    c, h, item, stock = setup(api)
    preview = {
        "lines": [{"item_id": item, "quantity": 1, "override_price": 500}],
        "reason": "Manager special",
    }
    assert (
        c.post("/orders/preview", headers=api[1]("cashier"), json=preview).status_code
        == 403
    )
    assert c.post("/orders/preview", headers=h, json=preview).json()["total"] == 550
