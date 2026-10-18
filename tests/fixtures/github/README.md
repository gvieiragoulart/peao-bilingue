# GitHub job repository fixtures

Real responses from `GET https://api.github.com/repos/<owner>/vagas/issues?state=open`,
fetched on 2026-10-18 for backend-br/vagas and phpdevbr/vagas. A few issues were kept from
each: a labeled job, one without labels, one with "na Company", and a pull request (#1331 in
phpdevbr, which the adapter skips).

They are trimmed to the fields the adapter reads (`number`, `title`, `html_url`, `state`,
`created_at`, `labels[].name`, `body`, `pull_request`). The `user` field, with the poster's
login, was removed. In the bodies, emails became `vagas@example.com` and phone numbers became
`(11) 90000-0000`. The links are the companies' public application pages.
