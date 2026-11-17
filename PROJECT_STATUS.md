# Send Me: Project Status

Last updated: session 6. Read this first, then `TODO.md`.

## What exists and works
| Area | State |
|---|---|
| Backend API | Built. 67 automated tests pass (SQLite). |
| Student app | Built and tested in a phone-size browser: register, sign in, home, categories, shop page, search with suggestions and recent searches, product page, cart, unlisted-item requests, checkout with saved destinations, payment, confirmation, order history, live tracking map, account, notifications. |
| Shop dashboard | Built and tested: overview, accept/reject orders, prepare, assign rider, delivery monitor with live map, product management (price, availability, stock, options, photos), unlisted-item requests with instant pricing, settings. |
| Rider app | Built and tested: phone + password sign-in (no email), assigned deliveries, customer details and call, navigation link, accept / picked up / delivered / failed, GPS sharing while delivering. |
| Administrator dashboard | Built and tested: analytics, orders, payments, item requests, shops and staff, riders (create with phone only, reset password, suspend), students, delivery pricing and locations, catalogue, promotions, hostels, support, system status and launch checklist, audit log. |
| Catalogue | 88 UGMSA Mini Mart products (exact names and prices). Review notes in `CATALOG_REVIEW.md`. |
| Browser end-to-end | `frontend/e2e/platform.cjs` runs student -> shop -> rider -> tracking -> admin. Passed 5 of 5 consecutive runs after a test-locator fix. |

## What is simulated until you configure it (never silently)
| Service | Without config | Production |
|---|---|---|
| Payments | **Simulated checkout**, labelled "TEST MODE". Success only after the simulated page records it, then verified by the server. | Set `PAYSTACK_SECRET_KEY`; add webhook URL. Real Paystack has **never been run** here. |
| Maps / distance | OpenStreetMap map; straight-line distance (shown as approximate) | Set `GOOGLE_MAPS_API_KEY` |
| Delivery rate and locations | Demo values (banner shown) | Set in Admin > Delivery |
| Email | Written to the server log | Configure SMTP/provider |
| Push | Not available | Planned |

## Known gaps
- Not run on a real PostgreSQL server (SQLite only so far).
- Real Paystack and Google calls untested (no keys). Map screen uses OpenStreetMap; swap to Google Maps JS when a browser key exists.
- Refunds are manual (orders are flagged `refund_pending`).
- Email sending and push notifications not implemented.
- Product photos: none yet (honest placeholders shown). Shop can upload from the dashboard.
- Accessibility and low-bandwidth pass not done beyond basics. No automated unit tests for the frontend.
