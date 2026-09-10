"""Theme incharge routes — dashboard, reviewer assignment, round-1 decision, round-2 decision."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import (
    InchargeForm,
    ReviewerCreateForm,
    RoundOneDecisionForm,
    RoundTwoDecisionForm,
    THEME_LABELS,
    validate,
)
from app_routes.service import (
    apply_final_decision,
    apply_round1_decision,
    assign_reviewer,
    create_reviewer,
    decorated_subs,
    detail_actions,
    eligible_reviewers,
    filter_submissions,
    find_reviewer,
    reviewers_list,
    round1_view,
    round2_view,
    scoped_submissions,
    students_map,
    submission_actions,
    submission_for,
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


def _decorate(user: dict, subs: list, round_no: int = 1) -> list:
    return decorated_subs(subs, students_map(), lambda s: submission_actions(user, s, round_no), round_no)


def _round_stats(all_subs: list, round_no: int) -> tuple:
    if round_no == 2:
        pending = sum(1 for s in all_subs if s.get("r2_status") == "r2_pending")
        under_review = sum(1 for s in all_subs if s.get("r2_status") == "r2_under_review")
    else:
        pending = sum(1 for s in all_subs if s["r1_status"] == "r1_pending")
        under_review = sum(1 for s in all_subs if s["r1_status"] == "r1_under_review")
    return pending, under_review


@router.get("/dashboard")
def dashboard(
    request: Request,
    user: dict = Depends(PANEL_USER),
    theme: str = "",
    status: str = "",
    type: str = "",
    round: int = 1,
):
    round_no = 2 if round == 2 else 1
    all_subs = scoped_submissions(user)
    subs = _decorate(user, filter_submissions(all_subs, theme, status, type, round_no), round_no)
    pending, under_review = _round_stats(all_subs, round_no)
    return render_msg(
        request,
        "incharge/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        subs=subs,
        themes=_theme_choices(user),
        filters={"theme": theme, "status": status, "type": type, "round": round_no},
        pending=pending,
        under_review=under_review,
    )


@router.get("/submission/{sid}")
def submission_detail(request: Request, sid: str, user: dict = Depends(PANEL_USER), round: int = 1):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    round_no = 2 if round == 2 else 1
    view = round2_view(sub) if round_no == 2 else round1_view(sub)
    return render(
        request,
        "incharge/submission.html",
        user=user,
        sub=view,
        students=students_map(),
        themes=_theme_choices(user),
        actions=detail_actions(user, sub, round_no),
        back_url=_back_url(user, round_no),
        round_no=round_no,
    )


# ---------- review: Round 1 decision (Selected for Round 2 / Not Selected) ----------

@router.get("/review/{sid}")
def review_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub["r1_status"] not in ("r1_pending", "r1_under_review"):
        return flash_response(_back_url(user), "bad_status")
    values = {"decision": "", "comment": sub["r1_comment"] or ""}
    return render_msg(
        request, "incharge/review.html",
        msg=request.query_params.get("msg"),
        user=user, sub=round1_view(sub), students=students_map(), themes=_theme_choices(user),
        back_url=_back_url(user), values=values, errors=None,
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
    if sub["r1_status"] not in ("r1_pending", "r1_under_review"):
        return flash_response(_back_url(user), "bad_status")
    form, errors = validate(RoundOneDecisionForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request, "incharge/review.html",
            user=user, sub=round1_view(sub), students=students_map(), themes=_theme_choices(user),
            back_url=_back_url(user), values={"decision": decision, "comment": comment}, errors=errors,
        )
    _, e = apply_round1_decision(user, sid, form.decision, form.comment)
    if e:
        return flash_response(_back_url(user), e)
    return flash_response(_back_url(user), "r1_decision_saved")


# ---------- review: final decision (Selected / Not Selected) ----------

@router.get("/review/{sid}/round2")
def review2_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("r2_status") not in ("r2_pending", "r2_under_review"):
        return flash_response(_back_url(user), "bad_status")
    if not sub.get("r2_status"):
        return flash_response(_back_url(user), "need_content")
    values = {"decision": "", "comment": sub.get("r2_comment") or ""}
    return render_msg(
        request, "incharge/review2.html",
        msg=request.query_params.get("msg"),
        user=user, sub=round2_view(sub), students=students_map(), themes=_theme_choices(user),
        back_url=_back_url(user), values=values, errors=None,
    )


@router.post("/review/{sid}/round2")
def review2_submit(
    request: Request,
    sid: str,
    user: dict = Depends(PANEL_USER),
    decision: str = Form(""),
    comment: str = Form(""),
):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("r2_status") not in ("r2_pending", "r2_under_review"):
        return flash_response(_back_url(user), "bad_status")
    form, errors = validate(RoundTwoDecisionForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request, "incharge/review2.html",
            user=user, sub=round2_view(sub), students=students_map(), themes=_theme_choices(user),
            back_url=_back_url(user), values={"decision": decision, "comment": comment}, errors=errors,
        )
    _, e = apply_final_decision(user, sid, form.decision, form.comment)
    if e:
        return flash_response(_back_url(user), e)
    return flash_response(_back_url(user), "final_decision_saved")


# ---------- reviewer assignment (Round 1 / Round 2) ----------

def _render_assign(request, user: dict, sub: dict, round_no: int, values: dict, errors: list | None):
    return render(
        request,
        "incharge/assign.html",
        sub=sub,
        round=round_no,
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
    if sub["r1_status"] != "r1_pending":
        return flash_response(_back_url(user), "submission_not_pending")
    return _render_assign(request, user, sub, 1, {}, None)


@router.get("/assign/{sid}/round2")
def assign2_form(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if sub.get("r2_status") != "r2_pending":
        return flash_response(_back_url(user), "submission_not_pending")
    if not sub.get("r2_status"):
        return flash_response(_back_url(user), "need_content")
    return _render_assign(request, user, sub, 2, {}, None)


def _assign_submit(request: Request, sid: str, user: dict, round_no: int,
                   reviewer_id: str, name: str, email: str, password: str):
    sub, err = submission_for(user, sid)
    if err:
        return flash_response(_back_url(user), err)
    if round_no == 1:
        if sub["r1_status"] != "r1_pending":
            return flash_response(_back_url(user), "submission_not_pending")
    elif sub.get("r2_status") != "r2_pending":
        return flash_response(_back_url(user), "submission_not_pending")
    elif not sub.get("r2_status"):
        return flash_response(_back_url(user), "need_content")
    eligible = eligible_reviewers(sub["theme"])

    if reviewer_id:
        reviewer = find_reviewer(reviewer_id)
        if not reviewer:
            return _render_assign(request, user, sub, round_no, {"reviewer_id": reviewer_id},
                                  ["Reviewer not found."])
        if sub["theme"] not in (reviewer.get("themes") or []):
            return _render_assign(request, user, sub, round_no, {"reviewer_id": reviewer_id},
                                  ["That reviewer isn't assigned to this theme — adjust their themes first."])
        _, e = assign_reviewer(user, sid, reviewer, round_no)
        return flash_response(_back_url(user), e or "assigned_reviewer")

    data = {"name": name, "email": email, "password": password}
    form, errors = validate(ReviewerCreateForm, data)
    existing = one("users", email=form.email) if form else None
    if existing:
        if existing["role"] == "reviewer":
            if sub["theme"] not in (existing.get("themes") or []):
                return _render_assign(request, user, sub, round_no, data,
                                      ["That email is already a reviewer but not assigned to this theme — adjust their themes first."])
            _, e = assign_reviewer(user, sid, existing, round_no)
            return flash_response(_back_url(user), "reviewer_exists_assigned")
        return _render_assign(request, user, sub, round_no, data,
                              ["That email belongs to a student / incharge / admin account — use a reviewer account or a different email."])
    if errors:
        return _render_assign(request, user, sub, round_no, data, errors)
    reviewer = create_reviewer(form.name, form.email, form.password, [sub["theme"]], created_by=user["id"])
    _, e = assign_reviewer(user, sid, reviewer, round_no)
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
    return _assign_submit(request, sid, user, 1, reviewer_id, name, email, password)


@router.post("/assign/{sid}/round2")
def assign2_submit(
    request: Request,
    sid: str,
    user: dict = Depends(PANEL_USER),
    reviewer_id: str = Form(""),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
):
    return _assign_submit(request, sid, user, 2, reviewer_id, name, email, password)


@router.get("/takeover/{sid}")
def takeover(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    _, err = unassign_reviewer(user, sid, 1)
    if err:
        return flash_response(_back_url(user), err)
    return flash_response(f"/incharge/review/{sid}", "reviewer_removed")


@router.get("/takeover/{sid}/round2")
def takeover2(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    _, err = unassign_reviewer(user, sid, 2)
    if err:
        return flash_response(_back_url(user), err)
    return flash_response(f"/incharge/review/{sid}/round2", "reviewer_removed")


@router.get("/change_reviewer/{sid}")
def change_reviewer(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    _, err = unassign_reviewer(user, sid, 1)
    if err:
        return flash_response(_back_url(user), err)
    return flash_response(f"/incharge/assign/{sid}", "reviewer_removed")


@router.get("/change_reviewer/{sid}/round2")
def change_reviewer2(request: Request, sid: str, user: dict = Depends(PANEL_USER)):
    _, err = unassign_reviewer(user, sid, 2)
    if err:
        return flash_response(_back_url(user), err)
    return flash_response(f"/incharge/assign/{sid}/round2", "reviewer_removed")


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


def _back_url(user: dict, round_no: int = 1) -> str:
    base = "/incharge/dashboard" if user["role"] == "theme_incharge" else "/admin/submissions"
    return f"{base}?round={round_no}" if round_no == 2 else base