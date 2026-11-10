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
| `SEED_UNIVERSITY`, `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `SEED_ADMIN_PHONE` | first run | Used by `python -m app.seed`. |

## Paystack setup
1. Create a Paystack account and copy the **test** secret key.
2. Set `PAYSTACK_SECRET_KEY`.
3. In the Paystack dashboard set the webhook URL to `https://YOUR_API_DOMAIN/payments/webhook/paystack`.
4. Make a test payment with Paystack test credentials. Check `GET /health` shows `payments_configured: true`.
5. To go live, replace the key with `sk_live_...` and complete Paystack business verification. Until you have done a real test charge, treat payments as **unproven**.
