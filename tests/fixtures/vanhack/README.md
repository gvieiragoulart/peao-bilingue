# Fixtures

Real HTML from the site, captured with the user's session and checked for user data before it
entered the repository.

## `listing.html`, `detail_12030.html`, `detail_12018.html`

Captured on 2026-10-05 from `/jobs/python-jobs` (the `div.vh-cards` container, after scrolling)
and from `/job/<id>` (the `div.vh-jd` root). `script`, `style`, `svg`, `img` and `.dropdown-menu`
were removed. They are job postings, with no user data.

`detail_12018.html` keeps the `.vh-jd-recommended` section on purpose, with minicards of **other**
jobs: it proves the extractor doesn't mix a recommended job into the open one.

When writing tests: the fixture runs without CSS, and `inner_text()` doesn't add the space inline
elements would have on the real page ("CAD $160k /yr" becomes "CAD$160k/yr").
