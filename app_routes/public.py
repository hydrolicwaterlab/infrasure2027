"""Public routes — landing page."""
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app_routes.service import announcements_list, ensure_default_categories, faq_groups, site_state
from app_routes.utils import flash_text
from auth import user_from_request
from site_config import BASE_DIR, SITE_CONFIG, templates

router = APIRouter()


def auth_context(request: Request) -> dict:
    """Attach current user (if any) to template context for role-aware nav."""
    return {"current_user": user_from_request(request), "site_state": site_state()}


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    """Serve robots.txt for AI / LLM crawlers at site root."""
    path = os.path.join(BASE_DIR, "static", "robots.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "User-agent: *\nAllow: /\n"
    return PlainTextResponse(content, media_type="text/plain")


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    ensure_default_categories()
    ctx = {"request": request, "config": SITE_CONFIG}
    ctx.update(auth_context(request))
    ctx.update(flash_text(request.query_params.get("msg")))
    ctx["announcements"] = announcements_list()
    ctx["faq_groups"] = faq_groups()
    return templates.TemplateResponse(request, "index.html", ctx)


@router.get("/policies", response_class=HTMLResponse)
def policies(request: Request):
    ctx = {"request": request, "config": SITE_CONFIG}
    ctx.update(auth_context(request))
    ctx.update(flash_text(request.query_params.get("msg")))
    return templates.TemplateResponse(request, "policies.html", ctx)


@router.get("/sponsorship", response_class=HTMLResponse)
def sponsorship(request: Request):
    ctx = {"request": request, "config": SITE_CONFIG}
    ctx.update(auth_context(request))
    ctx.update(flash_text(request.query_params.get("msg")))
    return templates.TemplateResponse(request, "sponsorship.html", ctx)