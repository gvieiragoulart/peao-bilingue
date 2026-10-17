# Fixtures

Real HTML from the site, captured with the user's session and **anonymized** before it entered the
repository.

## `profile.html`

Captured from `https://app.vanhack.com/profile` on 2026-10-05. It is the `.pf-main` subtree, with:

- **removed:** `.dropdown-menu` (option lists, huge and never read), `script`, `style`, `svg`,
  `img`, and the Intro Video card (`.iv-player-card`, `.iv-transcript-card`, `video`): the video
  has a URL signed with a SAS token and the transcript carries a name and a personal story;
- **anonymized:** the name ("Fulano De Tal"), email, phone, country code, passport expiration,
  visa status and the LinkedIn/GitHub links;
- **kept:** the rest of the structure and the professional data (role, skills, experience), which
  is what the tests check.

`input` values live in the DOM property, not the attribute, so the capture copies
`value`/`checked` into attributes; without that the fixture would open with every field empty.

To capture again after the site changes: open `/profile` with a valid session, repeat this
treatment and **audit the file** (`sig=`, `skoid`, `blob.core`, email, name) before committing.

## `listing.html`, `detail_12030.html`, `detail_12018.html`

Captured on 2026-10-05 from `/jobs/python-jobs` (the `div.vh-cards` container, after scrolling)
and from `/job/<id>` (the `div.vh-jd` root). `script`, `style`, `svg`, `img` and `.dropdown-menu`
were removed. They are job postings, with no user data.

`detail_12018.html` keeps the `.vh-jd-recommended` section on purpose, with minicards of **other**
jobs: it proves the extractor doesn't mix a recommended job into the open one.

When writing tests: the fixture runs without CSS, and `inner_text()` doesn't add the space inline
elements would have on the real page ("CAD $160k /yr" becomes "CAD$160k/yr").
