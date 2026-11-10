from .models import Order, Product, Shop, ProductVariant


def f(v):
    return None if v is None else float(v)


def variant_out(v: ProductVariant, base: Product):
    price = v.price if v.price is not None else base.price
    return {"id": v.id, "name": v.name, "price": f(price), "availability": v.availability.value,
            "orderable": price is not None and v.availability.value == "available"}


def product_out(p: Product, detail=False):
    orderable = p.active and p.price is not None and p.availability.value == "available"
    out = {"id": p.id, "shop_id": p.shop_id, "shop_name": p.shop.name, "category": p.category.slug,
           "category_name": p.category.name, "name": p.name, "price": f(p.price), "currency": "GHS",
           "image_url": p.image_url, "availability": p.availability.value if p.active else "unavailable",
           "price_listed": p.price is not None, "orderable": orderable or any(
               (v.price is not None or p.price is not None) and v.availability.value == "available"
               for v in p.variants) and p.active, "featured": p.featured,
           "has_variants": bool(p.variants)}
    if detail:
        out["description"] = p.description
        out["variants"] = [variant_out(v, p) for v in p.variants]
    return out


def shop_out(s: Shop):
    return {"id": s.id, "name": s.name, "slug": s.slug, "location": s.location, "phones": s.phones or [],
            "opening_hours": s.opening_hours or {}, "delivery_estimate_minutes": s.delivery_estimate_minutes,
            "accepting_orders": s.accepting_orders and s.active, "campus_id": s.campus_id}


def order_out(o: Order, include_rider=True):
    a = o.assignment
    rider = None
    if include_rider and a:
        rider = {"name": a.rider.user.full_name, "phone": a.rider.user.phone, "accepted": a.accepted_at is not None,
                 "lat": f(a.rider.last_lat), "lng": f(a.rider.last_lng)}
    out = {"id": o.id, "number": o.number, "status": o.status.value, "payment_status": o.payment_status.value,
           "shop": {"id": o.shop.id, "name": o.shop.name, "location": o.shop.location, "phones": o.shop.phones or []},
           "destination": o.destination, "instructions": o.instructions,
           "subtotal": f(o.subtotal), "delivery_fee": f(o.delivery_fee), "discount": f(o.discount), "total": f(o.total),
           "currency": "GHS", "estimated_arrival": o.estimated_arrival.isoformat() if o.estimated_arrival else None,
           "created_at": o.created_at.isoformat(), "cancel_reason": o.cancel_reason, "rider": rider,
           "items": [{"id": i.id, "name": i.name, "variant": i.variant_name, "unit_price": f(i.unit_price),
                      "quantity": i.quantity, "is_request": i.is_request, "request_id": i.request_id,
                      "line_total": f(i.unit_price * i.quantity) if i.unit_price is not None else None,
                      "needs_confirmation": i.is_request and i.unit_price is None} for i in o.items],
           "timeline": [{"status": h.status.value, "note": h.note, "at": h.created_at.isoformat()} for h in o.history]}
    return out
