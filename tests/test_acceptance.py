import time
import httpx
from test_workflow import api
from test_operations import setup, place, pay
from app import features, province_adapters as adapters


def test_cancellation_and_expense_reversal_preserve_history(api, monkeypatch):
    c, h, item, stock = setup(api)
    t = time.time()
    monkeypatch.setattr(features.time, "time", lambda: t)
    o = place(c, h, item)
    pay(c, h, o)
    c.post(f"/orders/{o['id']}/status", headers=h, json={"status": "preparing"})
    expense = c.post(
        "/expenses",
        headers=h,
        json={"category": "Utilities", "description": "Bill", "amount": 200},
    ).json()
    before = c.get(
        "/reports/dashboard", headers=h, params={"start": t - 1, "end": t + 1}
    ).json()
    assert before["operating_profit"] == 500
    monkeypatch.setattr(features.time, "time", lambda: t + 100)
    assert (
        c.post(
            f"/orders/{o['id']}/cancel",
            headers=h,
            json={"reason": "Cancelled after prep"},
        ).status_code
        == 200
    )
    assert (
        c.post(
            f"/expenses/{expense['id']}/reverse",
            headers=h,
            json={"reason": "Duplicate bill"},
        ).status_code
        == 200
    )
    historic = c.get(
        "/reports/dashboard", headers=h, params={"start": t - 1, "end": t + 1}
    ).json()
    assert historic["operating_profit"] == 500
    later = c.get(
        "/reports/dashboard", headers=h, params={"start": t + 99, "end": t + 101}
    ).json()
    assert later["net_sales"] == -1000
    assert later["inventory_losses"] == 300
    assert c.get("/reports/dashboard", headers=h).json()["operating_profit"] == -300


def test_srb_return_uses_original_authority(api, monkeypatch):
    c, h, item, stock = setup(api)
    for key in ("POS_ID", "NTN", "USERNAME", "PASSWORD"):
        monkeypatch.setenv("FISCAL_SRB_" + key, "123")
    c.post(
        "/fiscal/connectors",
        headers=h,
        json={
            "authority": "SRB",
            "environment_prefix": "FISCAL_SRB",
            "enabled": True,
            "mode": "live",
        },
    )
    c.put(
        "/settings/tax",
        headers=h,
        json={
            "province": "sindh",
            "tax_bps": 1000,
            "source": "Fixture",
            "discount_before_tax": False,
        },
    )
    o = place(c, h, item)
    p = pay(c, h, o)
    calls = []

    def send(url, payload, headers):
        calls.append(payload)
        return httpx.Response(
            200,
            json={
                "resCode": "00",
                "srbInvoiceId": "SRB123",
                "QRCodeLink": "https://apps.srb.gos.pk/InvoiceVerification/MobileInvoiceStatus.jsp?invoiceVerification=SRB123",
            },
        )

    monkeypatch.setattr(adapters, "send_request", send)
    assert (
        c.post(f"/fiscal/orders/{o['id']}/submit", headers=h).json()["status"]
        == "submitted"
    )
    c.put(
        "/settings/tax",
        headers=h,
        json={"province": "punjab", "tax_bps": 1000, "source": "Changed province"},
    )
    c.post(
        f"/orders/{o['id']}/refunds",
        headers=h,
        json={"payment_id": p["id"], "amount": 550, "reason": "Partial return"},
    )
    credit = c.get("/fiscal/submissions", headers=h).json()["credits"][0]
    result = c.post(f"/fiscal/credits/{credit['id']}/submit", headers=h)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "submitted"
    assert calls[-1]["invoiceType"] == 2
    assert calls[-1]["netAmount"] == 5.5
    assert o["code"] in calls[-1]["extraInf"]


def test_pending_worker_and_reconciliation(api, monkeypatch):
    c, h, item, stock = setup(api)
    for key in ("POS_ID", "TOKEN"):
        monkeypatch.setenv("FISCAL_PRA_" + key, "123")
    c.post(
        "/fiscal/connectors",
        headers=h,
        json={
            "authority": "PRA",
            "classification_code": "98010000",
            "environment_prefix": "FISCAL_PRA",
            "enabled": True,
            "mode": "test",
        },
    )
    o = place(c, h, item)
    monkeypatch.setattr(
        adapters,
        "send_request",
        lambda *args: httpx.Response(500, json={"message": "Error"}),
    )
    results = c.post("/fiscal/process-pending", headers=h).json()
    assert results[0]["status"] == "unknown"
    assert c.post("/fiscal/process-pending", headers=h).json() == []
    result = c.post(
        f"/fiscal/orders/{o['id']}/reconcile",
        headers=h,
        json={
            "outcome": "not_received",
            "reason": "Checked authority portal",
            "authority_evidence": "Support ticket ABC-123",
        },
    )
    assert result.json()["status"] == "pending"


def test_tax_before_discount_rule(api):
    c, h, item, stock = setup(api)
    c.put(
        "/settings/tax",
        headers=h,
        json={
            "province": "sindh",
            "tax_bps": 1000,
            "source": "Fixture",
            "discount_before_tax": False,
        },
    )
    c.post(
        "/menu/promotions",
        headers=h,
        json={"name": "Ten percent", "kind": "percent", "value": 1000},
    )
    o = place(c, h, item)
    assert o["net"] == 900 and o["tax"] == 100 and o["total"] == 1000
