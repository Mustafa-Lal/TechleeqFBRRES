"""Operational report detail with restaurant-local date boundaries."""

from datetime import date, timedelta
from app.features import *


@app.get("/reports/period")
def period_report(
    period: Literal["today", "week", "month"] = "today", user=Depends(manager)
):
    with db() as c:
        timezone = ZoneInfo(prefs(c)["timezone"])
    today = datetime.now(timezone).date()
    start = (
        today
        if period == "today"
        else today - timedelta(days=today.weekday())
        if period == "week"
        else today.replace(day=1)
    )
    start_at = datetime.combine(start, datetime.min.time(), timezone).timestamp()
    end_at = datetime.combine(
        today + timedelta(days=1), datetime.min.time(), timezone
    ).timestamp()
    return {"start": start_at, "end": end_at, **report(start_at, end_at, user)}


@app.get("/reports/operations")
def operations(start: float = 0, end: float = 1e20, user=Depends(manager)):
    with db() as c:
        orders = listing(c, "order")
        refunds = listing(c, "refund")
        payments = listing(c, "payment")
        expenses = listing(c, "expense")
        purchases = listing(c, "purchase")
        invoices = listing(c, "purchase_invoice")
        returns = listing(c, "purchase_return")
        timezone = ZoneInfo(prefs(c)["timezone"])
    by_id = {o["id"]: o for o in orders}
    trends = {}
    categories = {}
    promotions = {}

    def allocate(o, amount, timestamp):
        day = datetime.fromtimestamp(timestamp, timezone).date().isoformat()
        trends[day] = trends.get(day, 0) + amount
        remainder = amount
        for index, line in enumerate(o["lines"]):
            value = (
                remainder
                if index == len(o["lines"]) - 1
                else amount * line["net"] // max(o["net"], 1)
            )
            remainder -= value
            key = str(line["category_id"] or "combo")
            categories[key] = categories.get(key, 0) + value

    for o in orders:
        if o.get("recognized_at") is not None and start <= o["recognized_at"] < end:
            allocate(o, o["net"], o["recognized_at"])
            for line in o["lines"]:
                for discount in line["promotions"]:
                    promotions[str(discount["id"])] = (
                        promotions.get(str(discount["id"]), 0) + discount["amount"]
                    )
        if (
            o.get("recognized_at") is not None
            and start <= o.get("cancelled_at", -1) < end
        ):
            allocate(o, -o["cancel_net"], o["cancelled_at"])
    for refund in refunds:
        o = by_id[refund["order_id"]]
        if (
            o.get("recognized_at") is not None
            and not refund.get("cancellation")
            and start <= refund["created"] < end
        ):
            allocate(o, -refund["net"], refund["created"])
    expense_categories = {}
    for e in expenses:
        amount = e["amount"] - e.get("recoverable_tax", 0)
        effect = (amount if start <= e["created"] < end else 0) - (
            amount
            if e.get("reversed") and start <= e.get("reversed_at", e["created"]) < end
            else 0
        )
        expense_categories[e["category"]] = (
            expense_categories.get(e["category"], 0) + effect
        )
    return {
        "daily_net_sales": trends,
        "category_sales": categories,
        "promotion_discounts": promotions,
        "payments": {
            method: sum(
                p["applied"]
                for p in payments
                if p["method"] == method and start <= p.get("created", 0) < end
            )
            for method in ("cash", "card")
        },
        "expenses_by_category": expense_categories,
        "cancelled_orders": [
            o["id"] for o in orders if start <= o.get("cancelled_at", -1) < end
        ],
        "purchases": sum(
            p["total_cost"]
            for p in purchases
            if not p.get("returned") and start <= p["created"] < end
        )
        + sum(p["total"] for p in invoices if start <= p["created"] < end)
        - sum(
            sum(l["credit"] for l in r["lines"])
            for r in returns
            if start <= r["created"] < end
        ),
        "pending_fiscal": [
            o["id"]
            for o in orders
            if o["fiscal_status"] not in ("submitted", "test_submitted")
            and start <= o["created"] < end
        ],
    }
