# Send Me: Project Status

Last updated: session 2. Read this first, then `TODO.md`.

## Summary
| Area | State |
|---|---|
| Backend API (FastAPI, SQLAlchemy, Alembic) | Built. 52 automated tests pass on SQLite. |
| PostgreSQL | Schema and migration written. **Not yet run against a real Postgres server** (none available in the dev container). |
| Paystack payments | Implemented (initialize, verify, signed webhook, duplicate protection). Tested with a fake provider only. **Never run against real Paystack, test or live.** Needs your test key. |
| Student web app | **Not started.** Only the static design prototype `send-me.html` exists. It is not connected to the backend. |
| Shop, rider and admin web apps | **Not started.** The backend APIs for all three exist and are tested. |
| Push notifications | In-app notifications work. Push provider not wired. |
| Product catalogue | **Empty.** Product list was never supplied. Importer is ready: `backend/app/scripts/import_catalog.py`. |

## Definition-of-done journey, backend only
Register, login, saved destinations, browse, search, cart, unlisted request, checkout, payment, shop accept and prepare, rider assignment, rider delivery, order history and notifications are all covered by `tests/test_workflow.py` using a fake payment provider. A real provider transaction (step 10) has not been done.

## Business rules implemented
- Prices and stock are nullable. No price means the item is listed but cannot be ordered. No stock number means stock is not tracked.
- Delivery fee comes from admin settings (`PUT /admin/delivery-pricing`). Checkout is blocked until one is set.
- Order number `SM-YYYY-NNNNNN` is assigned only when payment is verified. Shops never see unpaid orders.
- Unlisted items are never given a price by the system. At checkout they are added unpriced. When the shop confirms a price, the student must approve and pay that amount separately.
- Statuses are exactly: Pending, Accepted, Shopping, On the Way, Delivered, Cancelled.
- Students can cancel only while Pending. A paid order that is cancelled becomes `refund_pending`. **Refunds are not automated.** Issue them in the Paystack dashboard.
- One shop per order.
