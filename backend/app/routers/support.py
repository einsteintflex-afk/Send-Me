from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..deps import DB, CurrentUser, Student
from ..models import Complaint, Order

router = APIRouter(prefix="/support", tags=["support"], dependencies=[Student])


class ComplaintIn(BaseModel):
    message: str = Field(min_length=5, max_length=1000)
    order_id: int | None = None


@router.post("/complaints", status_code=201)
def file_complaint(body: ComplaintIn, user: CurrentUser, db: DB):
    if body.order_id:
        o = db.get(Order, body.order_id)
        if not o or o.user_id != user.id:
            raise HTTPException(404, "Order not found.")
    c = Complaint(user_id=user.id, order_id=body.order_id, message=body.message)
    db.add(c)
    db.commit()
    return {"id": c.id}
