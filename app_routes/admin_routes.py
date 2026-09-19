"""Master admin routes — god view: stats, users, incharges, submissions, registrations, announcements, faqs."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import AnnouncementForm, FaqCategoryForm, FaqForm, InchargeForm, PasswordForm, clean_themes, validate
from app_routes.service import (
    SITE_FLAG_HINTS,
    SITE_FLAG_LABELS,
    announcements_list,
    apply_registration_action,
    create_announcement,
    create_category,
    create_faq,
    create_incharge,
    create_reviewer,
    decorated_subs,
    delete_announcement,
    delete_category,
    delete_faq,
    ensure_default_categories,
    faq_categories,
    faqs_list,
    filter_submissions,
    find_user,
    find_registration,
    delete_user_and_data,
    rename_category,
    reset_user_password,
    reviewers_list,
    scoped_submissions,
    set_incharge_themes,
    set_presentation_format,
    set_reviewer_themes,
    set_site_flag,
    site_state,
    split_paper_stages,
    students_map,
    submission_actions,
    toggle_announcement,
    toggle_user_active,
    update_announcement,
    update_faq,
)
from app_routes.utils import flash_response, render_msg
from auth import require_role
from db import load, one
from otp import send_credentials_email
from site_config import SITE_CONFIG

router = APIRouter(prefix="/admin")

ADMIN = require_role("master_admin")


def _stats() -> dict:
    users = load("users")
    subs = load("submissions")
    regs = load("registrations")
    students = [u for u in users if u["role"] == "student"]
    incharges = [u for u in users if u["role"] == "theme_incharge"]
    reviewers = [u for u in users if u["role"] == "reviewer"]
    return {
        "users": len(users),
        "students": len(students),
        "incharges": len(incharges),
        "reviewers": len(reviewers),
        "submissions": len(subs),
        "submitted": sum(1 for s in subs if s.get("status") == "submitted"),
        "under_review": sum(1 for s in subs if s.get("status") == "under_review"),
        "feedback_released": sum(1 for s in subs if s.get("status") == "feedback_released"),
        "round2_submitted": sum(1 for s in subs if s.get("status") == "round2_submitted"),
        "selected": sum(1 for s in subs if s.get("status") == "selected"),
        "not_selected": sum(1 for s in subs if s.get("status") == "not_selected"),
        "presenting": sum(1 for s in subs if s.get("status") == "selected" and s.get("presenting")),
        "formats_chosen": sum(1 for s in subs if s.get("status") == "selected" and s.get("presentation_format") in ("ppt", "poster")),
        "full_papers": sum(1 for s in subs if s.get("paper_type") == "full_paper"),
        "extended_abstracts": sum(1 for s in subs if s.get("paper_type") == "extended_abstract"),
        "registrations": len(regs),
        "reg_pending": sum(1 for r in regs if r["status"] == "pending"),
        "reg_approved": sum(1 for r in regs if r["status"] == "approved"),
        "fees_paid": sum(1 for r in regs if r.get("fee_paid")),
        "per_theme": [
            {
                "label": t["label"],
                "name": t["name"],
                "count": sum(1 for s in subs if s["theme"] == t["label"]),
            }
            for t in SITE_CONFIG["themes"]
        ],
    }


def _submit_actions():
    return lambda s: submission_actions(None, s)


@router.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(ADMIN)):
    return render_msg(
        request,
        "admin/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        stats=_stats(),
    )


# ---------- phase controls ----------

@router.get("/controls")
def controls(request: Request, user: dict = Depends(ADMIN)):
    return render_msg(
        request,
        "admin/controls.html",
        msg=request.query_params.get("msg"),
        user=user,
        state=site_state(),
        labels=SITE_FLAG_LABELS,
        hints=SITE_FLAG_HINTS,
    )


@router.post("/controls/{flag}/toggle")
def control_toggle(request: Request, flag: str, user: dict = Depends(ADMIN)):
    _, err = set_site_flag(flag, user)
    return flash_response("/admin/controls", err or "control_toggled")


# ---------- helpers ----------

def _matches_email(email: str, q: str) -> bool:
    return q.strip().lower() in (email or "").lower()


# ---------- submissions ----------

@router.get("/submissions")
def submissions(
    request: Request,
    user: dict = Depends(ADMIN),
    theme: str = "",
    status: str = "",
    type: str = "",
    q: str = "",
):
    # base scoped + theme/status/type filter
    subs = filter_submissions(scoped_submissions(user), theme, status, type)
    # gmail / email search — resolve owner email via students_map
    if q and q.strip():
        q_clean = q.strip().lower()
        smap = students_map()
        subs = [s for s in subs if q_clean in (smap.get(s.get("user_id"), {}).get("email") or "").lower()]
    feedback_subs, round2_subs, final_subs, done_subs = split_paper_stages(subs)
    feedback_subs = decorated_subs(feedback_subs, students_map(), _submit_actions())
    round2_subs = decorated_subs(round2_subs, students_map(), _submit_actions())
    final_subs = decorated_subs(final_subs, students_map(), _submit_actions())
    done_subs = decorated_subs(done_subs, students_map(), _submit_actions())
    return render_msg(
        request,
        "admin/submissions.html",
        msg=request.query_params.get("msg"),
        user=user,
        feedback_subs=feedback_subs,
        round2_subs=round2_subs,
        final_subs=final_subs,
        done_subs=done_subs,
        themes=SITE_CONFIG["themes"],
        filters={"theme": theme, "status": status, "type": type, "q": q},
        q=q,
    )


@router.post("/submissions/{sid}/format")
def submission_format(
    request: Request,
    sid: str,
    user: dict = Depends(ADMIN),
    presentation_format: str = Form(""),
):
    _, err = set_presentation_format(sid, presentation_format)
    if err == "bad_format":
        return flash_response(f"/incharge/submission/{sid}", "bad_format")
    if err:
        return flash_response("/admin/submissions", err)
    return flash_response(f"/incharge/submission/{sid}", "presentation_format_saved")


# ---------- registrations ----------
@router.get("/registrations")
def registrations(request: Request, user: dict = Depends(ADMIN), q: str = ""):
    regs = sorted(load("registrations"), key=lambda r: r.get("created_at", ""), reverse=True)
    if q and q.strip():
        q_clean = q.strip().lower()
        regs = [r for r in regs if q_clean in (r.get("email") or "").lower() or q_clean in (r.get("institute_email") or "").lower() or q_clean in (r.get("company_email") or "").lower()]
    return render_msg(request, "admin/registrations.html", user=user, regs=regs, q=q)


@router.post("/registrations/{rid}/set")
def registration_set(request: Request, rid: str, user: dict = Depends(ADMIN), action: str = Form("")):
    reg, err = apply_registration_action(rid, action)
    if err:
        return flash_response("/admin/registrations", err)
    return flash_response("/admin/registrations", "reg_updated")


@router.post("/registrations/{rid}/delete")
def registration_delete(request: Request, rid: str, user: dict = Depends(ADMIN)):
    reg = find_registration(rid)
    if not reg:
        return flash_response("/admin/registrations", "registration_not_found")
    uid = reg.get("user_id")
    if not uid:
        return flash_response("/admin/registrations", "user_not_found")
    _, err = delete_user_and_data(uid, user)
    return flash_response("/admin/registrations", err or "user_deleted")


# ---------- users ----------

@router.get("/users")
def users(request: Request, user: dict = Depends(ADMIN), q: str = ""):
    return _users_page(request, msg=request.query_params.get("msg"), q=q)


def _users_page(request: Request, msg=None, errors=None, active_reset=None, q: str = ""):
    # allow q from query param or explicitly passed
    if not q:
        q = request.query_params.get("q", "")
    people = sorted(load("users"), key=lambda u: u.get("created_at", ""))
    if q and q.strip():
        q_clean = q.strip().lower()
        people = [u for u in people if q_clean in (u.get("email") or "").lower() or q_clean in (u.get("name") or "").lower()]
    return render_msg(
        request,
        "admin/users.html",
        msg=msg,
        people=people,
        errors=errors,
        active_reset=active_reset,
        q=q,
    )


@router.post("/users/{uid}/toggle")
def user_toggle(request: Request, uid: str, user: dict = Depends(ADMIN)):
    _, err = toggle_user_active(uid, user)
    return flash_response("/admin/users", err or "user_toggled")


@router.post("/users/{uid}/password")
def user_password(
    request: Request,
    uid: str,
    user: dict = Depends(ADMIN),
    password: str = Form(""),
):
    form, errors = validate(PasswordForm, {"password": password})
    if errors:
        return _users_page(request, errors=errors, active_reset=uid)
    target, err = reset_user_password(uid, password)
    if err:
        return flash_response("/admin/users", err)
    return flash_response("/admin/users", "password_reset")


@router.post("/users/{uid}/delete")
def user_delete(request: Request, uid: str, user: dict = Depends(ADMIN)):
    _, err = delete_user_and_data(uid, user)
    return flash_response("/admin/users", err or "user_deleted")


# ---------- incharges ----------

def _incharges_page(request: Request, msg=None, values=None, errors=None):
    incharges = [u for u in load("users") if u["role"] == "theme_incharge"]
    return render_msg(
        request,
        "admin/incharges.html",
        msg=msg,
        incharges=incharges,
        themes=SITE_CONFIG["themes"],
        values=values or {},
        errors=errors,
    )


@router.get("/incharges")
def incharges(request: Request, user: dict = Depends(ADMIN)):
    return _incharges_page(request, msg=request.query_params.get("msg"))


@router.post("/incharges/create")
def incharge_create(
    request: Request,
    user: dict = Depends(ADMIN),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    themes: list[str] = Form([]),
):
    data = {"name": name, "email": email, "password": password, "themes": themes}
    form, errors = validate(InchargeForm, data)
    if not errors and one("users", email=form.email):
        errors = ["This email is already in use."]
    if errors:
        return _incharges_page(request, values=data, errors=errors)
    create_incharge(form.name, form.email, form.password, form.themes)
    send_credentials_email(form.name, form.email, form.password, "Theme Incharge")
    return flash_response("/admin/incharges", "incharge_created")


@router.post("/incharges/{uid}/themes")
def incharge_themes(
    request: Request,
    uid: str,
    user: dict = Depends(ADMIN),
    themes: list[str] = Form([]),
):
    target = find_user(uid)
    if not target or target["role"] != "theme_incharge":
        return flash_response("/admin/incharges", "user_not_found")
    try:
        ordered = clean_themes(themes)
    except ValueError:
        return flash_response("/admin/incharges", "incharge_themes_required")
    set_incharge_themes(uid, ordered)
    return flash_response("/admin/incharges", "incharge_themes_updated")


# ---------- reviewers ----------

def _reviewers_page(request: Request, msg=None, values=None, errors=None, q: str = ""):
    if not q:
        q = request.query_params.get("q", "")
    reviewers = reviewers_list()
    if q and q.strip():
        q_clean = q.strip().lower()
        reviewers = [r for r in reviewers if q_clean in (r.get("email") or "").lower() or q_clean in (r.get("name") or "").lower()]
    return render_msg(
        request,
        "admin/reviewers.html",
        msg=msg,
        reviewers=reviewers,
        themes=SITE_CONFIG["themes"],
        values=values or {},
        errors=errors,
        q=q,
    )


@router.get("/reviewers")
def reviewers(request: Request, user: dict = Depends(ADMIN), q: str = ""):
    return _reviewers_page(request, msg=request.query_params.get("msg"), q=q)


@router.post("/reviewers/create")
def reviewer_create(
    request: Request,
    user: dict = Depends(ADMIN),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    themes: list[str] = Form([]),
):
    data = {"name": name, "email": email, "password": password, "themes": themes}
    form, errors = validate(InchargeForm, data)
    if not errors and one("users", email=form.email):
        errors = ["This email is already in use."]
    if errors:
        return _reviewers_page(request, values=data, errors=errors)
    create_reviewer(form.name, form.email, form.password, form.themes, created_by=user["id"])
    send_credentials_email(form.name, form.email, form.password, "Reviewer")
    return flash_response("/admin/reviewers", "reviewer_created")


@router.post("/reviewers/{uid}/themes")
def reviewer_themes(
    request: Request,
    uid: str,
    user: dict = Depends(ADMIN),
    themes: list[str] = Form([]),
):
    target = find_user(uid)
    if not target or target["role"] != "reviewer":
        return flash_response("/admin/reviewers", "user_not_found")
    try:
        ordered = clean_themes(themes)
    except ValueError:
        return flash_response("/admin/reviewers", "incharge_themes_required")
    set_reviewer_themes(uid, ordered)
    return flash_response("/admin/reviewers", "reviewer_themes_updated")


# ---------- announcements ----------

@router.get("/announcements")
def announcements(request: Request, user: dict = Depends(ADMIN)):
    return _render_announcements(request, msg=request.query_params.get("msg"))


def _render_announcements(request, msg=None, values=None, errors=None):
    entries = announcements_list()
    return render_msg(
        request,
        "admin/announcements.html",
        msg=msg,
        entries=entries,
        values=values or {},
        errors=errors,
    )


@router.post("/announcements/create")
def announcement_create(
    request: Request,
    user: dict = Depends(ADMIN),
    title: str = Form(""),
    body: str = Form(""),
):
    data = {"title": title, "body": body}
    form, errors = validate(AnnouncementForm, data)
    if errors:
        return _render_announcements(request, values=data, errors=errors)
    create_announcement(form.title, form.body, user["id"])
    return flash_response("/admin/announcements", "announcement_created")


@router.post("/announcements/{aid}/edit")
def announcement_edit(
    request: Request,
    aid: str,
    user: dict = Depends(ADMIN),
    title: str = Form(""),
    body: str = Form(""),
):
    data = {"title": title, "body": body}
    form, errors = validate(AnnouncementForm, data)
    if errors:
        return _render_announcements(request, values={**data, "editing": aid}, errors=errors)
    _, err = update_announcement(aid, form.title, form.body)
    return flash_response("/admin/announcements", err or "announcement_updated")


@router.post("/announcements/{aid}/toggle")
def announcement_toggle(request: Request, aid: str, user: dict = Depends(ADMIN)):
    _, err = toggle_announcement(aid)
    return flash_response("/admin/announcements", err or "announcement_toggled")


@router.post("/announcements/{aid}/delete")
def announcement_delete(request: Request, aid: str, user: dict = Depends(ADMIN)):
    _, err = delete_announcement(aid)
    return flash_response("/admin/announcements", err or "announcement_deleted")


# ---------- FAQs ----------

@router.get("/faqs")
def faqs(request: Request, user: dict = Depends(ADMIN)):
    ensure_default_categories()
    return _render_faqs(request, msg=request.query_params.get("msg"))


def _render_faqs(request, msg=None, values=None, errors=None, editing=None, cat_editing=None):
    cats = faq_categories()
    entries = faqs_list()
    cat_map = {c["id"]: c["name"] for c in cats}
    return render_msg(
        request,
        "admin/faqs.html",
        msg=msg,
        categories=cats,
        entries=entries,
        cat_map=cat_map,
        values=values or {},
        errors=errors,
        editing=editing,
        cat_editing=cat_editing,
    )


@router.post("/faqs/categories/create")
def faq_category_create(
    request: Request,
    user: dict = Depends(ADMIN),
    name: str = Form(""),
):
    form, errors = validate(FaqCategoryForm, {"name": name})
    if errors:
        return _render_faqs(request, values={"cat": {"name": name}}, errors=errors)
    create_category(form.name)
    return flash_response("/admin/faqs", "faq_cat_created")


@router.post("/faqs/categories/{cid}/rename")
def faq_category_rename(
    request: Request,
    cid: str,
    user: dict = Depends(ADMIN),
    name: str = Form(""),
):
    form, errors = validate(FaqCategoryForm, {"name": name})
    if errors:
        return _render_faqs(request, cat_editing=cid, errors=errors)
    _, err = rename_category(cid, form.name)
    return flash_response("/admin/faqs", err or "faq_cat_renamed")


@router.post("/faqs/categories/{cid}/delete")
def faq_category_delete(request: Request, cid: str, user: dict = Depends(ADMIN)):
    _, err = delete_category(cid)
    return flash_response("/admin/faqs", err or "faq_cat_deleted")


@router.post("/faqs/create")
def faq_create(
    request: Request,
    user: dict = Depends(ADMIN),
    category_id: str = Form(""),
    question: str = Form(""),
    answer: str = Form(""),
    order: int = Form(0),
):
    data = {"category_id": category_id, "question": question, "answer": answer, "order": order}
    form, errors = validate(FaqForm, data)
    if errors:
        return _render_faqs(request, values={"faq": data}, errors=errors)
    create_faq(form.category_id, form.question, form.answer, form.order)
    return flash_response("/admin/faqs", "faq_created")


@router.post("/faqs/{fid}/edit")
def faq_edit(
    request: Request,
    fid: str,
    user: dict = Depends(ADMIN),
    category_id: str = Form(""),
    question: str = Form(""),
    answer: str = Form(""),
    order: int = Form(0),
):
    data = {"category_id": category_id, "question": question, "answer": answer, "order": order}
    form, errors = validate(FaqForm, data)
    if errors:
        return _render_faqs(request, values={**data, "editing": fid}, errors=errors)
    _, err = update_faq(fid, form.category_id, form.question, form.answer, form.order)
    return flash_response("/admin/faqs", err or "faq_updated")


@router.post("/faqs/{fid}/delete")
def faq_delete(request: Request, fid: str, user: dict = Depends(ADMIN)):
    _, err = delete_faq(fid)
    return flash_response("/admin/faqs", err or "faq_deleted")