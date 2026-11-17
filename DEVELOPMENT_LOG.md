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

## Session 5
- Riders can have no email (phone login). Admin can reset a password. Migration 0003.
- Distance pricing: fee = route km x admin rate (min fee optional). Google Routes API when keyed, straight-line fallback labelled approximate, flat-fee fallback. Distance cached. Stored on the order.
- Shop/hostel/address coordinates, admin geocode preview/apply, `/delivery/quote`, `/cart?address_id=`.
- Tracking API `GET /orders/{id}/tracking`: rider position only while On the Way, stale flag, private to the student. Rider GPS removed from generic order output.
- Unlisted requests now notify shop staff and all super admins at once; `/admin/requests` lists and prices across shops.
- 65 tests pass. Google was never called for real (no key). No real coordinates exist yet.

## Session 6 (approach change: build everything, no blocking on credentials)
- Backend: simulated checkout (MockProvider) when no Paystack key and ENV != production; demo seed (`python -m app.seed_demo`, dev only); `/config`, `/admin/integrations`, `/products/popular`; static serving of `frontend/dist`.
- Frontend (`frontend/`): Vite + React + TypeScript + Tailwind PWA, hash routing, Leaflet/OpenStreetMap map (no key). Student app done: auth, home, explore/shop, product, cart, request item, checkout, simulated payment, orders, live tracking, account, notifications.
- `frontend/e2e/student.cjs` drives the student journey in a phone-size browser. Passing.
