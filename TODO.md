# TODO

## Needs input from you (blocking real use)
- [x] Product list received and converted (`backend/data/ugmsa_catalog.csv`). Review items in `CATALOG_REVIEW.md`. Run: `python -m app.scripts.import_catalog data/ugmsa_catalog.csv`.
- [ ] UGMSA Mini Mart phone numbers.
- [ ] University name (seed uses a placeholder "University (set in admin)").
- [ ] Paystack account and test secret key (`PAYSTACK_SECRET_KEY`).
- [ ] Delivery fee amount (set in admin).
- [ ] Shop opening hours and typical delivery time.
- [ ] Sammy (rider), phone 0264944652: needs an email and a password to create the login. Run `python -m app.scripts.create_rider --name Sammy --phone 0264944652 --email ... --password ...` or use `POST /admin/riders`.
- [x] Confirmed: 0264944652 is Sammy's (rider) number, not the shop's.
- [x] UGMSA Mini Mart phones received: 0576966929, 0546504543 (seeded).

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
