"""App-wide rate limiter (slowapi).

Keys on the actual TCP peer (``request.client.host``) instead of the
``X-Forwarded-For`` header. The header is client-controlled and trivially
spoofed, which previously let an attacker bypass every rate limit (login
brute-force, OTP guessing, email bombing) by rotating ``X-Forwarded-For``.

If this app is ever deployed behind a trusted reverse proxy, run uvicorn with
``--proxy-headers`` so Starlette's ProxyHeadersMiddleware rewrites
``request.client.host`` to the real client IP (never trust the raw header).
"""

from slowapi import Limiter


def client_ip(request) -> str:
    """Rate-limit key: the real peer address, never the spoofable header."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=client_ip, default_limits=["120/minute"])