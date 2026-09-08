"""Theme incharge routes — dashboard, reviewer assignment, round-1 feedback, round-2 final decision."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import InchargeForm, ReviewerCreateForm, ReviewForm, RoundOneReviewForm, THEME_LABELS, validate
from app_routes.service import (
    apply_final_decision,
    apply_round1_feedback,
    assign_reviewer,
    create_reviewer,
    current_view,
    decorated_subs,
    detail_actions,
    eligible_reviewers,
    filter_submissions,
    find_reviewer,
    has_round2,
    reviewers_list,
    round1_view,
    scoped_submissions,
    students_map,
    submission_actions,
    submission_for,
    thread_submissions,
    unassign_reviewer,
)
from app_routes.utils import flash_response, render, render_msg
from auth import require_any
from db import one
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


@router.get("/dashboard")
def dashboard(
    request: Request,
    user: dict = Depends(PANEL_USER),
    theme: str = "",
    status: str = "",
    type: str = "",
    round: str = "",
):
    all_subs = scoped_submissions(user)
    subs = _decorate(user, filter_submissions(all_subs, theme, status, type, round))
    pending = sum(1 for s in all_subs if s["status"] == "pending")
    decisions = sum(1 for s in all_subs if s["status"] == "awaiting_decision")
    return render_msg(
        request,
        "incharge/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        subs=subs,
        themes=_theme_choices(user),
        filters={"theme": theme, "status": status, "type": type, "round": round},
        pending=pending,
        decisions=decisions,
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
        sub=current_view(sub),
        students=students_map(),
        themes=_theme_choices(user),
        actions=detail_actions(user, sub),
        thread=thread_submissions(sub),
        back_url=_back_url(user),
    )


# ---------- review: Round 1 feedback OR Round 2 final decision ----------

@router.get("/review/{sid}")
def review_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if not has_round2(sub):
        if sub["status"] not in ("pending", "under_review"):
            return flash_response(_back_url(user), "bad_status")
        values = {"comment": sub["reviewer_comment"] or ""}
        return render_msg(
            request, "incharge/review.html",
            msg=request.query_params.get("msg"),
            user=user, sub=round1_view(sub), students=students_map(), themes=_theme_choices(user),
            back_url=_back_url(user), mode="feedback", values=values, errors=None,
            thread=thread_submissions(sub),
        )
    if sub["status"] != "awaiting_decision":
        return flash_response(_back_url(user), "bad_status")
    values = {"decision": "", "comment": sub["review_comment"] or ""}
    return render_msg(
        request, "incharge/review.html",
        msg=request.query_params.get("msg"),
        user=user, sub=current_view(sub), students=students_map(), themes=_theme_choices(user),
        back_url=_back_url(user), mode="decision", values=values, errors=None,
        thread=thread_submissions(sub),
    )


@router.post("/review/{sid}")
def review_submit(
    request: Request,
    sid: str,
    user: dict = Depends(PANEL_USER),
    decision: str = Form(""),
    comment: str = Form(""),
):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if not has_round2(sub):
        form, errors = validate(RoundOneReviewForm, {"comment": comment})
        if errors:
            return render_msg(
                request, "incharge/review.html",
                user=user, sub=round1_view(sub), students=students_map(), themes=_theme_choices(user),
                back_url=_back_url(user), mode="feedback",
                values={"comment": comment}, errors=errors,
                thread=thread_submissions(sub),
            )
        _, e = apply_round1_feedback(user, sid, form.comment)
        return flash_response(_back_url(user), e or "feedback_sent")
    form, errors = validate(ReviewForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request, "incharge/review.html",
            user=user, sub=current_view(sub), students=students_map(), themes=_theme_choices(user),
            back_url=_back_url(user), mode="decision",
            values={"decision": decision, "comment": comment}, errors=errors,
            thread=thread_submissions(sub),
        )
    _, e = apply_final_decision(user, sid, form.decision, form.comment)
    if e:
        return flash_response(_back_url(user), e)
    return flash_response(_back_url(user), "review_saved")


# ---------- reviewer assignment (Round 1) ----------

@router.get("/assign/{sid}")
def assign_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if has_round2(sub) or sub["status"] != "pending":
        return flash_response(_back_url(user), "submission_not_pending")
    return render(
        request,
        "incharge/assign.html",
        sub=sub,
        reviewers=eligible_reviewers(sub["theme"]),
        themes=_theme_choices(user),
        students=students_map(),
        values={},
        errors=None,
    )


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
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if has_round2(sub) or sub["status"] != "pending":
        return flash_response(_back_url(user), "submission_not_pending")
    eligible = eligible_reviewers(sub["theme"])

    if reviewer_id:
        reviewer = find_reviewer(reviewer_id)
        if not reviewer:
            return render(request, "incharge/assign.html", sub=sub, reviewers=eligible,
                          themes=_theme_choices(user), students=students_map(), values={"reviewer_id": reviewer_id},
                          errors=["Reviewer not found."])
        if sub["theme"] not in (reviewer.get("themes") or []):
            return render(request, "incharge/assign.html", sub=sub, reviewers=eligible,
                          themes=_theme_choices(user), students=students_map(), values={"reviewer_id": reviewer_id},
                          errors=["That reviewer isn't assigned to this theme — adjust their themes first."])
        _, e = assign_reviewer(user, sid, reviewer)
        return flash_response(_back_url(user), e or "assigned_reviewer")

    data = {"name": name, "email": email, "password": password}
    form, errors = validate(ReviewerCreateForm, data)
    existing = one("users", email=form.email) if form else None
    if existing:
        if existing["role"] == "reviewer":
            if sub["theme"] not in (existing.get("themes") or []):
                return render(request, "incharge/assign.html", sub=sub, reviewers=eligible,
                              themes=_theme_choices(user), students=students_map(), values=data,
                              errors=["That email is already a reviewer but not assigned to this theme — adjust their themes first."])
            _, e = assign_reviewer(user, sid, existing)
            return flash_response(_back_url(user), "reviewer_exists_assigned")
        return render(request, "incharge/assign.html", sub=sub, reviewers=eligible,
                      themes=_theme_choices(user), students=students_map(), values=data,
                      errors=["That email belongs to a student / incharge / admin account — use a reviewer account or a different email."])
    if errors:
        return render(request, "incharge/assign.html", sub=sub, reviewers=eligible,
                      themes=_theme_choices(user), students=students_map(), values=data, errors=errors)
    reviewer = create_reviewer(form.name, form.email, form.password, [sub["theme"]], created_by=user["id"])
    _, e = assign_reviewer(user, sid, reviewer)
    return flash_response(_back_url(user), e or "reviewer_created_assigned")


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
        errors = ["An account with this email already exists."]
    if errors:
        return render(request, "incharge/reviewers.html", user=user,
                      reviewers=reviewers, themes=my_themes, values=data, errors=errors)
    create_reviewer(form.name, form.email, form.password, form.themes, created_by=user["id"])
    return flash_response("/incharge/reviewers", "reviewer_created")


def _back_url(user: dict) -> str:
    return "/incharge/dashboard" if user["role"] == "theme_incharge" else "/admin/submissions"