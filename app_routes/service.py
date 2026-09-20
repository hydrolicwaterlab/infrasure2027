"""Shared domain logic for panels (incharge / admin / student).

Everything two-or-more routers need lives here so routes stay thin and the
permission rules (theme scoping, self-lockout, round rules) are defined once.

Submission model: every paper is a *single* record in `submissions.json`.

Paper Round (round 1): the student picks Full Paper or Extended Abstract, then
uploads a PDF with a title and author list. A theme incharge or an assigned
reviewer reads it and writes **feedback only** — everyone advances; there is no
"not selected" at this stage. The admin then releases feedback and opens the
revision window, during which the student may optionally upload a new PDF and/or
edit the authors (title and type stay fixed). Once the revision window closes,
the reviewer records the **final decision** (Selected / Not Selected).

The presentation format (Presentation or Poster) is chosen when the paper is
first submitted. If selected, the student then ticks whether they will present
it. Payment arrives in a later phase; the payable amount is the number of ticked
presentations times the per-presentation fee.

The student's ``submission_ids`` back-references the thread.
"""
import logging
import os
from datetime import date, datetime

from app_routes.schemas import FORMATS, THEME_LABELS
from auth import hash_password
from db import find, insert, load, one, save, update
from site_config import BASE_DIR, INR_COUNTRIES, SITE_CONFIG

logger = logging.getLogger("service")

PAPER_TYPES = ("full_paper", "extended_abstract")
FINAL_DECISIONS = ("selected", "not_selected")

UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")

# Statuses a paper can be in.
STATUS_SUBMITTED = "submitted"
STATUS_UNDER_REVIEW = "under_review"
STATUS_FEEDBACK_RELEASED = "feedback_released"
STATUS_ROUND2_SUBMITTED = "round2_submitted"
STATUS_SELECTED = "selected"
STATUS_NOT_SELECTED = "not_selected"

# Admin phase-control toggles. `False` = closed / not declared.
# Final submission is the only phase open by default; the admin only needs to
# stop it. Presentation choice follows results automatically, so it has no flag.
SITE_FLAG_KEYS = (
    "registration_open",
    "paper_submission_open",
    "final_submission_open",
    "results_declared",
    "payment_open",
)

SITE_FLAG_DEFAULTS = {
    "registration_open": False,
    "paper_submission_open": False,
    "final_submission_open": True,
    "results_declared": False,
    "payment_open": False,
}

SITE_FLAG_LABELS = {
    "registration_open": "Registration",
    "paper_submission_open": "Submit for Review (first draft)",
    "final_submission_open": "Final Submission",
    "results_declared": "Declare results",
    "payment_open": "Payment",
}

SITE_FLAG_HINTS = {
    "registration_open": "Students can create accounts and save their participant details.",
    "paper_submission_open": "Students can submit new papers (Full Paper / Extended Abstract) and edit them before review.",
    "final_submission_open": "Open by default. While open, students may upload their revised PDF / edit authors and click Submit for Final Review. Stop it to lock the window; only final submissions can receive a decision.",
    "results_declared": "Students can see the final Selected / Not Selected outcome and tick which papers they will present.",
    "payment_open": "Selected participants can mark their registration fee as paid.",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- admin phase controls ----------

def site_state() -> dict:
    """The admin phase-control record — seeded with per-key defaults on first access."""
    rec = one("site_state", id="phase")
    if not rec:
        rec = {"id": "phase", **SITE_FLAG_DEFAULTS, "updated_by": "", "updated_at": now()}
        insert("site_state", rec, prefix="x")
        return rec
    out = {"id": rec["id"], "updated_by": rec.get("updated_by") or "", "updated_at": rec.get("updated_at") or ""}
    for k in SITE_FLAG_KEYS:
        out[k] = bool(rec.get(k, SITE_FLAG_DEFAULTS[k]))
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


def delete_user_and_data(uid: str, actor: dict):
    """Delete a user and all their data: submissions (+ PDFs), registrations, OTPs.

    Also unassigns them from any submissions they were reviewing.
    Returns (user, flash_code | None).
    """
    user = find_user(uid)
    if not user:
        return None, "user_not_found"
    if user["id"] == actor["id"]:
        return user, "cannot_delete_self"
    if user.get("role") == "master_admin":
        admins = [u for u in load("users") if u.get("role") == "master_admin"]
        if len(admins) <= 1:
            return user, "last_admin"

    # submissions owned by this user — by user_id, plus any back-referenced ids
    subs = load("submissions")
    owned_ids = {s["id"] for s in subs if s.get("user_id") == uid}
    owned_ids.update(user.get("submission_ids") or [])

    # delete uploaded PDFs for owned submissions
    for sid in owned_ids:
        for version in (1, 2):
            path = pdf_path(sid, version)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as exc:
                    logger.warning("Could not delete PDF for submission %s: %s", sid, exc)

    # filter out owned submissions (by user_id or back-reference)
    remaining = [s for s in subs if s.get("user_id") != uid and s["id"] not in owned_ids]

    # unassign this user as reviewer on remaining submissions
    dirty = False
    for s in remaining:
        if s.get("reviewer_id") == uid:
            s["reviewer_id"] = ""
            if s.get("status") == STATUS_UNDER_REVIEW:
                s["status"] = STATUS_SUBMITTED
            dirty = True
        if s.get("feedback_by") == uid:
            s["feedback_by"] = ""
            dirty = True
        if s.get("decided_by") == uid:
            s["decided_by"] = ""
            dirty = True

    if owned_ids or dirty:
        save("submissions", remaining)

    # registrations
    regs = load("registrations")
    filtered_regs = [r for r in regs if r.get("user_id") != uid]
    if len(filtered_regs) != len(regs):
        save("registrations", filtered_regs)

    # OTPs by account email or by the user_id embedded in the payload
    try:
        otps = load("otps")
        email = user.get("email") or ""
        filtered_otps = [
            o for o in otps
            if o.get("email") != email
            and (o.get("payload") or {}).get("user_id") != uid
        ]
        if len(filtered_otps) != len(otps):
            save("otps", filtered_otps)
    except Exception:
        pass

    # delete user record
    users = load("users")
    users_filtered = [u for u in users if u["id"] != uid]
    save("users", users_filtered)

    # invalidate sessions
    try:
        from auth import _sessions as _sess
        for tok in [t for t, sess in list(_sess.items()) if sess.get("user_id") == uid]:
            _sess.pop(tok, None)
    except Exception:
        pass

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
    """True once at least one paper is finally Selected."""
    return any(s.get("status") == STATUS_SELECTED for s in find("submissions", user_id=user["id"]))


def selected_count(user: dict) -> int:
    return sum(1 for s in find("submissions", user_id=user["id"]) if s.get("status") == STATUS_SELECTED)


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
    elif cat in ("Industry", "Others"):
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
    """A student's papers — each record is a thread; newest first."""
    subs = find("submissions", user_id=user["id"])
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


def presenting_submissions(user: dict) -> list:
    """Selected papers the student has ticked to present."""
    return [
        s for s in find("submissions", user_id=user["id"])
        if s.get("status") == STATUS_SELECTED and s.get("presenting")
    ]


def presenting_count(user: dict) -> int:
    return len(presenting_submissions(user))


# Participant category -> registration-fee row on the main-page table.
FEE_CATEGORY_BY_PARTICIPANT = {
    "Student": "Indian Students",
    "Academic": "Faculty / Research Scientist / Engineers from Govt. Org.",
    "Industry": "Consultant / Other",
    "Others": "Consultant / Other",
}
FEE_FOREIGN_LABEL = "Foreign Delegates / Authors"

# Domestic (INR) rate applies to the INR_COUNTRIES; everyone else is foreign.
_INR_COUNTRY_KEYS = {c.lower() for c in INR_COUNTRIES} | {"in", "bharat"}


def _is_foreign(reg: dict) -> bool:
    """True when the participant's country is not on the domestic (INR) list."""
    key = "company_country" if reg.get("participant_category") in ("Industry", "Others") else "institute_country"
    country = (reg.get(key) or "").strip().lower()
    return bool(country) and country not in _INR_COUNTRY_KEYS


def _fee_row(label: str):
    for cat in (SITE_CONFIG.get("registration_fees") or {}).get("categories", []):
        if cat.get("label") == label:
            return cat
    return None


def unit_fee(reg: dict | None):
    """Per-presentation fee taken from the main-page table.

    The row follows the participant's category (foreign participants use the
    Foreign Delegates / Authors row). Early-bird pricing applies through the date in
    ``registration_fees.early_bird_until``; spot pricing after. Returns a dict
    ``{label, period, value, currency, display}`` or ``None`` if unresolvable.
    """
    if not reg:
        return None
    if _is_foreign(reg):
        label = FEE_FOREIGN_LABEL
    else:
        label = FEE_CATEGORY_BY_PARTICIPANT.get(reg.get("participant_category") or "")
    row = _fee_row(label) if label else None
    if not row:
        return None
    cutoff = (SITE_CONFIG.get("registration_fees") or {}).get("early_bird_until") or ""
    period = "early"
    if cutoff:
        try:
            if date.today() > date.fromisoformat(cutoff):
                period = "spot"
        except ValueError:
            pass
    return {
        "label": row["label"],
        "period": period,
        "value": row[f"{period}_value"],
        "currency": row.get("currency") or "INR",
        "display": row[period],
    }


def payable_amount(user: dict):
    """(count, unit) tuple for the student's ticked presentations."""
    return presenting_count(user), unit_fee(registration_for(user))


# ---------- submissions / papers ----------

def paper_view(sub: dict) -> dict:
    """A normalised copy of the record for templates."""
    out = dict(sub)
    out["title"] = sub.get("title") or ""
    out["authors"] = sub.get("authors") or []
    out["paper_type"] = sub.get("paper_type") or ""
    out["status"] = sub.get("status") or STATUS_SUBMITTED
    out["has_pdf"] = bool(sub.get("pdf_name"))
    out["pdf_name"] = sub.get("pdf_name") or ""
    out["pdf_size"] = sub.get("pdf_size") or 0
    out["pdf_version"] = sub.get("pdf_version") or 1
    out["feedback"] = sub.get("feedback") or ""
    out["round2_submitted_at"] = sub.get("round2_submitted_at") or ""
    out["decision_comment"] = sub.get("decision_comment") or ""
    out["presenting"] = bool(sub.get("presenting"))
    out["presentation_format"] = sub.get("presentation_format") or ""
    out["history"] = sub.get("history") or []
    return out


def current_view(sub: dict) -> dict:
    """The record as it stands today."""
    return paper_view(sub)


def submission_for(user: dict, sid: str):
    """Return (submission, flash_code | None). Enforces theme scope."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if user["role"] == "theme_incharge" and sub["theme"] not in (user.get("themes") or []):
        return None, "not_your_theme"
    return sub, None


def _author_row(a) -> dict:
    row = a.model_dump() if hasattr(a, "model_dump") else dict(a)
    return {
        "name": row.get("name", "") or "",
        "designation": row.get("designation", "") or "",
        "affiliation": row.get("affiliation", "") or "",
        "email": row.get("email", "") or "",
    }


def create_paper(user: dict, theme: str, paper_type: str, presentation_format: str,
                 title: str, authors: list) -> dict:
    """Open a new paper thread — title + authors + (PDF attached separately)."""
    record = insert(
        "submissions",
        {
            "user_id": user["id"],
            "theme": theme,
            "paper_type": paper_type,
            "title": title,
            "authors": [_author_row(a) for a in authors],
            "version": 1,
            "pdf_name": "",
            "pdf_size": 0,
            "pdf_uploaded_at": "",
            "pdf_version": 1,
            "status": STATUS_SUBMITTED,
            "reviewer_id": "",
            "feedback": "",
            "feedback_by": "",
            "feedback_at": "",
            "round2_submitted_at": "",
            "decision_comment": "",
            "decided_by": "",
            "decided_at": "",
            "presenting": False,
            "presentation_format": presentation_format,
            "presentation_chosen_at": "",
            "history": [],
            "created_at": now(),
        },
        prefix="s",
    )
    ids = (user.get("submission_ids") or []) + [record["id"]]
    update("users", user["id"], {"submission_ids": ids})
    return record


def _validate_pdf(data: bytes):
    if not data or not data.startswith(b"%PDF"):
        return "bad_pdf_type"
    max_bytes = int(SITE_CONFIG.get("max_pdf_mb", 25)) * 1024 * 1024
    if len(data) > max_bytes:
        return "pdf_too_large"
    return None


def save_pdf(sid: str, version: int, filename: str, data: bytes):
    """Validate + store a PDF for a paper version. Returns (fields, flash_code | None)."""
    err = _validate_pdf(data)
    if err:
        return None, err
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = pdf_path(sid, version)
    with open(path, "wb") as f:
        f.write(data)
    name = (filename or "submission.pdf").strip()[:255] or "submission.pdf"
    fields = {
        "pdf_name": name,
        "pdf_size": len(data),
        "pdf_uploaded_at": now(),
        "pdf_version": int(version or 1),
    }
    update("submissions", sid, fields)
    return fields, None


def submit_paper(user: dict, theme: str, paper_type: str, presentation_format: str,
                 title: str, authors: list, filename: str, data: bytes):
    """Create a paper and attach its first PDF. Returns (record, flash_code | None)."""
    err = _validate_pdf(data)
    if err:
        return None, err
    record = create_paper(user, theme, paper_type, presentation_format, title, authors)
    _, e = save_pdf(record["id"], 1, filename, data)
    if e:
        return record, e
    return record, None


def update_paper(user: dict, sid: str, presentation_format: str, title: str, authors: list,
                 filename: str | None = None, data: bytes | None = None):
    """Edit a paper before review starts (status == submitted). Optionally replace the PDF."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, "submission_not_found"
    if sub.get("status") != STATUS_SUBMITTED:
        return None, "submission_locked"
    update("submissions", sid, {
        "title": title,
        "authors": [_author_row(a) for a in authors],
        "presentation_format": presentation_format,
    })
    if data:
        _, e = save_pdf(sid, sub.get("pdf_version") or 1, filename or "", data)
        if e:
            return sub, e
    return sub, None


def submit_round2(user: dict, sid: str, authors: list,
                  filename: str | None = None, data: bytes | None = None):
    """Round 2 submission: save authors / optional new PDF, then mark the paper submitted.

    Only possible after feedback is released and while the final-submission window
    is open. Once submitted the paper is locked and awaits the final decision.
    """
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, "submission_not_found"
    if sub.get("status") != STATUS_FEEDBACK_RELEASED:
        return None, "round2_not_ready"
    if not site_flag("final_submission_open"):
        return None, "round2_closed"
    if data:
        history = list(sub.get("history") or [])
        history.append({
            "version": sub.get("version") or 1,
            "title": sub.get("title") or "",
            "authors": sub.get("authors") or [],
            "pdf_name": sub.get("pdf_name") or "",
            "pdf_size": sub.get("pdf_size") or 0,
            "pdf_uploaded_at": sub.get("pdf_uploaded_at") or "",
            "feedback": sub.get("feedback") or "",
        })
        new_version = int(sub.get("version") or 1) + 1
        update("submissions", sid, {"version": new_version, "history": history})
        _, e = save_pdf(sid, new_version, filename or "", data)
        if e:
            return sub, e
    update("submissions", sid, {
        "authors": [_author_row(a) for a in authors],
        "status": STATUS_ROUND2_SUBMITTED,
        "round2_submitted_at": now(),
    })
    return one("submissions", id=sid), None


def pdf_path(sid: str, version: int = 1) -> str:
    return os.path.join(UPLOAD_DIR, f"{sid}_v{int(version or 1)}.pdf")


def can_view_pdf(user: dict, sub: dict) -> bool:
    """Who may open a paper PDF: the owner, theme-scoped incharge, assigned
    reviewer, or a master admin."""
    if user["role"] == "student":
        return sub["user_id"] == user["id"]
    if user["role"] == "theme_incharge":
        return sub["theme"] in (user.get("themes") or [])
    if user["role"] == "reviewer":
        return sub.get("reviewer_id") == user["id"]
    return user["role"] == "master_admin"


def save_feedback(user: dict, sid: str, feedback: str):
    """Round-1 feedback — no decision; every paper advances. Returns (sub, flash_code | None)."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("status") not in (STATUS_SUBMITTED, STATUS_UNDER_REVIEW):
        return None, "bad_status"
    if user["role"] == "reviewer":
        if sub.get("reviewer_id") != user["id"] or sub.get("status") != STATUS_UNDER_REVIEW:
            return None, "not_your_assignment"
    elif user["role"] == "theme_incharge":
        if sub["theme"] not in (user.get("themes") or []):
            return None, "not_your_theme"
    update("submissions", sid, {
        "feedback": feedback.strip()[:2000],
        "feedback_by": user["id"],
        "feedback_at": now(),
        "status": STATUS_FEEDBACK_RELEASED,
    })
    return sub, None


def apply_final_decision(user: dict, sid: str, decision: str, comment: str):
    """Final decision — Selected, or Not Selected — once the paper is submitted to Round 2."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if sub.get("status") != STATUS_ROUND2_SUBMITTED:
        return None, "bad_status"
    if decision not in FINAL_DECISIONS:
        return None, "bad_decision"
    if user["role"] == "reviewer":
        if sub.get("reviewer_id") != user["id"]:
            return None, "not_your_assignment"
    elif user["role"] == "theme_incharge":
        if sub["theme"] not in (user.get("themes") or []):
            return None, "not_your_theme"
    update("submissions", sid, {
        "status": decision,
        "decision_comment": (comment or "").strip()[:1000],
        "decided_by": user["id"],
        "decided_at": now(),
    })
    return sub, None


def set_presentation(user: dict, sid: str, presenting: bool):
    """After selection — opt this paper in/out of the programme. Format was chosen at submission."""
    sub = one("submissions", id=sid)
    if not sub or sub["user_id"] != user["id"]:
        return None, "submission_not_found"
    if sub.get("status") != STATUS_SELECTED:
        return None, "not_selected_yet"
    if not site_flag("results_declared"):
        return None, "results_not_declared"
    update("submissions", sid, {
        "presenting": bool(presenting),
        "presentation_chosen_at": now() if presenting else "",
    })
    return sub, None


def set_presentation_format(sid: str, fmt: str):
    """Admin override — change a submission's Presentation/Poster format at any time."""
    sub = one("submissions", id=sid)
    if not sub:
        return None, "submission_not_found"
    if fmt not in FORMATS:
        return None, "bad_format"
    update("submissions", sid, {"presentation_format": fmt})
    return sub, None


def assign_reviewer(user: dict, sid: str, reviewer: dict):
    """Assign an eligible reviewer for Round-1 feedback or the Round-2 decision."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    if sub.get("status") not in (STATUS_SUBMITTED, STATUS_ROUND2_SUBMITTED):
        return None, "submission_not_pending"
    if reviewer.get("role") != "reviewer":
        return None, "reviewer_not_found"
    if sub["theme"] not in (reviewer.get("themes") or []):
        return None, "reviewer_theme_mismatch"
    status = STATUS_UNDER_REVIEW if sub.get("status") == STATUS_SUBMITTED else sub.get("status")
    update("submissions", sid, {"reviewer_id": reviewer["id"], "status": status})
    return sub, None


def unassign_reviewer(user: dict, sid: str):
    """Remove the assigned reviewer. Round 1 re-opens; Round 2 stays awaiting a decision."""
    sub, err = submission_for(user, sid)
    if err:
        return None, err
    if sub.get("status") not in (STATUS_UNDER_REVIEW, STATUS_ROUND2_SUBMITTED) or not sub.get("reviewer_id"):
        return None, "no_reviewer_assigned"
    status = STATUS_SUBMITTED if sub.get("status") == STATUS_UNDER_REVIEW else sub.get("status")
    update("submissions", sid, {"reviewer_id": "", "status": status})
    return sub, None


# ---------- scoping / filters / listing ----------

def scoped_submissions(user: dict) -> list:
    """Incharge: only their assigned themes. Master admin: everything."""
    subs = load("submissions")
    if user["role"] == "theme_incharge":
        allowed = set(user.get("themes") or [])
        subs = [s for s in subs if s["theme"] in allowed]
    return sorted(subs, key=lambda s: s.get("created_at", ""), reverse=True)


def filter_submissions(subs: list, theme: str = "", status: str = "", paper_type: str = "") -> list:
    if theme:
        subs = [s for s in subs if s["theme"] == theme]
    if paper_type:
        subs = [s for s in subs if (s.get("paper_type") or "") == paper_type]
    if status:
        subs = [s for s in subs if (s.get("status") or "") == status]
    return subs


def split_paper_stages(subs: list) -> tuple:
    """Split papers into (awaiting feedback, awaiting Round 2, awaiting decision, decided)."""
    feedback = [s for s in subs if (s.get("status") or "") in (STATUS_SUBMITTED, STATUS_UNDER_REVIEW)]
    round2 = [s for s in subs if (s.get("status") or "") == STATUS_FEEDBACK_RELEASED]
    final = [s for s in subs if (s.get("status") or "") == STATUS_ROUND2_SUBMITTED]
    done = [s for s in subs if (s.get("status") or "") in (STATUS_SELECTED, STATUS_NOT_SELECTED)]
    return feedback, round2, final, done


def decorated_subs(subs: list, students: dict, action_fn) -> list:
    """Decorate each submission with current view fields, `_student`, `_reviewer`, `_actions`."""
    out = []
    for s in subs:
        row = current_view(s)
        row["_student"] = (students.get(s["user_id"]) or {}).get("name", "—")
        rev = students.get(s.get("reviewer_id")) or {}
        row["_reviewer"] = rev.get("name", "") or ""
        row["_actions"] = action_fn(s)
        out.append(row)
    return out


def submission_actions(user: dict, s: dict) -> list:
    """Role-aware row actions for the incharge/admin submission tables."""
    actions = []
    status = s.get("status")
    if status == STATUS_SUBMITTED:
        actions.append({"url": f"/incharge/assign/{s['id']}", "label": "Assign reviewer", "cls": "btn-primary"})
        actions.append({"url": f"/incharge/review/{s['id']}", "label": "Give feedback", "cls": "btn-outline"})
    elif status == STATUS_UNDER_REVIEW:
        actions.append({"url": f"/incharge/change_reviewer/{s['id']}", "label": "Change reviewer", "cls": "btn-outline"})
        actions.append({"url": f"/incharge/review/{s['id']}", "label": "Give feedback", "cls": "btn-primary"})
    elif status == STATUS_ROUND2_SUBMITTED:
        if s.get("reviewer_id"):
            actions.append({"url": f"/incharge/change_reviewer/{s['id']}", "label": "Change reviewer", "cls": "btn-outline"})
        else:
            actions.append({"url": f"/incharge/assign/{s['id']}", "label": "Assign reviewer", "cls": "btn-outline"})
        actions.append({"url": f"/incharge/final/{s['id']}", "label": "Final decision", "cls": "btn-primary"})
    return actions


def detail_actions(user: dict, s: dict) -> list:
    """Buttons for a submission detail page (side panel)."""
    actions = submission_actions(user, s)
    if s.get("status") == STATUS_UNDER_REVIEW and s.get("reviewer_id"):
        actions.append({"url": f"/incharge/takeover/{s['id']}", "label": "Take over & review myself", "cls": "btn-accent"})
    if s.get("status") == STATUS_ROUND2_SUBMITTED and s.get("reviewer_id"):
        actions.append({"url": f"/incharge/takeover/{s['id']}", "label": "Take over & decide myself", "cls": "btn-accent"})
    return actions


# ---------- reviewer scope ----------

def reviewer_submissions(reviewer: dict) -> list:
    """All papers assigned to this reviewer."""
    subs = [s for s in load("submissions") if s.get("reviewer_id") == reviewer["id"]]
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
