"""Security middleware: security response headers + CSRF protection.

Headers follow OWASP guidance. CSRF uses the synchronizer / double-submit
pattern: a random ``csrf_token`` cookie is set (HttpOnly, SameSite=lax) and
every state-changing form embeds the same value in a hidden field; on POST /
PUT / PATCH / DELETE the submitted token must match the cookie.

Cookie hardening (Secure / HSTS) is enabled when ``ENV=production`` or
``SESSION_COOKIE_SECURE=1`` so local http development keeps working.
"""
import os
import re
import secrets
from urllib.parse import parse_qs

from dotenv import load_dotenv
from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.responses import PlainTextResponse

load_dotenv()

CSRF_COOKIE = "csrf_token"

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'"
)


def _secure_cookies() -> bool:
    env = (os.getenv("ENV") or "").strip().lower()
    return env == "production" or (os.getenv("SESSION_COOKIE_SECURE") or "").strip() == "1"


class SecurityHeadersMiddleware:
    """Attach security headers to every HTTP response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Frame-Options"] = "DENY"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Content-Security-Policy"] = CSP
                if _secure_cookies():
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _csrf_cookie_header(token: str) -> str:
    secure = "; Secure" if _secure_cookies() else ""
    return f"{CSRF_COOKIE}={token}; Path=/; SameSite=lax; HttpOnly{secure}"


def _extract_token(body: bytes) -> str | None:
    """Pull ``csrf_token`` out of an urlencoded or multipart request body."""
    if not body:
        return None
    try:
        text = body.decode("utf-8", errors="ignore")
    except Exception:
        text = ""
    # application/x-www-form-urlencoded
    if "csrf_token=" in text:
        values = parse_qs(text).get("csrf_token")
        if values:
            return values[0]
    # multipart/form-data
    match = re.search(rb'name="csrf_token"\r\n\r\n([^\r\n]+)', body)
    if match:
        return match.group(1).decode("utf-8", errors="ignore")
    return None


def _body_replay(body: bytes):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


class CSRFProtectMiddleware:
    """Double-submit CSRF protection for state-changing requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        token = request.cookies.get(CSRF_COOKIE)
        state = scope.setdefault("state", {})

        if token:
            state["csrf_token"] = token
            set_cookie = False
        else:
            token = secrets.token_urlsafe(32)
            state["csrf_token"] = token
            set_cookie = True

        if scope["method"] in ("POST", "PUT", "PATCH", "DELETE"):
            body = b""
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    break
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
            submitted = _extract_token(body)
            if not submitted or not secrets.compare_digest(submitted, token):
                response = PlainTextResponse("Forbidden", status_code=403)
                if set_cookie:
                    response.raw_headers.append(
                        (b"set-cookie", _csrf_cookie_header(token).encode("latin-1"))
                    )
                return await response(scope, receive, send)
            receive = _body_replay(body)

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and set_cookie:
                headers = MutableHeaders(scope=message)
                headers.append("Set-Cookie", _csrf_cookie_header(token))
            await send(message)

        await self.app(scope, receive, send_wrapper)