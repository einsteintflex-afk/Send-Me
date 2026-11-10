from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from ..deps import DB
from ..models import (Availability, Campus, Category, Hostel, Product, Promotion, SearchLog, Shop, University)
from ..security import decode_token
from ..serializers import product_out, shop_out

router = APIRouter(tags=["catalog"])

# Common student spellings mapped to catalogue words. Extend as search logs show new ones.
SYNONYMS = {
    "coke": "coca-cola", "cocacola": "coca-cola", "coca cola": "coca-cola", "noodle": "indomie",
    "noodles": "indomie", "pad": "sanitary", "pads": "sanitary", "tp": "toilet", "pen": "pens",
    "slipper": "slippers", "sock": "socks", "biscuits": "biscuit", "egg": "eggs", "cereal": "cornflakes",
    "malt": "malt", "energy": "bullet", "juice": "fruit",
}


def expand(term: str) -> list[str]:
    t = term.strip().lower()
    out = {t}
    if t in SYNONYMS:
        out.add(SYNONYMS[t])
    for w in t.split():
        if w in SYNONYMS:
            out.add(SYNONYMS[w])
    return [o for o in out if o]


@router.get("/universities")
def universities(db: DB):
    return [{"id": u.id, "name": u.name, "campuses": [{"id": c.id, "name": c.name} for c in u.campuses if c.active]}
            for u in db.scalars(select(University).where(University.active.is_(True)).order_by(University.name))
            .unique()]


@router.get("/categories")
def categories(db: DB):
    return [{"id": c.id, "slug": c.slug, "name": c.name, "icon": c.icon} for c in
            db.scalars(select(Category).where(Category.active.is_(True)).order_by(Category.sort_order, Category.name))]


@router.get("/shops")
def shops(db: DB, campus_id: int | None = None):
    q = select(Shop).where(Shop.active.is_(True))
    if campus_id:
        q = q.where(Shop.campus_id == campus_id)
    return [shop_out(s) for s in db.scalars(q.order_by(Shop.name))]


@router.get("/shops/{shop_id}")
def shop_detail(shop_id: int, db: DB):
    s = db.get(Shop, shop_id)
    if not s or not s.active:
        raise HTTPException(404, "Shop not found.")
    return shop_out(s)


def _search_query(term: str | None, category: str | None, shop_id: int | None, availability: str | None):
    q = (select(Product).join(Category).join(Shop, Product.shop_id == Shop.id)
         .where(Product.active.is_(True), Shop.active.is_(True)))
    if shop_id:
        q = q.where(Product.shop_id == shop_id)
    if category:
        q = q.where(Category.slug == category)
    if availability == "available":
        q = q.where(Product.availability == Availability.available)
    if term:
        conds = []
        for t in expand(term):
            like = f"%{t}%"
            conds += [func.lower(Product.name).like(like), func.lower(Product.description).like(like),
                      func.lower(Category.name).like(like), func.lower(Shop.name).like(like)]
        q = q.where(or_(*conds))
    return q


@router.get("/products")
def products(db: DB, q: str | None = Query(default=None, max_length=100), category: str | None = None,
             shop_id: int | None = None, availability: str | None = None, featured: bool | None = None,
             limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
             authorization: str | None = Header(default=None)):
    query = _search_query(q, category, shop_id, availability)
    if featured:
        query = query.where(Product.featured.is_(True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.options(joinedload(Product.category), joinedload(Product.shop))
                      .order_by(Product.name).limit(limit).offset(offset)).unique().all()
    if q and q.strip() and offset == 0:
        uid = decode_token(authorization[7:], "access") if authorization and authorization.lower().startswith("bearer ") else None
        db.add(SearchLog(user_id=uid, term=q.strip().lower()[:100]))
        db.commit()
    return {"total": total, "items": [product_out(p) for p in rows]}


@router.get("/products/{pid}")
def product_detail(pid: int, db: DB):
    p = db.get(Product, pid)
    if not p or not p.active:
        raise HTTPException(404, "Product not found.")
    return product_out(p, detail=True)


@router.get("/search/suggestions")
def suggestions(db: DB, q: str = Query(min_length=1, max_length=100)):
    terms = expand(q)
    names: list[str] = []
    for t in terms:
        names += list(db.scalars(select(Product.name).where(Product.active.is_(True),
                                                            func.lower(Product.name).like(f"%{t}%")).limit(8)))
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    return seen[:8]


@router.get("/search/popular")
def popular(db: DB):
    rows = db.execute(select(SearchLog.term, func.count().label("n")).group_by(SearchLog.term)
                      .order_by(func.count().desc()).limit(8)).all()
    return [r[0] for r in rows]


@router.get("/promotions")
def promotions(db: DB):
    return [{"id": p.id, "title": p.title, "body": p.body, "image_url": p.image_url}
            for p in db.scalars(select(Promotion).where(Promotion.active.is_(True)))]


@router.get("/campuses/{campus_id}/hostels")
def hostels(campus_id: int, db: DB):
    return [{"id": h.id, "name": h.name} for h in db.scalars(
        select(Hostel).where(Hostel.campus_id == campus_id, Hostel.active.is_(True)).order_by(Hostel.sort_order, Hostel.id))]
