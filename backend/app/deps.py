from typing import Annotated
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, ShopStaff, User
from .security import decode_token

DB = Annotated[Session, Depends(get_db)]


def current_user(db: DB, authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in to continue.")
    uid = decode_token(authorization[7:], "access")
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role):
    def dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You do not have access to this.")
        return user
    return dep


def shop_scope(db: Session, user: User, shop_id: int | None = None) -> int:
    """Return the shop this user may manage. Super admins must name the shop."""
    if user.role == Role.super_admin:
        if shop_id is None:
            raise HTTPException(400, "shop_id is required for administrators.")
        return shop_id
    if user.role in (Role.shop_admin, Role.shop_staff):
        link = db.scalar(select(ShopStaff).where(ShopStaff.user_id == user.id))
        if not link:
            raise HTTPException(403, "Your account is not linked to a shop.")
        if shop_id is not None and shop_id != link.shop_id:
            raise HTTPException(403, "You cannot manage another shop.")
        return link.shop_id
    raise HTTPException(403, "You do not have access to this.")


Student = Depends(require_roles(Role.student))
ShopUser = Depends(require_roles(Role.shop_admin, Role.shop_staff, Role.super_admin))
ShopAdminOnly = Depends(require_roles(Role.shop_admin, Role.super_admin))
RiderUser = Depends(require_roles(Role.rider))
SuperAdmin = Depends(require_roles(Role.super_admin))
