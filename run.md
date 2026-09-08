# INFRASURE 2027 — How to Run

Conference website for INFRASURE 2027 — FastAPI + Jinja2, JSON-file database.

## 1. Setup (first time)

```bash
python3 -m venv .venv                 # create virtual environment
source .venv/bin/activate             # activate it (Windows: .venv\Scripts\activate)
pip install -r requirements.txt       # install dependencies
```

## 2. Existing admin accounts

The two master admin accounts live directly in `data/users.json` (no seeder needed):

| Account       | Email                            | Password |
|---------------|----------------------------------|----------|
| Master admin  | admin1@infrasure.in             | admin1   |
| Master admin  | admin2@infrasure.in             | admin2   |

Use the admin panel to create all other accounts — students register themselves,
theme incharges and reviewers are created by the admin (or reviewers by incharges).

## 3. Run the server

```bash
uvicorn main:app --reload --port 8000
# or without activate:
.venv/bin/uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000

## 4. The submission workflow (2 rounds)

```
student registers → student completes their details (info) → may apply (max 2)
  → Round 1 submitted (PPT/Poster + theme + title + abstract) → status: pending
  → incharge assigns a reviewer (or reviews Round 1 themselves)
  → under_review → reviewer sends feedback / questions / requested changes
  → feedback_given  (NO selected/not-selected in round 1)
  → student submits Round 2 — same record, fills title_r2/description_r2 (format
    and theme stay fixed) → status: awaiting_decision
  → Round 2 goes straight to the theme incharge (no reviewer)
  → awaiting_decision → incharge sees Round1 + feedback + Round2 side-by-side
  → decides selected | not_selected
```

- Only 2 rounds. Reviewer never selects anything — review is feedback only.
- Payment unlocks only after: a presentation is **selected** AND the conference
  team **approves** the student's details (`/admin/registrations`).
- Payment page is a **simulation** — it marks `fee_paid: true`. A real gateway
  comes later.

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