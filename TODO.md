# TODO

## Before production launch (you supply; nothing blocks development)
- [ ] `PAYSTACK_SECRET_KEY` (test first, then live) + webhook URL in Paystack, then make one real test payment.
- [ ] `GOOGLE_MAPS_API_KEY` (Routes + Geocoding), then Admin > Delivery > Preview/Apply and confirm each hostel and the shop on the map.
- [ ] Real price per km / minimum fee (Admin > Delivery). Demo values are placeholders.
- [ ] Real university name (Admin > Catalogue & promos > University).
- [ ] Create real riders in Admin > Riders (Sammy, 0264944652: name + phone + a password you choose; no email needed).
- [ ] Shop opening hours (Shop > Settings). Shop phones are already loaded.
- [ ] Review `CATALOG_REVIEW.md` items (duplicates, GH₵1.00 prices, Malta Guinness).
- [ ] Production server: `ENV=production`, strong `JWT_SECRET`, PostgreSQL, HTTPS, backups. Run `python -m app.seed` (not `seed_demo`).

## Engineering backlog
1. [ ] Run migrations and tests against real PostgreSQL.
2. [ ] Email provider (verification, password reset). Push notifications.
3. [ ] Automated Paystack refunds.
4. [ ] Google Maps JS tiles on the tracking/shop maps when a browser key exists.
5. [ ] Image storage on object storage (S3-compatible) instead of local disk.
6. [ ] Postgres full-text/trigram search for large catalogues.
7. [ ] Frontend unit tests; Lighthouse/low-bandwidth pass; accessibility audit.
8. [ ] Rate limiting on shared store (Redis) if running multiple API instances.
9. [ ] Security review and load test.
