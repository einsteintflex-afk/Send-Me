import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import admin, auth, cart, catalog, orders, rider, shop, support

settings = get_settings()
settings.validate_for_production()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("sendme")

app = FastAPI(title="Send Me API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_and_headers(request: Request, call_next):
    if request.url.path.startswith("/auth/") and request.method == "POST":
        ip = request.client.host if request.client else "?"
        now = time.time()
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_auth_per_minute:
            return JSONResponse({"detail": "Too many attempts. Wait a minute and try again."}, status_code=429)
        q.append(now)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


for r in (auth.router, catalog.router, cart.router, orders.router, shop.router, rider.router, admin.router, support.router):
    app.include_router(r)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health")
def health():
    return {"ok": True, "payments_configured": bool(settings.paystack_secret_key), "env": settings.env}
