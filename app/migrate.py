"""Idempotent migration of the first prototype's JSON snapshots. Back up first."""

from pathlib import Path
import sqlite3
from app import core


def migrate():
    path = Path(core.DB)
    backup = path.with_name(path.name + ".pre-v2.bak")
    if path.exists() and not backup.exists():
        with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
            source.backup(target)
    with core.db() as c:
        for o in core.listing(c, "order"):
            if "net" in o:
                continue
            o.update(
                net=o["subtotal"],
                discount=0,
                refunded=0,
                refund_net=0,
                refund_tax=0,
                consumption=[],
                receipt_count=0,
                payment_mode="cash",
                notes="",
                legacy_cost_detail_missing=True,
            )
            for l in o["lines"]:
                gross = l["price"] * l["quantity"]
                tax = (gross * o["tax_bps"] + 5000) // 10000
                l.update(
                    combo_id=None,
                    category_id=None,
                    components=[],
                    gross=gross,
                    discount=0,
                    promotions=[],
                    net=gross,
                    tax=tax,
                    total=gross + tax,
                )
            o["tax_rule"] = {
                "province": o["province"],
                "authority": o["authority"],
                "tax_bps": o["tax_bps"],
                "source": "Legacy invoice snapshot",
                "inclusive": False,
                "effective_from": o["created"],
            }
            core.save(c, "order", o, o["id"])
        for kind, defaults in [
            ("expense", {"reversed": False, "paid": 0}),
            ("purchase", {"paid": 0, "returned": False, "recoverable_tax": 0}),
        ]:
            for r in core.listing(c, kind):
                for k, v in defaults.items():
                    r.setdefault(k, v)
                core.save(c, kind, r, r["id"])
        c.execute("PRAGMA user_version=2")
    return str(backup)


if __name__ == "__main__":
    print("Migration complete. Backup:", migrate())
