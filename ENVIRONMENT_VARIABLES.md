# Environment variables (`backend/.env`, template in `backend/.env.example`)

| Variable | Required | Purpose |
|---|---|---|
| `ENV` | no | `development`, `test` or `production`. Production refuses to start with the default JWT secret. |
| `DATABASE_URL` | yes in production | e.g. `postgresql+psycopg://user:pass@host:5432/sendme`. Defaults to local SQLite. |
| `JWT_SECRET` | yes in production | Long random string. Generate with `python -c "import secrets;print(secrets.token_urlsafe(48))"`. |
| `FRONTEND_URL` | yes | Used in email links and the Paystack return URL. |
| `CORS_ORIGINS` | yes | Comma-separated allowed browser origins. |
| `UPLOAD_DIR` | no | Where images are stored. Mount a persistent volume. |
| `PAYSTACK_SECRET_KEY` | for payments | `sk_test_...` for testing, `sk_live_...` for live. Server only. Never put in frontend code. |
| `GOOGLE_MAPS_API_KEY` | for distance pricing | Server-only key with **Routes API** and **Geocoding API** enabled. Without it, distance falls back to straight-line (labelled approximate). A separate, referrer-restricted browser key will be needed later for the map on the tracking screen. |
| `SEED_UNIVERSITY`, `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `SEED_ADMIN_PHONE` | first run | Used by `python -m app.seed`. |

## Paystack setup
1. Create a Paystack account and copy the **test** secret key.
2. Set `PAYSTACK_SECRET_KEY`.
3. In the Paystack dashboard set the webhook URL to `https://YOUR_API_DOMAIN/payments/webhook/paystack`.
4. Make a test payment with Paystack test credentials. Check `GET /health` shows `payments_configured: true`.
5. To go live, replace the key with `sk_live_...` and complete Paystack business verification. Until you have done a real test charge, treat payments as **unproven**.

## Google Maps setup
1. In Google Cloud, create a project, enable billing, and enable **Routes API** and **Geocoding API**.
2. Create an API key, restrict it to those two APIs (and to your server IP), and set `GOOGLE_MAPS_API_KEY`.
3. Preview where Google thinks the shop and hostels are: `POST /admin/geocode` with `{"area_hint": "<university name>"}`. It only previews.
4. Check each result on a map. Wrong ones can be fixed with `PUT /admin/hostels/{id}/location` and `PUT /admin/shops/{id}/location`. Then run `POST /admin/geocode` with `{"apply": true}` for the good ones, or set every point by hand.
5. Set the price: `PUT /admin/delivery-distance` with `{"rate_per_km": "...", "min_fee": "...", "travel_mode": "WALK"}`. Fee = route distance in km × rate, never below the minimum.
