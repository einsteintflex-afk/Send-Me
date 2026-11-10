from sqlalchemy.orm import Session
from ..models import AuditLog


def audit(db: Session, actor_id: int | None, action: str, target: str | None = None, detail: dict | None = None):
    db.add(AuditLog(actor_id=actor_id, action=action, target=target, detail=detail))
