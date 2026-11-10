import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Notification, ShopStaff, StudentProfile

log = logging.getLogger("sendme.notify")
OUTBOX: list[dict] = []  # dev/test email outbox


def send_email(to: str, subject: str, body: str) -> None:
    """Console backend. Replace with SMTP/SES/SendGrid in production (see TODO.md)."""
    OUTBOX.append({"to": to, "subject": subject, "body": body})
    log.info("EMAIL to=%s subject=%s", to, subject)


def notify(db: Session, user_id: int, kind: str, title: str, body: str, order_id: int | None = None) -> None:
    prof = db.get(StudentProfile, user_id)
    if prof and prof.notification_prefs.get("in_app") is False:
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, order_id=order_id))
    # Push: add a provider call here (FCM/OneSignal) once configured. Stored notification is the source of truth.


def notify_shop(db: Session, shop_id: int, kind: str, title: str, body: str, order_id: int | None = None) -> None:
    for uid in db.scalars(select(ShopStaff.user_id).where(ShopStaff.shop_id == shop_id)):
        db.add(Notification(user_id=uid, kind=kind, title=title, body=body, order_id=order_id))
