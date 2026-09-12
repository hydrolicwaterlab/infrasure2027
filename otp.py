"""OTP helpers: generate, send (terminal + Gmail SMTP best-effort), verify."""
import logging
import secrets
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage

from dotenv import load_dotenv

from db import insert, load, update
from site_config import SITE_CONFIG

load_dotenv()

logger = logging.getLogger("otp")

OTP_TTL = 5 * 60  # 5 minutes
MAX_ATTEMPTS = 5
CODE_LEN = 6

# Minimum gap between codes sent to the same address — throttles email bombing.
OTP_COOLDOWN_SECONDS = 30

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_TIMEOUT = 15


def _env(name: str) -> str:
    import os

    return (os.getenv(name) or "").strip()


def _debug() -> bool:
    return _env("DEBUG") == "1"


def smtp_configured() -> bool:
    return bool(_env("GMAIL_USER") and _env("GMAIL_APP_PASSWORD"))


def _new_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_LEN):0{CODE_LEN}d}"


def send_otp(email: str, purpose: str, payload: dict | None = None) -> str:
    """Generate, persist, print and (best-effort) email an OTP.

    Always prints ``[OTP:<purpose>] <email> -> <code>`` to the terminal so the
    code is visible during development. Gmail SMTP delivery is attempted when
    GMAIL_USER / GMAIL_APP_PASSWORD are set in .env; failures are logged as
    warnings and never crash the request.
    """
    email = (email or "").strip().lower()
    code = _new_code()
    insert(
        "otps",
        {
            "purpose": purpose,
            "email": email,
            "code": code,
            "expires_at": time.time() + OTP_TTL,
            "attempts": 0,
            "used": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "payload": payload or {},
        },
        prefix="o",
    )
    if _debug():
        print(f"[OTP:{purpose}] {email} -> {code}")
    _mail_best_effort(email, purpose, code)
    return code


def _smtp_send(to_email: str, subject: str, body: str) -> None:
    """Best-effort Gmail SMTP delivery — logs failures, never raises."""
    user = _env("GMAIL_USER")
    app_password = _env("GMAIL_APP_PASSWORD")
    if not (user and app_password):
        logger.warning("GMAIL_USER / GMAIL_APP_PASSWORD not set — email printed to terminal only.")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=EMAIL_TIMEOUT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, app_password)
            smtp.send_message(msg)
        logger.info("Email delivered to %s", to_email)
    except Exception:
        logger.exception("Gmail SMTP delivery failed for %s", to_email)


def _mail_best_effort(to_email: str, purpose: str, code: str) -> None:
    subject = f"{SITE_CONFIG['name']} — One-time verification code"
    body = (
        f"Hello,\n\n"
        f"Your one-time verification code for {SITE_CONFIG['name']} is:\n\n"
        f"    {code}\n\n"
        f"This code expires in 5 minutes. If you did not request it, you can ignore this email.\n\n"
        f"— {SITE_CONFIG['name']} team"
    )
    _smtp_send(to_email, subject, body)


def send_credentials_email(name: str, email: str, password: str, role_label: str) -> None:
    """Best-effort email with a newly created account's login credentials.

    Always prints the credentials to the terminal so they are visible during
    development; Gmail SMTP delivery is attempted when GMAIL_USER /
    GMAIL_APP_PASSWORD are set. Failures are logged as warnings and never crash
    the request.
    """
    email = (email or "").strip().lower()
    role_label = role_label or "account"
    if _debug():
        print(f"[CREDENTIALS:{role_label}] {email} -> password: {password}")
    subject = f"{SITE_CONFIG['name']} — your {role_label} login credentials"
    body = (
        f"Dear {name or 'there'},\n\n"
        f"You have been appointed as a {role_label} for {SITE_CONFIG['name']}.\n\n"
        f"Your login details are:\n\n"
        f"    Email:    {email}\n"
        f"    Password: {password}\n\n"
        f"Log in at the portal (login page: /logininfrasure) with these details.\n\n"
        f"Please keep them safe. If you did not expect this email, you can ignore it.\n\n"
        f"— {SITE_CONFIG['name']} team"
    )
    _smtp_send(email, subject, body)


def latest_otp_payload(email: str, purpose: str) -> dict:
    """Payload of the latest unused OTP for (email, purpose) — used on resend."""
    email = (email or "").strip().lower()
    recs = [r for r in load("otps") if r.get("purpose") == purpose and r.get("email") == email and not r.get("used")]
    if not recs:
        return {}
    rec = max(recs, key=lambda r: r.get("expires_at", 0))
    return rec.get("payload") or {}


def otp_cooldown_remaining(email: str, purpose: str) -> int:
    """Seconds left before another code may be sent to ``email`` for ``purpose``.

    Returns 0 if no code was recently issued (or the timestamp is unreadable),
    so a cooldown never blocks a legitimate first request.
    """
    email = (email or "").strip().lower()
    recs = [r for r in load("otps") if r.get("purpose") == purpose and r.get("email") == email]
    if not recs:
        return 0
    latest = max(recs, key=lambda r: r.get("created_at", ""))
    created = latest.get("created_at") or ""
    try:
        created_ts = datetime.fromisoformat(created).timestamp()
    except (ValueError, TypeError):
        return 0
    return max(0, int(OTP_COOLDOWN_SECONDS - (time.time() - created_ts)))


RESET_TOKEN_TTL = 10 * 60  # 10 minutes


def issue_reset_token(email: str) -> str:
    """Create a single-use, time-limited password-reset token for an account."""
    email = (email or "").strip().lower()
    token = secrets.token_urlsafe(32)
    insert(
        "otps",
        {
            "purpose": "reset_token",
            "email": email,
            "code": token,
            "expires_at": time.time() + RESET_TOKEN_TTL,
            "attempts": 0,
            "used": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "payload": {},
        },
        prefix="o",
    )
    return token


def consume_reset_token(token: str) -> str | None:
    """Validate a reset token; returns the account email or None if invalid/expired."""
    token = (token or "").strip()
    recs = [r for r in load("otps") if r.get("purpose") == "reset_token" and r.get("code") == token and not r.get("used")]
    if not recs:
        return None
    rec = max(recs, key=lambda r: r.get("expires_at", 0))
    if time.time() > rec.get("expires_at", 0):
        return None
    update("otps", rec["id"], {"used": True})
    return rec.get("email")


def verify_otp(email: str, purpose: str, code: str) -> tuple[bool, str, dict | None]:
    """Check an OTP against the latest unused record for (email, purpose).

    Returns ``(ok, error_code, payload)`` where ``error_code`` is a FLASH key
    (``otp_expired`` / ``otp_incorrect``) or ``""`` on success. Consumes the
    OTP on success; invalid guesses count towards the attempt cap.
    """
    email = (email or "").strip().lower()
    code = (code or "").strip()
    recs = [r for r in load("otps") if r.get("purpose") == purpose and r.get("email") == email and not r.get("used")]
    if not recs:
        return False, "otp_incorrect", None
    rec = max(recs, key=lambda r: r.get("expires_at", 0))
    if time.time() > rec.get("expires_at", 0):
        return False, "otp_expired", None
    if rec.get("attempts", 0) >= MAX_ATTEMPTS:
        return False, "otp_expired", None
    if not secrets.compare_digest(str(rec.get("code", "")), code):
        update("otps", rec["id"], {"attempts": rec.get("attempts", 0) + 1})
        return False, "otp_incorrect", None
    update("otps", rec["id"], {"used": True})
    return True, "", rec.get("payload") or {}