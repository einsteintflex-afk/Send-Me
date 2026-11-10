from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, or_

from ..config import get_settings
from ..deps import DB, CurrentUser
from ..models import (Address, AuthToken, Campus, Role, StudentProfile, University, User)
from ..security import (decode_token, hash_password, hash_token, make_token, random_token, verify_password)
from ..services.notify import send_email
from ..services.util import normalize_gh_phone

router = APIRouter(prefix="/auth", tags=["auth"])
S = get_settings()


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    phone: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    university_id: int
    hostel: str = Field(min_length=1, max_length=200)
    block: str | None = Field(default=None, max_length=50)
    room: str = Field(min_length=1, max_length=50)


class LoginIn(BaseModel):
    identifier: str  # email or phone
    password: str


def tokens(user: User) -> dict:
    return {"access_token": make_token(user.id, "access", S.access_token_minutes),
            "refresh_token": make_token(user.id, "refresh", S.refresh_token_days * 24 * 60),
            "token_type": "bearer"}


def user_out(u: User, db=None) -> dict:
    out = {"id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone, "role": u.role.value,
           "email_verified": u.email_verified}
    if u.profile:
        out["university_id"] = u.profile.university_id
        out["notification_prefs"] = u.profile.notification_prefs
    return out


def _issue(db, user: User, purpose: str, minutes: int) -> str:
    raw = random_token()
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw),
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes)))
    return raw


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: DB):
    phone = normalize_gh_phone(body.phone)
    email = body.email.lower()
    if db.scalar(select(User).where(or_(User.email == email, User.phone == phone))):
        raise HTTPException(409, "An account with this email or phone number already exists.")
    uni = db.get(University, body.university_id)
    if not uni or not uni.active:
        raise HTTPException(422, "Choose your university.")
    user = User(email=email, phone=phone, full_name=body.full_name.strip(), password_hash=hash_password(body.password),
                role=Role.student)
    user.profile = StudentProfile(university_id=uni.id)
    db.add(user)
    db.flush()
    campus = db.scalar(select(Campus).where(Campus.university_id == uni.id, Campus.active.is_(True)))
    db.add(Address(user_id=user.id, campus_id=campus.id if campus else None, kind="hostel", label=body.hostel,
                   hostel=body.hostel, block=body.block, room=body.room, is_default=True))
    raw = _issue(db, user, "verify_email", 60 * 48)
    db.commit()
    send_email(user.email, "Verify your Send Me account", f"{S.frontend_url}/verify-email?token={raw}")
    return {"user": user_out(user), **tokens(user)}


@router.post("/login")
def login(body: LoginIn, db: DB):
    ident = body.identifier.strip()
    user = None
    if "@" in ident:
        user = db.scalar(select(User).where(User.email == ident.lower()))
    else:
        try:
            user = db.scalar(select(User).where(User.phone == normalize_gh_phone(ident)))
        except HTTPException:
            user = None
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "The email, phone number or password is not correct.")
    if not user.is_active:
        raise HTTPException(403, "This account has been suspended. Contact Send Me support.")
    return {"user": user_out(user), **tokens(user)}


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(body: RefreshIn, db: DB):
    uid = decode_token(body.refresh_token, "refresh")
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(401, "Please sign in again.")
    return tokens(user)


@router.get("/me")
def me(user: CurrentUser):
    return user_out(user)


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = None
    university_id: int | None = None
    notification_prefs: dict | None = None


@router.patch("/me")
def update_me(body: ProfileIn, user: CurrentUser, db: DB):
    if body.full_name:
        user.full_name = body.full_name.strip()
    if body.phone:
        phone = normalize_gh_phone(body.phone)
        other = db.scalar(select(User).where(User.phone == phone, User.id != user.id))
        if other:
            raise HTTPException(409, "That phone number is already used by another account.")
        user.phone = phone
    if user.profile:
        if body.university_id:
            if not db.get(University, body.university_id):
                raise HTTPException(422, "Choose your university.")
            user.profile.university_id = body.university_id
        if body.notification_prefs is not None:
            allowed = {"in_app", "push"}
            user.profile.notification_prefs = {k: bool(v) for k, v in body.notification_prefs.items() if k in allowed}
    db.commit()
    return user_out(user)


class TokenIn(BaseModel):
    token: str


def _consume(db, token: str, purpose: str) -> AuthToken:
    row = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(token), AuthToken.purpose == purpose))
    now = datetime.now(timezone.utc)
    exp = row.expires_at if row else None
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not row or row.used or exp < now:
        raise HTTPException(400, "This link is invalid or has expired. Request a new one.")
    row.used = True
    return row


@router.post("/verify-email")
def verify_email(body: TokenIn, db: DB):
    row = _consume(db, body.token, "verify_email")
    db.get(User, row.user_id).email_verified = True
    db.commit()
    return {"ok": True}


@router.post("/resend-verification")
def resend_verification(user: CurrentUser, db: DB):
    if user.email_verified:
        return {"ok": True}
    raw = _issue(db, user, "verify_email", 60 * 48)
    db.commit()
    send_email(user.email, "Verify your Send Me account", f"{S.frontend_url}/verify-email?token={raw}")
    return {"ok": True}


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: DB):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.is_active:
        raw = _issue(db, user, "reset_password", 60)
        db.commit()
        send_email(user.email, "Reset your Send Me password", f"{S.frontend_url}/reset-password?token={raw}")
    # Same answer either way so the endpoint cannot be used to discover accounts.
    return {"ok": True, "message": "If that email has an account, a reset link is on its way."}


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


@router.post("/reset-password")
def reset_password(body: ResetIn, db: DB):
    row = _consume(db, body.token, "reset_password")
    db.get(User, row.user_id).password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


# ---- saved delivery destinations ----
class AddressIn(BaseModel):
    kind: str = Field(default="hostel", pattern="^(hostel|pickup_point|other)$")
    label: str = Field(min_length=1, max_length=100)
    hostel: str | None = Field(default=None, max_length=200)
    block: str | None = Field(default=None, max_length=50)
    room: str | None = Field(default=None, max_length=50)
    place: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=300)
    campus_id: int | None = None
    is_default: bool = False


def addr_out(a: Address):
    return {c: getattr(a, c) for c in ("id", "kind", "label", "hostel", "block", "room", "place", "instructions",
                                       "campus_id", "is_default")}


@router.get("/addresses")
def list_addresses(user: CurrentUser, db: DB):
    return [addr_out(a) for a in db.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.id))]


@router.post("/addresses", status_code=201)
def add_address(body: AddressIn, user: CurrentUser, db: DB):
    if body.kind == "hostel" and not (body.hostel and body.room):
        raise HTTPException(422, "Enter the hostel and room number.")
    if body.kind != "hostel" and not body.place:
        raise HTTPException(422, "Enter the campus location.")
    if body.is_default:
        for a in db.scalars(select(Address).where(Address.user_id == user.id)):
            a.is_default = False
    a = Address(user_id=user.id, **body.model_dump())
    db.add(a)
    db.commit()
    return addr_out(a)


@router.put("/addresses/{aid}")
def edit_address(aid: int, body: AddressIn, user: CurrentUser, db: DB):
    a = db.get(Address, aid)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Destination not found.")
    if body.is_default:
        for o in db.scalars(select(Address).where(Address.user_id == user.id)):
            o.is_default = False
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    db.commit()
    return addr_out(a)


@router.delete("/addresses/{aid}", status_code=204)
def delete_address(aid: int, user: CurrentUser, db: DB):
    a = db.get(Address, aid)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Destination not found.")
    db.delete(a)
    db.commit()
