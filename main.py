"""INFRASURE 2027 — FastAPI app entry point."""
import os
import time

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from ratelimit import limiter
from security import CSRFProtectMiddleware, SecurityHeadersMiddleware
from site_config import BASE_DIR, SITE_CONFIG


def _warn_insecure_proxy_defaults() -> None:
    """Fail-secure startup warning for the X-Forwarded-For trust default.

    uvicorn enables ProxyHeadersMiddleware with ``forwarded_allow_ips``
    defaulting to 127.0.0.1, so a local client can spoof ``X-Forwarded-For``
    and reset the rate limiter's IP key. When not fronted by a trusted proxy
    this must be disabled (``--no-proxy-headers``); when fronted by one, the
    proxy's IP must be listed explicitly in ``FORWARDED_ALLOW_IPS``.
    """
    allow = (os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1") or "").strip()
    if not allow or allow == "127.0.0.1":
        print(
            "\n[SECURITY] uvicorn is trusting X-Forwarded-For from "
            f"{allow or '<none>'!r}. Rate limits are spoofable. Run with "
            "`--no-proxy-headers` (no proxy) or set FORWARDED_ALLOW_IPS to the "
            "trusted proxy IP only (proxy in front).\n"
        )


_warn_insecure_proxy_defaults()

app = FastAPI(
    title=SITE_CONFIG["name"],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.state.limiter = limiter
limiter._exempt_routes.add("starlette.staticfiles.StaticFiles")
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CSRFProtectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/media", StaticFiles(directory=os.path.join(BASE_DIR, "media")), name="media")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

from app_routes import admin_routes, auth_routes, incharge_routes, pdf_routes, public, reviewer_routes, student_routes  # noqa: E402
from app_routes.utils import base_ctx  # noqa: E402
from auth import Redirect  # noqa: E402
from site_config import templates  # noqa: E402

app.include_router(public.router)
app.include_router(auth_routes.router)
app.include_router(student_routes.router)
app.include_router(incharge_routes.router)
app.include_router(reviewer_routes.router)
app.include_router(admin_routes.router)
app.include_router(pdf_routes.router)


@app.exception_handler(Redirect)
def redirect_handler(request, exc: Redirect):
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded(request, exc: RateLimitExceeded):
    resp = templates.TemplateResponse(request, "429.html", base_ctx(request), status_code=429)
    try:
        retry_after = max(1, int(exc.limit.limit.get_expiry() - time.time()))
    except (AttributeError, TypeError):
        retry_after = 60
    resp.headers["Retry-After"] = str(retry_after)
    return resp


@app.exception_handler(404)
async def not_found(request, exc):
    return templates.TemplateResponse(request, "404.html", base_ctx(request), status_code=404)


@app.get("/health")
def health():
    return {"status": "ok"}