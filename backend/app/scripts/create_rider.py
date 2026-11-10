"""Create a rider account. Usage:
python -m app.scripts.create_rider --name "Sammy" --phone 0264944652 --email sammy@example.com --password '...'
"""
import argparse
from sqlalchemy import select
from ..db import SessionLocal
from ..models import Campus, Rider, Role, User
from ..security import hash_password
from ..services.util import normalize_gh_phone

ap = argparse.ArgumentParser()
ap.add_argument("--name", required=True)
ap.add_argument("--phone", required=True)
ap.add_argument("--email", required=True)
ap.add_argument("--password", required=True)
ap.add_argument("--campus-id", type=int)
a = ap.parse_args()
with SessionLocal() as db:
    campus = db.get(Campus, a.campus_id) if a.campus_id else db.scalar(select(Campus))
    if not campus:
        raise SystemExit("No campus found. Run python -m app.seed first.")
    u = User(email=a.email.lower(), phone=normalize_gh_phone(a.phone), full_name=a.name, role=Role.rider,
             password_hash=hash_password(a.password), email_verified=True)
    db.add(u)
    db.flush()
    db.add(Rider(user_id=u.id, campus_id=campus.id))
    db.commit()
    print(f"Rider {u.full_name} created with phone {u.phone}.")
