# Hacker News fixtures

Real responses from the HN Search API (Algolia), fetched on 2026-10-18:

- `search-threads.json`: `search_by_date?tags=story,author_whoishiring&hitsPerPage=10`, trimmed
  to its first 4 hits and to `objectID`, `title` and `created_at`. It has "Who is hiring?" and
  "Who wants to be hired?" for October and September 2026.
- `item-thread.json`: `items/49922569` ("Ask HN: Who is hiring? (October 2026)"), trimmed to 4
  of its 266 posts. One is open to LatAm; one is for the US and says it can't sponsor visas;
  one is US-only remote; one is onsite.

Usernames (`author`) became `null`, the replies under each post were removed, and emails
became `jobs@example.com`.
