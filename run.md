# INFRASURE 2027 — How to Run

Conference website for INFRASURE 2027 — FastAPI + Jinja2, JSON-file database.

## 1. Setup (first time)

```bash
python3 -m venv .venv                 # create virtual environment
source .venv/bin/activate             # activate it (Windows: .venv\Scripts\activate)
pip install -r requirements.txt       # install dependencies
```

## 2. Admin accounts

The two master admin accounts live directly in `data/users.json` (no seeder needed).

> **Security note:** never commit passwords to this file (or anywhere in git).
> Admin passwords are rotated to strong random values; store them in a password
> manager or `.env` (gitignored), never in `run.md`. If you need to reset one,
> run:

```bash
.venv/bin/python3 -c "
import json
from auth import hash_password
import secrets, string
with open('data/users.json') as f: users = json.load(f)
pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
for u in users:
    if u.get('email') == 'admin1@infrasure.in':
        u['password_hash'] = hash_password(pw)
        u['failed_logins'] = 0; u['locked_until'] = 0
        print('admin1@infrasure.in ->', pw)
with open('data/users.json','w') as f: json.dump(users, f, indent=2, ensure_ascii=False)
"
```

Use the admin panel to create all other accounts — students register themselves,
theme incharges and reviewers are created by the admin (or reviewers by incharges).

## 3. Run the server

> **Security requirement:** uvicorn must run with proxy-header trust **disabled**
> (`--no-proxy-headers`) unless this app is genuinely behind a trusted reverse
> proxy. Uvicorn's default (`proxy_headers=True`,
> `forwarded_allow_ips=127.0.0.1`) lets any local client spoof
> `X-Forwarded-For`, which bypasses every rate limit (login brute-force, OTP
> guessing, email bombing). `--no-proxy-headers` makes the rate limiter key on
> the real TCP peer address.

```bash
uvicorn main:app --reload --port 8000 --no-proxy-headers
# or without activate:
.venv/bin/uvicorn main:app --reload --port 8000 --no-proxy-headers
```

If you deploy behind nginx/Caddy/etc., keep `--proxy-headers` but restrict trust
to the proxy's own IP only:

```bash
uvicorn main:app --port 8000 --proxy-headers --forwarded-allow-ips <PROXY_IP>
```

Open http://127.0.0.1:8000

## 4. The submission workflow

```
student registers → completes their details (info) → may submit any number of papers
  → "New submission" → picks Full Paper or Extended Abstract
    → form: theme + title + PDF + authors → status: submitted
  → incharge assigns a reviewer (or reviews it themselves)
  → under_review → reviewer sends feedback ONLY (no selected/not-selected here)
  → feedback_released  (every submission advances)
  → while the final-submission window is open (open by default), student may
    upload a revised PDF and/or edit authors (title and paper type stay fixed)
    then clicks "Submit for Final Review" → status: round2_submitted (locked)
  → reviewer/incharge records the final decision → selected | not_selected
  → admin declares results → if selected, student picks PPT or Poster and ticks
    whether they will present it
  → payment: charged per presentation the student opted in to
```

- There is **no cap** on submissions; each paper is an independent record.
- Review feedback is guidance only — **everyone advances**; the only
  Selected / Not Selected decision happens after the final submission.
- The final-submission window is **open by default**; the admin can Stop it
  (there is no "open revision" step). Final decisions require the student to
  have submitted the final version (`round2_submitted`).
- Payment unlocks only after: a paper is **selected**, results are declared,
  AND the conference team **approves** the student's details
  (`/admin/registrations`). Presentation choice follows results automatically.
- Payment page is a **simulation** — it marks `fee_paid: true`. The
  per-presentation fee comes from the main-page registration table by category
  (Student → Indian Students, Academic → Faculty / Research Scientist / Engineers
  from Govt. Org., Industry/Others → Consultant / Other; non-India participants →
  Foreign Delegates / Authors) and by date (early bird through 31 Dec 2026,
  standard after). A real gateway comes later.

## 5. Project layout

```
main.py            # FastAPI app entry
site_config.py     # all event content (SITE_CONFIG) + Jinja2 templates
db.py              # JSON database helper (atomic writes)
auth.py            # password hashing + session tokens + role guards (4 roles)
app_routes/        # public / auth / student / incharge / reviewer / admin routers +
                    #   schemas.py (pydantic forms) · service.py (domain logic) · utils.py (flashes)
templates/         # Jinja2 templates (base, index, announcements, faq, login/register, per-role folders)
static/css/        # stylesheet
media/             # images (logo, gallery)
data/              # JSON "database" (gitignored) — users, submissions, registrations,
                    #   announcements, faq_categories, faqs
webinfo_md/        # content + planning docs
```

## 7. Announcements & FAQs

- Public pages: `/announcements` (archive — shows everything) and `/faq`
  (questions grouped by category).
- Only a **master admin** can manage them:
  - `/admin/announcements` — publish announcements, edit, delete, and toggle
    "show on homepage". The homepage strip (below the hero) shows only the
    toggled-on ones; the `/announcements` page always lists everything.
  - `/admin/faqs` — manage FAQ categories + FAQs (order controls sorting).
- FAQ categories are auto-seeded (General, Registration, Submissions, Selection,
  Payment) on first visit; a category can be deleted only after its FAQs are moved.

## 8. Useful links

- Docs (auto-generated): http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## 9. Notes

- `data/*.json` is gitignored runtime data. The two admins live in
  `data/users.json`; back that file up before clearing data.
- Sessions are in-memory; restarting the server logs everyone out (by design
  for now).
- Payment page is a **simulation** — it marks `fee_paid: true`. A real gateway
  comes later.