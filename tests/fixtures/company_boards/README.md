# Company job board fixtures

Real responses fetched on 2026-10-18, with the app's User-Agent and no key:

- `greenhouse-vtex.json`: `boards-api.greenhouse.io/v1/boards/vtex/jobs?content=true`, with 4
  jobs: Brazil, São Paulo, Manhattan and Barcelona;
- `lever-toptal.json`: `api.lever.co/v0/postings/toptal?mode=json`, with 3 jobs: the United
  States, South America and Anywhere;
- `ashby-nubank.json`: `api.ashbyhq.com/posting-api/job-board/nubank?includeCompensation=true`,
  with 3 jobs: São Paulo, Palo Alto, and São Paulo with other Brazilian cities.

The jobs were picked by location, so the place filter has something to keep and something to
drop. Emails in the text became `jobs@example.com`, and phone-shaped numbers became
`(11) 90000-0000`. URLs and ids were left untouched.
