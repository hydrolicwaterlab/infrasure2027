"""Shared domain logic for panels (incharge / admin / student).

Everything two-or-more routers need lives here so routes stay thin and the
permission rules (theme scoping, self-lockout, round rules) are defined once.

Submission model: every presentation is a *single* record in `submissions.json`
that holds both rounds side by side — Round 1 (``title_r1`` + ``description_r1``)
and Round 2 (``title_r2`` + ``description_r2``, once submitted). Theme and
submission format are fixed at Round 1. The record's status walks the whole
lifecycle, and the student's ``submission_ids`` back-references the thread.
"""
from datetime import datetime

from app_routes.schemas import MAX_SUBMISSIONS, THEME_LABELS
from auth import hash_password
from db import find, insert, load, one, save, update

REVIEW_DECISIONS = ("selected", "not_selected")
REVIEWED = frozenset(REVIEW_DECISIONS)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
    return any(s["status"] == "selected" for s in find("submissions", user_id=user["id"]))


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

def has_round2(sub: dict) -> bool:
    """Round 2 exists once any of its fields / timestamp is filled in."""
    return bool((sub.get("title_r2") or "").strip()
                or (sub.get("description_r2") or "").strip()
                or sub.get("round2_submitted_at"))


def sub_round(sub: dict) -> int:
    return 2 if has_round2(sub) else 1


def current_title(sub: dict) -> str:
    return (sub.get("title_r2") or "").strip() or (sub.get("title_r1") or "").strip()


def current_description(sub: dict) -> str:
    return (sub.get("description_r2") or "").strip() or (sub.get("description_r1") or "").strip()


def round1_view(sub: dict) -> dict:
    """A copy of the record as its Round-1 self — what students/panels saw first."""
    out = dict(sub)
    out["title"] = sub.get("title_r1") or ""
    out["description"] = sub.get("description_r1") or ""
    out["round"] = 1
    return out


def round2_view(sub: dict) -> dict | None:
    """A Round-2 view of the record (current title/abstract + decision), or None."""
    if not has_round2(sub):
        return None
    return {
        "id": sub["id"],
        "submission_type": sub.get("submission_type") or "",
        "theme": sub.get("theme") or "",
        "title": sub.get("title_r2") or "",
        "description": sub.get("description_r2") or "",
        "status": sub["status"],
        "review_comment": sub.get("review_comment") or "",
        "reviewed_by": sub.get("reviewed_by") or "",
        "reviewed_at": sub.get("reviewed_at") or "",
        "created_at": sub.get("round2_submitted_at") or "",
        "round": 2,
    }


def current_view(sub: dict) -> dict:
    """The record as it stands today — current title/abstract/round for listings."""
    out = dict(sub)
    out["title"] = current_title(sub)
    out["description"] = current_description(sub)
    out["round"] = sub_round(sub)
    return out


def round2_of(sub: dict) -> dict | None:
    return round2_view(sub)


def thread_submissions(sub: dict) -> list:
    """Both round views of a thread, round-ordered (may be just Round 1)."""
    views = [round1_view(sub)]
    r2 = round2_view(sub)
    if r2:
        views.append(r2)
    return views


def submission_for(user: dict, sid: str):
    """Return (submission, flash_code | None). Enforces theme scope."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if user["role"] == "theme_incharge" and sub["theme"] not in (user.get("themes") or []):
        return None, "not_your_theme"
    return sub, None


def create_round1(user: dict, submission_type: str, theme: str, title: str, description: str) -> dict:
    """Open a new presentation thread. Round 1 fields set now; Round 2 stays empty."""
    record = insert(
        "submissions",
        {
            "user_id": user["id"],
            "submission_type": submission_type,
            "theme": theme,
            "title_r1": title,
            "description_r1": description,
            "title_r2": "",
            "description_r2": "",
            "round2_submitted_at": "",
            "status": "pending",
            "assigned_reviewer_id": "",
            "reviewer_comment": "",
            "reviewer_reviewed_at": "",
            "reviewed_by": "",
            "review_comment": "",
            "reviewed_at": "",
            "created_at": now(),
        },
        prefix="s",
    )
    ids = (user.get("submission_ids") or []) + [record["id"]]
    update("users", user["id"], {"submission_ids": ids})
    return record


def submit_round2(user: dict, sid: str, title: str, description: str):
    """Record the Round-2 revision on the same thread after Round-1 feedback.

    Returns (submission, flash_code | None).
    """
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, "submission_not_found"
    if sub["status"] != "feedback_given":
        return None, "round2_not_ready"
    if has_round2(sub):
        return None, "round2_already_exists"
    update(
        "submissions",
        sid,
        {
            "title_r2": title,
            "description_r2": description,
            "round2_submitted_at": now(),
            "status": "awaiting_decision",
        },
    )
    return sub, None


def apply_round1_feedback(user: dict, sid: str, comment: str):
    """Round 1 feedback from a reviewer or an incharge — questions / changes only.

    Reviewer must be assigned (under_review); incharge needs theme scope and can
    also feed back on a `pending` submission if they take it over themselves.
    Returns (submission, flash_code | None).
    """
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if has_round2(sub):
        return None, "bad_status"
    if sub["status"] not in ("pending", "under_review"):
        return None, "bad_status"
    if user["role"] == "reviewer":
        if sub.get("assigned_reviewer_id") != user["id"] or sub["status"] != "under_review":
            return None, "not_your_assignment"
    elif user["role"] == "theme_incharge" and sub["theme"] not in (user.get("themes") or []):
        return None, "not_your_theme"
    update(
        "submissions",
        sid,
        {
            "reviewer_comment": comment.strip()[:1000],
            "reviewer_reviewed_at": now(),
            "status": "feedback_given",
        },
    )
    return sub, None


def assign_reviewer(user: dict, sid: str, reviewer: dict):
    """Assign an eligible reviewer to a pending Round-1 submission."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    if has_round2(sub):
        return None, "bad_status"
    if sub["status"] != "pending":
        return None, "submission_not_pending"
    if reviewer.get("role") != "reviewer":
        return None, "reviewer_not_found"
    if sub["theme"] not in (reviewer.get("themes") or []):
        return None, "reviewer_theme_mismatch"
    update("submissions", sid, {"assigned_reviewer_id": reviewer["id"], "status": "under_review"})
    return sub, None


def unassign_reviewer(user: dict, sid: str):
    """Remove the assigned reviewer from a Round-1 submission and re-open it as pending."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    if has_round2(sub) or not sub.get("assigned_reviewer_id"):
        return None, "no_reviewer_assigned"
    update("submissions", sid, {
        "assigned_reviewer_id": "",
        "reviewer_comment": "",
        "reviewer_reviewed_at": "",
        "status": "pending",
    })
    return sub, None


def apply_final_decision(user: dict, sid: str, decision: str, comment: str):
    """Theme incharge (or admin override) decides Selected / Not Selected once Round 2 is in."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    if not has_round2(sub):
        return None, "bad_status"
    if sub["status"] != "awaiting_decision":
        return None, "bad_status"
    if decision not in REVIEW_DECISIONS:
        return None, "bad_decision"
    update(
        "submissions",
        sid,
        {
            "status": decision,
            "reviewed_by": user["id"],
            "review_comment": comment.strip()[:1000],
            "reviewed_at": now(),
        },
    )
    return sub, None


# ---------- scoping / filters / listing ----------

def scoped_submissions(user: dict) -> list:
    """Incharge: only their assigned themes. Master admin: everything."""
    subs = load("submissions")
    if user["role"] == "theme_incharge":
        allowed = set(user.get("themes") or [])
        subs = [s for s in subs if s["theme"] in allowed]
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


def filter_submissions(subs: list, theme: str = "", status: str = "", stype: str = "", round_no: str = "") -> list:
    if theme:
        subs = [s for s in subs if s["theme"] == theme]
    if stype:
        subs = [s for s in subs if s["submission_type"] == stype]
    if round_no == "1":
        subs = [s for s in subs if not has_round2(s)]
    elif round_no == "2":
        subs = [s for s in subs if has_round2(s)]
    if status == "pending":
        subs = [s for s in subs if s["status"] == "pending"]
    elif status == "reviewed":
        subs = [s for s in subs if s["status"] in REVIEWED]
    elif status:
        subs = [s for s in subs if s["status"] == status]
    return subs


def decorated_subs(subs: list, students: dict, action_fn) -> list:
    """Decorate each submission with current view fields, `_student`, `_reviewer`, `_round`, `_actions`."""
    out = []
    for s in subs:
        row = current_view(s)
        row["_student"] = (students.get(s["user_id"]) or {}).get("name", "—")
        rev = students.get(s.get("assigned_reviewer_id")) or {}
        row["_reviewer"] = rev.get("name", "") or ""
        row["_actions"] = action_fn(s)
        out.append(row)
    return out


def submission_actions(user: dict, s: dict) -> list:
    """Role-aware row actions for the incharge/admin submission tables."""
    actions = []
    if not has_round2(s):
        if s["status"] == "pending":
            actions.append({"url": f"/incharge/assign/{s['id']}", "label": "Assign reviewer", "cls": "btn-primary"})
            actions.append({"url": f"/incharge/review/{s['id']}", "label": "Review myself", "cls": "btn-outline"})
        elif s["status"] == "under_review":
            actions.append({"url": f"/incharge/change_reviewer/{s['id']}", "label": "Change reviewer", "cls": "btn-outline"})
    elif s["status"] == "awaiting_decision":
        actions.append({"url": f"/incharge/review/{s['id']}", "label": "Make decision", "cls": "btn-primary"})
    elif s["status"] in REVIEWED:
        actions.append({"url": f"/incharge/review/{s['id']}", "label": "Change decision", "cls": "btn-outline"})
    return actions


def detail_actions(user: dict, s: dict) -> list:
    """Buttons for a submission detail page (side panel)."""
    actions = submission_actions(user, s)
    if not has_round2(s):
        if s["status"] == "pending":
            actions.append({"url": f"/incharge/review/{s['id']}", "label": "Review myself", "cls": "btn-outline"})
        elif s["status"] in ("under_review",) and s.get("assigned_reviewer_id"):
            actions.append({"url": f"/incharge/takeover/{s['id']}", "label": "Take over & review myself", "cls": "btn-accent"})
    return actions


# ---------- reviewer scope ----------

def reviewer_submissions(reviewer: dict) -> list:
    """Submissions assigned to this reviewer (Round 1 — before Round 2 exists)."""
    subs = [s for s in load("submissions")
            if s.get("assigned_reviewer_id") == reviewer["id"] and not has_round2(s)]
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