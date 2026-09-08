"""Shared route helpers: template context, flash codes, redirects."""
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse

from auth import user_from_request
from site_config import SITE_CONFIG, templates

FLASH = {
    # auth
    "registered": ("success", "Account created — please log in."),
    "login_required": ("error", "Please log in to access that page."),
    "bad_creds": ("error", "Incorrect email or password."),
    "inactive": ("error", "This account has been deactivated. Contact the organizers."),
    "loggedout": ("success", "You have been logged out."),
    "wrong_role": ("error", "Your account does not have access to that area."),
    "incharge_only": ("error", "This page is for theme incharge accounts."),
    "admin_only": ("error", "This page is for site administrators."),
    # submissions
    "submission_created": ("success", "Round 1 received — it is now pending review."),
    "submission_updated": ("success", "Your submission was updated."),
    "submissions_full": ("error", "You have reached the limit of 2 presentations."),
    "submission_locked": ("error", "This submission has already received feedback — submit Round 2 to make changes."),
    "submission_not_found": ("error", "Submission not found."),
    "round2_submitted": ("success", "Round 2 submitted — it is with the theme incharge for the final decision."),
    "round2_already_exists": ("error", "Round 2 already exists for this presentation."),
    "round2_not_ready": ("error", "Round 2 opens once the reviewer has sent feedback on Round 1."),
    "info_required": ("error", "Please complete your details before applying to present."),
    # review (feedback + final decision)
    "review_saved": ("success", "Decision saved — the student can now see the final outcome."),
    "feedback_sent": ("success", "Feedback sent — the student can now submit Round 2."),
    "not_your_theme": ("error", "You can only review submissions in your assigned themes."),
    "bad_decision": ("error", "Please choose Selected or Not Selected."),
    # reviewer workflow
    "assigned_reviewer": ("success", "Reviewer assigned — they can now review Round 1."),
    "reviewer_exists_assigned": ("success", "That reviewer already has an account — assigned them instead."),
    "reviewer_created_assigned": ("success", "New reviewer created and assigned."),
    "reviewer_theme_mismatch": ("error", "That reviewer is not assigned to this submission's theme."),
    "reviewer_not_found": ("error", "Reviewer not found."),
    "submission_not_pending": ("error", "Only pending submissions can be assigned."),
    "reviewer_email_taken": ("error", "That email belongs to a student/incharge/admin account — use a reviewer account or a different email."),
    "not_your_assignment": ("error", "This submission is not assigned to you."),
    "bad_status": ("error", "That action isn't valid in the submission's current state."),
    "review_submitted": ("success", "Your feedback was sent — the student can now submit Round 2."),
    "reviewer_created": ("success", "Reviewer account created."),
    "reviewer_themes_updated": ("success", "Assigned themes updated."),
    "reviewer_removed": ("success", "Reviewer removed — review Round 1 yourself or assign a new reviewer."),
    "no_reviewer_assigned": ("error", "No reviewer is assigned to this submission yet."),
    "need_reviewers": ("error", "No reviewers are available for this theme yet — add one below."),
    "need_selected": ("error", "Payment opens once a presentation is selected AND your registration is approved."),
    "registration_ready": ("success", "Your presentation was selected — the conference team will approve your details, then payment opens."),
    "payment_ready": ("success", "Your details are approved — you can proceed to payment."),
    "admin_approval_required": ("error", "Payment opens once the conference team approves your registration."),
    "fee_paid_success": ("success", "Payment recorded — see you at INFRASURE 2027!"),
    # attendance registration / participant info
    "attendance_created": ("success", "Your details were saved. You can now apply to present."),
    "attendance_updated": ("success", "Your details were updated."),
    "attendance_locked": ("error", "Your details have been processed — contact the organizers for changes."),
    # admin — users, incharges, registrations
    "user_toggled": ("success", "Account status updated."),
    "self_lockout": ("error", "You can't deactivate your own account."),
    "user_not_found": ("error", "Account not found."),
    "password_reset": ("success", "Password updated."),
    "incharge_created": ("success", "Theme incharge account created."),
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

TYPE_LABELS = {"ppt": "PPT", "poster": "Poster"}
MODE_LABELS = {"in_person": "In person", "online": "Online"}
STATUS_LABELS = {
    "pending": "Pending review",
    "under_review": "Under review",
    "feedback_given": "Feedback sent",
    "superseded": "Round 1 complete",
    "awaiting_decision": "Awaiting decision",
    "selected": "Selected",
    "not_selected": "Not selected",
    "approved": "Approved",
    "rejected": "Rejected",
    # legacy statuses (kept for safety on old records)
    "reviewer_done": "Reviewer feedback ready",
    "revision_requested": "Revision requested",
    "revised": "Revised",
}


def base_ctx(request: Request, **extra) -> dict:
    """Template context with config, current user, and any flash/extra vars."""
    return {"request": request, "config": SITE_CONFIG,
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
