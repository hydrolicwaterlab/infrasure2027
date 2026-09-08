"""Auth helpers: hashing, sessions, role guards."""
import hashlib
import secrets
import time

from fastapi import Depends, Request

from db import one

ROLES = ("student", "theme_incharge", "reviewer", "master_admin")

_sessions = {}  # token -> {"user_id", "role", "expires"}

SESSION_TTL = 6 * 60 * 60  # 6 hours


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"pbkdf2${salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, h = stored.split("$")
        if scheme != "pbkdf2":
            return False
        hash_ = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
        return secrets.compare_digest(h, hash_)
    except (ValueError, TypeError):
        return False


def create_session(user_id: str, role: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"user_id": user_id, "role": role, "expires": time.time() + SESSION_TTL}
    return token


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    s = _sessions.get(token)
    if not s:
        return None
    if s["expires"] < time.time():
        _sessions.pop(token, None)
        return None
    return s


def destroy_session(token: str) -> None:
    _sessions.pop(token, None)


def get_user(token: str | None) -> dict | None:
    s = get_session(token)
    if not s:
        return None
    return one("users", id=s["user_id"])

# ---------- FastAPI guards ----------

class Redirect(Exception):
    """Raised from dependencies; handled in main.py as a 303 redirect."""

    def __init__(self, url: str):
        self.url = url


COOKIE_NAME = "session_token"
COOKIE_OPTS = dict(httponly=True, samesite="lax", path="/", max_age=SESSION_TTL)


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, **COOKIE_OPTS)


def clear_session_cookie(response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def user_from_request(request: Request) -> dict | None:
    """Full user record if a valid session exists, else None."""
    user = get_user(request.cookies.get(COOKIE_NAME))
    if user and not user.get("active", True):
        return None
    return user


def require_login(request: Request) -> dict:
    user = user_from_request(request)
    if not user:
        raise Redirect("/login12345?msg=login_required")
    return user


def require_role(role: str):
    return require_any(role)


def require_any(*roles: str):
    """Allow any of the given roles; used for panels shared across roles."""
    def dependency(request: Request, user: dict = Depends(require_login)) -> dict:
        if user["role"] not in roles:
            raise Redirect("/?msg=wrong_role")
        return user

    return dependency


def home_for_role(user: dict) -> str:
    """Post-login landing page for a role."""
    if user["role"] == "student":
        return "/student/dashboard"
    if user["role"] == "theme_incharge":
        return "/incharge/dashboard"
    if user["role"] == "reviewer":
        return "/reviewer/dashboard"
    return "/admin/dashboard"
