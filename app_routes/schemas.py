"""Pydantic models for form validation."""
import re

from pydantic import BaseModel, field_validator, model_validator

MAX_SUBMISSIONS = 2
FORMATS = ("ppt", "poster")
ROUND1_DECISIONS = ("r1_selected", "r1_not_selected")
DESIGNATIONS = ("UG", "PG", "PhD Scholar", "Faculty", "Industry", "Other")
PARTICIPANT_CATEGORY = ("Student", "Academic", "Industry")
STUDENT_LEVEL = ("UG", "PG", "PhD")
UG_PROGRAM = ("BTech", "Dual Degree")
DEGREE_UG = ("BTech", "BE", "BSc", "BA", "BArch", "BDes", "Other")
DEGREE_PG = ("MTech", "ME", "MSc", "MA", "MBA", "MArch", "MDes", "Other")
ACADEMIC_ROLE = ("Postdoc", "Early Career Researcher", "Professor")
PROFESSOR_TYPE = ("Assistant Professor", "Associate Professor", "Professor")
PARTICIPATION_MODES = ("in_person",)
REVIEW_DECISIONS = ("selected", "not_selected")
ADMIN_REG_STATUS = ("approved", "rejected")

THEME_LABELS = tuple(f"Theme {i}" for i in range(1, 10))

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_RE = r"^\+?[0-9][0-9 \-]{8,14}$"

# Common free/personal email domains that are NOT allowed for institute/company email
PERSONAL_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.in",
    "outlook.com", "outlook.in", "hotmail.com", "live.com", "msn.com", "hotmail.co.uk",
    "aol.com",
    "protonmail.com", "proton.me", "pm.me",
    "icloud.com", "me.com", "mac.com",
    "yandex.com", "yandex.ru", "yandex.in",
    "zoho.com", "zoho.in", "zoho.eu",
    "gmx.com", "gmx.de",
    "mail.com",
    "tutanota.com", "tutanota.de",
    "fastmail.com",
    "rediffmail.com",
    "inbox.com",
})


def _is_personal_email(email: str) -> bool:
    """Return True if email domain is a known personal/free provider."""
    try:
        domain = email.strip().lower().split("@", 1)[1]
    except IndexError:
        return False
    if domain in PERSONAL_EMAIL_DOMAINS:
        return True
    # sub-domain check e.g. foo.gmail.com -> still personal
    for d in PERSONAL_EMAIL_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return True
    return False


def _errors(exc) -> list[str]:
    out = []
    for e in exc.errors():
        msg = e.get("msg", "Invalid value.")
        out.append(msg.removeprefix("Value error, "))
    return out


def validate(model, data: dict):
    """Return (instance | None, list[str] of human-readable errors)."""
    try:
        return model(**data), []
    except Exception as exc:  # ValidationError
        return None, _errors(exc)


def clean_name(v: str, label: str = "name") -> str:
    v = v.strip()
    if len(v) < 2:
        raise ValueError(f"Please enter your {label}.")
    return v


def clean_email(v: str, strict: bool = True) -> str:
    v = v.strip().lower()
    ok = EMAIL_RE if strict else "@" in v
    if not ok:
        raise ValueError("Please enter a valid email address.")
    return v


def clean_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return v


def clean_themes(v: list[str]) -> list[str]:
    chosen = {t for t in v if t in THEME_LABELS}
    if not chosen:
        raise ValueError("Assign at least one theme.")
    return [t for t in THEME_LABELS if t in chosen]  # config order, deduped


class _AccountBase(BaseModel):
    """Shared name/email/password fields for every account-creation form."""

    name: str = ""
    email: str = ""
    password: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return clean_name(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return clean_email(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return clean_password(v)


class RegisterForm(_AccountBase):
    confirm: str = ""
    agree: str = ""

    @model_validator(mode="after")
    def _match(self):
        if self.password != self.confirm:
            raise ValueError("Passwords do not match.")
        if self.agree not in ("on", "true", "1"):
            raise ValueError("Please accept the Terms and Conditions to create an account.")
        return self


class InchargeForm(_AccountBase):
    themes: list[str] = []

    @field_validator("themes")
    @classmethod
    def _themes(cls, v: list[str]) -> list[str]:
        return clean_themes(v)


class ReviewerCreateForm(_AccountBase):
    """Name/email/password for a new reviewer — themes are assigned separately."""


class PasswordForm(BaseModel):
    password: str = ""

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return clean_password(v)


class LoginForm(BaseModel):
    email: str = ""
    password: str = ""

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return clean_email(v, strict=False)


def clean_title(v: str) -> str:
    v = v.strip()
    if not 8 <= len(v) <= 160:
        raise ValueError("Title must be between 8 and 160 characters.")
    return v


def clean_description(v: str) -> str:
    v = v.strip()
    if not 40 <= len(v) <= 4000:
        raise ValueError("Abstract must be between 40 and 4,000 characters.")
    return v


class SubmissionForm(BaseModel):
    """Round 1 — title + abstract only. The format (PPT/Poster) is chosen in Round 2."""

    theme: str = ""
    title: str = ""
    description: str = ""

    @field_validator("theme")
    @classmethod
    def _theme(cls, v: str) -> str:
        if v not in THEME_LABELS:
            raise ValueError("Please choose one of the nine conference themes.")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return clean_title(v)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        return clean_description(v)


class FormatChoiceForm(BaseModel):
    """Round 2 starts with the student choosing PPT or Poster — per submission."""

    format: str = ""

    @field_validator("format")
    @classmethod
    def _format(cls, v: str) -> str:
        if v not in FORMATS:
            raise ValueError("Please choose PPT or Poster.")
        return v


class RoundOneDecisionForm(BaseModel):
    """Round 1 decision — Selected for Round 2, or Not Selected (dead end).

    Recorded by the assigned reviewer (when under review) or by the theme incharge
    directly. Always accompanies feedback shown to the student.
    """

    decision: str = ""
    comment: str = ""

    @field_validator("decision")
    @classmethod
    def _decision(cls, v: str) -> str:
        if v not in ROUND1_DECISIONS:
            raise ValueError("Please choose Selected for Round 2 or Not Selected.")
        return v

    @field_validator("comment")
    @classmethod
    def _comment(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Please leave at least a short note with your feedback.")
        return v.strip()[:1000]


class RoundTwoForm(BaseModel):
    """Round 2 (Poster) — revised title + abstract addressing the Round 1 feedback."""

    title: str = ""
    description: str = ""

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return clean_title(v)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        return clean_description(v)


class RoundTwoDecisionForm(BaseModel):
    """Final decision — Selected, or Not Selected (dead end).

    Recorded by the assigned Round 2 reviewer (when under review) or by the theme
    incharge directly. Always accompanies feedback shown to the student.
    """

    decision: str = ""
    comment: str = ""

    @field_validator("decision")
    @classmethod
    def _decision(cls, v: str) -> str:
        if v not in REVIEW_DECISIONS:
            raise ValueError("Please choose Selected or Not Selected.")
        return v

    @field_validator("comment")
    @classmethod
    def _comment(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Please leave at least a short note with your feedback.")
        return v.strip()[:1000]


class AnnouncementForm(BaseModel):
    title: str = ""
    body: str = ""

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not 3 <= len(v) <= 160:
            raise ValueError("Title must be between 3 and 160 characters.")
        return v

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        v = v.strip()
        if not 10 <= len(v) <= 4000:
            raise ValueError("Announcement body must be between 10 and 4,000 characters.")
        return v


class FaqCategoryForm(BaseModel):
    name: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return clean_name(v, "category name")


class FaqForm(BaseModel):
    category_id: str = ""
    question: str = ""
    answer: str = ""
    order: int = 0

    @field_validator("category_id")
    @classmethod
    def _category(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("c_"):
            raise ValueError("Please choose a category.")
        return v

    @field_validator("question")
    @classmethod
    def _question(cls, v: str) -> str:
        v = v.strip()
        if not 5 <= len(v) <= 300:
            raise ValueError("Question must be between 5 and 300 characters.")
        return v

    @field_validator("answer")
    @classmethod
    def _answer(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Answer must be at least 10 characters.")
        return v[:4000]

    @field_validator("order")
    @classmethod
    def _order(cls, v: int) -> int:
        return max(0, int(v or 0))


class AttendanceForm(BaseModel):
    """Participant details with conditional branching.

    Branching:
      participant_category = Student | Academic | Industry (compulsory)
      Student → student_level (UG|PG|PhD), ug_program (if UG), degree_name,
                department, institute_name, institute_address, institute_email,
                supervisor_name (if PhD)
      Academic → academic_role (Postdoc|ECR|Professor), professor_type (if Professor),
                 department, institute_name, institute_address, institute_email
      Industry → company_name, position, company_email (+ optional company_address)
    All fields in the active branch are compulsory.
    Legacy fields `designation`/`affiliation` are kept optional for backward compat.
    """

    full_name: str = ""
    phone: str = ""
    participation_mode: str = ""
    # new taxonomy
    participant_category: str = ""
    student_level: str = ""
    ug_program: str = ""
    degree_name: str = ""
    department: str = ""
    institute_name: str = ""
    institute_address: str = ""
    institute_country: str = ""
    institute_zipcode: str = ""
    institute_email: str = ""
    institute_email_same: str = ""
    supervisor_name: str = ""
    academic_role: str = ""
    professor_type: str = ""
    company_name: str = ""
    position: str = ""
    company_email: str = ""
    company_address: str = ""
    company_country: str = ""
    company_zipcode: str = ""
    company_email_same: str = ""
    # account email for cross-check (passed from route, not rendered)
    account_email: str = ""
    # legacy (optional, for old rows)
    designation: str = ""
    affiliation: str = ""

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return clean_name(v, "full name")

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        if not re.match(PHONE_RE, v.strip()):
            raise ValueError("Please enter a valid phone number.")
        return v.strip()

    @field_validator("participation_mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in PARTICIPATION_MODES:
            raise ValueError("Please choose in-person participation.")
        return v

    @model_validator(mode="after")
    def _branch_validate(self):
        # top-level category
        cat = (self.participant_category or "").strip()
        if cat not in PARTICIPANT_CATEGORY:
            raise ValueError("Please select whether you are Student, Academic or Industry.")
        self.participant_category = cat
        self.account_email = (self.account_email or "").strip().lower()

        # helpers
        def _req(val: str, msg: str) -> str:
            if not val or not val.strip():
                raise ValueError(msg)
            return val.strip()

        def _email(val: str, msg: str) -> str:
            v = _req(val, msg)
            if not re.match(EMAIL_RE, v.lower()):
                raise ValueError("Please enter a valid email address.")
            return v.lower()

        def _addr(val: str, msg: str) -> str:
            v = _req(val, msg)
            if not 10 <= len(v) <= 600:
                raise ValueError("Address must be between 10 and 600 characters.")
            return v

        def _country(val: str, msg: str) -> str:
            v = _req(val, msg)
            if not 2 <= len(v) <= 56:
                raise ValueError("Country must be between 2 and 56 characters.")
            if not re.match(r"^[A-Za-z \-']+$", v):
                raise ValueError("Country should contain only letters, spaces, hyphens or apostrophes.")
            return v.strip()

        def _zipcode(val: str, msg: str) -> str:
            v = _req(val, msg)
            if not 3 <= len(v) <= 10:
                raise ValueError("Zip / postal code must be 3 to 10 characters.")
            if not re.match(r"^[A-Za-z0-9 \-]+$", v):
                raise ValueError("Zip / postal code should contain only letters, digits, spaces or hyphens.")
            return v.strip()

        if cat == "Student":
            lvl = _req(self.student_level, "Please select UG, PG or PhD.")
            if lvl not in STUDENT_LEVEL:
                raise ValueError("Please select UG, PG or PhD.")
            self.student_level = lvl

            if lvl == "UG":
                prog = _req(self.ug_program, "Please select BTech or Dual Degree for UG.")
                if prog not in UG_PROGRAM:
                    raise ValueError("Please select BTech or Dual Degree.")
                self.ug_program = prog
            else:
                self.ug_program = (self.ug_program or "").strip()

            deg = _req(self.degree_name, "Please enter your degree (e.g. BTech, BSc, MTech, MSc).")
            if not 1 <= len(deg) <= 80:
                raise ValueError("Degree must be between 1 and 80 characters.")
            self.degree_name = deg

            self.department = _req(self.department, "Please enter your department.")
            self.institute_name = _req(self.institute_name, "Please enter your institute name.")
            self.institute_address = _addr(self.institute_address, "Please enter your institute address.")
            self.institute_country = _country(self.institute_country, "Please enter your country.")
            self.institute_zipcode = _zipcode(self.institute_zipcode, "Please enter your zip / postal code.")
            # institute email: optional for UG/PG; compulsory otherwise
            same_inst = (self.institute_email_same or "").strip().lower() in ("on", "true", "1", "yes")
            self.institute_email_same = "on" if same_inst else ""
            if same_inst:
                acct = _req(self.account_email, "Registration email missing.")
                acct = _email(acct, "Registration email is invalid.")
                if _is_personal_email(acct):
                    raise ValueError("Your registration email is a personal address (Gmail/Yahoo/Outlook). Please enter your official institute email instead of using 'Same as registration email'.")
                self.institute_email = acct
            elif lvl in ("UG", "PG") and not (self.institute_email or "").strip():
                self.institute_email = ""
            else:
                self.institute_email = _email(self.institute_email, "Please enter your institute email.")
                if _is_personal_email(self.institute_email):
                    raise ValueError("Please use your official institute email, not a personal email (Gmail/Yahoo/Outlook etc.).")

            if lvl == "PhD":
                self.supervisor_name = _req(self.supervisor_name, "Please enter your supervisor name.")
            else:
                self.supervisor_name = (self.supervisor_name or "").strip()

            # clear academic/industry fields
            self.academic_role = (self.academic_role or "").strip()
            self.professor_type = (self.professor_type or "").strip()
            self.company_name = (self.company_name or "").strip()
            self.position = (self.position or "").strip()
            self.company_email = (self.company_email or "").strip()
            self.company_address = (self.company_address or "").strip()
            self.company_country = (self.company_country or "").strip()
            self.company_zipcode = (self.company_zipcode or "").strip()
            self.company_email_same = (self.company_email_same or "").strip()

        elif cat == "Academic":
            role = _req(self.academic_role, "Please select Postdoc, Early Career Researcher or Professor.")
            if role not in ACADEMIC_ROLE:
                raise ValueError("Please select Postdoc, Early Career Researcher or Professor.")
            self.academic_role = role

            if role == "Professor":
                pt = _req(self.professor_type, "Please select Assistant, Associate or Professor.")
                if pt not in PROFESSOR_TYPE:
                    raise ValueError("Please select Assistant Professor, Associate Professor or Professor.")
                self.professor_type = pt
            else:
                self.professor_type = (self.professor_type or "").strip()

            self.department = _req(self.department, "Please enter your department.")
            self.institute_name = _req(self.institute_name, "Please enter your institute / organization name.")
            self.institute_address = _addr(self.institute_address, "Please enter your institute address.")
            self.institute_country = _country(self.institute_country, "Please enter your country.")
            self.institute_zipcode = _zipcode(self.institute_zipcode, "Please enter your zip / postal code.")
            same_inst = (self.institute_email_same or "").strip().lower() in ("on", "true", "1", "yes")
            self.institute_email_same = "on" if same_inst else ""
            if same_inst:
                acct = _req(self.account_email, "Registration email missing.")
                acct = _email(acct, "Registration email is invalid.")
                if _is_personal_email(acct):
                    raise ValueError("Your registration email is a personal address (Gmail/Yahoo/Outlook). Please enter your official institute email instead of using 'Same as registration email'.")
                self.institute_email = acct
            else:
                self.institute_email = _email(self.institute_email, "Please enter your institute email.")
                if _is_personal_email(self.institute_email):
                    raise ValueError("Please use your official institute email, not a personal email (Gmail/Yahoo/Outlook etc.).")

            # clear student/industry
            self.student_level = (self.student_level or "").strip()
            self.ug_program = (self.ug_program or "").strip()
            self.degree_name = (self.degree_name or "").strip()
            self.supervisor_name = (self.supervisor_name or "").strip()
            self.company_name = (self.company_name or "").strip()
            self.position = (self.position or "").strip()
            self.company_email = (self.company_email or "").strip()
            self.company_address = (self.company_address or "").strip()
            self.company_country = (self.company_country or "").strip()
            self.company_zipcode = (self.company_zipcode or "").strip()

        else:  # Industry
            self.company_name = _req(self.company_name, "Please enter your company name.")
            self.position = _req(self.position, "Please enter your position / designation.")
            same_comp = (self.company_email_same or "").strip().lower() in ("on", "true", "1", "yes")
            self.company_email_same = "on" if same_comp else ""
            if same_comp:
                acct = _req(self.account_email, "Registration email missing.")
                acct = _email(acct, "Registration email is invalid.")
                if _is_personal_email(acct):
                    raise ValueError("Your registration email is a personal address (Gmail/Yahoo/Outlook). Please enter your official company email instead of using 'Same as registration email'.")
                self.company_email = acct
            else:
                self.company_email = _email(self.company_email, "Please enter your company email.")
                if _is_personal_email(self.company_email):
                    raise ValueError("Please use your official company email, not a personal email (Gmail/Yahoo/Outlook etc.).")
            self.company_address = _addr(self.company_address, "Please enter your company address.")
            self.company_country = _country(self.company_country, "Please enter your country.")
            self.company_zipcode = _zipcode(self.company_zipcode, "Please enter your zip / postal code.")

            # clear student/academic but keep department not needed
            self.student_level = (self.student_level or "").strip()
            self.ug_program = (self.ug_program or "").strip()
            self.degree_name = (self.degree_name or "").strip()
            self.department = (self.department or "").strip()
            self.institute_name = (self.institute_name or "").strip()
            self.institute_address = (self.institute_address or "").strip()
            self.institute_country = (self.institute_country or "").strip()
            self.institute_zipcode = (self.institute_zipcode or "").strip()
            self.institute_email = (self.institute_email or "").strip()
            self.supervisor_name = (self.supervisor_name or "").strip()
            self.academic_role = (self.academic_role or "").strip()
            self.professor_type = (self.professor_type or "").strip()

        # legacy fields: normalize but not required
        self.designation = (self.designation or "").strip()
        self.affiliation = (self.affiliation or "").strip()
        # keep backward compat: if new institute_name present, mirror to affiliation
        if self.institute_name and not self.affiliation:
            self.affiliation = self.institute_name
        # if old designation present and no category mapping, ignore
        return self