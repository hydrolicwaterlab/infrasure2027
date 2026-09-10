"""Shared domain logic for panels (incharge / admin / student).

Everything two-or-more routers need lives here so routes stay thin and the
permission rules (theme scoping, self-lockout, round rules) are defined once.

Submission model (phase 2): every presentation is a *single* record in
`submissions.json`. Round 1 is title + abstract only; the theme incharge routes
it to a reviewer (or reviews it themselves) and records Selected for Round 2 /
Not Selected with feedback. If selected, the student picks the format (PPT or
Poster) for Round 2 — recorded on ``format``. Round 2 content is then submitted
(a revised title + abstract for Poster, a PDF upload for PPT); it is editable
until the Round 2 reviewer (or the incharge) starts reviewing. The final
decision is Selected / Not Selected. Payment arrives in a later phase.
The student's ``submission_ids`` back-references the thread.
"""
import os
from datetime import datetime

from app_routes.schemas import MAX_SUBMISSIONS, THEME_LABELS
from auth import hash_password
from db import find, insert, load, one, save, update
from site_config import BASE_DIR, SITE_CONFIG

ROUND1_DECISIONS = ("r1_selected", "r1_not_selected")
ROUND1_OPEN = ("r1_pending", "r1_under_review")
FINAL_DECISIONS = ("selected", "not_selected")
ROUND2_OPEN = ("r2_pending", "r2_under_review")
FORMATS = ("ppt", "poster")

UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")

# Field names per round — lets assign/unassign/takeover work for both rounds.
ROUND_FIELDS = {
    1: {"status": "r1_status", "reviewer": "r1_reviewer_id", "comment": "r1_comment", "reviewed_by": "r1_reviewed_by",
        "reviewed_at": "r1_reviewed_at", "open": "r1_pending", "under": "r1_under_review"},
    2: {"status": "r2_status", "reviewer": "r2_reviewer_id", "comment": "r2_comment", "reviewed_by": "r2_reviewed_by",
        "reviewed_at": "r2_reviewed_at", "open": "r2_pending", "under": "r2_under_review"},
}

# Admin phase-control toggles. `False` = closed / not declared.
SITE_FLAG_KEYS = (
    "registration_open",
    "round1_open",
    "round1_results_declared",
    "round2_open",
    "round2_results_declared",
    "payment_open",
)

SITE_FLAG_DEFAULTS = {k: False for k in SITE_FLAG_KEYS}

SITE_FLAG_LABELS = {
    "registration_open": "Registration",
    "round1_open": "Round 1 entry",
    "round1_results_declared": "Round 1 results",
    "round2_open": "Round 2 entry",
    "round2_results_declared": "Round 2 results",
    "payment_open": "Payment",
}

SITE_FLAG_HINTS = {
    "registration_open": "Students can create accounts and save their participant details.",
    "round1_open": "Students can apply with a title + abstract and edit pending submissions.",
    "round1_results_declared": "Students can see the Round 1 outcome and move into Round 2.",
    "round2_open": "Students can choose a format and submit Round 2 content (poster form / PDF).",
    "round2_results_declared": "Students can see the final decision and become payment-eligible.",
    "payment_open": "Selected participants can mark their registration fee as paid.",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- admin phase controls ----------

def site_state() -> dict:
    """The admin phase-control record — seeded (all closed) on first access."""
    rec = one("site_state", id="phase")
    if not rec:
        rec = {"id": "phase", **SITE_FLAG_DEFAULTS, "updated_by": "", "updated_at": now()}
        insert("site_state", rec, prefix="x")
        return rec
    out = {"id": rec["id"], "updated_by": rec.get("updated_by") or "", "updated_at": rec.get("updated_at") or ""}
    for k in SITE_FLAG_KEYS:
        out[k] = bool(rec.get(k, False))
    return out


def site_flag(name: str) -> bool:
    return bool(site_state().get(name, False))


def set_site_flag(flag: str, actor: dict):
    """Flip one phase toggle. Returns (state, flash_code | None)."""
    if flag not in SITE_FLAG_KEYS:
        return None, "control_not_found"
    state = site_state()
    state[flag] = not state[flag]
    update("site_state", "phase", {flag: state[flag], "updated_by": actor["id"], "updated_at": now()})
    return state, None


# ---------- users ----------

def students_map() -> dict[str, dict]:
    return {u["id"]: u for u in load("users")}


def find_user(uid: str) -> dict | None:
    return one("users", id=uid)


def toggle_user_active(uid: str, actor: dict):
    """Flip active flag. Returns (user, flash_code | None)."""
    user = find_user(uid)
    if not user:
        return None, "user_not_found"
    if user["id"] == actor["id"]:
        return user, "self_lockout"
    update("users", uid, {"active": not user.get("active", True)})
    return user, None


def reset_user_password(uid: str, password: str):
    user = find_user(uid)
    if not user:
        return None, "user_not_found"
    update("users", uid, {"password_hash": hash_password(password)})
    return user, None


def create_incharge(name: str, email: str, password: str, themes: list[str]) -> dict:
    ordered = [t for t in THEME_LABELS if t in themes]
    return insert(
        "users",
        {
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "role": "theme_incharge",
            "themes": ordered,
            "submission_ids": [],
            "active": True,
            "created_at": now(),
        },
        prefix="u",
    )


def set_incharge_themes(uid: str, themes: list[str]):
    ordered = [t for t in THEME_LABELS if t in themes]
    return update("users", uid, {"themes": ordered})


# ---------- reviewers ----------

def reviewers_list() -> list:
    """All reviewer accounts (regardless of who created them)."""
    return [u for u in load("users") if u["role"] == "reviewer"]


def find_reviewer(uid: str) -> dict | None:
    u = find_user(uid)
    if u and u["role"] == "reviewer":
        return u
    return None


def eligible_reviewers(theme: str) -> list:
    """Reviewers who can handle a submission in the given theme (active ones)."""
    return [r for r in reviewers_list() if theme in (r.get("themes") or []) and r.get("active", True)]


def create_reviewer(name: str, email: str, password: str, themes: list[str], created_by: str | None = None) -> dict:
    ordered = [t for t in THEME_LABELS if t in themes]
    return insert(
        "users",
        {
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "role": "reviewer",
            "themes": ordered,
            "submission_ids": [],
            "created_by": created_by or "",
            "active": True,
            "created_at": now(),
        },
        prefix="u",
    )


def set_reviewer_themes(uid: str, themes: list[str]):
    ordered = [t for t in THEME_LABELS if t in themes]
    return update("users", uid, {"themes": ordered})


# ---------- student gates ----------

def has_selected_submission(user: dict) -> bool:
    """True once a presentation has been *finally* selected (Round 2 decision)."""
    return any(s.get("r2_status") == "selected" for s in find("submissions", user_id=user["id"]))


def registration_for(user: dict) -> dict | None:
    """The participant's info record (optional details captured up front)."""
    return one("registrations", user_id=user["id"])


def info_complete(user: dict) -> bool:
    """A student must have saved their details before applying (no admin approval needed).

    For new branching registrations, also ensures required branch fields are present
    so legacy rows (pre-branch) are treated as incomplete and force a re-edit.
    """
    reg = registration_for(user)
    if not reg:
        return False
    # legacy rows without participant_category are incomplete under new schema
    if not reg.get("participant_category"):
        return False
    cat = reg.get("participant_category")
    if cat == "Student":
        if not reg.get("student_level") or not reg.get("degree_name"):
            return False
        if not reg.get("department") or not reg.get("institute_name"):
            return False
        # institute email is optional for UG/PG students
        email_ok = bool(reg.get("institute_email")) or reg.get("student_level") in ("UG", "PG")
        if not reg.get("institute_address") or not reg.get("institute_country") or not reg.get("institute_zipcode") or not email_ok:
            return False
        if reg.get("student_level") == "UG" and not reg.get("ug_program"):
            return False
        if reg.get("student_level") == "PhD" and not reg.get("supervisor_name"):
            return False
    elif cat == "Academic":
        if not reg.get("academic_role") or not reg.get("department"):
            return False
        if not reg.get("institute_name") or not reg.get("institute_address") or not reg.get("institute_country") or not reg.get("institute_zipcode") or not reg.get("institute_email"):
            return False
        if reg.get("academic_role") == "Professor" and not reg.get("professor_type"):
            return False
    elif cat == "Industry":
        if not reg.get("company_name") or not reg.get("position") or not reg.get("company_email"):
            return False
        if not reg.get("company_address") or not reg.get("company_country") or not reg.get("company_zipcode"):
            return False
    else:
        return False
    return True


def payment_eligible(reg: dict | None) -> bool:
    """Payment unlock: a selected thread + an admin-approved registration."""
    return bool(reg) and reg.get("status") == "approved"


def student_threads(user: dict) -> list:
    """A student's presentations — each record is a thread; newest first."""
    subs = find("submissions", user_id=user["id"])
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


def thread_count(user: dict) -> int:
    """Max 2 presentations — tracked on the user's own ``submission_ids``."""
    return len(user.get("submission_ids") or [])


# ---------- submissions / threads ----------

def format_chosen(sub: dict) -> bool:
    """True once the student has picked PPT or Poster for Round 2."""
    return (sub.get("format") or "") in FORMATS


def round1_view(sub: dict) -> dict:
    """A copy of the record as its Round-1 self — title/abstract + chosen format."""
    out = dict(sub)
    out["title_r1"] = sub.get("title_r1") or ""
    out["description_r1"] = sub.get("description_r1") or ""
    out["title"] = out["title_r1"]
    out["description"] = out["description_r1"]
    out["format"] = sub.get("format") or ""
    out["round"] = 1
    return out


def round2_view(sub: dict) -> dict:
    """The record as its Round-2 self — Round-1 details plus revised content / PDF / final status."""
    out = round1_view(sub)
    out["title_r2"] = sub.get("title_r2") or ""
    out["description_r2"] = sub.get("description_r2") or ""
    out["has_pdf"] = bool(sub.get("pdf_name"))
    out["pdf_name"] = sub.get("pdf_name") or ""
    out["pdf_size"] = sub.get("pdf_size") or 0
    out["pdf_uploaded_at"] = sub.get("pdf_uploaded_at") or ""
    out["r2_status"] = sub.get("r2_status") or ""
    out["r2_reviewer_id"] = sub.get("r2_reviewer_id") or ""
    out["r2_comment"] = sub.get("r2_comment") or ""
    out["r2_reviewed_by"] = sub.get("r2_reviewed_by") or ""
    out["r2_reviewed_at"] = sub.get("r2_reviewed_at") or ""
    out["content_received_at"] = sub.get("content_received_at") or ""
    out["title"] = out["title_r2"] or out["title_r1"]
    out["description"] = out["description_r2"] or out["description_r1"]
    out["round"] = 2
    return out


def current_view(sub: dict) -> dict:
    """The record as it stands today — Round 1 until Round 2 content is submitted."""
    if sub.get("r2_status"):
        return round2_view(sub)
    return round1_view(sub)


def content_received(sub: dict) -> bool:
    """True once the student has submitted Round 2 content (poster form or PPT PDF)."""
    return bool(sub.get("r2_status"))


def submission_for(user: dict, sid: str):
    """Return (submission, flash_code | None). Enforces theme scope."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if user["role"] == "theme_incharge" and sub["theme"] not in (user.get("themes") or []):
        return None, "not_your_theme"
    return sub, None


def create_round1(user: dict, theme: str, title: str, description: str) -> dict:
    """Open a new presentation thread — Round 1 is title + abstract only."""
    record = insert(
        "submissions",
        {
            "user_id": user["id"],
            "theme": theme,
            "title_r1": title,
            "description_r1": description,
            "r1_status": "r1_pending",
            "r1_reviewer_id": "",
            "r1_comment": "",
            "r1_reviewed_by": "",
            "r1_reviewed_at": "",
            "format": "",
            "format_chosen_at": "",
            "title_r2": "",
            "description_r2": "",
            "pdf_name": "",
            "pdf_size": 0,
            "pdf_uploaded_at": "",
            "r2_status": "",
            "r2_reviewer_id": "",
            "r2_comment": "",
            "r2_reviewed_by": "",
            "r2_reviewed_at": "",
            "content_received_at": "",
            "created_at": now(),
        },
        prefix="s",
    )
    ids = (user.get("submission_ids") or []) + [record["id"]]
    update("users", user["id"], {"submission_ids": ids})
    return record


def choose_format(user: dict, sid: str, fmt: str):
    """Student picks PPT or Poster for Round 2 — per submission, independently."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, "submission_not_found"
    if sub["r1_status"] != "r1_selected":
        return None, "round2_not_ready"
    if format_chosen(sub):
        return None, "format_already_chosen"
    if fmt not in FORMATS:
        return None, "bad_format"
    update("submissions", sid, {"format": fmt, "format_chosen_at": now()})
    return sub, None


def _r2_submission_gate(user: dict, sid: str):
    """Shared checks before Round-2 content is submitted. Returns (sub, flash_code | None)."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, "submission_not_found"
    if sub["r1_status"] != "r1_selected":
        return None, "round2_not_ready"
    if not format_chosen(sub):
        return None, "round2_not_ready"
    if sub.get("r2_status") in ("r2_under_review", "selected", "not_selected"):
        return None, "content_locked"
    return sub, None


def submit_round2_content(user: dict, sid: str, title: str, description: str):
    """Poster: save the revised Round 2 title + abstract (editable until review starts)."""
    sub, err = _r2_submission_gate(user, sid)
    if err:
        return None, err
    if (sub.get("format") or "") != "poster":
        return None, "bad_format"
    first = not sub.get("r2_status")
    update("submissions", sid, {
        "title_r2": title,
        "description_r2": description,
        "r2_status": "r2_pending",
        "content_received_at": now() if first else sub.get("content_received_at") or now(),
    })
    return sub, None


def upload_round2_pdf(user: dict, sid: str, filename: str, data: bytes):
    """PPT: validate + store the uploaded PDF and mark Round 2 content as pending."""
    sub, err = _r2_submission_gate(user, sid)
    if err:
        return None, err
    if (sub.get("format") or "") != "ppt":
        return None, "bad_format"
    if not data or not data.startswith(b"%PDF"):
        return None, "bad_pdf_type"
    max_bytes = int(SITE_CONFIG.get("max_pdf_mb", 25)) * 1024 * 1024
    if len(data) > max_bytes:
        return None, "pdf_too_large"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, f"{sid}.pdf")
    with open(path, "wb") as f:
        f.write(data)
    first = not sub.get("r2_status")
    update("submissions", sid, {
        "pdf_name": (filename or "submission.pdf").strip()[:255] or "submission.pdf",
        "pdf_size": len(data),
        "pdf_uploaded_at": now(),
        "r2_status": "r2_pending",
        "content_received_at": now() if first else sub.get("content_received_at") or now(),
    })
    return sub, None


def pdf_path(sid: str) -> str:
    return os.path.join(UPLOAD_DIR, f"{sid}.pdf")


def can_view_pdf(user: dict, sub: dict) -> bool:
    """Who may open the Round-2 PDF: the owner, theme-scoped incharge, assigned
    Round-2 reviewer, or a master admin."""
    if user["role"] == "student":
        return sub["user_id"] == user["id"]
    if user["role"] == "theme_incharge":
        return sub["theme"] in (user.get("themes") or [])
    if user["role"] == "reviewer":
        return sub.get("r2_reviewer_id") == user["id"]
    return user["role"] == "master_admin"


def apply_round1_decision(user: dict, sid: str, decision: str, comment: str):
    """Round 1 decision — Selected for Round 2, or Not Selected (dead end).

    The assigned reviewer decides when a submission is under review; the theme
    incharge decides on any open submission in their theme (or takes it over).
    Returns (submission, flash_code | None).
    """
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub["r1_status"] not in ROUND1_OPEN:
        return None, "bad_status"
    if decision not in ROUND1_DECISIONS:
        return None, "bad_decision"
    if user["role"] == "reviewer":
        if sub.get("r1_reviewer_id") != user["id"] or sub["r1_status"] != "r1_under_review":
            return None, "not_your_assignment"
    elif user["role"] == "theme_incharge" and sub["theme"] not in (user.get("themes") or []):
        return None, "not_your_theme"
    update(
        "submissions",
        sid,
        {
            "r1_status": decision,
            "r1_comment": comment.strip()[:1000],
            "r1_reviewed_by": user["id"],
            "r1_reviewed_at": now(),
        },
    )
    return sub, None


def apply_final_decision(user: dict, sid: str, decision: str, comment: str):
    """Final decision — Selected, or Not Selected (dead end).

    The assigned Round-2 reviewer decides when a submission is under review; the
    theme incharge decides on any Round-2-pending submission in their theme (or
    takes it over). Returns (submission, flash_code | None).
    """
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("r2_status") not in ROUND2_OPEN:
        return None, "bad_status"
    if decision not in FINAL_DECISIONS:
        return None, "bad_decision"
    if user["role"] == "reviewer":
        if sub.get("r2_reviewer_id") != user["id"] or sub.get("r2_status") != "r2_under_review":
            return None, "not_your_assignment"
    elif user["role"] == "theme_incharge" and sub["theme"] not in (user.get("themes") or []):
        return None, "not_your_theme"
    update(
        "submissions",
        sid,
        {
            "r2_status": decision,
            "r2_comment": comment.strip()[:1000],
            "r2_reviewed_by": user["id"],
            "r2_reviewed_at": now(),
        },
    )
    return sub, None


def assign_reviewer(user: dict, sid: str, reviewer: dict, round_no: int = 1):
    """Assign an eligible reviewer to an open (pending) submission in the given round."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    f = ROUND_FIELDS[round_no]
    if sub.get(f["status"]) != f["open"]:
        return None, "submission_not_pending"
    if round_no == 2 and not sub.get("r2_status"):
        return None, "need_content"
    if reviewer.get("role") != "reviewer":
        return None, "reviewer_not_found"
    if sub["theme"] not in (reviewer.get("themes") or []):
        return None, "reviewer_theme_mismatch"
    update("submissions", sid, {f["reviewer"]: reviewer["id"], f["status"]: f["under"]})
    return sub, None


def unassign_reviewer(user: dict, sid: str, round_no: int = 1):
    """Remove the assigned reviewer in the given round and re-open it as pending."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    f = ROUND_FIELDS[round_no]
    if sub.get(f["status"]) != f["under"] or not sub.get(f["reviewer"]):
        return None, "no_reviewer_assigned"
    update("submissions", sid, {
        f["reviewer"]: "",
        f["comment"]: "",
        f["reviewed_by"]: "",
        f["reviewed_at"]: "",
        f["status"]: f["open"],
    })
    return sub, None


# ---------- scoping / filters / listing ----------

def scoped_submissions(user: dict) -> list:
    """Incharge: only their assigned themes. Master admin: everything."""
    subs = load("submissions")
    if user["role"] == "theme_incharge":
        allowed = set(user.get("themes") or [])
        subs = [s for s in subs if s["theme"] in allowed]
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


def filter_submissions(subs: list, theme: str = "", status: str = "", stype: str = "", round_no: int = 1) -> list:
    if theme:
        subs = [s for s in subs if s["theme"] == theme]
    if stype:
        subs = [s for s in subs if (s.get("format") or "") == stype]
    if status:
        key = "r2_status" if round_no == 2 else "r1_status"
        subs = [s for s in subs if (s.get(key) or "") == status]
    return subs


def decorated_subs(subs: list, students: dict, action_fn, round_no: int = 1) -> list:
    """Decorate each submission with current view fields, `_student`, `_reviewer`, `_round`, `_actions`."""
    out = []
    for s in subs:
        row = current_view(s)
        row["_student"] = (students.get(s["user_id"]) or {}).get("name", "—")
        reviewer_key = "r2_reviewer_id" if round_no == 2 else "r1_reviewer_id"
        rev = students.get(s.get(reviewer_key)) or {}
        row["_reviewer"] = rev.get("name", "") or ""
        row["_actions"] = action_fn(s)
        out.append(row)
    return out


def submission_actions(user: dict, s: dict, round_no: int = 1) -> list:
    """Role-aware row actions for the incharge/admin submission tables."""
    actions = []
    if round_no == 1:
        if s["r1_status"] == "r1_pending":
            actions.append({"url": f"/incharge/assign/{s['id']}", "label": "Assign reviewer", "cls": "btn-primary"})
            actions.append({"url": f"/incharge/review/{s['id']}", "label": "Review myself", "cls": "btn-outline"})
        elif s["r1_status"] == "r1_under_review":
            actions.append({"url": f"/incharge/change_reviewer/{s['id']}", "label": "Change reviewer", "cls": "btn-outline"})
    elif s.get("r2_status") == "r2_pending":
        actions.append({"url": f"/incharge/assign/{s['id']}/round2", "label": "Assign Round 2 reviewer", "cls": "btn-primary"})
        actions.append({"url": f"/incharge/review/{s['id']}/round2", "label": "Review myself", "cls": "btn-outline"})
    elif s.get("r2_status") == "r2_under_review":
        actions.append({"url": f"/incharge/change_reviewer/{s['id']}/round2", "label": "Change reviewer", "cls": "btn-outline"})
    return actions


def detail_actions(user: dict, s: dict, round_no: int = 1) -> list:
    """Buttons for a submission detail page (side panel)."""
    actions = submission_actions(user, s, round_no)
    if round_no == 1:
        if s["r1_status"] == "r1_under_review" and s.get("r1_reviewer_id"):
            actions.append({"url": f"/incharge/takeover/{s['id']}", "label": "Take over & review myself", "cls": "btn-accent"})
    elif s.get("r2_status") == "r2_under_review" and s.get("r2_reviewer_id"):
        actions.append({"url": f"/incharge/takeover/{s['id']}/round2", "label": "Take over & review myself", "cls": "btn-accent"})
    return actions


# ---------- reviewer scope ----------

def reviewer_submissions(reviewer: dict) -> list:
    """Round-1 submissions assigned to this reviewer."""
    subs = [s for s in load("submissions") if s.get("r1_reviewer_id") == reviewer["id"]]
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


def reviewer_round2_submissions(reviewer: dict) -> list:
    """Round-2 submissions assigned to this reviewer."""
    subs = [s for s in load("submissions") if s.get("r2_reviewer_id") == reviewer["id"]]
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


# ---------- attendance registrations ----------

def find_registration(rid: str) -> dict | None:
    return one("registrations", id=rid)


def apply_registration_action(rid: str, action: str):
    """Apply an admin action to a registration. Returns (reg, flash_code | None)."""
    reg = find_registration(rid)
    if not reg:
        return None, "registration_not_found"
    if action == "approve":
        update("registrations", rid, {"status": "approved"})
    elif action == "reject":
        update("registrations", rid, {"status": "rejected"})
    elif action == "fee":
        update("registrations", rid, {"fee_paid": not reg.get("fee_paid")})
    else:
        return reg, "registration_not_found"
    return reg, None


# ---------- announcements ----------

DEFAULT_ANNOUNCEMENT_CATEGORIES = ("General", "Registration", "Submissions", "Selection", "Payment")


def ensure_default_categories():
    """Seed default FAQ categories when the collection is missing/empty."""
    cats = load("faq_categories")
    if cats:
        return
    for i, name in enumerate(DEFAULT_ANNOUNCEMENT_CATEGORIES, start=1):
        insert("faq_categories", {"name": name, "order": i}, prefix="c")


def announcements_list() -> list:
    """All announcements, newest first."""
    return sorted(load("announcements"), key=lambda a: a.get("created_at", ""), reverse=True)


def create_announcement(title: str, body: str, created_by: str) -> dict:
    return insert(
        "announcements",
        {
            "title": title,
            "body": body,
            "show_on_home": True,
            "created_by": created_by or "",
            "created_at": now(),
        },
        prefix="a",
    )


def update_announcement(aid: str, title: str, body: str):
    a = one("announcements", id=aid)
    if not a:
        return None, "announcement_not_found"
    update("announcements", aid, {"title": title, "body": body})
    return a, None


def toggle_announcement(aid: str):
    a = one("announcements", id=aid)
    if not a:
        return None, "announcement_not_found"
    update("announcements", aid, {"show_on_home": not a.get("show_on_home", False)})
    return a, None


def delete_announcement(aid: str):
    a = one("announcements", id=aid)
    if not a:
        return None, "announcement_not_found"
    records = [x for x in load("announcements") if x["id"] != aid]
    save("announcements", records)
    return a, None


# ---------- faqs ----------

def faq_categories() -> list:
    cats = load("faq_categories")
    return sorted(cats, key=lambda c: c.get("order", 0))


def faqs_list() -> list:
    return sorted(load("faqs"), key=lambda f: (f.get("order", 0), f.get("created_at", "")))


def faqs_by_category(category_id: str) -> list:
    return [f for f in faqs_list() if f.get("category_id") == category_id]


def faq_groups() -> list:
    """Categories each with their FAQs, ready for the public page."""
    out = []
    for c in faq_categories():
        out.append({"category": c, "faqs": faqs_by_category(c["id"])})
    return out


def create_category(name: str) -> dict:
    cats = faq_categories()
    nxt = (max((c.get("order", 0) for c in cats), default=0)) + 1
    return insert("faq_categories", {"name": name, "order": nxt}, prefix="c")


def rename_category(cid: str, name: str):
    c = one("faq_categories", id=cid)
    if not c:
        return None, "faq_cat_not_found"
    update("faq_categories", cid, {"name": name})
    return c, None


def delete_category(cid: str):
    c = one("faq_categories", id=cid)
    if not c:
        return None, "faq_cat_not_found"
    if faqs_by_category(cid):
        return c, "faq_cat_in_use"
    records = [x for x in load("faq_categories") if x["id"] != cid]
    save("faq_categories", records)
    return c, None


def create_faq(category_id: str, question: str, answer: str, order: int) -> dict:
    return insert(
        "faqs",
        {
            "category_id": category_id,
            "question": question,
            "answer": answer,
            "order": int(order or 0),
            "created_at": now(),
        },
        prefix="f",
    )


def update_faq(fid: str, category_id: str, question: str, answer: str, order: int):
    f = one("faqs", id=fid)
    if not f:
        return None, "faq_not_found"
    update("faqs", fid, {
        "category_id": category_id,
        "question": question,
        "answer": answer,
        "order": int(order or 0),
    })
    return f, None


def delete_faq(fid: str):
    f = one("faqs", id=fid)
    if not f:
        return None, "faq_not_found"
    records = [x for x in load("faqs") if x["id"] != fid]
    save("faqs", records)
    return f, None