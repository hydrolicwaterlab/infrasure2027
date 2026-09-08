"""Reviewer routes — dashboard + Round-1 feedback (questions / requested changes only)."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import RoundOneReviewForm, validate
from app_routes.service import apply_round1_feedback, has_round2, reviewer_submissions, round1_view, students_map
from app_routes.utils import flash_response, render_msg
from auth import require_role
from db import one
from site_config import SITE_CONFIG

router = APIRouter(prefix="/reviewer")

REVIEWER = require_role("reviewer")


def review_for(reviewer: dict, sid: str):
    """Return (submission, flash_code | None) — Round 1, assigned to this reviewer, still under review."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if has_round2(sub):
        return None, "bad_status"
    if sub.get("assigned_reviewer_id") != reviewer["id"]:
        return None, "not_your_assignment"
    if sub["status"] != "under_review":
        return None, "bad_status"
    return sub, None


def _decorate(subs: list) -> list:
    students = students_map()
    out = []
    for s in subs:
        row = round1_view(s)
        row["_student"] = (students.get(s["user_id"]) or {}).get("name", "—")
        out.append(row)
    return out


@router.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(REVIEWER)):
    all_subs = reviewer_submissions(user)
    to_review = [s for s in all_subs if s["status"] == "under_review"]
    done = [s for s in all_subs if s["status"] == "feedback_given"]
    return render_msg(
        request,
        "reviewer/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        themes=SITE_CONFIG["themes"],
        to_review=_decorate(to_review),
        done=_decorate(done),
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
        sub=round1_view(sub),
        students=students_map(),
        values={"comment": sub.get("reviewer_comment") or ""},
        errors=None,
    )


@router.post("/review/{sid}")
def review_submit(
    request: Request,
    sid: str,
    user: dict = Depends(REVIEWER),
    comment: str = Form(""),
):
    sub, err = review_for(user, sid)
    if err:
        return flash_response("/reviewer/dashboard", err)
    form, errors = validate(RoundOneReviewForm, {"comment": comment})
    if errors:
        return render_msg(
            request,
            "reviewer/review.html",
            user=user,
            sub=round1_view(sub),
            students=students_map(),
            values={"comment": comment},
            errors=errors,
        )
    _, e = apply_round1_feedback(user, sid, form.comment)
    if e:
        return flash_response("/reviewer/dashboard", e)
    return flash_response("/reviewer/dashboard", "review_submitted")