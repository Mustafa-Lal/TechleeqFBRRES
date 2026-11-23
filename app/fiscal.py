"""KPRA adapter. Secrets remain in environment variables, never API responses."""

import re
import httpx
import qrcode
import qrcode.image.svg
from urllib.parse import urlencode
from app.features import *

app.router.routes[:] = [
    r
    for r in app.router.routes
    if getattr(r, "path", "") != "/fiscal/orders/{ident}/submit"
]


class Connector(Strict):
    authority: Literal["PRA", "SRB", "KPRA", "BRA", "FBR"]
    environment_prefix: str = Field(pattern=r"^FISCAL_[A-Z0-9_]+$")
    enabled: bool = False


@app.post("/fiscal/connectors")
def configure(body: Connector, user=Depends(manager)):
    if body.enabled and body.authority != "KPRA":
        fail(
            "This authority adapter is not available; configuration may be saved disabled",
            409,
        )
    if body.enabled and not all(
        os.getenv(body.environment_prefix + "_" + key)
        for key in ("NTN", "POS_ID", "KEY")
    ):
        fail("Missing credential environment variables", 409)
    with db() as c:
        return write(c, "connector", body.model_dump(), user)


@app.get("/fiscal/connectors")
def connectors(user=Depends(manager)):
    with db() as c:
        return listing(c, "connector")


def post_invoice(payload):
    return httpx.post(
        "https://kpra.gov.pk/api/rims-integration", json=payload, timeout=20
    )


@app.post("/fiscal/orders/{ident}/submit")
def submit(ident: int, user=Depends(manager)):
    with db() as c:
        o = get(c, "order", ident)
        if o["fiscal_status"] == "submitted":
            return {"status": "submitted", "reference": o["fiscal_reference"]}
        if o["fiscal_status"] in ("sending", "unknown"):
            fail(
                "Submission outcome uncertain; reconcile with authority before retry",
                409,
            )
        if o["authority"] != "KPRA":
            fail("Authority adapter not available", 409)
        candidates = [
            s
            for s in listing(c, "connector")
            if s["authority"] == o["authority"] and s["enabled"]
        ]
        config = (
            get(c, "connector", o["connector_id"])
            if o.get("connector_id")
            else (candidates[-1] if candidates else None)
        )
        if not config:
            fail("Configure credentials first", 409)
        prefix = config["environment_prefix"]
        credentials = {
            k.lower(): os.getenv(prefix + "_" + k, "") for k in ("NTN", "POS_ID", "KEY")
        }
        if not all(credentials.values()):
            fail("Credentials unavailable", 409)
        if o["payment_mode"] == "mixed":
            fail("KPRA mixed payment mapping must be confirmed before submission", 409)
        payload = {
            **credentials,
            "invoice_no": o["code"],
            "amount": o["net"] / 100,
            "tax_rate": o["tax_bps"] / 100,
            "tax_amount": o["tax"] / 100,
            "total_amount": o["total"] / 100,
            "date_time": datetime.fromtimestamp(
                o["created"], ZoneInfo("Asia/Karachi")
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "payment_mode": 2 if o["payment_mode"] == "card" else 1,
        }
        o.update(fiscal_status="sending", connector_id=config["id"])
        save(c, "order", o, ident)
    try:
        response = post_invoice(payload)
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected authority response")
        valid = (
            response.status_code == 201
            and data.get("status") == 201
            and data.get("data", {}).get("invoice_no") == o["code"]
            and str(data["data"].get("pos_id")) == credentials["pos_id"]
            and data["data"].get("transaction_id") is not None
        )
        if valid:
            result = {
                "status": "submitted",
                "reference": str(data["data"]["transaction_id"]),
                "verification_url": "https://kpra.gov.pk/api/?"
                + urlencode({"pos_id": credentials["pos_id"], "invoice_no": o["code"]}),
            }
        elif response.status_code in (400, 401, 403, 405):
            result = {
                "status": "failed",
                "error": f"Authority rejected request (HTTP {response.status_code})",
            }
        else:
            result = {
                "status": "unknown",
                "error": "Uncertain authority response; reconciliation required",
            }
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        result = {
            "status": "unknown",
            "error": "Submission outcome uncertain; reconciliation required",
        }
    with db() as c:
        fresh = get(c, "order", ident)
        fresh["fiscal_status"] = result["status"]
        fresh["fiscal_reference"] = result.get("reference")
        fresh["verification_url"] = result.get("verification_url")
        fresh["fiscal_error"] = result.get("error")
        write(c, "order", fresh, user, ident)
    return result


@app.get("/orders/{ident}/qr")
def invoice_qr(ident: int, user=Depends(staff)):
    with db() as c:
        o = owned(c, ident, user)
        if o["fiscal_status"] != "submitted" or not o.get("verification_url"):
            fail("Invoice not verified", 409)
        image = qrcode.make(
            o["verification_url"], image_factory=qrcode.image.svg.SvgPathImage
        )
        output = io.BytesIO()
        image.save(output)
        return Response(output.getvalue(), media_type="image/svg+xml")


def post_credit(payload):
    return httpx.post(
        "https://kpra.gov.pk/api/kpra-credit-note", json=payload, timeout=20
    )


@app.post("/fiscal/credits/{ident}/submit")
def submit_credit(ident: int, user=Depends(manager)):
    with db() as c:
        credit = get(c, "fiscal_credit", ident)
        if credit["status"] == "submitted":
            return credit
        if credit["status"] in ("sending", "unknown"):
            fail("Reconcile uncertain credit before retry", 409)
        o = get(c, "order", credit["order_id"])
        if o["authority"] != "KPRA" or o["fiscal_status"] != "submitted":
            fail("Original invoice must be submitted through KPRA first", 409)
        config = get(c, "connector", o["connector_id"])
        prefix = config["environment_prefix"]
        credentials = {
            k.lower(): os.getenv(prefix + "_" + k, "") for k in ("NTN", "POS_ID", "KEY")
        }
        if not all(credentials.values()):
            fail("Credentials unavailable", 409)
        refund = (
            get(c, "refund", credit["refund_id"]) if credit.get("refund_id") else credit
        )
        payload = {
            **credentials,
            "invoice_no": o["code"],
            "credit_note_no": f"CN-{ident}",
            "note_type": "partial" if refund["amount"] < o["total"] else "full",
            "reason": refund["reason"],
            "amount": refund["net"] / 100,
            "tax_rate": o["tax_bps"] / 100,
            "tax_amount": refund["tax"] / 100,
            "total_amount": refund["amount"] / 100,
        }
        credit["status"] = "sending"
        save(c, "fiscal_credit", credit, ident)
    try:
        response = post_credit(payload)
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected authority response")
        accepted = (
            response.status_code in (200, 201)
            and data.get("data", {}).get("credit_note_no") == payload["credit_note_no"]
            and data["data"].get("credit_note_id") is not None
        )
        state = (
            "submitted"
            if accepted
            else "failed"
            if response.status_code in (400, 401, 403, 404, 405)
            else "unknown"
        )
        reference = str(data["data"]["credit_note_id"]) if accepted else None
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        state, reference = "unknown", None
    with db() as c:
        credit = get(c, "fiscal_credit", ident)
        credit.update(status=state, reference=reference)
        return write(c, "fiscal_credit", credit, user, ident)
