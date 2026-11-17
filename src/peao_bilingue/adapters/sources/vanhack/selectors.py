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
