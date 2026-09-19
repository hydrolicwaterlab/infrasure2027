"""Student routes — dashboard, participant info, paper submission, revision, presentation choice, payment."""
import re

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app_routes.schemas import (
    PAPER_TYPES,
    AttendanceForm,
    PaperSubmissionForm,
    PresentationChoiceForm,
    Round2Form,
    validate,
)
from app_routes.service import (
    current_view,
    has_selected_submission,
    info_complete,
    now,
    paper_view,
    payable_amount,
    payment_eligible,
    presenting_count,
    presenting_submissions,
    registration_for,
    set_presentation,
    site_flag,
    student_threads,
    students_map,
    submit_paper,
    submit_round2,
    update_paper,
)
from app_routes.utils import flash_response, flash_text, render, render_msg
from auth import require_role
from db import insert, one, update
from otp import latest_otp_payload, send_otp, verify_otp

router = APIRouter(prefix="/participant")

PAPER_TYPE_LABELS = {"full_paper": "Full Paper", "extended_abstract": "Extended Abstract"}


def _split_phone(v: str) -> tuple[str, str]:
    """Split a stored phone value into (country_code, local_number)."""
    v = (v or "").strip()
    m = re.match(r"^(\+\d{1,4})\s*(.*)$", v)
    if m:
        return m.group(1), m.group(2)
    return "+91", v


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
    vals = {**values, "email": user["email"]}
    vals["phone_country_code"], vals["phone_number"] = _split_phone(vals.get("phone"))
    ctx = dict(
        request=request,
        template="student/info_form.html",
        mode="edit" if reg else "create",
        reg=reg,
        values=vals,
        user=user,
        account_is_personal=_is_personal_email(user["email"]),
        otp_show=True,
        otp_email=email,
        otp_purpose="institute",
        otp_purpose_label="verify your institute email",
        otp_resend_url="/participant/info",
        otp_action="/participant/verifyotp",
    )
    if otp_error:
        ctx["otp_error"] = otp_error
    if flash:
        ctx.update(flash_text(flash))
    return render(**ctx)


def _owned_submission(user: dict, sid: str):
    """Any of the student's own papers, regardless of status."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, flash_response("/participant/dashboard", "submission_not_found")
    return sub, None


def _authors_from_form(form_data) -> list[dict]:
    """Zip repeated author_* fields from a Starlette FormData into row dicts."""
    names = form_data.getlist("author_name")
    designations = form_data.getlist("author_designation")
    affiliations = form_data.getlist("author_affiliation")
    emails = form_data.getlist("author_email")
    return [
        {"name": n, "designation": d, "affiliation": a, "email": e}
        for n, d, a, e in zip(names, designations, affiliations, emails)
    ]


def _paper_form_values(theme: str, paper_type: str, presentation_format: str,
                       title: str, authors: list) -> dict:
    return {"theme": theme, "paper_type": paper_type, "presentation_format": presentation_format,
            "title": title, "authors": authors}


@router.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(require_role("student"))):
    threads = [current_view(s) for s in student_threads(user)]
    reg = registration_for(user)
    return render_msg(
        request,
        "student/dashboard.html",
        msg=request.query_params.get("msg"),
        user=user,
        threads=threads,
        reg=reg,
        has_selected=has_selected_submission(user),
        selected_count=sum(1 for s in threads if s["status"] == "selected"),
        presenting_count=presenting_count(user),
        info_done=info_complete(user),
    )


# ---------- participant info (required before applying) ----------

@router.get("/info")
def info_form(request: Request, user: dict = Depends(require_role("student"))):
    if not site_flag("registration_open"):
        return flash_response("/participant/dashboard", "registration_closed")
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/participant/dashboard", "attendance_locked")
    q = request.query_params
    if q.get("resend"):
        email = (q.get("otp_email") or "").strip().lower()
        payload = latest_otp_payload(email, "institute")
        if payload and payload.get("user_id") == user["id"]:
            send_otp(email, "institute", payload=payload)
            return _render_info_with_otp(request, user, reg, payload.get("values", {}), email, flash="institute_otp_sent")
    values = dict(reg) if reg else {"full_name": user["name"], "email": user["email"]}
    values["phone_country_code"], values["phone_number"] = _split_phone(values.get("phone"))
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
    phone_country_code: str = Form("+91"),
    participation_mode: str = Form("in_person"),
    participant_category: str = Form(""),
    student_level: str = Form(""),
    ug_program: str = Form(""),
    degree_name: str = Form(""),
    department: str = Form(""),
    institute_name: str = Form(""),
    institute_address: str = Form(""),
    institute_country: str = Form(""),
    institute_country_other: str = Form(""),
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
    company_country_other: str = Form(""),
    company_zipcode: str = Form(""),
    # legacy (hidden, for backward compat)
    designation: str = Form(""),
    affiliation: str = Form(""),
):
    if not site_flag("registration_open"):
        return flash_response("/participant/dashboard", "registration_closed")
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/participant/dashboard", "attendance_locked")
    code = (phone_country_code or "").strip() or "+91"
    local = (phone or "").strip()
    phone_full = f"{code} {local}".strip()
    data = {
        "full_name": full_name, "phone": phone_full,
        "phone_country_code": code, "phone_number": local,
        "participation_mode": participation_mode,
        "participant_category": participant_category,
        "student_level": student_level, "ug_program": ug_program,
        "degree_name": degree_name, "department": department,
        "institute_name": institute_name, "institute_address": institute_address,
        "institute_country": institute_country, "institute_zipcode": institute_zipcode,
        "institute_country_other": institute_country_other,
        "institute_email": institute_email, "institute_email_same": institute_email_same,
        "supervisor_name": supervisor_name,
        "academic_role": academic_role, "professor_type": professor_type,
        "company_name": company_name, "position": position,
        "company_email": company_email, "company_email_same": company_email_same,
        "company_address": company_address,
        "company_country": company_country, "company_zipcode": company_zipcode,
        "company_country_other": company_country_other,
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
        return flash_response("/participant/dashboard", "attendance_updated")
    insert("registrations", {
        "user_id": user["id"], **fields,
        "status": "pending", "fee_paid": False, "created_at": now(),
    }, prefix="r")
    return flash_response("/participant/dashboard", "attendance_created")


@router.post("/verifyotp")
def verify_institute_otp(
    request: Request,
    user: dict = Depends(require_role("student")),
    email: str = Form(""),
    purpose: str = Form(""),
    code: str = Form(""),
):
    if not site_flag("registration_open"):
        return flash_response("/participant/dashboard", "registration_closed")
    if purpose != "institute":
        return flash_response("/participant/info", "otp_missing")
    email = (email or "").strip().lower()
    reg = registration_for(user)
    if reg and reg["status"] != "pending":
        return flash_response("/participant/dashboard", "attendance_locked")
    ok, err, payload = verify_otp(email, "institute", code)
    if not ok:
        saved = latest_otp_payload(email, "institute")
        return _render_info_with_otp(request, user, reg, saved.get("values", {}), email,
                                     otp_error=flash_text(err)["error"])
    if not payload or payload.get("user_id") != user["id"]:
        return flash_response("/participant/info", "otp_missing")
    fields = payload.get("values", {})
    fields["verified_institute_email"] = fields.get("institute_email", "")
    if reg:
        update("registrations", reg["id"], fields)
    else:
        insert("registrations", {
            "user_id": user["id"], **fields,
            "status": "pending", "fee_paid": False, "created_at": now(),
        }, prefix="r")
    return flash_response("/participant/dashboard", "institute_verified")


# ---------- paper submission (round 1) ----------

@router.get("/apply")
def apply_form(request: Request, user: dict = Depends(require_role("student")), type: str = ""):
    if not site_flag("paper_submission_open"):
        return flash_response("/participant/dashboard", "paper_closed")
    if not info_complete(user):
        return flash_response("/participant/info", "info_required")
    if type not in PAPER_TYPES:
        return render(request, "student/paper_type.html", user=user)
    return render(request, "student/paper_form.html", mode="create",
                  values=_paper_form_values("", type, "", "", [{}]), user=user)


@router.post("/apply")
async def apply_submit(
    request: Request,
    user: dict = Depends(require_role("student")),
    paper_type: str = Form(""),
    presentation_format: str = Form(""),
    theme: str = Form(""),
    title: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not site_flag("paper_submission_open"):
        return flash_response("/participant/dashboard", "paper_closed")
    if not info_complete(user):
        return flash_response("/participant/info", "info_required")
    form_data = await request.form()
    authors = _authors_from_form(form_data)
    data = _paper_form_values(theme, paper_type, presentation_format, title, authors)
    form, errors = validate(PaperSubmissionForm, data)
    data_bytes = await file.read() if file is not None else b""
    if form and not data_bytes:
        errors = ["Please upload your paper as a PDF file."]
    if errors:
        return render(request, "student/paper_form.html", mode="create", values=data,
                      errors=errors, user=user)
    _, e = submit_paper(user, form.theme, form.paper_type, form.presentation_format,
                        form.title, form.authors,
                        file.filename if file else "submission.pdf", data_bytes)
    if e:
        return flash_response("/participant/apply?type=" + form.paper_type, e)
    return flash_response("/participant/dashboard", "paper_submitted")


@router.get("/edit/{sid}")
def edit_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if not site_flag("paper_submission_open"):
        return flash_response("/participant/dashboard", "paper_closed")
    if sub["status"] != "submitted":
        return flash_response("/participant/dashboard", "submission_locked")
    values = _paper_form_values(sub.get("theme", ""), sub.get("paper_type", ""),
                                sub.get("presentation_format", ""),
                                sub.get("title", ""), sub.get("authors") or [{}])
    return render(request, "student/paper_form.html", mode="edit", sub=paper_view(sub),
                  values=values, user=user)


@router.post("/edit/{sid}")
async def edit_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    paper_type: str = Form(""),
    presentation_format: str = Form(""),
    theme: str = Form(""),
    title: str = Form(""),
    file: UploadFile | None = File(None),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if not site_flag("paper_submission_open"):
        return flash_response("/participant/dashboard", "paper_closed")
    if sub["status"] != "submitted":
        return flash_response("/participant/dashboard", "submission_locked")
    form_data = await request.form()
    authors = _authors_from_form(form_data)
    data = _paper_form_values(theme, paper_type, presentation_format, title, authors)
    form, errors = validate(PaperSubmissionForm, data)
    if errors:
        return render(request, "student/paper_form.html", mode="edit", sub=paper_view(sub),
                      values=data, errors=errors, user=user)
    data_bytes = await file.read() if file is not None and file.filename else None
    _, e = update_paper(user, sid, form.presentation_format, form.title, form.authors,
                        file.filename if (file and data_bytes) else None, data_bytes)
    if e:
        return flash_response(f"/participant/edit/{sid}", e)
    return flash_response("/participant/dashboard", "paper_updated")


@router.get("/submission/{sid}")
def submission_detail(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    return render(request, "student/submission.html", user=user, sub=paper_view(sub),
                  students=students_map())


# ---------- round 2 submission (after feedback) ----------

@router.get("/round2/{sid}")
def round2_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if sub["status"] != "feedback_released":
        return flash_response(f"/participant/submission/{sid}", "round2_not_ready")
    if not site_flag("final_submission_open"):
        return flash_response(f"/participant/submission/{sid}", "round2_closed")
    values = {"authors": sub.get("authors") or [{}]}
    return render(request, "student/round2_form.html", user=user, sub=paper_view(sub),
                  values=values, students=students_map())


@router.post("/round2/{sid}")
async def round2_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    file: UploadFile | None = File(None),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if sub["status"] != "feedback_released":
        return flash_response(f"/participant/submission/{sid}", "round2_not_ready")
    if not site_flag("final_submission_open"):
        return flash_response(f"/participant/submission/{sid}", "round2_closed")
    form_data = await request.form()
    authors = _authors_from_form(form_data)
    form, errors = validate(Round2Form, {"authors": authors})
    if errors:
        return render(request, "student/round2_form.html", user=user, sub=paper_view(sub),
                      values={"authors": authors}, errors=errors, students=students_map())
    data_bytes = await file.read() if file is not None and file.filename else None
    _, e = submit_round2(user, sid, form.authors,
                         file.filename if (file and data_bytes) else None, data_bytes)
    if e:
        return flash_response(f"/participant/round2/{sid}", e)
    return flash_response(f"/participant/submission/{sid}", "round2_submitted")


# ---------- presentation choice (after selection) ----------

@router.get("/submission/{sid}/present")
def present_form(request: Request, sid: str, user: dict = Depends(require_role("student"))):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if sub["status"] != "selected":
        return flash_response(f"/participant/submission/{sid}", "not_selected_yet")
    if not site_flag("results_declared"):
        return flash_response(f"/participant/submission/{sid}", "results_not_declared")
    values = {"presenting": "on" if sub.get("presenting") else ""}
    return render(request, "student/presentation.html", user=user, sub=paper_view(sub),
                  values=values)


@router.post("/submission/{sid}/present")
def present_submit(
    request: Request,
    sid: str,
    user: dict = Depends(require_role("student")),
    presenting: str = Form(""),
):
    sub, redir = _owned_submission(user, sid)
    if redir:
        return redir
    if sub["status"] != "selected":
        return flash_response(f"/participant/submission/{sid}", "not_selected_yet")
    if not site_flag("results_declared"):
        return flash_response(f"/participant/submission/{sid}", "results_not_declared")
    is_presenting = (presenting or "").strip().lower() in ("on", "true", "1", "yes")
    data = {"presenting": presenting}
    form, errors = validate(PresentationChoiceForm, data)
    if errors:
        return render(request, "student/presentation.html", user=user, sub=paper_view(sub),
                      values=data, errors=errors)
    _, e = set_presentation(user, sid, is_presenting)
    if e:
        return flash_response(f"/participant/submission/{sid}/present", e)
    return flash_response(f"/participant/submission/{sid}", "presentation_saved")


# ---------- payment (deferred; amount announced later) ----------

def _payment_gate(user: dict):
    """Shared payment checks. Returns (reg, flash_code | None)."""
    if not has_selected_submission(user):
        return None, "need_selected"
    if not site_flag("results_declared"):
        return None, "results_not_declared"
    if not site_flag("payment_open"):
        return None, "payment_closed"
    reg = registration_for(user)
    if not reg:
        return None, "payment_ready"
    if not payment_eligible(reg):
        return None, "admin_approval_required"
    return reg, None


@router.get("/payment")
def payment_page(request: Request, user: dict = Depends(require_role("student"))):
    reg, err = _payment_gate(user)
    if err:
        return flash_response("/participant/dashboard", err)
    count, unit = payable_amount(user)
    total_value = count * unit["value"] if unit else 0
    return render_msg(request, "student/payment.html", msg=request.query_params.get("msg"),
                      user=user, reg=reg, presenting=presenting_submissions(user),
                      count=count, unit=unit, total_value=total_value)


@router.post("/payment")
def payment_submit(request: Request, user: dict = Depends(require_role("student"))):
    reg, err = _payment_gate(user)
    if err:
        return flash_response("/participant/dashboard", err)
    update("registrations", reg["id"], {"fee_paid": True})
    return flash_response("/participant/payment", "fee_paid_success")
