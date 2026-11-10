# Development Log

## Session 1
- Delivered a static HTML design prototype (`send-me.html`). No backend.

## Session 2
- Inspected repo: only README, LICENSE and the prototype. Product list and shop phone numbers were not in the repo.
- Chose FastAPI + SQLAlchemy 2 + Alembic. Tests run on SQLite, production targets PostgreSQL.
- Built: config, security (Argon2, JWT access/refresh), 5 roles, full relational schema (35 tables incl. multi-shop, snapshots, audit log), migration `0001`.
- Built routers: auth (register, login, refresh, verify email, password reset, saved addresses), catalog and search (synonyms, suggestions, popular), cart and unlisted requests, checkout and orders, payments (Paystack), notifications, shop dashboard API, rider API, super-admin API, complaints.
- Added: rate limiting on `/auth/*`, security headers, secure image upload (size and magic-byte checks), audit log.
- Tests: 52 passing (auth, shopping, orders, payments, webhooks, unlisted requests, cancellation, rider flow, permissions, admin, catalog import).
- Not done: all frontends, Postgres run, real Paystack run, push notifications, email delivery.

## Session 3
- Added hostel list (D block(College of health sciences student hostel), B- block, R-block, BQ, M-block, N- block) stored exactly as supplied. `GET /campuses/{id}/hostels`, admin add/hide, migration 0002, seeded.
- Added `app/scripts/create_rider.py`. Sammy's account not created yet (needs email and password).

## Session 4
- Received product table and shop phones. Built `ugmsa_catalog.csv` (88 products, exact names/prices, untracked stock left blank). Seed now sets shop phones and a Frozen & Chilled category. Added import test. `CATALOG_REVIEW.md` lists items to confirm.
