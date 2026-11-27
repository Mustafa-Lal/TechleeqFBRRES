"""Restaurant operations, immutable transaction snapshots and administrative APIs."""

import csv
import io
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response
from pydantic import ConfigDict, model_validator
from html import escape
from app.core import *

# Replace the foundation routes while preserving their public paths.
REPLACED = {
    "/orders",
    "/orders/{ident}/status",
    "/reports/dashboard",
    "/inventory/low-stock",
    "/inventory/purchases",
    "/expenses",
    "/settings/tax",
}
app.router.routes[:] = [
    r for r in app.router.routes if getattr(r, "path", "") not in REPLACED
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def write(c, kind, data, user, ident=None):
    before = get(c, kind, ident) if ident else None
    result = save(c, kind, data, ident)
    save(
        c,
        "change",
        {
            "entity": kind,
            "record_id": result["id"],
            "before": before,
            "after": dict(result),
            "user_id": user["id"],
            "created": time.time(),
        },
    )
    return result


def prefs(c):
    rows = listing(c, "restaurant")
    return (
        rows[-1]
        if rows
        else {
            "name": "Restaurant",
            "timezone": "Asia/Karachi",
            "currency": "PKR",
            "address": "",
            "phone": "",
        }
    )


class Restaurant(Strict):
    order_prefix: str = Field(default="R", pattern=r"^[A-Z]{1,8}$")
    recoverable_purchase_tax: bool = False
    recoverable_expense_tax: bool = False
    name: str = Field(min_length=1)
    address: str = ""
    phone: str = ""
    timezone: str = "Asia/Karachi"
    currency: Literal["PKR"] = "PKR"


@app.put("/settings/restaurant")
def restaurant(body: Restaurant, user=Depends(manager)):
    try:
        ZoneInfo(body.timezone)
    except Exception:
        fail("Invalid timezone")
    with db() as c:
        return write(c, "restaurant", body.model_dump(), user)


@app.get("/settings/restaurant")
def restaurant_get(user=Depends(staff)):
    with db() as c:
        return prefs(c)


class UserEdit(Strict):
    role: Literal[
        "manager", "cashier", "entry_clerk", "preparation_display", "customer_display"
    ]
    active: bool


@app.get("/users")
def users(user=Depends(manager)):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id,username,role,active FROM users")]


@app.put("/users/{ident}")
def user_edit(ident: int, body: UserEdit, user=Depends(manager)):
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (ident,)).fetchone()
        if not row:
            fail("User not found", 404)
        if (
            row["role"] == "manager"
            and row["active"]
            and (not body.active or body.role != "manager")
        ):
            if (
                c.execute(
                    "SELECT count(*) FROM users WHERE role='manager' AND active=1"
                ).fetchone()[0]
                <= 1
            ):
                fail("Cannot remove last active manager", 409)
        c.execute(
            "UPDATE users SET role=?,active=? WHERE id=?",
            (body.role, int(body.active), ident),
        )
        c.execute("DELETE FROM sessions WHERE user_id=?", (ident,))
        audit(c, user, "user_updated", ident)
        return {"id": ident, **body.model_dump()}


@app.delete("/users/{ident}")
def user_delete(ident: int, user=Depends(manager)):
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (ident,)).fetchone()
        if not row:
            fail("User not found", 404)
        if ident == user["id"]:
            fail("Cannot delete your own account while signed in", 409)
        if (
            row["role"] == "manager"
            and row["active"]
            and c.execute(
                "SELECT count(*) FROM users WHERE role='manager' AND active=1"
            ).fetchone()[0]
            <= 1
        ):
            fail("Cannot delete last active manager", 409)
        c.execute("DELETE FROM sessions WHERE user_id=?", (ident,))
        c.execute("DELETE FROM users WHERE id=?", (ident,))
        audit(c, user, "user_deleted", ident)
        return {"deleted": True, "id": ident}


class Password(Strict):
    password: str = Field(min_length=10, max_length=128)
    old_password: str | None = None


@app.post("/users/{ident}/password")
def reset_password(ident: int, body: Password, user=Depends(current)):
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (ident,)).fetchone()
        if not row:
            fail("User not found", 404)
        if user["role"] != "manager":
            if (
                ident != user["id"]
                or not body.old_password
                or not passwords.verify(body.old_password, row["password"])
            ):
                fail("Permission denied", 403)
        c.execute(
            "UPDATE users SET password=? WHERE id=?",
            (passwords.hash(body.password), ident),
        )
        c.execute("DELETE FROM sessions WHERE user_id=?", (ident,))
        audit(c, user, "password_reset", ident)
        return {"changed": True}


class TaxConfig(Settings):
    discount_before_tax: bool = True
    card_tax_bps: int | None = Field(default=None, ge=0, le=10000)
    inclusive: bool = False
    source: str = Field(min_length=1)
    effective_from: float = 0
    registration: str = ""
    auto_submit: bool = Field(default=False)


@app.put("/settings/tax")
def tax_config(body: TaxConfig, user=Depends(manager)):
    with db() as c:
        c.execute(
            "INSERT OR REPLACE INTO settings VALUES(1,?,?)",
            (body.province, body.tax_bps),
        )
        rules = listing(c, "tax_rule")
        rule_data = {**body.model_dump(), "authority": AUTHORITIES[body.province]}
        
        # Synchronize auto_submit with connector(s) for this authority
        auth = AUTHORITIES[body.province]
        conns = [s for s in listing(c, "connector") if s.get("authority") == auth]
        for conn in conns:
            conn["auto_submit"] = body.auto_submit
            save(c, "connector", conn, conn["id"])
        if body.auto_submit and not conns:
            new_conn = {
                "authority": auth,
                "environment_prefix": f"FISCAL_{auth}",
                "enabled": True,
                "pos_id": "",
                "auto_submit": True,
                "mode": "test",
                "transport": "local" if auth in ("BRA", "FBR") else "cloud",
                "classification_code": "",
            }
            save(c, "connector", new_conn)

        now = time.time()
        if body.effective_from <= now:
            active_rules = [r for r in rules if r.get("effective_from", 0) <= now]
            if active_rules:
                ident = active_rules[0]["id"]
                res = write(c, "tax_rule", rule_data, user, ident=ident)
                for extra in active_rules[1:]:
                    c.execute(
                        "DELETE FROM records WHERE kind='tax_rule' AND id=?",
                        (extra["id"],),
                    )
                return res
        elif rules:
            future_rules = [r for r in rules if r.get("effective_from", 0) > now]
            if future_rules:
                return write(
                    c, "tax_rule", rule_data, user, ident=future_rules[0]["id"]
                )
        return write(
            c,
            "tax_rule",
            rule_data,
            user,
        )


@app.get("/settings/tax")
def tax_rules(user=Depends(manager)):
    with db() as c:
        return listing(c, "tax_rule")


@app.get("/settings/tax/{ident}")
def tax_rule_get(ident: int, user=Depends(manager)):
    with db() as c:
        return get(c, "tax_rule", ident)


@app.put("/settings/tax/{ident}")
def tax_rule_update(ident: int, body: TaxConfig, user=Depends(manager)):
    with db() as c:
        c.execute(
            "INSERT OR REPLACE INTO settings VALUES(1,?,?)",
            (body.province, body.tax_bps),
        )
        auth = AUTHORITIES[body.province]
        conns = [s for s in listing(c, "connector") if s.get("authority") == auth]
        for conn in conns:
            conn["auto_submit"] = body.auto_submit
            save(c, "connector", conn, conn["id"])
        return write(
            c,
            "tax_rule",
            {**body.model_dump(), "authority": AUTHORITIES[body.province]},
            user,
            ident=ident,
        )


@app.delete("/settings/tax/{ident}")
def tax_rule_delete(ident: int, user=Depends(manager)):
    with db() as c:
        c.execute("DELETE FROM records WHERE kind='tax_rule' AND id=?", (ident,))
        audit(c, user, "tax_rule_deleted", ident)
        return {"deleted": True}


class CategoryEdit(Category):
    active: bool = True
    position: int = 0


@app.get("/menu/categories")
def categories(user=Depends(staff)):
    with db() as c:
        return sorted(listing(c, "category"), key=lambda x: x.get("position", 0))


@app.put("/menu/categories/{ident}")
def edit_category(ident: int, body: CategoryEdit, user=Depends(manager)):
    with db() as c:
        return write(c, "category", body.model_dump(), user, ident)


@app.delete("/menu/categories/{ident}")
def delete_category(ident: int, user=Depends(manager)):
    with db() as c:
        get(c, "category", ident)
        items_in_cat = [
            i for i in listing(c, "item") if i.get("category_id") == ident
        ]
        for item in items_in_cat:
            c.execute(
                "DELETE FROM records WHERE kind='item' AND id=?", (item["id"],)
            )
            audit(c, user, "item_deleted", item["id"])
        c.execute("DELETE FROM records WHERE kind='category' AND id=?", (ident,))
        audit(c, user, "category_deleted", ident)
        return {"deleted": True, "id": ident, "deleted_items": len(items_in_cat)}


class ItemEdit(Item):
    code: str = Field(min_length=1)
    description: str = ""
    available: bool = True
    parent_item_id: int | None = None
    image_url: str | None = None


@app.put("/menu/items/{ident}")
def edit_item(ident: int, body: ItemEdit, user=Depends(manager)):
    with db() as c:
        get(c, "category", body.category_id)
        for r in body.recipe:
            get(c, "stock", r.stock_id)
        if any(
            i.get("code") == body.code and i["id"] != ident for i in listing(c, "item")
        ):
            fail("Duplicate item code", 409)
        if body.parent_item_id:
            get(c, "item", body.parent_item_id)
        return write(c, "item", body.model_dump(), user, ident)


@app.get("/management/menu/items")
def management_menu(user=Depends(manager)):
    with db() as c:
        return listing(c, "item")


class Schedule(Strict):
    name: str = Field(min_length=1)
    active: bool = True
    starts_at: float = 0
    ends_at: float | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("End must follow start")
        return self


class Promotion(Schedule):
    kind: Literal["percent", "fixed"]
    value: int = Field(gt=0)
    item_ids: list[int] = []
    category_ids: list[int] = []
    minimum_subtotal: int = Field(default=0, ge=0)
    stackable: bool = False
    priority: int = 0

    @model_validator(mode="after")
    def rate(self):
        if self.kind == "percent" and self.value > 10000:
            raise ValueError("Percentage in basis points cannot exceed 10000")
        return self


class Component(Strict):
    item_id: int
    quantity: int = Field(gt=0)


class Combo(Schedule):
    price: int = Field(ge=0)
    components: list[Component] = Field(min_length=1)


def scheduled(row, now=None):
    now = now or time.time()
    return (
        row.get("active", True)
        and row.get("starts_at", 0) <= now
        and (row.get("ends_at") is None or now < row["ends_at"])
    )


def catalog_routes(path, kind, schema):
    def create(body: schema, user=Depends(manager)):
        with db() as c:
            if kind == "combo":
                for r in body.components:
                    get(c, "item", r.item_id)
            return write(c, kind, body.model_dump(), user)

    def update(ident: int, body: schema, user=Depends(manager)):
        with db() as c:
            if kind == "combo":
                for r in body.components:
                    get(c, "item", r.item_id)
            return write(c, kind, body.model_dump(), user, ident)

    def read(user=Depends(staff)):
        with db() as c:
            return listing(c, kind)

    app.post(path, status_code=201)(create)
    app.put(path + "/{ident}")(update)
    app.get(path)(read)


catalog_routes("/menu/combos", "combo", Combo)
catalog_routes("/menu/promotions", "promotion", Promotion)


class BasketLine(Strict):
    item_id: int | None = None
    combo_id: int | None = None
    quantity: int = Field(gt=0, le=1000)
    override_price: int | None = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def exclusive(self):
        if (self.item_id is None) == (self.combo_id is None):
            raise ValueError("Specify item_id or combo_id")
        return self


class Basket(Strict):
    lines: list[BasketLine] = Field(min_length=1, max_length=100)
    payment_mode: Literal["cash", "card", "mixed"] = "cash"
    notes: str = ""
    manual_discount: int = Field(default=0, ge=0)
    reason: str = ""
    allow_shortage: bool = False


def available(c, i):
    cat = get(c, "category", i["category_id"])
    if (
        not i.get("active", True)
        or not i.get("available", True)
        or not cat.get("active", True)
    ):
        fail("Menu item unavailable", 409)


def price(c, body, user):
    if (body.manual_discount or body.allow_shortage) and (
        user["role"] != "manager" or not body.reason.strip()
    ):
        fail("Manager and reason required", 403)
    rules = [r for r in listing(c, "tax_rule") if r["effective_from"] <= time.time()]
    if not rules:
        fail("Configure an effective tax rule first", 409)
    rule = max(rules, key=lambda r: (r["effective_from"], r["id"]))
    lines = []
    for raw in body.lines:
        if raw.item_id:
            i = get(c, "item", raw.item_id)
            available(c, i)
            line = {
                **raw.model_dump(),
                "name": i["name"],
                "category_id": i["category_id"],
                "price": i["price"],
                "recipe": i["recipe"],
                "components": [],
            }
        else:
            combo = get(c, "combo", raw.combo_id)
            if not scheduled(combo):
                fail("Combo unavailable", 409)
            recipe = []
            components = []
            for component in combo["components"]:
                i = get(c, "item", component["item_id"])
                available(c, i)
                recipe += [
                    {
                        "stock_id": r["stock_id"],
                        "quantity": r["quantity"] * component["quantity"],
                    }
                    for r in i["recipe"]
                ]
                components.append({**component, "name": i["name"]})
            line = {
                **raw.model_dump(),
                "name": combo["name"],
                "category_id": None,
                "price": combo["price"],
                "recipe": recipe,
                "components": components,
            }
        if raw.override_price is not None:
            if user["role"] != "manager" or not body.reason.strip():
                fail("Manager and reason required for price override", 403)
            line["price"] = raw.override_price
        line.update(gross=line["price"] * raw.quantity, discount=0, promotions=[])
        lines.append(line)
    subtotal = sum(l["gross"] for l in lines)
    for promo in sorted(
        listing(c, "promotion"), key=lambda p: (-p["priority"], p["id"])
    ):
        if not scheduled(promo) or subtotal < promo["minimum_subtotal"]:
            continue
        eligible = [
            l
            for l in lines
            if (
                not promo["item_ids"]
                and not promo["category_ids"]
                or l["item_id"] in promo["item_ids"]
                or l["category_id"] in promo["category_ids"]
            )
            and not l.get("locked")
            and (promo["stackable"] or not l["promotions"])
        ]
        remaining = promo["value"]
        for l in eligible:
            base = l["gross"] - l["discount"]
            amount = min(
                base,
                (base * promo["value"] + 5000) // 10000
                if promo["kind"] == "percent"
                else remaining,
            )
            if amount:
                l["discount"] += amount
                l["promotions"].append({"id": promo["id"], "amount": amount})
                remaining -= amount
                if not promo["stackable"]:
                    l["locked"] = True
    remaining = body.manual_discount
    for l in lines:
        take = min(remaining, l["gross"] - l["discount"])
        l["discount"] += take
        remaining -= take
    if remaining:
        fail("Discount exceeds order value")
    rate = (
        rule["card_tax_bps"]
        if body.payment_mode == "card" and rule.get("card_tax_bps") is not None
        else rule["tax_bps"]
    )
    for l in lines:
        base = l["gross"] - l["discount"]
        taxable = base if rule.get("discount_before_tax", True) else l["gross"]
        l["tax"] = (
            (taxable * rate + (10000 + rate) // 2) // (10000 + rate)
            if rule["inclusive"]
            else (taxable * rate + 5000) // 10000
        )
        l["net"] = base - l["tax"] if rule["inclusive"] else base
        l["total"] = l["net"] + l["tax"]
    return {
        "lines": lines,
        "subtotal": subtotal,
        "discount": sum(l["discount"] for l in lines),
        "net": sum(l["net"] for l in lines),
        "tax": sum(l["tax"] for l in lines),
        "total": sum(l["total"] for l in lines),
        "province": rule["province"],
        "authority": rule["authority"],
        "tax_bps": rate,
        "tax_rule": rule,
        "payment_mode": body.payment_mode,
        "notes": body.notes,
        "reason": body.reason,
    }


def needs(order):
    quantities = {}
    for l in order["lines"]:
        for r in l["recipe"]:
            quantities[r["stock_id"]] = (
                quantities.get(r["stock_id"], 0) + r["quantity"] * l["quantity"]
            )
    return quantities


def reserved(c, stock_id, exclude=None):
    return sum(
        needs(o).get(stock_id, 0)
        for o in listing(c, "order")
        if o["status"] == "queued" and o["id"] != exclude
    )


def notifications(c):
    active = {n["stock_id"]: n for n in listing(c, "notification") if n["active"]}
    for s in listing(c, "stock"):
        low = s["quantity"] - reserved(c, s["id"]) <= s["threshold"]
        if low and s["id"] not in active:
            save(
                c,
                "notification",
                {
                    "stock_id": s["id"],
                    "message": s["name"] + " needs replenishment",
                    "created": time.time(),
                    "active": True,
                    "read": False,
                },
            )
        elif not low and s["id"] in active:
            n = active[s["id"]]
            n["active"] = False
            save(c, "notification", n, n["id"])


def movement(c, s, quantity, value, kind, user, reference):
    s["quantity"] += quantity
    s["value"] += value
    save(c, "stock", s, s["id"])
    save(
        c,
        "movement",
        {
            "stock_id": s["id"],
            "quantity": quantity,
            "value": value,
            "kind": kind,
            "user_id": user["id"],
            "reference": reference,
            "created": time.time(),
        },
    )


@app.post("/orders/preview")
def preview(body: Basket, user=Depends(staff)):
    with db() as c:
        return price(c, body, user)


@app.post("/orders", status_code=201)
def place_order(body: Basket, user=Depends(staff)):
    with db() as c:
        o = price(c, body, user)
        configs = [
            config
            for config in listing(c, "connector")
            if config["authority"] == o["authority"] and config["enabled"]
        ]
        if configs:
            o["connector_id"] = configs[-1]["id"]
        for sid, qty in needs(o).items():
            s = get(c, "stock", sid)
            if s["quantity"] - reserved(c, sid) < qty and not body.allow_shortage:
                fail("Insufficient available stock: " + s["name"], 409)
        o.update(
            cashier_id=user["id"],
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
        )
        save(c, "order", o)
        o["code"] = f"{prefs(c).get('order_prefix', 'R')}-{o['id']:06d}"
        save(c, "order", o, o["id"])
        for sid, qty in needs(o).items():
            save(
                c,
                "movement",
                {
                    "stock_id": sid,
                    "quantity": 0,
                    "reserved": qty,
                    "value": 0,
                    "kind": "reservation",
                    "reference": o["id"],
                    "created": time.time(),
                    "user_id": user["id"],
                },
            )
        notifications(c)
        audit(c, user, "order_created", o["id"])
        order_id = o["id"]
    hook = getattr(app.state, "on_order_created", None)
    if hook:
        return hook(order_id, user)
    with db() as c:
        return get(c, "order", order_id)


@app.get("/orders")
def order_list(
    status: str | None = None,
    code: str | None = None,
    cashier_id: int | None = None,
    start: float = 0,
    end: float = 1e20,
    user=Depends(staff),
):
    with db() as c:
        usernames = {
            r["id"]: r["username"]
            for r in c.execute("SELECT id, username FROM users")
        }
        return [
            {
                **o,
                "created_by": usernames.get(
                    o.get("cashier_id"), f"User #{o.get('cashier_id', '?')}"
                ),
            }
            for o in listing(c, "order")
            if (not status or o["status"] == status)
            and (not code or code.lower() in o["code"].lower())
            and (not cashier_id or o["cashier_id"] == cashier_id)
            and start <= o["created"] < end
        ]


@app.get("/orders/{ident}")
def order_get(ident: int, user=Depends(staff)):
    with db() as c:
        o = owned(c, ident, user, read=True)
        row = c.execute(
            "SELECT username FROM users WHERE id=?", (o.get("cashier_id"),)
        ).fetchone()
        return {
            **o,
            "created_by": row["username"]
            if row
            else f"User #{o.get('cashier_id', '?')}",
        }


class NextStatus(Status):
    reason: str = ""
    allow_unpaid: bool = False


@app.post("/orders/{ident}/status")
def next_status(ident: int, body: NextStatus, user=Depends(staff)):
    with db() as c:
        o = owned(c, ident, user)
        if {"queued": "preparing", "preparing": "ready", "ready": "collected"}.get(
            o["status"]
        ) != body.status:
            fail("Invalid status transition", 409)
        if body.status == "preparing":
            if o["paid"] - o.get("refunded", 0) < o["total"] and not (
                body.allow_unpaid and user["role"] == "manager" and body.reason
            ):
                fail("Payment or Manager authorization required", 409)
            for sid, qty in needs(o).items():
                s = get(c, "stock", sid)
                if s["quantity"] < qty:
                    fail("Replenish stock before preparation", 409)
                cost = (s["value"] * qty + s["quantity"] // 2) // s["quantity"]
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
                movement(c, s, -qty, -cost, "consumption", user, ident)
                if cost == 0:
                    o["uncosted_stock"] = True
                o["cost"] += cost
                o["consumption"].append(
                    {"stock_id": sid, "quantity": qty, "value": cost}
                )
        if body.status == "preparing":
            o["recognized_at"] = time.time()
            o["recognized_cost"] = o["cost"]
        o["status"] = body.status
        write(c, "order", o, user, ident)
        audit(c, user, body.status, ident)
        notifications(c)
        return o


class Reason(Strict):
    reason: str = Field(min_length=1)


class Refund(Reason):
    payment_id: int
    amount: int = Field(gt=0)
    line_indices: list[int] = []


def refund_record(c, o, p, amount, reason, user):
    already = sum(
        r["amount"] for r in listing(c, "refund") if r["payment_id"] == p["id"]
    )
    if amount > p["applied"] - already:
        fail("Refund exceeds remaining payment", 409)
    previous = o.get("refunded", 0)
    total = previous + amount
    if total > o["total"]:
        fail("Refund exceeds order total", 409)
    net = (o["net"] * total + o["total"] // 2) // o["total"] if o["total"] else 0
    incremental = net - o.get("refund_net", 0)
    result = write(
        c,
        "refund",
        {
            "order_id": o["id"],
            "cancellation": o["status"] == "cancelled",
            "payment_id": p["id"],
            "amount": amount,
            "net": incremental,
            "tax": amount - incremental,
            "method": p["method"],
            "reason": reason,
            "created": time.time(),
            "user_id": user["id"],
            "shift_id": next(
                (
                    s["id"]
                    for s in listing(c, "shift")
                    if s["cashier_id"] == user["id"] and s["closed"] is None
                ),
                None,
            ),
        },
        user,
    )
    o.update(refunded=total, refund_net=net, refund_tax=total - net)
    save(c, "order", o, o["id"])
    save(
        c,
        "fiscal_credit",
        {
            "order_id": o["id"],
            "authority": o["authority"],
            "province": o["province"],
            "refund_id": result["id"],
            "status": "pending",
            "amount": amount,
        },
    )
    return result


@app.post("/orders/{ident}/refunds")
def refund(ident: int, body: Refund, user=Depends(manager)):
    with db() as c:
        o = get(c, "order", ident)
        p = get(c, "payment", body.payment_id)
        if p["order_id"] != ident:
            fail("Payment does not belong to order")
        if any(i < 0 or i >= len(o["lines"]) for i in body.line_indices):
            fail("Invalid refunded line")
        result = refund_record(c, o, p, body.amount, body.reason, user)
        result["line_indices"] = body.line_indices
        save(c, "refund", result, result["id"])
        return result


class Cancel(Reason):
    stock_disposition: Literal["waste", "restore_unused"] = "waste"


def cancellation_credit(c, o, user):
    """Fiscal reversal covers the invoice even when no customer payment exists."""
    credits = [r for r in listing(c, "fiscal_credit") if r["order_id"] == o["id"]]
    credited = sum(r["amount"] for r in credits)
    if credited >= o["total"]:
        return
    documents = [
        get(c, "refund", r["refund_id"]) if r.get("refund_id") else r for r in credits
    ]
    amount = o["total"] - credited
    net = o["net"] - sum(r["net"] for r in documents)
    write(
        c,
        "fiscal_credit",
        {
            "order_id": o["id"],
            "authority": o["authority"],
            "province": o["province"],
            "status": "pending",
            "amount": amount,
            "net": net,
            "tax": amount - net,
            "reason": o.get("cancel_reason", "Order cancellation"),
            "created": time.time(),
            "user_id": user["id"],
        },
        user,
    )


@app.post("/orders/{ident}/cancel")
def cancel(ident: int, body: Cancel, user=Depends(manager)):
    with db() as c:
        o = get(c, "order", ident)
        if o["status"] == "cancelled":
            fail("Already cancelled", 409)
        if o["status"] == "queued":
            for sid, qty in needs(o).items():
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
        if body.stock_disposition == "restore_unused":
            for used in o["consumption"]:
                s = get(c, "stock", used["stock_id"])
                movement(
                    c, s, used["quantity"], used["value"], "restoration", user, ident
                )
            o["cost"] = 0
        o["cancelled_at"] = time.time()
        o["cancel_net"] = o["net"] - o.get("refund_net", 0)
        o["cancel_tax"] = o["tax"] - o.get("refund_tax", 0)
        o["status"] = "cancelled"
        o["cancel_reason"] = body.reason
        save(c, "order", o, ident)
        for p in listing(c, "payment"):
            if p["order_id"] == ident:
                refunded = sum(
                    r["amount"]
                    for r in listing(c, "refund")
                    if r["payment_id"] == p["id"]
                )
                if p["applied"] > refunded:
                    refund_record(c, o, p, p["applied"] - refunded, body.reason, user)
        write(c, "order", o, user, ident)
        cancellation_credit(c, o, user)
        notifications(c)
        return o


@app.put("/orders/{ident}")
def edit_order(ident: int, body: Basket, user=Depends(manager)):
    with db() as c:
        old = get(c, "order", ident)
        if (
            old["status"] != "queued"
            or old["paid"]
            or old["fiscal_status"]
            in ("submitted", "sending", "unknown", "test_submitted", "reconciled")
        ):
            fail("Cancel/refund this order and create a replacement", 409)
        if not body.reason:
            fail("Reason required")
        new = price(c, body, user)
        for sid, qty in needs(new).items():
            if (
                get(c, "stock", sid)["quantity"] - reserved(c, sid, ident) < qty
                and not body.allow_shortage
            ):
                fail("Insufficient stock", 409)
        old.update(new)
        write(c, "order", old, user, ident)
        notifications(c)
        return old


@app.get("/orders/{ident}/receipt", response_class=HTMLResponse)
def receipt(ident: int, user=Depends(staff)):
    import qrcode
    import qrcode.image.svg

    with db() as c:
        o = owned(c, ident, user, read=True)
        p = prefs(c)
        count = o.get("receipt_count", 0)
        o["receipt_count"] = count + 1
        save(c, "order", o, ident)
        is_fiscal_active = (
            o.get("fiscal_status") in ("submitted", "test_submitted")
            and bool(o.get("verification_url"))
        )
        pos_id = None
        if is_fiscal_active:
            pos_id = o.get("pos_id")
            if not pos_id and o.get("connector_id"):
                try:
                    cfg = get(c, "connector", o["connector_id"])
                    pos_id = cfg.get("pos_id") or os.getenv(
                        cfg["environment_prefix"] + "_POS_ID"
                    )
                except Exception:
                    pass
        ntn = (o.get("tax_rule") or {}).get("registration", "")
        tax_rate_pct = f"{o.get('tax_bps', 0) / 100:.2f}".rstrip("0").rstrip(".")
        cashier_row = c.execute(
            "SELECT username FROM users WHERE id=?", (o.get("cashier_id"),)
        ).fetchone()
        cashier_name = cashier_row["username"] if cashier_row else f"Staff #{o.get('cashier_id', '')}"
        total_qty = sum(l["quantity"] for l in o["lines"])
        row_parts = []
        for l in o["lines"]:
            note_html = (
                f"<div class='item-note'>* {escape(l['notes'])}</div>"
                if l.get("notes")
                else ""
            )
            row_parts.append(
                f"<tr>"
                f"<td class='item-col'>{escape(l['name'])}{note_html}</td>"
                f"<td class='num qty-col'>{l['quantity']}</td>"
                f"<td class='num rate-col'>{l['price'] / 100:.2f}</td>"
                f"<td class='num amt-col'>{l['total'] / 100:.2f}</td>"
                f"</tr>"
            )
        rows = "".join(row_parts)
        payments = [pay for pay in listing(c, "payment") if pay["order_id"] == ident]
        paid_total = sum(pay["applied"] for pay in payments)
        balance_due = max(0, o["total"] - paid_total)
        payment_lines = []
        for pay in payments:
            tendered = pay.get("amount", pay["applied"] + pay.get("change", 0))
            payment_lines.append(
                f"<div class='row'><span>Paid ({escape(pay['method'].upper())})</span>"
                f"<span>{tendered / 100:.2f}</span></div>"
            )
            if pay.get("change", 0) > 0:
                payment_lines.append(
                    f"<div class='row'><span>Change Returned</span>"
                    f"<span>{pay['change'] / 100:.2f}</span></div>"
                )
        if balance_due > 0:
            payment_lines.append(
                f"<div class='row bold'><span>BALANCE DUE</span><span>{balance_due / 100:.2f}</span></div>"
            )
        payment_html = "".join(payment_lines)
        fiscal_html = ""
        if is_fiscal_active:
            qr_img = qrcode.make(
                o["verification_url"], image_factory=qrcode.image.svg.SvgPathImage
            )
            qr_buf = io.BytesIO()
            qr_img.save(qr_buf)
            qr_svg = qr_buf.getvalue().decode("utf-8")
            ref_label = "FBR INVOICE #" if o.get("authority") == "FBR" else "FISCAL INVOICE #"
            test_banner = (
                "<div class='test-banner'>TEST INVOICE — NOT FOR LIVE VERIFICATION</div>"
                if o["fiscal_status"] == "test_submitted"
                else ""
            )
            fiscal_html = (
                f"<div class='fiscal-box'>"
                f"{test_banner}"
                f"<div class='fiscal-ref'><strong>{ref_label}</strong><span>{escape(str(o.get('fiscal_reference') or ''))}</span></div>"
                f"<div class='qr-wrap'>{qr_svg}</div>"
                f"<p class='meta'>Authority: {escape(str(o.get('authority', '')))} · Status: {escape(o['fiscal_status'])}</p>"
                f"</div>"
            )

        created_str = datetime.fromtimestamp(
            o["created"], ZoneInfo(p["timezone"])
        ).isoformat(sep=" ", timespec="seconds")
        doc_title = "TAX INVOICE" if is_fiscal_active else "SALES RECEIPT"
        doc_label = "USIN / Inv #:" if is_fiscal_active else "Order #:"
        pos_row = (
            f"<div class='row'><span>POS ID:</span><span>{escape(str(pos_id))}</span></div>"
            f"<div class='row'><span>Authority:</span><span>{escape(str(o.get('authority', '')))}</span></div>"
            if (is_fiscal_active and pos_id)
            else ""
        )
        discount_row = (
            f"<div class='row'><span>Discount</span><span>-{o['discount'] / 100:.2f}</span></div>"
            if o.get("discount", 0) > 0
            else ""
        )
        return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Receipt {escape(o['code'])}</title>
<style>
  @page {{ size: 80mm auto; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Courier New', Courier, Consolas, monospace;
    background: #eef1f6;
    margin: 0;
    padding: 16px;
    color: #000000;
    font-size: 12px;
    line-height: 1.35;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .ticket {{
    width: 80mm;
    max-width: 100%;
    margin: 0 auto;
    background: #ffffff;
    padding: 5mm 4mm;
    box-shadow: 0 8px 24px rgba(0,0,0,.10);
  }}
  .center {{ text-align: center; }}
  .bold {{ font-weight: 700; }}
  h1 {{ font-size: 16px; font-weight: 700; margin: 0 0 3px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .doc-title {{ font-size: 13px; font-weight: 700; letter-spacing: 1px; margin: 6px 0 2px; text-align: center; }}
  .copy-tag {{ font-size: 11px; font-weight: 700; text-align: center; margin: 2px 0 4px; }}
  .meta {{ font-size: 11px; color: #000000; margin: 2px 0; }}
  .divider {{ border-top: 1px dashed #000000; margin: 7px 0; }}
  .double-divider {{ border-top: 1px solid #000000; border-bottom: 1px solid #000000; height: 3px; margin: 7px 0; }}
  .row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: 11.5px; margin: 2.5px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin: 4px 0; }}
  th {{ text-align: left; border-top: 1px dashed #000000; border-bottom: 1px dashed #000000; padding: 4px 2px; font-size: 10.5px; font-weight: 700; text-transform: uppercase; }}
  td {{ padding: 4px 2px; vertical-align: top; }}
  .num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .item-col {{ width: 46%; word-break: break-word; }}
  .qty-col {{ width: 12%; }}
  .rate-col {{ width: 20%; }}
  .amt-col {{ width: 22%; }}
  .item-note {{ font-size: 10px; font-style: italic; margin-top: 1px; }}
  .total-row {{ font-size: 14px; font-weight: 700; margin: 5px 0; padding: 5px 0; border-top: 1px solid #000000; border-bottom: 2px double #000000; }}
  .fiscal-box {{ margin-top: 8px; padding-top: 8px; border-top: 1px dashed #000000; text-align: center; }}
  .fiscal-ref {{ display: flex; flex-direction: column; gap: 2px; font-size: 11.5px; margin-bottom: 6px; }}
  .qr-wrap {{ margin: 4px 0; }}
  .qr-wrap svg {{ width: 124px; height: 124px; display: block; margin: 0 auto; }}
  .test-banner {{ border: 1px solid #000000; font-size: 10px; font-weight: 700; padding: 3px 5px; margin-bottom: 6px; }}
  .footer {{ text-align: center; margin-top: 10px; padding-top: 8px; border-top: 1px dashed #000000; font-size: 11px; }}
  .footer p {{ margin: 2px 0; }}
  .print-btn {{ display: block; width: 100%; margin-top: 14px; padding: 10px; border: 0; border-radius: 6px; background: #5b97e0; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; font-weight: 700; cursor: pointer; font-size: 13px; }}
  @media print {{
    body {{ background: #ffffff; padding: 0; margin: 0; }}
    .ticket {{ width: 76mm; margin: 0 auto; padding: 2mm 2mm 4mm; box-shadow: none; }}
    .no-print {{ display: none !important; }}
  }}
</style>
</head>
<body>
  <div class="ticket">
    <div class="center">
      <h1>{escape(p['name'])}</h1>
      {f"<p class='meta'>{escape(p['address'])}</p>" if p.get('address') else ""}
      {f"<p class='meta'>Tel: {escape(p['phone'])}</p>" if p.get('phone') else ""}
      {f"<p class='meta'>NTN / Reg: {escape(ntn)}</p>" if ntn else ""}
    </div>
    <div class="double-divider"></div>
    <div class="doc-title">{doc_title}</div>
    {"<div class='copy-tag'>*** DUPLICATE COPY ***</div>" if count else ""}
    <div class="divider"></div>
    <div class="row"><span>{doc_label}</span><span class="bold">{escape(o['code'])}</span></div>
    <div class="row"><span>Date:</span><span>{escape(created_str)}</span></div>
    <div class="row"><span>Cashier:</span><span>{escape(cashier_name)}</span></div>
    <div class="row"><span>Mode:</span><span>{escape(str(o.get('payment_mode', 'cash')).upper())}</span></div>
    {pos_row}
    <table>
      <thead><tr><th class="item-col">Item</th><th class="num qty-col">Qty</th><th class="num rate-col">Rate</th><th class="num amt-col">Amt</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="divider"></div>
    <div class="row"><span>Items / Total Qty</span><span>{len(o['lines'])} / {total_qty}</span></div>
    <div class="row"><span>Subtotal</span><span>{o['subtotal'] / 100:.2f}</span></div>
    {discount_row}
    <div class="row"><span>Sales Tax ({tax_rate_pct}%)</span><span>{o['tax'] / 100:.2f}</span></div>
    <div class="row total-row"><span>TOTAL (PKR)</span><span>{o['total'] / 100:.2f}</span></div>
    {f"<div class='divider'></div>{payment_html}" if payment_html else ""}
    {fiscal_html}
    <div class="footer">
      <p class="bold">Thank you for dining with us!</p>
      <p>Please come again</p>
      <p style="margin-top:6px;font-size:10px;">Powered by Techleeq POS</p>
    </div>
    <button class="print-btn no-print" onclick="window.print()">Print Receipt</button>
  </div>
  <script>
    if (window.self === window.top) {{
      window.addEventListener('load', function() {{
        setTimeout(function() {{ window.print(); }}, 150);
      }});
    }}
  </script>
</body>
</html>"""


@app.get("/inventory/low-stock")
def low(user=Depends(manager)):
    with db() as c:
        return [
            {**s, "available": s["quantity"] - reserved(c, s["id"])}
            for s in listing(c, "stock")
            if s["quantity"] - reserved(c, s["id"]) <= s["threshold"]
        ]


@app.get("/notifications")
def alerts(user=Depends(manager)):
    with db() as c:
        notifications(c)
        return listing(c, "notification")


@app.post("/notifications/{ident}/read")
def mark_read(ident: int, user=Depends(manager)):
    with db() as c:
        n = get(c, "notification", ident)
        n["read"] = True
        return save(c, "notification", n, ident)


class Supplier(Strict):
    name: str = Field(min_length=1)
    contact: str = ""
    active: bool = True


def inventory_catalog(path, kind, schema, dependency=inventory):
    def create(body: schema, user=Depends(dependency)):
        with db() as c:
            return write(c, kind, body.model_dump(), user)

    def update(ident: int, body: schema, user=Depends(dependency)):
        with db() as c:
            return write(c, kind, body.model_dump(), user, ident)

    def read(user=Depends(dependency)):
        with db() as c:
            return listing(c, kind)

    app.post(path, status_code=201)(create)
    app.put(path + "/{ident}")(update)
    app.get(path)(read)


inventory_catalog("/inventory/categories", "stock_category", CategoryEdit)
inventory_catalog("/suppliers", "supplier", Supplier)
inventory_catalog("/expenses/categories", "expense_category", CategoryEdit, manager)


class StockEdit(Stock):
    code: str
    category_id: int | None = None
    active: bool = True
    conversions: dict[str, int] = {}


@app.put("/inventory/items/{ident}")
def stock_edit(ident: int, body: StockEdit, user=Depends(inventory)):
    if any(v <= 0 for v in body.conversions.values()):
        fail("Conversions must be positive")
    with db() as c:
        if body.category_id:
            get(c, "stock_category", body.category_id)
        if any(
            s.get("code") == body.code and s["id"] != ident for s in listing(c, "stock")
        ):
            fail("Duplicate stock code", 409)
        s = get(c, "stock", ident)
        s.update(body.model_dump())
        return write(c, "stock", s, user, ident)


class PurchaseEntry(Purchase):
    supplier_id: int | None = None
    unit: str | None = None
    paid: int = Field(default=0, ge=0)
    recoverable_tax: int = Field(default=0, ge=0)
    purchased_at: float | None = None


@app.post("/inventory/purchases", status_code=201)
def buy(body: PurchaseEntry, user=Depends(inventory)):
    if body.paid > body.total_cost or body.recoverable_tax > body.total_cost:
        fail("Invalid payment or recoverable tax")
    with db() as c:
        if (
            body.recoverable_tax
            and user["role"] != "manager"
            and not prefs(c).get("recoverable_purchase_tax", False)
        ):
            fail("Manager must configure recoverable purchase tax", 403)
        s = get(c, "stock", body.stock_id)
        if body.supplier_id:
            get(c, "supplier", body.supplier_id)
        if any(
            p["supplier_reference"] == body.supplier_reference
            and p.get("supplier_id") == body.supplier_id
            for p in listing(c, "purchase")
        ):
            fail("Duplicate supplier invoice", 409)
        factor = (
            1
            if not body.unit or body.unit == s["unit"]
            else s.get("conversions", {}).get(body.unit)
        )
        if factor is None:
            fail("Unknown purchase unit")
        p = write(
            c,
            "purchase",
            {
                **body.model_dump(),
                "quantity": body.quantity * factor,
                "returned": False,
                "created": body.purchased_at or time.time(),
                "user_id": user["id"],
            },
            user,
        )
        movement(
            c,
            s,
            p["quantity"],
            body.total_cost - body.recoverable_tax,
            "purchase",
            user,
            p["id"],
        )
        notifications(c)
        return p


class Amount(Strict):
    amount: int = Field(gt=0)
    method: Literal["cash", "card", "bank"] = "cash"


@app.post("/inventory/purchases/{ident}/payments")
def purchase_payment(ident: int, body: Amount, user=Depends(inventory)):
    with db() as c:
        p = get(c, "purchase", ident)
        if p["returned"] or p["paid"] + body.amount > p["total_cost"]:
            fail("Invalid payment", 409)
        p["paid"] += body.amount
        write(c, "purchase", p, user, ident)
        return write(
            c,
            "supplier_payment",
            {**body.model_dump(), "purchase_id": ident, "created": time.time()},
            user,
        )


@app.post("/inventory/purchases/{ident}/return")
def purchase_return(ident: int, body: Reason, user=Depends(manager)):
    with db() as c:
        p = get(c, "purchase", ident)
        s = get(c, "stock", p["stock_id"])
        if p["returned"]:
            fail("Already returned", 409)
        if s["quantity"] - reserved(c, s["id"]) < p["quantity"]:
            fail("Stock already used or reserved", 409)
        cost = p["total_cost"] - p["recoverable_tax"]
        if s["value"] < cost:
            fail("Return cost exceeds remaining stock valuation", 409)
        movement(c, s, -p["quantity"], -cost, "supplier_return", user, ident)
        p["returned"] = True
        p["supplier_credit"] = p["paid"]
        p["return_reason"] = body.reason
        write(c, "purchase", p, user, ident)
        notifications(c)
        return p


class Adjustment(Reason):
    stock_id: int
    quantity: int
    added_value: int = Field(default=0, ge=0)


@app.post("/inventory/adjustments")
def propose_adjustment(body: Adjustment, user=Depends(inventory)):
    with db() as c:
        get(c, "stock", body.stock_id)
        return write(
            c,
            "adjustment",
            {
                **body.model_dump(),
                "status": "pending",
                "created": time.time(),
                "user_id": user["id"],
            },
            user,
        )


@app.post("/inventory/adjustments/{ident}/approve")
def approve_adjustment(ident: int, user=Depends(manager)):
    with db() as c:
        a = get(c, "adjustment", ident)
        s = get(c, "stock", a["stock_id"])
        if (
            a.get("expected_quantity") is not None
            and a["expected_quantity"] != s["quantity"]
        ):
            fail("Stock changed since count; recount before approval", 409)
        if a["status"] != "pending":
            fail("Already approved", 409)
        if s["quantity"] + a["quantity"] < reserved(c, s["id"]):
            fail("Adjustment conflicts with reserved stock", 409)
        value = (
            a["added_value"]
            if a["quantity"] >= 0
            else -(
                (s["value"] * (-a["quantity"]) + s["quantity"] // 2) // s["quantity"]
            )
        )
        movement(c, s, a["quantity"], value, "adjustment", user, ident)
        a.update(status="approved", value=value, approved_at=time.time())
        write(c, "adjustment", a, user, ident)
        notifications(c)
        return a


class ExpenseEntry(Expense):
    recoverable_tax: int = Field(default=0, ge=0)
    payee: str = ""
    paid: int = Field(default=0, ge=0)
    method: Literal["cash", "card", "bank"] = "cash"
    incurred_at: float | None = None


@app.post("/expenses", status_code=201)
def expense_create(body: ExpenseEntry, user=Depends(inventory)):
    if body.paid > body.amount or body.recoverable_tax > body.amount:
        fail("Payment exceeds expense")
    with db() as c:
        if (
            body.recoverable_tax
            and user["role"] != "manager"
            and not prefs(c).get("recoverable_expense_tax", False)
        ):
            fail("Manager must configure recoverable expense tax", 403)
        return write(
            c,
            "expense",
            {
                **body.model_dump(),
                "created": body.incurred_at or time.time(),
                "reversed": False,
                "user_id": user["id"],
            },
            user,
        )


@app.post("/expenses/{ident}/reverse")
def expense_reverse(ident: int, body: Reason, user=Depends(manager)):
    with db() as c:
        e = get(c, "expense", ident)
        if e["reversed"]:
            fail("Already reversed", 409)
        e["reversed"] = True
        e["reversed_at"] = time.time()
        e["reason"] = body.reason
        return write(c, "expense", e, user, ident)


@app.post("/expenses/{ident}/payments")
def expense_payment(ident: int, body: Amount, user=Depends(inventory)):
    with db() as c:
        e = get(c, "expense", ident)
        if e["reversed"] or e["paid"] + body.amount > e["amount"]:
            fail("Invalid expense payment", 409)
        e["paid"] += body.amount
        write(c, "expense", e, user, ident)
        return write(
            c,
            "expense_payment",
            {**body.model_dump(), "expense_id": ident, "created": time.time()},
            user,
        )


def ledger(path, kind):
    def read(
        start: float = 0,
        end: float = 1e20,
        category: str | None = None,
        payee: str | None = None,
        user_id: int | None = None,
        payment_status: Literal["paid", "partially_paid", "unpaid"] | None = None,
        user=Depends(inventory),
    ):
        with db() as c:
            return [
                r
                for r in listing(c, kind)
                if start <= r.get("created", 0) < end
                and (category is None or r.get("category") == category)
                and (payee is None or r.get("payee") == payee)
                and (user_id is None or r.get("user_id") == user_id)
                and (
                    payment_status is None
                    or payment_status
                    == (
                        "paid"
                        if r.get("paid", 0) >= r.get("amount", r.get("total_cost", 1))
                        else "partially_paid"
                        if r.get("paid", 0) > 0
                        else "unpaid"
                    )
                )
            ]

    app.get(path)(read)


for path, kind in [
    ("/expenses", "expense"),
    ("/inventory/purchases", "purchase"),
    ("/inventory/movements", "movement"),
    ("/inventory/adjustments", "adjustment"),
]:
    ledger(path, kind)


class ShiftOpen(Strict):
    opening_float: int = Field(ge=0)


@app.post("/shifts/open")
def open_shift(body: ShiftOpen, user=Depends(staff)):
    with db() as c:
        if any(
            s["cashier_id"] == user["id"] and s["closed"] is None
            for s in listing(c, "shift")
        ):
            fail("Shift already open", 409)
        return write(
            c,
            "shift",
            {
                "cashier_id": user["id"],
                "opened": time.time(),
                "closed": None,
                **body.model_dump(),
            },
            user,
        )


class Drawer(Reason):
    amount: int


@app.post("/shifts/{ident}/movements")
def drawer(ident: int, body: Drawer, user=Depends(staff)):
    with db() as c:
        s = get(c, "shift", ident)
        if s["closed"] or (user["role"] != "manager" and s["cashier_id"] != user["id"]):
            fail("Shift unavailable", 409)
        return write(
            c,
            "drawer",
            {**body.model_dump(), "shift_id": ident, "created": time.time()},
            user,
        )


class Close(Strict):
    counted_cash: int = Field(ge=0)


@app.post("/shifts/{ident}/close")
def close_shift(ident: int, body: Close, user=Depends(staff)):
    with db() as c:
        s = get(c, "shift", ident)
        if s["closed"] or (user["role"] != "manager" and s["cashier_id"] != user["id"]):
            fail("Shift unavailable", 409)
        movements = sum(
            d["amount"] for d in listing(c, "drawer") if d["shift_id"] == ident
        )
        receipts = sum(
            p["applied"]
            for p in listing(c, "payment")
            if p.get("shift_id") == ident and p["method"] == "cash"
        )
        refunds = sum(
            r["amount"]
            for r in listing(c, "refund")
            if r["method"] == "cash" and r.get("shift_id") == ident
        )
        s.update(
            closed=time.time(),
            counted_cash=body.counted_cash,
            expected_cash=s["opening_float"] + movements + receipts - refunds,
        )
        s["difference"] = body.counted_cash - s["expected_cash"]
        return write(c, "shift", s, user, ident)


@app.get("/shifts")
def shifts(user=Depends(staff)):
    with db() as c:
        return [
            s
            for s in listing(c, "shift")
            if user["role"] == "manager" or s["cashier_id"] == user["id"]
        ]


@app.get("/reports/dashboard")
def report(start: float = 0, end: float = 1e20, user=Depends(manager)):
    with db() as c:
        all_orders = listing(c, "order")
        recognized = [
            o
            for o in all_orders
            if o.get("recognized_at") is not None and start <= o["recognized_at"] < end
        ]
        cancelled = [
            o
            for o in all_orders
            if o.get("recognized_at") is not None
            and start <= o.get("cancelled_at", -1) < end
        ]
        refunds = [
            r
            for r in listing(c, "refund")
            if start <= r["created"] < end
            and not r.get("cancellation")
            and get(c, "order", r["order_id"]).get("recognized_at") is not None
        ]
        revenue = (
            sum(o["net"] for o in recognized)
            - sum(r["net"] for r in refunds)
            - sum(o["cancel_net"] for o in cancelled)
        )
        cost = sum(o.get("recognized_cost", o["cost"]) for o in recognized) - sum(
            o.get("recognized_cost", o["cost"]) for o in cancelled
        )
        loss = sum(o["cost"] for o in cancelled) - sum(
            a.get("value", 0)
            for a in listing(c, "adjustment")
            if a["status"] == "approved"
            and a.get("value", 0) < 0
            and start <= a.get("approved_at", a["created"]) < end
        )
        expenses = sum(
            e["amount"] - e.get("recoverable_tax", 0)
            for e in listing(c, "expense")
            if start <= e["created"] < end
        ) - sum(
            e["amount"] - e.get("recoverable_tax", 0)
            for e in listing(c, "expense")
            if e.get("reversed") and start <= e.get("reversed_at", e["created"]) < end
        )
        items = {}
        for o in recognized:
            if o["status"] == "cancelled":
                continue
            for l in o["lines"]:
                key = ("combo:" if l["combo_id"] else "item:") + str(
                    l["combo_id"] or l["item_id"]
                )
                entry = items.setdefault(
                    key, {"name": l["name"], "quantity": 0, "net_sales": 0}
                )
                entry["quantity"] += l["quantity"]
                entry["net_sales"] += l["net"]
        payments = [
            p for p in listing(c, "payment") if start <= p.get("created", 0) < end
        ]
        return {
            "net_sales": revenue,
            "cost_of_sales": cost,
            "expenses": expenses,
            "inventory_losses": loss,
            "gross_profit": revenue - cost,
            "operating_profit": revenue - cost - expenses - loss,
            "orders": len(recognized),
            "discounts": sum(o["discount"] for o in recognized),
            "refunds": sum(
                r["amount"] for r in listing(c, "refund") if start <= r["created"] < end
            ),
            "tax": sum(o["tax"] for o in recognized)
            - sum(r["tax"] for r in refunds)
            - sum(o["cancel_tax"] for o in cancelled),
            "outstanding": sum(
                max(0, o["total"] - o["paid"])
                for o in all_orders
                if o["status"] != "cancelled"
            ),
            "best_selling": sorted(items.values(), key=lambda x: -x["quantity"]),
            "costs_complete": all(l["recipe"] for o in recognized for l in o["lines"])
            and not any(
                o.get("uncosted_stock") or o.get("legacy_cost_detail_missing")
                for o in recognized
            ),
            "order_ids": [o["id"] for o in recognized],
            "tax_collected": sum(p.get("tax_collected", 0) for p in payments)
            - sum(
                r["tax"] for r in listing(c, "refund") if start <= r["created"] < end
            ),
            "expense_ids": [
                e["id"] for e in listing(c, "expense") if start <= e["created"] < end
            ],
            "refund_ids": [
                r["id"] for r in listing(c, "refund") if start <= r["created"] < end
            ],
            "payments_by_method": {
                method: sum(p["applied"] for p in payments if p["method"] == method)
                for method in ("cash", "card")
            },
        }


@app.get("/reports/export/{kind}")
def export(
    kind: Literal[
        "order",
        "purchase",
        "purchase_invoice",
        "purchase_return",
        "supplier_payment",
        "expense",
        "refund",
        "payment",
        "movement",
        "shift",
        "change",
    ],
    start: float = 0,
    end: float = 1e20,
    user=Depends(manager),
):
    with db() as c:
        rows = [
            r
            for r in listing(c, kind)
            if start <= r.get("created", r.get("opened", 0)) < end
        ]
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(
            output, fieldnames=sorted(set().union(*(r.keys() for r in rows)))
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: ("'" + str(v) if str(v).startswith(("=", "+", "-", "@")) else v)
                    for k, v in row.items()
                }
            )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'},
    )


@app.get("/reports/suppliers")
def supplier_balances(user=Depends(manager)):
    with db() as c:
        return [
            {
                "supplier_id": s["id"],
                "name": s["name"],
                "outstanding": sum(
                    p["total_cost"] - p["paid"]
                    for p in listing(c, "purchase")
                    if p.get("supplier_id") == s["id"] and not p["returned"]
                ),
            }
            for s in listing(c, "supplier")
        ]


@app.get("/audit/changes")
def changes(user=Depends(manager)):
    with db() as c:
        return listing(c, "change")


@app.get("/fiscal/submissions")
def fiscal_queue(user=Depends(manager)):
    with db() as c:
        return {
            "invoices": [
                {
                    "order_id": o["id"],
                    "authority": o["authority"],
                    "status": o["fiscal_status"],
                }
                for o in listing(c, "order")
            ],
            "credits": listing(c, "fiscal_credit"),
        }


@app.post("/fiscal/orders/{ident}/submit")
def fiscal_submit(ident: int, user=Depends(manager)):
    with db() as c:
        o = get(c, "order", ident)
        fail(
            f"{o['authority']} live connector requires approved configuration and credentials",
            409,
        )


@app.get("/displays/{screen}/events")
async def display_events(
    screen: Literal["customer", "preparation"], request: Request, user=Depends(current)
):
    if user["role"] not in ("manager", screen + "_display"):
        fail("Permission denied", 403)

    async def stream():
        previous = None
        while not await request.is_disconnected():
            # Revalidate session so logout and account deactivation revoke streams.
            try:
                current(request.headers.get("authorization", ""))
            except HTTPException:
                break
            data = customer_display(user) if screen == "customer" else preparation(user)
            serialized = json.dumps(data)
            if serialized != previous:
                yield "data: " + serialized + "\n\n"
                previous = serialized
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
