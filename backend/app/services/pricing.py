from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import DeliveryPricing, Shop


def delivery_fee(db: Session, shop: Shop) -> Decimal | None:
    """Most specific configured rule wins. None means the admin has not set a fee yet."""
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
