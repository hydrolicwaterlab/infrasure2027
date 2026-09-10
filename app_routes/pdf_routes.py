"""Protected inline PDF serving for Round-2 (PPT) content.

Only the owning student, a theme-scoped incharge, the assigned Round-2 reviewer,
and master admins may open a submission's PDF. Served inline so panels can embed
it in a browser viewer without downloading.
"""
import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse

from app_routes.service import can_view_pdf, pdf_path
from auth import require_login
from db import one

router = APIRouter()


@router.get("/pdf/{sid}")
def serve_pdf(sid: str, user: dict = Depends(require_login)):
    sub = one("submissions", id=sid)
    if not sub:
        return RedirectResponse("/?msg=submission_not_found", status_code=303)
    if not sub.get("pdf_name"):
        return RedirectResponse("/", status_code=303)
    if not can_view_pdf(user, sub):
        return RedirectResponse("/?msg=wrong_role", status_code=303)
    path = pdf_path(sid)
    if not os.path.exists(path):
        return RedirectResponse("/", status_code=303)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=sub.get("pdf_name") or f"{sid}.pdf",
        content_disposition_type="inline",
    )