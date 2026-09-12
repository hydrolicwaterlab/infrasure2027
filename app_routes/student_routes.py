"""Student routes — dashboard, threads (round 1 apply/edit), format choice, round 2 content, info, payment."""
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app_routes.schemas import (
    MAX_SUBMISSIONS,
    AttendanceForm,
    FormatChoiceForm,
    RoundTwoForm,
    SubmissionForm,
    validate,
)
from app_routes.service import (
    choose_format,
    create_round1,
    current_view,
    has_selected_submission,
    info_complete,
    now,
    payment_eligible,
    registration_for,
    round2_view,
    round1_view,
    site_flag,
    student_threads,
    students_map,
    submit_round2_content,
    thread_count,
    upload_round2_pdf,
)
from app_routes.utils import flash_response, flash_text, render, render_msg
from auth import require_role
from db import insert, one, update
from otp import latest_otp_payload, send_otp, verify_otp

router = APIRouter(prefix="/student")


def _attendance_fields(form, user: dict) -> dict:
    """Turn a validated AttendanceForm into the persistent registration fields."""
    return {
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


def _render_info_with_otp(request, user, reg, values, email, otp_error=None, flash=None):
    """Re-render the participant info form with the OTP modal open."""
    from app_routes.schemas import _is_personal_email
    ctx = dict(
        request=request,
        template="student/info_form.html",
        mode="edit" if reg else "create",
        reg=reg,
        values={**values, "email": user["email"]},
        user=user,
        account_is_personal=_is_personal_email(user["email"]),
        otp_show=True,
        otp_email=email,
        otp_purpose="institute",
        otp_purpose_label="verify your institute email",
        otp_resend_url="/student/info",
        otp_action="/student/verifyotp",
    )
    if otp_error:
        ctx["otp_error"] = otp_error
    if flash:
        ctx.update(flash_text(flash))
    return render(**ctx)


def _owned_submission(user: dict, sid: str):
    """Any of the student's own submissions, regardless of status."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, flash_response("/student/dashboard", "submission_not_found")
    return sub, None


@router.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(require_role("student"))):
    threads = [current_view(s) for s in student_threads(user)]
    reg = registration_for(user)
    has_selected = has_selected_submission(user)
    can_apply = info_complete(user) and thread_count(user) < MAX_SUBMISSIONS
    return render_msg(
        request,
        "student/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        threads=threads,
        reg=reg,
        has_selected=has_selected,
        can_apply=can_apply,
        info_done=info_complete(user),
        slots_left=max(0, MAX_SUBMISSIONS - len(threads)),
    )


# ---------- participant info (required before applying) ----------

@router.get("/info")
def info_form(request: Request, user: dict = Depends(require_role("student"))):
    if not site_flag("registration_open"):
        return flash_response("/student/dashboard", "registration_closed")
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/student/dashboard", "attendance_locked")
    q = request.query_params
    if q.get("resend"):
        email = (q.get("otp_email") or "").strip().lower()
        payload = latest_otp_payload(email, "institute")
        if payload and payload.get("user_id") == user["id"]:
            send_otp(email, "institute", payload=payload)
            return _render_info_with_otp(request, user, reg, payload.get("values", {}), email, flash="institute_otp_sent")
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
    if not site_flag("registration_open"):
        return flash_response("/student/dashboard", "registration_closed")
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
    # Gate new/changed institute emails behind an OTP.
    effective_inst = (form.institute_email or "").strip().lower()
    account_email = user["email"].strip().lower()
    already_verified = ((reg or {}).get("verified_institute_email") or "").strip().lower()
    needs_verify = bool(effective_inst) and effective_inst != account_email and effective_inst != already_verified
    if needs_verify:
        payload = {
            "values": _attendance_fields(form, user),
            "user_id": user["id"],
            "reg_id": (reg or {}).get("id", ""),
        }
        send_otp(effective_inst, "institute", payload=payload)
        return _render_info_with_otp(request, user, reg, _attendance_fields(form, user), effective_inst,
                                     flash="institute_otp_sent")
    fields = _attendance_fields(form, user)
    fields["verified_institute_email"] = form.institute_email
    if reg:
        update("registrations", reg["id"], fields)
        return flash_response("/student/dashboard", "attendance_updated")
    insert("registrations", {
        "user_id": user["id"], **fields,
        "status": "pending", "fee_paid": False, "created_at": now(),
    }, prefix="r")
    return flash_response("/student/dashboard", "attendance_created")


@router.post("/verifyotp")
def verify_institute_otp(
    request: Request,
    user: dict = Depends(require_role("student")),
    email: str = Form(""),
    purpose: str = Form(""),
    code: str = Form(""),
):
    if not site_flag("registration_open"):
        return flash_response("/student/dashboard", "registration_closed")
    if purpose != "institute":
        return flash_response("/student/info", "otp_missing")
    email = (email or "").strip().lower()
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/student/dashboard", "attendance_locked")
    ok, err, payload = verify_otp(email, "institute", code)
    if not ok:
        saved = latest_otp_payload(email, "institute")
        return _render_info_with_otp(request, user, reg, saved.get("values", {}), email,
                                     otp_error=flash_text(err)["error"])
    if not payload or payload.get("user_id") != user["id"]:
        return flash_response("/student/info", "otp_missing")
    fields = payload.get("values", {})
    fields["verified_institute_email"] = fields.get("institute_email", "")
    if reg:
        update("registrations", reg["id"], fields)
    else:
        insert("registrations", {
            "user_id": user["id"], **fields,
            "status": "pending", "fee_paid": False, "created_at": now(),
        }, prefix="r")
    return flash_response("/student/dashboard", "institute_verified")


# ---------- round 1 ----------

@router.get("/apply")
def apply_form(request: Request, user: dict = Depends(require_role("student"))):
    if not site_flag("round1_open"):
        return flash_response("/student/dashboard", "round1_closed")
    if not info_complete(user):
        return flash_response("/student/info", "info_required")
    if thread_count(user) >= MAX_SUBMISSIONS:
        return flash_response("/student/dashboard", "submissions_full")
    return render(request, "student/round1_form.html", mode="create", values={}, user=user)


@router.post("/apply")
def apply_submit(
    request: Request,
    user: dict = Depends(require_role("student")),
    theme: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
):
    if not site_flag("round1_open"):
        return flash_response("/student/dashboard", "round1_closed")
    if not info_complete(user):
        return flash_response("/student/info", "info_required")
    if thread_count(user) >= MAX_SUBMISSIONS:
        return flash_response("/student/dashboard", "submissions_full")
    data = {"theme": theme, "title": title, "description": description}
    form, errors = validate(SubmissionForm, data)
    if errors:
        return render(request, "student/round1_form.html", mode="create", values=data, errors=errors, user=user)
    create_round1(user, form.theme, form.title, form.description)
    return flash_response("/student/dashboard", "r1_created")


@router.get("/edit/{sid}")
def edit_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if not site_flag("round1_open"):
        return flash_response("/student/dashboard", "round1_closed")
    if sub["r1_status"] != "r1_pending":
        return flash_response("/student/dashboard", "submission_locked")
    return render(request, "student/round1_form.html", mode="edit", sub=sub,
                  values=round1_view(sub), user=user)


@router.post("/edit/{sid}")
def edit_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    theme: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if not site_flag("round1_open"):
        return flash_response("/student/dashboard", "round1_closed")
    if sub["r1_status"] != "r1_pending":
        return flash_response("/student/dashboard", "submission_locked")
    data = {"theme": theme, "title": title, "description": description}
    form, errors = validate(SubmissionForm, data)
    if errors:
        return render(request, "student/round1_form.html", mode="edit", sub=sub,
                      values=data, errors=errors, user=user)
    update("submissions", sid, {
        "theme": form.theme,
        "title_r1": form.title,
        "description_r1": form.description,
    })
    return flash_response("/student/dashboard", "submission_updated")


@router.get("/submission/{sid}")
def submission_detail(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    return render(request, "student/submission.html", user=user, sub=current_view(sub),
                  students=students_map())


# ---------- round 2: format choice then content (poster form / ppt PDF) ----------

def _r2_access_err(sub: dict) -> str | None:
    """Return a flash code if Round-2 content can't be submitted yet, else None."""
    if not site_flag("round1_results_declared"):
        return "round1_results_not_declared"
    if not site_flag("round2_open"):
        return "round2_closed"
    if sub["r1_status"] != "r1_selected":
        return "round2_not_ready"
    if not sub.get("format"):
        return "round2_not_ready"
    if sub.get("r2_status") in ("r2_under_review", "selected", "not_selected"):
        return "content_locked"
    return None


@router.get("/submission/{sid}/round2")
def round2_choice(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if not site_flag("round1_results_declared"):
        return flash_response(f"/student/submission/{sid}", "round1_results_not_declared")
    if not site_flag("round2_open"):
        return flash_response(f"/student/submission/{sid}", "round2_closed")
    if sub["r1_status"] != "r1_selected":
        return flash_response(f"/student/submission/{sid}", "round2_not_ready")
    if sub.get("format"):
        target = "content" if sub["format"] == "poster" else "upload"
        return RedirectResponse(f"/student/submission/{sid}/round2/{target}", status_code=303)
    return render(request, "student/round2_choice.html", user=user, sub=round1_view(sub),
                  values={"format": sub.get("format") or ""}, errors=None, students=students_map())


@router.post("/submission/{sid}/round2")
def round2_choose(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    format: str = Form(""),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if not site_flag("round1_results_declared"):
        return flash_response(f"/student/submission/{sid}", "round1_results_not_declared")
    if not site_flag("round2_open"):
        return flash_response(f"/student/submission/{sid}", "round2_closed")
    form, errors = validate(FormatChoiceForm, {"format": format})
    if errors:
        return render(request, "student/round2_choice.html", user=user, sub=round1_view(sub),
                      values={"format": format}, errors=errors, students=students_map())
    _, err = choose_format(user, sid, form.format)
    if err:
        return flash_response(f"/student/submission/{sid}/round2", err)
    target = "content" if form.format == "poster" else "upload"
    return flash_response(f"/student/submission/{sid}/round2/{target}", "format_chosen")


# ----- poster: revised title + abstract -----

@router.get("/submission/{sid}/round2/content")
def round2_content_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if (sub.get("format") or "") != "poster":
        return flash_response(f"/student/submission/{sid}", "bad_format")
    err = _r2_access_err(sub)
    if err:
        return flash_response(f"/student/submission/{sid}", err)
    return render(request, "student/round2_content.html", user=user, sub=round2_view(sub),
                  values={"title": sub.get("title_r2") or "", "description": sub.get("description_r2") or ""},
                  errors=None, students=students_map())


@router.post("/submission/{sid}/round2/content")
def round2_content_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    title: str = Form(""),
    description: str = Form(""),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if (sub.get("format") or "") != "poster":
        return flash_response(f"/student/submission/{sid}", "bad_format")
    err = _r2_access_err(sub)
    if err:
        return flash_response(f"/student/submission/{sid}", err)
    form, errors = validate(RoundTwoForm, {"title": title, "description": description})
    if errors:
        return render(request, "student/round2_content.html", user=user, sub=round2_view(sub),
                      values={"title": title, "description": description}, errors=errors, students=students_map())
    _, e = submit_round2_content(user, sid, form.title, form.description)
    if e:
        return flash_response(f"/student/submission/{sid}", e)
    return flash_response(f"/student/submission/{sid}", "r2_content_saved")


# ----- ppt: PDF upload -----

@router.get("/submission/{sid}/round2/upload")
def round2_upload_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if (sub.get("format") or "") != "ppt":
        return flash_response(f"/student/submission/{sid}", "bad_format")
    err = _r2_access_err(sub)
    if err:
        return flash_response(f"/student/submission/{sid}", err)
    return render(request, "student/round2_upload.html", user=user, sub=round2_view(sub),
                  errors=None, students=students_map())


@router.post("/submission/{sid}/round2/upload")
async def round2_upload_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    file: UploadFile = File(...),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if (sub.get("format") or "") != "ppt":
        return flash_response(f"/student/submission/{sid}", "bad_format")
    err = _r2_access_err(sub)
    if err:
        return flash_response(f"/student/submission/{sid}", err)
    data = await file.read()
    _, e = upload_round2_pdf(user, sid, file.filename or "submission.pdf", data)
    if e:
        return flash_response(f"/student/submission/{sid}/round2/upload", e)
    return flash_response(f"/student/submission/{sid}", "r2_uploaded")


# ---------- payment (requires final selection + declared results + open phase + approved info) ----------

@router.get("/payment")
def payment_page(request: Request, user: dict = Depends(require_role("student"))):
    if not has_selected_submission(user):
        return flash_response("/student/dashboard", "need_selected")
    if not site_flag("round2_results_declared"):
        return flash_response("/student/dashboard", "round2_results_not_declared")
    if not site_flag("payment_open"):
        return flash_response("/student/dashboard", "payment_closed")
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
    if not site_flag("round2_results_declared"):
        return flash_response("/student/dashboard", "round2_results_not_declared")
    if not site_flag("payment_open"):
        return flash_response("/student/dashboard", "payment_closed")
    reg = registration_for(user)
    if not reg:
        return flash_response("/student/info", "payment_ready")
    if not payment_eligible(reg):
        return flash_response("/student/dashboard", "admin_approval_required")
    update("registrations", reg["id"], {"fee_paid": True})
    return flash_response("/student/payment", "fee_paid_success")