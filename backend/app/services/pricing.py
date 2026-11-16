from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Address, DeliveryPricing, DistanceCache, Hostel, Shop, SystemSetting
from .maps import MapsError, get_maps, haversine_meters
from .util import money

SETTING_KEY = "delivery_distance"
MODES = {"WALK", "DRIVE", "TWO_WHEELER"}


def flat_fee(db: Session, shop: Shop) -> Decimal | None:
    """Most specific configured flat rule wins. None means the admin has not set one."""
    rules = db.scalars(select(DeliveryPricing).where(
        (DeliveryPricing.shop_id == shop.id) |
        ((DeliveryPricing.shop_id.is_(None)) & (DeliveryPricing.campus_id == shop.campus_id)) |
        ((DeliveryPricing.shop_id.is_(None)) & (DeliveryPricing.campus_id.is_(None))))).all()
    for pick in (lambda r: r.shop_id == shop.id, lambda r: r.campus_id == shop.campus_id and r.shop_id is None,
                 lambda r: r.shop_id is None and r.campus_id is None):
        for r in rules:
            if pick(r):
                return r.fee
    return None


delivery_fee = flat_fee  # backwards-compatible name


def distance_settings(db: Session) -> dict | None:
    row = db.get(SystemSetting, SETTING_KEY)
    if row and row.value.get("rate_per_km") not in (None, ""):
        return row.value
    return None


def dest_coords(db: Session, addr_like) -> tuple[float, float] | None:
    """addr_like is an Address or an order destination dict."""
    get = addr_like.get if isinstance(addr_like, dict) else (lambda k: getattr(addr_like, k, None))
    lat, lng = get("latitude"), get("longitude")
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    hid = get("hostel_id")
    h = db.get(Hostel, hid) if hid else None
    if h and h.latitude is not None and h.longitude is not None:
        return float(h.latitude), float(h.longitude)
    return None


def _key(lat, lng):
    return f"{float(lat):.5f},{float(lng):.5f}"


def route_distance(db: Session, o, d, mode: str) -> tuple[float, str]:
    """Return (km, method). Uses Google when configured, otherwise straight-line distance."""
    ok, dk = _key(*o), _key(*d)
    cached = db.scalar(select(DistanceCache).where(DistanceCache.origin_key == ok, DistanceCache.dest_key == dk,
                                                   DistanceCache.mode == mode))
    if cached:
        return cached.meters / 1000, "google"
    try:
        meters = get_maps().route_meters(o[0], o[1], d[0], d[1], mode)
    except MapsError:
        return haversine_meters(o[0], o[1], d[0], d[1]) / 1000, "straight_line"
    try:
        with db.begin_nested():
            db.add(DistanceCache(origin_key=ok, dest_key=dk, mode=mode, meters=meters))
    except IntegrityError:
        pass
    return meters / 1000, "google"


def quote_delivery(db: Session, shop: Shop, addr_like) -> dict | None:
    """Delivery fee for this shop and destination.
    Distance pricing (rate per km set by admin) when both locations are known, else the flat fee, else None."""
    cfg = distance_settings(db)
    dest = dest_coords(db, addr_like) if addr_like is not None else None
    if cfg and dest and shop.latitude is not None and shop.longitude is not None:
        mode = cfg.get("travel_mode", "WALK")
        km, method = route_distance(db, (float(shop.latitude), float(shop.longitude)), dest, mode)
        fee = money(Decimal(str(km)) * Decimal(str(cfg["rate_per_km"])))
        if cfg.get("min_fee") not in (None, ""):
            fee = max(fee, money(cfg["min_fee"]))
        return {"fee": fee, "distance_km": round(km, 3), "method": method}
    flat = flat_fee(db, shop)
    if flat is not None:
        return {"fee": flat, "distance_km": None, "method": "flat"}
    return None
