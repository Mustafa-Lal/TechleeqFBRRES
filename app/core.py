"""Local restaurant API. Money is stored in integer minor units (paisa)."""

from contextvars import ContextVar
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from pwdlib import PasswordHash

app = FastAPI(title="FIRRES Restaurant API", version="1.0.0")
passwords = PasswordHash.recommended()
audit_actor = ContextVar("audit_actor", default=None)
DB = os.getenv("DATABASE_PATH", "restaurant.db")
AUTHORITIES = {
    "punjab": "PRA",
    "sindh": "SRB",
    "khyber_pakhtunkhwa": "KPRA",
    "balochistan": "BRA",
    "islamabad": "FBR",
}


@contextmanager
def db():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.create_function("audit_actor", 0, lambda: audit_actor.get())
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='records'").fetchone():
            con.execute(
                "CREATE TABLE IF NOT EXISTS record_history(id INTEGER PRIMARY KEY, entity TEXT, record_id INTEGER, previous TEXT, current TEXT, user_id INTEGER, created REAL)"
            )
            con.execute(
                "CREATE TRIGGER IF NOT EXISTS record_update_audit AFTER UPDATE ON records WHEN NEW.kind NOT IN ('change','attachment') BEGIN INSERT INTO record_history(entity,record_id,previous,current,user_id,created) VALUES(NEW.kind,NEW.id,OLD.data,NEW.data,audit_actor(),unixepoch('subsec')); END"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS records_kind_index ON records(kind,id)"
            )
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), expires REAL);
        CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, kind TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), province TEXT, tax_bps INTEGER);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, record_id INTEGER, created REAL);
        """)


initialize()


def fail(message, code=400):
    raise HTTPException(code, message)


def get(c, kind, ident):
    row = c.execute(
        "SELECT data FROM records WHERE id=? AND kind=?", (ident, kind)
    ).fetchone()
    if not row:
        fail("Record not found", 404)
    return json.loads(row[0])


def save(c, kind, data, ident=None):
    if ident is None:
        ident = c.execute(
            "INSERT INTO records(kind,data) VALUES (?,?)", (kind, "{}")
        ).lastrowid
    data["id"] = ident
    c.execute(
        "UPDATE records SET data=? WHERE id=? AND kind=?",
        (json.dumps(data), ident, kind),
    )
    return data


def listing(c, kind):
    return [
        json.loads(r[0])
        for r in c.execute("SELECT data FROM records WHERE kind=? ORDER BY id", (kind,))
    ]


def audit(c, user, action, ident):
    c.execute(
        "INSERT INTO audit(user_id,action,record_id,created) VALUES(?,?,?,?)",
        (user["id"], action, ident, time.time()),
    )


def current(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ")
    with db() as c:
        row = c.execute(
            "SELECT u.id,u.username,u.role FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
        if not row:
            fail("Authentication required", 401)
        return dict(row)


def allow(*roles):
    def check(user=Depends(current)):
        if user["role"] not in roles:
            fail("Permission denied", 403)
        return user

    return check


manager = allow("manager")
staff = allow("manager", "cashier")
inventory = allow("manager", "entry_clerk")


class Login(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=10, max_length=128)


class UserCreate(Login):
    role: Literal[
        "manager", "cashier", "entry_clerk", "preparation_display", "customer_display"
    ]


@app.post("/auth/login")
def login(body: Login):
    uname = body.username.strip()
    with db() as c:
        row = c.execute(
            "SELECT * FROM users WHERE (username=? OR username=?) AND active=1",
            (uname, body.username),
        ).fetchone()
        if not row or not passwords.verify(body.password, row["password"]):
            fail("Invalid credentials", 401)
        token = secrets.token_urlsafe(48)
        c.execute(
            "INSERT INTO sessions VALUES (?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                row["id"],
                time.time() + 28800,
            ),
        )
        return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/logout")
def logout(authorization: str = Header(), user=Depends(current)):
    with db() as c:
        c.execute(
            "DELETE FROM sessions WHERE token=?",
            (
                hashlib.sha256(
                    authorization.removeprefix("Bearer ").encode()
                ).hexdigest(),
            ),
        )
    return {"logged_out": True}


@app.get("/auth/me")
def me(user=Depends(current)):
    return user


@app.post("/users", status_code=201)
def create_user(body: UserCreate, user=Depends(manager)):
    uname = body.username.strip()
    with db() as c:
        try:
            ident = c.execute(
                "INSERT INTO users(username,password,role) VALUES(?,?,?)",
                (uname, passwords.hash(body.password), body.role),
            ).lastrowid
        except sqlite3.IntegrityError:
            fail("Username already exists", 409)
        audit(c, user, "user_created", ident)
        return {"id": ident, "username": uname, "role": body.role}


class Settings(BaseModel):
    province: Literal[
        "punjab", "sindh", "khyber_pakhtunkhwa", "balochistan", "islamabad"
    ]
    tax_bps: int = Field(
        ge=0, le=10000, description="Official rate in basis points: 1000 = 10%"
    )


@app.put("/settings/tax")
def settings(body: Settings, user=Depends(manager)):
    with db() as c:
        c.execute(
            "INSERT OR REPLACE INTO settings VALUES(1,?,?)",
            (body.province, body.tax_bps),
        )
        audit(c, user, "tax_settings_changed", 1)
    return {
        **body.model_dump(),
        "authority": AUTHORITIES[body.province],
        "live_submission_enabled": False,
    }


class Category(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@app.post("/menu/categories", status_code=201)
def category(body: Category, user=Depends(manager)):
    with db() as c:
        return save(c, "category", body.model_dump())


class Ingredient(BaseModel):
    stock_id: int
    quantity: int = Field(
        gt=0, description="Quantity in the stock item's smallest unit"
    )


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category_id: int
    price: int = Field(ge=0, description="Paisa")
    active: bool = True
    available: bool = True
    code: str | None = None
    description: str = ""
    parent_item_id: int | None = None
    image_url: str | None = None
    recipe: list[Ingredient] = Field(default_factory=list)


@app.post("/menu/items", status_code=201)
def item(body: Item, user=Depends(manager)):
    with db() as c:
        get(c, "category", body.category_id)
        for ingredient in body.recipe:
            get(c, "stock", ingredient.stock_id)
        if body.parent_item_id:
            get(c, "item", body.parent_item_id)
        if body.code and any(i.get("code") == body.code for i in listing(c, "item")):
            fail("Duplicate item code", 409)
        result = save(c, "item", body.model_dump())
        result["code"] = body.code or f"ITEM-{result['id']}"
        return save(c, "item", result, result["id"])


@app.get("/menu/items")
def menu(user=Depends(staff)):
    with db() as c:
        return [
            {k: v for k, v in i.items() if k != "recipe"}
            for i in listing(c, "item")
            if i["active"]
            and i.get("available", True)
            and get(c, "category", i["category_id"]).get("active", True)
        ]


class Stock(BaseModel):
    code: str | None = None
    category_id: int | None = None
    active: bool = True
    conversions: dict[str, int] = {}
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    threshold: int = Field(ge=0)


@app.post("/inventory/items", status_code=201)
def stock(body: Stock, user=Depends(inventory)):
    with db() as c:
        if body.category_id is not None:
            get(c, "stock_category", body.category_id)
        if any(v <= 0 for v in body.conversions.values()):
            fail("Conversions must be positive")
        if body.code and any(s.get("code") == body.code for s in listing(c, "stock")):
            fail("Duplicate stock code", 409)
        s = save(c, "stock", {**body.model_dump(), "quantity": 0, "value": 0})
        s["code"] = body.code or f"STOCK-{s['id']}"
        return save(c, "stock", s, s["id"])


class Purchase(BaseModel):
    stock_id: int
    quantity: int = Field(gt=0)
    total_cost: int = Field(ge=0)
    supplier_reference: str = Field(min_length=1)


@app.post("/inventory/purchases", status_code=201)
def purchase(body: Purchase, user=Depends(inventory)):
    with db() as c:
        s = get(c, "stock", body.stock_id)
        s["quantity"] += body.quantity
        s["value"] += body.total_cost
        save(c, "stock", s, s["id"])
        result = save(
            c,
            "purchase",
            {**body.model_dump(), "created": time.time(), "user_id": user["id"]},
        )
        audit(c, user, "purchase", result["id"])
        return result


@app.get("/inventory/items")
def stocks(user=Depends(inventory)):
    with db() as c:
        return listing(c, "stock")


@app.get("/inventory/low-stock")
def low_stock(user=Depends(manager)):
    with db() as c:
        return [s for s in listing(c, "stock") if s["quantity"] <= s["threshold"]]


class Line(BaseModel):
    item_id: int
    quantity: int = Field(gt=0, le=1000)
    notes: str = Field(default="", max_length=500)


class Order(BaseModel):
    lines: list[Line] = Field(min_length=1, max_length=100)


@app.post("/orders", status_code=201)
def order(body: Order, user=Depends(staff)):
    with db() as c:
        cfg = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
        if not cfg:
            fail("Manager must configure tax jurisdiction first", 409)
        lines, subtotal = [], 0
        for line in body.lines:
            i = get(c, "item", line.item_id)
            if not i["active"]:
                fail("Item unavailable", 409)
            lines.append(
                {
                    **line.model_dump(),
                    "name": i["name"],
                    "price": i["price"],
                    "recipe": i["recipe"],
                }
            )
            subtotal += i["price"] * line.quantity
        tax = (subtotal * cfg["tax_bps"] + 5000) // 10000
        result = save(
            c,
            "order",
            {
                "cashier_id": user["id"],
                "created": time.time(),
                "status": "queued",
                "lines": lines,
                "subtotal": subtotal,
                "tax": tax,
                "total": subtotal + tax,
                "paid": 0,
                "cost": 0,
                "province": cfg["province"],
                "authority": AUTHORITIES[cfg["province"]],
                "tax_bps": cfg["tax_bps"],
                "fiscal_status": "not_configured",
            },
        )
        result["code"] = f"R{result['id']:06d}"
        save(c, "order", result, result["id"])
        audit(c, user, "order_created", result["id"])
        return result


def owned(c, ident, user, read=False):
    return get(c, "order", ident)


@app.get("/orders")
def orders(user=Depends(staff)):
    with db() as c:
        return [
            o
            for o in listing(c, "order")
            if user["role"] == "manager" or o["cashier_id"] == user["id"]
        ]


class Payment(BaseModel):
    amount: int = Field(gt=0)
    method: Literal["cash", "card"]
    reference: str = Field(
        default_factory=lambda: secrets.token_urlsafe(16), min_length=1, max_length=100
    )


@app.post("/orders/{ident}/payments")
def pay(ident: int, body: Payment, user=Depends(staff)):
    with db() as c:
        o = owned(c, ident, user)
        if o["status"] == "cancelled":
            fail("Order cancelled", 409)
        for p in listing(c, "payment"):
            if p["reference"] == body.reference:
                fail("Payment reference already recorded", 409)
        if (
            o.get("payment_mode") in ("cash", "card")
            and body.method != o["payment_mode"]
        ):
            fail("Payment method differs from invoice tax basis", 409)
        due = o["total"] - o["paid"]
        if due <= 0 or (body.method == "card" and body.amount > due):
            fail("Invalid payment amount", 409)
        applied = min(due, body.amount)

        def collected(paid):
            return (
                paid
                - (o.get("net", o["subtotal"]) * paid + o["total"] // 2) // o["total"]
            )

        tax_collected = collected(o["paid"] + applied) - collected(o["paid"])
        p = save(
            c,
            "payment",
            {
                **body.model_dump(),
                "order_id": ident,
                "applied": applied,
                "tax_collected": tax_collected,
                "change": body.amount - applied,
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
        )
        o["paid"] += applied
        save(c, "order", o, ident)
        audit(c, user, "payment", p["id"])
        return p


class Status(BaseModel):
    status: Literal["preparing", "ready", "collected"]


@app.post("/orders/{ident}/status")
def transition(ident: int, body: Status, user=Depends(staff)):
    with db() as c:
        o = owned(c, ident, user)
        if {"queued": "preparing", "preparing": "ready", "ready": "collected"}.get(
            o["status"]
        ) != body.status:
            fail("Invalid status transition", 409)
        if body.status == "preparing":
            if o["paid"] != o["total"]:
                fail("Payment required before preparation", 409)
            for line in o["lines"]:
                for r in line["recipe"]:
                    s = get(c, "stock", r["stock_id"])
                    qty = r["quantity"] * line["quantity"]
                    if s["quantity"] < qty:
                        fail("Insufficient stock: " + s["name"], 409)
                    cost = (s["value"] * qty + s["quantity"] // 2) // s["quantity"]
                    s["quantity"] -= qty
                    s["value"] -= cost
                    o["cost"] += cost
                    save(c, "stock", s, s["id"])
        o["status"] = body.status
        audit(c, user, body.status, ident)
        return save(c, "order", o, ident)


@app.get("/displays/customer")
def customer_display(user=Depends(allow("manager", "customer_display"))):
    with db() as c:
        return [
            {
                "code": o["code"],
                "status": "ready" if o["status"] == "ready" else "preparing",
            }
            for o in listing(c, "order")
            if o["status"] in ("queued", "preparing", "ready")
        ]


@app.get("/displays/preparation")
def preparation(user=Depends(allow("manager", "preparation_display"))):
    with db() as c:
        return [
            {
                "code": o["code"],
                "status": o["status"],
                "notes": o.get("notes", ""),
                "elapsed_seconds": int(time.time() - o["created"]),
                "lines": [
                    {
                        **{k: l[k] for k in ("name", "quantity", "notes")},
                        "components": l.get("components", []),
                    }
                    for l in o["lines"]
                ],
            }
            for o in listing(c, "order")
            if o["status"] in ("queued", "preparing")
        ]


class Expense(BaseModel):
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    amount: int = Field(gt=0)


@app.post("/expenses", status_code=201)
def expense(body: Expense, user=Depends(inventory)):
    with db() as c:
        return save(
            c,
            "expense",
            {**body.model_dump(), "created": time.time(), "user_id": user["id"]},
        )


@app.get("/reports/dashboard")
def dashboard(user=Depends(manager)):
    with db() as c:
        sold = [
            o
            for o in listing(c, "order")
            if o["status"] in ("preparing", "ready", "collected")
        ]
        revenue = sum(o["subtotal"] for o in sold)
        cost = sum(o["cost"] for o in sold)
        expenses = sum(e["amount"] for e in listing(c, "expense"))
        return {
            "net_sales": revenue,
            "cost_of_sales": cost,
            "expenses": expenses,
            "gross_profit": revenue - cost,
            "operating_profit": revenue - cost - expenses,
            "orders": len(sold),
            "costs_complete": all(l["recipe"] for o in sold for l in o["lines"]),
        }


@app.get("/audit")
def history(user=Depends(manager)):
    with db() as c:
        return [
            dict(r)
            for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 1000")
        ]


@app.get("/health")
def health():
    return {"status": "ok"}
