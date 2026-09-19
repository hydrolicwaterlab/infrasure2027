"""Reviewer routes — dashboards, round-1 feedback, final decision."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import FinalDecisionForm, PaperFeedbackForm, validate
from app_routes.service import (
    apply_final_decision,
    current_view,
    reviewer_submissions,
    save_feedback,
    split_paper_stages,
    students_map,
)
from app_routes.utils import flash_response, render_msg
from auth import require_role
from db import one
from site_config import SITE_CONFIG

router = APIRouter(prefix="/reviewer")

REVIEWER = require_role("reviewer")


def _review_for(reviewer: dict, sid: str):
    """Return (submission, flash_code | None) — assigned, awaiting feedback."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("reviewer_id") != reviewer["id"]:
        return None, "not_your_assignment"
    if sub.get("status") != "under_review":
        return None, "bad_status"
    return sub, None


def _final_for(reviewer: dict, sid: str):
    """Return (submission, flash_code | None) — assigned, Round 2 submitted, awaiting final decision."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("reviewer_id") != reviewer["id"]:
        return None, "not_your_assignment"
    if sub.get("status") != "round2_submitted":
        return None, "bad_status"
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
    subs = reviewer_submissions(user)
    feedback_subs, round2_subs, final_subs, done = split_paper_stages(subs)
    to_review_count = len(feedback_subs) + len(final_subs)
    return render_msg(
        request,
        "reviewer/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        themes=SITE_CONFIG["themes"],
        feedback_subs=_decorate(feedback_subs),
        round2_subs=_decorate(round2_subs),
        final_subs=_decorate(final_subs),
        done=_decorate(done),
        to_review_count=to_review_count,
    )


@router.get("/review/{sid}")
def review_form(request: Request, sid: str, user: dict = Depends(REVIEWER)):
    sub, err = _review_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    return render_msg(
        request,
        "reviewer/review.html",
        user=user,
        sub=current_view(sub),
        students=students_map(),
        values={"feedback": sub.get("feedback") or ""},
        errors=None,
    )


@router.post("/review/{sid}")
def review_submit(
    request: Request,
    sid: str,
    user: dict = Depends(REVIEWER),
    feedback: str = Form(""),
):
    sub, err = _review_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    form, errors = validate(PaperFeedbackForm, {"feedback": feedback})
    if errors:
        return render_msg(
            request,
            "reviewer/review.html",
            user=user,
            sub=current_view(sub),
            students=students_map(),
            values={"feedback": feedback},
            errors=errors,
        )
    _, e = save_feedback(user, sid, form.feedback)
    if e:
        return flash_response("/reviewer/dashboard", e)
    return flash_response("/reviewer/dashboard", "feedback_saved")


@router.get("/final/{sid}")
def final_form(request: Request, sid: str, user: dict = Depends(REVIEWER)):
    sub, err = _final_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    return render_msg(
        request,
        "reviewer/decision.html",
        user=user,
        sub=current_view(sub),
        students=students_map(),
        values={"decision": "", "comment": sub.get("decision_comment") or ""},
        errors=None,
    )


@router.post("/final/{sid}")
def final_submit(
    request: Request,
    sid: str,
    user: dict = Depends(REVIEWER),
    decision: str = Form(""),
    comment: str = Form(""),
):
    sub, err = _final_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    form, errors = validate(FinalDecisionForm, {"decision": decision, "comment": comment})
    if errors:
        return render_msg(
            request,
            "reviewer/decision.html",
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
