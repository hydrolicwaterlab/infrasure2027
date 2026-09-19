"""Shared route helpers: template context, flash codes, redirects."""
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse

from auth import user_from_request
from site_config import SITE_CONFIG, templates

FLASH = {
    # auth
    "registered": ("success", "Account created — please log in."),
    "otp_sent": ("success", "A one-time code has been sent to your email."),
    "otp_verified": ("success", "Email verified."),
    "otp_incorrect": ("error", "That code is incorrect — please try again."),
    "otp_expired": ("error", "That code has expired. Please request a new one."),
    "otp_missing": ("error", "No verification in progress — please start again."),
    "email_not_found": ("error", "No account found for that email."),
    "forgot_check_email": ("success", "If an account exists for that email, a verification code has been sent."),
    "password_reset": ("success", "Password reset — please log in with your new password."),
    "password_mismatch": ("error", "Passwords do not match."),
    "institute_verified": ("success", "Institute email verified — your details were saved."),
    "institute_otp_sent": ("success", "A verification code was sent to your institute email."),
    "login_required": ("error", "Please log in to access that page."),
    "bad_creds": ("error", "Incorrect email or password."),
    "inactive": ("error", "This account has been deactivated. Contact the organizers."),
    "loggedout": ("success", "You have been logged out."),
    "wrong_role": ("error", "Your account does not have access to that area."),
    "incharge_only": ("error", "This page is for theme incharge accounts."),
    "admin_only": ("error", "This page is for site administrators."),
    # papers
    "paper_submitted": ("success", "Paper received — it is now pending review."),
    "paper_updated": ("success", "Your paper was updated."),
    "paper_closed": ("error", "Paper submission is currently closed."),
    "submission_locked": ("error", "This paper has already been reviewed — it can no longer be edited."),
    "submission_not_found": ("error", "Submission not found."),
    "info_required": ("error", "Please complete your details before submitting a paper."),
    "bad_pdf_type": ("error", "Please upload a valid PDF file."),
    "pdf_too_large": ("error", "That file is too large — please keep it under the size limit."),
    # revision / final submission
    "round2_submitted": ("success", "Final submission received — the final decision will follow."),
    "round2_not_ready": ("error", "The final submission opens only after review feedback is released."),
    "round2_closed": ("error", "The final submission window is closed."),
    # feedback / final decision
    "feedback_saved": ("success", "Feedback saved — the paper advances to the next stage."),
    "feedback_sent": ("success", "Feedback sent to the student."),
    "final_decision_saved": ("success", "Final decision saved — the student can see the outcome once results are declared."),
    "bad_decision": ("error", "Please choose Selected or Not Selected."),
    "bad_status": ("error", "That action isn't valid in the paper's current state."),
    "not_your_theme": ("error", "You can only review submissions in your assigned themes."),
    # presentation choice
    "presentation_saved": ("success", "Your presentation choice was saved."),
    "presentation_closed": ("error", "Presentation choice is currently closed."),
    "not_selected_yet": ("error", "This paper has not been selected."),
    "results_not_declared": ("error", "Results are not announced yet."),
    "presentation_format_saved": ("success", "Presentation format updated."),
    "bad_format": ("error", "Please choose Presentation or Poster."),
    # admin phase controls
    "registration_closed": ("error", "Registration is currently closed — please try again later."),
    "control_not_found": ("error", "That control does not exist."),
    "control_toggled": ("success", "Phase control updated."),
    # reviewer workflow
    "assigned_reviewer": ("success", "Reviewer assigned — they can now review the paper."),
    "reviewer_exists_assigned": ("success", "That reviewer already has an account — assigned them instead."),
    "reviewer_created_assigned": ("success", "New reviewer created and assigned — login credentials emailed."),
    "reviewer_theme_mismatch": ("error", "That reviewer is not assigned to this submission's theme."),
    "reviewer_not_found": ("error", "Reviewer not found."),
    "submission_not_pending": ("error", "Only unreviewed papers can be assigned."),
    "reviewer_email_taken": ("error", "That email belongs to a student/incharge/admin account — use a reviewer account or a different email."),
    "not_your_assignment": ("error", "This submission is not assigned to you."),
    "review_submitted": ("success", "Your decision was saved — the student can see the outcome."),
    "reviewer_created": ("success", "Reviewer account created — login credentials emailed."),
    "reviewer_themes_updated": ("success", "Assigned themes updated."),
    "reviewer_removed": ("success", "Reviewer removed — give feedback yourself or assign a new reviewer."),
    "no_reviewer_assigned": ("error", "No reviewer is assigned to this submission yet."),
    "need_reviewers": ("error", "No reviewers are available for this theme yet — add one below."),
    # payment
    "need_selected": ("error", "Payment opens once a presentation is selected AND your registration is approved."),
    "registration_ready": ("success", "Your presentation was selected — the conference team will approve your details, then payment opens."),
    "payment_ready": ("success", "Your details are approved — you can proceed to payment."),
    "admin_approval_required": ("error", "Payment opens once the conference team approves your registration."),
    "payment_closed": ("error", "Payment is currently closed."),
    "fee_paid_success": ("success", "Payment recorded — see you at INFRASURE 2027!"),
    # attendance registration / participant info
    "attendance_created": ("success", "Your details were saved. You can now submit a paper."),
    "attendance_updated": ("success", "Your details were updated."),
    "attendance_locked": ("error", "Your details have been processed — contact the organizers for changes."),
    # admin — users, incharges, registrations
    "user_toggled": ("success", "Account status updated."),
    "self_lockout": ("error", "You can't deactivate your own account."),
    "user_not_found": ("error", "Account not found."),
    "password_reset": ("success", "Password updated."),
    "user_deleted": ("success", "Account and all associated submissions, registration and files deleted."),
    "cannot_delete_self": ("error", "You can't delete your own account."),
    "last_admin": ("error", "Cannot delete the last master admin account."),
    "incharge_created": ("success", "Theme incharge account created — login credentials emailed."),
    "incharge_themes_updated": ("success", "Assigned themes updated."),
    "incharge_themes_required": ("error", "Assign at least one theme."),
    "registration_not_found": ("error", "Registration not found."),
    "reg_updated": ("success", "Registration updated."),
    # announcements
    "announcement_created": ("success", "Announcement published."),
    "announcement_updated": ("success", "Announcement updated."),
    "announcement_deleted": ("success", "Announcement deleted."),
    "announcement_toggled": ("success", "Homepage visibility updated."),
    "announcement_not_found": ("error", "Announcement not found."),
    # FAQs
    "faq_created": ("success", "FAQ added."),
    "faq_updated": ("success", "FAQ updated."),
    "faq_deleted": ("success", "FAQ deleted."),
    "faq_not_found": ("error", "FAQ not found."),
    "faq_cat_created": ("success", "FAQ category added."),
    "faq_cat_renamed": ("success", "FAQ category renamed."),
    "faq_cat_deleted": ("success", "FAQ category deleted."),
    "faq_cat_not_found": ("error", "FAQ category not found."),
    "faq_cat_in_use": ("error", "Move or delete this category's FAQs before removing it."),
}

TYPE_LABELS = {"ppt": "Presentation", "poster": "Poster", "full_paper": "Full Paper", "extended_abstract": "Extended Abstract"}
MODE_LABELS = {"in_person": "In person"}
STATUS_LABELS = {
    "submitted": "Submitted for review",
    "under_review": "Under review",
    "feedback_released": "Feedback released",
    "round2_submitted": "Final submission received",
    "selected": "Selected",
    "not_selected": "Not selected",
    "approved": "Approved",
    "rejected": "Rejected",
    # masked results (shown to students until the admin declares them)
    "awaiting": "Result to be announced",
}


def base_ctx(request: Request, **extra) -> dict:
    """Template context with config, current user, and any flash/extra vars."""
    from app_routes.service import site_state
    return {"request": request, "config": SITE_CONFIG, "site_state": site_state(),
            "current_user": user_from_request(request), **extra}


def render(request, template: str, **extra):
    return templates.TemplateResponse(request, template, base_ctx(request, **extra))


def page_ctx(request: Request, msg: str | None = None, **extra) -> dict:
    """Template context with config, current user, optional flash, and extras."""
    return {**base_ctx(request), **flash_text(msg), **extra}


def render_msg(request, template: str, msg: str | None = None, **extra):
    """Render a template carrying a ?msg= flash, plus page extras."""
    return templates.TemplateResponse(request, template, page_ctx(request, msg, **extra))


def flash_response(url: str, code: str, **params) -> RedirectResponse:
    qs = {"msg": code, **params}
    return RedirectResponse(f"{url}{'&' if '?' in url else '?'}{urlencode(qs)}", status_code=303)


def flash_text(msg: str | None) -> dict:
    """Turn a ?msg= code into the `success` / `error` vars base.html expects."""
    entry = FLASH.get(msg or "")
    if not entry:
        return {}
    kind, text = entry
    return {kind: text}
