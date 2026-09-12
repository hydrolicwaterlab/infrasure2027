"""Auth routes — /register, /login, /logout, OTP verification, forgot password."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app_routes.service import now, site_flag
from app_routes.schemas import LoginForm, RegisterForm, clean_password, validate
from app_routes.utils import flash_response, flash_text, render
from auth import (
    create_session,
    destroy_session,
    hash_password,
    home_for_role,
    is_locked,
    lockout_remaining,
    register_failed_login,
    reset_failed_logins,
    set_session_cookie,
    clear_session_cookie,
    user_from_request,
    verify_password,
)
from db import insert, one, update
from otp import (
    consume_reset_token,
    issue_reset_token,
    latest_otp_payload,
    otp_cooldown_remaining,
    send_otp,
    verify_otp,
)
from ratelimit import limiter

router = APIRouter()

RESEND_BY_PURPOSE = {
    "register": "/registerinfrasure",
    "forgot": "/forgotpassword",
}

# Pre-computed valid PBKDF2 hash; verified for unknown accounts so login time
# does not reveal whether an email is registered (prevents timing enumeration).
_DUMMY_HASH = hash_password("timing-equalizer-dummy")

OTP_COOLDOWN_MSG = "A code was sent recently — please wait a moment before requesting another."


def _redirect_home_for(user: dict) -> RedirectResponse:
    return RedirectResponse(home_for_role(user), status_code=303)


def _register_values_from_payload(payload: dict) -> dict:
    """Reconstruct register.html form values from a stored OTP payload."""
    return {
        "name": payload.get("name", ""),
        "email": payload.get("email", ""),
        "password": "",
        "confirm": "",
        "agree": "on",
    }


# ---------- registration (OTP-gated) ----------

@router.get("/registerinfrasure")
@limiter.limit("20/minute")
def register_form(request: Request):
    if user_from_request(request):
        return _redirect_home_for(user_from_request(request))
    if not site_flag("registration_open"):
        return flash_response("/", "registration_closed")
    q = request.query_params
    if q.get("resend"):
        email = (q.get("otp_email") or "").strip().lower()
        payload = latest_otp_payload(email, "register")
        if payload.get("email", "").lower() == email and otp_cooldown_remaining(email, "register") == 0:
            send_otp(email, "register", payload=payload)
            return render(
                request,
                "register.html",
                values=_register_values_from_payload(payload),
                otp_show=True,
                otp_email=email,
                otp_purpose="register",
                otp_purpose_label="verify your account",
                otp_resend_url=RESEND_BY_PURPOSE["register"],
                **flash_text("otp_sent"),
            )
    return render(request, "register.html", **flash_text(request.query_params.get("msg")))


@router.post("/registerinfrasure")
@limiter.limit("20/minute")
def register_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
    agree: str = Form(""),
):
    if user_from_request(request):
        return _redirect_home_for(user_from_request(request))
    if not site_flag("registration_open"):
        return flash_response("/", "registration_closed")
    data = {"name": name, "email": email, "password": password, "confirm": confirm, "agree": agree}
    form, errors = validate(RegisterForm, data)
    if not errors and one("users", email=form.email):
        errors = ["An account with this email already exists. Try logging in."]
    if errors:
        return render(request, "register.html", errors=errors, values=data)
    if otp_cooldown_remaining(form.email, "register") > 0:
        return render(
            request,
            "register.html",
            values=data,
            errors=[OTP_COOLDOWN_MSG],
        )
    send_otp(
        form.email,
        "register",
        payload={
            "name": form.name,
            "email": form.email,
            "password_hash": hash_password(form.password),
        },
    )
    return render(
        request,
        "register.html",
        values=_register_values_from_payload({"name": form.name, "email": form.email}),
        otp_show=True,
        otp_email=form.email,
        otp_purpose="register",
        otp_purpose_label="verify your account",
        otp_resend_url=RESEND_BY_PURPOSE["register"],
        **flash_text("otp_sent"),
    )


# ---------- login / logout ----------

@router.get("/logininfrasure")
@limiter.limit("20/minute")
def login_form(request: Request):
    user = user_from_request(request)
    if user:
        return _redirect_home_for(user)
    return render(request, "login.html", **flash_text(request.query_params.get("msg")))


@router.post("/logininfrasure")
@limiter.limit("20/minute")
def login_submit(request: Request, email: str = Form(""), password: str = Form("")):
    data = {"email": email, "password": password}
    form, errors = validate(LoginForm, data)
    user = one("users", email=form.email) if form else None
    if user and not user.get("active", True):
        return render(request, "login.html", errors=["This account has been deactivated. Contact the organizers."], values=data)
    if user and is_locked(user):
        return render(request, "login.html",
                      errors=[f"This account is temporarily locked after too many failed attempts. Try again in {lockout_remaining(user)} seconds."],
                      values=data)
    if not user:
        # Burn the same PBKDF2 time as a real account so response timing does
        # not reveal which emails are registered.
        verify_password(password, _DUMMY_HASH)
        errors = errors or ["Incorrect email or password."]
        return render(request, "login.html", errors=errors, values=data)
    if not verify_password(password, user["password_hash"]):
        update("users", user["id"], register_failed_login(user))
        errors = errors or ["Incorrect email or password."]
        return render(request, "login.html", errors=errors, values=data)
    update("users", user["id"], reset_failed_logins(user))
    resp = RedirectResponse(home_for_role(user), status_code=303)
    set_session_cookie(resp, create_session(user["id"], user["role"]))
    return resp


@router.post("/logout")
def logout(request: Request):
    destroy_session(request.cookies.get("session_token"))
    resp = flash_response("/", "loggedout")
    clear_session_cookie(resp)
    return resp


# ---------- shared OTP verification ----------

@router.post("/verifyotp")
@limiter.limit("30/minute")
def verify_otp_submit(request: Request, email: str = Form(""), purpose: str = Form(""), code: str = Form("")):
    email = (email or "").strip().lower()
    if purpose == "register":
        ok, err, payload = verify_otp(email, "register", code)
        if not ok:
            payload = latest_otp_payload(email, "register")
            return render(
                request,
                "register.html",
                values=_register_values_from_payload(payload),
                errors=[],
                otp_show=True,
                otp_email=email,
                otp_purpose="register",
                otp_purpose_label="verify your account",
                otp_resend_url=RESEND_BY_PURPOSE["register"],
                otp_error=flash_text(err)["error"],
            )
        if one("users", email=email):
            return flash_response("/logininfrasure", "registered")
        insert(
            "users",
            {
                "name": payload.get("name"),
                "email": payload.get("email"),
                "password_hash": payload.get("password_hash"),
                "role": "student",
                "themes": [],
                "submission_ids": [],
                "active": True,
                "created_at": now(),
            },
            prefix="u",
        )
        return flash_response("/logininfrasure", "registered")
    if purpose == "forgot":
        ok, err, payload = verify_otp(email, "forgot", code)
        if not ok:
            return render(
                request,
                "forgot_password.html",
                state="otp",
                values={"email": email},
                otp_show=True,
                otp_email=email,
                otp_purpose="forgot",
                otp_purpose_label="reset your password",
                otp_resend_url=RESEND_BY_PURPOSE["forgot"],
                otp_generic=True,
                otp_error=flash_text(err)["error"],
            )
        if not one("users", email=email):
            return render(
                request,
                "forgot_password.html",
                state="otp",
                values={"email": email},
                otp_show=True,
                otp_email=email,
                otp_purpose="forgot",
                otp_purpose_label="reset your password",
                otp_resend_url=RESEND_BY_PURPOSE["forgot"],
                otp_generic=True,
                otp_error=flash_text("email_not_found")["error"],
            )
        return render(
            request,
            "forgot_password.html",
            state="reset",
            values={"email": email},
            reset_token=issue_reset_token(email),
        )
    if purpose == "institute":
        # handled in student_routes (needs the logged-in user) — see /student/verifyotp
        return flash_response("/student/info", "otp_missing")
    return flash_response("/", "otp_missing")


# ---------- forgot password ----------

@router.get("/forgotpassword")
@limiter.limit("20/minute")
def forgot_password_form(request: Request):
    q = request.query_params
    if q.get("resend"):
        email = (q.get("otp_email") or "").strip().lower()
        if latest_otp_payload(email, "forgot") and otp_cooldown_remaining(email, "forgot") == 0:
            send_otp(email, "forgot", payload={"email": email})
            return render(
                request,
                "forgot_password.html",
                state="otp",
                values={"email": email},
                otp_show=True,
                otp_email=email,
                otp_purpose="forgot",
                otp_purpose_label="reset your password",
                otp_resend_url=RESEND_BY_PURPOSE["forgot"],
                otp_generic=True,
                **flash_text("forgot_check_email"),
            )
    return render(request, "forgot_password.html", state="email", **flash_text(q.get("msg")))


@router.post("/forgotpassword")
@limiter.limit("20/minute")
def forgot_password_submit(request: Request, email: str = Form("")):
    email = (email or "").strip().lower()
    if "@" not in email:
        return render(request, "forgot_password.html", state="email", errors=["Please enter a valid email address."])
    # Only email an OTP if an account exists — prevents SMTP abuse via random emails.
    # The response is identical either way so attackers cannot probe registered emails.
    # A per-address cooldown also throttles repeat requests to a known account.
    if one("users", email=email) and otp_cooldown_remaining(email, "forgot") == 0:
        send_otp(email, "forgot", payload={"email": email})
    return render(
        request,
        "forgot_password.html",
        state="otp",
        values={"email": email},
        otp_show=True,
        otp_email=email,
        otp_purpose="forgot",
        otp_purpose_label="reset your password",
        otp_resend_url=RESEND_BY_PURPOSE["forgot"],
        otp_generic=True,
        **flash_text("forgot_check_email"),
    )


@router.post("/resetpassword")
@limiter.limit("20/minute")
def reset_password_submit(
    request: Request,
    email: str = Form(""),
    token: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
):
    acct_email = consume_reset_token(token)
    if not acct_email or acct_email != (email or "").strip().lower():
        return render(request, "forgot_password.html", state="email", errors=["That reset link has expired — please start again."])
    try:
        clean_password(password)
    except ValueError as exc:
        return render(request, "forgot_password.html", state="reset",
                      values={"email": acct_email}, reset_token=token,
                      errors=[str(exc)])
    if password != confirm:
        return render(request, "forgot_password.html", state="reset",
                      values={"email": acct_email}, reset_token=token,
                      errors=["Passwords do not match."])
    user = one("users", email=acct_email)
    if not user:
        return flash_response("/logininfrasure", "email_not_found")
    update("users", user["id"], {"password_hash": hash_password(password)})
    return flash_response("/logininfrasure", "password_reset")