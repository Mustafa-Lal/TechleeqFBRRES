"""Purchase invoices, returns, attachments, reporting and frontend contracts."""

import base64
from pathlib import Path
from fastapi import UploadFile, File
from app.features import *


class PurchaseLine(Strict):
    stock_id: int
    quantity: int = Field(gt=0)
    unit: str | None = None
    unit_cost: int = Field(ge=0)
    discount: int = Field(default=0, ge=0)
    tax: int = Field(default=0, ge=0)
    recoverable_tax: bool = False
    charges: int = Field(default=0, ge=0)


class PurchaseInvoice(Strict):
    supplier_id: int
    invoice_reference: str = Field(min_length=1, max_length=100)
    purchased_at: float | None = None
    lines: list[PurchaseLine] = Field(min_length=1, max_length=100)
    paid: int = Field(default=0, ge=0)
    method: Literal["cash", "card", "bank"] = "cash"


@app.post("/inventory/invoices", status_code=201)
def purchase_invoice(body: PurchaseInvoice, user=Depends(inventory)):
    with db() as c:
        get(c, "supplier", body.supplier_id)
        if any(
            p.get("supplier_id") == body.supplier_id
            and p.get("invoice_reference") == body.invoice_reference
            for p in listing(c, "purchase_invoice")
        ):
            fail("Duplicate supplier invoice", 409)
        lines = []
        for line in body.lines:
            if (
                line.recoverable_tax
                and user["role"] != "manager"
                and not prefs(c).get("recoverable_purchase_tax", False)
            ):
                fail("Manager must configure recoverable purchase tax", 403)
            s = get(c, "stock", line.stock_id)
            factor = (
                1
                if line.unit in (None, s["unit"])
                else s.get("conversions", {}).get(line.unit)
            )
            if factor is None:
                fail("Unknown purchase unit")
            goods = line.quantity * line.unit_cost - line.discount
            if goods < 0:
                fail("Discount exceeds goods cost")
            total = goods + line.tax + line.charges
            cost = total - (line.tax if line.recoverable_tax else 0)
            lines.append(
                {
                    **line.model_dump(),
                    "base_quantity": line.quantity * factor,
                    "total": total,
                    "cost": cost,
                    "returned_quantity": 0,
                    "returned_cost": 0,
                    "returned_total": 0,
                }
            )
        total = sum(l["total"] for l in lines)
        if body.paid > total:
            fail("Payment exceeds invoice total")
        invoice = write(
            c,
            "purchase_invoice",
            {
                "supplier_id": body.supplier_id,
                "invoice_reference": body.invoice_reference,
                "created": body.purchased_at or time.time(),
                "lines": lines,
                "total": total,
                "paid": body.paid,
                "credited": 0,
                "user_id": user["id"],
            },
            user,
        )
        for line in lines:
            movement(
                c,
                get(c, "stock", line["stock_id"]),
                line["base_quantity"],
                line["cost"],
                "purchase_invoice",
                user,
                invoice["id"],
            )
        if body.paid:
            write(
                c,
                "invoice_payment",
                {
                    "invoice_id": invoice["id"],
                    "amount": body.paid,
                    "method": body.method,
                    "created": time.time(),
                },
                user,
            )
        notifications(c)
        return invoice


@app.get("/inventory/invoices")
def purchase_invoices(user=Depends(inventory)):
    with db() as c:
        return [
            {
                **p,
                "outstanding": max(0, p["total"] - p["credited"] - p["paid"]),
                "supplier_credit": max(0, p["paid"] - (p["total"] - p["credited"])),
            }
            for p in listing(c, "purchase_invoice")
        ]


@app.post("/inventory/invoices/{ident}/payments")
def invoice_payment(ident: int, body: Amount, user=Depends(inventory)):
    with db() as c:
        p = get(c, "purchase_invoice", ident)
        if p["paid"] + body.amount > p["total"] - p["credited"]:
            fail("Payment exceeds outstanding balance", 409)
        p["paid"] += body.amount
        write(c, "purchase_invoice", p, user, ident)
        return write(
            c,
            "invoice_payment",
            {"invoice_id": ident, **body.model_dump(), "created": time.time()},
            user,
        )


class ReturnLine(Strict):
    line_index: int = Field(ge=0)
    quantity: int = Field(gt=0, description="Quantity in base stock units")


class PurchaseReturn(Reason):
    lines: list[ReturnLine] = Field(min_length=1)


@app.post("/inventory/invoices/{ident}/returns")
def invoice_return(ident: int, body: PurchaseReturn, user=Depends(manager)):
    with db() as c:
        p = get(c, "purchase_invoice", ident)
        details = []
        for returned in body.lines:
            if returned.line_index >= len(p["lines"]):
                fail("Invalid line index")
            l = p["lines"][returned.line_index]
            cumulative = l["returned_quantity"] + returned.quantity
            if cumulative > l["base_quantity"]:
                fail("Return exceeds purchased quantity", 409)
            s = get(c, "stock", l["stock_id"])
            if s["quantity"] - reserved(c, s["id"]) < returned.quantity:
                fail("Stock consumed or reserved", 409)
            target_cost = (l["cost"] * cumulative + l["base_quantity"] // 2) // l[
                "base_quantity"
            ]
            target_total = (l["total"] * cumulative + l["base_quantity"] // 2) // l[
                "base_quantity"
            ]
            cost = target_cost - l["returned_cost"]
            credit = target_total - l["returned_total"]
            if s["value"] < cost:
                fail("Insufficient stock valuation; manager adjustment required", 409)
            movement(c, s, -returned.quantity, -cost, "purchase_return", user, ident)
            l.update(
                returned_quantity=cumulative,
                returned_cost=target_cost,
                returned_total=target_total,
            )
            p["credited"] += credit
            details.append({**returned.model_dump(), "credit": credit, "cost": cost})
        write(c, "purchase_invoice", p, user, ident)
        notifications(c)
        return write(
            c,
            "purchase_return",
            {
                "invoice_id": ident,
                "lines": details,
                "reason": body.reason,
                "created": time.time(),
                "user_id": user["id"],
            },
            user,
        )


@app.post("/attachments/{entity}/{ident}", status_code=201)
async def upload_attachment(
    entity: Literal["purchase", "purchase_invoice", "expense"],
    ident: int,
    file: UploadFile = File(),
    user=Depends(inventory),
):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        fail("Attachment exceeds 5 MiB", 413)
    media = (
        "application/pdf"
        if content.startswith(b"%PDF-")
        else "image/png"
        if content.startswith(b"\x89PNG\r\n\x1a\n")
        else "image/jpeg"
        if content.startswith(b"\xff\xd8\xff")
        else None
    )
    if media is None:
        fail("Only PDF, PNG and JPEG receipts are accepted", 415)
    with db() as c:
        get(c, entity, ident)
        item = write(
            c,
            "attachment",
            {
                "entity": entity,
                "record_id": ident,
                "name": Path(file.filename or "receipt").name,
                "media_type": media,
                "content": base64.b64encode(content).decode(),
                "created": time.time(),
                "user_id": user["id"],
            },
            user,
        )
        return {k: v for k, v in item.items() if k != "content"}


@app.get("/attachments/{ident}")
def attachment(ident: int, user=Depends(inventory)):
    with db() as c:
        item = get(c, "attachment", ident)
        return Response(
            base64.b64decode(item["content"]),
            media_type=item["media_type"],
            headers={
                "Content-Disposition": "attachment",
                "X-Content-Type-Options": "nosniff",
            },
        )


class ReturnedItem(Strict):
    line_index: int = Field(ge=0)
    quantity: int = Field(gt=0)


class ItemReturn(Reason):
    items: list[ReturnedItem] = Field(min_length=1)
    restore_unused: bool = False


@app.post("/orders/{ident}/returned-items")
def returned_items(ident: int, body: ItemReturn, user=Depends(manager)):
    """Record physical returned quantities separately from payment refunds."""
    with db() as c:
        o = get(c, "order", ident)
        if o["status"] not in ("preparing", "ready", "collected"):
            fail("Order has not been prepared", 409)
        previous = {}
        for r in listing(c, "item_return"):
            if r["order_id"] == ident:
                for l in r["items"]:
                    previous[l["line_index"]] = (
                        previous.get(l["line_index"], 0) + l["quantity"]
                    )
        if body.restore_unused:
            fail(
                "Prepared ingredients require an approved stock adjustment for restoration",
                409,
            )
        for l in body.items:
            if l.line_index >= len(o["lines"]):
                fail("Invalid order line")
            previous[l.line_index] = previous.get(l.line_index, 0) + l.quantity
            if previous[l.line_index] > o["lines"][l.line_index]["quantity"]:
                fail("Returned quantity exceeds sold quantity", 409)
        return write(
            c,
            "item_return",
            {
                "order_id": ident,
                **body.model_dump(),
                "created": time.time(),
                "user_id": user["id"],
            },
            user,
        )


@app.get("/reports/items")
def item_report(
    start: float = 0,
    end: float = 1e20,
    user=Depends(manager),
    sort_by: Literal["quantity", "net_sales"] = "quantity",
):
    with db() as c:
        items = {}
        component_totals = {}
        for o in listing(c, "order"):
            if not start <= o["created"] < end or o["status"] not in (
                "preparing",
                "ready",
                "collected",
            ):
                continue
            refunds = [r for r in listing(c, "refund") if r["order_id"] == o["id"]]
            net_refund = sum(r["net"] for r in refunds)
            remaining = net_refund
            returns = {}
            for r in listing(c, "item_return"):
                if r["order_id"] == o["id"]:
                    for l in r["items"]:
                        returns[l["line_index"]] = (
                            returns.get(l["line_index"], 0) + l["quantity"]
                        )
            for index, l in enumerate(o["lines"]):
                reduction = (
                    min(l["net"], remaining)
                    if index == len(o["lines"]) - 1
                    else min(
                        remaining,
                        (net_refund * l["net"] + o["net"] // 2) // o["net"]
                        if o["net"]
                        else 0,
                    )
                )
                remaining -= reduction
                key = ("combo:" if l["combo_id"] else "item:") + str(
                    l["combo_id"] or l["item_id"]
                )
                row = items.setdefault(
                    key, {"key": key, "name": l["name"], "quantity": 0, "net_sales": 0}
                )
                quantity = l["quantity"] - returns.get(index, 0)
                row["quantity"] += quantity
                row["net_sales"] += l["net"] - reduction
                for component in l.get("components", []):
                    component_totals[str(component["item_id"])] = (
                        component_totals.get(str(component["item_id"]), 0)
                        + quantity * component["quantity"]
                    )
        return {
            "items": sorted(items.values(), key=lambda x: (-x[sort_by], x["key"])),
            "combo_component_quantities": component_totals,
        }


@app.get("/orders/{ident}/payments")
def order_payments(ident: int, user=Depends(staff)):
    with db() as c:
        o = owned(c, ident, user, read=True)
        return {
            "payments": [p for p in listing(c, "payment") if p["order_id"] == ident],
            "refunds": [r for r in listing(c, "refund") if r["order_id"] == ident],
            "outstanding": max(0, o["total"] - o["paid"]),
            "status": "refunded"
            if o.get("refunded") == o["total"] and o["total"] > 0
            else "partially_refunded"
            if o.get("refunded", 0) > 0
            else "paid"
            if o["paid"] == o["total"]
            else "partially_paid"
            if o["paid"]
            else "unpaid",
        }


@app.get("/attachments/{entity}/{ident}/list")
def attachment_list(
    entity: Literal["purchase", "purchase_invoice", "expense"],
    ident: int,
    user=Depends(inventory),
):
    with db() as c:
        get(c, entity, ident)
        return [
            {k: v for k, v in a.items() if k != "content"}
            for a in listing(c, "attachment")
            if a["entity"] == entity and a["record_id"] == ident
        ]


app.router.routes[:] = [
    r
    for r in app.router.routes
    if getattr(r, "path", "")
    not in ("/reports/dashboard", "/reports/suppliers", "/orders/{ident}/receipt")
]


@app.get("/reports/dashboard")
def full_dashboard(start: float = 0, end: float = 1e20, user=Depends(manager)):
    result = report(start, end, user)
    result["best_selling"] = item_report(start, end, user)["items"]
    return result


@app.get("/reports/suppliers")
def full_supplier_balances(user=Depends(manager)):
    with db() as c:
        results = []
        for s in listing(c, "supplier"):
            old = [p for p in listing(c, "purchase") if p.get("supplier_id") == s["id"]]
            new = [
                p for p in listing(c, "purchase_invoice") if p["supplier_id"] == s["id"]
            ]
            balance = sum(
                p["total_cost"] - p["paid"] for p in old if not p["returned"]
            ) + sum(max(0, p["total"] - p["credited"] - p["paid"]) for p in new)
            credit = sum(p.get("supplier_credit", 0) for p in old) + sum(
                max(0, p["paid"] - (p["total"] - p["credited"])) for p in new
            )
            results.append(
                {
                    "supplier_id": s["id"],
                    "name": s["name"],
                    "outstanding": balance,
                    "supplier_credit": credit,
                }
            )
        return results


@app.get("/orders/{ident}/receipt", response_class=HTMLResponse)
def fiscal_receipt(ident: int, user=Depends(staff)):
    return receipt(ident, user)


class Revision(Basket):
    stock_disposition: Literal["waste", "restore_unused"] = "waste"


@app.post("/orders/{ident}/revision", status_code=201)
def revise_order(ident: int, body: Revision, user=Depends(manager)):
    """Correct a confirmed invoice with an atomic reversal and linked replacement."""
    if not body.reason.strip():
        fail("Revision reason required")
    with db() as c:
        old = get(c, "order", ident)
        if old["status"] == "cancelled" or old["fiscal_status"] in (
            "sending",
            "unknown",
        ):
            fail("Order cannot be revised in its current state", 409)
        replacement = price(c, body, user)
        if body.stock_disposition == "restore_unused":
            for used in old["consumption"]:
                movement(
                    c,
                    get(c, "stock", used["stock_id"]),
                    used["quantity"],
                    used["value"],
                    "restoration",
                    user,
                    ident,
                )
            old["cost"] = 0
        for sid, qty in needs(replacement).items():
            if (
                get(c, "stock", sid)["quantity"] - reserved(c, sid, ident) < qty
                and not body.allow_shortage
            ):
                fail("Insufficient stock for replacement", 409)
        if old["status"] == "queued":
            for sid, qty in needs(old).items():
                save(
                    c,
                    "movement",
                    {
                        "stock_id": sid,
                        "quantity": 0,
                        "value": 0,
                        "reserved": -qty,
                        "kind": "reservation_release",
                        "reference": ident,
                        "created": time.time(),
                        "user_id": user["id"],
                    },
                )
        old.update(
            status="cancelled",
            cancel_reason=body.reason,
            cancelled_at=time.time(),
            cancel_net=old["net"] - old.get("refund_net", 0),
            cancel_tax=old["tax"] - old.get("refund_tax", 0),
        )
        save(c, "order", old, ident)
        for p in listing(c, "payment"):
            if p["order_id"] == ident:
                refunded = sum(
                    r["amount"]
                    for r in listing(c, "refund")
                    if r["payment_id"] == p["id"]
                )
                if p["applied"] > refunded:
                    refund_record(c, old, p, p["applied"] - refunded, body.reason, user)
        replacement.update(
            cashier_id=old["cashier_id"],
            created=time.time(),
            confirmed_at=time.time(),
            status="queued",
            paid=0,
            cost=0,
            refunded=0,
            refund_net=0,
            refund_tax=0,
            fiscal_status="pending",
            consumption=[],
            receipt_count=0,
            replaces_order_id=ident,
        )
        write(c, "order", replacement, user)
        replacement["code"] = (
            f"{prefs(c).get('order_prefix', 'R')}-{replacement['id']:06d}"
        )
        write(c, "order", replacement, user, replacement["id"])
        old["replacement_order_id"] = replacement["id"]
        write(c, "order", old, user, ident)
        for sid, qty in needs(replacement).items():
            save(
                c,
                "movement",
                {
                    "stock_id": sid,
                    "quantity": 0,
                    "value": 0,
                    "reserved": qty,
                    "kind": "reservation",
                    "reference": replacement["id"],
                    "created": time.time(),
                    "user_id": user["id"],
                },
            )
        cancellation_credit(c, old, user)
        notifications(c)
        return {"reversed_order": old, "replacement_order": replacement}


class Count(Reason):
    stock_id: int
    counted_quantity: int = Field(ge=0)
    added_value: int = Field(default=0, ge=0)


@app.post("/inventory/counts", status_code=201)
def stock_count(body: Count, user=Depends(inventory)):
    with db() as c:
        s = get(c, "stock", body.stock_id)
        return write(
            c,
            "adjustment",
            {
                "stock_id": s["id"],
                "quantity": body.counted_quantity - s["quantity"],
                "added_value": body.added_value,
                "expected_quantity": s["quantity"],
                "counted_quantity": body.counted_quantity,
                "reason": body.reason,
                "status": "pending",
                "created": time.time(),
                "user_id": user["id"],
            },
            user,
        )
