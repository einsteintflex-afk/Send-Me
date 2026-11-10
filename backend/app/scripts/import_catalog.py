"""Import the shop's product list from CSV.

Columns (header row required): name,category,price,variant,availability,stock_qty,description
 - name and category (a category slug) are required. Names are kept exactly as written.
 - price blank means "no price supplied": the product is listed but cannot be ordered.
 - variant blank for single products. Several rows with the same name become variants of one product.
 - availability: available | unavailable (default available)
 - stock_qty blank means stock is not tracked.
Usage: python -m app.scripts.import_catalog path/to/catalog.csv --shop ugmsa-mini-mart [--dry-run]
"""
import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from ..db import SessionLocal
from ..models import Availability, Category, Product, ProductVariant, Shop


def run(db, path: str, shop_slug: str, dry: bool = False) -> dict:
    shop = db.scalar(select(Shop).where(Shop.slug == shop_slug))
    if not shop:
        raise SystemExit(f"Shop '{shop_slug}' not found. Run python -m app.seed first.")
    cats = {c.slug: c for c in db.scalars(select(Category))}
    errors, created, variants_added, unpriced = [], 0, 0, []
    groups: dict[str, list[tuple[int, dict]]] = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            name = (row.get("name") or "").strip()
            if not name:
                errors.append(f"line {n}: missing name")
                continue
            groups.setdefault(name, []).append((n, row))
    for name, rows in groups.items():
        first_n, first = rows[0]
        cat = cats.get((first.get("category") or "").strip())
        if not cat:
            errors.append(f"line {first_n}: unknown category '{first.get('category')}' for {name}")
            continue

        def parse(row, n):
            raw = (row.get("price") or "").strip().replace("GH₵", "").replace(",", "")
            price = None
            if raw:
                try:
                    price = Decimal(raw)
                    if price < 0:
                        raise InvalidOperation
                except InvalidOperation:
                    errors.append(f"line {n}: bad price '{row.get('price')}' for {name}")
                    return "ERR", None, None
            sq = (row.get("stock_qty") or "").strip()
            stock = int(sq) if sq.isdigit() else None
            av = Availability.unavailable if (row.get("availability") or "").strip().lower() == "unavailable" else Availability.available
            return price, stock, av

        p = db.scalar(select(Product).where(Product.shop_id == shop.id, Product.name == name))
        if not p:
            p = Product(shop_id=shop.id, category_id=cat.id, name=name, description=(first.get("description") or "").strip() or None)
            db.add(p)
            created += 1
        single = len(rows) == 1 and not (first.get("variant") or "").strip()
        if single:
            price, stock, av = parse(first, first_n)
            if price == "ERR":
                continue
            p.price, p.stock_qty, p.availability = price, stock, av
            if price is None:
                unpriced.append(name)
        else:
            for n, row in rows:
                vname = (row.get("variant") or "").strip()
                if not vname:
                    errors.append(f"line {n}: {name} has several rows, each needs a variant name")
                    continue
                price, stock, av = parse(row, n)
                if price == "ERR":
                    continue
                db.flush()
                v = db.scalar(select(ProductVariant).where(ProductVariant.product_id == p.id, ProductVariant.name == vname)) if p.id else None
                if not v:
                    v = ProductVariant(name=vname)
                    p.variants.append(v)
                    variants_added += 1
                v.price, v.stock_qty, v.availability = price, stock, av
                if price is None:
                    unpriced.append(f"{name} / {vname}")
    if errors or dry:
        db.rollback()
    else:
        db.commit()
    return {"created_products": created, "variants": variants_added, "without_price": unpriced, "errors": errors,
            "committed": not (errors or dry)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--shop", default="ugmsa-mini-mart")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    with SessionLocal() as s:
        res = run(s, a.csv, a.shop, a.dry_run)
    print(res)
    sys.exit(1 if res["errors"] else 0)
