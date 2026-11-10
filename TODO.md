# TODO

## Needs input from you (blocking real use)
- [ ] Product list with exact names and prices (CSV or pasted). Import with `python -m app.scripts.import_catalog`.
- [ ] UGMSA Mini Mart phone numbers.
- [ ] University name (seed uses a placeholder "University (set in admin)").
- [ ] Paystack account and test secret key (`PAYSTACK_SECRET_KEY`).
- [ ] Delivery fee amount (set in admin).
- [ ] Shop opening hours and typical delivery time.
- [ ] Real rider names and phones (create via admin).

## Next engineering tasks, in order
1. [ ] Run migrations and test suite against real PostgreSQL (`docker compose up db`).
2. [ ] Frontend: Next.js + TypeScript + Tailwind PWA. Student app first (welcome, register, home, explore, product, cart, request item, checkout, Paystack redirect and return, orders, tracking, account).
3. [ ] Frontend: shop dashboard (orders, products, requests, settings).
4. [ ] Frontend: rider screens.
5. [ ] Frontend: super admin.
6. [ ] Real email sending (SMTP or provider) replacing the console outbox in `services/notify.py`.
7. [ ] Push notifications (FCM or OneSignal) hook in `notify()`.
8. [ ] Automated Paystack refunds for `refund_pending` orders.
9. [ ] Move rate limiting to Redis if running more than one API instance.
10. [ ] Image storage on S3-compatible object storage instead of local disk.
11. [ ] Search upgrade (Postgres full-text or trigram) once the catalogue is large.
12. [ ] Mobile viewport tests on the frontend once it exists.
13. [ ] Security review pass and load test.
