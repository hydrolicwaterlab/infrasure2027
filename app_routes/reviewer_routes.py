"""Reviewer routes — dashboards + Round 1 / Round 2 decisions."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import RoundOneDecisionForm, RoundTwoDecisionForm, validate
from app_routes.service import (
    apply_final_decision,
    apply_round1_decision,
    current_view,
    reviewer_round2_submissions,
    reviewer_submissions,
    students_map,
)
from app_routes.utils import flash_response, render_msg
from auth import require_role
from db import one
from site_config import SITE_CONFIG

router = APIRouter(prefix="/reviewer")

REVIEWER = require_role("reviewer")


def review_for(reviewer: dict, sid: str):
    """Return (submission, flash_code | None) — Round 1, assigned to this reviewer, still open."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("r1_reviewer_id") != reviewer["id"]:
        return None, "not_your_assignment"
    if sub["r1_status"] != "r1_under_review":
        return None, "bad_status"
    return sub, None


def review2_for(reviewer: dict, sid: str):
    """Return (submission, flash_code | None) — Round 2, assigned to this reviewer, still open."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("r2_reviewer_id") != reviewer["id"]:
        return None, "not_your_assignment"
    if sub.get("r2_status") != "r2_under_review":
        return None, "bad_status"
    if not sub.get("r2_status"):
        return None, "need_content"
    return sub, None


def _decorate(subs: list) -> list:
    students = students_map()
    out = []
    for s in subs:
        row = current_view(s)
        row["_student"] = (students.get(s["user_id"]) or {}).get("name", "—")
        out.append(row)
    return out


@router.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(REVIEWER)):
    r1_subs = reviewer_submissions(user)
    r2_subs = reviewer_round2_submissions(user)
    to_review = [s for s in r1_subs if s["r1_status"] == "r1_under_review"]
    done = [s for s in r1_subs if s["r1_status"] in ("r1_selected", "r1_not_selected")]
    r2_to_review = [s for s in r2_subs if s.get("r2_status") == "r2_under_review"]
    r2_done = [s for s in r2_subs if s.get("r2_status") in ("selected", "not_selected")]
    return render_msg(
        request,
        "reviewer/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        themes=SITE_CONFIG["themes"],
        to_review=_decorate(to_review),
        done=_decorate(done),
        r2_to_review=_decorate(r2_to_review),
        r2_done=_decorate(r2_done),
    )


@router.get("/review/{sid}")
def review_form(request: Request, sid: str, user: dict = Depends(REVIEWER)):
    sub, err = review_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    return render_msg(
        request,
        "reviewer/review.html",
        user=user,
        sub=current_view(sub),
        students=students_map(),
        values={"decision": "", "comment": sub.get("r1_comment") or ""},
        errors=None,
    )


@router.post("/review/{sid}")
def review_submit(
    request: Request,
    sid: str,
    user: dict = Depends(REVIEWER),
    decision: str = Form(""),
    comment: str = Form(""),
):
    sub, err = review_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    form, errors = validate(RoundOneDecisionForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request,
            "reviewer/review.html",
            user=user,
            sub=current_view(sub),
            students=students_map(),
            values={"decision": decision, "comment": comment},
            errors=errors,
        )
    _, e = apply_round1_decision(user, sid, form.decision, form.comment)
    if e:
        return flash_response("/reviewer/dashboard", e)
    return flash_response("/reviewer/dashboard", "review_submitted")


@router.get("/review/{sid}/round2")
def review2_form(request: Request, sid: str, user: dict = Depends(REVIEWER)):
    sub, err = review2_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    return render_msg(
        request,
        "reviewer/review2.html",
        user=user,
        sub=current_view(sub),
        students=students_map(),
        values={"decision": "", "comment": sub.get("r2_comment") or ""},
        errors=None,
    )


@router.post("/review/{sid}/round2")
def review2_submit(
    request: Request,
    sid: str,
    user: dict = Depends(REVIEWER),
    decision: str = Form(""),
    comment: str = Form(""),
):
    sub, err = review2_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    form, errors = validate(RoundTwoDecisionForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request,
            "reviewer/review2.html",
            user=user,
            sub=current_view(sub),
            students=students_map(),
            values={"decision": decision, "comment": comment},
            errors=errors,
        )
    _, e = apply_final_decision(user, sid, form.decision, form.comment)
    if e:
        return flash_response("/reviewer/dashboard", e)
    return flash_response("/reviewer/dashboard", "final_decision_saved")