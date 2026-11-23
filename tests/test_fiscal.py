import httpx
from test_workflow import api
from test_operations import setup, place
from app import fiscal


def connector(c, h, monkeypatch):
    for key, value in [("NTN", "N123"), ("POS_ID", "P123"), ("KEY", "secret")]:
        monkeypatch.setenv("FISCAL_TEST_" + key, value)
    response = c.post(
        "/fiscal/connectors",
        headers=h,
        json={
            "authority": "KPRA",
            "environment_prefix": "FISCAL_TEST",
            "enabled": True,
            "mode": "live",
        },
    )
    assert response.status_code == 200, response.text
    c.put(
        "/settings/tax",
        headers=h,
        json={"province": "khyber_pakhtunkhwa", "tax_bps": 1000, "source": "test"},
    )


def test_submit_and_duplicate_protection(api, monkeypatch):
    c, h, item, _ = setup(api)
    connector(c, h, monkeypatch)
    o = place(c, h, item)
    calls = []

    def send(payload):
        calls.append(payload)
        return httpx.Response(
            201,
            json={
                "status": 201,
                "data": {
                    "invoice_no": o["code"],
                    "pos_id": "P123",
                    "transaction_id": 42,
                },
            },
        )

    monkeypatch.setattr(fiscal, "post_invoice", send)
    path = f"/fiscal/orders/{o['id']}/submit"
    assert c.post(path, headers=h).json()["status"] == "submitted"
    assert c.post(path, headers=h).json()["reference"] == "42"
    assert len(calls) == 1 and calls[0]["amount"] == 10
    assert c.get(f"/orders/{o['id']}/qr", headers=h).status_code == 200


def test_timeout_never_auto_retries(api, monkeypatch):
    c, h, item, _ = setup(api)
    connector(c, h, monkeypatch)
    o = place(c, h, item)

    def timeout(payload):
        raise httpx.ReadTimeout("test")

    monkeypatch.setattr(fiscal, "post_invoice", timeout)
    path = f"/fiscal/orders/{o['id']}/submit"
    assert c.post(path, headers=h).json()["status"] == "unknown"
    assert c.post(path, headers=h).status_code == 409
    assert c.get(f"/orders/{o['id']}/qr", headers=h).status_code == 409


def test_unsupported_authority_never_claims_success(api):
    c, h, item, _ = setup(api)
    o = place(c, h, item)
    assert c.post(f"/fiscal/orders/{o['id']}/submit", headers=h).status_code == 409
