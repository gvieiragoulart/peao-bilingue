"""VanHack site selectors, all documented.

Mapped against the real site on 2026-10-05.

Login is **passwordless** and lives on `auth.vanhack.com`, outside the app
(`app.vanhack.com/login` returns 404). The login selectors exist only to **detect** the
login screen and the Cloudflare challenge, never to fill in the form, which is always
the user's job.
"""

# --- Login screen (auth.vanhack.com) -----------------------------------------

# Subtitle text; confirms the flow doesn't use a password.
LOGIN_SUBTITLE = "No password needed"

# Email field of the magic-link form.
LOGIN_EMAIL_INPUT = 'input[type="email"]'

# Social login buttons; the email form uses the "Continue" submit button.
LOGIN_LINKEDIN_BUTTON = "Continue with LinkedIn"
LOGIN_GOOGLE_BUTTON = "Continue with Google"
LOGIN_SUBMIT_BUTTON = "Continue"

# Honeypot: a text input labeled "Website", invisible to humans. Filling it in marks
# the session as a bot. NEVER interact with it.
LOGIN_HONEYPOT_LABEL = "Website"

# --- Human challenge (Cloudflare Turnstile) ----------------------------------

# The widget runs inside a Cloudflare iframe.
TURNSTILE_IFRAME = 'iframe[src*="challenges.cloudflare.com"]'

# Message shown when Turnstile rejects the browser (the typical case for an automated
# browser): "Security check could not complete. Refresh this page or try another
# browser."
SECURITY_CHECK_FAILED = "Security check could not complete"

# Other generic signs of a block or a check. Cloudflare also shows them in the
# browser's language, hence the Portuguese one.
CHALLENGE_TEXTS = (
    SECURITY_CHECK_FAILED,
    "Verify you are human",
    "Confirme que \u00e9 humano",
    "Checking your browser",
)

# --- Profile page (/profile) -------------------------------------------------
# Mapped against the real site. The layout is semantic and stable: `pf-*` is the
# profile, `vh-*` is the design system. The ids Blazor generates (`0HNP0Q2EPN2A7`,
# `vhdd-<guid>-button`) change on every render: never use them.

PROFILE_READY = "#profile-first-name"  # anchor: the profile has rendered

SECTION = "section.pf-section"
SECTION_TITLE = "h5.pf-section-title"

# A question/answer pair: label.pf-label + one control (dropdown or autocomplete).
FIELD = "div.pf-field"
FIELD_LABEL = "label.pf-label"
DROPDOWN = "div.vh-dd"  # custom dropdown; its text is the chosen value
AUTOCOMPLETE_INPUT = "input.form-control"  # the value lives in input_value()

# A field may have radios, checkboxes or several rows (e.g. 7 countries).
RADIO_CHECKED = "label.pf-radio:has(input:checked)"
CHECKBOX_CHECKED = "label.pf-check:has(input:checked)"
TARGET_ROW = "div.pf-target-row"  # one country preference per row

# What these controls show when nothing was chosen.
EMPTY_VALUES = ("Select an option", "Choose a country", "Select Language")

# Skills: two groups (top 3 and secondary), told apart by their title.
SKILL_GROUP = "div.pf-skill-group"
SKILL_GROUP_TITLE = "div.pf-skill-group-title"
SKILL_ROW = "div.pf-skill-row"
SKILL_SELECT = "div.pf-skill-select"
SKILL_YEARS = "div.pf-skill-years"
MAIN_SKILLS_GROUP = "Rank your top 3 skills"
SECONDARY_SKILLS_GROUP = "Add 5 secondary skills"

# Languages
LANG_ROW = "div.pf-lang-row"
LANG_SELECT = "div.pf-lang-select"
LANG_LEVEL = "div.pf-lang-level"

# Experience: one company may have several roles.
EXPERIENCE = "div.pf-exp"
EXP_COMPANY = "a.pf-item-title"
EXP_INDUSTRY = "div.pf-item-sub"
EXP_ROLE = "div.pf-role"
EXP_ROLE_HEAD = "div.pf-role-head"  # role + period, in the same text
EXP_ROLE_DESC = "div.pf-role-desc"
EXP_ROLE_CHIPS = "div.pf-chips span.vh-chip"  # one skill per chip; some have spaces

# Education
EDUCATION_DEGREE = "div.pf-degree"

# English level assessed in the Intro Video, as "Level: Fluent".
INTRO_VIDEO_CARD = "div.pf-intro-video-card"
INTRO_VIDEO_LEVEL = r"Level:\s*(\w+)"

# Social links, told apart by their placeholder.
LINK_INPUTS = {
    "linkedin": 'input[placeholder="http://linkedin.com/"]',
    "github": 'input[placeholder="http://github.com/"]',
    "site": 'input[placeholder="http://sitename.com/"]',
}

# Labels of the questions that become structured snapshot fields.
LABEL_ROLE = "Which role best applies to your experience?"
LABEL_IT_YEARS = "For how many years have you been working as an IT professional?"
LABEL_LEADERSHIP = "Do you have leadership experience?"
LABEL_LEADERSHIP_YEARS = "Years of leadership"
LABEL_REMOTE = "Are you open to remote jobs?"
LABEL_AVAILABILITY = "When would you be available to start a new job?"

# PII: never goes into the snapshot or the prompt (see "Non-negotiable rules").
# Besides these, the CV URL is signed (SAS token) and is left out too.
PII_LABELS = (
    "phone",
    "passport",
    "visa",
    "email",
    "birth",
    "document",
    "citizenship",
    "name",
)

# --- Job listing (/jobs and /jobs/{slug}-jobs) --------------------------------
# Searching is done by URL: /jobs/python-jobs really filters (checked by comparing the
# ids returned). The listing **scrolls infinitely**: 10 cards on the first render, 25
# after scrolling.

CARDS_CONTAINER = "div.vh-cards"
# A search with no results: the container exists and says "You're seeing 0 jobs".
EMPTY_STATE_TEXT = "You're seeing 0 jobs"
# Scoping the links to the container is required: the job page has `a.vh-jd-minicard`
# pointing to other jobs (recommended/recent).
CARD_LINK = "a.vh-card-link"
CARD = "div.vh-card"
CARD_EYEBROW = "div.vh-eyebrow"  # e.g. "BACKEND ENGINEER · 8+ YEARS OF EXPERIENCE"
CARD_TITLE = "h2.vh-card-title"
CARD_LOCATION = "span.vh-detail-label"
CARD_MODE = "span.vh-mode-pill"  # "Hybrid" / "Fully remote"
CARD_SKILL = "span.vh-skill"
CARD_SKILL_MUST = "vh-skill-must"  # modifier: required skill
CARD_POSTED = "span.vh-posted"
CARD_SALARY = "div.vh-salary-amount"
CARD_CANDIDATE_LOCATION = "div.vh-card-candidate-location"

JOB_URL_ID = r"/job/(\d+)"  # the job id comes from the URL, never from the text

# --- Job page (/job/{id}) -----------------------------------------------------

JD_ROOT = "div.vh-jd"
JD_TITLE = "section.vh-jd-hero h1"
JD_FACT = "span.vh-jd-fact"
JD_MODE = "span.vh-jd-mode-pill"
JD_CANDIDATE_LOCATION = "div.vh-jd-candidate-location"
JD_DESCRIPTION = "div.vh-jd-description"
JD_SALARY = "span.vh-jd-apply-salary-amount"

# Skill blocks: a header (MUST-HAVE / NICE-TO-HAVE / LANGUAGES) + chips.
JD_SUBBLOCK = "div.vh-jd-subblock"
JD_SUBBLOCK_HEAD = "div.vh-jd-skill-key-head"
JD_CHIP = "span.vh-jd-skill"
JD_CHIP_YEARS = "small"  # inside the chip: "5 Year(s)"
JD_HEAD_MUST = "MUST-HAVE"
JD_HEAD_NICE = "NICE-TO-HAVE"
JD_HEAD_LANGUAGES = "LANGUAGES"

# VanHack **doesn't publish the company**: not on the card, not on the job page (the
# description says "our hiring partner"). `company` is None on purpose.
