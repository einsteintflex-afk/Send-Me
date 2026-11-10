from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Address, Availability, Cart, CartItem, DeliveryAssignment, Order, OrderCounter, OrderItem,
                      OrderStatus, OrderStatusHistory, PaymentStatus, Product, ProductRequest, RequestStatus,
                      Rider, Shop, User)
from .notify import notify, notify_shop
from .pricing import delivery_fee
from .util import money

ALLOWED = {
    OrderStatus.pending: {OrderStatus.accepted, OrderStatus.cancelled},
    OrderStatus.accepted: {OrderStatus.shopping, OrderStatus.cancelled},
    OrderStatus.shopping: {OrderStatus.on_the_way, OrderStatus.cancelled},
    OrderStatus.on_the_way: {OrderStatus.delivered},
    OrderStatus.delivered: set(),
    OrderStatus.cancelled: set(),
}
STATUS_MESSAGES = {
    OrderStatus.accepted: ("order_accepted", "Order accepted", "The shop has accepted your order."),
    OrderStatus.shopping: ("order_preparing", "Order being prepared", "The shop is getting your items ready."),
    OrderStatus.on_the_way: ("order_dispatched", "Your order is on the way", "A rider is bringing your order."),
    OrderStatus.delivered: ("order_delivered", "Order delivered", "Your order has been delivered."),
    OrderStatus.cancelled: ("order_cancelled", "Order cancelled", "Your order was cancelled."),
}


def utcnow():
    return datetime.now(timezone.utc)


def next_order_number(db: Session) -> str:
    year = utcnow().year
    row = db.scalar(select(OrderCounter).where(OrderCounter.year == year).with_for_update())
    if not row:
        row = OrderCounter(year=year, last=0)
        db.add(row)
        db.flush()
    row.last += 1
    return f"SM-{year}-{row.last:06d}"


def snapshot_destination(addr: Address) -> dict:
    return {"kind": addr.kind, "label": addr.label, "hostel": addr.hostel, "block": addr.block, "room": addr.room,
            "place": addr.place, "campus_id": addr.campus_id}


def create_order_from_cart(db: Session, user: User, address_id: int, instructions: str | None,
                           idempotency_key: str | None) -> Order:
    if idempotency_key:
        existing = db.scalar(select(Order).where(Order.user_id == user.id, Order.idempotency_key == idempotency_key))
        if existing:
            return existing
    addr = db.get(Address, address_id)
    if not addr or addr.user_id != user.id:
        raise HTTPException(422, "Choose a delivery destination.")
    if addr.kind == "hostel" and not (addr.hostel and addr.room):
        raise HTTPException(422, "Add your hostel and room number.")
    if addr.kind != "hostel" and not addr.place:
        raise HTTPException(422, "Add the campus location for delivery.")

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    reqs = db.scalars(select(ProductRequest).where(
        ProductRequest.user_id == user.id, ProductRequest.in_cart.is_(True),
        ProductRequest.status.in_([RequestStatus.submitted, RequestStatus.priced]))).all()
    items = list(cart.items) if cart else []
    if not items and not reqs:
        raise HTTPException(422, "Your cart is empty.")

    shop_ids = {i.product.shop_id for i in items} | {r.shop_id for r in reqs}
    if len(shop_ids) != 1:
        raise HTTPException(409, "Your cart has items from different shops. Order from one shop at a time.")
    shop = db.get(Shop, shop_ids.pop())
    if not shop.active or not shop.accepting_orders:
        raise HTTPException(409, f"{shop.name} is not taking orders right now.")
    fee = delivery_fee(db, shop)
    if fee is None:
        raise HTTPException(409, "Delivery is not available yet because the delivery fee has not been set.")

    order = Order(user_id=user.id, shop_id=shop.id, destination=snapshot_destination(addr),
                  instructions=(instructions or None), idempotency_key=idempotency_key,
                  status=OrderStatus.pending, payment_status=PaymentStatus.awaiting)
    subtotal = Decimal("0")
    for ci in items:
        p: Product = ci.product
        unit = ci.variant.price if ci.variant and ci.variant.price is not None else p.price
        avail = ci.variant.availability if ci.variant else p.availability
        stock = ci.variant.stock_qty if ci.variant else p.stock_qty
        if not p.active or avail != Availability.available:
            raise HTTPException(409, f"{p.name} is not available right now. Remove it to continue.")
        if unit is None:
            raise HTTPException(409, f"{p.name} has no price yet. Remove it or request it as a special item.")
        if stock is not None and ci.quantity > stock:
            raise HTTPException(409, f"Only {stock} of {p.name} left.")
        subtotal += money(unit) * ci.quantity
        order.items.append(OrderItem(product_id=p.id, variant_id=ci.variant_id, name=p.name,
                                     variant_name=ci.variant.name if ci.variant else None,
                                     unit_price=money(unit), quantity=ci.quantity))
    for r in reqs:
        priced = r.status == RequestStatus.priced and r.confirmed_unit_price is not None
        if priced:
            subtotal += money(r.confirmed_unit_price) * r.quantity
            r.status = RequestStatus.approved  # checking out at the confirmed price is the student's approval
        order.items.append(OrderItem(request_id=r.id, name=r.name, quantity=r.quantity, is_request=True,
                                     unit_price=money(r.confirmed_unit_price) if priced else None))
        r.in_cart = False
    total = subtotal + fee
    if total <= 0:
        raise HTTPException(422, "Nothing to pay for yet.")
    order.subtotal, order.delivery_fee, order.total = money(subtotal), money(fee), money(total)
    order.history.append(OrderStatusHistory(status=OrderStatus.pending, note="Order created, awaiting payment",
                                            actor_id=user.id))
    db.add(order)
    db.flush()
    for r in reqs:
        r.order_id = order.id
    if cart:
        for ci in list(cart.items):
            db.delete(ci)
    return order


def can_view(user: User, order: Order, shop_id_of_user: int | None, rider_assigned: bool) -> bool:
    from ..models import Role
    if user.role == Role.super_admin:
        return True
    if user.role == Role.student:
        return order.user_id == user.id
    if user.role in (Role.shop_admin, Role.shop_staff):
        return shop_id_of_user == order.shop_id
    if user.role == Role.rider:
        return rider_assigned
    return False


def change_status(db: Session, order: Order, new: OrderStatus, actor: User, note: str | None = None) -> None:
    if new == order.status:
        return
    if new not in ALLOWED[order.status]:
        raise HTTPException(409, f"An order that is {order.status.value} cannot move to {new.value}.")
    if new != OrderStatus.cancelled and order.payment_status != PaymentStatus.paid:
        raise HTTPException(409, "This order has not been paid for yet.")
    if new == OrderStatus.on_the_way and not order.assignment:
        raise HTTPException(409, "Assign a rider before sending the order out.")
    order.status = new
    order.history.append(OrderStatusHistory(status=new, note=note, actor_id=actor.id))
    if new == OrderStatus.delivered and order.assignment:
        order.assignment.delivered_at = utcnow()
    if new == OrderStatus.cancelled:
        order.cancel_reason = note
        if order.payment_status == PaymentStatus.paid:
            order.payment_status = PaymentStatus.refund_pending  # refund is processed manually in Paystack
    kind, title, body = STATUS_MESSAGES[new]
    if new == OrderStatus.cancelled and note:
        body = f"{body} Reason: {note}"
    notify(db, order.user_id, kind, title, f"{body} ({order.number or '#'+str(order.id)})", order.id)


def assign_rider(db: Session, order: Order, rider_user_id: int, actor: User) -> None:
    if order.payment_status != PaymentStatus.paid:
        raise HTTPException(409, "This order has not been paid for yet.")
    if order.status in (OrderStatus.delivered, OrderStatus.cancelled):
        raise HTTPException(409, "This order is closed.")
    rider = db.get(Rider, rider_user_id)
    if not rider or not rider.active:
        raise HTTPException(404, "Rider not found.")
    shop = db.get(Shop, order.shop_id)
    if rider.campus_id != shop.campus_id:
        raise HTTPException(409, "This rider works on a different campus.")
    if order.assignment:
        order.assignment.rider_id = rider_user_id
        order.assignment.accepted_at = None
        order.assignment.failed_reason = None
    else:
        db.add(DeliveryAssignment(order_id=order.id, rider_id=rider_user_id))
    db.flush()
    db.refresh(order)
    notify(db, order.user_id, "rider_assigned", "Rider assigned", "A rider has been assigned to your order.", order.id)
    notify(db, rider_user_id, "delivery_assigned", "New delivery", f"You have a new delivery: {order.number}", order.id)
