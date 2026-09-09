"""Student routes — dashboard, threads (round1 apply/edit, round2), info, payment."""
from fastapi import APIRouter, Depends, Form, Request

from app_routes.schemas import MAX_SUBMISSIONS, RoundTwoForm, SubmissionForm, AttendanceForm, validate
from app_routes.service import (
    create_round1,
    has_round2,
    has_selected_submission,
    info_complete,
    now,
    payment_eligible,
    registration_for,
    round1_view,
    round2_of,
    student_threads,
    students_map,
    submit_round2,
    thread_count,
)
from app_routes.utils import flash_response, render, render_msg
from auth import require_role
from db import insert, one, update

router = APIRouter(prefix="/student")


def _owned_submission(user: dict, sid: str):
    """Any of the student's own submissions, regardless of status."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, flash_response("/student/dashboard", "submission_not_found")
    return sub, None


def _own_round1(user: dict, sid: str):
    """The student's own submission (the thread anchor)."""
    return _owned_submission(user, sid)


@router.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(require_role("student"))):
    threads = student_threads(user)
    decorated = []
    for r1 in threads:
        row = dict(r1)
        row["title"] = (r1.get("title_r2") or "").strip() or (r1.get("title_r1") or "")
        row["description"] = (r1.get("description_r2") or "").strip() or (r1.get("description_r1") or "")
        row["round2"] = round2_of(r1)
        decorated.append(row)
    reg = registration_for(user)
    has_selected = has_selected_submission(user)
    can_apply = info_complete(user) and thread_count(user) < MAX_SUBMISSIONS
    return render_msg(
        request,
        "student/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        threads=decorated,
        reg=reg,
        has_selected=has_selected,
        can_apply=can_apply,
        info_done=info_complete(user),
        slots_left=max(0, MAX_SUBMISSIONS - len(threads)),
    )


# ---------- participant info (required before applying) ----------

@router.get("/info")
def info_form(request: Request, user: dict = Depends(require_role("student"))):
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/student/dashboard", "attendance_locked")
    values = dict(reg) if reg else {"full_name": user["name"], "email": user["email"]}
    # checkbox prefill: if saved email equals account email and account is institutional
    from app_routes.schemas import _is_personal_email
    account_is_personal = _is_personal_email(user["email"])
    # auto-check if previously saved as same
    if reg and reg.get("institute_email") and reg["institute_email"].lower() == user["email"].lower() and not account_is_personal:
        values.setdefault("institute_email_same", "on")
    if reg and reg.get("company_email") and reg["company_email"].lower() == user["email"].lower() and not account_is_personal:
        values.setdefault("company_email_same", "on")
    return render(request, "student/info_form.html", mode="edit" if reg else "create",
                  reg=reg, values=values, user=user,
                  account_is_personal=account_is_personal)


@router.post("/info")
def info_submit(
    request: Request,
    user: dict = Depends(require_role("student")),
    full_name: str = Form(""),
    phone: str = Form(""),
    participation_mode: str = Form("in_person"),
    participant_category: str = Form(""),
    student_level: str = Form(""),
    ug_program: str = Form(""),
    degree_name: str = Form(""),
    department: str = Form(""),
    institute_name: str = Form(""),
    institute_address: str = Form(""),
    institute_country: str = Form(""),
    institute_zipcode: str = Form(""),
    institute_email: str = Form(""),
    institute_email_same: str = Form(""),
    supervisor_name: str = Form(""),
    academic_role: str = Form(""),
    professor_type: str = Form(""),
    company_name: str = Form(""),
    position: str = Form(""),
    company_email: str = Form(""),
    company_email_same: str = Form(""),
    company_address: str = Form(""),
    company_country: str = Form(""),
    company_zipcode: str = Form(""),
    # legacy (hidden, for backward compat)
    designation: str = Form(""),
    affiliation: str = Form(""),
):
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/student/dashboard", "attendance_locked")
    data = {
        "full_name": full_name, "phone": phone,
        "participation_mode": participation_mode,
        "participant_category": participant_category,
        "student_level": student_level, "ug_program": ug_program,
        "degree_name": degree_name, "department": department,
        "institute_name": institute_name, "institute_address": institute_address,
        "institute_country": institute_country, "institute_zipcode": institute_zipcode,
        "institute_email": institute_email, "institute_email_same": institute_email_same,
        "supervisor_name": supervisor_name,
        "academic_role": academic_role, "professor_type": professor_type,
        "company_name": company_name, "position": position,
        "company_email": company_email, "company_email_same": company_email_same,
        "company_address": company_address,
        "company_country": company_country, "company_zipcode": company_zipcode,
        "account_email": user["email"],
        "designation": designation, "affiliation": affiliation,
    }
    form, errors = validate(AttendanceForm, data)
    if errors:
        from app_routes.schemas import _is_personal_email
        return render(request, "student/info_form.html",
                      mode="edit" if reg else "create", reg=reg,
                      values={**data, "email": user["email"]}, errors=errors, user=user,
                      account_is_personal=_is_personal_email(user["email"]))
    fields = {
        "full_name": form.full_name,
        "email": user["email"],
        "phone": form.phone,
        "participation_mode": form.participation_mode,
        "participant_category": form.participant_category,
        "student_level": form.student_level,
        "ug_program": form.ug_program,
        "degree_name": form.degree_name,
        "department": form.department,
        "institute_name": form.institute_name,
        "institute_address": form.institute_address,
        "institute_country": form.institute_country,
        "institute_zipcode": form.institute_zipcode,
        "institute_email": form.institute_email,
        "supervisor_name": form.supervisor_name,
        "academic_role": form.academic_role,
        "professor_type": form.professor_type,
        "company_name": form.company_name,
        "position": form.position,
        "company_email": form.company_email,
        "company_address": form.company_address,
        "company_country": form.company_country,
        "company_zipcode": form.company_zipcode,
        # keep legacy mirrors for older admin views
        "designation": form.designation or form.participant_category,
        "affiliation": form.affiliation or form.institute_name or form.company_name,
    }
    if reg:
        update("registrations", reg["id"], fields)
        return flash_response("/student/dashboard", "attendance_updated")
    insert("registrations", {
        "user_id": user["id"], **fields,
        "status": "pending", "fee_paid": False, "created_at": now(),
    }, prefix="r")
    return flash_response("/student/dashboard", "attendance_created")


# ---------- round 1 ----------

@router.get("/apply")
def apply_form(request: Request, user: dict = Depends(require_role("student"))):
    if not info_complete(user):
        return flash_response("/student/info", "info_required")
    if thread_count(user) >= MAX_SUBMISSIONS:
        return flash_response("/student/dashboard", "submissions_full")
    return render(request, "student/round1_form.html", mode="create", values={}, user=user)


@router.post("/apply")
def apply_submit(
    request: Request,
    user: dict = Depends(require_role("student")),
    submission_type: str = Form(""),
    theme: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
):
    if not info_complete(user):
        return flash_response("/student/info", "info_required")
    if thread_count(user) >= MAX_SUBMISSIONS:
        return flash_response("/student/dashboard", "submissions_full")
    data = {"submission_type": submission_type, "theme": theme, "title": title, "description": description}
    form, errors = validate(SubmissionForm, data)
    if errors:
        return render(request, "student/round1_form.html", mode="create", values=data, errors=errors, user=user)
    create_round1(user, form.submission_type, form.theme, form.title, form.description)
    return flash_response("/student/dashboard", "submission_created")


@router.get("/edit/{sid}")
def edit_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _own_round1(user, sid)
    if redir:
        return redir
    if sub["status"] != "pending":
        return flash_response("/student/dashboard", "submission_locked")
    return render(request, "student/round1_form.html", mode="edit", sub=sub,
                  values=round1_view(sub), user=user)


@router.post("/edit/{sid}")
def edit_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    submission_type: str = Form(""),
    theme: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
):
    sub, redir = _own_round1(user, sid)
    if redir:
        return redir
    if sub["status"] != "pending":
        return flash_response("/student/dashboard", "submission_locked")
    data = {"submission_type": submission_type, "theme": theme, "title": title, "description": description}
    form, errors = validate(SubmissionForm, data)
    if errors:
        return render(request, "student/round1_form.html", mode="edit", sub=sub,
                      values=data, errors=errors, user=user)
    update("submissions", sid, {
        "submission_type": form.submission_type,
        "theme": form.theme,
        "title_r1": form.title,
        "description_r1": form.description,
    })
    return flash_response("/student/dashboard", "submission_updated")


@router.get("/submission/{sid}")
def submission_detail(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _own_round1(user, sid)
    if redir:
        return redir
    return render(request, "student/submission.html", user=user, sub=round1_view(sub),
                  r2=round2_of(sub), students=students_map())


# ---------- round 2 ----------

@router.get("/submission/{sid}/round2/apply")
def round2_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _own_round1(user, sid)
    if redir:
        return redir
    if sub["status"] != "feedback_given":
        return flash_response(f"/student/submission/{sid}", "round2_not_ready")
    if has_round2(sub):
        return flash_response(f"/student/submission/{sid}/round2", "round2_already_exists")
    return render(request, "student/round2_form.html", mode="create", sub=round1_view(sub),
                  values={}, user=user, students=students_map())


@router.post("/submission/{sid}/round2/apply")
def round2_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    title: str = Form(""),
    description: str = Form(""),
):
    sub, redir = _own_round1(user, sid)
    if redir:
        return redir
    if sub["status"] != "feedback_given":
        return flash_response(f"/student/submission/{sid}", "round2_not_ready")
    data = {"title": title, "description": description}
    form, errors = validate(RoundTwoForm, data)
    if errors:
        return render(request, "student/round2_form.html", mode="create", sub=round1_view(sub),
                      values=data, errors=errors, user=user, students=students_map())
    _, err = submit_round2(user, sid, form.title, form.description)
    if err:
        return flash_response(f"/student/submission/{sid}", err)
    return flash_response(f"/student/submission/{sid}/round2", "round2_submitted")


@router.get("/submission/{sid}/round2")
def round2_detail(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _own_round1(user, sid)
    if redir:
        return redir
    r2 = round2_of(sub)
    if not r2:
        if sub["status"] != "feedback_given":
            return flash_response(f"/student/submission/{sid}", "round2_not_ready")
        return flash_response(f"/student/submission/{sid}/round2/apply", "round2_not_ready")
    return render(request, "student/round2.html", user=user, sub=round1_view(sub), r2=r2,
                  students=students_map())


# ---------- payment (requires selected + admin-approved info) ----------

@router.get("/payment")
def payment_page(request: Request, user: dict = Depends(require_role("student"))):
    if not has_selected_submission(user):
        return flash_response("/student/dashboard", "need_selected")
    reg = registration_for(user)
    if not reg:
        return flash_response("/student/info", "payment_ready")
    if not payment_eligible(reg):
        return flash_response("/student/dashboard", "admin_approval_required")
    return render_msg(request, "student/payment.html", msg=request.query_params.get("msg"),
                      user=user, reg=reg)


@router.post("/payment")
def payment_submit(request: Request, user: dict = Depends(require_role("student"))):
    if not has_selected_submission(user):
        return flash_response("/student/dashboard", "need_selected")
    reg = registration_for(user)
    if not reg:
        return flash_response("/student/info", "payment_ready")
    if not payment_eligible(reg):
        return flash_response("/student/dashboard", "admin_approval_required")
    update("registrations", reg["id"], {"fee_paid": True})
    return flash_response("/student/payment", "fee_paid_success")