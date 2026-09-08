"""Auth routes — /register, /login, /logout."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app_routes.service import now
from app_routes.schemas import LoginForm, RegisterForm, validate
from app_routes.utils import flash_response, flash_text, render
from auth import (
    create_session,
    destroy_session,
    hash_password,
    home_for_role,
    set_session_cookie,
    clear_session_cookie,
    user_from_request,
    verify_password,
)
from db import insert, one

router = APIRouter()


def _redirect_home_for(user: dict) -> RedirectResponse:
    return RedirectResponse(home_for_role(user), status_code=303)


@router.get("/register12345")
def register_form(request: Request):
    if user_from_request(request):
        return _redirect_home_for(user_from_request(request))
    return render(request, "register.html", **flash_text(request.query_params.get("msg")))


@router.post("/register12345")
def register_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
):
    if user_from_request(request):
        return _redirect_home_for(user_from_request(request))
    data = {"name": name, "email": email, "password": password, "confirm": confirm}
    form, errors = validate(RegisterForm, data)
    if not errors and one("users", email=form.email):
        errors = ["An account with this email already exists. Try logging in."]
    if errors:
        return render(request, "register.html", errors=errors, values=data)
    insert(
        "users",
        {
            "name": form.name,
            "email": form.email,
            "password_hash": hash_password(form.password),
            "role": "student",
            "themes": [],
            "submission_ids": [],
            "active": True,
            "created_at": now(),
        },
        prefix="u",
    )
    return flash_response("/login12345", "registered")


@router.get("/login12345")
def login_form(request: Request):
    user = user_from_request(request)
    if user:
        return _redirect_home_for(user)
    return render(request, "login.html", **flash_text(request.query_params.get("msg")))


@router.post("/login12345")
def login_submit(request: Request, email: str = Form(""), password: str = Form("")):
    data = {"email": email, "password": password}
    form, errors = validate(LoginForm, data)
    user = one("users", email=form.email) if form else None
    if user and not user.get("active", True):
        return render(request, "login.html", errors=["This account has been deactivated. Contact the organizers."], values=data)
    if not user or not verify_password(password, user["password_hash"]):
        errors = errors or ["Incorrect email or password."]
        return render(request, "login.html", errors=errors, values=data)
    resp = RedirectResponse(home_for_role(user), status_code=303)
    set_session_cookie(resp, create_session(user["id"], user["role"]))
    return resp


@router.get("/logout")
def logout(request: Request):
    destroy_session(request.cookies.get("session_token"))
    resp = flash_response("/", "loggedout")
    clear_session_cookie(resp)
    return resp
