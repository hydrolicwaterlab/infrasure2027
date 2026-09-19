"""Theme incharge routes — dashboard, reviewer assignment, feedback, final decision."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import (
    FinalDecisionForm,
    InchargeForm,
    PaperFeedbackForm,
    ReviewerCreateForm,
    THEME_LABELS,
    validate,
)
from app_routes.service import (
    apply_final_decision,
    assign_reviewer,
    create_reviewer,
    decorated_subs,
    detail_actions,
    eligible_reviewers,
    filter_submissions,
    find_reviewer,
    paper_view,
    reviewers_list,
    save_feedback,
    scoped_submissions,
    split_paper_stages,
    students_map,
    submission_actions,
    submission_for,
    unassign_reviewer,
)
from app_routes.utils import flash_response, render, render_msg
from auth import require_any
from db import one
from otp import send_credentials_email
from site_config import SITE_CONFIG

router = APIRouter(prefix="/incharge")

PANEL_USER = require_any("theme_incharge", "master_admin")


def _theme_choices(user: dict) -> list:
    if user["role"] == "master_admin":
        return SITE_CONFIG["themes"]
    allowed = set(user.get("themes") or [])
    return [t for t in SITE_CONFIG["themes"] if t["label"] in allowed]


def _decorate(user: dict, subs: list) -> list:
    return decorated_subs(subs, students_map(), lambda s: submission_actions(user, s))


def _round_stats(all_subs: list) -> tuple:
    awaiting_feedback = sum(1 for s in all_subs if s.get("status") in ("submitted", "under_review"))
    awaiting_round2 = sum(1 for s in all_subs if s.get("status") == "feedback_released")
    awaiting_final = sum(1 for s in all_subs if s.get("status") == "round2_submitted")
    return awaiting_feedback, awaiting_round2, awaiting_final


TABS = ("feedback", "round2", "final", "decided")


@router.get("/dashboard")
def dashboard(
    request: Request,
    user: dict = Depends(PANEL_USER),
    theme: str = "",
    status: str = "",
    type: str = "",
    tab: str = "",
):
    all_subs = scoped_submissions(user)
    filtered = filter_submissions(all_subs, theme, status, type)
    feedback_subs, round2_subs, final_subs, done_subs = split_paper_stages(filtered)
    feedback_subs = _decorate(user, feedback_subs)
    round2_subs = _decorate(user, round2_subs)
    final_subs = _decorate(user, final_subs)
    done_subs = _decorate(user, done_subs)
    awaiting_feedback, awaiting_round2, awaiting_final = _round_stats(all_subs)
    active_tab = tab if tab in TABS else "feedback"
    return render_msg(
        request,
        "incharge/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        feedback_subs=feedback_subs,
        round2_subs=round2_subs,
        final_subs=final_subs,
        done_subs=done_subs,
        themes=_theme_choices(user),
        filters={"theme": theme, "status": status, "type": type},
        active_tab=active_tab,
        awaiting_feedback=awaiting_feedback,
        awaiting_round2=awaiting_round2,
        awaiting_final=awaiting_final,
    )


@router.get("/submission/{sid}")
def submission_detail(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    return render(
        request,
        "incharge/submission.html",
        user=user,
        sub=paper_view(sub),
        students=students_map(),
        themes=_theme_choices(user),
        actions=detail_actions(user, sub),
        back_url=_back_url(user),
    )


# ---------- feedback (round 1 — everyone advances) ----------

@router.get("/review/{sid}")
def review_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("status") not in ("submitted", "under_review"):
        return flash_response(_back_url(user), "bad_status")
    values = {"feedback": sub.get("feedback") or ""}
    return render_msg(
        request, "incharge/review.html",
        msg=request.query_params.get("msg"),
        user=user, sub=paper_view(sub), students=students_map(), themes=_theme_choices(user),
        back_url=_back_url(user), values=values, errors=None,
    )


@router.post("/review/{sid}")
def review_submit(
    request: Request,
    sid: str,
    user: dict = Depends(PANEL_USER),
    feedback: str = Form(""),
):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("status") not in ("submitted", "under_review"):
        return flash_response(_back_url(user), "bad_status")
    form, errors = validate(PaperFeedbackForm, {"feedback": feedback})
    if errors:
        return render_msg(
            request, "incharge/review.html",
            user=user, sub=paper_view(sub), students=students_map(), themes=_theme_choices(user),
            back_url=_back_url(user), values={"feedback": feedback}, errors=errors,
        )
    _, e = save_feedback(user, sid, form.feedback)
    if e:
        return flash_response(_back_url(user), e)
    return flash_response(_back_url(user), "feedback_saved")


# ---------- final decision (after the revision window) ----------

@router.get("/final/{sid}")
def final_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("status") != "round2_submitted":
        return flash_response(_back_url(user), "bad_status")
    values = {"decision": "", "comment": sub.get("decision_comment") or ""}
    return render_msg(
        request, "incharge/decision.html",
        msg=request.query_params.get("msg"),
        user=user, sub=paper_view(sub), students=students_map(), themes=_theme_choices(user),
        back_url=_back_url(user), values=values, errors=None,
    )


@router.post("/final/{sid}")
def final_submit(
    request: Request,
    sid: str,
    user: dict = Depends(PANEL_USER),
    decision: str = Form(""),
    comment: str = Form(""),
):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("status") != "round2_submitted":
        return flash_response(_back_url(user), "bad_status")
    form, errors = validate(FinalDecisionForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request, "incharge/decision.html",
            user=user, sub=paper_view(sub), students=students_map(), themes=_theme_choices(user),
            back_url=_back_url(user), values={"decision": decision, "comment": comment}, errors=errors,
        )
    _, e = apply_final_decision(user, sid, form.decision, form.comment)
    if e:
        return flash_response(_back_url(user), e)
    return flash_response(_back_url(user), "final_decision_saved")


# ---------- reviewer assignment ----------

def _render_assign(request, user: dict, sub: dict, values: dict, errors: list | None):
    return render(
        request,
        "incharge/assign.html",
        sub=paper_view(sub),
        reviewers=eligible_reviewers(sub["theme"]),
        themes=_theme_choices(user),
        students=students_map(),
        values=values,
        errors=errors,
    )


@router.get("/assign/{sid}")
def assign_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("status") not in ("submitted", "round2_submitted"):
        return flash_response(_back_url(user), "submission_not_pending")
    return _render_assign(request, user, sub, {}, None)


def _assign_submit(request: Request, sid: str, user: dict,
                   reviewer_id: str, name: str, email: str, password: str):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("status") not in ("submitted", "round2_submitted"):
        return flash_response(_back_url(user), "submission_not_pending")

    if reviewer_id:
        reviewer = find_reviewer(reviewer_id)
        if not reviewer:
            return _render_assign(request, user, sub, {"reviewer_id": reviewer_id},
                                  ["Reviewer not found."])
        if sub["theme"] not in (reviewer.get("themes") or []):
            return _render_assign(request, user, sub, {"reviewer_id": reviewer_id},
                                  ["That reviewer isn't assigned to this theme — adjust their themes first."])
        _, e = assign_reviewer(user, sid, reviewer)
        return flash_response(_back_url(user), e or "assigned_reviewer")

    data = {"name": name, "email": email, "password": password}
    form, errors = validate(ReviewerCreateForm, data)
    existing = one("users", email=form.email) if form else None
    if existing:
        if existing["role"] == "reviewer":
            if sub["theme"] not in (existing.get("themes") or []):
                return _render_assign(request, user, sub, data,
                                      ["That email is already a reviewer but not assigned to this theme — adjust their themes first."])
            _, e = assign_reviewer(user, sid, existing)
            return flash_response(_back_url(user), "reviewer_exists_assigned")
        return _render_assign(request, user, sub, data,
                              ["This email is already in use."])
    if errors:
        return _render_assign(request, user, sub, data, errors)
    reviewer = create_reviewer(form.name, form.email, form.password, [sub["theme"]], created_by=user["id"])
    send_credentials_email(form.name, form.email, form.password, "Reviewer")
    _, e = assign_reviewer(user, sid, reviewer)
    return flash_response(_back_url(user), e or "reviewer_created_assigned")


@router.post("/assign/{sid}")
def assign_submit(
    request: Request,
    sid: str,
    user: dict = Depends(PANEL_USER),
    reviewer_id: str = Form(""),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
):
    return _assign_submit(request, sid, user, reviewer_id, name, email, password)


@router.get("/takeover/{sid}")
def takeover(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    _, err = unassign_reviewer(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    return flash_response(f"/incharge/review/{sid}", "reviewer_removed")


@router.get("/change_reviewer/{sid}")
def change_reviewer(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    _, err = unassign_reviewer(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    return flash_response(f"/incharge/assign/{sid}", "reviewer_removed")


# ---------- reviewer management (incharge's own reviewers) ----------

@router.get("/reviewers")
def reviewers_page(request: Request, user: dict = Depends(PANEL_USER)):
    my_themes = _theme_choices(user)
    allowed = {t["label"] for t in my_themes}
    reviewers = [r for r in reviewers_list() if set(r.get("themes") or []) & allowed]
    return render(request, "incharge/reviewers.html", user=user, reviewers=reviewers,
                  themes=my_themes, values={}, errors=None)


@router.post("/reviewers/create")
def reviewers_create(
    request: Request,
    user: dict = Depends(PANEL_USER),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    themes: list[str] = Form([]),
):
    my_themes = _theme_choices(user)
    allowed = {t["label"] for t in my_themes}
    reviewers = [r for r in reviewers_list() if set(r.get("themes") or []) & allowed]
    data = {"name": name, "email": email, "password": password, "themes": themes}
    form, errors = validate(InchargeForm, data)
    if form:
        chosen = set(form.themes) or set()
        ordered = [t for t in THEME_LABELS if t in chosen and t in allowed]
        if not ordered:
            errors = errors or ["Assign at least one theme you manage."]
        form.themes = ordered
    if not errors and one("users", email=form.email):
        errors = ["This email is already in use."]
    if errors:
        return render(request, "incharge/reviewers.html", user=user,
                      reviewers=reviewers, themes=my_themes, values=data, errors=errors)
    create_reviewer(form.name, form.email, form.password, form.themes, created_by=user["id"])
    send_credentials_email(form.name, form.email, form.password, "Reviewer")
    return flash_response("/incharge/reviewers", "reviewer_created")


def _back_url(user: dict) -> str:
    return "/incharge/dashboard" if user["role"] == "theme_incharge" else "/admin/submissions"
