# Get on Board fixture

`search-backend-remote.json` is a real response from
`https://www.getonbrd.com/api/v0/search/jobs?query=backend&remote=true&per_page=100&expand=["company"]`,
fetched on 2026-10-18 with no key. It was trimmed to 4 of its 57 jobs: one with a salary, one
without, one in Spanish, and one more. The company logos were removed. Emails and
phone-shaped numbers in the text became `jobs@example.com` and `(11) 90000-0000`; URLs were
left untouched.
