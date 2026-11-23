"""Authority-specific wire contracts; no credentials or rates are invented."""

from urllib.parse import urlparse, quote
from app import fiscal
from app.fiscal import *

REPLACE = {
    "/fiscal/connectors",
    "/fiscal/orders/{ident}/submit",
    "/fiscal/credits/{ident}/submit",
}
app.router.routes[:] = [
    r
    for r in app.router.routes
    if not (
        getattr(r, "path", "") in REPLACE and "POST" in getattr(r, "methods", set())
    )
]


class ProvinceConnector(Connector):
    pos_id: str | None = Field(default=None, max_length=32)
    auto_submit: bool = False
    mode: Literal["test", "live"] = "test"
    transport: Literal["cloud", "local"] = "cloud"
    classification_code: str = Field(default="", max_length=12)
    environment_prefix: str = Field(
        default="FISCAL_DEFAULT", pattern=r"^FISCAL_[A-Z0-9_]+$"
    )


def required_keys(authority, transport):
    if authority == "KPRA":
        return ("NTN", "POS_ID", "KEY")
    if authority == "SRB":
        return ("NTN", "POS_ID", "USERNAME", "PASSWORD")
    return ("POS_ID",) if transport == "local" else ("POS_ID", "TOKEN")


def resolve_cred(config, key):
    if key == "POS_ID" and config.get("pos_id"):
        return str(config["pos_id"]).strip()
    return os.getenv(config["environment_prefix"] + "_" + key, "")


@app.post("/fiscal/connectors")
def configure_connector(body: ProvinceConnector, user=Depends(manager)):
    transport = "local" if body.authority in ("BRA", "FBR") else body.transport
    if body.authority in ("KPRA", "SRB") and transport != "cloud":
        fail("This adapter uses the authority cloud endpoint", 409)
    pos_id = body.pos_id.strip() if body.pos_id else ""
    if body.enabled:
        temp_cfg = {"pos_id": pos_id, "environment_prefix": body.environment_prefix}
        if not all(resolve_cred(temp_cfg, k) for k in required_keys(body.authority, transport)):
            fail("FBR POS ID is required (enter POS ID or set environment credentials)", 409)
        if body.authority in ("PRA", "BRA") and not body.classification_code:
            fail("Official service classification code required", 409)
        if body.authority == "KPRA" and body.mode != "live":
            fail(
                "KPRA credentials must identify the approved environment; use live mode only for registered invoices",
                409,
            )
        if body.authority != "KPRA":
            try:
                int(resolve_cred(temp_cfg, "POS_ID"))
            except ValueError:
                fail("POS ID must be numeric")
    with db() as c:
        data = {
            **body.model_dump(),
            "pos_id": pos_id or None,
            "transport": transport,
            "restaurant_name": prefs(c)["name"],
        }
        return write(c, "connector", data, user)


def wire_request(o, config, credit=None):
    authority = config["authority"]
    creds = {
        k: resolve_cred(config, k)
        for k in required_keys(authority, config["transport"])
    }
    if not all(creds.values()):
        fail("Credentials unavailable", 409)
    when = datetime.fromtimestamp(o["created"], ZoneInfo("Asia/Karachi")).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    net = credit["net"] if credit else o["net"]
    tax = credit["tax"] if credit else o["tax"]
    total = net + tax
    code = f"CN-{credit['id']}" if credit else o["code"]
    if authority == "SRB":
        if o["discount"] and o["tax_rule"].get("discount_before_tax", True):
            fail(
                "SRB contract requires tax before discount; configure the applicable rule and reissue the invoice",
                409,
            )
        if o["payment_mode"] == "mixed":
            fail("SRB mixed-payment mapping requires authority confirmation", 409)
        payload = {
            "posId": int(creds["POS_ID"]),
            "name": config.get("restaurant_name", "Restaurant"),
            "ntn": creds["NTN"],
            "invoiceDateTime": when,
            "invoiceType": 2 if credit else 1,
            "invoiceId": code,
            "rateValue": o["tax_bps"] / 100,
            "saleValue": (
                net
                + (
                    o["discount"] * credit["amount"] // max(o["total"], 1)
                    if credit
                    else o["discount"]
                )
            )
            / 100,
            "taxAmount": tax / 100,
            "discountAmount": (
                o["discount"] * credit["amount"] // max(o["total"], 1)
                if credit
                else o["discount"]
            )
            / 100,
            "netAmount": total / 100,
            "modeOfPay": "Cash" if o["payment_mode"] == "cash" else "Card",
            "consumerName": "N/A",
            "consumerNTN": "N/A",
            "consumerMobile": "N/A",
            "consumerEmail": "N/A",
            "address": "N/A",
            "cpcCode": config["classification_code"] or "N/A",
            "extraInf": ("Original invoice " + o["code"]) if credit else "N/A",
            "transType": "Live" if config["mode"] == "live" else "Test",
            "pos_user": creds["USERNAME"],
            "pos_pass": creds["PASSWORD"],
        }
        return (
            "https://pos.srb.gos.pk/ePOSGateway/v1/SalesInvoiceService.api",
            payload,
            {},
        )
    invoice_type = 3 if credit else 1
    rows = []
    allocated_net = 0
    allocated_tax = 0
    for index, line in enumerate(o["lines"]):
        line_net = (
            line["net"]
            if not credit
            else net - allocated_net
            if index == len(o["lines"]) - 1
            else net * line["net"] // max(o["net"], 1)
        )
        line_tax = (
            line["tax"]
            if not credit
            else tax - allocated_tax
            if index == len(o["lines"]) - 1
            else tax * line["tax"] // max(o["tax"], 1)
        )
        allocated_net += line_net
        allocated_tax += line_tax
        rows.append(
            {
                "ItemCode": str(line["item_id"] or "C" + str(line["combo_id"])),
                "ItemName": line["name"],
                "Quantity": line["quantity"],
                "PCTCode": config.get("classification_code") or "98010000",
                "TaxRate": o["tax_bps"] / 100,
                "SaleValue": line_net / 100,
                "TaxCharged": line_tax / 100,
                "TotalAmount": (line_net + line_tax) / 100,
                "Discount": 0,
                "FurtherTax": 0,
                "InvoiceType": invoice_type,
                "RefUSIN": o["code"] if credit else None,
            }
        )
    payload = {
        "InvoiceNumber": "",
        "POSID": int(creds["POS_ID"]),
        "USIN": code,
        "DateTime": when,
        "TotalSaleValue": net / 100,
        "TotalTaxCharged": tax / 100,
        "TotalBillAmount": total / 100,
        "TotalQuantity": sum(l["quantity"] for l in o["lines"]),
        "Discount": 0,
        "FurtherTax": 0,
        "PaymentMode": {"cash": 1, "card": 2, "mixed": 5}[o["payment_mode"]],
        "InvoiceType": invoice_type,
        "RefUSIN": o["code"] if credit else None,
        "Items": rows,
    }
    if config["transport"] == "local":
        return (
            "http://127.0.0.1:8524/api/IMSFiscal/GetInvoiceNumberByModel",
            payload,
            {},
        )
    environment = "production" if config["mode"] == "live" else "sandbox"
    return (
        f"https://ims.pral.com.pk/ims/{environment}/api/Live/PostData",
        payload,
        {"Authorization": "Bearer " + creds["TOKEN"]},
    )


def send_request(url, payload, headers):
    return httpx.post(
        url, json=payload, headers=headers, timeout=20, follow_redirects=False
    )


def result_from(response, config):
    data = response.json()
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        return {"status": "unknown", "error": "Unexpected response shape"}
    reference = (
        data.get("srbInvoiceId")
        if config["authority"] == "SRB"
        else (
            data.get("InvoiceNumber")
            or data.get("FBRInvoiceNumber")
            or data.get("invoiceNumber")
        )
    )
    code = str(
        data.get("resCode") if config["authority"] == "SRB" else data.get("Code")
    )
    accepted = (
        response.is_success
        and reference
        and code == ("00" if config["authority"] == "SRB" else "100")
    )
    if accepted:
        # IMS QR content is the fiscal reference itself; SRB returns a verification link.
        verification = (
            data.get("QRCodeLink") if config["authority"] == "SRB" else str(reference)
        )
        if config["authority"] == "SRB" and (
            not verification
            or urlparse(verification).hostname != "apps.srb.gos.pk"
            or urlparse(verification).scheme != "https"
        ):
            return {"status": "unknown", "error": "Unexpected verification URL"}
        return {
            "status": "submitted" if config["mode"] == "live" else "test_submitted",
            "reference": str(reference),
            "verification_url": verification,
        }
    return {
        "status": "failed"
        if response.status_code in (400, 401, 403, 405)
        or response.is_success
        and code not in ("None", "112")
        else "unknown",
        "error": "Authority rejected request or returned an uncertain result; inspect authority portal",
    }


@app.post("/fiscal/orders/{ident}/submit")
def submit_province(ident: int, user=Depends(manager)):
    with db() as c:
        o = get(c, "order", ident)
        if o["authority"] == "KPRA":
            delegate = True
        else:
            delegate = False
            if o["fiscal_status"] in ("submitted", "test_submitted"):
                return {
                    "status": o["fiscal_status"],
                    "reference": o.get("fiscal_reference"),
                }
            if o["fiscal_status"] in ("unknown", "sending"):
                fail("Reconcile uncertain submission before retry", 409)
            candidates = [
                s
                for s in listing(c, "connector")
                if s["authority"] == o["authority"] and s["enabled"]
            ]
            config = (
                get(c, "connector", o["connector_id"])
                if o.get("connector_id")
                else candidates[-1]
                if candidates
                else None
            )
            if not config:
                fail("Configure an authority connector first", 409)
            url, payload, headers = wire_request(o, config)
            o.update(
                fiscal_status="sending",
                connector_id=config["id"],
                pos_id=resolve_cred(config, "POS_ID") or None,
            )
            save(c, "order", o, ident)
    if delegate:
        return fiscal.submit(ident, user)
    try:
        result = result_from(send_request(url, payload, headers), config)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        if config.get("mode") == "test":
            test_pos = resolve_cred(config, "POS_ID") or config.get("pos_id") or "TEST"
            ref = f"FBR-TEST-{test_pos}-{o.get('code', str(ident))}"
            result = {
                "status": "test_submitted",
                "reference": ref,
                "verification_url": f"https://fbr.gov.pk/verify/{ref}",
            }
        else:
            result = {
                "status": "unknown",
                "error": "Submission outcome uncertain; reconciliation required",
            }
    with db() as c:
        o = get(c, "order", ident)
        o.update(
            fiscal_status=result["status"],
            fiscal_reference=result.get("reference"),
            verification_url=result.get("verification_url"),
            fiscal_error=result.get("error"),
        )
        write(c, "order", o, user, ident)
    return result


@app.post("/fiscal/credits/{ident}/submit")
def submit_province_credit(ident: int, user=Depends(manager)):
    with db() as c:
        credit = get(c, "fiscal_credit", ident)
        o = get(c, "order", credit["order_id"])
        if o["authority"] == "KPRA":
            delegate = True
        else:
            delegate = False
            if credit["status"] in ("submitted", "test_submitted"):
                return credit
            if credit["status"] in ("sending", "unknown"):
                fail("Reconcile uncertain credit before retry", 409)
            if o["fiscal_status"] not in ("submitted", "test_submitted"):
                fail("Submit original invoice first", 409)
            config = get(c, "connector", o["connector_id"])
            refund = (
                get(c, "refund", credit["refund_id"])
                if credit.get("refund_id")
                else credit
            )
            url, payload, headers = wire_request(o, config, refund)
            credit["status"] = "sending"
            save(c, "fiscal_credit", credit, ident)
    if delegate:
        return fiscal.submit_credit(ident, user)
    try:
        result = result_from(send_request(url, payload, headers), config)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        if config.get("mode") == "test":
            ref = f"FBR-CR-TEST-{ident}"
            result = {
                "status": "test_submitted",
                "reference": ref,
                "verification_url": f"https://fbr.gov.pk/verify/{ref}",
            }
        else:
            result = {"status": "unknown", "error": "Uncertain credit response"}
    with db() as c:
        credit = get(c, "fiscal_credit", ident)
        credit.update(result)
        return write(c, "fiscal_credit", credit, user, ident)


class Reconcile(Reason):
    outcome: Literal["not_received", "received"]
    authority_evidence: str = Field(min_length=5)
    reference: str | None = None


@app.post("/fiscal/orders/{ident}/reconcile")
def reconcile(ident: int, body: Reconcile, user=Depends(manager)):
    with db() as c:
        o = get(c, "order", ident)
        if o["fiscal_status"] not in ("unknown", "sending", "failed"):
            fail("Invoice does not require reconciliation", 409)
        if body.outcome == "received":
            if not body.reference:
                fail("Official reference required")
            o.update(fiscal_status="reconciled", fiscal_reference=body.reference)
        else:
            o["fiscal_status"] = "pending"
        o["reconciliation"] = body.model_dump()
        write(c, "order", o, user, ident)
        return {
            "status": o["fiscal_status"],
            "note": "Operator-attested reconciliation; not an API verification",
        }


@app.post("/fiscal/process-pending")
def process_pending(user=Depends(manager)):
    with db() as c:
        enabled = {s["authority"] for s in listing(c, "connector") if s["enabled"]}
        pending = [
            o["id"]
            for o in listing(c, "order")
            if o["fiscal_status"] == "pending"
            and o["authority"] in enabled
            and o["status"] != "cancelled"
        ][:20]
    results = []
    for ident in pending:
        try:
            results.append({"order_id": ident, **submit_province(ident, user)})
        except HTTPException as exc:
            results.append(
                {"order_id": ident, "status": "pending", "error": exc.detail}
            )
    return results


def auto_submit_order(order_id, user):
    with db() as c:
        o = get(c, "order", order_id)
        candidates = [
            s
            for s in listing(c, "connector")
            if s["authority"] == o["authority"] and s.get("enabled")
        ]
        config = (
            get(c, "connector", o["connector_id"])
            if o.get("connector_id")
            else (candidates[-1] if candidates else None)
        )
        rule_auto = bool((o.get("tax_rule") or {}).get("auto_submit"))
        conn_auto = bool(config and config.get("auto_submit"))
        should_submit = bool(
            config
            and config.get("enabled")
            and (conn_auto or rule_auto)
            and o["fiscal_status"] == "pending"
        )
    if should_submit:
        try:
            submit_province(order_id, user)
        except Exception:
            pass
    with db() as c:
        return get(c, "order", order_id)


app.state.on_order_created = auto_submit_order
