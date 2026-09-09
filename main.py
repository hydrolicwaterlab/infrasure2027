"""INFRASURE 2027 — FastAPI app entry point."""
import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from site_config import BASE_DIR, SITE_CONFIG

app = FastAPI(
    title=SITE_CONFIG["name"],
    docs_url=None,
    redoc_url="/wellnotexpectingyoutobehere1234554321",
    openapi_url=None,
)

app.mount("/media", StaticFiles(directory=os.path.join(BASE_DIR, "media")), name="media")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

from app_routes import admin_routes, auth_routes, incharge_routes, public, reviewer_routes, student_routes  # noqa: E402
from app_routes.utils import base_ctx  # noqa: E402
from auth import Redirect  # noqa: E402
from site_config import templates  # noqa: E402

app.include_router(public.router)
app.include_router(auth_routes.router)
app.include_router(student_routes.router)
app.include_router(incharge_routes.router)
app.include_router(reviewer_routes.router)
app.include_router(admin_routes.router)


@app.exception_handler(Redirect)
def redirect_handler(request, exc: Redirect):
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(404)
async def not_found(request, exc):
    return templates.TemplateResponse(request, "404.html", base_ctx(request), status_code=404)


@app.get("/ping")
def ping():
    return "pong"


@app.get("/health")
def health():
    return {"status": "ok", "app": SITE_CONFIG["name"]}