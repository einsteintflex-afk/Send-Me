"""Relational schema for Send Me. Multi-shop, multi-campus from day one."""
import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text,
                        UniqueConstraint, CheckConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    student = "student"
    shop_admin = "shop_admin"
    shop_staff = "shop_staff"
    rider = "rider"
    super_admin = "super_admin"


# Exact statuses required by the product spec. Do not rename.
class OrderStatus(str, enum.Enum):
    pending = "Pending"
    accepted = "Accepted"
    shopping = "Shopping"
    on_the_way = "On the Way"
    delivered = "Delivered"
    cancelled = "Cancelled"


class PaymentStatus(str, enum.Enum):
    awaiting = "awaiting_payment"
    paid = "paid"
    failed = "failed"
    abandoned = "abandoned"
    refund_pending = "refund_pending"
    refunded = "refunded"


class Availability(str, enum.Enum):
    available = "available"
    unavailable = "unavailable"


class RequestStatus(str, enum.Enum):
    submitted = "submitted"        # waiting for shop
    rejected = "rejected"
    priced = "priced"              # shop confirmed price, waiting for student approval
    approved = "approved"          # student approved and paid
    declined = "declined"          # student declined the price


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class University(Base, TimestampMixin):
    __tablename__ = "universities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    campuses: Mapped[list["Campus"]] = relationship(back_populates="university")


class Campus(Base, TimestampMixin):
    __tablename__ = "campuses"
    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id"))
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    university: Mapped[University] = relationship(back_populates="campuses")
    __table_args__ = (UniqueConstraint("university_id", "name"),)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    profile: Mapped["StudentProfile | None"] = relationship(back_populates="user", uselist=False)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id"))
    notification_prefs: Mapped[dict] = mapped_column(JSON, default=lambda: {"in_app": True, "push": False})
    user: Mapped[User] = relationship(back_populates="profile")
    university: Mapped[University] = relationship()


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    campus_id: Mapped[int | None] = mapped_column(ForeignKey("campuses.id"))
    kind: Mapped[str] = mapped_column(String(20), default="hostel")  # hostel | pickup_point | other
    label: Mapped[str] = mapped_column(String(100))
    hostel: Mapped[str | None] = mapped_column(String(200))
    block: Mapped[str | None] = mapped_column(String(50))
    room: Mapped[str | None] = mapped_column(String(50))
    place: Mapped[str | None] = mapped_column(String(200))  # pickup point / alternative location
    instructions: Mapped[str | None] = mapped_column(String(300))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"
    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    location: Mapped[str | None] = mapped_column(String(300))
    phones: Mapped[list] = mapped_column(JSON, default=list)
    opening_hours: Mapped[dict] = mapped_column(JSON, default=dict)
    delivery_estimate_minutes: Mapped[int | None] = mapped_column(Integer)  # None = not configured
    accepting_orders: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    campus: Mapped[Campus] = relationship()


class ShopStaff(Base):
    __tablename__ = "shop_staff"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)


class Rider(Base, TimestampMixin):
    __tablename__ = "riders"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Reserved for GPS tracking. Nullable until a rider app reports a position.
    last_lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    last_lng: Mapped[float | None] = mapped_column(Numeric(9, 6))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    # NULL price means "not supplied". Such products cannot be ordered.
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    availability: Mapped[Availability] = mapped_column(Enum(Availability), default=Availability.available)
    # NULL stock means "not tracked". Never invent a number.
    stock_qty: Mapped[int | None] = mapped_column(Integer)
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    category: Mapped[Category] = relationship()
    shop: Mapped[Shop] = relationship()
    __table_args__ = (
        UniqueConstraint("shop_id", "name"),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_product_price_nonneg"),
        CheckConstraint("stock_qty IS NULL OR stock_qty >= 0", name="ck_product_stock_nonneg"),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    availability: Mapped[Availability] = mapped_column(Enum(Availability), default=Availability.available)
    stock_qty: Mapped[int | None] = mapped_column(Integer)
    product: Mapped[Product] = relationship(back_populates="variants")
    __table_args__ = (UniqueConstraint("product_id", "name"),)


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_cartitem_qty_pos"),)


class ProductRequest(Base, TimestampMixin):
    """A student asking a shop for something not in the catalogue."""
    __tablename__ = "product_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    image_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.submitted)
    in_cart: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    shop_note: Mapped[str | None] = mapped_column(String(300))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(20), unique=True)  # assigned when payment is verified
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, values_callable=lambda e: [m.value for m in e]),
                                                default=OrderStatus.pending, index=True)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.awaiting)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    # Address snapshot so later edits to saved addresses never change a past order.
    destination: Mapped[dict] = mapped_column(JSON)
    instructions: Mapped[str | None] = mapped_column(String(300))
    estimated_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    history: Mapped[list["OrderStatusHistory"]] = relationship(back_populates="order", cascade="all, delete-orphan",
                                                               order_by="OrderStatusHistory.id")
    shop: Mapped[Shop] = relationship()
    assignment: Mapped["DeliveryAssignment | None"] = relationship(back_populates="order", uselist=False)
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_order_idem"),)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    request_id: Mapped[int | None] = mapped_column(ForeignKey("product_requests.id"))
    # Snapshots at time of purchase
    name: Mapped[str] = mapped_column(String(300))
    variant_name: Mapped[str | None] = mapped_column(String(100))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # NULL until a request is priced
    quantity: Mapped[int] = mapped_column(Integer)
    is_request: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="order")  # order | request_topup
    request_id: Mapped[int | None] = mapped_column(ForeignKey("product_requests.id"))
    provider: Mapped[str] = mapped_column(String(20), default="paystack")
    reference: Mapped[str] = mapped_column(String(64), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GHS")
    status: Mapped[str] = mapped_column(String(20), default="initialized")  # initialized|success|failed|abandoned
    channel: Mapped[str | None] = mapped_column(String(30))
    provider_payload: Mapped[dict | None] = mapped_column(JSON)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    event_key: Mapped[str] = mapped_column(String(120))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("provider", "event_key"),)


class DeliveryAssignment(Base, TimestampMixin):
    __tablename__ = "delivery_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    rider_id: Mapped[int] = mapped_column(ForeignKey("riders.user_id"), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_reason: Mapped[str | None] = mapped_column(String(300))
    order: Mapped[Order] = relationship(back_populates="assignment")
    rider: Mapped[Rider] = relationship()


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, values_callable=lambda e: [m.value for m in e]))
    note: Mapped[str | None] = mapped_column(String(300))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    order: Mapped[Order] = relationship(back_populates="history")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),)


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    message: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Promotion(Base):
    __tablename__ = "promotions"
    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(ForeignKey("campuses.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeliveryPricing(Base):
    """Admin-configured delivery fee. Most specific rule wins: shop, then campus, then global."""
    __tablename__ = "delivery_pricing"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"))
    campus_id: Mapped[int | None] = mapped_column(ForeignKey("campuses.id"))
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    __table_args__ = (CheckConstraint("fee >= 0", name="ck_fee_nonneg"),)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class AuthToken(Base):
    """One-time tokens for email verification and password reset. Only the hash is stored."""
    __tablename__ = "auth_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # verify_email | reset_password
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    term: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrderCounter(Base):
    __tablename__ = "order_counters"
    year: Mapped[int] = mapped_column(primary_key=True)
    last: Mapped[int] = mapped_column(Integer, default=0)


Index("ix_products_name_lower", Product.name)
